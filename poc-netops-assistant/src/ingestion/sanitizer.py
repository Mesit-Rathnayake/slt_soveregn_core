import re
import sys
from pathlib import Path

# Ensure Windows PowerShell/CMD outputs UTF-8 cleanly
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class SovereignDataSanitizer:
    """
    SLT Sovereign AI Governance Control:
    Sanitizes raw telecom incident logs by masking PII, internal IPv4 addresses,
    contact numbers, and credentials before AI ingestion or vector indexing.
    """

    def __init__(self):
        self.rules = [
            # 1. Mask Sri Lankan Phone Numbers (e.g., +94 71 234 5678 or 0771234567)
            (r"(\+94\s?\d{2}\s?\d{3}\s?\d{4}|\b0\d{2}[\s-]?\d{3}[\s-]?\d{4}\b)", "[REDACTED_SL_PHONE]"),
            # 2. Mask Email Addresses
            (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b", "[REDACTED_EMAIL]"),
            # 3. Mask Internal/Management IPv4 Addresses
            (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[REDACTED_INTERNAL_IP]"),
            # 4. Mask SNMP Community Strings / Passwords / Secrets
            (r"(?i)(community string|password|secret|key)(\s*[:=]\s*|\s+used for debugging:\s*)(\S+)", r"\1\2[REDACTED_CREDENTIAL]")
        ]

    def sanitize_text(self, raw_text: str) -> dict:
        sanitized = raw_text
        redaction_count = 0

        for pattern, replacement in self.rules:
            matches = re.findall(pattern, sanitized)
            redaction_count += len(matches)
            sanitized = re.sub(pattern, replacement, sanitized)

        return {
            "sanitized_text": sanitized,
            "redactions_applied": redaction_count
        }


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parents[2]
    raw_ticket_path = base_dir / "data" / "synthetic_incidents" / "inc_2026_1042_raw.txt"
    clean_ticket_path = base_dir / "data" / "synthetic_incidents" / "inc_2026_1042_sanitized.txt"

    if not raw_ticket_path.exists():
        print(f"[WARNING] Could not find {raw_ticket_path}.")
    else:
        raw_content = raw_ticket_path.read_text(encoding="utf-8")
        sanitizer = SovereignDataSanitizer()
        result = sanitizer.sanitize_text(raw_content)

        clean_ticket_path.write_text(result["sanitized_text"], encoding="utf-8")

        print("=" * 60)
        print("SLT SOVEREIGN AI - DATA SANITIZATION PIPELINE TEST")
        print("=" * 60)
        print(f"[OK] Total Sensitive Fields Masked: {result['redactions_applied']}")
        print(f"[OK] Saved Clean Ticket To: {clean_ticket_path.name}\n")
        print("--- PREVIEW OF SANITIZED INCIDENT TICKET ---")
        print(result["sanitized_text"])