import hashlib
import importlib
import sys
from pathlib import Path
import streamlit as st

SRC_DIR = Path(__file__).resolve().parents[1]
BASE_DIR = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import retrieval.cloudfront_gateway as cf_mod
import retrieval.aws_kb_client as aws_kb_mod
import retrieval.rag_engine as rag_mod
import voice.voice_agent as voice_mod
import mcp.slt_mcp_server as mcp_mod
import agent.guardrails_evals as guard_mod
import agent.orchestrator as orch_mod

importlib.reload(cf_mod)
importlib.reload(aws_kb_mod)
importlib.reload(rag_mod)
importlib.reload(voice_mod)
importlib.reload(mcp_mod)
importlib.reload(guard_mod)
importlib.reload(orch_mod)

from agent.orchestrator import SLTMobitelUnifiedAgent
from agent.governance import SovereignGovernanceManager
from agent.llm_gateway import SovereignLLMGateway
from retrieval.cloudfront_gateway import SLTCloudFrontEdgeGateway

st.set_page_config(
    page_title="AI Assistant",
    page_icon="💬",
    layout="wide"
)

# ---------------------------------------------------------------------------
# SLTMOBITEL BRAND STYLING (SLT Royal Blue #0056A4 + Mobitel Green #00A859)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Global layout & typography */
    .stApp {
        background-color: #f8fafc;
    }
    .block-container {
        max-width: 920px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }

    /* Top SLTMobitel brand banner */
    .slt-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 20px;
        border-radius: 12px;
        background: linear-gradient(135deg, #00478f 0%, #0066b3 58%, #00a859 100%);
        color: #ffffff;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 14px rgba(0, 71, 143, 0.12);
    }
    .slt-header-title {
        font-size: 1.2rem;
        font-weight: 700;
        letter-spacing: -0.01em;
        margin: 0;
        color: #ffffff;
    }
    .slt-header-sub {
        font-size: 0.82rem;
        opacity: 0.92;
        margin: 2px 0 0 0;
        color: #e2f1ff;
    }
    .slt-status-pill {
        background: rgba(255, 255, 255, 0.16);
        border: 1px solid rgba(255, 255, 255, 0.28);
        color: #ffffff;
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
        white-space: nowrap;
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
    }
    .sidebar-brand {
        padding: 10px 14px;
        border-left: 4px solid #00a859;
        background: #f0f7ff;
        border-radius: 0 8px 8px 0;
        margin-bottom: 1rem;
    }
    .sidebar-brand-title {
        font-weight: 700;
        font-size: 1rem;
        color: #00478f;
        margin: 0;
    }
    .sidebar-brand-sub {
        font-size: 0.76rem;
        color: #475569;
        margin: 0;
    }

    /* Buttons: SLTMobitel Blue & Green hover state */
    .stButton > button {
        border-radius: 8px;
        border: 1px solid #cbd5e1;
        background-color: #ffffff;
        color: #0f172a;
        font-size: 0.86rem;
        font-weight: 500;
        transition: all 0.15s ease;
    }
    .stButton > button:hover {
        border-color: #00a859;
        color: #00478f;
        background-color: #f0fdf4;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #0056a4 0%, #00a859 100%);
        color: #ffffff;
        border: none;
        font-weight: 600;
    }
    .stButton > button[kind="primary"]:hover {
        opacity: 0.94;
        color: #ffffff;
    }

    /* Chat messages */
    div[data-testid="stChatMessage"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 12px 16px;
        margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
    }

    /* Subtle PII privacy pill */
    .privacy-badge {
        display: inline-block;
        background-color: #ecfdf5;
        color: #047857;
        border: 1px solid #a7f3d0;
        padding: 2px 10px;
        border-radius: 999px;
        font-size: 0.74rem;
        font-weight: 600;
        margin-bottom: 6px;
    }

    /* Chat input bar accent */
    div[data-testid="stChatInput"] {
        border-color: #0056a4;
    }
    </style>
    """,
    unsafe_allow_html=True
)

manuals_dir = BASE_DIR / "data" / "approved_manuals"
incidents_dir = BASE_DIR / "data" / "synthetic_incidents"
audit_log_path = BASE_DIR / "data" / "audit_trail.jsonl"


def _compute_code_hash() -> str:
    """Computes a fast hash of source file modification times so Streamlit invalidates cache on any code change."""
    h = hashlib.md5()
    for py_file in sorted(SRC_DIR.rglob("*.py")):
        try:
            h.update(f"{py_file.name}:{py_file.stat().st_mtime_ns}".encode("utf-8"))
        except OSError:
            pass
    return h.hexdigest()


@st.cache_resource
def get_agent_and_governance(_code_hash: str):
    import agent.llm_gateway as llm_mod
    importlib.reload(cf_mod)
    importlib.reload(aws_kb_mod)
    importlib.reload(llm_mod)
    importlib.reload(rag_mod)
    importlib.reload(voice_mod)
    importlib.reload(mcp_mod)
    importlib.reload(guard_mod)
    importlib.reload(orch_mod)
    agent_inst = orch_mod.SLTMobitelUnifiedAgent(manuals_dir=manuals_dir, enable_embeddings=False)
    gov_inst = SovereignGovernanceManager(audit_log_path=audit_log_path)
    return agent_inst, gov_inst


agent, governance = get_agent_and_governance(_compute_code_hash())
if not hasattr(agent.rag.aws_kb_client, "cloudfront"):
    agent.rag.aws_kb_client.cloudfront = SLTCloudFrontEdgeGateway(env_path=BASE_DIR / ".env")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "session_memory" not in st.session_state:
    st.session_state.session_memory = {}
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None
if "pending_route" not in st.session_state:
    st.session_state.pending_route = "AUTO"
if "pending_from_voice" not in st.session_state:
    st.session_state.pending_from_voice = False
if "last_audio_hash" not in st.session_state:
    st.session_state.last_audio_hash = None
if "active_role" not in st.session_state:
    st.session_state.active_role = "Existing Customer"
if "current_page" not in st.session_state:
    st.session_state.current_page = "💬 AI Assistant"


def queue_prompt(prompt_text: str, route: str = "AUTO", from_voice: bool = False):
    st.session_state.pending_prompt = prompt_text
    st.session_state.pending_route = route
    st.session_state.pending_from_voice = from_voice


# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <p class="sidebar-brand-title">AI Assistant</p>
            <p class="sidebar-brand-sub">Support & Operations</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    if st.button("New Conversation", use_container_width=True, type="primary"):
        st.session_state.chat_history = []
        st.session_state.session_memory = {}
        st.session_state.pending_prompt = None
        st.session_state.pending_from_voice = False
        st.rerun()

    st.divider()
    st.caption("NAVIGATION")
    current_page = st.radio(
        "Navigation",
        options=["💬 AI Assistant", "🛡️ Role & Access Portal"],
        index=0 if st.session_state.current_page == "💬 AI Assistant" else 1,
        label_visibility="collapsed",
        key="sidebar_nav_radio"
    )
    st.session_state.current_page = current_page

    st.divider()
    enable_voice_agent = st.toggle("Auto-play voice responses", value=False, key="toggle_voice_agent")

    st.divider()
    st.caption("CURRENT ACTIVE ROLE")
    active_role = st.session_state.active_role
    if active_role == "Existing Customer":
        st.success("👤 **Existing Customer**\n\nAccount: `SLT-ACC-0112456789`\n\nFault ticketing: **Enabled**")
    elif active_role == "New Customer":
        st.info("👋 **New Customer**\n\nPlan exploration mode.\n\nFault ticketing: **Restricted**")
    else:
        st.warning(f"🔧 **Staff:** {active_role}")

    if st.session_state.current_page == "💬 AI Assistant":
        if st.button("Change Role / Permissions", use_container_width=True):
            st.session_state.current_page = "🛡️ Role & Access Portal"
            st.rerun()

    st.divider()
    st.caption("NETWORK INCIDENT SCENARIOS")
    raw_files = sorted(incidents_dir.glob("*_raw.txt"))
    file_map = {f.name.replace("_raw.txt", "").replace("_", " ").title(): f for f in raw_files}
    chosen_label = st.selectbox("Scenario", options=list(file_map.keys()), label_visibility="collapsed")
    if st.button("Load Incident Log", use_container_width=True):
        ticket_content = file_map[chosen_label].read_text(encoding="utf-8")
        queue_prompt(ticket_content, route="NETOPS_INCIDENT")
        st.rerun()

    st.divider()
    with st.expander("System Settings"):
        selected_engine = st.selectbox(
            "Model Backend",
            options=[
                "AWS_BEDROCK",
                "LOCAL_GROUNDED_RULE_ENGINE",
                "GEMINI_CLOUD"
            ],
            index=0
        )

        bedrock_model_input = None
        if selected_engine == "AWS_BEDROCK":
            bedrock_model_input = st.selectbox(
                "Bedrock Model",
                options=SovereignLLMGateway.BEDROCK_MODELS,
                index=0
            )

        route_choice = st.selectbox(
            "Routing Mode",
            options=[
                "AUTO (Smart Detection)",
                "AWS_CLOUD_KB (KnowledgeBase Only)",
                "NETOPS_INCIDENT (NetOps SOPs Only)",
                "HYBRID_BOTH (Combined)"
            ],
            index=0
        )
        selected_route = route_choice.split()[0]
        kb_top_k = st.slider("Retrieved Chunks", 1, 5, 3)
        show_dev_details = st.checkbox("Show retrieved sources", value=False)
        cf_metrics = agent.rag.aws_kb_client.cloudfront.metrics
        st.caption(
            f"Edge Cache: {cf_metrics['cache_hits']} hits · {cf_metrics['cache_misses']} fetches"
        )
        if st.button("Clear Edge Cache", use_container_width=True):
            agent.mcp_server.call_tool("slt_cloudfront_cache_status", {"action": "invalidate"})
            st.toast("Edge cache cleared.")


# ---------------------------------------------------------------------------
# HELPER: Render Assistant Message
# ---------------------------------------------------------------------------
def render_assistant_message(turn: dict, turn_index: int, is_latest: bool = False):
    if turn.get("redactions_applied", 0) > 0:
        st.markdown(
            f'<div class="privacy-badge">Protected {turn["redactions_applied"]} sensitive field(s)</div>',
            unsafe_allow_html=True
        )

    st.markdown(turn["answer_markdown"])

    if turn.get("escalation_required"):
        st.warning(f"**Escalation Target:** {turn['escalation_target']}")

    if turn.get("key_points") and turn.get("has_enough_knowledge", True):
        for kp in turn["key_points"]:
            st.markdown(f"- {kp}")

    spoken_text = turn.get("spoken_response", "")
    from_voice_input = turn.get("from_voice_input", False)
    if spoken_text and (enable_voice_agent or from_voice_input):
        mp3_bytes = agent.voice_agent.synthesize_speech_mp3(spoken_text)
        if mp3_bytes:
            should_autoplay = bool(is_latest and (enable_voice_agent or from_voice_input))
            st.audio(mp3_bytes, format="audio/mp3", autoplay=should_autoplay)

    if show_dev_details:
        with st.expander("Sources & Trace"):
            mcp_used = turn.get("mcp_tool_called", "N/A")
            st.caption(
                f"Route: `{turn['intent_route']}` · Tool: `{mcp_used}` · "
                f"Latency: `{turn['latency_ms']:.0f} ms`"
            )
            if turn.get("draft_handover_summary"):
                st.code(turn["draft_handover_summary"], language="markdown")
            if turn.get("retrieved_chunks"):
                for idx, ch in enumerate(turn["retrieved_chunks"], 1):
                    sc = ch.get("score", ch.get("similarity_score", 0.0))
                    st.markdown(f"**{idx}. `{ch['doc_id']}`** (`{sc}`)")
                    st.caption(ch["content"])

# ---------------------------------------------------------------------------
# MAIN INTERFACE
# ---------------------------------------------------------------------------
if st.session_state.current_page == "💬 AI Assistant":
    active_role = st.session_state.active_role
    role_icon = "👤" if active_role == "Existing Customer" else ("👋" if active_role == "New Customer" else "🔧")
    st.markdown(
        f"""
        <div class="slt-header">
            <div>
                <p class="slt-header-title">AI Assistant</p>
                <p class="slt-header-sub">Technical Support & Operations</p>
            </div>
            <span class="slt-status-pill">{role_icon} {active_role}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    if not st.session_state.chat_history and not st.session_state.pending_prompt:
        st.markdown("##### How can I help you today?")
        c1, c2 = st.columns(2)
        if active_role == "Existing Customer":
            with c1:
                if st.button("📱 Check active packages & USSD codes (#888# / #1456#)", use_container_width=True, key="btn_ext_ussd"):
                    queue_prompt("How to see active packages", "AWS_CLOUD_KB")
                    st.rerun()
                if st.button("📊 Show my account profile & data balance", use_container_width=True, key="btn_ext_account"):
                    queue_prompt("Show my account status", "AWS_CLOUD_KB")
                    st.rerun()
            with c2:
                if st.button("⚡ What Fibre packages are under Rs. 5,000?", use_container_width=True, key="btn_ext_fibre"):
                    queue_prompt("What Fibre packages are under Rs. 5,000?", "AWS_CLOUD_KB")
                    st.rerun()
                if st.button("🔧 Router & Wi-Fi troubleshooting steps", use_container_width=True, key="btn_ext_router"):
                    queue_prompt("How do I restart or troubleshoot my router?", "AWS_CLOUD_KB")
                    st.rerun()
        elif active_role == "New Customer":
            with c1:
                if st.button("⚡ What Fibre packages are under Rs. 5,000?", use_container_width=True, key="btn_new_fibre"):
                    queue_prompt("What Fibre packages are under Rs. 5,000?", "AWS_CLOUD_KB")
                    st.rerun()
                if st.button("📺 4G LTE Home Broadband & PEOTV packages", use_container_width=True, key="btn_new_lte"):
                    queue_prompt("What are the SLTMobitel 4G LTE Home Broadband and PEOTV packages and prices?", "AWS_CLOUD_KB")
                    st.rerun()
            with c2:
                if st.button("🚀 High-speed packages (>= 500 Mbps)", use_container_width=True, key="btn_new_highspeed"):
                    queue_prompt("Show me packages with at least 500 Mbps", "AWS_CLOUD_KB")
                    st.rerun()
                if st.button("📝 How do I apply for a new SLT connection?", use_container_width=True, key="btn_new_apply"):
                    queue_prompt("How do I apply for a new SLT connection?", "AWS_CLOUD_KB")
                    st.rerun()
        else:
            with c1:
                if st.button("Check active packages & USSD codes (#888# / #1456#)", use_container_width=True, key="btn_staff_packages"):
                    queue_prompt("How to see active packages", "AWS_CLOUD_KB")
                    st.rerun()
                if st.button("Router & Wi-Fi troubleshooting steps", use_container_width=True, key="btn_staff_router"):
                    queue_prompt("How do I restart or troubleshoot my router?", "AWS_CLOUD_KB")
                    st.rerun()
            with c2:
                if st.button("4G LTE Home Broadband & PEOTV packages", use_container_width=True, key="btn_staff_lte"):
                    queue_prompt("What are the SLTMobitel 4G LTE Home Broadband and PEOTV packages and prices?", "AWS_CLOUD_KB")
                    st.rerun()
                if st.button("Diagnose BGP optical signal loss (-21.4 dBm)", use_container_width=True, key="btn_staff_bgp"):
                    queue_prompt(
                        "INCIDENT TICKET: INC-2026-1042 | AFFECTED NODE: SLT-CORE-PE-CMB-01 (172.16.45.128)\n"
                        "Contact: kasun@slt.com.lk (+94 71 234 5678). BGP-5-ADJCHANGE link flapped 7 times. "
                        "Optical Rx Power measured at -21.4 dBm.",
                        "NETOPS_INCIDENT"
                    )
                    st.rerun()

    # Render Conversation Thread
    total_turns = len(st.session_state.chat_history)
    for idx, msg in enumerate(st.session_state.chat_history):
        with st.chat_message("user"):
            st.write(msg["user_input"])
        with st.chat_message("assistant"):
            render_assistant_message(msg["agent_response"], idx, is_latest=(idx == total_turns - 1))

    # Standard AI Agent Chat Input Bar with Integrated Microphone Input (accept_audio=True)
    chat_submission = st.chat_input(
        "Ask a question or click the mic to speak...",
        accept_audio=True
    )

    active_user_message = None
    route_for_turn = selected_route
    is_voice_turn = False

    if st.session_state.pending_prompt:
        active_user_message = st.session_state.pending_prompt
        is_voice_turn = bool(st.session_state.get("pending_from_voice", False))
        if selected_route == "AUTO":
            route_for_turn = st.session_state.pending_route
        st.session_state.pending_prompt = None
        st.session_state.pending_from_voice = False
    elif chat_submission is not None:
        if isinstance(chat_submission, str):
            if chat_submission.strip():
                active_user_message = chat_submission.strip()
        else:
            # ChatInputValue with .text and/or .audio
            if getattr(chat_submission, "audio", None) is not None:
                audio_bytes = chat_submission.audio.getvalue()
                audio_hash = hashlib.sha256(audio_bytes).hexdigest()
                if audio_hash != st.session_state.last_audio_hash:
                    st.session_state.last_audio_hash = audio_hash
                    with st.spinner("Listening..."):
                        stt_res = agent.voice_agent.transcribe_audio_bytes(audio_bytes)
                    if stt_res.get("success") and stt_res.get("transcript"):
                        active_user_message = stt_res["transcript"]
                        is_voice_turn = True
                    else:
                        st.warning(stt_res.get("error", "Could not recognize speech. Please try again."))
            elif getattr(chat_submission, "text", None) and chat_submission.text.strip():
                active_user_message = chat_submission.text.strip()

    if active_user_message:
        with st.chat_message("user"):
            st.write(active_user_message)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                turn_res = agent.run_agent(
                    user_input=active_user_message,
                    route_mode=route_for_turn,
                    inference_engine=selected_engine,
                    top_k=kb_top_k,
                    conversation_history=st.session_state.chat_history,
                    session_memory=st.session_state.session_memory,
                    bedrock_model=bedrock_model_input,
                    user_role=active_role
                )
                turn_res["from_voice_input"] = is_voice_turn
                governance.log_event(
                    user_role=active_role,
                    action_type=f"{'VOICE' if is_voice_turn else 'CHAT'}_{turn_res['intent_route']}",
                    ticket_id="VOICE-AGENT" if is_voice_turn else "CHAT-AGENT",
                    redactions_count=turn_res["redactions_applied"],
                    severity=turn_res["severity"],
                    citations=turn_res["citations"],
                    latency_ms=turn_res["latency_ms"],
                    engine_mode=turn_res["inference_mode"]
                )
                st.session_state.chat_history.append({
                    "user_input": active_user_message,
                    "agent_response": turn_res
                })
                st.session_state.session_memory = turn_res.get(
                    "session_memory",
                    st.session_state.session_memory,
                )
                st.rerun()

else:
    # -----------------------------------------------------------------------
    # DEDICATED ROLE-BASED ACCESS CONTROL & CUSTOMER PORTAL PAGE
    # -----------------------------------------------------------------------
    st.markdown(
        """
        <div class="slt-header">
            <div>
                <p class="slt-header-title">Role-Based Access Control (RBAC) Portal</p>
                <p class="slt-header-sub">Customer Segmentation, Privileges & Live Account Gateway</p>
            </div>
            <span class="slt-status-pill">SLT Security Layer</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("### 1. Select Active Role")
    role_options = list(SovereignGovernanceManager.ROLES.keys())
    selected_portal_role = st.selectbox(
        "Current Active Profile",
        options=role_options,
        index=role_options.index(st.session_state.active_role),
        key="select_portal_active_role"
    )
    if selected_portal_role != st.session_state.active_role:
        st.session_state.active_role = selected_portal_role
        st.success(f"Role updated to: **{selected_portal_role}**")
        st.rerun()

    if selected_portal_role == "Existing Customer":
        st.success(
            "👤 **Existing Customer (Subscriber):** Authenticated access. "
            "Can view account balance/data remaining, query all packages, and **log or track fault tickets**."
        )
    elif selected_portal_role == "New Customer":
        st.info(
            "👋 **New Customer (Visitor / Prospect):** General conversational assistant. "
            "Can browse packages, explore speeds/prices, and check coverage. "
            "**Fault ticketing and private billing stats are locked** until registered."
        )
    else:
        st.warning(
            f"🔧 **Internal Staff Role ({selected_portal_role}):** "
            "Full engineering access to BGP/OSPF SOP manuals, incident diagnostics, and governance audit logs."
        )

    st.divider()

    st.markdown("### 2. Privilege Comparison Matrix")
    matrix_data = [
        {"Role": "Existing Customer", "Package / KB Search": "✅ Full", "Fault Ticketing": "✅ Allowed", "Account / Usage Stats": "✅ Allowed", "NetOps Incident SOPs": "❌ Restricted", "Audit Logs": "❌ Restricted"},
        {"Role": "New Customer", "Package / KB Search": "✅ Full", "Fault Ticketing": "❌ Restricted", "Account / Usage Stats": "❌ Restricted", "NetOps Incident SOPs": "❌ Restricted", "Audit Logs": "❌ Restricted"},
        {"Role": "Tier-1 NOC Agent", "Package / KB Search": "✅ Full", "Fault Ticketing": "✅ Allowed", "Account / Usage Stats": "✅ Allowed", "NetOps Incident SOPs": "✅ Full", "Audit Logs": "❌ Restricted"},
        {"Role": "Tier-2 Core Engineer", "Package / KB Search": "✅ Full", "Fault Ticketing": "✅ Allowed", "Account / Usage Stats": "✅ Allowed", "NetOps Incident SOPs": "✅ Full", "Audit Logs": "✅ Full"},
        {"Role": "Sovereign Auditor", "Package / KB Search": "✅ Full", "Fault Ticketing": "❌ Restricted", "Account / Usage Stats": "✅ Allowed", "NetOps Incident SOPs": "✅ Full", "Audit Logs": "✅ Full"}
    ]
    st.dataframe(matrix_data, use_container_width=True, hide_index=True)

    st.divider()

    st.markdown("### 3. Customer Account & Ticketing Gateway (Stub / Live)")
    tab1, tab2, tab3 = st.tabs(["📊 Account Profile", "🎫 Log Fault Ticket", "🔍 Track Ticket Status"])

    with tab1:
        prof = agent.mcp_server.account_gateway.get_account_profile("0112456789")
        st.markdown(
            f"""
            - **Account Number:** `{prof['account_id']}`
            - **Subscriber Name:** {prof['customer_name']}
            - **Connection Status:** `{prof['connection_status']}`
            - **Subscribed Package:** {prof['subscribed_package']}
            - **Data Remaining:** **{prof['data_remaining_gb']} GB** / {prof['data_total_gb']} GB
            - **Current Bill:** **Rs. {prof['current_balance_rs']:,.2f}** (Due Date: {prof['bill_due_date']})
            - **Optical Rx Power:** {prof['optical_rx_power_dbm']} dBm
            - **Gateway Status:** `{prof['gateway_status']}`
            """
        )

    with tab2:
        if st.session_state.active_role == "New Customer":
            st.warning("⚠️ New Customers cannot create fault tickets. Please switch to **Existing Customer** above.")
        else:
            with st.form("portal_fault_form"):
                svc = st.selectbox("Service Category", ["Fibre", "4G LTE", "PEOTV", "Copper Voice"])
                desc = st.text_area("Issue Description", value="Optical LOS LED is solid red, router restarted but no connection")
                contact = st.text_input("Contact Mobile", value="071 234 5678")
                submitted = st.form_submit_button("Submit Fault Ticket", type="primary")
                if submitted:
                    tick_res = agent.mcp_server.account_gateway.create_fault_ticket(
                        identifier="SLT-ACC-0112456789",
                        service_type=svc,
                        issue_description=desc,
                        contact_number=contact
                    )
                    st.success(f"✅ Ticket Logged: `{tick_res['ticket_id']}` (Target SLA: {tick_res['ticket_details']['target_sla']})")
                    st.markdown(tick_res["summary_markdown"])

    with tab3:
        query_tid = st.text_input("Enter Ticket Reference (e.g. FLT-2026-1042)", value="FLT-2026-1042", key="input_portal_tid")
        if st.button("Check Ticket Progress", key="btn_portal_check_tid"):
            status_obj = agent.mcp_server.account_gateway.get_ticket_status(query_tid)
            if status_obj["found"]:
                st.info(status_obj["summary_markdown"])
            else:
                st.error(status_obj["summary_markdown"])

    st.divider()

    st.markdown("### 4. Supervisor CRM Key Configuration")
    is_live = agent.mcp_server.account_gateway.is_live_crm_enabled
    if is_live:
        st.success("🟢 **Live CRM Key Configured:** The system is connected to the upstream SLTMobitel customer data API.")
    else:
        st.info(
            "🟡 **Running in Stub Mode (Realistic Mock Data):** "
            "To connect to the live SLT CRM when your supervisor provides the key, "
            "add `SLT_CUSTOMER_DATA_API_KEY=\"<key>\"` to `.env` or Streamlit Cloud Secrets. "
            "The gateway will automatically switch to production data without any code changes."
        )

    st.divider()
    if st.button("← Return to Chat Assistant", type="primary", use_container_width=True, key="btn_portal_return_chat"):
        st.session_state.current_page = "💬 AI Assistant"
        st.rerun()
