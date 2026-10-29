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
from retrieval.cloudfront_gateway import SLTCloudFrontEdgeGateway


class SLTMobitelCloudKBClient:
    """
    SLTMobitel KnowledgeBase Access HTTP API Client (AWS API Gateway / CloudFront).
    Endpoint: POST https://ww5659pvgk.execute-api.us-east-1.amazonaws.com/prod/retrieve
    Header: x-auth-secret
    """

    DEFAULT_ENDPOINT = "https://ww5659pvgk.execute-api.us-east-1.amazonaws.com/prod/retrieve"
    DEFAULT_SECRET = "d215af7a649fe83938414634e789b39cb3ed4ad0a1077c2d"

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

        # 2. If the chunk contains broken JSON array items of packages/add-ons, convert them to readable lines!
        # Example: { "name": "Unlimited LTE Flash 10", "price": 4090, "data": "Unlimited (10 GB then 1 Mbps)" }
        if '"name"' in text and '"price"' in text:
            items_found = []
            for obj_match in re.finditer(r'\{[^{}]*"name"\s*:\s*"([^"]+)"[^{}]*\}', text):
                block = obj_match.group(0)
                name_val = obj_match.group(1)
                price_m = re.search(r'"price"\s*:\s*(\d+)', block)
                data_m = re.search(r'"data"\s*:\s*"([^"]+)"', block)
                desc_m = re.search(r'"description"\s*:\s*"([^"]+)"', block)
                chan_m = re.search(r'"channels"\s*:\s*(\d+)', block)
                speed_m = re.search(r'"speed"\s*:\s*"([^"]+)"', block)

                parts = [f"**{name_val}**"]
                if price_m:
                    parts.append(f"Rs. {price_m.group(1)}")
                if data_m:
                    parts.append(f"Data: {data_m.group(1)}")
                if desc_m:
                    parts.append(desc_m.group(1))
                if chan_m:
                    parts.append(f"{chan_m.group(1)} Channels")
                if speed_m and speed_m.group(1).lower() != "not specified":
                    parts.append(f"Speed: {speed_m.group(1)}")
                items_found.append(" — ".join(parts))

            if items_found:
                text = "\n".join(items_found)

        # 3. Unescape literal \n and \t sequences if present
        text = text.replace("\\n", "\n").replace("\\t", " ").replace("&amp;", "&").replace("\r", "\n")

        # 4. Strip trilingual CSV quote delimiters (",") and non-ASCII Sinhala/Tamil translation blocks
        # Many KB chunks are CSV columns like: "English text...","~ සිංහල පෙළ...","• தமிழ் உரை..."
        if '","' in text:
            csv_parts = [p.strip(' "~•') for p in text.split('","') if p.strip(' "~•')]
            # Keep parts that are predominantly English (ASCII >= 80%)
            eng_parts = [
                p for p in csv_parts
                if (sum(1 for c in p if ord(c) < 128) / max(len(p), 1)) >= 0.80
            ]
            if eng_parts:
                text = "\n".join(eng_parts)

        # Remove any remaining Sinhala (U+0D80–U+0DFF) and Tamil (U+0B80–U+0BFF) script blocks & stray CSV quotes
        text = re.sub(r"[\u0D80-\u0DFF\u0B80-\u0BFF]+", "", text)
        text = re.sub(r'","', "\n", text)
        text = re.sub(r'[~•■□●]+', "• ", text)
        text = re.sub(r"\s{2,}", " ", text)
        return text.strip(' "\'\n\t,')

    @staticmethod
    def _rerank_chunk_score(query: str, cleaned_content: str, base_score: float) -> float:
        """
        Reranks chunks returned by the AWS KB API to fix noisy vector ordering:
        - Demotes pure Sinhala/Tamil chunks when the user's query is in English.
        - Boosts chunks that contain exact keyword matches with the user's query.
        """
        import re
        if not cleaned_content:
            return 0.0

        score = base_score
        # Check ASCII ratio of query vs chunk content
        query_ascii_ratio = sum(1 for ch in query if ord(ch) < 128) / max(len(query), 1)
        content_ascii_chars = sum(1 for ch in cleaned_content if ord(ch) < 128)
        content_ascii_ratio = content_ascii_chars / max(len(cleaned_content), 1)

        # If user asked in English (>90% ASCII), penalize chunks that are mostly Sinhala/Tamil (<60% ASCII)
        if query_ascii_ratio > 0.90 and content_ascii_ratio < 0.60:
            score -= 0.18

        # Boost exact keyword overlap
        stopwords = {"what", "how", "can", "the", "and", "for", "with", "are", "slt", "mobitel", "sltmobitel"}
        q_words = {w for w in re.findall(r"[a-zA-Z0-9]{3,}", query.lower()) if w not in stopwords}
        c_words = set(re.findall(r"[a-zA-Z0-9]{3,}", cleaned_content.lower()))
        overlap_count = len(q_words.intersection(c_words))
        score += min(overlap_count * 0.04, 0.16)

        return max(0.0, min(score, 0.99))

    def __init__(self, env_path: Path | None = None, endpoint_url: str | None = None, auth_secret: str | None = None):
        if env_path:
            load_dotenv_file(env_path)
        self.cloudfront = SLTCloudFrontEdgeGateway(env_path=env_path)
        self.endpoint_url = (
            endpoint_url
            or os.getenv("SLT_KB_API_URL", self.DEFAULT_ENDPOINT)
        ).strip()
        self.auth_secret = (
            auth_secret
            or os.getenv("SLT_KB_AUTH_SECRET", self.DEFAULT_SECRET)
        ).strip()
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
            "endpoint": url
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
    print(f"🔍 DISCOVERING DOCUMENTS IN SLTMOBITEL AWS KB API:\n   {client.endpoint_url}")
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

