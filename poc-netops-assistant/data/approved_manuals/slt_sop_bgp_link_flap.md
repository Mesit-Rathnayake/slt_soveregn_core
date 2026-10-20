# SLT Network Operations Standard Operating Procedure (SOP)
**Document ID:** SLT-NET-SOP-042  
**Title:** Core & Aggregation Router BGP Peer Flapping and Optical Link Degradation  
**Approved For:** Tier-1 / Tier-2 Network Operations Center (NOC) Engineers  
**Classification:** Tier-1 Approved Technical Documentation

---

## Section 1: Symptom Identification
Engineers may observe one or more of the following alarms in the NMS (Network Management System):
- `BGP-5-ADJCHANGE: neighbor Down (Hold Timer Expired)`
- `LINK-3-UPDOWN: Interface TenGigE0/1/0, changed state to down`
- High CRC error rates or input packet drops on core fiber trunks.

## Section 2: Safe Diagnostic Commands (Read-Only)
**WARNING:** Do NOT reset interfaces or clear BGP sessions on core links without Tier-3 approval. Run only the following read-only diagnostic commands:
1. Verify BGP neighbor state and uptime:
   `show bgp ipv4 unicast summary`
2. Check interface optical transceiver power levels (Rx/Tx dBm):
   `show interfaces TenGigE0/1/0 transceiver detail`
3. Inspect physical layer CRC and framing errors:
   `show interfaces TenGigE0/1/0 | include CRC|drops`

## Section 3: Root Cause Evaluation Thresholds
- **Normal Optical Rx Power:** `-1.0 dBm` to `-14.0 dBm`.
- **Degraded Optical Warning:** `-14.1 dBm` to `-18.0 dBm` (Suspect dirty fiber patch cord or bending loss).
- **Critical Optical Loss (LOS):** Below `-18.1 dBm` (Suspect external fiber cut or faulty SFP+ module).

## Section 4: Troubleshooting & Escalation Procedure
1. **If Optical Rx Power is between -14.1 dBm and -18.0 dBm:**
   - Schedule maintenance window to inspect and clean LC/UPC fiber connectors at the ODF (Optical Distribution Frame).
2. **If Optical Rx Power is below -18.1 dBm OR link flaps > 5 times in 15 minutes:**
   - **Immediate Escalation Required:** Escalate ticket to **SLT Tier-3 Core Transport Team** and dispatch the **Regional Fiber Maintenance Unit**.
   - Do NOT attempt autonomous BGP routing policy modifications.
