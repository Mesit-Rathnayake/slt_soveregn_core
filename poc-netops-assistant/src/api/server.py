import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Header, Request
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
from api.security import SovereignTokenManager, SlidingWindowRateLimiter
from retrieval.cloudfront_gateway import SLTCloudFrontEdgeGateway

manuals_dir = BASE_DIR / "data" / "approved_manuals"
audit_log_path = BASE_DIR / "data" / "audit_trail.jsonl"

agent = SLTMobitelUnifiedAgent(manuals_dir=manuals_dir, enable_embeddings=False)
if not hasattr(agent.rag.aws_kb_client, "cloudfront"):
    agent.rag.aws_kb_client.cloudfront = SLTCloudFrontEdgeGateway(env_path=BASE_DIR / ".env")
governance = SovereignGovernanceManager(audit_log_path=audit_log_path)
token_manager = SovereignTokenManager()
rate_limiter = SlidingWindowRateLimiter()

IS_PRODUCTION = os.getenv("SLT_ENV", "dev").strip().lower() == "prod"
STAFF_ACCESS_PIN = os.getenv("SLT_STAFF_ACCESS_PIN", "SLT-OPS-2026").strip()

allowed_origins_env = os.getenv(
    "SLT_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
)
ALLOWED_ORIGINS = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]

app = FastAPI(
    title="SLTMobitel Sovereign AI Platform API",
    version="1.1.0",
    description="Hardened FastAPI backend for SLTMobitel Customer & Technical Officer Portal.",
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-User-Role"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


def _client_ip(request: Request | None) -> str:
    if request is None:
        return "local-test"
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"


def _enforce_rate_limit(bucket: str, max_requests: int, window_seconds: int):
    allowed, retry_after = rate_limiter.allow(bucket, max_requests, window_seconds)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Please wait {retry_after} seconds and try again.",
            headers={"Retry-After": str(retry_after)},
        )


def _resolve_identity(
    authorization: str | None,
    fallback_role: str | None,
    *,
    allow_anonymous_new_customer: bool = False,
) -> dict:
    """
    Resolves caller identity:
    - If Authorization: Bearer <token> is supplied, cryptographically verifies signature & expiry.
    - In production (SLT_ENV=prod), privileged roles strictly require a verified Bearer token.
    - In local dev / test mode, allows fallback_role when no Authorization header is sent.
    """
    if authorization and isinstance(authorization, str) and authorization.strip().lower().startswith("bearer "):
        raw_token = authorization.strip()[7:].strip()
        payload = token_manager.verify_token(raw_token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired session token. Please sign in again.")
        return {
            "role": payload["role"],
            "subject": payload.get("sub", ""),
            "service_segment": payload.get("seg", "Fibre"),
            "authenticated": True,
        }

    role = fallback_role or ("New Customer" if allow_anonymous_new_customer else "")
    if IS_PRODUCTION and role != "New Customer":
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please verify via OTP or Staff Login."
        )
    return {
        "role": role,
        "subject": "",
        "service_segment": None,
        "authenticated": False,
    }


class ChatRequest(BaseModel):
    user_input: str = Field(..., min_length=1, max_length=4000)
    user_role: str = Field(default="Existing Customer")
    service_segment: str = Field(default="Fibre")
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


class OfficerTicketUpdateRequest(BaseModel):
    status: str | None = Field(default=None)
    officer_name: str = Field(default="Eng. Nimal Silva")
    contact_channel: str = Field(default="Phone Call")
    customer_message: str = Field(default="")
    internal_note: str = Field(default="")
    user_role: str = Field(default="Technical Officer")


class OTPRequestModel(BaseModel):
    connection_number: str = Field(..., min_length=9, max_length=15)
    channel: str = Field(default="SMS")


class OTPVerifyModel(BaseModel):
    connection_number: str = Field(..., min_length=9, max_length=15)
    otp_code: str = Field(..., min_length=4, max_length=8)


class StaffLoginModel(BaseModel):
    role: str = Field(default="Technical Officer")
    staff_id: str = Field(default="TO-101")
    display_name: str = Field(default="Eng. Nimal Silva")
    access_pin: str = Field(default="")


class OfficerOTPRequestModel(BaseModel):
    staff_id: str = Field(..., min_length=3, max_length=60)
    channel: str = Field(default="SMS")


class OfficerOTPVerifyModel(BaseModel):
    staff_id: str = Field(..., min_length=3, max_length=60)
    otp_code: str = Field(..., min_length=4, max_length=8)


@app.get("/api/health")
def health_check():
    tools = [t["name"] for t in agent.mcp_server.list_tools()]
    cf_metrics = agent.rag.aws_kb_client.cloudfront.metrics
    return {
        "status": "healthy",
        "service": "SLTMobitel Sovereign AI Platform",
        "environment": "prod" if IS_PRODUCTION else "dev",
        "mcp_tools": tools,
        "crm_live_mode": agent.mcp_server.account_gateway.is_live_crm_enabled,
        "edge_cache": cf_metrics,
    }


@app.get("/api/roles")
def list_roles():
    return {
        "roles": SovereignGovernanceManager.ROLES
    }


@app.post("/api/auth/request-otp")
def auth_request_otp(req: OTPRequestModel, request: Request = None):
    ip = _client_ip(request)
    _enforce_rate_limit(f"otp_req_ip:{ip}", max_requests=10, window_seconds=300)
    _enforce_rate_limit(f"otp_req_num:{req.connection_number}", max_requests=5, window_seconds=300)
    try:
        return agent.mcp_server.account_gateway.request_otp(
            connection_number=req.connection_number,
            channel=req.channel,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/auth/verify-otp")
def auth_verify_otp(req: OTPVerifyModel, request: Request = None):
    ip = _client_ip(request)
    _enforce_rate_limit(f"otp_ver_ip:{ip}", max_requests=15, window_seconds=300)
    res = agent.mcp_server.account_gateway.verify_otp(
        connection_number=req.connection_number,
        otp_code=req.otp_code,
    )
    if not res.get("verified"):
        raise HTTPException(status_code=401, detail=res.get("error", "OTP verification failed."))

    access_token = token_manager.issue_token(
        role="Existing Customer",
        subject=res["connection_number"],
        service_segment=res["service_segment"],
        display_name=res["profile"].get("customer_name", ""),
    )
    return {**res, "access_token": access_token, "token_type": "Bearer"}


@app.post("/api/auth/officer/request-otp")
def auth_officer_request_otp(req: OfficerOTPRequestModel, request: Request = None):
    ip = _client_ip(request)
    _enforce_rate_limit(f"officer_otp_ip:{ip}", max_requests=10, window_seconds=300)
    _enforce_rate_limit(f"officer_otp_id:{req.staff_id.upper()}", max_requests=5, window_seconds=300)
    try:
        return agent.mcp_server.account_gateway.request_officer_otp(
            staff_id=req.staff_id,
            channel=req.channel,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/auth/officer/verify-otp")
def auth_officer_verify_otp(req: OfficerOTPVerifyModel, request: Request = None):
    ip = _client_ip(request)
    _enforce_rate_limit(f"officer_ver_ip:{ip}", max_requests=15, window_seconds=300)
    res = agent.mcp_server.account_gateway.verify_officer_otp(
        staff_id=req.staff_id,
        otp_code=req.otp_code,
    )
    if not res.get("verified"):
        raise HTTPException(status_code=401, detail=res.get("error", "Officer OTP verification failed."))

    access_token = token_manager.issue_token(
        role="Technical Officer",
        subject=res["staff_id"],
        service_segment="All",
        display_name=res["display_name"],
    )
    return {**res, "access_token": access_token, "token_type": "Bearer"}


@app.post("/api/auth/staff-login")
def auth_staff_login(req: StaffLoginModel, request: Request = None):
    ip = _client_ip(request)
    _enforce_rate_limit(f"staff_login:{ip}", max_requests=10, window_seconds=300)
    allowed_staff_roles = {
        "Technical Officer",
        "Tier-1 NOC / Support Agent",
        "Tier-2 Core Engineer",
        "Sovereign Cloud Auditor",
    }
    if req.role not in allowed_staff_roles:
        raise HTTPException(status_code=400, detail="Invalid staff role.")
    if IS_PRODUCTION and req.access_pin != STAFF_ACCESS_PIN:
        raise HTTPException(status_code=401, detail="Invalid staff access PIN.")

    access_token = token_manager.issue_token(
        role=req.role,
        subject=req.staff_id,
        service_segment="All",
        display_name=req.display_name,
    )
    return {
        "authenticated": True,
        "role": req.role,
        "staff_id": req.staff_id,
        "display_name": req.display_name,
        "access_token": access_token,
        "token_type": "Bearer",
    }


@app.post("/api/chat")
def chat(
    req: ChatRequest,
    authorization: str | None = Header(default=None),
    request: Request = None,
):
    ip = _client_ip(request)
    _enforce_rate_limit(f"chat:{ip}", max_requests=30, window_seconds=60)

    ident = _resolve_identity(
        authorization,
        req.user_role,
        allow_anonymous_new_customer=True,
    )
    effective_role = ident["role"]
    effective_segment = ident["service_segment"] or req.service_segment

    if effective_role not in SovereignGovernanceManager.ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role: {effective_role}")
    if not governance.check_permission(effective_role, "can_use_ai_agent"):
        raise HTTPException(
            status_code=403,
            detail="AI Assistant access is not enabled for the Technical Officer role. Use the Fault Ticket Review Queue."
        )

    turn_res = agent.run_agent(
        user_input=req.user_input.strip(),
        route_mode=req.route_mode,
        inference_engine=req.inference_engine,
        top_k=req.top_k,
        conversation_history=req.conversation_history[-10:],
        session_memory=req.session_memory,
        user_role=effective_role,
        service_segment=effective_segment,
    )

    governance.log_event(
        user_role=effective_role,
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
def get_account(
    account_id: str,
    service_segment: str | None = None,
    x_user_role: str = Header(default="Existing Customer"),
    authorization: str | None = Header(default=None),
):
    ident = _resolve_identity(authorization, x_user_role)
    effective_role = ident["role"]
    if not governance.check_permission(effective_role, "can_view_account_stats"):
        raise HTTPException(
            status_code=403,
            detail="Account overview requires an Existing Customer subscription or authorized staff role."
        )

    # IDOR Protection: Authenticated Existing Customers may only query their own verified connection
    if ident["authenticated"] and effective_role == "Existing Customer" and ident["subject"]:
        req_digits = agent.mcp_server.account_gateway._normalize_connection_number(account_id)
        sub_digits = agent.mcp_server.account_gateway._normalize_connection_number(ident["subject"])
        if req_digits != sub_digits:
            raise HTTPException(
                status_code=403,
                detail="Access denied: you may only view your own verified connection account."
            )

    return agent.mcp_server.account_gateway.get_account_profile(account_id, service_segment=service_segment)


@app.post("/api/tickets")
def create_ticket(
    req: FaultTicketRequest,
    authorization: str | None = Header(default=None),
    request: Request = None,
):
    ip = _client_ip(request)
    _enforce_rate_limit(f"ticket_create:{ip}", max_requests=10, window_seconds=60)

    ident = _resolve_identity(authorization, req.user_role)
    effective_role = ident["role"]
    if not governance.check_permission(effective_role, "can_log_fault_tickets"):
        raise HTTPException(
            status_code=403,
            detail="Fault ticket creation is restricted to Existing Customers and NOC Support Agents."
        )

    target_account = ident["subject"] if (ident["authenticated"] and effective_role == "Existing Customer" and ident["subject"]) else req.account_number

    res = agent.mcp_server.account_gateway.create_fault_ticket(
        identifier=target_account,
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
        user_role=effective_role,
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
def get_ticket(
    ticket_id: str,
    x_user_role: str = Header(default="Existing Customer"),
    authorization: str | None = Header(default=None),
):
    ident = _resolve_identity(authorization, x_user_role)
    if not governance.check_permission(ident["role"], "can_view_account_stats"):
        raise HTTPException(
            status_code=403,
            detail="Ticket status lookup is restricted to Existing Customers and authorized staff."
        )
    return agent.mcp_server.account_gateway.get_ticket_status(ticket_id)


@app.get("/api/officer/workloads")
def officer_workloads(
    x_user_role: str = Header(default="Technical Officer"),
    authorization: str | None = Header(default=None),
):
    ident = _resolve_identity(authorization, x_user_role)
    if not governance.check_permission(ident["role"], "can_manage_fault_tickets"):
        raise HTTPException(
            status_code=403,
            detail="Officer workload metrics are restricted to Technical Officers and NOC Engineers."
        )
    return agent.mcp_server.account_gateway.get_officer_workloads()


@app.get("/api/officer/tickets")
def officer_list_tickets(
    status: str | None = None,
    officer: str | None = None,
    x_user_role: str = Header(default="Technical Officer"),
    authorization: str | None = Header(default=None),
):
    ident = _resolve_identity(authorization, x_user_role)
    if not governance.check_permission(ident["role"], "can_manage_fault_tickets"):
        raise HTTPException(
            status_code=403,
            detail="Fault ticket queue management is restricted to Technical Officers and NOC Engineers."
        )
    tickets = agent.mcp_server.account_gateway.list_all_tickets(
        status_filter=status,
        officer_filter=officer,
    )
    workloads = agent.mcp_server.account_gateway.get_officer_workloads()
    return {"count": len(tickets), "tickets": tickets, "workloads": workloads}


@app.patch("/api/officer/tickets/{ticket_id}")
def officer_update_ticket(
    ticket_id: str,
    req: OfficerTicketUpdateRequest,
    authorization: str | None = Header(default=None),
):
    ident = _resolve_identity(authorization, req.user_role)
    if not governance.check_permission(ident["role"], "can_manage_fault_tickets"):
        raise HTTPException(
            status_code=403,
            detail="Only Technical Officers and NOC Engineers can update fault tickets or log customer contacts."
        )
    try:
        updated = agent.mcp_server.account_gateway.update_ticket(
            ticket_id=ticket_id,
            status=req.status,
            officer_name=req.officer_name,
            contact_channel=req.contact_channel,
            customer_message=req.customer_message,
            internal_note=req.internal_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail=f"Fault ticket '{ticket_id}' not found.")
    governance.log_event(
        user_role=ident["role"],
        action_type="OFFICER_TICKET_UPDATE",
        ticket_id=ticket_id,
        redactions_count=0,
        severity=updated["priority"],
        citations=["SLTMobitel CSM"],
        latency_ms=1.0,
        engine_mode="OFFICER_TICKET_CONSOLE",
    )
    return {"updated": True, "ticket": updated, "workloads": agent.mcp_server.account_gateway.get_officer_workloads()}


@app.post("/api/voice/tts")
def synthesize_tts(req: TTSRequest, request: Request = None):
    ip = _client_ip(request)
    _enforce_rate_limit(f"tts:{ip}", max_requests=20, window_seconds=60)
    mp3_bytes = agent.voice_agent.synthesize_speech_mp3(req.text)
    if not mp3_bytes:
        raise HTTPException(status_code=503, detail="TTS synthesis unavailable.")
    return Response(content=mp3_bytes, media_type="audio/mpeg")


@app.get("/api/audit-logs")
def get_audit_logs(
    limit: int = 30,
    x_user_role: str = Header(default="Tier-2 Core Engineer"),
    authorization: str | None = Header(default=None),
):
    ident = _resolve_identity(authorization, x_user_role)
    if not governance.check_permission(ident["role"], "can_view_audit_logs"):
        raise HTTPException(status_code=403, detail="Audit logs require Tier-2 Engineer or Auditor role.")
    return {"logs": governance.read_audit_logs(limit=limit)}


# Serve built React frontend in production if dist/ exists
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=not IS_PRODUCTION)
