import json
from datetime import datetime, timezone
from pathlib import Path


class SovereignGovernanceManager:
    """
    SLT Sovereign AI Governance & Audit Layer:
    Enforces Role-Based Access Control (RBAC) and maintains an immutable
    audit log of all AI queries, PII redactions, citations, and latency.
    """

    ROLES = {
        "Tier-1 NOC Engineer": {
            "can_analyze_incidents": True,
            "can_search_sops": True,
            "can_view_audit_logs": False,
            "allowed_classifications": ["Tier-1 Approved Technical Documentation"]
        },
        "Tier-2 Core Engineer": {
            "can_analyze_incidents": True,
            "can_search_sops": True,
            "can_view_audit_logs": True,
            "allowed_classifications": ["Tier-1 Approved Technical Documentation", "Tier-2 Restricted"]
        },
        "Sovereign Platform Auditor": {
            "can_analyze_incidents": True,
            "can_search_sops": True,
            "can_view_audit_logs": True,
            "allowed_classifications": ["Tier-1 Approved Technical Documentation", "Tier-2 Restricted"]
        }
    }

    def __init__(self, audit_log_path: Path):
        self.audit_log_path = audit_log_path
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    def check_permission(self, role: str, permission_key: str) -> bool:
        role_config = self.ROLES.get(role, {})
        return role_config.get(permission_key, False)

    def log_event(
        self,
        user_role: str,
        action_type: str,
        ticket_id: str,
        redactions_count: int,
        severity: str,
        citations: list[str],
        latency_ms: float,
        engine_mode: str
    ) -> dict:
        entry = {
            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "user_role": user_role,
            "action_type": action_type,
            "ticket_id": ticket_id,
            "redactions_applied": redactions_count,
            "assessed_severity": severity,
            "citations_used": citations,
            "latency_ms": round(latency_ms, 2),
            "engine_mode": engine_mode
        }
        with self.audit_log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return entry

    def read_audit_logs(self, limit: int = 50) -> list[dict]:
        if not self.audit_log_path.exists():
            return []
        lines = self.audit_log_path.read_text(encoding="utf-8").strip().splitlines()
        records = [json.loads(line) for line in lines if line.strip()]
        return list(reversed(records[-limit:]))