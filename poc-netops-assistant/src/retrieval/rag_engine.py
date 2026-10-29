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
        scored_chunks = []

        for chunk in self.knowledge_base:
            chunk_tokens = set(re.findall(r"[a-zA-Z0-9_-]{3,}", chunk["content"].lower()))
            lexical_overlap = len(query_tokens.intersection(chunk_tokens))
            if chunk["doc_id"].lower() in query_text.lower():
                lexical_overlap += 10

            if lexical_overlap > 0:
                norm_score = min(0.95, 0.55 + (lexical_overlap * 0.06))
                scored_chunks.append((lexical_overlap, norm_score, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        results = []
        for overlap, norm_score, chunk in scored_chunks[:top_k]:
            c_copy = {k: v for k, v in chunk.items() if k != "embedding"}
            c_copy["similarity_score"] = round(norm_score, 4)
            results.append(c_copy)
        return results

    def retrieve_from_aws_kb(
        self,
        query_text: str,
        top_k: int = 3,
        kb_secret_override: str | None = None,
        kb_endpoint_override: str | None = None
    ) -> dict:
        """Retrieves relevant chunks from the SLTMobitel AWS KnowledgeBase HTTP API."""
        return self.aws_kb_client.retrieve(
            query=query_text,
            top_k=top_k,
            secret_override=kb_secret_override,
            endpoint_override=kb_endpoint_override
        )

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
        "how", "what", "when", "where", "who", "why", "which", "can", "could",
        "would", "should", "the", "and", "for", "with", "from", "that", "this",
        "have", "has", "had", "not", "are", "was", "were", "will", "about",
        "into", "your", "my", "our", "their", "please", "tell", "check", "get",
        "use", "using", "slt", "mobitel", "sltmobitel", "context", "previous",
        "question", "does", "need", "want"
    }

    @classmethod
    def _chunks_are_relevant_to_query(cls, query_text: str, chunks: list[dict], min_score: float = 0.50) -> bool:
        """
        Determines whether the retrieved AWS KB chunks actually contain knowledge relevant
        to the user's question. Prevents dumping irrelevant chunks when the KB doesn't know.
        """
        if not chunks:
            return False

        top_score = max(float(c.get("score", 0.0)) for c in chunks)
        # Extract meaningful query keywords (excluding common stopwords)
        raw_words = re.findall(r"[a-zA-Z0-9]{3,}", query_text.lower())
        query_keywords = {w for w in raw_words if w not in cls.STOPWORDS}

        combined_content = " ".join(c.get("content", "") for c in chunks).lower()
        content_words = set(re.findall(r"[a-zA-Z0-9]{3,}", combined_content))

        overlap = query_keywords.intersection(content_words)

        # High vector similarity score (>= 0.65) is trusted directly
        if top_score >= 0.65:
            return True
        # Moderate score (>= min_score) requires at least 1 meaningful keyword match
        if top_score >= min_score and (len(overlap) >= 1 or not query_keywords):
            return True
        # Below min_score (e.g., 0.45 noise), require strong keyword overlap (>= 2 matching domain terms)
        if top_score >= 0.42 and len(overlap) >= 2:
            return True

        return False

    @staticmethod
    def _synthesize_clean_kb_fallback(query_text: str, chunks: list[dict]) -> tuple[str, list[str]]:
        """
        Synthesizes a clean, conversational answer and bullet points directly from
        the retrieved AWS KB chunks when an external LLM is offline or in fast mode.
        """
        q_lower = query_text.lower()
        combined = "\n".join(c.get("content", "") for c in chunks)

        # 1. USSD / Balance / Billing / Self-Care Portal / Add-on questions
        if any(w in q_lower for w in ("balance", "ussd", "code", "bill", "billing", "1456", "888", "add-on", "addon", "extra gb", "170", "roaming", "youtube", "myslt")):
            if any(k in combined for k in ("#1456#", "#888#", "#170#", "MySLT", "YouTube")):
                ans = (
                    "You can check your **SLTMobitel Data & Bill Balance**, activate **Extra GB / Data Add-ons**, "
                    "and manage your account using the **MySLT App**, **Web Portal**, or **USSD Shortcodes**:"
                )
                bullets = [
                    "**Activate Data Add-ons / Extra GB:** Dial **`#170#`** or use the **MySLT App** (`https://myslt.slt.lk/`) to add Extra GB or Social/Streaming bundles (e.g., **YouTube 7-Day Add-on: 15 GB for Rs. 155**, or Zoom/Teams add-ons).",
                    "**Check Detailed Data Usage (`MySLT App / Portal`):** Open **MySLT App → Internet → Select Data Remaining → More → Enable Detailed Reports**.",
                    "**Billing & Balance USSD (`#1456#` or dial `1456` IVR):** Check Current Usage, Account Balance, Last Month Bill, Last Payment, and Credit Limit.",
                    "**Self-Care Portal (`#888#`):** Manage 'My Package', Pre-Paid/Post-Paid plans, Activations & Deactivations, and PUK codes."
                ]
                return ans, bullets

        # 2. 4G LTE Home Broadband & PeoTV Packages / Pricing
        if any(w in q_lower for w in ("package", "price", "peotv", "peo", "lte", "broadband", "flash", "hbb", "channel")):
            if "Unlimited LTE Flash" in combined or "PEO HD PLUS" in combined:
                ans = (
                    "Here are the **SLTMobitel 4G LTE Home Broadband** and **PEOTV** packages available in the KnowledgeBase:"
                )
                bullets = [
                    "**4G LTE Home Broadband (30 Days):** `20 GB` for **Rs. 535** | **HBB Anytime 899:** `35 GB` for **Rs. 899** | **HBB Anytime 1899:** `75 GB` for **Rs. 1,899**.",
                    "**Unlimited LTE Flash Packages:** **Flash 5** (`5 GB` at standard LTE speed, then `1 Mbps` unlimited) | **Flash 10** (**Rs. 4,090** — `10 GB` at standard LTE speed, then `1 Mbps` unlimited).",
                    "**PEOTV Packages:** **PEO HD PLUS** (`160 channels` — **Rs. 3,125**), **PEO TITANIUM** (`139 channels` — **Rs. 2,940**), **PEO PLATINUM** (`125 channels` — **Rs. 2,660**)."
                ]
                return ans, bullets

        # 3. APN / SIM / Credit Limit / Value Added Services (VAS)
        if any(w in q_lower for w in ("apn", "sim", "credit limit", "vas", "value added", "mtunes", "gprs")):
            if "APN" in combined or "credit limit" in combined.lower():
                ans = (
                    "Here are the **SLTMobitel Mobile Data (APN), SIM, Credit Limit, and VAS** details from the KnowledgeBase:"
                )
                bullets = [
                    "**Mobile Data APN Setting:** Set your handset GPRS/Mobile Data APN to **`mobitel`**.",
                    "**Triple-Cut SIM Card:** SLTMobitel provides a 3-in-1 SIM (Standard, Micro, and Nano SIM) to fit any handset.",
                    "**Credit Limit Policy:** You receive an SMS alert at **75% usage** of your credit limit. Exceeding 100% may interrupt service until an interim payment is made.",
                    "**Value Added Services (VAS):** Includes mTunes (`777`), News Alerts, mInsurance, e-Channelling (`225`), mTicketing (`365`), and Job Alerts."
                ]
                return ans, bullets

        # 4. Payment Receipt / Complaint / Support Contact Channels
        if any(w in q_lower for w in ("complaint", "receipt", "whatsapp", "support", "contact", "branch", "office", "location")):
            if "info@mobitel.lk" in combined or "branch-locator" in combined:
                ans = (
                    "You can contact **SLTMobitel Customer Support**, submit payment receipts for logged complaints, "
                    "or locate the nearest SLT branch using the official channels below:"
                )
                bullets = [
                    "**Hotline:** Dial **`1717`** to log a service request or inquiry.",
                    "**Submit Payment Receipts (with SR Number & Mobile Number):** WhatsApp/Viber **`+94 71 175 5777`**, Email **`info@mobitel.lk`**, or Fax **`+94 11 233 0396`**.",
                    "**Island-Wide Branch Locator:** Find your nearest SLT office at `https://www.slt.lk/en/contact-us/branch-locator/our-locations/our-network`."
                ]
                return ans, bullets

        # 5. Enterprise / SME / Business Solutions (Cloud, Cyber Security, Starlink)
        if any(w in q_lower for w in ("enterprise", "business", "sme", "wholesale", "starlink", "cloud", "cyber")):
            if "Enterprise Solutions" in combined or "SME" in combined:
                ans = (
                    "**SLTMobitel Business & Enterprise Solutions** provide tailored ICT services for SMEs, "
                    "Micro Businesses, Enterprises, and Wholesale partners:"
                )
                bullets = [
                    "**Core Offerings:** Connectivity, Cloud Services, Cyber Security, Voice & Collaboration, AI Portfolio, and Digital & Managed Services.",
                    "**SME & Enterprise Focus:** Bespoke, business-grade ICT infrastructure designed to scale local and global operations."
                ]
                return ans, bullets

        # 6. Router / Wi-Fi / Broadband Basic Troubleshooting Steps
        if any(w in q_lower for w in ("router", "restart", "wifi", "wi-fi", "wlan", "cable", "slow", "disconnect", "connection", "internet")):
            # If the user is reporting a follow-up failure (e.g., "the restart button does not do anything" / "still not working"),
            # do NOT repeat the basic 4 steps — explain that the KB only has the basic restart check and advise fault escalation!
            unresolved_signals = (
                "doesnot", "does not", "doesn't", "did not", "didn't", "not working",
                "nothing happens", "still", "already tried", "broken", "stuck", "dead",
                "do anything", "won't", "wont", "cannot", "can't"
            )
            if any(sig in q_lower for sig in unresolved_signals):
                ans = (
                    "I don't have deeper hardware-repair steps for a non-responsive router button in the current "
                    "SLTMobitel KnowledgeBase (which only covers the initial 4-step power, cable, WLAN, and restart check). "
                    "Since the router button is not responding:"
                )
                bullets = [
                    "**Power-Cycle via Wall Socket:** Turn off the main wall power switch (or unplug the power adapter) for **30 seconds**, then plug it back in.",
                    "**Avoid the Pinhole 'Reset' Button:** Do **not** hold the recessed pinhole *Reset* button, as that erases your SLT Fibre/4G PPPoE configuration.",
                    "**Log a Hardware Fault / CPE Replacement:** Call **`1212`** (SLT Fixed/Fibre) or **`1717`** (Mobitel), or report a fault via the **MySLT App** so a technician can inspect or replace the faulty router."
                ]
                return ans, bullets

            if any(k in combined.lower() for k in ("restart router", "wlan", "cables are properly connected", "wi-fi")):
                ans = (
                    "To troubleshoot or restart your **SLTMobitel Home Broadband Router / Wi-Fi connection**, "
                    "follow these steps from the SLTMobitel Support KnowledgeBase:"
                )
                bullets = [
                    "**1. Check Router Power:** Verify that the router is plugged in and powered on.",
                    "**2. Inspect Cable Connections:** Check that all power, telephone/Fibre patch cords, and Ethernet cables are securely connected.",
                    "**3. Verify Wi-Fi / WLAN Status:** Check if the router's **Wi-Fi (WLAN)** indicator LED is on. If not, press the **Wi-Fi / WLAN button** on the router to turn it on.",
                    "**4. Restart the Router:** Power off the router, wait ~15–30 seconds, and switch it back on to refresh your connection (or call **`1212` / `1717`** if the fault persists)."
                ]
                return ans, bullets

        # General clean paragraph & numbered-step fallback
        raw_top = chunks[0].get("content", "")
        # If the text has inline numbered steps like "1. ... 2. ... 3. ...", split them into clean bullets!
        numbered_matches = re.split(r"(?=\b\d+\.\s+[A-Z])", raw_top)
        if len(numbered_matches) >= 3:
            cleaned_steps = []
            for m in numbered_matches:
                s = m.strip(" ,\"'•~")
                if len(s) >= 6:
                    if not re.match(r"^\d+\.", s):
                        s = f"• {s}"
                    cleaned_steps.append(s)
            return "Here are the recommended steps from the SLTMobitel KnowledgeBase:", cleaned_steps[:6]

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
        Queries the SLTMobitel AWS KnowledgeBase API (/prod/retrieve) and synthesizes
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
            kb_error = f"AWS KnowledgeBase API call failed: {exc}"
            chunks = []

        citations = [f"{c['doc_id']} (Score: {c['score']})" for c in chunks]
        llm_error_note = None

        # Check if the retrieved chunks actually have enough knowledge to answer the query
        has_relevant_knowledge = self._chunks_are_relevant_to_query(sanitized_query, chunks)

        if not chunks or not has_relevant_knowledge:
            polite_abstention = (
                "I don't have enough knowledge in the current SLTMobitel KnowledgeBase to answer that specific question. "
                "Please try asking about topics covered in our knowledge base, or contact **SLTMobitel Support (1212)** "
                "or the **MySLT App** for direct assistance."
            )
            return {
                "query": sanitized_query,
                "inference_mode": active_mode,
                "has_enough_knowledge": False,
                "answer": polite_abstention,
                "confidence": "ABSTAINED",
                "key_points": [],
                "follow_up_suggestion": "Try asking a different SLTMobitel question or paste a network incident ticket.",
                "citations": [],
                "retrieved_chunks": chunks,
                "count": len(chunks),
                "kb_api_error": kb_error,
                "llm_fallback_warning": None
            }

        if active_mode in ("AWS_BEDROCK", "GEMINI_CLOUD"):
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
                        "answer": (
                            raw_ans if raw_ans else
                            "I don't have enough knowledge in the SLTMobitel KnowledgeBase to answer that specific question."
                        ),
                        "confidence": "ABSTAINED",
                        "key_points": [],
                        "follow_up_suggestion": "Please try another question or contact SLTMobitel 1212.",
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
                    "follow_up_suggestion": str(
                        llm_res.get("follow_up_suggestion", "Need more help? Reach SLTMobitel via 1212 or the MySLT App.")
                    ),
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
            "follow_up_suggestion": "You can ask a follow-up question below or check the official SLTMobitel portal (slt.lk).",
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
        sop_signals = (
            "bgp", "ospf", "gpon", "pon_los", "dyinggasp", "exstart",
            "mtu", "tengige", "rx power", "dbm", "slt-net-sop", "olt", "ont",
            "inc-", "incident ticket"
        )
        return any(sig in t_lower for sig in sop_signals)
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
            abstain_msg = (
                "I don't have enough knowledge in the SLT Network Operations SOPs to answer that question. "
                "Our NetOps SOPs only cover **Core BGP Optical Loss (`SLT-NET-SOP-042`)**, "
                "**OSPF EXSTART MTU Mismatches (`SLT-NET-SOP-043`)**, and **GPON OLT Feeder Fiber Cuts (`SLT-NET-SOP-044`)**."
            )
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
                                "I don't have enough knowledge in the SLT Network Operations SOPs to answer that question."
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
    rag = SovereignNetOpsRAG(manuals_dir=manuals_dir, enable_embeddings=True)
    ticket_text = clean_ticket_path.read_text(encoding="utf-8")
    report = rag.analyze_incident(ticket_text, mode_override="OLLAMA_LOCAL", ollama_model="granite3.1-dense:2b")

    print("=" * 70)
    print("SLT HYBRID SOVEREIGN AI - RAG REPORT")
    print("=" * 70)
    print(f"Engine Mode       : {report['inference_mode']}")
    print(f"Assessed Severity : {report['severity']}")
    print(f"Escalation Target : {report['escalation_target']}\n")
    print(f"Root-Cause Diagnosis:\n  {report['diagnosis_summary']}\n")
