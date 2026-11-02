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
def get_agent_and_governance(_version: str = "v6.6"):
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
# SIDEBAR: Session Controls & Optional Admin Drawer
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("SLTMobitel Assistant")

    if st.button("New Chat", use_container_width=True, type="primary"):
        st.session_state.chat_history = []
        st.session_state.pending_prompt = None
        st.rerun()

    st.divider()
    st.markdown("**Sample Incident Tickets**")
    raw_files = sorted(incidents_dir.glob("*_raw.txt"))
    file_map = {f.name: f for f in raw_files}
    chosen_ticket_file = st.selectbox("Select scenario:", options=list(file_map.keys()), label_visibility="collapsed")
    if st.button("Load Incident Ticket", use_container_width=True):
        ticket_content = file_map[chosen_ticket_file].read_text(encoding="utf-8")
        queue_prompt(ticket_content, route="NETOPS_INCIDENT")
        st.rerun()

    st.divider()
    with st.expander("Settings & Diagnostics"):
        selected_engine = st.selectbox(
            "Model Backend:",
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
                "AWS Bedrock Model:",
                options=SovereignLLMGateway.BEDROCK_MODELS,
                index=0
            )

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

        kb_top_k = st.slider("Top-K Chunks:", 1, 5, 3)

        cf_metrics = agent.rag.aws_kb_client.cloudfront.metrics
        st.caption(
            f"Edge Cache: `{cf_metrics['cache_hits']}` Hits | "
            f"`{cf_metrics['cache_misses']}` Origin Fetches"
        )
        if st.button("Clear Cache", use_container_width=True):
            agent.rag.aws_kb_client.cloudfront.clear_edge_cache()
            st.success("Cache cleared.")

        show_dev_details = st.checkbox(
            "Show retrieved sources under replies",
            value=False
        )

        active_role = st.selectbox(
            "RBAC Role:",
            options=list(SovereignGovernanceManager.ROLES.keys()),
            index=1
        )


# ---------------------------------------------------------------------------
# HELPER: Render Clean Assistant Chat Message
# ---------------------------------------------------------------------------
def render_assistant_message(turn: dict, turn_index: int, is_latest: bool = False):
    if turn.get("redactions_applied", 0) > 0:
        st.markdown(
            f'<div class="privacy-badge">Masked {turn["redactions_applied"]} sensitive PII/IP detail(s)</div>',
            unsafe_allow_html=True
        )

    st.markdown(turn["answer_markdown"])

    if turn.get("escalation_required"):
        st.error(f"**Escalation Required:** {turn['escalation_target']}")

    if turn.get("key_points") and turn.get("has_enough_knowledge", True):
        for kp in turn["key_points"]:
            st.markdown(f"- {kp}")

    if show_dev_details:
        with st.expander("Diagnostics & Retrieved Sources"):
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


# ---------------------------------------------------------------------------
# MAIN CHAT INTERFACE
# ---------------------------------------------------------------------------
st.markdown("### SLTMobitel Assistant")

if not st.session_state.chat_history and not st.session_state.pending_prompt:
    with st.chat_message("assistant"):
        st.markdown("Hello! How can I help you today?")

# Render Conversation Thread
total_turns = len(st.session_state.chat_history)
for idx, msg in enumerate(st.session_state.chat_history):
    with st.chat_message("user"):
        st.write(msg["user_input"])
    with st.chat_message("assistant"):
        render_assistant_message(msg["agent_response"], idx, is_latest=(idx == total_turns - 1))

# Bottom Chat Input Bar
chat_input_text = st.chat_input("Ask a question or paste a network incident log...")

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
                bedrock_model=bedrock_model_input
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
