# Risk Assessment, Governance & Implementation Roadmap
**Project:** SLT Sovereign AI Platform (IBM Sovereign Core v1.1.0)  
**Prepared by:** Mesith Rathnayake (Intern AI Engineer, SLT Digital Labs)  
**Alignment:** Proposal Sections 6–9

---

## 1. Risk Register & Technical Mitigation Matrix

| Risk Category | Specific Threat / Challenge | Impact | Technical Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **Sensitive Data Exposure** | Incident tickets may contain customer PII, credentials, or internal network details. | High | Detect and redact sensitive data before vector indexing; test sanitization against representative cases and enforce role-based access to authorized workspaces. |
| **Incorrect AI Responses (Hallucinations)** | AI suggests an invalid CLI command or faulty troubleshooting step to a network engineer. | High | Enforce **Strict Grounded RAG**: system prompts require exact document citations (Manual Name + Page/Section). Set temperature to `0.0–0.1` and require human-in-the-loop review. |
| **Unauthorized Autonomous Action** | The assistant could modify live production network configurations. | Critical | **Read-only advisory boundary**: provide no network-device credentials or write-capable integrations to the PoC. Any production change must be reviewed and applied by an authorized engineer through existing systems. |
| **Licensing & Entitlement Delays** | Delay in receiving IBM Sovereign Core or Red Hat OCP entitlement keys blocks project progress. | Medium | Decouple the PoC application layer using an environment-agnostic API wrapper so development and testing proceed locally until keys arrive. |
| **Insufficient Infrastructure** | High GPU/memory demand for large foundation models exceeds available lab hardware. | Medium | Utilize quantized Small Language Models (SLMs, e.g., 3B–8B parameter models) optimized for telecom RAG tasks during PoC evaluation. |
| **Operational & Cost Overhead** | Storage, power, staffing, and licensing costs may scale unpredictably in production. | Medium | Use available platform metering and workload benchmarks to estimate compute and storage per query during Phase 4 before production sizing. |

---

## 2. Data Classification & Governance Policy (PoC Scope)

To support **digital and data sovereignty**, data entering the AI Network Operations Assistant is classified into three tiers:

1. **Tier 1 — Approved for PoC Ingestion (Green):**
   * Vendor hardware manuals (e.g., standard Huawei/Cisco/Juniper public or approved documentation).
   * General SLT Network Standard Operating Procedures (SOPs) and escalation matrices.
   * **Sanitized or synthetic** incident tickets, with IP addresses, names, credentials, and other identifying details replaced by non-sensitive placeholders.
2. **Tier 2 — Restricted / Requires Masking (Amber):**
   * Historical trouble tickets containing real node names or internal VLAN IDs. They must be authorized for PoC use, sanitized, and reviewed before ingestion.
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

- [x] **Phase 1 — Research & Feasibility (Complete)**
  - [x] Study IBM Sovereign Core v1.1.0 architecture & sovereign cloud pillars.
  - [x] Document hardware, RHEL 10.1 Landing Zone, and 4-network prerequisites (`01-feasibility-and-prerequisites.md`).
- [x] **Phase 2 — Architecture & Planning (Complete)**
  - [x] Define 6-layer logical architecture (`02-architecture-design.md`).
  - [x] Establish risk register, governance tiers, and configuration templates (`infra-config-templates/`).
- [ ] **Phase 3 — Controlled Platform Deployment (Blocked — Awaiting Keys)**
  - [ ] Confirm physical bare-metal availability and receive IBM/Red Hat entitlement keys.
  - [ ] Configure RHEL 10.1 Landing Zone with `podman`, `oras`, and `oc`.
  - [ ] Populate real `global.yaml`, `odf.yaml`, `certificates.yaml`, and `template.env`.
  - [ ] Execute `bootstrap.sh` (~6 hours) and validate core services.
- [ ] **Phase 4 — Proof-of-Concept Development (In Progress)**
  - [ ] Create synthetic telecom manuals and sanitized incident dataset.
  - [ ] Build modular RAG ingestion, vector store, and citation-enforced AI assistant.
  - [ ] Evaluate accuracy, latency, and security guardrails.
- [ ] **Phase 5 — Evaluation & Recommendations**
  - [ ] Compile final benchmark metrics, TCO analysis, and production roadmap for SLT management.