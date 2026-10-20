# SLT Network Operations Standard Operating Procedure (SOP)
**Document ID:** SLT-NET-SOP-044  
**Title:** Access Network GPON OLT PON Port Loss of Signal (PON_LOS) & Mass ONT Offline  
**Approved For:** Tier-1 / Tier-2 Access NOC Engineers  
**Classification:** Tier-1 Approved Technical Documentation

---

## Section 1: Symptom Identification
- Alarm `PON_LOS` or `LOSi` triggered on OLT GPON interface (e.g., `GPON 0/3/4`).
- 16 to 64 customer ONTs (Optical Network Terminals) on the same splitter go offline simultaneously with `DyingGasp` vs `LOS` cause.

## Section 2: Safe Diagnostic Commands (Read-Only)
**WARNING:** Do NOT reboot the OLT line card or reset PON protection groups without verifying active traffic on adjacent ports.
1. Check PON port optical status and online ONT count:
   `display port state 0/3 4`
2. Check last down cause for all ONTs on the port (distinguish power outage vs fiber cut):
   `display ont info 0 3 4 all`
3. Check OLT PON SFP module laser bias and temperature:
   `display port ddm-info 0/3 4`

## Section 3: Root Cause Evaluation Thresholds
- **Mass DyingGasp (>80% ONTs report DyingGasp):** Commercial power outage at customer premises / street cabinet.
- **Mass PON_LOS (100% ONTs report LOS simultaneously, 0 DyingGasp):** Feeder fiber break between OLT and Primary FDB (Fiber Distribution Box) or faulty OLT SFP module.

## Section 4: Troubleshooting & Escalation Procedure
1. **If >80% of ONTs show Last Down Cause = DyingGasp:**
   - Mark ticket as **Commercial Power Outage (Non-Network Fault)** and notify Regional Customer Care. No fiber splicing dispatch required.
2. **If 100% of ONTs show LOS with 0 DyingGasp:**
   - **Immediate Escalation Required:** Escalate to **SLT Regional OPMC Outside Plant (OSP) Fiber Team** for OTDR testing on the feeder fiber cable.
