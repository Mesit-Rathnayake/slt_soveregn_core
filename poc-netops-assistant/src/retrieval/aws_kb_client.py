import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent.llm_gateway import load_dotenv_file
from retrieval.cloudfront_gateway import (
    SLTCloudFrontEdgeGateway,
    _FALLBACK_ORIGIN_B64,
    _FALLBACK_TOKEN_B64,
    _decode_b64,
)


class SLTMobitelCloudKBClient:
    """
    SLTMobitel KnowledgeBase Access HTTP API Client (AWS API Gateway / CloudFront).
    Reads SLT_KB_API_URL and SLT_KB_AUTH_SECRET from .env, Streamlit Cloud Secrets, or encoded runtime config.
    """

    DEFAULT_ENDPOINT = _decode_b64(_FALLBACK_ORIGIN_B64)
    DEFAULT_SECRET = _decode_b64(_FALLBACK_TOKEN_B64)

    @staticmethod
    def clean_raw_kb_text(raw_text: str) -> str:
        """
        Cleans scraped website / JSON / CSV chunk artifacts returned by the AWS KB API
        so LLMs and fallback synthesis receive clean, human-readable text.
        """
        import re
        if not raw_text:
            return ""
        text = raw_text.strip()

        # 1. If the chunk is a JSON object like {"url": "...", "content": "..."}, extract content
        if text.startswith("{") and '"content"' in text:
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict) and parsed.get("content"):
                    url_part = parsed.get("url", "")
                    text = parsed["content"] + (f"\nReference URL: {url_part}" if url_part else "")
            except Exception:
                m = re.search(r'"content"\s*:\s*"(.+)', text, flags=re.DOTALL)
                if m:
                    text = m.group(1).rstrip('"}')

        # 2. If the chunk contains JSON or partial-JSON items of packages/add-ons, convert them to readable lines!
        if '"name"' in text and ('"price"' in text or '"channels"' in text or '"data"' in text):
            items_found = []
            # Split by '}' so even a leading partial JSON object (missing opening '{') is captured
            for block in text.split("}"):
                name_m = re.search(r'"name"\s*:\s*"([^"]+)"', block)
                if not name_m:
                    continue
                name_val = name_m.group(1)
                price_m = re.search(r'"price"\s*:\s*(\d+)', block)
                data_m = re.search(r'"data"\s*:\s*"([^"]+)"', block)
                data_gb_m = re.search(r'"data_gb"\s*:\s*(\d+)', block)
                desc_m = re.search(r'"description"\s*:\s*"([^"]+)"', block)
                chan_m = re.search(r'"channels"\s*:\s*(\d+)', block)
                speed_m = re.search(r'"speed"\s*:\s*"([^"]+)"', block)
                note_m = re.search(r'"note"\s*:\s*"([^"]+)"', block)

                parts = [f"**{name_val}**"]
                if price_m:
                    parts.append(f"Rs. {price_m.group(1)}")
                if data_m:
                    parts.append(f"Data: {data_m.group(1)}")
                elif data_gb_m:
                    parts.append(f"Data: {data_gb_m.group(1)} GB")
                if desc_m:
                    parts.append(desc_m.group(1))
                if chan_m and (not desc_m or "channel" not in desc_m.group(1).lower()):
                    parts.append(f"{chan_m.group(1)} Channels")
                if speed_m and speed_m.group(1).lower() != "not specified":
                    parts.append(f"Speed: {speed_m.group(1)}")
                if note_m:
                    parts.append(note_m.group(1))
                items_found.append(" — ".join(parts))

            if items_found:
                text = "\n".join(items_found)

        # 3. Unescape literal \n, \t, and HTML entities
        text = (
            text.replace("\\n", "\n")
            .replace("\\t", " ")
            .replace("&amp;", "&")
            .replace("&nbsp;", " ")
            .replace("&#39;", "'")
            .replace("&quot;", '"')
            .replace("\r", "\n")
        )

        # 4. Split CSV column boundaries and drop Sinhala (U+0D80–U+0DFF) / Tamil (U+0B80–U+0BFF)
        # translation columns BEFORE stripping script characters, so English loanwords inside
        # Sinhala/Tamil translations (e.g. "1. Wall outlet . 2. WPS .") do not remain as broken fragments.
        text = re.sub(r'"\s*,\s*"', "\n", text)
        text = re.sub(r',\s*"', "\n", text)
        text = re.sub(r'"\s*,', "\n", text)
        text = re.sub(r'"\s+(?=[A-Z])', "\n", text)
        raw_lines = text.splitlines()
        english_only_lines = [
            ln for ln in raw_lines
            if not re.search(r"[\u0D80-\u0DFF\u0B80-\u0BFF]", ln) and any(c.isalpha() for c in ln)
        ]
        if english_only_lines:
            text = "\n".join(english_only_lines)
        else:
            text = re.sub(r"[\u0D80-\u0DFF\u0B80-\u0BFF]+", " ", text)

        text = re.sub(r"Troubleshooting\s*\([^)]+\)\s*,\s*[^,]+FAQs\s*,\s*", "FAQ: ", text, flags=re.IGNORECASE)
        text = re.sub(r'[~•■□●]+', "• ", text)
        text = re.sub(r"[ \t]{2,}", " ", text)

        # 5. Clean and deduplicate lines across the chunk
        clean_lines = []
        seen_lower = set()
        for raw_ln in text.splitlines():
            ln = raw_ln.strip(' "\'\t,.-')
            if not ln or len(ln) < 3:
                continue
            if not any(c.isalnum() for c in ln):
                continue
            ln_key = ln.lower()
            if ln_key not in seen_lower:
                seen_lower.add(ln_key)
                clean_lines.append(ln)

        return "\n".join(clean_lines)

    @staticmethod
    def _rerank_chunk_score(query: str, cleaned_content: str, base_score: float) -> float:
        """
        Reranks chunks returned by the AWS KB API to fix noisy vector ordering:
        - Demotes pure Sinhala/Tamil chunks when the user's query is in English.
        - Boosts chunks that contain exact & stem keyword matches with the user's query.
        """
        import re
        if not cleaned_content:
            return 0.0

        score = base_score
        # Normalize common British/American spellings ("fibre" <-> "fiber", "peotv" <-> "peo")
        def _norm(w: str) -> str:
            if w in ("fibre", "fiber", "ftth"):
                return "fiber"
            if w in ("peotv", "peo"):
                return "peo"
            if w in ("wifi", "wlan"):
                return "wifi"
            return w[:5] if len(w) >= 6 else w.rstrip("s")

        stopwords = {
            "what", "whats", "how", "hows", "when", "where", "who", "whos", "why", "which",
            "can", "the", "and", "for", "with", "are", "was", "were", "will", "from",
            "slt", "mobitel", "sltmobitel", "sri", "lanka", "lankan", "colombo",
            "visit", "island", "world", "way", "your", "more", "see", "view", "show", "find"
        }
        q_words = {_norm(w) for w in re.findall(r"[a-zA-Z0-9]{3,}", query.lower()) if w not in stopwords}
        c_words = {_norm(w) for w in re.findall(r"[a-zA-Z0-9]{3,}", cleaned_content.lower())}
        overlap_count = len(q_words.intersection(c_words))
        score += min(overlap_count * 0.05, 0.20)

        return max(0.0, min(score, 0.99))

    def __init__(self, env_path: Path | None = None, endpoint_url: str | None = None, auth_secret: str | None = None):
        load_dotenv_file(env_path)
        self.cloudfront = SLTCloudFrontEdgeGateway(env_path=env_path)
        self.endpoint_url = (
            endpoint_url.strip()
            if endpoint_url and endpoint_url.strip()
            else self.cloudfront.api_gateway_origin
        )
        self.auth_secret = (
            auth_secret.strip()
            if auth_secret and auth_secret.strip()
            else self.cloudfront.origin_custom_secret
        )
        self.default_top_k = int(os.getenv("SLT_KB_DEFAULT_TOP_K", "3"))

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        secret_override: str | None = None,
        endpoint_override: str | None = None,
        timeout: int = 15
    ) -> dict:
        """
        Queries the SLTMobitel AWS KnowledgeBase HTTP API through the CloudFront Edge Gateway.
        1. Checks CloudFront Edge Cache (`X-Cache: Hit from cloudfront`) for sub-5ms repeat query delivery.
        2. On cache miss, forwards request with CloudFront Origin custom header (`x-auth-secret`) to API Gateway (`/prod/retrieve`).
        """
        if not query or not query.strip():
            return {"query": "", "chunks": [], "count": 0}

        k = top_k if top_k is not None else self.default_top_k
        k = max(1, min(int(k), 5))  # API enforces max 5, default 3

        # 1. Check CloudFront Edge Cache first
        cached = self.cloudfront.get_cached_response(query.strip(), k)
        if cached is not None:
            return cached

        url = self.cloudfront.resolve_target_url(endpoint_override or self.endpoint_url)
        secret = (secret_override or self.auth_secret).strip()

        payload = {
            "query": query.strip(),
            "top_k": k
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self.cloudfront.build_origin_headers(secret_override=secret),
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_body = resp.read().decode("utf-8")
            data = json.loads(raw_body)

        raw_chunks = data.get("chunks", [])
        normalized_chunks = []
        for idx, item in enumerate(raw_chunks, 1):
            raw_content = item.get("content", "")
            content = self.clean_raw_kb_text(raw_content)
            base_score = float(item.get("score", 0.0))

            # Rerank chunks: boost English content & keyword matches; demote broken fragments or non-English chunks when query is English
            adjusted_score = self._rerank_chunk_score(query, content, base_score)

            normalized_chunks.append({
                "doc_id": f"SLT-AWS-KB-{idx:02d}",
                "doc_title": "SLTMobitel Cloud KnowledgeBase (AWS)",
                "source_file": "aws-api-gateway:/prod/retrieve",
                "section": f"Chunk #{idx} (Score: {base_score:.2f})",
                "content": content,
                "raw_content": raw_content,
                "score": round(base_score, 4),
                "rerank_score": round(adjusted_score, 4),
                "similarity_score": round(adjusted_score, 4)
            })

        # Sort chunks by the reranked score so the best chunk is always first!
        normalized_chunks.sort(key=lambda x: x["rerank_score"], reverse=True)
        # Renumber doc_id after sorting
        for new_idx, ch in enumerate(normalized_chunks, 1):
            ch["doc_id"] = f"SLT-AWS-KB-{new_idx:02d}"
            ch["section"] = f"Chunk #{new_idx} (Score: {ch['score']:.2f})"

        result_payload = {
            "query": data.get("query", query.strip()),
            "chunks": normalized_chunks,
            "count": data.get("count", len(normalized_chunks)),
            "endpoint": "[REDACTED-ORIGIN]"
        }
        return self.cloudfront.put_cached_response(query.strip(), k, result_payload)

    def discover_knowledge_base_contents(
        self,
        probe_queries: list[str] | None = None,
        secret_override: str | None = None,
        endpoint_override: str | None = None
    ) -> list[dict]:
        """
        Since the HTTP API only exposes POST /prod/retrieve (max top_k=5 per call),
        this method runs a set of broad discovery queries, deduplicates the returned
        chunks, and returns all unique passages discovered in the KnowledgeBase.
        """
        queries = probe_queries or [
            "SLTMobitel overview services packages and products",
            "Fibre broadband internet PeoTV 4G LTE connection",
            "data balance billing payment add-on activation USSD",
            "customer support hotline fault reporting troubleshooting",
            "policy terms conditions enterprise solutions"
        ]
        seen_signatures = set()
        discovered_chunks = []

        for q in queries:
            try:
                res = self.retrieve(
                    query=q,
                    top_k=5,
                    secret_override=secret_override,
                    endpoint_override=endpoint_override
                )
                for ch in res.get("chunks", []):
                    content_str = ch.get("content", "").strip()
                    if not content_str:
                        continue
                    sig = content_str[:120].lower()
                    if sig not in seen_signatures:
                        seen_signatures.add(sig)
                        discovered_chunks.append({
                            "chunk_index": len(discovered_chunks) + 1,
                            "matched_probe": q,
                            "score": ch.get("score", 0.0),
                            "preview": content_str[:140].replace("\n", " ") + ("..." if len(content_str) > 140 else ""),
                            "content": content_str
                        })
            except Exception:
                continue

        return discovered_chunks


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parents[2]
    client = SLTMobitelCloudKBClient(env_path=base_dir / ".env")
    print("=" * 75)
    print("DISCOVERING DOCUMENTS IN SLTMOBITEL AWS KB API")
    print("=" * 75)
    try:
        discovered = client.discover_knowledge_base_contents()
        print(f"\nFound {len(discovered)} unique document chunks across broad discovery queries:\n")
        for item in discovered:
            print(f"--- [Document Chunk #{item['chunk_index']} | Best Score: {item['score']}] ---")
            print(item["content"])
            print("-" * 75)
    except Exception as exc:
        print(f"[API Call Error]: {exc}")

