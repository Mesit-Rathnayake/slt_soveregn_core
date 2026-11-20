import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

SRC_DIR = Path(__file__).resolve().parents[1]
BASE_DIR = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent.governance import SovereignGovernanceManager
from agent.orchestrator import SLTMobitelUnifiedAgent
from retrieval.cloudfront_gateway import SLTCloudFrontEdgeGateway

manuals_dir = BASE_DIR / "data" / "approved_manuals"
audit_log_path = BASE_DIR / "data" / "audit_trail.jsonl"

agent = SLTMobitelUnifiedAgent(manuals_dir=manuals_dir, enable_embeddings=False)
if not hasattr(agent.rag.aws_kb_client, "cloudfront"):
    agent.rag.aws_kb_client.cloudfront = SLTCloudFrontEdgeGateway(env_path=BASE_DIR / ".env")
governance = SovereignGovernanceManager(audit_log_path=audit_log_path)

app = FastAPI(
    title="SLTMobitel Sovereign AI Platform API",
    version="1.0.0",
    description="FastAPI backend for the SLTMobitel React Customer & NetOps AI Portal."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    user_input: str = Field(..., min_length=1, max_length=4000)
    user_role: str = Field(default="Existing Customer")
    route_mode: str = Field(default="AUTO")
    inference_engine: str = Field(default_factory=lambda: os.getenv("AI_INFERENCE_MODE", "LOCAL_GROUNDED_RULE_ENGINE"))
    top_k: int = Field(default=3, ge=1, le=5)
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)
    session_memory: dict[str, Any] = Field(default_factory=dict)


class FaultTicketRequest(BaseModel):
    account_number: str = Field(default="SLT-ACC-0112456789")
    service_type: str = Field(default="Fibre")
    fault_category: str = Field(default="General Connectivity Fault")
    led_status: str = Field(default="Not Specified")
    router_restarted: bool = Field(default=False)
    affected_devices: str = Field(default="All Devices")
    issue_started: str = Field(default="Today")
    impact_level: str = Field(default="High (Household Outage)")
    issue_description: str = Field(..., min_length=3, max_length=2000)
    contact_name: str = Field(default="Kasun Perera")
    contact_number: str = Field(default="071 234 5678")
    service_address: str = Field(default="Registered Premises Address")
    preferred_visit_slot: str = Field(default="Anytime (08:00 - 18:00)")
    user_role: str = Field(default="Existing Customer")


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=3000)


@app.get("/api/health")
def health_check():
    tools = [t["name"] for t in agent.mcp_server.list_tools()]
    cf_metrics = agent.rag.aws_kb_client.cloudfront.metrics
    return {
        "status": "healthy",
        "service": "SLTMobitel Sovereign AI Platform",
        "mcp_tools": tools,
        "crm_live_mode": agent.mcp_server.account_gateway.is_live_crm_enabled,
        "edge_cache": cf_metrics,
    }


@app.get("/api/roles")
def list_roles():
    return {
        "roles": SovereignGovernanceManager.ROLES
    }


@app.post("/api/chat")
def chat(req: ChatRequest):
    if req.user_role not in SovereignGovernanceManager.ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role: {req.user_role}")

    turn_res = agent.run_agent(
        user_input=req.user_input.strip(),
        route_mode=req.route_mode,
        inference_engine=req.inference_engine,
        top_k=req.top_k,
        conversation_history=req.conversation_history[-10:],
        session_memory=req.session_memory,
        user_role=req.user_role,
    )

    governance.log_event(
        user_role=req.user_role,
        action_type=f"WEB_{turn_res['intent_route']}",
        ticket_id="WEB-CHAT",
        redactions_count=turn_res["redactions_applied"],
        severity=turn_res["severity"],
        citations=turn_res["citations"],
        latency_ms=turn_res["latency_ms"],
        engine_mode=turn_res["inference_mode"],
    )

    return turn_res


@app.get("/api/account/{account_id}")
def get_account(account_id: str, x_user_role: str = Header(default="Existing Customer")):
    if not governance.check_permission(x_user_role, "can_view_account_stats"):
        raise HTTPException(
            status_code=403,
            detail="Account overview requires an Existing Customer subscription or authorized staff role."
        )
    return agent.mcp_server.account_gateway.get_account_profile(account_id)


@app.post("/api/tickets")
def create_ticket(req: FaultTicketRequest):
    if not governance.check_permission(req.user_role, "can_log_fault_tickets"):
        raise HTTPException(
            status_code=403,
            detail="Fault ticket creation is restricted to Existing Customers and NOC Support Agents."
        )
    res = agent.mcp_server.account_gateway.create_fault_ticket(
        identifier=req.account_number,
        service_type=req.service_type,
        issue_description=req.issue_description,
        contact_number=req.contact_number,
        fault_category=req.fault_category,
        led_status=req.led_status,
        router_restarted=req.router_restarted,
        affected_devices=req.affected_devices,
        issue_started=req.issue_started,
        impact_level=req.impact_level,
        contact_name=req.contact_name,
        service_address=req.service_address,
        preferred_visit_slot=req.preferred_visit_slot,
    )
    governance.log_event(
        user_role=req.user_role,
        action_type="FAULT_TICKET_CREATED",
        ticket_id=res["ticket_id"],
        redactions_count=0,
        severity=res["ticket_details"]["priority"],
        citations=["SLTMobitel CSM"],
        latency_ms=1.0,
        engine_mode="STRUCTURED_FAULT_TICKET",
    )
    return res


@app.get("/api/tickets/{ticket_id}")
def get_ticket(ticket_id: str, x_user_role: str = Header(default="Existing Customer")):
    if not governance.check_permission(x_user_role, "can_view_account_stats"):
        raise HTTPException(
            status_code=403,
            detail="Ticket status lookup is restricted to Existing Customers and authorized staff."
        )
    return agent.mcp_server.account_gateway.get_ticket_status(ticket_id)


@app.post("/api/voice/tts")
def synthesize_tts(req: TTSRequest):
    mp3_bytes = agent.voice_agent.synthesize_speech_mp3(req.text)
    if not mp3_bytes:
        raise HTTPException(status_code=503, detail="TTS synthesis unavailable.")
    return Response(content=mp3_bytes, media_type="audio/mpeg")


@app.get("/api/audit-logs")
def get_audit_logs(limit: int = 30, x_user_role: str = Header(default="Tier-2 Core Engineer")):
    if not governance.check_permission(x_user_role, "can_view_audit_logs"):
        raise HTTPException(status_code=403, detail="Audit logs require Tier-2 Engineer or Auditor role.")
    return {"logs": governance.read_audit_logs(limit=limit)}


# Serve built React frontend in production if dist/ exists
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
