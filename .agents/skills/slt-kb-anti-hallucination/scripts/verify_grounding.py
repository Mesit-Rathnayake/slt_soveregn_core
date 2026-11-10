import sys
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[4]
SRC_DIR = ROOT_DIR / "poc-netops-assistant" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent.orchestrator import SLTMobitelUnifiedAgent
from retrieval.cloudfront_gateway import KBConfigError


def run_audit() -> int:
    manuals_dir = ROOT_DIR / "poc-netops-assistant" / "data" / "approved_manuals"
    agent = SLTMobitelUnifiedAgent(manuals_dir=manuals_dir, enable_embeddings=False)

    mock_kb = {
        "query": "test",
        "chunks": [
            {
                "doc_id": "SLT-AWS-KB-01",
                "doc_title": "SLTMobitel Cloud KnowledgeBase (AWS)",
                "source_file": "aws-api-gateway:/prod/retrieve",
                "section": "Chunk #1 (Score: 0.65)",
                "content": (
                    "FAQ: My wifi is not working\n"
                    "1. Check if Wi-Fi is enabled on your device and the router is powered on.\n"
                    "2. Check if all cables are tightly connected.\n"
                    "3. Check if WLAN light is on and GPON light is green.\n"
                    "4. Restart the router.\n"
                    "FAQ: Internet connection is slow\n"
                    "1. Check usage to see if quota is exceeded via MySLT App/Portal (https://myslt.slt.lk/)\n"
                    "2. Restart router\n"
                    "3. Change Wi-Fi password\n"
                    "4. Check if Telephone line is tightly connected.\n"
                    "PEO Gold: 108 channels — Rs. 2,100. Speed: 100 Mbps. USSD code #1456#."
                ),
                "raw_content": "",
                "score": 0.65,
                "rerank_score": 0.70,
                "similarity_score": 0.70,
            }
        ],
        "count": 1,
    }

    # 1. Out-of-domain hallucination traps sharing words ('speed', 'light', 'gold', 'price', 'code')
    traps = [
        "What is the speed of light?",
        "What is the price of gold today?",
        "Write python code to sort a list",
        "What is the weather in Tokyo?",
        "Whats the Capital of Sri Lanka",
        "How do I book a flight to Colombo?",
    ]
    with patch.object(agent.rag, "retrieve_from_aws_kb", return_value=mock_kb):
        for q in traps:
            res = agent.run_agent(q, route_mode="AUTO", inference_engine="LOCAL_GROUNDED_RULE_ENGINE")
            assert res["has_enough_knowledge"] is False, f"Hallucinated on out-of-domain trap: {q}"

        # 2. Verify no ungrounded hardware claims (e.g. 'pinhole', 'pppoe') in router troubleshooting
        r_res = agent.run_agent(
            "my internet is not working",
            route_mode="AUTO",
            inference_engine="LOCAL_GROUNDED_RULE_ENGINE",
        )
        combined_out = (r_res["answer_markdown"] + " " + " ".join(r_res["key_points"])).lower()
        assert "pinhole" not in combined_out and "pppoe" not in combined_out, (
            "Found ungrounded pinhole/PPPoE claim in router troubleshooting output"
        )

    # 3. Verify SSRF / secret exfiltration protection on untrusted endpoint_override
    try:
        agent.rag.aws_kb_client.retrieve(
            "test", endpoint_override="https://evil.example.com/retrieve"
        )
        raise AssertionError("Expected KBConfigError for untrusted endpoint_override")
    except KBConfigError:
        pass

    print("[PASS] SLTMobitel Anti-Hallucination, Grounding & Security Audit succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_audit())
