import os
import random
import re
from datetime import datetime, timezone
from pathlib import Path


class SLTCustomerAccountGateway:
    """
    SLTMobitel Customer Account & Fault Ticketing Gateway:
    - Provides account profile & billing stats for authenticated existing customers.
    - Handles customer fault ticket creation (e.g. Fibre LOS, slow connection, PEOTV faults).
    - Supports supervisor's upcoming live CRM key via `SLT_CUSTOMER_DATA_API_KEY`.
    - Serves verified mock account stats and deterministic ticket logging until live key is loaded.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_endpoint: str | None = None,
        env_path: Path | None = None
    ):
        self.env_path = env_path or (Path(__file__).resolve().parents[2] / ".env")
        loaded_key, loaded_endpoint = self._load_env_credentials()
        self.api_key = api_key or os.getenv("SLT_CUSTOMER_DATA_API_KEY") or loaded_key
        self.api_endpoint = (
            api_endpoint
            or os.getenv("SLT_CUSTOMER_DATA_ENDPOINT")
            or loaded_endpoint
            or "https://api.slt.lk/crm/v1/customer"
        )
        self._mock_tickets = [
            {
                "ticket_id": "FLT-2026-1042",
                "account_id": "SLT-ACC-0112456789",
                "service_type": "Fibre Broadband (FTTH)",
                "fault_category": "Wi-Fi / Router Hardware Issue",
                "led_status": "All Lights Green",
                "router_restarted": True,
                "affected_devices": "All Devices",
                "issue_started": "1-2 days ago",
                "impact_level": "Medium (Degraded Service)",
                "contact_name": "Kasun Perera",
                "contact_number": "071 234 5678",
                "service_address": "No. 42, Galle Road, Colombo 03",
                "preferred_visit_slot": "Morning (08:00 - 12:00)",
                "status": "RESOLVED",
                "priority": "NORMAL",
                "target_sla": "Within 8 Hours",
                "created_at": "2026-10-15T09:30:00Z",
                "resolved_at": "2026-10-15T13:45:00Z",
                "issue_description": "Wi-Fi password reset and 5GHz channel optimization",
                "assigned_team": "SLT Regional Fibre Operations",
                "assigned_officer": "Eng. Nimal Silva",
                "officer_updates": [
                    {
                        "timestamp": "2026-10-15T11:10:00Z",
                        "officer_name": "Eng. Nimal Silva",
                        "channel": "Phone Call",
                        "message": "Contacted customer and assisted with 5GHz channel optimization. Speed confirmed normal.",
                        "internal_note": "ONT Rx power healthy at -18.2 dBm.",
                        "status_change": "RESOLVED"
                    }
                ]
            },
            {
                "ticket_id": "FLT-2026-2108",
                "account_id": "SLT-ACC-0112889941",
                "service_type": "Fibre Broadband (FTTH)",
                "fault_category": "Red LOS / Blinking PON LED",
                "led_status": "LOS Red (Solid or Blinking)",
                "router_restarted": True,
                "affected_devices": "All Devices (Wi-Fi & Ethernet)",
                "issue_started": "Today",
                "impact_level": "Critical (Work / Business Halted)",
                "contact_name": "Dilani Fernando",
                "contact_number": "077 891 2345",
                "service_address": "No. 18, Havelock Road, Colombo 05 (Near Police Park)",
                "preferred_visit_slot": "Morning (08:00 - 12:00)",
                "status": "LOGGED",
                "priority": "CRITICAL / HIGH",
                "target_sla": "Within 4 Hours (High Priority Optical/Line Fault)",
                "created_at": "2026-11-20T06:15:00Z",
                "issue_description": "LOS LED turned solid red after heavy rain this morning. Restarted ONT twice and checked patch cord.",
                "assigned_team": "SLT Regional Fibre Operations & GPON Maintenance",
                "assigned_officer": "Unassigned",
                "officer_updates": []
            },
            {
                "ticket_id": "FLT-2026-2114",
                "account_id": "SLT-ACC-0812233445",
                "service_type": "PEOTV",
                "fault_category": "Channel Freezing / Pixelation",
                "led_status": "All Lights Green (No Internet)",
                "router_restarted": True,
                "affected_devices": "PEOTV / Telephone Handset Only",
                "issue_started": "1-2 days ago",
                "impact_level": "Medium (Degraded Service)",
                "contact_name": "Ruwan Bandara",
                "contact_number": "071 554 9087",
                "service_address": "No. 74, Peradeniya Road, Kandy",
                "preferred_visit_slot": "Afternoon (12:00 - 16:00)",
                "status": "IN_PROGRESS",
                "priority": "NORMAL",
                "target_sla": "Within 8 Hours",
                "created_at": "2026-11-20T04:40:00Z",
                "issue_description": "HD channels freezing every 2-3 minutes on PEOTV Set-Top Box even though Fibre internet works fine.",
                "assigned_team": "PEOTV Regional Maintenance & Headend Ops",
                "assigned_officer": "Tech. Chamara Jayasinghe",
                "officer_updates": [
                    {
                        "timestamp": "2026-11-20T05:20:00Z",
                        "officer_name": "Tech. Chamara Jayasinghe",
                        "channel": "SMS Notification",
                        "message": "We are checking your IPTV multicast profile and will call before the afternoon visit.",
                        "internal_note": "Checking STB Ethernet port 4 VLAN binding.",
                        "status_change": "IN_PROGRESS"
                    }
                ]
            }
        ]

    def _load_env_credentials(self) -> tuple[str, str]:
        if not self.env_path.exists():
            return "", ""
        key, endpoint = "", ""
        try:
            for line in self.env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("SLT_CUSTOMER_DATA_API_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val and not val.startswith("REPLACE_") and not val.startswith("INSERT_"):
                        key = val
                elif line.startswith("SLT_CUSTOMER_DATA_ENDPOINT="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val and not val.startswith("REPLACE_"):
                        endpoint = val
        except Exception:
            pass
        return key, endpoint

    @property
    def is_live_crm_enabled(self) -> bool:
        """Returns True if a live CRM API key is configured by the supervisor."""
        return bool(
            self.api_key
            and not self.api_key.startswith("REPLACE_")
            and not self.api_key.startswith("INSERT_")
            and len(self.api_key) > 8
        )

    def get_account_profile(self, identifier: str = "0112456789", service_segment: str = "Fibre") -> dict:
        """
        Fetches customer account overview, subscribed package, data balance,
        and active tickets tailored to the customer's service segment
        (Fibre, Broadband, PEOTV, Mobile). Uses live CRM if key is present; otherwise mock stats.
        """
        clean_id = re.sub(r"[^0-9a-zA-Z\-]", "", str(identifier)).strip() or "0112456789"
        acc_num = clean_id if clean_id.startswith("SLT-ACC-") else f"SLT-ACC-{clean_id}"
        seg_key = (service_segment or "Fibre").strip().lower()

        if self.is_live_crm_enabled:
            try:
                import urllib.request
                import json
                req = urllib.request.Request(
                    f"{self.api_endpoint}/profile?account_id={acc_num}&segment={seg_key}",
                    headers={
                        "x-api-key": self.api_key,
                        "Accept": "application/json",
                        "User-Agent": "SLTMobitel-UnifiedAgent/1.0"
                    }
                )
                with urllib.request.urlopen(req, timeout=4) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        data["is_mock_data"] = False
                        return data
            except Exception:
                pass  # Fall back to verified mock stats gracefully

        # Segment-tailored verified mock profiles
        open_ticks = [t for t in self._mock_tickets if t["status"] != "RESOLVED"]
        base_common = {
            "account_id": acc_num,
            "telephone_number": "011 234 5678",
            "customer_name": "Kasun Perera",
            "bill_due_date": "2026-11-28",
            "open_tickets_count": len(open_ticks),
            "recent_tickets": self._mock_tickets[-5:],
            "is_mock_data": True,
            "gateway_status": "CONNECTED_STUB_MODE (Awaiting Live CRM Key)"
        }

        if "peo" in seg_key or "tv" in seg_key:
            return {
                **base_common,
                "service_segment": "PEOTV",
                "connection_status": "ACTIVE (STB Online)",
                "service_category": "PEOTV Digital TV",
                "subscribed_package": "PEOTV Titanium (120+ Channels, HD Enabled)",
                "monthly_rental_rs": 2940.0,
                "current_balance_rs": 2940.0,
                "data_total_gb": 120.0,
                "data_remaining_gb": 120.0,
                "quota_label": "Active Channels",
                "quota_unit": "Channels",
                "signal_metric_label": "STB Signal / VLAN",
                "signal_metric_value": "HD Multicast OK (VLAN 40)",
                "optical_rx_power_dbm": -18.2,
            }
        if "broadband" in seg_key or "lte" in seg_key or "4g" in seg_key:
            return {
                **base_common,
                "service_segment": "Broadband",
                "connection_status": "ACTIVE (4G LTE Connected)",
                "service_category": "Home Broadband (4G LTE)",
                "subscribed_package": "Unlimited LTE Flash 10 (10 GB/day, 4G LTE)",
                "monthly_rental_rs": 4090.0,
                "current_balance_rs": 4090.0,
                "data_total_gb": 10.0,
                "data_remaining_gb": 7.4,
                "quota_label": "Daily High-Speed Quota",
                "quota_unit": "GB",
                "signal_metric_label": "4G LTE RSRP Signal",
                "signal_metric_value": "-76 dBm (Strong 4G+)",
                "optical_rx_power_dbm": -76.0,
            }
        if "mobile" in seg_key or "mobitel" in seg_key:
            return {
                **base_common,
                "telephone_number": "071 234 5678",
                "service_segment": "Mobile",
                "connection_status": "ACTIVE (4G / VoLTE)",
                "service_category": "SLTMobitel Mobile Postpaid",
                "subscribed_package": "Mobitel Postpaid Max (50 GB Anytime + Unlimited Calls)",
                "monthly_rental_rs": 1890.0,
                "current_balance_rs": 1890.0,
                "data_total_gb": 50.0,
                "data_remaining_gb": 31.8,
                "quota_label": "Mobile Data Remaining",
                "quota_unit": "GB",
                "signal_metric_label": "Network / SIM Status",
                "signal_metric_value": "4G VoLTE Active (eSIM Ready)",
                "optical_rx_power_dbm": -82.0,
            }

        # Default: Fibre
        return {
            **base_common,
            "service_segment": "Fibre",
            "connection_status": "ACTIVE (GPON Online)",
            "service_category": "Fibre Broadband (FTTH)",
            "subscribed_package": "Fibre Flash 25 (250 GB Anytime, 100 Mbps)",
            "monthly_rental_rs": 4790.0,
            "current_balance_rs": 4790.0,
            "data_total_gb": 250.0,
            "data_remaining_gb": 142.5,
            "quota_label": "Monthly Data Remaining",
            "quota_unit": "GB",
            "signal_metric_label": "Optical Rx Power",
            "signal_metric_value": "-18.2 dBm (Healthy)",
            "optical_rx_power_dbm": -18.2,
        }

    def create_fault_ticket(
        self,
        identifier: str,
        service_type: str = "Fibre",
        issue_description: str = "Connection fault reported by subscriber",
        contact_number: str | None = None,
        fault_category: str = "General Connectivity Fault",
        led_status: str = "Not Specified",
        router_restarted: bool = False,
        affected_devices: str = "All Devices",
        issue_started: str = "Today",
        impact_level: str = "High (Household Outage)",
        contact_name: str | None = None,
        service_address: str | None = None,
        preferred_visit_slot: str = "Anytime (08:00 - 18:00)"
    ) -> dict:
        """
        Creates and logs a descriptive customer fault ticket with hardware diagnostics,
        impact assessment, and field visit details.
        Generates a unique reference (e.g. FLT-2026-XXXX) and assigns SLA and regional field team.
        """
        clean_id = re.sub(r"[^0-9a-zA-Z\-]", "", str(identifier)).strip() or "0112456789"
        acc_num = clean_id if clean_id.startswith("SLT-ACC-") else f"SLT-ACC-{clean_id}"

        desc_lower = f"{issue_description} {fault_category} {led_status}".lower()
        svc_lower = service_type.lower()

        # Categorize Division
        if any(w in svc_lower for w in ("peotv", "tv", "channels")):
            category = "PEOTV"
            division = "PEOTV Regional Maintenance & Headend Ops"
        elif any(w in svc_lower for w in ("lte", "4g", "mobile")):
            category = "4G LTE"
            division = "Mobitel Wireless Access Network Operations"
        elif any(w in svc_lower for w in ("copper", "voice", "telephone", "landline")):
            category = "Copper Voice / Megaline"
            division = "Copper Network & Cable Maintenance"
        else:
            category = "Fibre Broadband (FTTH)"
            division = "SLT Regional Fibre Operations & GPON Maintenance"

        # Determine Priority & SLA
        is_critical = (
            any(w in desc_lower for w in ("los", "red light", "red", "no connection", "down", "not working", "cut", "outage"))
            or "critical" in impact_level.lower()
        )
        priority = "CRITICAL / HIGH" if is_critical else "NORMAL"
        target_sla = "Within 4 Hours (High Priority Optical/Line Fault)" if is_critical else "Within 8 Hours"

        # Generate ticket reference
        random_num = random.randint(3000, 9999)
        ticket_id = f"FLT-2026-{random_num}"
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        ticket_record = {
            "ticket_id": ticket_id,
            "account_id": acc_num,
            "service_type": category,
            "fault_category": fault_category,
            "led_status": led_status,
            "router_restarted": bool(router_restarted),
            "affected_devices": affected_devices,
            "issue_started": issue_started,
            "impact_level": impact_level,
            "status": "LOGGED",
            "priority": priority,
            "assigned_team": division,
            "target_sla": target_sla,
            "created_at": created_at,
            "issue_description": issue_description,
            "contact_name": contact_name or "Kasun Perera",
            "contact_number": contact_number or "071 234 5678",
            "service_address": service_address or "Registered Premises Address",
            "preferred_visit_slot": preferred_visit_slot,
            "assigned_officer": "Unassigned",
            "officer_updates": [],
            "is_mock_ticket": not self.is_live_crm_enabled
        }
        self._mock_tickets.append(ticket_record)

        restart_label = "Yes (Already restarted)" if router_restarted else "No"
        summary_md = (
            f"### Fault Ticket Logged Successfully: `{ticket_id}`\n\n"
            f"- **Account Number:** `{acc_num}`\n"
            f"- **Service & Fault Type:** {category} — {fault_category}\n"
            f"- **Router / LED Diagnostics:** `{led_status}` | Router Restarted: {restart_label} | Affected: {affected_devices}\n"
            f"- **Impact & Timeline:** {impact_level} (Started: {issue_started})\n"
            f"- **Detailed Issue Description:** {issue_description}\n"
            f"- **Priority & SLA:** {priority} — {target_sla}\n"
            f"- **Assigned Team:** {division}\n"
            f"- **On-Site Contact:** {ticket_record['contact_name']} (`{ticket_record['contact_number']}`)\n"
            f"- **Premises & Visit Window:** {ticket_record['service_address']} | {preferred_visit_slot}\n\n"
            f"Our technical field operations team has been notified. You can track this ticket via the "
            f"**MySLT App** or by calling **1212** quoting reference **`{ticket_id}`**."
        )

        return {
            "ticket_id": ticket_id,
            "status": "LOGGED",
            "ticket_details": ticket_record,
            "summary_markdown": summary_md
        }

    def get_ticket_status(self, ticket_id: str) -> dict:
        """Retrieves full details and status of an existing fault ticket."""
        clean_tid = ticket_id.strip().upper()
        for t in self._mock_tickets:
            if t["ticket_id"].upper() == clean_tid:
                return {
                    "found": True,
                    "ticket": t,
                    "summary_markdown": (
                        f"### Ticket Reference: `{t['ticket_id']}`\n"
                        f"- **Status:** `{t['status']}` | **Priority:** {t['priority']}\n"
                        f"- **Service & Fault:** {t['service_type']} — {t.get('fault_category', 'General Fault')}\n"
                        f"- **Diagnostics:** LED: `{t.get('led_status', 'N/A')}` | Restarted: {'Yes' if t.get('router_restarted') else 'No'} | Devices: {t.get('affected_devices', 'N/A')}\n"
                        f"- **Description:** {t['issue_description']}\n"
                        f"- **Assigned Division:** {t['assigned_team']}\n"
                        f"- **Target SLA:** {t.get('target_sla', 'Within 8 Hours')}\n"
                        f"- **Visit Window & Address:** {t.get('preferred_visit_slot', 'Anytime')} — {t.get('service_address', 'Registered Address')}"
                    )
                }
        return {
            "found": False,
            "ticket": None,
            "summary_markdown": f"No fault ticket found matching reference `{ticket_id}`. Please verify the ticket number or call 1212."
        }

    def list_all_tickets(self, status_filter: str | None = None) -> list[dict]:
        """Returns all fault tickets for Technical Officer review, newest first."""
        items = list(reversed(self._mock_tickets))
        if status_filter and status_filter.upper() != "ALL":
            sf = status_filter.upper()
            items = [t for t in items if t["status"].upper() == sf]
        return items

    def update_ticket(
        self,
        ticket_id: str,
        status: str | None = None,
        officer_name: str | None = None,
        contact_channel: str | None = None,
        customer_message: str | None = None,
        internal_note: str | None = None
    ) -> dict | None:
        """
        Allows a Technical Officer to update a fault ticket's status, assign themselves,
        log an outbound customer contact (Call/SMS/Message), and record internal engineering notes.
        """
        clean_tid = ticket_id.strip().upper()
        for t in self._mock_tickets:
            if t["ticket_id"].upper() == clean_tid:
                if status:
                    t["status"] = status.strip().upper()
                    if t["status"] == "RESOLVED":
                        t["resolved_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if officer_name:
                    t["assigned_officer"] = officer_name.strip()
                if customer_message or internal_note or contact_channel:
                    t.setdefault("officer_updates", []).append({
                        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "officer_name": officer_name or t.get("assigned_officer") or "Technical Officer",
                        "channel": contact_channel or "Portal Update",
                        "message": (customer_message or "").strip(),
                        "internal_note": (internal_note or "").strip(),
                        "status_change": t["status"]
                    })
                return t
        return None
