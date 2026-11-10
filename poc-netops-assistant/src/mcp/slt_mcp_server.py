import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SRC_DIR = Path(__file__).resolve().parents[1]
BASE_DIR = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ingestion.sanitizer import SovereignDataSanitizer
from retrieval.rag_engine import SovereignNetOpsRAG
from voice.voice_agent import SLTMobitelVoiceAgent


class SLTMCPToolServer:
    """
    Model Context Protocol (MCP) Server for SLTMobitel AI Platform.
    Implements MCP specification (2024-11-05) over JSON-RPC 2.0 (stdio & in-process client):
    - MCP Tools (`tools/list`, `tools/call`):
      1. `slt_sanitize_pii` — Masks Sri Lankan phone numbers, emails, IPv4 addresses, and credentials.
      2. `slt_query_cloud_kb` — Queries SLTMobitel AWS KnowledgeBase API (/prod/retrieve via CloudFront).
      3. `slt_diagnose_netops_incident` — Diagnoses BGP, OSPF, and GPON incidents against SLT SOPs.
      4. `slt_cloudfront_cache_status` — Inspects or clears the Amazon CloudFront Edge Cache.
    - MCP Resources (`resources/list`, `resources/read`):
      Exposes approved SLT NetOps SOP manuals (`slt://manuals/...`) and governance audit logs.
    """

    PROTOCOL_VERSION = "2024-11-05"
    SERVER_INFO = {
        "name": "sltmobitel-sovereign-mcp-server",
        "version": "1.0.0"
    }

    def __init__(
        self,
        manuals_dir: Path | None = None,
        sanitizer: SovereignDataSanitizer | None = None,
        rag: SovereignNetOpsRAG | None = None
    ):
        self.manuals_dir = manuals_dir or (BASE_DIR / "data" / "approved_manuals")
        self.sanitizer = sanitizer or SovereignDataSanitizer()
        self.rag = rag or SovereignNetOpsRAG(manuals_dir=self.manuals_dir, enable_embeddings=False)

    def list_tools(self) -> list[dict]:
        """Returns the MCP `tools/list` schema definitions."""
        return [
            {
                "name": "slt_sanitize_pii",
                "description": (
                    "Masks sensitive PII (Sri Lankan phone numbers, email addresses, internal IPv4 addresses, "
                    "and router credentials) before transmitting text to external cloud APIs or LLMs."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "raw_text": {
                            "type": "string",
                            "description": "Raw user query or network incident ticket text."
                        }
                    },
                    "required": ["raw_text"]
                }
            },
            {
                "name": "slt_query_cloud_kb",
                "description": (
                    "Queries the SLTMobitel AWS KnowledgeBase HTTP API (POST /prod/retrieve via Amazon CloudFront "
                    "Edge Gateway) and synthesizes a grounded answer for customer, package, billing, USSD, or router queries."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "sanitized_query": {
                            "type": "string",
                            "description": "PII-sanitized customer or product support question."
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of KnowledgeBase chunks to retrieve (1 to 5).",
                            "default": 3
                        },
                        "inference_engine": {
                            "type": "string",
                            "description": "Synthesis backend (AWS_BEDROCK, LOCAL_GROUNDED_RULE_ENGINE, GEMINI_CLOUD).",
                            "default": "AWS_BEDROCK"
                        }
                    },
                    "required": ["sanitized_query"]
                }
            },
            {
                "name": "slt_diagnose_netops_incident",
                "description": (
                    "Diagnoses network operations incident tickets against approved SLT SOP manuals "
                    "(SLT-NET-SOP-042 BGP, SLT-NET-SOP-043 OSPF, SLT-NET-SOP-044 GPON) and returns read-only CLI actions."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "sanitized_ticket": {
                            "type": "string",
                            "description": "PII-sanitized network incident log or alarm text."
                        },
                        "inference_engine": {
                            "type": "string",
                            "description": "Synthesis backend (AWS_BEDROCK, LOCAL_GROUNDED_RULE_ENGINE, GEMINI_CLOUD).",
                            "default": "AWS_BEDROCK"
                        },
                        "include_aws_kb": {
                            "type": "boolean",
                            "description": "Whether to augment local SOP retrieval with AWS Cloud KB chunks.",
                            "default": False
                        }
                    },
                    "required": ["sanitized_ticket"]
                }
            },
            {
                "name": "slt_cloudfront_cache_status",
                "description": "Returns Amazon CloudFront Edge Gateway cache hit/miss metrics or invalidates the edge cache.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["status", "invalidate"],
                            "default": "status"
                        }
                    }
                }
            },
            {
                "name": "slt_format_voice_ivr",
                "description": (
                    "Formats an assistant markdown answer and key points into a natural spoken script "
                    "and W3C SSML (<speak>...</speak>) for 1212/1717 Voice IVR & Amazon Polly TTS."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "answer_markdown": {"type": "string"},
                        "key_points": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["answer_markdown"]
                }
            }
        ]

    def list_resources(self) -> list[dict]:
        """Returns the MCP `resources/list` catalog of approved SLT NetOps SOPs."""
        resources = []
        if self.manuals_dir.exists():
            for fp in sorted(self.manuals_dir.glob("*.md")):
                resources.append({
                    "uri": f"slt://manuals/{fp.stem}",
                    "name": fp.stem.upper(),
                    "description": f"Approved SLTMobitel Technical SOP Manual ({fp.name})",
                    "mimeType": "text/markdown"
                })
        return resources

    def read_resource(self, uri: str) -> dict:
        """Reads an MCP resource by URI (`slt://manuals/<name>`)."""
        if uri.startswith("slt://manuals/"):
            stem = uri.replace("slt://manuals/", "").strip()
            target = self.manuals_dir / f"{stem}.md"
            if target.exists():
                return {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "text/markdown",
                            "text": target.read_text(encoding="utf-8")
                        }
                    ]
                }
        raise ValueError(f"MCP Resource not found: {uri}")

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        """
        Executes a registered MCP tool (`tools/call`) and returns both:
        - `structuredContent`: Raw Python dict for internal orchestrator speed
        - `content`: Standard MCP text content block array `[{"type": "text", "text": "..."}]`
        """
        args = arguments or {}

        if name == "slt_sanitize_pii":
            raw_text = str(args.get("raw_text", ""))
            res = self.sanitizer.sanitize_text(raw_text)
            return {
                "isError": False,
                "structuredContent": res,
                "content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]
            }

        if name == "slt_query_cloud_kb":
            try:
                safe_top_k = max(1, min(int(args.get("top_k", 3)), 5))
            except (TypeError, ValueError):
                safe_top_k = 3
            res = self.rag.answer_kb_question(
                sanitized_query=str(args.get("sanitized_query", "")),
                top_k=safe_top_k,
                mode_override=args.get("inference_engine"),
                ollama_model=args.get("ollama_model"),
                gemini_api_key=args.get("gemini_api_key"),
                bedrock_model=args.get("bedrock_model"),
                aws_region=args.get("aws_region"),
                aws_access_key_id=args.get("aws_access_key_id"),
                aws_secret_access_key=args.get("aws_secret_access_key"),
                kb_secret_override=args.get("kb_secret_override"),
                kb_endpoint_override=args.get("kb_endpoint_override")
            )
            return {
                "isError": False,
                "structuredContent": res,
                "content": [{"type": "text", "text": res.get("answer", "")}]
            }

        if name == "slt_diagnose_netops_incident":
            res = self.rag.analyze_incident(
                sanitized_ticket=str(args.get("sanitized_ticket", "")),
                mode_override=args.get("inference_engine"),
                ollama_model=args.get("ollama_model"),
                gemini_api_key=args.get("gemini_api_key"),
                bedrock_model=args.get("bedrock_model"),
                aws_region=args.get("aws_region"),
                aws_access_key_id=args.get("aws_access_key_id"),
                aws_secret_access_key=args.get("aws_secret_access_key"),
                include_aws_kb=bool(args.get("include_aws_kb", False)),
                kb_secret_override=args.get("kb_secret_override")
            )
            return {
                "isError": False,
                "structuredContent": res,
                "content": [{"type": "text", "text": res.get("diagnosis_summary", "")}]
            }

        if name == "slt_cloudfront_cache_status":
            action = args.get("action", "status")
            cf = self.rag.aws_kb_client.cloudfront
            if action == "invalidate":
                cf.clear_edge_cache()
            status_payload = {
                "action": action,
                "cache_type": "Local in-process TTL cache (not the Amazon CloudFront edge cache)",
                "ttl_seconds": cf.cache_ttl_seconds,
                "kb_configured": cf.is_configured,
                "metrics": dict(cf.metrics)
            }
            return {
                "isError": False,
                "structuredContent": status_payload,
                "content": [{"type": "text", "text": json.dumps(status_payload)}]
            }

        if name == "slt_format_voice_ivr":
            ans_md = str(args.get("answer_markdown", ""))
            kps = args.get("key_points") or []
            spoken = SLTMobitelVoiceAgent.format_for_speech(ans_md, kps)
            ssml = SLTMobitelVoiceAgent.build_ssml(spoken)
            voice_payload = {
                "spoken_response": spoken,
                "ssml_response": ssml
            }
            return {
                "isError": False,
                "structuredContent": voice_payload,
                "content": [{"type": "text", "text": spoken}]
            }

        return {
            "isError": True,
            "structuredContent": {"error": f"Unknown MCP tool: {name}"},
            "content": [{"type": "text", "text": f"Error: Unknown MCP tool '{name}'"}]
        }

    def handle_jsonrpc_request(self, request: dict) -> dict | None:
        """
        Handles a standard Model Context Protocol (MCP) JSON-RPC 2.0 message.
        Supports: `initialize`, `notifications/initialized`, `tools/list`, `tools/call`,
        `resources/list`, `resources/read`, and `ping`.
        """
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params") or {}

        # Notifications have no id and expect no response
        if req_id is None and method.startswith("notifications/"):
            return None

        try:
            if method == "initialize":
                result = {
                    "protocolVersion": self.PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {"listChanged": False},
                        "resources": {"subscribe": False, "listChanged": False}
                    },
                    "serverInfo": self.SERVER_INFO
                }
            elif method == "tools/list":
                result = {"tools": self.list_tools()}
            elif method == "tools/call":
                tool_name = params.get("name", "")
                tool_args = params.get("arguments") or {}
                result = self.call_tool(tool_name, tool_args)
            elif method == "resources/list":
                result = {"resources": self.list_resources()}
            elif method == "resources/read":
                uri = params.get("uri", "")
                result = self.read_resource(uri)
            elif method == "ping":
                result = {}
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": str(exc)}
            }

    def serve_stdio(self):
        """Runs the MCP Server over standard input/output (stdio) for external MCP hosts."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                resp = self.handle_jsonrpc_request(req)
                if resp is not None:
                    sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                    sys.stdout.flush()
            except Exception as exc:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {exc}"}
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()


if __name__ == "__main__":
    server = SLTMCPToolServer()
    if "--list-tools" in sys.argv:
        print(json.dumps(server.list_tools(), indent=2))
    else:
        server.serve_stdio()

