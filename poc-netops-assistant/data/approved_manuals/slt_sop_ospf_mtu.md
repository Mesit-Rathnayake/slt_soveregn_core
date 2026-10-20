# SLT Network Operations Standard Operating Procedure (SOP)
**Document ID:** SLT-NET-SOP-043  
**Title:** Core & Metro Router OSPF Neighbor Stuck in EXSTART/EXCHANGE  
**Approved For:** Tier-1 / Tier-2 Network Operations Center (NOC) Engineers  
**Classification:** Tier-1 Approved Technical Documentation

---

## Section 1: Symptom Identification
Engineers may observe the following alarms in the NMS or router syslog:
- `OSPF-5-ADJCHG: Process 1, Nbr on TenGigE0/2/0 from EXSTART to DOWN`
- OSPF neighbor state remains stuck in `EXSTART` or `EXCHANGE` after a maintenance window or link cutover.

## Section 2: Safe Diagnostic Commands (Read-Only)
**WARNING:** Do NOT clear the entire OSPF process (`clear ip ospf process`) on production core routers without Tier-3 approval. Run only these read-only commands:
1. Check current OSPF neighbor states:
   `show ip ospf neighbor`
2. Verify interface IP MTU settings on both ends:
   `show ip ospf interface TenGigE0/2/0 | include MTU|State`
3. Test jumbo frame path MTU without fragmentation:
   `ping <peer-ip> size 9000 df-bit`

## Section 3: Root Cause Evaluation Thresholds
- **Standard SLT Core MPLS Backhaul MTU:** `9198 bytes` (or matching `1500 bytes` on legacy metro links).
- **MTU Mismatch Condition:** Local interface MTU != Remote interface MTU causes DBD (Database Description) packet rejection during `EXSTART`.

## Section 4: Troubleshooting & Escalation Procedure
1. **If OSPF state is EXSTART/EXCHANGE and MTU mismatch is confirmed:**
   - Document local vs. remote MTU values and escalate to **SLT Tier-2 Metro/Core Configuration Team** to align interface MTU during an authorized change window.
2. **If MTU matches on both ends but OSPF remains stuck > 15 minutes:**
   - **Immediate Escalation Required:** Escalate to **SLT Tier-3 IP Core Engineering** to investigate control-plane CoPP (Control Plane Policing) drops or hardware forwarding faults.
