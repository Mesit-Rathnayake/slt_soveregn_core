import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent.llm_gateway import SovereignLLMGateway
from retrieval.aws_kb_client import SLTMobitelCloudKBClient


class SovereignNetOpsRAG:
    """
    SLTMobitel AI - AWS Cloud KnowledgeBase + Local SOP RAG Engine.
    - SLTMobitel Cloud KB: Uses AWS API Gateway/CloudFront HTTP API (/prod/retrieve).
    - Local NetOps SOPs: Uses fast lexical keyword & section retrieval.
    - Inference Engines: AWS Bedrock, Google Gemini, or Deterministic Grounded Synthesis.
    """

    def __init__(self, manuals_dir: Path, enable_embeddings: bool = False):
        self.manuals_dir = manuals_dir
        env_path = manuals_dir.parents[1] / ".env"
        self.llm_gateway = SovereignLLMGateway(env_path=env_path)
        self.aws_kb_client = SLTMobitelCloudKBClient(env_path=env_path)
        self.inference_mode = os.getenv("AI_INFERENCE_MODE", "AWS_BEDROCK")
        self.enable_embeddings = False
        self.knowledge_base = self._load_manuals()

    def _load_manuals(self) -> list[dict]:
        chunks = []
        if not self.manuals_dir.exists():
            return chunks

        for file_path in sorted(self.manuals_dir.glob("*.md")):
            content = file_path.read_text(encoding="utf-8")
            doc_id_match = re.search(r"\*\*Document ID:\*\*\s*(\S+)", content)
            title_match = re.search(r"\*\*Title:\*\*\s*(.+)", content)
            doc_id = doc_id_match.group(1) if doc_id_match else file_path.stem
            doc_title = title_match.group(1).strip() if title_match else file_path.name

            sections = re.split(r"\n(?=##\s+)", content)
            for sec in sections:
                lines = sec.strip().splitlines()
                if not lines:
                    continue
                header = lines[0].replace("##", "").strip()
                chunk_text = sec.strip()
                chunks.append({
                    "doc_id": doc_id,
                    "doc_title": doc_title,
                    "source_file": file_path.name,
                    "section": header,
                    "content": chunk_text,
                    "embedding": None
                })
        return chunks

    def retrieve_relevant_sections(self, query_text: str, top_k: int = 4) -> list[dict]:
        query_tokens = set(re.findall(r"[a-zA-Z0-9_-]{3,}", query_text.lower()))
        ussd_in_q = re.findall(r"[*#]?[0-9]+#?", query_text.lower())
        scored_chunks = []

        for chunk in self.knowledge_base:
            chunk_content_lower = chunk["content"].lower()
            chunk_tokens = set(re.findall(r"[a-zA-Z0-9_-]{3,}", chunk_content_lower))
            lexical_overlap = len(query_tokens.intersection(chunk_tokens))
            if chunk["doc_id"].lower() in query_text.lower():
                lexical_overlap += 10

            # Boost exact USSD code match (e.g. #247#, #170#, *#06#, 1456, 888)
            for code in ussd_in_q:
                if len(code) >= 3 and (code in chunk_content_lower or f"#{code}#" in chunk_content_lower):
                    lexical_overlap += 6

            # Boost section title match
            sec_lower = chunk.get("section", "").lower()
            if any(t in sec_lower for t in query_tokens if len(t) >= 4 and t not in self.STOPWORDS):
                lexical_overlap += 3

            if lexical_overlap > 0:
                norm_score = min(0.95, 0.55 + (lexical_overlap * 0.06))
                scored_chunks.append((lexical_overlap, norm_score, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        results = []
        for overlap, norm_score, chunk in scored_chunks[:top_k]:
            c_copy = {k: v for k, v in chunk.items() if k != "embedding"}
            c_copy["similarity_score"] = round(norm_score, 4)
            c_copy["score"] = round(norm_score, 4)
            results.append(c_copy)
        return results

    @classmethod
    def _expand_kb_search_query(cls, query_text: str) -> str:
        """
        Enriches short USSD code or loan queries with semantic context so the AWS KB
        vector search retrieves the matching USSD/loan document chunks.
        """
        current_q = re.split(r"\s*\(context:", query_text, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        q_lower = current_q.lower()
        has_credit_loan = re.search(
            r"(?:#247#|\b247\b|\bcredit\s+loan\b|\binstant\s+loan\b|\bsmart\s+loan\b|\bcash\s+loan\b|\bvoice\s+loan\b"
            r"|\bborrow\b|\bloan\b|\badvance\b.*\bcredit\b|\bcredit\b.*\badvance\b)",
            q_lower,
        )
        has_data_loan = re.search(r"\b(?:data\s+loan|borrow\s+data|emergency\s+data)\b", q_lower)
        # A contrast such as "credit loan, not data loan" names the desired
        # product explicitly; prefer it over the negated alternative.
        if has_credit_loan and has_data_loan:
            return "How to take a credit loan"
        if has_data_loan:
            return "USSD #170# data balance loan"
        if has_credit_loan:
            return "How to take a credit loan"
        if re.search(r"(?:#170#|\b170\b)", q_lower):
            return "USSD #170# data balance loan"
        if re.search(r"(?:#1456#|\b1456\b)", q_lower):
            return "USSD #1456# billing usage account balance credit limit"
        if re.search(r"(?:#888#|\b888\b)", q_lower):
            return "USSD #888# self-care portal my package my activations"
        if re.search(r"(?:#111#|\b111\b)", q_lower):
            return "USSD #111# mCash top up bank account"
        if re.search(r"(?:#999#|\b999\b)", q_lower):
            return "USSD #999# international roaming IDD rates"
        if re.search(r"(?:\*#06#|\b06#\b)", q_lower):
            return "*#06# eSIM EID compatibility check"
        return query_text

    def retrieve_from_aws_kb(
        self,
        query_text: str,
        top_k: int = 3,
        kb_secret_override: str | None = None,
        kb_endpoint_override: str | None = None
    ) -> dict:
        """
        Resilient Hybrid Retrieval:
        1. Queries the SLTMobitel Cloud KnowledgeBase HTTP API (/prod/retrieve).
        2. Queries the local approved KnowledgeBase catalog (slt_customer_kb_catalog.md & SOPs).
        3. Merges, scores, and deduplicates retrieved chunks to ensure resilient grounding.
        """
        effective_query = self._expand_kb_search_query(query_text)
        cloud_chunks = []
        cloud_error = None
        try:
            cloud_res = self.aws_kb_client.retrieve(
                query=effective_query,
                top_k=top_k,
                secret_override=kb_secret_override,
                endpoint_override=kb_endpoint_override
            )
            cloud_chunks = cloud_res.get("chunks", [])
        except Exception as exc:
            cloud_error = str(exc)
            cloud_chunks = []

        local_sections = self.retrieve_relevant_sections(query_text, top_k=top_k)
        local_chunks = []
        for sec in local_sections:
            local_chunks.append({
                "doc_id": sec.get("doc_id", "SLT-CUST-KB-01"),
                "doc_title": sec.get("doc_title", "SLTMobitel Customer KnowledgeBase"),
                "source_file": sec.get("source_file", "slt_customer_kb_catalog.md"),
                "section": sec.get("section", ""),
                "content": sec.get("content", ""),
                "score": float(sec.get("similarity_score", 0.75)),
                "similarity_score": float(sec.get("similarity_score", 0.75))
            })

        merged_chunks = []
        seen_texts = set()
        for c in cloud_chunks:
            txt = (c.get("content", "") or "").strip()[:80].lower()
            if txt and txt not in seen_texts:
                seen_texts.add(txt)
                merged_chunks.append(c)

        for c in local_chunks:
            txt = (c.get("content", "") or "").strip()[:80].lower()
            if txt and txt not in seen_texts:
                seen_texts.add(txt)
                merged_chunks.append(c)

        merged_chunks.sort(key=lambda x: float(x.get("score", x.get("similarity_score", 0.0))), reverse=True)
        return {
            "query": query_text,
            "chunks": merged_chunks[:max(top_k, 3)],
            "count": len(merged_chunks[:max(top_k, 3)]),
            "cloud_error": cloud_error
        }

    def _invoke_llm(
        self,
        prompt: str,
        active_mode: str,
        ollama_model: str | None = None,
        gemini_api_key: str | None = None,
        bedrock_model: str | None = None,
        aws_region: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None
    ) -> tuple[dict, str]:
        if active_mode == "AWS_BEDROCK":
            chosen_bedrock = bedrock_model or self.llm_gateway.aws_bedrock_model
            llm_res = self.llm_gateway.generate_with_bedrock(
                prompt,
                model_override=chosen_bedrock,
                aws_region=aws_region,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key
            )
            return llm_res, f"AWS_BEDROCK ({chosen_bedrock})"
        elif active_mode == "GEMINI_CLOUD":
            llm_res = self.llm_gateway.generate_with_gemini(prompt, api_key_override=gemini_api_key)
            return llm_res, f"GEMINI_CLOUD ({self.llm_gateway.gemini_model})"
        else:
            raise ValueError(f"Unsupported LLM mode: {active_mode}")

    STOPWORDS = {
        "how", "hows", "what", "whats", "when", "where", "who", "whos", "why", "which",
        "can", "could", "would", "should", "the", "and", "for", "with", "from", "that",
        "this", "have", "has", "had", "not", "are", "was", "were", "will", "about",
        "into", "your", "my", "our", "their", "please", "tell", "check", "get",
        "use", "using", "slt", "mobitel", "sltmobitel", "context", "previous",
        "question", "does", "need", "want", "sri", "lanka", "lankan", "colombo",
        "visit", "island", "world", "way", "more", "make", "give", "know",
        "see", "view", "show", "find", "list"
    }

    @staticmethod
    def _stem_token(word: str) -> str:
        """Lightweight stemmer & spelling normalizer so British/American and plural forms match."""
        w = word.lower().strip()
        if w in ("fibre", "fiber", "ftth"):
            return "fiber"
        if w in ("peotv", "peo"):
            return "peo"
        if w in ("wifi", "wlan"):
            return "wifi"
        if w in ("addon", "addons"):
            return "addon"
        if w in ("prepaid", "postpaid"):
            return "paid"
        if w in ("socket", "outlet", "plug", "plugged"):
            return "outlet"
        if w in ("restart", "restarted", "restarting", "reboot", "rebooted"):
            return "restart"
        if w in ("working", "works", "worked", "work"):
            return "work"
        if w in ("slow", "slower", "slowly"):
            return "slow"
        if w in ("turned", "powered", "switched"):
            return "power"
        if w in ("remaining", "reamaining", "remainig", "remains", "remain"):
            return "remain"
        if w in ("quota", "quotas"):
            return "quota"
        if w in ("balance", "balances"):
            return "balanc"
        if w in ("usage", "usages"):
            return "usage"
        if w.startswith("activ"):
            return "activ"
        if w.startswith("packag"):
            return "packag"
        if w.startswith("troubleshoot"):
            return "troubleshoot"
        if w.startswith("connect"):
            return "connect"
        if len(w) > 4 and w.endswith("es"):
            return w[:-2]
        if len(w) > 3 and w.endswith("s"):
            return w[:-1]
        return w

    @classmethod
    def _has_any_term(cls, text: str, terms) -> bool:
        """
        Word-boundary aware term matcher so short tokens like 'led', 'sim', 'peo', 'idd', 'vas', 'low'
        never match inside unrelated words like 'knowledge', 'simple', 'people', 'middle', 'follow'.
        Also applies stem-normalization so plurals and inflections match cleanly.
        """
        t_lower = text.lower()
        words = re.findall(r"[a-z0-9]+", t_lower)
        word_set = set(words)
        stemmed_set = {cls._stem_token(w) for w in words}
        for term in terms:
            term_l = term.lower().strip()
            if not term_l:
                continue
            if " " not in term_l and term_l.isalnum():
                if term_l in word_set or cls._stem_token(term_l) in stemmed_set:
                    return True
            else:
                if re.search(r"(?<![a-z0-9])" + re.escape(term_l) + r"(?![a-z0-9])", t_lower):
                    return True
        return False

    @classmethod
    def _is_kb_summary_query(cls, query_text: str) -> bool:
        """Detects queries asking for a summary, overview, or catalog of everything in the KnowledgeBase."""
        current_q = re.split(r"\s*\(context:", query_text, maxsplit=1, flags=re.IGNORECASE)[0].strip().lower()
        if cls._has_any_term(current_q, ("knowledge base", "knowledgebase", "kb")):
            if cls._has_any_term(current_q, (
                "summary", "summarize", "summarise", "everything", "all", "overview",
                "topics", "contain", "contains", "inside", "about", "what is in", "whats in", "catalog"
            )):
                return True
        if cls._has_any_term(current_q, ("summary", "summarize", "summarise")) and cls._has_any_term(current_q, ("everything", "all topics", "all services")):
            return True
        return False

    OUT_OF_DOMAIN_PATTERNS = (
        r"\bspeed\s+of\s+(?:light|sound)\b",
        r"\bprice\s+of\s+(?:gold|silver|oil|rice|car|bitcoin|crypto)\b",
        r"\b(?:capital|president|prime\s+minister|population|currency|flag|anthem|history|geography)\s+of\b",
        r"\bweather\s+in\b",
        r"\b(?:python|java|javascript|c\+\+|html|sql|react)\s+code\b",
        r"\b(?:write|generate)\s+(?:a\s+)?(?:poem|essay|story|song|code|script)\b",
        r"\b(?:recipe|cook|bake|chicken|curry|pizza|dhal)\b",
        r"\b(?:cricket|football|soccer|world\s+cup|olympics|movie|actor|actress)\b",
        r"\b(?:book\s+a\s+flight|flight\s+ticket|hotel\s+booking|visa\s+application|renew\s+(?:my\s+)?passport)\b"
    )

    @classmethod
    def _chunks_are_relevant_to_query(cls, query_text: str, chunks: list[dict], min_score: float = 0.35) -> bool:
        """
        Determines whether the retrieved AWS KB chunks actually contain knowledge relevant
        to the user's question. Prevents dumping irrelevant chunks when the KB doesn't know,
        while accepting valid AWS KB chunks whose cosine similarity is in the 0.35–0.65 range.
        """
        if not chunks:
            return False

        if cls._is_kb_summary_query(query_text):
            return True

        current_q = re.split(r"\s*\(context:", query_text, maxsplit=1, flags=re.IGNORECASE)[0].strip().lower()
        if any(re.search(pat, current_q) for pat in cls.OUT_OF_DOMAIN_PATTERNS):
            return False

        top_score = max(
            float(c.get("rerank_score", c.get("score", 0.0)))
            for c in chunks
        )
        raw_words = [
            w for w in re.findall(r"[a-zA-Z0-9]{2,}", query_text.lower())
            if w not in cls.STOPWORDS and (len(w) >= 3 or w.isdigit())
        ]
        query_keywords = {cls._stem_token(w) for w in raw_words}

        if not query_keywords:
            return False

        combined_content = " ".join(c.get("content", "") + " " + c.get("raw_content", "") for c in chunks).lower()
        content_words = {
            cls._stem_token(w) for w in re.findall(r"[a-zA-Z0-9]{2,}", combined_content)
            if len(w) >= 3 or w.isdigit()
        }

        overlap = query_keywords.intersection(content_words)

        # USSD and specialized keyword synonyms mapping
        ussd_in_q = re.findall(r"[*#]?[0-9]+#?", current_q)
        for code in ussd_in_q:
            if len(code) >= 3 and (code in combined_content or f"#{code}#" in combined_content):
                return True

        if cls._has_any_term(current_q, ("111", "#111#")) and cls._has_any_term(combined_content, ("mcash", "m-cash", "bank account", "wallet")):
            return True
        if cls._has_any_term(current_q, ("999", "#999#")) and cls._has_any_term(combined_content, ("roaming", "idd", "country code", "rate", "minute")):
            return True
        if cls._has_any_term(current_q, ("170", "#170#")) and cls._has_any_term(combined_content, ("loan", "data", "bundle", "validity", "quota")):
            return True
        if cls._has_any_term(current_q, ("247", "#247#")) and cls._has_any_term(combined_content, ("loan", "tenure", "outgoing", "subscriber")):
            return True
        if cls._has_any_term(current_q, ("loan", "borrow", "credit loan", "advance")) and cls._has_any_term(combined_content, ("loan",)):
            return True
        if cls._has_any_term(current_q, ("1456", "#1456#")) and cls._has_any_term(combined_content, ("bill", "usage", "credit limit", "balance")):
            return True
        if cls._has_any_term(current_q, ("888", "#888#")) and cls._has_any_term(combined_content, ("package", "activation", "puk", "prepaid", "postpaid")):
            return True
        if cls._has_any_term(current_q, ("06#", "*#06#", "eid")) and cls._has_any_term(combined_content, ("esim", "eid")):
            return True

        if len(overlap) == 0:
            return False

        if top_score >= min_score and len(overlap) >= 1:
            return True

        return False

    @classmethod
    def _synthesize_clean_kb_fallback(cls, query_text: str, chunks: list[dict]) -> tuple[str, list[str]]:
        """
        Deterministic answer synthesis used when no LLM is available.

        Anti-hallucination rules:
        1. Every template below contains ONLY facts verified in the SLTMobitel KnowledgeBase
           (see docs/04-knowledgebase-full-catalog.md). No invented LEDs, timings, prices or codes.
        2. Grounding gate: a topic template is used only if the retrieved chunks actually mention
           that topic. Otherwise we fall through to extracting text from the chunks themselves.
        3. Topic detection uses the CURRENT question (word-boundary matching); conversation context
           is only used to pick the next troubleshooting stage.
        """
        parts = re.split(r"\s*\(context:", query_text, maxsplit=1, flags=re.IGNORECASE)
        current_q = parts[0].strip().lower()
        context_part = parts[1].strip(" )").lower() if len(parts) > 1 else ""
        combined_lower = " ".join(
            (c.get("content", "") or "") + " " + (c.get("raw_content", "") or "") for c in chunks
        ).lower()

        def asks(*terms) -> bool:
            return cls._has_any_term(current_q, terms)

        def grounded(*anchors) -> bool:
            return cls._has_any_term(combined_lower, anchors)

        # 0. Complete summary (sourced from the reconstructed catalog)
        if cls._is_kb_summary_query(query_text):
            ans = "Here is a complete summary of available services, packages, and support topics:"
            bullets = [
                "**1. Broadband packages:** **4G LTE** (Anytime volume packages from `20 GB` Rs. 535 to `400 GB` Rs. 7,990; LTE Unlimited 2/4/8 Mbps; Unlimited LTE Flash 5 & 10) and **Fibre (FTTH)** packages from *Fiber Starter* (Rs. 2,690) to *Ultra Prime* (`1000/500 Mbps`), plus Megaline-to-Fibre migration offers.",
                "**2. PEOTV & fixed voice:** PEOTV packages from *PEO Bronze* (72 channels, Rs. 860) to *PEO HD Plus* (160 channels, Rs. 3,125), *PEO 4G Elite*, *PEO Mobile* (Rs. 249), and unlimited fixed voice plans (Rs. 747 / Rs. 902 per month).",
                "**3. Data add-ons:** YouTube, Messenger, Youth, Entertainment Combo, Streamer Premium, Gamer Lite/Premium, LMS Lite/Max and Voice 100 Min.",
                "**4. Self-care & account:** `#1456#` (billing), `#888#` (self-care / active packages), `#170#` / MySLT App (data remaining), `#111#` (mCash), `#999#` (roaming), `*#06#` (eSIM EID check), APN `mobitel`, credit-limit alert at 75%, and new-connection documents.",
                "**5. Troubleshooting & support:** Router / Wi-Fi not working, slow internet, wireless extender (WPS), ONT LED meanings and fixed-voice line issues; hotlines `1212` (Fixed/Fibre/PEOTV) and `1717` (Mobile), payment-receipt channels and branch locations."
            ]
            return ans, bullets

        is_troubleshoot_intent = asks(
            "not working", "slow", "slower", "slowly", "low speed", "speed is", "troubleshoot", "restart",
            "restarted", "reboot", "disconnected", "no connection", "no internet",
            "blinking", "problem", "issue", "fault", "broken", "socket", "outlet",
            "on but", "on bot", "turned on", "powered on", "switched on", "is on"
        )

        is_quota_or_balance_intent = asks(
            "quota", "balance", "usage", "remaining", "reamaining", "remainig", "remains",
            "check data", "check my data", "check quota", "data remaining", "data quota",
            "how much data", "data left", "check balance", "bill balance"
        ) or (
            asks("check", "how to check", "view", "know", "see") and asks("data", "quota", "usage", "balance", "package", "plan", "bill")
        )

        # 1AA. Instant Credit Loan (#247#) & Data Loan (#170#)
        if asks(
            "loan", "data loan", "credit loan", "instant loan", "smart loan", "cash loan", "voice loan",
            "borrow", "borrow data", "emergency data", "247"
        ) and grounded(
            "loan", "247", "170", "7678", "recharge", "repay", "data loan", "recovery", "tenure", "outgoing"
        ):
            explicit_credit_loan = asks("247", "credit loan", "instant loan", "smart loan", "cash loan", "voice loan",
                                        "borrow credit", "credit", "advance")
            is_contrastive_credit_loan = (
                explicit_credit_loan
                and asks("data loan")
                and re.search(r"\bnot\s+(?:a\s+)?data\s+loan\b", current_q)
            )
            is_credit_loan = is_contrastive_credit_loan or explicit_credit_loan or (
                grounded("247", "outgoing") and not asks("data loan", "borrow data", "emergency data", "170")
            )
            if is_credit_loan:
                if asks("247") and not asks("how to take", "how to get", "get", "take", "activate", "obtain", "borrow", "loan"):
                    ans = "**`#247#`** is the **Instant Credit Loan** USSD code (usable for local outgoing calls, local SMS, internet browsing, and Value-Added Services):"
                else:
                    ans = "To take an **Instant Credit Loan (`#247#`)** (usable for local calls, SMS, internet browsing, and VAS), dial the USSD code for your preferred amount:"
                bullets = [
                    "**Rs. 25 Loan:** Dial **`#247#25#`** (Service charge: Rs. 1.75 + taxes | Validity: 5 days | Eligibility: > 3 months on network).",
                    "**Rs. 40 Loan:** Dial **`#247#`** on **Tue / Wed / Thu** (Service charge: Rs. 3.00 + taxes | Validity: 7 days | Eligibility: > 3 months).",
                    "**Rs. 50 Loan:** Dial **`#247#50#`** (Service charge: Rs. 3.50 + taxes | Validity: 7 days | Eligibility: > 3 months).",
                    "**Rs. 75 Loan:** Dial **`#247#75#`** (Service charge: Rs. 5.25 + taxes | Validity: 7 days | Eligibility: > 3 months).",
                    "**Rs. 90 Loan:** Dial **`#247#`** on **Fri / Sat / Sun / Mon** (Service charge: Rs. 6.00 + taxes | Validity: 7 days | Eligibility: > 3 months).",
                    "**Rs. 100 Loan:** Dial **`#247#100#`** (Service charge: Rs. 7.00 + taxes | Validity: 7 days | Eligibility: > 6 months on network).",
                    "**Repayment:** Automatically recovered (full or partial) on your next mobile recharge."
                ]
                return ans, bullets

            # If asking how to check data loan balance specifically
            if asks("balance", "remaining", "check", "available") and not asks("get", "activate", "how to get", "obtain", "repay", "pay"):
                ans = "To check your **Data Loan balance**:"
                bullets = [
                    "**1. SMS Self-Care:** Type **`DB`** and send it via SMS to **`7678`**.",
                    "**2. USSD:** Dial **`#170#`** on your mobile."
                ]
                return ans, bullets

            # If asking how to repay a data loan
            if asks("repay", "re-pay", "recover", "recovery", "settle", "pay back"):
                ans = "How **Data Loan repayment** works:"
                bullets = [
                    "**Automatic recovery upon recharge:** The loan amount + service charge is automatically recovered when you perform a normal recharge or a voice/data package recharge.",
                    "**Full recovery:** If your recharge amount is sufficient, the total loan and service fee are deducted entirely.",
                    "**Partial recovery:** If your recharge amount is insufficient, a partial deduction is made, and the remaining balance is recovered on your next recharge."
                ]
                return ans, bullets

            # Default: How to get / activate a data loan (#170#)
            ans = "To get a **Data Loan**, follow these steps on your phone:"
            bullets = [
                "**Step 1:** Dial **`#170#`** on your phone.",
                "**Step 2:** Select **Option 8 (“Data Loan”)**.",
                "**Step 3:** Select your applicable loan tier (**Option 1, 2, or 3**), or dial directly: **`#170#36#`** (Rs. 36 — `296 MB`, 3 days), **`#170#58#`** (Rs. 58 — `512 MB`, 7 days), **`#170#118#`** (Rs. 118 — `1.1 GB`, 14 days), or **`#170#159#`** (Rs. 159 — `1.5 GB`, 14 days).",
                "**Balance check:** SMS **`DB`** to **`7678`** or dial **`#170#`**.",
                "**Repayment:** Automatically deducted (full or partial) on your next mobile recharge."
            ]
            return ans, bullets

        # 1A. Data quota, remaining data, balance & active packages (#170#, MySLT App, #1456#, #888#)
        if (
            is_quota_or_balance_intent
            or asks("balance", "ussd", "code", "codes", "bill", "billing", "1456", "888", "170", "myslt", "usage",
                    "active", "activated", "activation", "activations", "my package", "current package",
                    "upahara", "samurdhi", "garusaru", "kalaguna", "liyasara")
        ) and grounded(
            "170", "1456", "888", "myslt", "usage", "balance", "data", "quota", "package", "bill", "portal", "internet"
        ):
            # Check data quota / remaining data specifically
            if asks("quota", "remaining", "reamaining", "remainig", "remains", "data remaining", "data quota",
                    "how much data", "data left", "check data") or (asks("check", "view", "how to check") and asks("quota", "data")):
                ans = "To check your **remaining data quota and balance**, use the **MySLT App** or these self-care channels:"
                bullets = [
                    "**1. MySLT App / Web Portal (`https://myslt.slt.lk/`):** Navigate to **Internet → Data Remaining** to view your real-time daily/monthly quota. Select *Data Remaining → More → Enable Detailed Reports* for breakdown reports.",
                    "**2. USSD `#170#`:** Dial **`#170#`** on your mobile to view remaining data balances and active add-on volume.",
                    "**3. USSD `#1456#` (or `1456` IVR):** Dial **`#1456#`** to view current data usage, total billed usage, account balance, and credit limit.",
                    "**4. SMS Self-Care:** Type **`DB`** and send it via SMS to **`7678`** to receive your remaining data balance.",
                    "**5. `#888#` Self-Care Portal:** Dial **`#888#`** → Select **My Package** or **My Activations** to verify your active Pre-Paid or Post-Paid package details."
                ]
                return ans, bullets

            # Check active packages specifically
            if asks("active", "activated", "activation", "activations", "my package", "current package",
                    "upahara", "samurdhi", "garusaru", "kalaguna", "liyasara"):
                ans = "You can check your **active packages** using these self-care channels:"
                bullets = [
                    "**`#888#` Self-Care Portal:** Select **My Package** or **My Activations** to see active Pre-Paid/Post-Paid packages, activate/deactivate plans, and check PUK codes.",
                    "**Data remaining (`#170#` / MySLT App):** MySLT App → Internet → Data Remaining (`https://myslt.slt.lk/`).",
                    "**Billing & usage (`#1456#` or `1456` IVR):** Current usage, account balance, last month bill and credit limit.",
                    "**Post-Paid plans listed under `#888#`:** Samurdhi, New Upahara, Meth, Garusaru, Media, Upahara, Kalaguna, Liyasara, ACTIVF, SRIL, VAL50, FX190/390/790, DoubleM."
                ]
                return ans, bullets

            # Specific #170# USSD inquiry (e.g. "What does #170# does")
            if asks("170") and not asks("1456", "888"):
                ans = "**`#170#`** is the **Mobile Data & Self-Care USSD portal** (used alongside the **MySLT App**):"
                bullets = [
                    "**1. Check Remaining Data Balance:** Dial **`#170#`** to view remaining data quota and active bundle balances.",
                    "**2. Activate a Data Loan (`#170#` → Option 8):** Borrow emergency data bundles (`#170#36#` for `296 MB` / Rs. 36, `#170#58#` for `512 MB` / Rs. 58, `#170#118#` for `1.1 GB` / Rs. 118, `#170#159#` for `1.5 GB` / Rs. 159).",
                    "**3. Data Packages & Add-ons:** Activate or manage mobile data plans and Extra GB add-ons."
                ]
                return ans, bullets

            # Specific #1456# USSD inquiry
            if asks("1456") and not asks("170", "888"):
                ans = "**`#1456#`** (and `1456` IVR) is the **Billing & Usage Information USSD portal**:"
                bullets = [
                    "**Usage & Balance:** Check current usage, total billed usage, and real-time account balance.",
                    "**Bill Details:** View last month's bill, billed date, billing period, and last payment details.",
                    "**Credit Limit:** Check your active credit limit (automatic SMS alert sent at 75% usage)."
                ]
                return ans, bullets

            # Specific #888# USSD inquiry
            if asks("888") and not asks("1456", "170"):
                ans = "**`#888#`** is the **Self-Care Information USSD portal** for managing packages and SIM services:"
                bullets = [
                    "**My Package & My Activations:** Check active Pre-Paid/Post-Paid packages and activate or deactivate plans.",
                    "**PUK Codes:** Retrieve PUK codes for locked SIM cards.",
                    "**Supported Plans:** Post-Paid plans (*Samurdhi, New Upahara, Meth, Garusaru, Media, Upahara, Kalaguna, Liyasara, ACTIVF, SRIL, VAL50, FX190/390/790, DoubleM*) and Mobile Broadband data plans."
                ]
                return ans, bullets

            # USSD / balance / billing general
            ans = "You can check your **data and bill balance** using the **MySLT App** or these USSD codes:"
            bullets = [
                "**`#1456#` (or `1456` IVR):** Current usage, account balance, last month bill, total billed usage, last payment, billed date, billing period and credit limit.",
                "**`#888#` Self-Care Portal:** My Package, My Activations, Pre-Paid/Post-Paid plans and PUK codes.",
                "**`#170#` / MySLT App:** MySLT App → Internet → Data Remaining (`https://myslt.slt.lk/`); enable detailed reports via *Data Remaining → More → Enable Detailed Reports*.",
                "**`#247#`:** Instant credit loan for calls, SMS, data, and VAS.",
                "**Other codes:** `#999#` (roaming) | `#111#` (mCash) | `*#06#` (eSIM EID check)."
            ]
            return ans, bullets

        # 1B. eSIM & new-connection documents
        if asks("esim", "e-sim", "eid", "06#") and grounded("esim", "e-sim", "06#", "eid"):
            ans = "To check **eSIM compatibility**:"
            bullets = [
                "**Check compatibility:** Dial **`*#06#`** on your phone and confirm that an **EID number** is displayed.",
                "**More information:** `https://sltmobitel.lk/esim`."
            ]
            return ans, bullets
        if asks("document", "documents", "nic", "passport", "new connection") and grounded(
                "application form", "billing proof", "passport", "driving license", "identity card"):
            ans = "Required documents for a **new connection**:"
            bullets = [
                "**1. Completed application form**",
                "**2. Identity proof:** National Identity Card (NIC), Driving License, or Passport.",
                "**3. Valid billing proof:** Water bill, electricity bill, fixed telephone bill, credit card statement, or current account statement."
            ]
            return ans, bullets

        # 1C. mCash (#111#)
        if asks("mcash", "m-cash", "111") and grounded("mcash", "m-cash", "111"):
            ans = "**mCash (`#111#`)** mobile money & account management:"
            bullets = [
                "**mCash USSD:** Dial **`#111#`** on your phone.",
                "**Remove a saved bank account:** mCash Main Menu → **Top Up Via Bank Account** → select the bank account → tap the **Delete** icon → **Confirm**."
            ]
            return ans, bullets

        # 1CC. International Roaming & IDD (#999#)
        if asks("roaming", "idd", "999") and grounded("roaming", "idd", "country code", "minute", "rate", "turks", "kitts", "antigua"):
            ans = "**`#999#`** is the **International Roaming & IDD** USSD portal:"
            bullets = [
                "**Roaming USSD:** Dial **`#999#`** on your mobile to activate or manage International Roaming services and data plans while traveling.",
                "**Rates & Details:** Visit `https://sltmobitel.lk/personal/idd-and-roaming` for destination-specific IDD and roaming call/data rates."
            ]
            return ans, bullets

        # 1D. Data add-ons
        if asks("add-on", "addon", "addons", "extra gb", "youtube", "whatsapp", "messenger", "viber",
                "youth", "gamer", "gaming", "lms", "learning", "streamer", "entertainment combo") and grounded(
                "youtube", "messenger", "gamer", "lms", "streamer", "add-on", "addon", "youth", "entertainment"):
            ans = "Available **data add-ons** (manage via the **MySLT App** / `#170#`):"
            bullets = [
                "**Social & video (7 days):** YouTube `15 GB` — **Rs. 155** | Messenger `10 GB` (WhatsApp, Viber, Messenger) — **Rs. 45** | Youth Add-on `20 GB` — **Rs. 195**.",
                "**Streaming (monthly):** Entertainment Combo (unlimited entertainment streaming) — **Rs. 1,990** | Streamer Premium `150 GB` — **Rs. 4,000**.",
                "**Gaming (monthly):** Gamer Lite `25 GB` — **Rs. 500** | Gamer Premium `100 GB` — **Rs. 3,000**.",
                "**E-learning & voice (monthly):** LMS Lite `30 GB` — **Rs. 195** | LMS Max `100 GB` — **Rs. 490** | Voice 100 Min (SLT-to-SLT) — **Rs. 200**."
            ]
            return ans, bullets

        # 2A. Fibre packages
        if not is_troubleshoot_intent and not is_quota_or_balance_intent and asks("fibre", "fiber", "ftth", "trio", "megaline", "ultra", "turbo") and grounded(
                "fibre", "fiber", "ftth", "trio", "megaline", "ultra", "turbo"):
            ans = "**Fibre (FTTH)** broadband packages (`100 Mbps` to `1 Gbps`):"
            bullets = [
                "**Volume & Trio:** Fiber Starter `80 GB` — **Rs. 2,690** (`100/50 Mbps`) | Trio Vibe `40 GB` — **Rs. 3,530** | Trio Vibe Plus `40 GB` — **Rs. 4,100** | Trio Shine `100 GB` — **Rs. 4,950**.",
                "**Unlimited:** Unlimited Home — **Rs. 5,900** (`100/50`) | Unlimited Home Plus — **Rs. 9,900** (`200/100`) | Unlimited Twin — **Rs. 14,900** (`200/200`) | Unlimited Pro — **Rs. 19,900** (`500/200`).",
                "**High speed:** Unlimited Edge — **Rs. 29,900** (`750/250`) | Unlimited Turbo — **Rs. 39,900** (`1000/300`) | Ultra Prime `5,000 GB` — **Rs. 75,000** (`1000/500`) | Ultra Flash Prime `200 GB/day` — **Rs. 75,000** (`1000/500`).",
                "**Megaline → Fibre migration (STB included):** Standard **Rs. 7,500**, promotional **Rs. 5,000**."
            ]
            return ans, bullets

        # 2B. PEOTV packages
        if not is_troubleshoot_intent and not is_quota_or_balance_intent and asks("peotv", "peo", "channel", "channels", "television", "tv",
                                               "uthayam", "titanium", "platinum", "silver", "bronze", "gold") and grounded(
                "peo", "peotv", "channel", "channels"):
            if not asks("lte", "4g", "broadband"):
                ans = "**PEOTV** packages:"
                bullets = [
                    "**Premium:** PEO HD Plus `160 ch` — **Rs. 3,125** | PEO Titanium `139 ch` — **Rs. 2,940** | PEO Platinum `125 ch` — **Rs. 2,660**.",
                    "**Mid-tier:** PEO Gold `108 ch` — **Rs. 2,100** | PEO Entertainment `112 ch` — **Rs. 1,875** | PEO Family `100 ch` — **Rs. 1,625**.",
                    "**Standard & regional:** PEO Silver Plus `98 ch` — **Rs. 1,375** | PEO Silver `87 ch` — **Rs. 1,125** | PEO Tamil Regional `68 ch` — **Rs. 1,125** | PEO Bronze `72 ch` — **Rs. 860** | PEO Uthayam `63 ch` — **Rs. 860**.",
                    "**4G & mobile:** PEO 4G Elite `50 ch` — **Rs. 790** (set-top box Rs. 11,990 incl. taxes) | PEO Mobile app (unlimited app data) — **Rs. 249**."
                ]
                return ans, bullets

        # 2C. 4G LTE / general packages
        if not is_troubleshoot_intent and not is_quota_or_balance_intent and asks("package", "packages", "price", "prices", "lte", "4g", "broadband",
                                               "flash", "hbb", "plan", "plans", "unlimited", "anytime", "volte") and grounded(
                "lte", "4g", "hbb", "anytime", "flash", "unlimited", "package", "packages", "rs", "peo", "peotv"):
            ans = "**4G LTE Home Broadband, Unlimited Flash, Fibre, and PEOTV** packages:"
            bullets = [
                "**Anytime (volume):** `20 GB` — **Rs. 535** (30 days) | HBB Anytime 899 `35 GB` | HBB Anytime 1899 `75 GB` | `115 GB` — **Rs. 2,590** | `200 GB` — **Rs. 3,990** | `400 GB` — **Rs. 7,990**.",
                "**LTE Unlimited & Flash:** 2 Mbps — **Rs. 2,950** | 4 Mbps — **Rs. 5,150** | 8 Mbps — **Rs. 7,090** | **Unlimited LTE Flash 5:** **Rs. 2,350** (`5 GB/day` then `1 Mbps`) | **Unlimited LTE Flash 10:** **Rs. 4,090** (`10 GB/day` then `1 Mbps`, free unlimited `12 midnight – 7 AM`).",
                "**Fibre (FTTH) Broadband:** Starts at **Fiber Starter** (`80 GB` — **Rs. 2,690**, `100/50 Mbps`) and **Unlimited Home** (**Rs. 5,900**) up to `1 Gbps` **Unlimited Turbo / Ultra Prime**.",
                "**PEOTV & Fixed Voice Plans:** **PEO Bronze** (`72 ch` — **Rs. 860**) to **PEO HD Plus** (`160 ch` — **Rs. 3,125**) | **Unltd Home My Phone:** **Rs. 747/month** | **Voice Unltd Home/Office SLT Phone:** **Rs. 902/month**."
            ]
            return ans, bullets

        # 3. APN / SIM / credit limit / VAS / roaming
        if asks("roaming", "idd", "international", "abroad", "overseas") and grounded("roaming", "idd", "999"):
            ans = "**Roaming & IDD** information:"
            bullets = [
                "**Check rates / activate:** Dial **`#999#`**.",
                "**Details:** `https://sltmobitel.lk/personal/idd-and-roaming` (Mobile/Fixed IDD and outbound/inbound roaming rates)."
            ]
            return ans, bullets
        if asks("apn", "sim", "credit limit", "gprs", "vas", "value added", "mtunes", "echannelling") and grounded(
                "apn", "sim", "credit limit", "gprs", "mobitel", "vas", "value", "mtunes", "echannelling"):
            ans = "**APN, SIM, credit limit, and VAS** details:"
            bullets = [
                "**Mobile data APN:** Set the GPRS / mobile data APN to **`mobitel`**.",
                "**Triple-cut SIM:** 3-in-1 SIM (Standard, Micro and Nano). eSIM compatibility can be checked by dialing **`*#06#`**.",
                "**Credit-limit alert:** You receive an SMS alert at **75% usage** of your credit limit.",
                "**Value Added Services (VAS):** Includes mTunes, News Alerts, mInsurance, e-Channelling, mTicketing, and mCash (`#111#`)."
            ]
            return ans, bullets

        # 4. Support hotlines / receipts / branches
        if asks("complaint", "receipt", "support", "contact", "branch", "branches", "office", "location",
                "locations", "store", "hotline", "number", "kandy", "jaffna", "airport", "gampaha") and grounded(
                "1212", "1717", "branch", "receipt", "hotline", "store", "5777"):
            ans = "**Support hotlines, receipt channels, and branch locations**:"
            bullets = [
                "**Hotlines:** **`1212`** (SLT Fixed / Fibre / PEOTV) | **`1717`** (Mobitel Mobile).",
                "**Payment receipts (include SR number & mobile number):** WhatsApp/Viber **`+94 71 175 5777`**, email **`info@mobitel.lk`**, fax **`+94 11 233 0396`**.",
                "**Branches:** Colombo Flagship Store (No. 108, W.A.D. Ramanayake Mw, Colombo 02), BIA Airport arrival/departure (`0112 265 555`), Kandy City Centre, Jaffna, Anuradhapura, and mini branches at BMICH, One Galle Face, Rotunda Tower and Singer Mega Gampaha (general `071 275 5777`)."
            ]
            return ans, bullets

        # 4B. Enterprise / SME / Business Solutions (Cloud, SDDC, Cyber Security, Starlink)
        if asks("enterprise", "business", "sme", "wholesale", "starlink", "cloud", "sddc", "cyber") and grounded(
                "enterprise", "business", "sme", "wholesale", "starlink", "cloud", "sddc", "cyber"):
            ans = "**Business & Enterprise Solutions** include:"
            bullets = [
                "**Enterprise Premium Cloud & SDDC:** High-performance **Software Defined Data Center (SDDC)** cloud with rapid provisioning and **pay-as-you-go** billing.",
                "**Core Enterprise Portfolio:** Enterprise Connectivity, Cyber Security, Voice & Collaboration, AI Portfolio, Digital & Managed Services, and Starlink Business solutions."
            ]
            return ans, bullets

        # 5. Fixed voice / landphone troubleshooting
        if asks("dial tone", "ringing", "tone volume", "noise", "disturbance", "telephone", "landphone",
                "landline", "phone wire", "voice") and grounded("dial tone", "ringing", "noise", "telephone", "phone"):
            ans = "**Fixed voice / landphone troubleshooting** steps:"
            bullets = [
                "**No dial tone, or noise/disturbance on the line:** Check that all telephone cables are tightly connected.",
                "**Ringing sound very low:** Set the ring-tone volume button on the telephone to **High**.",
                "**`Phone` LED on the ONT is OFF:** The voice account cannot register — call **`1212`**. (With a single voice connection, `Phone 2` is always OFF.)",
                "**Damaged phone wire inside or outside the premises:** Log a complaint via **`1212`** or the **MySLT App** (`https://myslt.slt.lk/`)."
            ]
            return ans, bullets

        # 6. Wireless extender (WPS)
        if asks("extender", "wps", "repeater", "booster") and grounded("extender", "wps"):
            ans = "To connect a **wireless extender** using **WPS**:"
            bullets = [
                "**1.** Plug the wireless extender into a wall outlet.",
                "**2.** Press the **WPS** button on the router.",
                "**3.** Press the **WPS** button on the wireless extender."
            ]
            return ans, bullets

        # 7. Multi-stage router / internet troubleshooting (KB facts only)
        router_terms = (
            "router", "restart", "restarted", "reboot", "wifi", "wi-fi", "wlan", "cable", "cables",
            "slow", "slower", "slowly", "speed", "disconnect", "connection", "connectivity", "internet", "broadband",
            "led", "blinking", "light", "lights", "socket", "outlet", "power", "button", "turned", "powered"
        )
        if (asks(*router_terms) or cls._has_any_term(context_part, router_terms)) and grounded(
                "router", "wifi", "wi-fi", "wlan", "gpon", "restart", "internet", "cable", "cables",
                "slow", "quota", "outlet", "connection", "telephone", "socket", "power"):
            escalate = "**Report a fault:** Call **`1212`** (Fixed/Fibre) or **`1717`** (Mobile), or log it in the **MySLT App** (`https://myslt.slt.lk/`)."

            # Stage: already restarted, still failing
            if asks("restarted", "rebooted", "already tried", "did that", "done that", "still slow", "still not working", "already restarted"):
                ans = "Since you have **already restarted the router** and the problem continues, here are the next recommended checks:"
                bullets = [
                    "**1. Check your data quota:** In the **MySLT App** → Internet → Data Remaining, confirm your quota is not exceeded (Unlimited LTE Flash packages drop to `1 Mbps` after the daily `5 GB` / `10 GB`).",
                    "**2. Check the `GPON` LED:** Solid green means the optical link to SLT is working normally. If it is not solid green, the line needs to be checked by SLT.",
                    "**3. Check the telephone / Fibre line:** Make sure it is tightly connected.",
                    f"**4.** {escalate}"
                ]
                return ans, bullets

            # Stage: slow internet
            if asks("slow", "slower", "slowly", "low speed", "speed is very low", "speed is low", "very low", "lagging", "buffering") or (
                asks("speed") and asks("low", "bad", "poor", "drop", "issue", "down", "slower", "slowly", "problem", "usual")
            ) or asks("slower than", "speed is slow", "speed is slower"):
                if cls._has_any_term(context_part, ("slow", "slower", "slowly", "speed", "lagging")):
                    ans = "If your **internet speed is still low** after the basic steps, check these next:"
                    bullets = [
                        "**1. Detailed usage report:** MySLT App → Internet → Data Remaining → More → **Enable Detailed Reports**, to see whether your quota has been used up.",
                        "**2. Flash package limit:** On *Unlimited LTE Flash 5 / 10*, speed drops to `1 Mbps` after `5 GB` / `10 GB` per day (free unlimited `12 midnight – 7 AM`). Extra GB can be added via the **MySLT App**.",
                        "**3. Unknown devices:** Change your Wi-Fi password so other devices cannot use your connection.",
                        f"**4.** {escalate}"
                    ]
                    return ans, bullets

                ans = "To troubleshoot a **slow internet connection**, follow these steps:"
                bullets = [
                    "**1. Check usage:** See whether your quota is exceeded via the **MySLT App / Portal** (`https://myslt.slt.lk/`).",
                    "**2. Restart the router.**",
                    "**3. Change your Wi-Fi password.**",
                    "**4. Check the telephone line:** Make sure it is tightly connected."
                ]
                return ans, bullets

            # Stage: router confirmed powered on / on but no connection
            if asks(
                "no connection", "no internet", "on but", "on bot", "lights are on",
                "router is on", "router is turned on", "router is powered on",
                "turned on", "powered on", "switched on", "it is on", "device is on"
            ) or (
                asks("router", "device", "it", "power") and asks("turned on", "powered on", "switched on", "is on")
            ):
                if cls._has_any_term(context_part, ("slow", "slower", "slowly", "speed", "lagging")):
                    ans = "With the **router powered on**, check these next steps to resolve the slow connection:"
                    bullets = [
                        "**1. `WLAN` & `GPON` LEDs:** Confirm `WLAN` is ON (press **Wi-Fi / WLAN** button if OFF) and `GPON` is solid green.",
                        "**2. Check Data Quota:** In the **MySLT App** (`https://myslt.slt.lk/`) → Internet → Data Remaining, verify you haven't exceeded your daily/monthly quota.",
                        "**3. Cable integrity:** Verify that the Fibre/telephone patch cord and Ethernet cables are tightly connected.",
                        "**4. Change Wi-Fi Password:** Prevent unauthorized devices from consuming bandwidth, or call **`1212`** / **`1717`** for line inspection."
                    ]
                    return ans, bullets

                ans = "If your **router is powered on but there is no internet connection**, check the following:"
                bullets = [
                    "**1. `WLAN` LED:** It should be ON. If it is OFF, press the **Wi-Fi / WLAN** button on the router.",
                    "**2. `GPON` LED:** Solid green means the optical link to SLT is normal. If it is not solid green, the line needs checking by SLT.",
                    "**3. Cables:** Make sure the telephone/Fibre and Ethernet cables are tightly connected, then restart the router.",
                    f"**4.** {escalate}"
                ]
                return ans, bullets

            # Stage: power socket / wall outlet confirmed fine
            if asks("power socket", "wall socket", "wall outlet", "socket is fine", "outlet is fine", "power is fine") or (
                asks("socket", "outlet", "wall") and asks("fine", "ok", "working", "good")
            ):
                if cls._has_any_term(context_part, ("socket", "outlet")):
                    ans = "With the **power socket and wall outlet both confirmed working**, check the router itself:"
                    bullets = [
                        "**1. Router lights:** If the router shows no lights at all even on a working wall outlet, the router or its adapter may be faulty — report it to **`1212`**.",
                        "**2. `WLAN` and `GPON` LEDs:** `WLAN` should be ON (press the Wi-Fi/WLAN button if OFF) and `GPON` should be solid green.",
                        f"**3.** {escalate}"
                    ]
                    return ans, bullets

                ans = "Since the **power socket is fine**, please check these next:"
                bullets = [
                    "**1. Router power:** Make sure the router itself is switched on.",
                    "**2. Cables:** Check that the power, Ethernet and telephone/Fibre cables are tightly connected.",
                    "**3. `WLAN` LED:** It should be ON — if OFF, press the **Wi-Fi / WLAN** button on the router.",
                    "**4. `GPON` LED:** It should be solid green. Then restart the router."
                ]
                return ans, bullets

            # Stage: physical router button not responding
            if asks("button", "switch") and asks("doesnot", "does not", "doesn't", "did not", "didn't", "not working",
                                                 "nothing happens", "broken", "stuck", "dead", "won't", "wont", "not responding"):
                ans = "If the **router button is not responding**:"
                bullets = [
                    "**1. Restart from the wall:** Switch the router off at the wall outlet (or unplug it), then plug it back in.",
                    "**2. Check the LEDs** after it starts: `WLAN` ON and `GPON` solid green.",
                    f"**3.** {escalate}"
                ]
                return ans, bullets

            # Stage: initial "internet / Wi-Fi not working" / how to restart router
            ans = "To troubleshoot your **router & Wi-Fi** connection:"
            bullets = [
                "**1. Device & router power:** Make sure Wi-Fi is turned on on your phone/laptop and the router is powered ON.",
                "**2. Cables:** Check that the power, Ethernet and telephone/Fibre cables are tightly connected.",
                "**3. `WLAN` and `GPON` LEDs:** `WLAN` should be ON (press the **Wi-Fi / WLAN** button if OFF) and `GPON` should be solid green.",
                "**4. Restart the router**, and check your quota usage in the **MySLT App** if the problem continues."
            ]
            return ans, bullets

        # 8. Dynamic grounded extractor: extracts structured tables, steps, or bullet points directly from the chunks
        combined_raw = "\n\n".join(c.get("content", "") for c in chunks if c.get("content"))

        # 8A. Match Table Rows (e.g. any package, add-on, or plan table in the KB)
        table_lines = [ln.strip() for ln in combined_raw.splitlines() if ln.strip().startswith("|")]
        if len(table_lines) >= 3:
            headers = [c.strip() for c in table_lines[0].split("|") if c.strip()]
            rows = []
            for line in table_lines[2:]:
                cols = [c.strip() for c in line.split("|") if c.strip()]
                if cols:
                    rows.append(cols)
            # Filter rows by query relevance
            q_keywords = [w for w in re.findall(r"[a-zA-Z0-9]{2,}", current_q) if w not in cls.STOPWORDS]
            matching_rows = []
            for r in rows:
                r_text = " ".join(r).lower()
                if any(w in r_text for w in q_keywords if len(w) >= 3):
                    matching_rows.append(r)
            selected_rows = matching_rows if matching_rows else rows[:6]
            formatted_bullets = []
            for r in selected_rows[:6]:
                if len(r) >= 3:
                    formatted_bullets.append(f"**{r[0]}:** {r[1]} — {r[2]}" + (f" ({r[3]})" if len(r) > 3 else ""))
                elif len(r) == 2:
                    formatted_bullets.append(f"**{r[0]}:** {r[1]}")
                else:
                    formatted_bullets.append(" | ".join(r))
            title = f"**{headers[0]} & Details:**" if headers else "Available packages:"
            return title, formatted_bullets

        # 8B. Match Numbered Step sequences (Step 1, Step 2, ...)
        step_matches = re.findall(r"(?:Step\s*\d+[\s:\-–]+|\b\d+[\.\)]\s+)([^\n\r]+)", combined_raw, re.IGNORECASE)
        clean_steps = [s.strip() for s in step_matches if len(s.strip()) > 8 and not re.search(r"application\s*form|download|bill\s*proof", s, re.I)]
        if len(clean_steps) >= 2:
            return "Follow these steps from the KnowledgeBase:", [f"**Step {i+1}:** {st}" for i, st in enumerate(clean_steps[:5])]

        # 8C. Match Bullet Points (- Item: Details)
        q_keywords = [w for w in re.findall(r"[a-zA-Z0-9]{2,}", current_q) if w not in cls.STOPWORDS]
        kv_bullets = []
        for line in combined_raw.splitlines():
            l_str = line.strip()
            if l_str.startswith(("-", "*", "•")):
                clean_l = re.sub(r"^[\-\*\•]\s*", "", l_str).strip()
                if clean_l and not clean_l.startswith("Title:") and not clean_l.startswith("Document ID:"):
                    clean_lower = clean_l.lower()
                    if any(w in clean_lower for w in q_keywords if len(w) >= 3):
                        if not clean_l.startswith("**") and ":" in clean_l:
                            p1, p2 = clean_l.split(":", 1)
                            if len(p1) < 35:
                                clean_l = f"**{p1.strip()}:** {p2.strip()}"
                        kv_bullets.append(clean_l)
        if len(kv_bullets) >= 2:
            return "Here are the relevant details from the KnowledgeBase:", kv_bullets[:6]

        # 8D. Top lines fallback
        raw_top = chunks[0].get("content", "") if chunks else ""
        raw_top = re.sub(r"^FAQ:\s*", "", raw_top, flags=re.MULTILINE)
        lines = [ln.strip(" ,\"'•~") for ln in raw_top.splitlines() if ln.strip(" ,\"'•~")]
        if not lines:
            return "", []
        deduped = []
        for ln in lines:
            if not deduped or deduped[-1].lower() != ln.lower():
                deduped.append(ln)
        main_text = " ".join(deduped[:3])
        extra_bullets = deduped[3:7]
        return main_text, extra_bullets

    def answer_kb_question(
        self,
        sanitized_query: str,
        top_k: int = 3,
        mode_override: str | None = None,
        ollama_model: str | None = None,
        gemini_api_key: str | None = None,
        bedrock_model: str | None = None,
        aws_region: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        kb_secret_override: str | None = None,
        kb_endpoint_override: str | None = None
    ) -> dict:
        """
        Queries the KnowledgeBase API (/prod/retrieve) and synthesizes
        a clear, natural answer — or politely states 'I don't have enough knowledge to answer that'
        if the retrieved chunks do not match the question.
        """
        active_mode = mode_override or self.inference_mode
        kb_error = None
        try:
            kb_response = self.retrieve_from_aws_kb(
                query_text=sanitized_query,
                top_k=top_k,
                kb_secret_override=kb_secret_override,
                kb_endpoint_override=kb_endpoint_override
            )
            chunks = kb_response.get("chunks", [])
        except Exception as exc:
            kb_error = f"KnowledgeBase API call failed: {exc}"
            chunks = []

        citations = [f"{c['doc_id']} (Score: {c['score']})" for c in chunks]
        llm_error_note = None

        # Check if the retrieved chunks actually have enough knowledge to answer the query
        has_relevant_knowledge = self._chunks_are_relevant_to_query(sanitized_query, chunks)

        if not chunks or not has_relevant_knowledge:
            polite_abstention = "I don't have enough knowledge to answer that question."
            return {
                "query": sanitized_query,
                "inference_mode": active_mode,
                "has_enough_knowledge": False,
                "answer": polite_abstention,
                "confidence": "ABSTAINED",
                "key_points": [],
                "follow_up_suggestion": "",
                "citations": [],
                "retrieved_chunks": chunks,
                "count": len(chunks),
                "kb_api_error": kb_error,
                "llm_fallback_warning": None
            }

        # Loan and USSD answers use grounded deterministic templates. These
        # queries contain competing product names (#247# credit loan versus
        # #170# data loan), so free-form synthesis can select the wrong product
        # even when retrieval returned the correct passages.
        is_loan_or_ussd_query = self._has_any_term(
            sanitized_query,
            ("loan", "borrow", "247", "170", "1456", "888", "111", "999", "06")
        )
        if (
            active_mode in ("AWS_BEDROCK", "GEMINI_CLOUD")
            and not self._is_kb_summary_query(sanitized_query)
            and not is_loan_or_ussd_query
        ):
            prompt = self.llm_gateway.build_kb_qa_prompt(sanitized_query, chunks)
            try:
                llm_res, engine_label = self._invoke_llm(
                    prompt=prompt,
                    active_mode=active_mode,
                    ollama_model=ollama_model,
                    gemini_api_key=gemini_api_key,
                    bedrock_model=bedrock_model,
                    aws_region=aws_region,
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key
                )
                llm_has_knowledge = bool(llm_res.get("has_enough_knowledge", True))
                raw_ans = str(llm_res.get("answer", "")).strip()
                if not llm_has_knowledge or "don't have enough knowledge" in raw_ans.lower():
                    return {
                        "query": sanitized_query,
                        "inference_mode": engine_label,
                        "has_enough_knowledge": False,
                        "answer": "I don't have enough knowledge to answer that question.",
                        "confidence": "ABSTAINED",
                        "key_points": [],
                        "follow_up_suggestion": "",
                        "citations": [],
                        "retrieved_chunks": chunks,
                        "count": len(chunks),
                        "kb_api_error": kb_error,
                        "llm_fallback_warning": None
                    }

                return {
                    "query": sanitized_query,
                    "inference_mode": engine_label,
                    "has_enough_knowledge": True,
                    "answer": raw_ans,
                    "confidence": "HIGH",
                    "key_points": [str(kp) for kp in llm_res.get("key_points", []) if str(kp).strip()],
                    "follow_up_suggestion": str(llm_res.get("follow_up_suggestion", "")),
                    "citations": citations,
                    "retrieved_chunks": chunks,
                    "count": len(chunks),
                    "kb_api_error": kb_error,
                    "llm_fallback_warning": None
                }
            except Exception as exc:
                llm_error_note = f"LLM synthesis ({active_mode}) unavailable: {exc}."

        # Clean, natural fallback synthesis from the retrieved chunks
        top_chunk = chunks[0]
        main_paragraph, bullet_list = self._synthesize_clean_kb_fallback(sanitized_query, chunks)

        return {
            "query": sanitized_query,
            "inference_mode": "AWS_KB_DIRECT_SYNTHESIS",
            "has_enough_knowledge": True,
            "answer": main_paragraph,
            "confidence": "HIGH" if float(top_chunk.get("score", 0.0)) >= 0.60 else "MEDIUM",
            "key_points": bullet_list,
            "follow_up_suggestion": "",
            "citations": citations,
            "retrieved_chunks": chunks,
            "count": len(chunks),
            "kb_api_error": kb_error,
            "llm_fallback_warning": llm_error_note
        }

    @staticmethod
    def _clean_recommended_actions(raw_actions) -> list[str]:
        """
        Ensures recommended_actions from smaller LLMs (like granite3.1:2b) are always clean,
        human-readable strings — never raw Python dicts like {'action': 'First step', ...}
        or prompt template placeholders like 'First step with [Citation: ...]'.
        """
        if not raw_actions:
            return []
        if not isinstance(raw_actions, list):
            raw_actions = [raw_actions]

        cleaned_list = []
        for item in raw_actions:
            if isinstance(item, dict):
                # Extract meaningful fields from dict
                cmd = item.get("command") or item.get("cli") or ""
                rem = item.get("reminder") or item.get("description") or item.get("step") or item.get("action") or ""
                cite = item.get("citation") or ""
                parts = []
                if rem and rem.lower() not in ("first step", "second step", "third step", "safety guardrail reminder"):
                    parts.append(str(rem).strip())
                if cmd:
                    parts.append(f"Run read-only command: `{cmd}`")
                if cite:
                    parts.append(f"[{cite}]")
                text = " — ".join(parts) if parts else ""
            else:
                text = str(item).strip()
                # Strip template literal echoes like "First step with " or "1. Second step with read-only CLI command: "
                text = re.sub(
                    r"^(?:\d+[\.\)]\s*)?(?:First|Second|Third)\s+step(?:\s+with(?:\s+read-only\s+CLI\s+command)?)?\s*[:\-]?\s*",
                    "",
                    text,
                    flags=re.IGNORECASE
                )
                text = re.sub(
                    r"^(?:\d+[\.\)]\s*)?Safety\s+guardrail\s+reminder(?:\s+with)?\s*[:\-]?\s*",
                    "Safety Guardrail: ",
                    text,
                    flags=re.IGNORECASE
                )

            # Skip empty or pure citation-only placeholders
            stripped_no_cite = re.sub(r"\[Citation:[^\]]+\]", "", text, flags=re.IGNORECASE).strip(" :-.")
            if stripped_no_cite and stripped_no_cite.lower() not in ("first step", "second step", "safety guardrail"):
                cleaned_list.append(text.strip())

        return cleaned_list

    @staticmethod
    def _is_valid_netops_telemetry(sanitized_ticket: str) -> bool:
        """
        Checks whether the input actually contains a recognized SLT NetOps SOP topic
        (BGP, OSPF, GPON/PON, MTU, EXSTART, Rx Power, OLT/ONT, or SOP ID).
        Prevents general questions like 'How do I make my router fast' from being hallucinated as OSPF/BGP faults.
        """
        t_lower = sanitized_ticket.lower()
        sop_patterns = (
            r"\bbgp\b", r"\bospf\b", r"\bgpon\b", r"\bpon_los\b", r"\bdyinggasp\b",
            r"\bexstart\b", r"\bmtu\b", r"\btengige\w*\b", r"\brx\s+power\b",
            r"\bdbm\b", r"\bslt-net-sop\b", r"\bolt\b", r"\bonts?\b",
            r"\binc-\d+", r"\bincident\s+ticket\b"
        )
        return any(re.search(pat, t_lower) for pat in sop_patterns)
    def extract_ticket_metadata(self, sanitized_ticket: str) -> dict:
        ticket_id = re.search(r"INCIDENT TICKET:\s*(\S+)", sanitized_ticket)
        node = re.search(r"AFFECTED NODE:\s*([^\r\n(]+)", sanitized_ticket)
        return {
            "ticket_id": ticket_id.group(1).strip() if ticket_id else "UNKNOWN-TICKET",
            "affected_node": node.group(1).strip() if node else "UNKNOWN-NODE"
        }

    def analyze_incident(
        self,
        sanitized_ticket: str,
        mode_override: str | None = None,
        ollama_model: str | None = None,
        gemini_api_key: str | None = None,
        bedrock_model: str | None = None,
        aws_region: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        include_aws_kb: bool = False,
        kb_secret_override: str | None = None
    ) -> dict:
        active_mode = mode_override or self.inference_mode
        meta = self.extract_ticket_metadata(sanitized_ticket)

        # If the user asked a general question not covered by the BGP/OSPF/GPON SOPs, abstain cleanly!
        if not self._is_valid_netops_telemetry(sanitized_ticket):
            abstain_msg = "I don't have enough knowledge to answer that question."
            return {
                "ticket_id": meta["ticket_id"],
                "affected_node": meta["affected_node"],
                "inference_mode": active_mode,
                "has_enough_knowledge": False,
                "severity": "INFO / INSUFFICIENT TELEMETRY",
                "escalation_required": False,
                "escalation_target": "None",
                "diagnosis_summary": abstain_msg,
                "recommended_actions": [],
                "citations": [],
                "retrieved_chunks": [],
                "draft_handover_summary": "",
                "llm_fallback_warning": None
            }

        retrieved = self.retrieve_relevant_sections(sanitized_ticket, top_k=4)

        if include_aws_kb:
            try:
                aws_res = self.retrieve_from_aws_kb(
                    sanitized_ticket[:300],
                    top_k=2,
                    kb_secret_override=kb_secret_override
                )
                retrieved.extend(aws_res.get("chunks", []))
            except Exception:
                pass

        citations = [f"{c['doc_id']} ({c['section']})" for c in retrieved]
        llm_error_note = None
        rule_res = self._evaluate_with_rules(sanitized_ticket)

        if active_mode in ("AWS_BEDROCK", "GEMINI_CLOUD"):
            prompt = self.llm_gateway.build_grounded_prompt(sanitized_ticket, retrieved)
            try:
                llm_res, engine_label = self._invoke_llm(
                    prompt=prompt,
                    active_mode=active_mode,
                    ollama_model=ollama_model,
                    gemini_api_key=gemini_api_key,
                    bedrock_model=bedrock_model,
                    aws_region=aws_region,
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key
                )

                if not llm_res.get("has_enough_knowledge", True):
                    return {
                        "ticket_id": meta["ticket_id"],
                        "affected_node": meta["affected_node"],
                        "inference_mode": engine_label,
                        "has_enough_knowledge": False,
                        "severity": "INFO / INSUFFICIENT TELEMETRY",
                        "escalation_required": False,
                        "escalation_target": "None",
                        "diagnosis_summary": str(
                            llm_res.get(
                                "diagnosis_summary",
                                "I don't have enough knowledge to answer that question."
                            )
                        ),
                        "recommended_actions": [],
                        "citations": [],
                        "retrieved_chunks": retrieved,
                        "draft_handover_summary": "",
                        "llm_fallback_warning": None
                    }

                severity = str(llm_res.get("severity", rule_res["severity"]))
                escalation_required = bool(llm_res.get("escalation_required", rule_res["escalation_required"]))
                escalation_target = str(llm_res.get("escalation_target", rule_res["escalation_target"]))
                diagnosis = str(llm_res.get("diagnosis_summary", rule_res["diagnosis"]))
                recommended_actions = self._clean_recommended_actions(llm_res.get("recommended_actions", []))

                # If the small LLM returned broken/empty actions, use the verified deterministic SOP actions
                if len(recommended_actions) < 2:
                    recommended_actions = rule_res["recommended_actions"]

                draft_summary = self._build_handover_markdown(
                    meta, severity, escalation_required, escalation_target, diagnosis, citations, engine_label
                )
                return {
                    "ticket_id": meta["ticket_id"],
                    "affected_node": meta["affected_node"],
                    "inference_mode": engine_label,
                    "has_enough_knowledge": True,
                    "severity": severity,
                    "escalation_required": escalation_required,
                    "escalation_target": escalation_target,
                    "diagnosis_summary": diagnosis,
                    "recommended_actions": recommended_actions,
                    "citations": citations,
                    "retrieved_chunks": retrieved,
                    "draft_handover_summary": draft_summary,
                    "llm_fallback_warning": None
                }
            except Exception as exc:
                llm_error_note = f"LLM call ({active_mode}) failed: {exc}. Automatically fell back to Deterministic Rule Engine."
        draft_summary = self._build_handover_markdown(
            meta,
            rule_res["severity"],
            rule_res["escalation_required"],
            rule_res["escalation_target"],
            rule_res["diagnosis"],
            citations,
            "LOCAL_GROUNDED_RULE_ENGINE"
        )

        return {
            "ticket_id": meta["ticket_id"],
            "affected_node": meta["affected_node"],
            "inference_mode": "LOCAL_GROUNDED_RULE_ENGINE",
            "has_enough_knowledge": "insufficient telemetry" not in rule_res["severity"].lower(),
            "severity": rule_res["severity"],
            "escalation_required": rule_res["escalation_required"],
            "escalation_target": rule_res["escalation_target"],
            "diagnosis_summary": rule_res["diagnosis"],
            "recommended_actions": rule_res["recommended_actions"],
            "citations": citations,
            "retrieved_chunks": retrieved,
            "draft_handover_summary": draft_summary,
            "llm_fallback_warning": llm_error_note
        }

    def _build_handover_markdown(
        self, meta: dict, severity: str, esc_req: bool, esc_target: str, diagnosis: str, citations: list[str], engine: str
    ) -> str:
        return (
            f"### 📋 SLT NOC Draft Incident Handover Summary\n"
            f"- **Ticket ID:** `{meta['ticket_id']}` | **Affected Node:** `{meta['affected_node']}`\n"
            f"- **AI Engine Used:** `{engine}`\n"
            f"- **Assessed Severity:** {severity}\n"
            f"- **Escalation Required:** {'YES -> ' + esc_target if esc_req else 'NO (' + esc_target + ')'}\n"
            f"- **Root-Cause Summary:** {diagnosis}\n"
            f"- **Primary SOP Referenced:** `{citations[0] if citations else 'N/A'}`\n"
            f"- **Compliance Note:** All PII, internal IPs, and credentials were sanitized prior to analysis. Advisory actions strictly enforce read-only network guardrails."
        )

    def _evaluate_with_rules(self, sanitized_ticket: str) -> dict:
        text_lower = sanitized_ticket.lower()

        if "bgp" in text_lower or "tengige0/1/0" in text_lower or "rx power measured" in text_lower:
            rx_match = re.search(r"Rx Power measured at\s*(-?\d+\.\d+)\s*dBm", sanitized_ticket, re.IGNORECASE)
            flap_match = re.search(r"flapped\s*(\d+)\s*times", sanitized_ticket, re.IGNORECASE)
            rx_dbm = float(rx_match.group(1)) if rx_match else None
            flap_count = int(flap_match.group(1)) if flap_match else 0

            if rx_dbm is not None and (rx_dbm < -18.1 or flap_count > 5):
                return {
                    "severity": "CRITICAL (Tier-3 Escalation Mandatory)",
                    "escalation_required": True,
                    "escalation_target": "SLT Tier-3 Core Transport Team & Regional Fiber Maintenance Unit",
                    "diagnosis": (
                        f"Detected Critical Optical Loss (Rx Power: {rx_dbm} dBm, below the -18.1 dBm threshold) "
                        f"and severe link instability ({flap_count} flaps, exceeding the >5 flaps/15 min threshold)."
                    ),
                    "recommended_actions": [
                        "1. IMMEDIATE ESCALATION: Escalate ticket to SLT Tier-3 Core Transport Team and dispatch Regional Fiber Maintenance Unit [Citation: SLT-NET-SOP-042, Section 4].",
                        "2. READ-ONLY VERIFICATION: Run `show bgp ipv4 unicast summary` and `show interfaces TenGigE0/1/0 transceiver detail` to monitor status [Citation: SLT-NET-SOP-042, Section 2].",
                        "3. SAFETY GUARDRAIL: Do NOT reset interfaces, clear BGP sessions, or modify BGP routing policies autonomously [Citation: SLT-NET-SOP-042, Section 2 & 4]."
                    ]
                }
            elif rx_dbm is not None and (-18.0 <= rx_dbm <= -14.1):
                return {
                    "severity": "WARNING (Degraded Optical Signal)",
                    "escalation_required": False,
                    "escalation_target": "Scheduled ODF Fiber Cleaning (No Emergency Tier-3 Escalation)",
                    "diagnosis": f"Optical Rx Power ({rx_dbm} dBm) is in the Degraded Warning range (-14.1 to -18.0 dBm).",
                    "recommended_actions": [
                        "1. Schedule maintenance window to inspect and clean LC/UPC fiber connectors at the ODF [Citation: SLT-NET-SOP-042, Section 4].",
                        "2. Monitor CRC counters via `show interfaces TenGigE0/1/0 | include CRC|drops` [Citation: SLT-NET-SOP-042, Section 2]."
                    ]
                }

        if "ospf" in text_lower or "exstart" in text_lower or "mtu" in text_lower:
            mtu_values = [int(m) for m in re.findall(r"MTU(?:\s+is)?\s+(\d+)\s*bytes", sanitized_ticket, re.IGNORECASE)]
            mtu_detail = f" (Detected MTU values: {mtu_values} bytes)" if len(set(mtu_values)) > 1 else ""
            return {
                "severity": "HIGH (Tier-2 Configuration Alignment Required)",
                "escalation_required": True,
                "escalation_target": "SLT Tier-2 Metro/Core Configuration Team",
                "diagnosis": (
                    f"OSPF neighbor stuck in EXSTART due to Interface IP MTU mismatch{mtu_detail} "
                    f"against the standard SLT 9198-byte Core MPLS or 1500-byte Metro alignment."
                ),
                "recommended_actions": [
                    "1. ESCALATION: Escalate to SLT Tier-2 Metro/Core Configuration Team to align interface MTU during an authorized window [Citation: SLT-NET-SOP-043, Section 4].",
                    "2. READ-ONLY VERIFICATION: Run `show ip ospf interface TenGigE0/2/0 | include MTU|State` and `ping <peer-ip> size 9000 df-bit` [Citation: SLT-NET-SOP-043, Section 2].",
                    "3. SAFETY GUARDRAIL: Do NOT run `clear ip ospf process` on production core routers [Citation: SLT-NET-SOP-043, Section 2]."
                ]
            }

        if "pon_los" in text_lower or "gpon" in text_lower or "ont" in text_lower:
            if "0 dyinggasp" in text_lower:
                return {
                    "severity": "CRITICAL (Feeder Fiber Cut Suspected)",
                    "escalation_required": True,
                    "escalation_target": "SLT Regional OPMC Outside Plant (OSP) Fiber Team",
                    "diagnosis": (
                        "100% of ONTs on PON port dropped simultaneously with LOS and 0 DyingGasp alarms, "
                        "indicating an optical feeder fiber cut or OLT SFP transceiver failure."
                    ),
                    "recommended_actions": [
                        "1. IMMEDIATE DISPATCH: Escalate to SLT Regional OPMC Outside Plant (OSP) Fiber Team for OTDR testing on feeder cable [Citation: SLT-NET-SOP-044, Section 4].",
                        "2. READ-ONLY VERIFICATION: Run `display port state 0/3 4` and `display port ddm-info 0/3 4` [Citation: SLT-NET-SOP-044, Section 2].",
                        "3. SAFETY GUARDRAIL: Do NOT reboot the OLT line card or reset PON protection groups [Citation: SLT-NET-SOP-044, Section 2]."
                    ]
                }

        return {
            "severity": "INFO / INSUFFICIENT TELEMETRY",
            "escalation_required": False,
            "escalation_target": "Tier-2 NOC Shift Lead",
            "diagnosis": "I don't have enough matching network telemetry or SOP knowledge to diagnose that specific issue automatically.",
            "recommended_actions": []
        }


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parents[2]
    manuals_dir = base_dir / "data" / "approved_manuals"
    clean_ticket_path = base_dir / "data" / "synthetic_incidents" / "inc_2026_1042_sanitized.txt"

    print("Initializing SLT Hybrid AWS + Sovereign NetOps RAG Engine...")
    rag = SovereignNetOpsRAG(manuals_dir=manuals_dir, enable_embeddings=False)
    ticket_text = clean_ticket_path.read_text(encoding="utf-8")
    report = rag.analyze_incident(ticket_text, mode_override="AWS_BEDROCK")

    print("=" * 70)
    print("SLT HYBRID SOVEREIGN AI - RAG REPORT")
    print("=" * 70)
    print(f"Engine Mode       : {report['inference_mode']}")
    print(f"Assessed Severity : {report['severity']}")
    print(f"Escalation Target : {report['escalation_target']}\n")
    print(f"Root-Cause Diagnosis:\n  {report['diagnosis_summary']}\n")
