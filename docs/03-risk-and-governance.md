---

### 📄 File 2: `docs/03-risk-and-governance.md`
*(Covers Proposal Sections 6, 7, and 8: Risk Mitigation, Governance Controls, Cost Framework, and the 5-Phase Implementation Roadmap).*

```markdown
# Phase 1 & 2: Risk Assessment, Governance & Implementation Roadmap
**Project:** SLT Sovereign AI Platform (IBM Sovereign Core v1.1.0)  
**Prepared by:** Mesith Rathnayake (Intern AI Engineer, SLT Digital Labs)  
**Alignment:** Proposal Sections 6, 7, 8 & 9

---

## 1. Risk Register & Technical Mitigation Matrix

| Risk Category | Specific Threat / Challenge | Impact | Technical Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **Sensitive Data Exposure** | Ingestion of raw incident tickets containing customer PII, core router passwords, or internal SLT IP topologies. | High | Implement an automated **Regex + NER Sanitization Pipeline** prior to vector indexing; enforce strict RBAC per tenant workspace. |
| **Incorrect AI Responses (Hallucinations)** | AI suggests an invalid CLI command or faulty troubleshooting step to a network engineer. | High | Enforce **Strict Grounded RAG**: system prompts require exact document citations (Manual Name + Page/Section). Set temperature to `0.0–0.1` and require human-in-the-loop review. |
| **Unauthorized Autonomous Action** | AI modifies live production network configurations. | Critical | **Air-Gapped Advisory Architecture**: The PoC application has no SSH/NETCONF/SNMP write permissions to production network elements. |
| **Licensing & Entitlement Delays** | Delay in receiving IBM Sovereign Core or Red Hat OCP entitlement keys blocks project progress. | Medium | Decouple the PoC application layer using an environment-agnostic API wrapper so development and testing proceed locally until keys arrive. |
| **Insufficient Infrastructure** | High GPU/memory demand for large foundation models exceeds available lab hardware. | Medium | Utilize quantized Small Language Models (SLMs, e.g., 3B–8B parameter models) optimized for telecom RAG tasks during PoC evaluation. |
| **Operational & Cost Overhead** | Unpredictable scaling costs for storage, power, and licensing in production. | Medium | Use IBM Sovereign Core's built-in metering to benchmark compute/storage per query during Phase 4 before committing to production sizing. |

---

## 2. Data Classification & Governance Policy (PoC Scope)

To comply with **Digital and Data Sovereignty**, data entering the AI Network Operations Assistant is classified into three tiers:

1. **Tier 1 — Approved for PoC Ingestion (Green):**
   * Vendor hardware manuals (e.g., standard Huawei/Cisco/Juniper public or approved documentation).
   * General SLT Network Standard Operating Procedures (SOPs) and escalation matrices.
   * **Sanitized / Synthetic** incident tickets (all IPs masked as `10.x.x.x`, staff/customer names removed).
2. **Tier 2 — Restricted / Requires Masking (Amber):**
   * Historical trouble tickets containing real node names or internal VLAN IDs (Must pass through the automated sanitization script before use).
3. **Tier 3 — Strictly Prohibited in PoC (Red):**
   * Live customer billing/CDR records, plaintext credentials, cryptographic keys, and classified national telecom topology maps.

---

## 3. Initial Cost-Estimation Framework
Before transitioning from Phase 4 (PoC) to Production, SLT must evaluate Total Cost of Ownership (TCO) across four buckets:
* **Software Subscriptions:** IBM Sovereign Core entitlement, Red Hat OpenShift Container Platform (OCP), Red Hat Enterprise Linux (RHEL 10.1), and OpenShift Data Foundation (ODF).
* **Hardware Capital Expenditure (CapEx):** Bare-metal servers (Control + Worker nodes), enterprise NVMe/SSD drives for Ceph/ODF, 40GbE/10GbE network switches, and GPU cards (if required for concurrent inference).
* **Operational Expenditure (OpEx):** Data center power, cooling, and rack space within SLT premises.
* **Staffing & Enablement:** Training SLT Platform Administrators (OpenShift/Sovereign Core) and AI Engineers.

---

## 4. Phased Implementation Roadmap & Status Tracker

- [x] **Phase 1 — Research & Feasibility (In Progress)**
  - [x] Study IBM Sovereign Core v1.1.0 architecture & sovereign cloud pillars.
  - [x] Document hardware, RHEL 10.1 Landing Zone, and 4-network prerequisites (`01-feasibility-and-prerequisites.md`).
  - [ ] Verify physical bare-metal availability and receive IBM/Red Hat entitlement keys.
- [x] **Phase 2 — Architecture & Planning (In Progress)**
  - [x] Define 6-layer logical architecture (`02-architecture-design.md`).
  - [x] Establish risk register, governance tiers, and configuration templates (`infra-config-templates/`).
- [ ] **Phase 3 — Controlled Platform Deployment (Blocked — Awaiting Keys)**
  - [ ] Configure RHEL 10.1 Landing Zone with `podman`, `oras`, and `oc`.
  - [ ] Populate real `global.yaml`, `odf.yaml`, `certificates.yaml`, and `template.env`.
  - [ ] Execute `bootstrap.sh` (~6 hours) and validate core services.
- [ ] **Phase 4 — Proof-of-Concept Development (Starting Local Prototype Now)**
  - [ ] Create synthetic telecom manuals and sanitized incident dataset.
  - [ ] Build modular RAG ingestion, vector store, and citation-enforced AI assistant.
  - [ ] Evaluate accuracy, latency, and security guardrails.
- [ ] **Phase 5 — Evaluation & Recommendations**
  - [ ] Compile final benchmark metrics, TCO analysis, and production roadmap for SLT management.