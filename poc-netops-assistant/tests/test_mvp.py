import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
BASE_DIR = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ingestion.sanitizer import SovereignDataSanitizer
from retrieval.rag_engine import SovereignNetOpsRAG


def test_pii_and_ip_sanitization():
    sanitizer = SovereignDataSanitizer()
    sample = "Contact kasun@slt.com.lk or +94 71 234 5678 on IP 172.16.45.128 with secret: my_pass_123"
    res = sanitizer.sanitize_text(sample)
    assert "[REDACTED_EMAIL]" in res["sanitized_text"]
    assert "[REDACTED_SL_PHONE]" in res["sanitized_text"]
    assert "[REDACTED_INTERNAL_IP]" in res["sanitized_text"]
    assert "[REDACTED_CREDENTIAL]" in res["sanitized_text"]
    assert "172.16.45.128" not in res["sanitized_text"]


def test_critical_optical_loss_escalation():
    manuals_dir = BASE_DIR / "data" / "approved_manuals"
    rag = SovereignNetOpsRAG(manuals_dir=manuals_dir)
    ticket = "BGP-5-ADJCHANGE link flapped 7 times. Optical Rx Power measured at -21.4 dBm."
    report = rag.analyze_incident(ticket)
    assert "CRITICAL" in report["severity"]
    assert any("SLT-NET-SOP-042" in c for c in report["citations"])