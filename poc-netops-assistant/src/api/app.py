import os
import sys
import time
from pathlib import Path
import streamlit as st

SRC_DIR = Path(__file__).resolve().parents[1]
BASE_DIR = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ingestion.sanitizer import SovereignDataSanitizer
from retrieval.rag_engine import SovereignNetOpsRAG
from agent.governance import SovereignGovernanceManager

st.set_page_config(
    page_title="SLT Sovereign AI - NetOps Assistant MVP",
    page_icon="🛡️",
    layout="wide"
)

sanitizer = SovereignDataSanitizer()
manuals_dir = BASE_DIR / "data" / "approved_manuals"
incidents_dir = BASE_DIR / "data" / "synthetic_incidents"
audit_log_path = BASE_DIR / "data" / "audit_trail.jsonl"

rag_engine = SovereignNetOpsRAG(manuals_dir=manuals_dir)
governance = SovereignGovernanceManager(audit_log_path=audit_log_path)

with st.sidebar:
    st.title("🛡️ SLT Sovereign AI")
    st.caption("IBM Sovereign Core v1.1.0 — Hybrid AI MVP")
    st.divider()

    st.markdown("### 🧠 AI Inference Engine")
    selected_engine = st.selectbox(
        "Select Inference Backend:",
        options=[
            "OLLAMA_LOCAL",
            "GEMINI_CLOUD",
            "LOCAL_GROUNDED_RULE_ENGINE"
        ],
        index=0
    )

    ollama_model_input = None
    gemini_key_input = None

    if selected_engine == "OLLAMA_LOCAL":
        available_models = rag_engine.llm_gateway.list_local_ollama_models()
        ollama_model_input = st.selectbox(
            "Select Local Sovereign LLM:",
            options=available_models,
            index=0
        )
        st.caption(f"Vector Embeddings: `{rag_engine.llm_gateway.ollama_embed_model}`")
        st.success("🔒 Data Residency: 100% On-Premises (LocalHost)")
    elif selected_engine == "GEMINI_CLOUD":
        gemini_key_input = st.text_input(
            "Google Gemini API Key:",
            value=os.getenv("GEMINI_API_KEY", ""),
            type="password",
            help="Used to benchmark external provider latency vs. local sovereign inference."
        )
        st.warning("☁️ Data Residency: External Cloud Provider (Sanitized Only)")
    else:
        st.success("🔒 Data Residency: 100% On-Premises (Deterministic Rules)")

    st.divider()
    st.markdown("### 👤 Active User Role (RBAC)")
    active_role = st.selectbox(
        "Simulate SLT Identity Role:",
        options=list(SovereignGovernanceManager.ROLES.keys()),
        index=1
    )

    st.divider()
    st.markdown("### 📚 Indexed SLT Manuals")
    for md_file in sorted(manuals_dir.glob("*.md")):
        st.markdown(f"- `{md_file.name}`")

st.title("📡 SLT AI Network Operations (NetOps) Assistant")
st.markdown(
    "**Proof-of-Concept Workbench:** Compare **On-Premises Sovereign LLM (Ollama)**, "
    "**External Cloud Provider (Gemini)**, and **Deterministic Rule Baseline** with full PII/IP sanitization."
)

tab1, tab2, tab3 = st.tabs([
    "🚨 1. Incident Triage & Handover Generator",
    "📖 2. Approved SOP Knowledge Search",
    "🔒 3. Governance & Audit Trail (RBAC)"
])

with tab1:
    raw_files = sorted(incidents_dir.glob("*_raw.txt"))
    file_map = {f.name: f for f in raw_files}

    selected_file_name = st.selectbox(
        "Select a Synthetic SLT Incident Scenario (or edit below):",
        options=list(file_map.keys())
    )
    default_text = file_map[selected_file_name].read_text(encoding="utf-8") if selected_file_name else ""

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1️⃣ Raw NOC Incident Ticket")
        raw_input = st.text_area("Unsanitized Ticket Input:", value=default_text, height=280)
        analyze_btn = st.button("🛡️ Sanitize, Diagnose & Generate Handover", type="primary", use_container_width=True)

    if analyze_btn and raw_input.strip():
        with st.spinner(f"Sanitizing ticket & running grounded inference via {selected_engine}..."):
            t0 = time.perf_counter()
            sanitized_res = sanitizer.sanitize_text(raw_input)
            clean_text = sanitized_res["sanitized_text"]
            redactions = sanitized_res["redactions_applied"]

            report = rag_engine.analyze_incident(
                clean_text,
                mode_override=selected_engine,
                ollama_model=ollama_model_input,
                gemini_api_key=gemini_key_input
            )
            latency_ms = (time.perf_counter() - t0) * 1000

            governance.log_event(
                user_role=active_role,
                action_type="INCIDENT_TRIAGE",
                ticket_id=report["ticket_id"],
                redactions_count=redactions,
                severity=report["severity"],
                citations=report["citations"],
                latency_ms=latency_ms,
                engine_mode=report["inference_mode"]
            )

        if report.get("llm_fallback_warning"):
            st.warning(f"⚠️ {report['llm_fallback_warning']}")

        with col2:
            st.subheader("2️⃣ Sanitized Sovereign Payload")
            st.metric("Sensitive Fields Masked (PII / IPs / Secrets)", redactions)
            st.code(clean_text, language="text")

        st.divider()
        st.subheader("3️⃣ Grounded Diagnostic & Escalation Assessment")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Ticket ID", report["ticket_id"])
        m2.metric("Active Engine", report["inference_mode"])
        m3.metric("Escalation Mandatory?", "YES" if report["escalation_required"] else "NO")
        m4.metric("Response Latency", f"{latency_ms:.0f} ms")

        if report["escalation_required"]:
            st.error(f"**🚨 Severity: {report['severity']} | Escalation Target:** {report['escalation_target']}")
        else:
            st.success(f"**✅ Severity: {report['severity']} | Routing Target:** {report['escalation_target']}")

        st.markdown("#### 🔍 Grounded Root-Cause Analysis")
        st.info(report["diagnosis_summary"])

        c_left, c_right = st.columns(2)
        with c_left:
            st.markdown("#### 🛠️ Recommended Read-Only Actions")
            for act in report["recommended_actions"]:
                st.markdown(f"- {act}")
            st.markdown("#### 📌 Verified SOP Citations")
            for cite in report["citations"]:
                st.caption(f"✔ `{cite}`")

        with c_right:
            st.markdown("#### 📝 Draft Incident Summary (For Shift Handover)")
            st.markdown(report["draft_handover_summary"])
            st.code(report["draft_handover_summary"], language="markdown")

with tab2:
    st.subheader("🔎 Search Approved SLT Technical Manuals & Procedures")
    search_query = st.text_input(
        "Enter keywords, alarm codes, or CLI commands:",
        value="OSPF EXSTART MTU mismatch"
    )
    if st.button("Search Approved Manuals") and search_query.strip():
        t0 = time.perf_counter()
        results = rag_engine.retrieve_relevant_sections(search_query, top_k=4)
        latency_ms = (time.perf_counter() - t0) * 1000

        governance.log_event(
            user_role=active_role,
            action_type="SOP_SEARCH",
            ticket_id="N/A",
            redactions_count=0,
            severity="INFO",
            citations=[f"{r['doc_id']} ({r['section']})" for r in results],
            latency_ms=latency_ms,
            engine_mode=selected_engine
        )

        st.caption(f"Found {len(results)} grounded sections in {latency_ms:.2f} ms")
        for idx, item in enumerate(results, 1):
            with st.expander(f"{idx}. [{item['doc_id']}] {item['doc_title']} — {item['section']}", expanded=(idx == 1)):
                st.markdown(item["content"])
                st.caption(f"Source File: `data/approved_manuals/{item['source_file']}`")

with tab3:
    st.subheader("🔒 Sovereign AI Audit Trail & RBAC Verification")
    if not governance.check_permission(active_role, "can_view_audit_logs"):
        st.error(
            f"⛔ **Access Denied:** Role `{active_role}` does not have permission to view platform audit logs. "
            "Switch role to `Tier-2 Core Engineer` or `Sovereign Platform Auditor` in the left sidebar."
        )
    else:
        st.success(f"✅ Access Granted for Role: `{active_role}`")
        logs = governance.read_audit_logs(limit=25)
        if not logs:
            st.info("No audit events recorded yet. Run an Incident Triage or SOP Search first!")
        else:
            st.dataframe(logs, use_container_width=True)