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


class SovereignNetOpsRAG:
    """
    SLT Sovereign AI - Hybrid Semantic Vector + LLM RAG Engine.
    Uses 'nomic-embed-text:latest' for dense vector retrieval and
    'granite3.1-dense:2b' / 'qwen2.5:3b' for grounded incident diagnostics.
    """

    def __init__(self, manuals_dir: Path, enable_embeddings: bool = True):
        self.manuals_dir = manuals_dir
        env_path = manuals_dir.parents[1] / ".env"
        self.llm_gateway = SovereignLLMGateway(env_path=env_path)
        self.inference_mode = os.getenv("AI_INFERENCE_MODE", "OLLAMA_LOCAL")
        self.enable_embeddings = enable_embeddings
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
                embedding = (
                    self.llm_gateway.get_embedding(f"{doc_id} {doc_title} {chunk_text}")
                    if self.enable_embeddings else None
                )
                chunks.append({
                    "doc_id": doc_id,
                    "doc_title": doc_title,
                    "source_file": file_path.name,
                    "section": header,
                    "content": chunk_text,
                    "embedding": embedding
                })
        return chunks

    def retrieve_relevant_sections(self, query_text: str, top_k: int = 4) -> list[dict]:
        query_tokens = set(re.findall(r"[a-zA-Z0-9_-]{3,}", query_text.lower()))
        query_emb = self.llm_gateway.get_embedding(query_text) if self.enable_embeddings else None
        scored_chunks = []

        for chunk in self.knowledge_base:
            chunk_tokens = set(re.findall(r"[a-zA-Z0-9_-]{3,}", chunk["content"].lower()))
            lexical_overlap = len(query_tokens.intersection(chunk_tokens))
            if chunk["doc_id"].lower() in query_text.lower():
                lexical_overlap += 10

            semantic_score = 0.0
            if query_emb and chunk.get("embedding"):
                semantic_score = self.llm_gateway.cosine_similarity(query_emb, chunk["embedding"])

            # Hybrid score: combine dense vector similarity (scaled) + lexical keyword match
            combined_score = (semantic_score * 20.0) + lexical_overlap
            if combined_score > 0:
                scored_chunks.append((combined_score, semantic_score, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        results = []
        for combined, sem_score, chunk in scored_chunks[:top_k]:
            c_copy = {k: v for k, v in chunk.items() if k != "embedding"}
            c_copy["similarity_score"] = round(sem_score, 4)
            results.append(c_copy)
        return results

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
        gemini_api_key: str | None = None
    ) -> dict:
        active_mode = mode_override or self.inference_mode
        meta = self.extract_ticket_metadata(sanitized_ticket)
        retrieved = self.retrieve_relevant_sections(sanitized_ticket, top_k=4)
        citations = [f"{c['doc_id']} ({c['section']})" for c in retrieved]
        llm_error_note = None

        if active_mode in ("OLLAMA_LOCAL", "GEMINI_CLOUD"):
            prompt = self.llm_gateway.build_grounded_prompt(sanitized_ticket, retrieved)
            try:
                if active_mode == "OLLAMA_LOCAL":
                    chosen_model = ollama_model or self.llm_gateway.ollama_model
                    llm_res = self.llm_gateway.generate_with_ollama(prompt, model_override=chosen_model)
                    engine_label = f"OLLAMA_LOCAL ({chosen_model})"
                else:
                    llm_res = self.llm_gateway.generate_with_gemini(prompt, api_key_override=gemini_api_key)
                    engine_label = f"GEMINI_CLOUD ({self.llm_gateway.gemini_model})"

                severity = str(llm_res.get("severity", "CRITICAL"))
                escalation_required = bool(llm_res.get("escalation_required", True))
                escalation_target = str(llm_res.get("escalation_target", "SLT Tier-3 Engineering"))
                diagnosis = str(llm_res.get("diagnosis_summary", "Diagnosis generated by LLM."))
                raw_actions = llm_res.get("recommended_actions", [])
                recommended_actions = [str(a) for a in raw_actions] if isinstance(raw_actions, list) else [str(raw_actions)]

                draft_summary = self._build_handover_markdown(
                    meta, severity, escalation_required, escalation_target, diagnosis, citations, engine_label
                )
                return {
                    "ticket_id": meta["ticket_id"],
                    "affected_node": meta["affected_node"],
                    "inference_mode": engine_label,
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

        rule_res = self._evaluate_with_rules(sanitized_ticket)
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
            if len(set(mtu_values)) > 1:
                return {
                    "severity": "HIGH (Tier-2 Configuration Alignment Required)",
                    "escalation_required": True,
                    "escalation_target": "SLT Tier-2 Metro/Core Configuration Team",
                    "diagnosis": (
                        f"OSPF neighbor stuck in EXSTART due to confirmed Interface IP MTU mismatch "
                        f"(Detected MTU values: {mtu_values} bytes vs standard 9198/1500 alignment)."
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
            "severity": "INFO / MANUAL TRIAGE REQUIRED",
            "escalation_required": False,
            "escalation_target": "Tier-2 NOC Shift Lead",
            "diagnosis": "Incident telemetry requires manual review of retrieved SOP sections.",
            "recommended_actions": ["1. Review retrieved SLT SOP sections and perform read-only diagnostics."]
        }


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parents[2]
    manuals_dir = base_dir / "data" / "approved_manuals"
    clean_ticket_path = base_dir / "data" / "synthetic_incidents" / "inc_2026_1042_sanitized.txt"

    print("Indexing SLT SOP Manuals with 'nomic-embed-text:latest' & calling 'granite3.1-dense:2b'...")
    rag = SovereignNetOpsRAG(manuals_dir=manuals_dir, enable_embeddings=True)
    ticket_text = clean_ticket_path.read_text(encoding="utf-8")
    report = rag.analyze_incident(ticket_text, mode_override="OLLAMA_LOCAL", ollama_model="granite3.1-dense:2b")

    print("=" * 70)
    print("SLT SOVEREIGN AI - LIVE IBM GRANITE 3.1 + NOMIC VECTOR RAG REPORT")
    print("=" * 70)
    print(f"Engine Mode       : {report['inference_mode']}")
    print(f"Assessed Severity : {report['severity']}")
    print(f"Escalation Target : {report['escalation_target']}\n")
    print(f"LLM Root-Cause Diagnosis:\n  {report['diagnosis_summary']}\n")
    print("LLM Recommended Actions:")
    for step in report["recommended_actions"]:
        print(f"  {step}")
    print("\nTop Vector-Retrieved SOP Chunks (Cosine Similarity):")
    for c in report["retrieved_chunks"]:
        print(f"  - [{c['doc_id']}] {c['section']} (Similarity: {c.get('similarity_score')})")
    print("=" * 70)