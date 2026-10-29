import importlib
import os
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
import agent.guardrails_evals as guard_mod
import agent.orchestrator as orch_mod

importlib.reload(cf_mod)
importlib.reload(aws_kb_mod)
importlib.reload(rag_mod)
importlib.reload(guard_mod)
importlib.reload(orch_mod)

from agent.orchestrator import SLTMobitelUnifiedAgent
from agent.governance import SovereignGovernanceManager
from agent.llm_gateway import SovereignLLMGateway
from retrieval.aws_kb_client import SLTMobitelCloudKBClient
from retrieval.cloudfront_gateway import SLTCloudFrontEdgeGateway

st.set_page_config(
    page_title="SLTMobitel AI Assistant",
    page_icon="💬",
    layout="wide"
)

# Clean, User-Friendly Chat Styling (No cluttered technical scorecards in the chat)
st.markdown(
    """
    <style>
    .clean-answer-text {
        font-size: 1.04rem;
        line-height: 1.62;
        color: #0f172a;
        margin-bottom: 0.5rem;
    }
    .privacy-badge {
        display: inline-block;
        background-color: #fef9c3;
        color: #854d0e;
        padding: 2px 10px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        margin-bottom: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

manuals_dir = BASE_DIR / "data" / "approved_manuals"
incidents_dir = BASE_DIR / "data" / "synthetic_incidents"
audit_log_path = BASE_DIR / "data" / "audit_trail.jsonl"


@st.cache_resource
def get_agent_and_governance(_version: str = "v6.2"):
    agent_inst = SLTMobitelUnifiedAgent(manuals_dir=manuals_dir, enable_embeddings=False)
    gov_inst = SovereignGovernanceManager(audit_log_path=audit_log_path)
    return agent_inst, gov_inst


agent, governance = get_agent_and_governance()
if not hasattr(agent.rag.aws_kb_client, "cloudfront"):
    agent.rag.aws_kb_client.cloudfront = SLTCloudFrontEdgeGateway(env_path=BASE_DIR / ".env")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None
if "pending_route" not in st.session_state:
    st.session_state.pending_route = "AUTO"


def queue_prompt(prompt_text: str, route: str = "AUTO"):
    st.session_state.pending_prompt = prompt_text
    st.session_state.pending_route = route


# ---------------------------------------------------------------------------
# SIDEBAR: Simple Session Controls + Optional Admin/Developer Drawer
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("💬 SLTMobitel AI")
    st.caption("Intelligent Customer & NetOps Chat Agent")

    if st.button("➕ Start New Chat", use_container_width=True, type="primary"):
        st.session_state.chat_history = []
        st.session_state.pending_prompt = None
        st.rerun()

    st.divider()
    st.markdown("### 🔎 Explore API KnowledgeBase")
    if st.button("📚 Scan & View All Documents in API", use_container_width=True):
        with st.spinner("Probing SLTMobitel AWS KnowledgeBase API (/prod/retrieve)..."):
            fresh_client = SLTMobitelCloudKBClient(env_path=BASE_DIR / ".env")
            st.session_state["discovered_kb_docs"] = fresh_client.discover_knowledge_base_contents()

    if "discovered_kb_docs" in st.session_state:
        docs_found = st.session_state["discovered_kb_docs"]
        if not docs_found:
            st.warning("Could not retrieve chunks from the API. Check your internet connection or secret key.")
        else:
            st.success(f"Found {len(docs_found)} unique document chunks in the API!")
            with st.expander(f"📖 View Discovered API Chunks ({len(docs_found)})", expanded=True):
                for d in docs_found:
                    st.markdown(f"**Chunk #{d['chunk_index']}** *(Score: `{d['score']}`)*")
                    st.caption(d["content"])
                    st.divider()

    st.divider()
    st.markdown("### 📎 Quick Test with a Sample Ticket")
    raw_files = sorted(incidents_dir.glob("*_raw.txt"))
    file_map = {f.name: f for f in raw_files}
    chosen_ticket_file = st.selectbox("Select NOC Incident Scenario:", options=list(file_map.keys()))
    if st.button("📨 Send Incident to Chat", use_container_width=True):
        ticket_content = file_map[chosen_ticket_file].read_text(encoding="utf-8")
        queue_prompt(ticket_content, route="NETOPS_INCIDENT")
        st.rerun()

    st.divider()
    with st.expander("⚙️ AI Model & Admin Diagnostics"):
        selected_engine = st.selectbox(
            "AI Model Backend:",
            options=[
                "AWS_BEDROCK",
                "LOCAL_GROUNDED_RULE_ENGINE",
                "GEMINI_CLOUD"
            ],
            index=0
        )

        ollama_model_input = None
        gemini_key_input = None
        bedrock_model_input = None
        aws_region_input = os.getenv("AWS_REGION", "us-east-1")
        aws_ak_input = os.getenv("AWS_ACCESS_KEY_ID", "")
        aws_sk_input = os.getenv("AWS_SECRET_ACCESS_KEY", "")

        if selected_engine == "AWS_BEDROCK":
            bedrock_model_input = st.selectbox(
                "AWS Bedrock Model:",
                options=SovereignLLMGateway.BEDROCK_MODELS,
                index=0
            )
            aws_region_input = st.text_input("AWS Region:", value=aws_region_input)
            aws_ak_input = st.text_input("AWS Access Key ID:", value=aws_ak_input, type="password")
            aws_sk_input = st.text_input("AWS Secret Access Key:", value=aws_sk_input, type="password")
        elif selected_engine == "GEMINI_CLOUD":
            gemini_key_input = st.text_input("Gemini API Key:", value=os.getenv("GEMINI_API_KEY", ""), type="password")

        route_choice = st.selectbox(
            "Routing Mode:",
            options=[
                "AUTO (Smart Intent Detection)",
                "AWS_CLOUD_KB (SLTMobitel API Only)",
                "NETOPS_INCIDENT (Local SOPs Only)",
                "HYBRID_BOTH (AWS KB + Local SOPs)"
            ],
            index=0
        )
        selected_route = route_choice.split()[0]

        kb_top_k = st.slider("AWS KB Top-K Chunks:", 1, 5, 3)
        cf_domain_input = st.text_input(
            "CloudFront Distribution Domain (Optional):",
            value=os.getenv("SLT_CLOUDFRONT_DOMAIN", ""),
            placeholder="e.g. d111111abcdef8.cloudfront.net"
        )
        kb_endpoint_input = st.text_input("API Gateway Origin Endpoint:", value=agent.rag.aws_kb_client.endpoint_url)
        kb_secret_input = st.text_input(
            "Origin Header `x-auth-secret`:",
            value=agent.rag.aws_kb_client.auth_secret,
            type="password"
        )

        # Display live CloudFront Edge Cache metrics
        cf_metrics = agent.rag.aws_kb_client.cloudfront.metrics
        st.caption(
            f"🌐 **CloudFront Edge Cache:** `{cf_metrics['cache_hits']}` Hits | "
            f"`{cf_metrics['cache_misses']}` Origin Fetches (`MAA50-P1 Edge`)"
        )
        if st.button("🔄 Invalidate CloudFront Edge Cache (`/*`)", use_container_width=True):
            agent.rag.aws_kb_client.cloudfront.clear_edge_cache()
            st.success("CloudFront Edge Cache invalidated!")

        show_dev_details = st.checkbox(
            "Show Developer / Source Inspector under replies",
            value=False,
            help="Enable only when you want to inspect retrieved chunks, sanitization, or internal eval metrics."
        )

        active_role = st.selectbox(
            "RBAC Role:",
            options=list(SovereignGovernanceManager.ROLES.keys()),
            index=1
        )


# ---------------------------------------------------------------------------
# HELPER: Render Clean, Natural Assistant Chat Message
# ---------------------------------------------------------------------------
def render_assistant_message(turn: dict, turn_index: int, is_latest: bool = False):
    # Subtle privacy note ONLY if sensitive PII/IP was automatically masked
    if turn.get("redactions_applied", 0) > 0:
        st.markdown(
            f'<div class="privacy-badge">🛡️ Privacy Guardrail: Automatically masked '
            f'{turn["redactions_applied"]} sensitive PII/IP detail(s)</div>',
            unsafe_allow_html=True
        )

    # Clear, natural answer right in the chat bubble
    st.markdown(turn["answer_markdown"])

    # If it's a critical network incident, show a clean alert
    if turn.get("escalation_required"):
        st.error(f"🚨 **Escalation Required:** {turn['escalation_target']}")

    # Clean bullet points (only when present and relevant)
    if turn.get("key_points") and turn.get("has_enough_knowledge", True):
        for kp in turn["key_points"]:
            st.markdown(f"- {kp}")

    # Optional Developer Inspector (hidden by default so end-users only see clean answers)
    if show_dev_details:
        with st.expander("🔍 Developer Diagnostics & Retrieved Sources"):
            st.caption(
                f"Route: `{turn['intent_route']}` | Engine: `{turn['inference_mode']}` | "
                f"Latency: `{turn['latency_ms']:.0f} ms`"
            )
            if turn.get("draft_handover_summary"):
                st.markdown("**Shift Handover Summary:**")
                st.code(turn["draft_handover_summary"], language="markdown")
            if turn.get("retrieved_chunks"):
                st.markdown("**Retrieved Chunks:**")
                for idx, ch in enumerate(turn["retrieved_chunks"], 1):
                    sc = ch.get("score", ch.get("similarity_score", 0.0))
                    st.markdown(f"**{idx}. `{ch['doc_id']}`** *(Score: `{sc}`)*")
                    st.caption(ch["content"])

    # Clickable follow-up suggestions under the latest assistant turn
    if is_latest and turn.get("suggested_followups"):
        f_cols = st.columns(len(turn["suggested_followups"]))
        for i, follow_q in enumerate(turn["suggested_followups"]):
            with f_cols[i]:
                if st.button(f"💬 {follow_q}", key=f"followup_{turn_index}_{i}", use_container_width=True):
                    queue_prompt(follow_q, route="AUTO")
                    st.rerun()


# ---------------------------------------------------------------------------
# MAIN CHAT INTERFACE
# ---------------------------------------------------------------------------
st.markdown("### 💬 SLTMobitel AI Assistant")
st.caption("Ask about SLTMobitel services & packages, or paste a network incident ticket for troubleshooting.")

# Friendly Welcome Bubble when chat is empty
if not st.session_state.chat_history and not st.session_state.pending_prompt:
    with st.chat_message("assistant", avatar="🤖"):
        st.markdown(
            "Hello! 👋 How can I help you today?\n\n"
            "I am connected to the **SLTMobitel AWS KnowledgeBase API** and the **NetOps SOP Assistant**. "
            "Ask me about **USSD self-care codes (`#1456#`, `#888#`, `#170#`), 4G LTE & PEOTV packages, "
            "APN & Credit Limit rules, Enterprise solutions**, or paste a **network fault ticket**."
        )
        s1, s2, s3, s4 = st.columns(4)
        with s1:
            if st.button("📱 Balance & USSD Codes (#1456# / #888#)", use_container_width=True):
                queue_prompt("How do I check my billing, account balance, and USSD self-care codes?", "AWS_CLOUD_KB")
                st.rerun()
        with s2:
            if st.button("📺 4G LTE & PEOTV Package Prices", use_container_width=True):
                queue_prompt("What are the SLTMobitel 4G LTE Home Broadband and PEOTV packages and prices?", "AWS_CLOUD_KB")
                st.rerun()
        with s3:
            if st.button("🚨 Diagnose BGP Optical Loss (-21.4 dBm)", use_container_width=True):
                queue_prompt(
                    "INCIDENT TICKET: INC-2026-1042 | AFFECTED NODE: SLT-CORE-PE-CMB-01 (172.16.45.128)\n"
                    "Contact: kasun@slt.com.lk (+94 71 234 5678). BGP-5-ADJCHANGE link flapped 7 times. "
                    "Optical Rx Power measured at -21.4 dBm.",
                    "NETOPS_INCIDENT"
                )
                st.rerun()
        with s4:
            if st.button("❓ Test an Unknown Question", use_container_width=True):
                queue_prompt("What is the weather forecast in Tokyo tomorrow?", "AWS_CLOUD_KB")
                st.rerun()

# Render Conversation Thread
total_turns = len(st.session_state.chat_history)
for idx, msg in enumerate(st.session_state.chat_history):
    with st.chat_message("user", avatar="🧑"):
        st.write(msg["user_input"])
    with st.chat_message("assistant", avatar="🤖"):
        render_assistant_message(msg["agent_response"], idx, is_latest=(idx == total_turns - 1))

# Bottom Chat Input Bar
chat_input_text = st.chat_input("Type your message here...")

active_user_message = None
route_for_turn = selected_route

if st.session_state.pending_prompt:
    active_user_message = st.session_state.pending_prompt
    if selected_route == "AUTO":
        route_for_turn = st.session_state.pending_route
    st.session_state.pending_prompt = None
elif chat_input_text and chat_input_text.strip():
    active_user_message = chat_input_text.strip()

if active_user_message:
    with st.chat_message("user", avatar="🧑"):
        st.write(active_user_message)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Thinking..."):
            turn_res = agent.run_agent(
                user_input=active_user_message,
                route_mode=route_for_turn,
                inference_engine=selected_engine,
                top_k=kb_top_k,
                conversation_history=st.session_state.chat_history,
                ollama_model=ollama_model_input,
                gemini_api_key=gemini_key_input,
                bedrock_model=bedrock_model_input,
                aws_region=aws_region_input,
                aws_access_key_id=aws_ak_input,
                aws_secret_access_key=aws_sk_input,
                kb_secret_override=kb_secret_input,
                kb_endpoint_override=kb_endpoint_input
            )
            governance.log_event(
                user_role=active_role,
                action_type=f"CHAT_{turn_res['intent_route']}",
                ticket_id="CHAT-AGENT",
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
            st.rerun()
