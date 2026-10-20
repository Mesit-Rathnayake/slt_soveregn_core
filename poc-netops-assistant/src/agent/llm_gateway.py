import json
import math
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def load_dotenv_file(env_path: Path):
    """Lightweight .env loader with zero external dependencies."""
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class SovereignLLMGateway:
    """
    SLT Sovereign AI - Local Ollama & Multi-Provider LLM Gateway.
    Uses 'nomic-embed-text:latest' for semantic vector embeddings and
    'granite3.1-dense:2b' / 'qwen2.5:3b' for grounded RAG generation.
    """

    def __init__(self, env_path: Path | None = None):
        if env_path:
            load_dotenv_file(env_path)
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "granite3.1-dense:2b")
        self.ollama_embed_model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text:latest")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    def list_local_ollama_models(self) -> list[str]:
        """Queries local Ollama daemon (/api/tags) and filters out embedding-only models."""
        url = f"{self.ollama_url.rstrip('/')}/api/tags"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [
                    m["name"] for m in data.get("models", [])
                    if "embed" not in m["name"].lower()
                ]
                return models if models else [self.ollama_model]
        except Exception:
            return [self.ollama_model]

    def get_embedding(self, text: str) -> list[float] | None:
        """Generates a semantic vector embedding using local Ollama (nomic-embed-text)."""
        url = f"{self.ollama_url.rstrip('/')}/api/embeddings"
        payload = {
            "model": self.ollama_embed_model,
            "prompt": text
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return body.get("embedding")
        except Exception:
            return None

    @staticmethod
    def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    def build_grounded_prompt(self, sanitized_ticket: str, retrieved_chunks: list[dict]) -> str:
        context_blocks = []
        for c in retrieved_chunks:
            context_blocks.append(f"[{c['doc_id']} - {c['section']}]\n{c['content']}")
        context_str = "\n\n".join(context_blocks)

        return f"""You are the SLT Sovereign AI Network Operations (NetOps) Assistant at SLT Digital Labs.
Analyze the SANITIZED INCIDENT TICKET below using ONLY the APPROVED SLT SOP CONTEXT provided.

STRICT SOVEREIGN GOVERNANCE RULES:
1. Ground every diagnosis and action strictly in the provided SOP thresholds.
2. Include exact citations like [Citation: SLT-NET-SOP-042, Section 4] in your recommended_actions.
3. Enforce Read-Only Advisory Mode: NEVER recommend autonomous configuration changes, interface resets, or clearing routing processes.
4. Respond ONLY with a valid JSON object matching this exact schema:
{{
  "severity": "CRITICAL | HIGH | WARNING | INFO",
  "escalation_required": true,
  "escalation_target": "Exact SLT team name from SOP",
  "diagnosis_summary": "Detailed 2-sentence root cause explanation citing exact telemetry values from the ticket and thresholds from the SOP.",
  "recommended_actions": [
    "1. First step with [Citation: DOC-ID, Section X]",
    "2. Second step with read-only CLI command and [Citation: DOC-ID, Section X]",
    "3. Safety guardrail reminder with [Citation: DOC-ID, Section X]"
  ]
}}

=== APPROVED SLT SOP CONTEXT ===
{context_str}

=== SANITIZED INCIDENT TICKET ===
{sanitized_ticket}
"""

    def generate_with_ollama(self, prompt: str, model_override: str | None = None) -> dict:
        model = model_override or self.ollama_model
        url = f"{self.ollama_url.rstrip('/')}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.1}
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return json.loads(body["response"])

    def generate_with_gemini(self, prompt: str, api_key_override: str | None = None) -> dict:
        api_key = api_key_override or self.gemini_key
        if not api_key or "PASTE_YOUR" in api_key:
            raise ValueError("Missing valid GEMINI_API_KEY in .env or sidebar input.")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.gemini_model}:generateContent?key={api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            raw_text = body["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(raw_text)


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parents[2]
    gw = SovereignLLMGateway(env_path=base_dir / ".env")
    models = gw.list_local_ollama_models()
    emb = gw.get_embedding("BGP link flap optical Rx power -21.4 dBm")
    print("=" * 60)
    print("SLT SOVEREIGN AI - OLLAMA LLM + EMBEDDING GATEWAY CHECK")
    print("=" * 60)
    print(f"Ollama Endpoint       : {gw.ollama_url}")
    print(f"Generation LLMs       : {models}")
    print(f"Embedding Model       : {gw.ollama_embed_model}")
    print(f"Vector Dimension Size : {len(emb) if emb else 'Offline'}")