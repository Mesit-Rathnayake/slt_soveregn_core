import json
import os
import sys
import tempfile
import time
from pathlib import Path

# Ensure 'src' is on sys.path
SRC_DIR = Path(__file__).resolve().parents[1]
BASE_DIR = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent.orchestrator import SLTMobitelUnifiedAgent
from agent.governance import SovereignGovernanceManager

# Global singletons for AWS Lambda execution environment reuse across warm invocations
_AGENT_INSTANCE = None
_GOVERNANCE_INSTANCE = None

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, x-auth-secret, X-Amz-Date, X-Api-Key, X-Amz-Security-Token"
}


def _get_agent_and_governance():
    global _AGENT_INSTANCE, _GOVERNANCE_INSTANCE
    if _AGENT_INSTANCE is None:
        manuals_dir = BASE_DIR / "data" / "approved_manuals"
        default_audit = (BASE_DIR / "data" / "audit_trail.jsonl")
        if not default_audit.parent.exists() or os.name != "nt" or "PYTEST_CURRENT_TEST" in os.environ:
            # In AWS Lambda environment, read-only container, or pytest run, write to /tmp
            audit_log_path = Path(os.getenv("SLT_AUDIT_LOG_PATH", Path(tempfile.gettempdir()) / "audit_trail.jsonl"))
        else:
            audit_log_path = Path(os.getenv("SLT_AUDIT_LOG_PATH", default_audit))

        _AGENT_INSTANCE = SLTMobitelUnifiedAgent(manuals_dir=manuals_dir, enable_embeddings=False)
        _GOVERNANCE_INSTANCE = SovereignGovernanceManager(audit_log_path=audit_log_path)
    return _AGENT_INSTANCE, _GOVERNANCE_INSTANCE


def _build_response(status_code: int, payload: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(payload, ensure_ascii=False)
    }


def lambda_handler(event: dict, context=None) -> dict:
    """
    AWS Lambda Serverless Handler for SLTMobitel Sovereign AI Assistant.
    Supports:
    1. Amazon API Gateway HTTP API (Payload v2.0 & v1.0) and REST API.
    2. AWS Lambda Function URLs (direct HTTPS invoke).
    3. Direct AWS SDK invoke (`lambda.invoke()`).
    4. Model Context Protocol (MCP) JSON-RPC 2.0 messages (`jsonrpc: "2.0"`).
    5. Health check / Ping endpoint (`GET /health`).
    """
    t_start = time.perf_counter()

    # 1. Determine HTTP method and path (API Gateway v1/v2 or Function URL)
    http_method = (
        event.get("requestContext", {}).get("http", {}).get("method")
        or event.get("httpMethod")
        or "POST"
    ).upper()

    raw_path = (
        event.get("requestContext", {}).get("http", {}).get("path")
        or event.get("path")
        or ""
    ).lower()

    # Handle CORS Preflight OPTIONS
    if http_method == "OPTIONS":
        return {
            "statusCode": 204,
            "headers": CORS_HEADERS,
            "body": ""
        }

    # Handle GET /health check
    if http_method == "GET" or raw_path.endswith("/health"):
        agent, _ = _get_agent_and_governance()
        mcp_tools = [t["name"] for t in agent.mcp_server.list_tools()]
        return _build_response(200, {
            "status": "healthy",
            "service": "SLTMobitel Sovereign AI Serverless Assistant",
            "mcp_protocol_version": agent.mcp_server.PROTOCOL_VERSION,
            "mcp_tools_available": mcp_tools,
            "timestamp": time.time()
        })

    # 2. Extract and parse request body
    body_raw = event.get("body")
    if body_raw is None:
        # Direct invocation without API Gateway wrapper
        body = event
    elif isinstance(body_raw, str):
        try:
            body = json.loads(body_raw) if body_raw.strip() else {}
        except json.JSONDecodeError as exc:
            return _build_response(400, {
                "error": "Bad Request: Invalid JSON in request body",
                "details": str(exc)
            })
    elif isinstance(body_raw, dict):
        body = body_raw
    else:
        body = {}

    agent, governance = _get_agent_and_governance()

    # 3. Check if this is an MCP JSON-RPC 2.0 request (e.g. tools/list, tools/call)
    if body.get("jsonrpc") == "2.0" and "method" in body:
        mcp_res = agent.mcp_server.handle_jsonrpc_request(body)
        if mcp_res is None:
            return _build_response(204, {})
        return _build_response(200, mcp_res)

    # 3B. Check if this is an Amazon Connect Contact Flow IVR Event or POST /voice request
    connect_params = body.get("Details", {}).get("Parameters", {})
    is_voice_route = raw_path.endswith("/voice") or bool(connect_params) or bool(body.get("voice_mode"))
    if connect_params and not body.get("user_input"):
        body["user_input"] = (
            connect_params.get("transcript")
            or connect_params.get("inputTranscript")
            or connect_params.get("CustomerInput")
            or ""
        )

    # 4. Standard Assistant Chat / Voice / Query Invocation
    user_input = (
        body.get("user_input")
        or body.get("transcript")
        or body.get("prompt")
        or body.get("query")
        or body.get("ticket")
        or ""
    )

    if not isinstance(user_input, str) or not user_input.strip():
        return _build_response(400, {
            "error": "Missing required field: 'user_input' (or 'prompt' / 'query').",
            "example_payload": {
                "user_input": "What are the SLTMobitel 4G LTE & PEOTV package prices?",
                "route_mode": "AUTO",
                "inference_engine": "AWS_BEDROCK",
                "top_k": 3
            }
        })

    route_mode = str(body.get("route_mode", "AUTO"))
    inference_engine = str(body.get("inference_engine", "AWS_BEDROCK"))
    top_k = int(body.get("top_k", 3))
    conversation_history = body.get("conversation_history") or []
    active_role = str(body.get("role", "Tier-1 NOC / Support Agent"))

    # Optional overrides
    bedrock_model = body.get("bedrock_model")
    gemini_key = body.get("gemini_api_key")
    aws_region = body.get("aws_region")
    aws_ak = body.get("aws_access_key_id")
    aws_sk = body.get("aws_secret_access_key")
    kb_secret = body.get("kb_secret_override")
    kb_endpoint = body.get("kb_endpoint_override")

    try:
        turn_res = agent.run_agent(
            user_input=user_input.strip(),
            route_mode=route_mode,
            inference_engine=inference_engine,
            top_k=top_k,
            conversation_history=conversation_history,
            gemini_api_key=gemini_key,
            bedrock_model=bedrock_model,
            aws_region=aws_region,
            aws_access_key_id=aws_ak,
            aws_secret_access_key=aws_sk,
            kb_secret_override=kb_secret,
            kb_endpoint_override=kb_endpoint
        )

        governance.log_event(
            user_role=active_role,
            action_type=f"LAMBDA_{turn_res['intent_route']}",
            ticket_id="LAMBDA-API",
            redactions_count=turn_res["redactions_applied"],
            severity=turn_res["severity"],
            citations=turn_res["citations"],
            latency_ms=turn_res["latency_ms"],
            engine_mode=turn_res["inference_mode"]
        )

        total_latency_ms = round((time.perf_counter() - t_start) * 1000, 1)

        if turn_res.get("escalation_required"):
            ivr_queue = "SLT_NOC_TIER3_EMERGENCY_QUEUE"
        elif not turn_res.get("has_enough_knowledge", True):
            ivr_queue = "SLT_1212_HUMAN_AGENT_QUEUE"
        else:
            ivr_queue = "SELF_SERVICE_COMPLETED"

        return _build_response(200, {
            "success": True,
            "voice_mode": is_voice_route,
            "answer": turn_res["answer_markdown"],
            "spoken_response": turn_res.get("spoken_response", ""),
            "ssml_response": turn_res.get("ssml_response", ""),
            "ivr_queue_action": ivr_queue,
            "key_points": turn_res.get("key_points", []),
            "intent_route": turn_res["intent_route"],
            "mcp_tool_called": turn_res.get("mcp_tool_called"),
            "inference_mode": turn_res["inference_mode"],
            "has_enough_knowledge": turn_res.get("has_enough_knowledge", True),
            "escalation_required": turn_res.get("escalation_required", False),
            "escalation_target": turn_res.get("escalation_target", "None"),
            "citations": turn_res.get("citations", []),
            "redactions_applied": turn_res.get("redactions_applied", 0),
            "suggested_followups": turn_res.get("suggested_followups", []),
            "latency_ms": total_latency_ms
        })
    except Exception as exc:
        return _build_response(500, {
            "success": False,
            "error": "Internal Server Error during AI agent execution",
            "details": str(exc)
        })


if __name__ == "__main__":
    # Local CLI test
    test_event = {
        "httpMethod": "POST",
        "path": "/chat",
        "body": json.dumps({"user_input": "How do I check my data balance?"})
    }
    resp = lambda_handler(test_event)
    print("Lambda Response:", json.dumps(resp, indent=2))
