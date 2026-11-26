import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def load_dotenv_file(env_path: Path | None = None):
    """Lightweight .env + Streamlit Secrets loader with zero external dependencies."""
    if env_path and env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    # Also load from Streamlit Cloud Secrets (st.secrets) if available
    try:
        import streamlit as st
        for k, v in st.secrets.items():
            if isinstance(v, (str, int, float, bool)):
                os.environ.setdefault(str(k).strip(), str(v).strip())
    except Exception:
        pass


class SovereignLLMGateway:
    """
    SLTMobitel Cloud AI LLM Gateway (AWS Bedrock & Google Gemini).
    Supports:
    - AWS Bedrock Runtime (Claude 3 Haiku / Sonnet, Amazon Titan, Meta Llama 3 via boto3)
    - Google Gemini Cloud API
    """

    BEDROCK_MODELS = [
        "anthropic.claude-3-haiku-20240307-v1:0",
        "anthropic.claude-3-5-sonnet-20240620-v1:0",
        "amazon.nova-lite-v1:0",
        "amazon.nova-pro-v1:0",
        "amazon.titan-text-express-v1",
        "meta.llama3-8b-instruct-v1:0"
    ]

    def __init__(self, env_path: Path | None = None):
        if env_path:
            load_dotenv_file(env_path)
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        self.aws_region = os.getenv("AWS_REGION", "us-east-1")
        self.aws_bedrock_model = os.getenv(
            "AWS_BEDROCK_MODEL_ID",
            "anthropic.claude-3-haiku-20240307-v1:0"
        )

    @staticmethod
    def _is_valid_secret(val: str | None) -> bool:
        if not val:
            return False
        cleaned = val.strip()
        return bool(cleaned) and "PASTE_YOUR" not in cleaned.upper() and "REPLACE_ME" not in cleaned.upper()

    def get_status(self) -> dict:
        """Returns non-sensitive readiness status for AWS Bedrock and Google Gemini."""
        ak = os.getenv("AWS_ACCESS_KEY_ID", "")
        sk = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        gk = os.getenv("GEMINI_API_KEY", "") or self.gemini_key
        active_mode = os.getenv("AI_INFERENCE_MODE", "AWS_BEDROCK").strip()
        try:
            import importlib.util
            boto3_ok = bool(importlib.util.find_spec("boto3"))
        except Exception:
            boto3_ok = False
        bedrock_ready = boto3_ok and self._is_valid_secret(ak) and self._is_valid_secret(sk)
        gemini_ready = self._is_valid_secret(gk)
        return {
            "active_mode": active_mode,
            "aws_bedrock_configured": bedrock_ready,
            "aws_bedrock_model": os.getenv("AWS_BEDROCK_MODEL_ID", self.aws_bedrock_model),
            "aws_region": os.getenv("AWS_REGION", self.aws_region),
            "boto3_installed": boto3_ok,
            "gemini_configured": gemini_ready,
            "gemini_model": os.getenv("GEMINI_MODEL", self.gemini_model),
            "live_llm_ready": (active_mode == "AWS_BEDROCK" and bedrock_ready) or (active_mode == "GEMINI_CLOUD" and gemini_ready),
        }

    def test_connection(self, mode: str | None = None) -> dict:
        """Runs a lightweight JSON-grounded ping against the configured LLM backend."""
        target_mode = (mode or os.getenv("AI_INFERENCE_MODE", "AWS_BEDROCK")).strip()
        ping_prompt = (
            'Respond ONLY with valid JSON: {"status": "ok", "engine": "' + target_mode + '", '
            '"message": "SLTMobitel SovereignLLMGateway connected."}'
        )
        try:
            if target_mode == "AWS_BEDROCK":
                res = self.generate_with_bedrock(ping_prompt)
            elif target_mode == "GEMINI_CLOUD":
                res = self.generate_with_gemini(ping_prompt)
            else:
                return {"connected": False, "mode": target_mode, "error": f"Unsupported mode: {target_mode}"}
            return {"connected": True, "mode": target_mode, "response": res}
        except Exception as exc:
            return {"connected": False, "mode": target_mode, "error": str(exc)}

    @staticmethod
    def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _extract_json_dict(raw_text: str) -> dict:
        """Safely extracts a JSON object from LLM text output even if wrapped in markdown fences."""
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise

    def build_grounded_prompt(self, sanitized_ticket: str, retrieved_chunks: list[dict]) -> str:
        context_blocks = []
        for c in retrieved_chunks:
            context_blocks.append(f"[{c['doc_id']} - {c['section']}]\n{c['content']}")
        context_str = "\n\n".join(context_blocks)

        return f"""You are a Network Operations (NetOps) AI Assistant.
Analyze the NETWORK REQUEST / TICKET below using ONLY the APPROVED SOP CONTEXT provided.

STRICT RULES:
1. If the user's question is general or NOT covered by the provided SOPs, set "has_enough_knowledge" to false, "escalation_required" to false, and set "diagnosis_summary" to: "I don't have enough knowledge to answer that question."
2. Write every item in "recommended_actions" as a plain, complete English sentence (NEVER output nested JSON objects or placeholder words like "First step with").
3. Enforce Read-Only Advisory Mode: never recommend autonomous configuration changes or clearing routing processes.
4. Respond ONLY with a valid JSON object matching this exact schema:
{{
  "has_enough_knowledge": true,
  "severity": "CRITICAL",
  "escalation_required": true,
  "escalation_target": "Tier-3 Core Transport Team",
  "diagnosis_summary": "Clear 2-sentence explanation of the root cause based on the SOP thresholds.",
  "recommended_actions": [
    "Escalate immediately to the relevant engineering team as specified in the SOP.",
    "Run the read-only CLI verification command from the SOP to check interface or protocol status.",
    "Do not reset interfaces or clear routing processes on production routers."
  ]
}}

=== APPROVED SOP CONTEXT ===
{context_str}

=== NETWORK REQUEST / TICKET ===
{sanitized_ticket}
"""

    def build_kb_qa_prompt(self, sanitized_query: str, retrieved_chunks: list[dict]) -> str:
        context_blocks = []
        for idx, c in enumerate(retrieved_chunks, 1):
            context_blocks.append(f"--- PASSAGE {idx} ---\n{c['content'].strip()}")
        context_str = "\n\n".join(context_blocks) if context_blocks else "No relevant information found."

        return f"""You are a helpful, direct AI assistant.
Answer the USER QUESTION clearly, naturally, and concisely using the reference information below. Do not use robotic phrases like "according to the knowledge base", "in our knowledge base", or unsolicited corporate disclaimers.

STRICT RULES:
1. Answer ONLY if the reference passages actually contain the information needed to answer the USER QUESTION.
2. If the user is following up on a troubleshooting session (e.g., reporting that the power socket is fine, the router is on with no connection, internet is slow, or they already restarted it), acknowledge their update and suggest ONLY the next steps that actually appear in the passages that they have not tried yet.
3. NEVER add facts, prices, USSD codes, LED names, timings, phone numbers or procedures that are not written in the passages.
4. If the passages are unrelated to the user's question, set "has_enough_knowledge" to false and set "answer" to: "I don't have enough knowledge to answer that question."
5. Write in clean, natural, human-friendly English. Do NOT dump raw database text, chunk IDs, or technical metadata.
6. Respond ONLY with a valid JSON object matching this exact schema:
{{
  "has_enough_knowledge": true,
  "answer": "A clear, friendly, direct answer to the user's question.",
  "key_points": [
    "Short, helpful bullet point 1 (leave empty [] if has_enough_knowledge is false)",
    "Short, helpful bullet point 2"
  ],
  "follow_up_suggestion": ""
}}

=== REFERENCE PASSAGES ===
{context_str}

=== USER QUESTION ===
{sanitized_query}
"""

    def generate_with_bedrock(
        self,
        prompt: str,
        model_override: str | None = None,
        aws_region: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None
    ) -> dict:
        """Generates structured JSON output using AWS Bedrock Runtime (Converse API / InvokeModel)."""
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 is required for AWS_BEDROCK mode. Run 'pip install boto3'.") from exc

        model_id = model_override or self.aws_bedrock_model
        region = aws_region or self.aws_region

        session_kwargs = {"region_name": region}
        ak = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID", "")
        sk = aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY", "")
        st_tok = aws_session_token or os.getenv("AWS_SESSION_TOKEN", "")

        if ak and "PASTE_YOUR" not in ak and sk and "PASTE_YOUR" not in sk:
            session_kwargs["aws_access_key_id"] = ak.strip()
            session_kwargs["aws_secret_access_key"] = sk.strip()
            if st_tok:
                session_kwargs["aws_session_token"] = st_tok.strip()

        client = boto3.client("bedrock-runtime", **session_kwargs)

        if hasattr(client, "converse"):
            resp = client.converse(
                modelId=model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"temperature": 0.1, "maxTokens": 1024}
            )
            raw_text = resp["output"]["message"]["content"][0]["text"]
            return self._extract_json_dict(raw_text)

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "temperature": 0.1,
            "messages": [{"role": "user", "content": prompt}]
        })
        resp = client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=body
        )
        resp_body = json.loads(resp["body"].read().decode("utf-8"))
        raw_text = resp_body["content"][0]["text"]
        return self._extract_json_dict(raw_text)

    def generate_with_gemini(self, prompt: str, api_key_override: str | None = None) -> dict:
        api_key = api_key_override or os.getenv("GEMINI_API_KEY", "") or self.gemini_key
        if not self._is_valid_secret(api_key):
            raise ValueError("Missing valid GEMINI_API_KEY in .env or sidebar input.")

        primary_model = os.getenv("GEMINI_MODEL", self.gemini_model).strip() or "gemini-3.8-flash"
        candidate_models = []
        for m in (primary_model, "gemini-3.1-flash-lite", "gemini-flash-latest"):
            if m and m not in candidate_models:
                candidate_models.append(m)

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }
        payload_bytes = json.dumps(payload).encode("utf-8")
        last_err = None
        body = None

        for model_name in candidate_models:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model_name}:generateContent"
            )
            req = urllib.request.Request(
                url,
                data=payload_bytes,
                # Send the key as a header, not in the URL, so it never appears in logs/proxies/tracebacks.
                headers={"Content-Type": "application/json", "x-goog-api-key": api_key.strip()},
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    self.gemini_model = model_name
                    break
            except urllib.error.HTTPError as exc:
                last_err = RuntimeError(f"Gemini API ({model_name}) returned HTTP {exc.code}")
                if exc.code in (404, 429, 500, 503):
                    continue
                raise last_err from None
            except Exception as exc:
                last_err = exc
                continue

        if body is None:
            raise last_err or RuntimeError("Gemini API request failed across all candidate models.")
        candidates = body.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini API returned no candidates (possibly blocked by safety filters).")
        parts = candidates[0].get("content", {}).get("parts") or []
        raw_text = "".join(p.get("text", "") for p in parts)
        if not raw_text.strip():
            raise RuntimeError("Gemini API returned an empty response.")
        return self._extract_json_dict(raw_text)


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parents[2]
    gw = SovereignLLMGateway(env_path=base_dir / ".env")
    status = gw.get_status()
    print("=" * 60)
    print("SLTMOBITEL AI - AWS BEDROCK & CLOUD GATEWAY CHECK")
    print("=" * 60)
    print(f"Active Mode          : {status['active_mode']}")
    print(f"AWS Region           : {status['aws_region']}")
    print(f"Default Bedrock LLM  : {status['aws_bedrock_model']}")
    print(f"Bedrock Configured   : {status['aws_bedrock_configured']} (boto3: {status['boto3_installed']})")
    print(f"Gemini Model         : {status['gemini_model']}")
    print(f"Gemini Configured    : {status['gemini_configured']}")
    print(f"Live LLM Ready       : {status['live_llm_ready']}")
    if "--test" in sys.argv:
        print("-" * 60)
        print("Running live connection test...")
        res = gw.test_connection()
        print(json.dumps(res, indent=2))
