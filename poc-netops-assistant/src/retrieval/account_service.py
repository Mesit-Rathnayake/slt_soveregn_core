import os
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path


class SLTCustomerAccountGateway:
    """
    SLTMobitel Customer Account, OTP Authentication & Fault Ticketing Gateway:
    - Connection-number + OTP (SMS/Email) authentication with automatic service-type detection.
    - Account overview including credit limit, current bill, data quota, current & previous tickets.
    - Least-loaded Round-Robin Technical Officer assignment with a configurable max In-Progress cap.
    - Plug-and-play ready for supervisor's upcoming live CRM / OTP API or MCP server.
    """

    MAX_IN_PROGRESS_PER_OFFICER = 2
    ACTIVE_WORKLOAD_STATUSES = {"IN_PROGRESS", "CONTACTED_CUSTOMER"}

    TECHNICAL_OFFICERS = [
        {"officer_id": "TO-101", "name": "Eng. Nimal Silva", "division": "Fibre & GPON Operations"},
        {"officer_id": "TO-102", "name": "Tech. Chamara Jayasinghe", "division": "PEOTV & Broadband Ops"},
        {"officer_id": "TO-103", "name": "Eng. Kavindu Perera", "division": "Metro Access Maintenance"},
        {"officer_id": "TO-104", "name": "Tech. Sashini Wickramasinghe", "division": "Customer Field Operations"},
    ]

    # Sample subscriber directory for stub mode (automatically maps connection number -> service type)
    SUBSCRIBER_DIRECTORY = {
        "0112456789": {
            "customer_name": "Kasun Perera",
            "mobile": "071 234 5678",
            "email": "kasun.perera@sltnet.lk",
            "service_segment": "Fibre",
            "service_category": "Fibre Broadband (FTTH)",
            "connection_status": "ACTIVE (GPON Online)",
            "subscribed_package": "Fibre Flash 25 (250 GB Anytime, 100 Mbps)",
            "monthly_rental_rs": 4790.0,
            "current_balance_rs": 4790.0,
            "credit_limit_rs": 15000.0,
            "data_total_gb": 250.0,
            "data_remaining_gb": 142.5,
            "quota_label": "Monthly Data Remaining",
            "quota_unit": "GB",
            "signal_metric_label": "Optical Rx Power",
            "signal_metric_value": "-18.2 dBm (Healthy)",
            "optical_rx_power_dbm": -18.2,
            "service_address": "No. 42, Galle Road, Colombo 03",
        },
        "0112889941": {
            "customer_name": "Dilani Fernando",
            "mobile": "077 891 2345",
            "email": "dilani.f@gmail.com",
            "service_segment": "Broadband",
            "service_category": "Home Broadband (4G LTE)",
            "connection_status": "ACTIVE (4G LTE Connected)",
            "subscribed_package": "Unlimited LTE Flash 10 (10 GB/day, 4G LTE)",
            "monthly_rental_rs": 4090.0,
            "current_balance_rs": 4090.0,
            "credit_limit_rs": 12000.0,
            "data_total_gb": 10.0,
            "data_remaining_gb": 7.4,
            "quota_label": "Daily High-Speed Quota",
            "quota_unit": "GB",
            "signal_metric_label": "4G LTE RSRP Signal",
            "signal_metric_value": "-76 dBm (Strong 4G+)",
            "optical_rx_power_dbm": -76.0,
            "service_address": "No. 18, Havelock Road, Colombo 05",
        },
        "0812233445": {
            "customer_name": "Ruwan Bandara",
            "mobile": "071 554 9087",
            "email": "ruwan.bandara@yahoo.com",
            "service_segment": "PEOTV",
            "service_category": "PEOTV Digital TV",
            "connection_status": "ACTIVE (STB Online)",
            "subscribed_package": "PEOTV Titanium (120+ Channels, HD Enabled)",
            "monthly_rental_rs": 2940.0,
            "current_balance_rs": 2940.0,
            "credit_limit_rs": 10000.0,
            "data_total_gb": 120.0,
            "data_remaining_gb": 120.0,
            "quota_label": "Active Channels",
            "quota_unit": "Channels",
            "signal_metric_label": "STB Signal / VLAN",
            "signal_metric_value": "HD Multicast OK (VLAN 40)",
            "optical_rx_power_dbm": -18.2,
            "service_address": "No. 74, Peradeniya Road, Kandy",
        },
        "0712345678": {
            "customer_name": "Nadeesha Silva",
            "mobile": "071 234 5678",
            "email": "nadeesha.s@mobitel.lk",
            "service_segment": "SLT Mobitel",
            "service_category": "SLT Mobitel Postpaid",
            "connection_status": "ACTIVE (4G / VoLTE)",
            "subscribed_package": "SLT Mobitel Postpaid Max (50 GB Anytime + Unlimited Calls)",
            "monthly_rental_rs": 1890.0,
            "current_balance_rs": 1890.0,
            "credit_limit_rs": 8000.0,
            "data_total_gb": 50.0,
            "data_remaining_gb": 31.8,
            "quota_label": "Mobile Data Remaining",
            "quota_unit": "GB",
            "signal_metric_label": "Network / SIM Status",
            "signal_metric_value": "4G VoLTE Active (eSIM Ready)",
            "optical_rx_power_dbm": -82.0,
            "service_address": "No. 15, Nawala Road, Nugegoda",
        },
    }

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
        self._otp_store: dict[str, dict] = {}
        self._rr_pointer: int = 0
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
                "service_type": "Home Broadband (4G LTE)",
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
                "status": "IN_PROGRESS",
                "priority": "CRITICAL / HIGH",
                "target_sla": "Within 4 Hours (High Priority Optical/Line Fault)",
                "created_at": "2026-11-20T06:15:00Z",
                "issue_description": "Signal dropped after heavy rain this morning. Restarted router twice.",
                "assigned_team": "SLT Regional Fibre Operations & GPON Maintenance",
                "assigned_officer": "Eng. Nimal Silva",
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

    @staticmethod
    def _normalize_connection_number(raw: str) -> str:
        digits = re.sub(r"\D", "", str(raw or ""))
        if digits.startswith("94") and len(digits) == 11:
            digits = "0" + digits[2:]
        return digits or "0112456789"

    @staticmethod
    def _mask_contact(value: str, channel: str) -> str:
        if channel.upper() == "EMAIL" and "@" in value:
            local, domain = value.split("@", 1)
            return f"{local[:2]}***@{domain}"
        digits = re.sub(r"\D", "", value)
        if len(digits) >= 7:
            return f"{digits[:3]} *** {digits[-4:]}"
        return "***"

    def _lookup_subscriber_record(self, connection_number: str) -> dict:
        digits = self._normalize_connection_number(connection_number)
        if digits in self.SUBSCRIBER_DIRECTORY:
            return dict(self.SUBSCRIBER_DIRECTORY[digits])

        # Infer connection type automatically from Sri Lankan numbering prefixes
        if digits.startswith(("070", "071")):
            template = dict(self.SUBSCRIBER_DIRECTORY["0712345678"])
            template["mobile"] = f"{digits[:3]} {digits[3:6]} {digits[6:]}"
            return template
        if digits.startswith("081"):
            return dict(self.SUBSCRIBER_DIRECTORY["0812233445"])
        if digits.startswith(("011", "038", "031")):
            return dict(self.SUBSCRIBER_DIRECTORY["0112456789"])
        return dict(self.SUBSCRIBER_DIRECTORY["0112889941"])

    def request_otp(self, connection_number: str, channel: str = "SMS") -> dict:
        """
        Initiates OTP authentication for a subscriber connection number.
        Automatically resolves the subscriber's connection type & masked delivery target.
        """
        digits = self._normalize_connection_number(connection_number)
        if len(digits) < 9 or len(digits) > 10:
            raise ValueError("Please enter a valid 9 or 10 digit SLTMobitel connection number (e.g. 0112456789 or 0712345678).")

        ch = "EMAIL" if str(channel).strip().upper() == "EMAIL" else "SMS"
        sub = self._lookup_subscriber_record(digits)
        otp_code = f"{random.randint(100000, 999999)}"
        expires_at = time.time() + 300  # 5 minutes

        self._otp_store[digits] = {
            "otp": otp_code,
            "channel": ch,
            "expires_at": expires_at,
            "attempts": 0,
            "service_segment": sub["service_segment"],
        }

        target_raw = sub["email"] if ch == "EMAIL" else sub["mobile"]
        masked_target = self._mask_contact(target_raw, ch)

        return {
            "sent": True,
            "connection_number": digits,
            "channel": ch,
            "masked_destination": masked_target,
            "expires_in_seconds": 300,
            "detected_service_segment": sub["service_segment"],
            # Exposed only while in stub mode so the supervisor/user can verify without live SMS/Email gateway
            "demo_otp_code": None if self.is_live_crm_enabled else otp_code,
            "message": f"A 6-digit OTP has been sent via {ch} to {masked_target}."
        }

    def verify_otp(self, connection_number: str, otp_code: str) -> dict:
        """Verifies the 6-digit OTP and returns the subscriber's full profile with auto-detected service type."""
        digits = self._normalize_connection_number(connection_number)
        entry = self._otp_store.get(digits)
        if not entry:
            return {"verified": False, "error": "No active OTP found for this connection number. Please request a new OTP."}
        if time.time() > entry["expires_at"]:
            self._otp_store.pop(digits, None)
            return {"verified": False, "error": "OTP has expired. Please request a new OTP."}

        entry["attempts"] += 1
        if entry["attempts"] > 5:
            self._otp_store.pop(digits, None)
            return {"verified": False, "error": "Too many failed OTP attempts. Please request a new OTP."}

        if str(otp_code).strip() != entry["otp"]:
            return {"verified": False, "error": "Invalid OTP code. Please check and try again."}

        self._otp_store.pop(digits, None)
        profile = self.get_account_profile(digits, service_segment=entry["service_segment"])
        return {
            "verified": True,
            "connection_number": digits,
            "account_id": profile["account_id"],
            "service_segment": profile["service_segment"],
            "profile": profile,
        }

    def get_account_profile(self, identifier: str = "0112456789", service_segment: str | None = None) -> dict:
        """
        Fetches customer account overview, credit limit, subscribed package, data balance,
        current (active) tickets, and previous (resolved) tickets.
        Auto-detects service segment from connection number if service_segment is not specified.
        """
        clean_id = re.sub(r"[^0-9a-zA-Z\-]", "", str(identifier)).strip() or "0112456789"
        digits = self._normalize_connection_number(clean_id)
        acc_num = clean_id if clean_id.startswith("SLT-ACC-") else f"SLT-ACC-{digits}"

        if self.is_live_crm_enabled:
            try:
                import urllib.request
                import json
                req = urllib.request.Request(
                    f"{self.api_endpoint}/profile?account_id={acc_num}",
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
                pass

        # Resolve profile by connection number first; override template only if caller explicitly specifies a different segment
        sub = self._lookup_subscriber_record(digits)
        if service_segment:
            seg_l = service_segment.strip().lower()
            if ("peo" in seg_l or "tv" in seg_l) and sub["service_segment"] != "PEOTV":
                sub = dict(self.SUBSCRIBER_DIRECTORY["0812233445"])
            elif ("broadband" in seg_l or "lte" in seg_l or "4g" in seg_l) and sub["service_segment"] != "Broadband":
                sub = dict(self.SUBSCRIBER_DIRECTORY["0112889941"])
            elif ("mobile" in seg_l or "mobitel" in seg_l) and sub["service_segment"] != "SLT Mobitel":
                sub = dict(self.SUBSCRIBER_DIRECTORY["0712345678"])

        # Separate current (active) tickets vs previous (resolved) tickets for this subscriber
        acc_tickets = [t for t in reversed(self._mock_tickets) if t["account_id"] == acc_num]
        # If no tickets directly match a custom entered number, show empty lists cleanly
        current_tickets = [t for t in acc_tickets if t["status"] != "RESOLVED"]
        previous_tickets = [t for t in acc_tickets if t["status"] == "RESOLVED"]

        credit_limit = float(sub.get("credit_limit_rs", 15000.0))
        current_balance = float(sub.get("current_balance_rs", 4790.0))
        available_credit = max(0.0, credit_limit - current_balance)

        return {
            "account_id": acc_num,
            "connection_number": digits,
            "telephone_number": sub["mobile"],
            "email": sub["email"],
            "customer_name": sub["customer_name"],
            "service_address": sub["service_address"],
            "service_segment": sub["service_segment"],
            "service_category": sub["service_category"],
            "connection_status": sub["connection_status"],
            "subscribed_package": sub["subscribed_package"],
            "monthly_rental_rs": sub["monthly_rental_rs"],
            "current_balance_rs": current_balance,
            "credit_limit_rs": credit_limit,
            "available_credit_rs": available_credit,
            "bill_due_date": "2026-11-28",
            "data_total_gb": sub["data_total_gb"],
            "data_remaining_gb": sub["data_remaining_gb"],
            "quota_label": sub["quota_label"],
            "quota_unit": sub["quota_unit"],
            "signal_metric_label": sub["signal_metric_label"],
            "signal_metric_value": sub["signal_metric_value"],
            "optical_rx_power_dbm": sub["optical_rx_power_dbm"],
            "open_tickets_count": len(current_tickets),
            "current_tickets": current_tickets,
            "previous_tickets": previous_tickets,
            "recent_tickets": acc_tickets[:6],
            "is_mock_data": True,
            "gateway_status": "CONNECTED_STUB_MODE (Awaiting Live CRM Key)"
        }

    def get_officer_workloads(self) -> dict:
        """Returns each Technical Officer's live In-Progress count, max cap, and queued ticket count."""
        counts = {o["name"]: 0 for o in self.TECHNICAL_OFFICERS}
        resolved_counts = {o["name"]: 0 for o in self.TECHNICAL_OFFICERS}
        for t in self._mock_tickets:
            off = t.get("assigned_officer", "")
            if off in counts:
                if t["status"] in self.ACTIVE_WORKLOAD_STATUSES:
                    counts[off] += 1
                elif t["status"] == "RESOLVED":
                    resolved_counts[off] += 1

        officers_summary = []
        for o in self.TECHNICAL_OFFICERS:
            active_c = counts[o["name"]]
            officers_summary.append({
                **o,
                "in_progress_count": active_c,
                "resolved_count": resolved_counts[o["name"]],
                "max_in_progress": self.MAX_IN_PROGRESS_PER_OFFICER,
                "at_capacity": active_c >= self.MAX_IN_PROGRESS_PER_OFFICER,
            })

        queued_count = sum(1 for t in self._mock_tickets if t["status"] == "QUEUED")
        return {
            "max_in_progress_per_officer": self.MAX_IN_PROGRESS_PER_OFFICER,
            "queued_tickets_count": queued_count,
            "officers": officers_summary,
        }

    def _assign_least_loaded_officer(self) -> tuple[str, str]:
        """
        Least-Loaded Round-Robin assignment with Maximum In-Progress Cap:
        - Picks the officer with the fewest active In-Progress tickets below MAX_IN_PROGRESS_PER_OFFICER.
        - Breaks ties using round-robin pointer rotation so tasks distribute evenly.
        - If all officers are at maximum capacity, queues the ticket (`QUEUED`).
        """
        workloads = self.get_officer_workloads()["officers"]
        eligible = [
            (idx, o) for idx, o in enumerate(workloads)
            if o["in_progress_count"] < self.MAX_IN_PROGRESS_PER_OFFICER
        ]
        if not eligible:
            return "Queued (All Officers at Max Capacity)", "QUEUED"

        min_load = min(o["in_progress_count"] for _, o in eligible)
        min_candidates = [(idx, o) for idx, o in eligible if o["in_progress_count"] == min_load]

        # Round-robin tie-breaker starting from _rr_pointer
        n = len(workloads)
        min_candidates.sort(key=lambda pair: (pair[0] - self._rr_pointer) % n)
        chosen_idx, chosen_officer = min_candidates[0]
        self._rr_pointer = (chosen_idx + 1) % n
        return chosen_officer["name"], "IN_PROGRESS"

    def _promote_queued_tickets(self):
        """Auto-assigns oldest QUEUED tickets whenever a Technical Officer frees up capacity."""
        for t in self._mock_tickets:
            if t["status"] == "QUEUED":
                officer_name, new_status = self._assign_least_loaded_officer()
                if new_status == "IN_PROGRESS":
                    t["assigned_officer"] = officer_name
                    t["status"] = "IN_PROGRESS"
                    t.setdefault("officer_updates", []).append({
                        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "officer_name": officer_name,
                        "channel": "Auto-Dispatch",
                        "message": f"Ticket automatically assigned to {officer_name} from the priority queue.",
                        "internal_note": "Promoted from QUEUED via least-loaded round-robin.",
                        "status_change": "IN_PROGRESS"
                    })
                else:
                    break

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
        Creates and logs a descriptive customer fault ticket and assigns it to the
        least-loaded Technical Officer via Round-Robin (respecting max In-Progress limit).
        """
        clean_id = re.sub(r"[^0-9a-zA-Z\-]", "", str(identifier)).strip() or "0112456789"
        digits = self._normalize_connection_number(clean_id)
        acc_num = clean_id if clean_id.startswith("SLT-ACC-") else f"SLT-ACC-{digits}"

        desc_lower = f"{issue_description} {fault_category} {led_status}".lower()
        svc_lower = service_type.lower()

        if any(w in svc_lower for w in ("peotv", "tv", "channels")):
            category = "PEOTV"
            division = "PEOTV Regional Maintenance & Headend Ops"
        elif any(w in svc_lower for w in ("lte", "4g", "broadband")):
            category = "Home Broadband (4G LTE)"
            division = "Wireless Broadband Operations"
        elif any(w in svc_lower for w in ("mobile", "mobitel")):
            category = "SLT Mobitel"
            division = "SLT Mobitel RAN & Mobile Operations"
        elif any(w in svc_lower for w in ("copper", "voice", "telephone", "landline")):
            category = "Copper Voice / Megaline"
            division = "Copper Network & Cable Maintenance"
        else:
            category = "Fibre Broadband (FTTH)"
            division = "SLT Regional Fibre Operations & GPON Maintenance"

        is_critical = (
            any(w in desc_lower for w in ("los", "red light", "red", "no connection", "down", "not working", "cut", "outage"))
            or "critical" in impact_level.lower()
        )
        priority = "CRITICAL / HIGH" if is_critical else "NORMAL"
        target_sla = "Within 4 Hours (High Priority Optical/Line Fault)" if is_critical else "Within 8 Hours"

        assigned_officer, initial_status = self._assign_least_loaded_officer()

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
            "status": initial_status,
            "priority": priority,
            "assigned_team": division,
            "assigned_officer": assigned_officer,
            "target_sla": target_sla,
            "created_at": created_at,
            "issue_description": issue_description,
            "contact_name": contact_name or "Kasun Perera",
            "contact_number": contact_number or "071 234 5678",
            "service_address": service_address or "Registered Premises Address",
            "preferred_visit_slot": preferred_visit_slot,
            "officer_updates": [],
            "is_mock_ticket": not self.is_live_crm_enabled
        }
        self._mock_tickets.append(ticket_record)

        restart_label = "Yes (Already restarted)" if router_restarted else "No"
        assignment_line = (
            f"- **Assigned Technical Officer:** {assigned_officer} (Status: `{initial_status}`)\n"
            if initial_status != "QUEUED"
            else f"- **Assignment Status:** `QUEUED` — All Technical Officers are currently at maximum capacity ({self.MAX_IN_PROGRESS_PER_OFFICER} active tasks). Your ticket will be auto-assigned as soon as an officer becomes free.\n"
        )
        summary_md = (
            f"### Fault Ticket Logged Successfully: `{ticket_id}`\n\n"
            f"- **Account Number:** `{acc_num}`\n"
            f"- **Service & Fault Type:** {category} — {fault_category}\n"
            f"- **Router / LED Diagnostics:** `{led_status}` | Router Restarted: {restart_label} | Affected: {affected_devices}\n"
            f"- **Impact & Timeline:** {impact_level} (Started: {issue_started})\n"
            f"- **Detailed Issue Description:** {issue_description}\n"
            f"- **Priority & SLA:** {priority} — {target_sla}\n"
            f"{assignment_line}"
            f"- **Assigned Division:** {division}\n"
            f"- **On-Site Contact:** {ticket_record['contact_name']} (`{ticket_record['contact_number']}`)\n"
            f"- **Premises & Visit Window:** {ticket_record['service_address']} | {preferred_visit_slot}\n\n"
            f"You can track this ticket anytime in **My Account & Fault Tickets** or by calling **1212** quoting **`{ticket_id}`**."
        )

        return {
            "ticket_id": ticket_id,
            "status": initial_status,
            "assigned_officer": assigned_officer,
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
                        f"- **Assigned Technical Officer:** {t.get('assigned_officer', 'Unassigned')}\n"
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

    def list_all_tickets(self, status_filter: str | None = None, officer_filter: str | None = None) -> list[dict]:
        """Returns all fault tickets for Technical Officer review, newest first."""
        items = list(reversed(self._mock_tickets))
        if status_filter and status_filter.upper() != "ALL":
            sf = status_filter.upper()
            items = [t for t in items if t["status"].upper() == sf]
        if officer_filter and officer_filter.strip() and officer_filter.upper() != "ALL":
            of = officer_filter.strip().lower()
            items = [t for t in items if of in (t.get("assigned_officer") or "").lower()]
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
        Enforces MAX_IN_PROGRESS_PER_OFFICER and auto-promotes QUEUED tickets on resolution.
        """
        clean_tid = ticket_id.strip().upper()
        for t in self._mock_tickets:
            if t["ticket_id"].upper() == clean_tid:
                target_status = status.strip().upper() if status else t["status"]
                target_officer = officer_name.strip() if officer_name else t.get("assigned_officer", "")

                # Enforce max In-Progress cap if moving a ticket into active state for an officer
                if target_status in self.ACTIVE_WORKLOAD_STATUSES and target_officer:
                    active_for_officer = sum(
                        1 for other in self._mock_tickets
                        if other["ticket_id"] != t["ticket_id"]
                        and other.get("assigned_officer") == target_officer
                        and other["status"] in self.ACTIVE_WORKLOAD_STATUSES
                    )
                    if active_for_officer >= self.MAX_IN_PROGRESS_PER_OFFICER:
                        raise ValueError(
                            f"{target_officer} already has {active_for_officer}/{self.MAX_IN_PROGRESS_PER_OFFICER} "
                            f"active In-Progress tasks (maximum capacity reached). Resolve an existing ticket first."
                        )

                if status:
                    t["status"] = target_status
                    if t["status"] == "RESOLVED":
                        t["resolved_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if officer_name:
                    t["assigned_officer"] = target_officer
                if customer_message or internal_note or contact_channel:
                    t.setdefault("officer_updates", []).append({
                        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "officer_name": target_officer or "Technical Officer",
                        "channel": contact_channel or "Portal Update",
                        "message": (customer_message or "").strip(),
                        "internal_note": (internal_note or "").strip(),
                        "status_change": t["status"]
                    })

                # Auto-promote any QUEUED tickets if an officer just freed up a slot
                if t["status"] == "RESOLVED":
                    self._promote_queued_tickets()
                return t
        return None
