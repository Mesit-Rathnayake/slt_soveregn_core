# Risk Assessment, Governance & Implementation Roadmap
**Project:** SLTMobitel Hybrid Cloud & Sovereign AI Platform (AWS + Local Hybrid)  
**Prepared by:** Mesith Rathnayake (Intern AI Engineer, SLT Digital Labs)  

---

## 1. Risk Register & Technical Mitigation Matrix

| Risk Category | Specific Threat / Challenge | Impact | Technical Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **Sensitive Data Exposure to Cloud** | Incident tickets or user queries sent to AWS API Gateway or Bedrock may contain customer PII, SL phone numbers, or internal IPs. | High | Run mandatory **Pre-Flight Sanitization (`sanitizer.py`)** locally before any external HTTP call to `/prod/retrieve` or AWS Bedrock. |
| **High Licensing Cost (IBM Sovereign Core)** | Acquiring dedicated IBM Sovereign Core & bare-metal OpenShift entitlements is cost-prohibitive for PoC/MVP deployment. | High | **Resolved via AWS Hybrid Pivot:** Replaced IBM Sovereign Core with serverless **AWS CloudFormation, CloudFront, API Gateway (`/prod/retrieve`), and Amazon Bedrock**, paired with free local **Ollama** models. |
| **Incorrect AI Responses (Hallucinations)** | AI suggests an invalid CLI command, wrong USSD code, or unverified package detail. | High | Enforce **Strict Grounded RAG**: prompts require exact citations (`[Citation: SLT-AWS-KB-01]` or `[Citation: SLT-NET-SOP-042]`) with temperature `0.1`. |
| **Unauthorized Autonomous Action** | The assistant could modify live production network configurations. | Critical | **Read-only advisory boundary**: provide no network-device credentials or write-capable integrations. All actions require human engineer review. |
| **Cloud / Network Latency or Outage** | AWS API Gateway (`~1–5s` response time) or external LLM credentials may be temporarily unreachable. | Medium | Automatic graceful fallback to **AWS KB Direct Chunk Synthesis** and **Local Deterministic Rule / Ollama Engine** so operations never halt. |

---

## 2. Data Classification & Governance Policy

1. **Tier 1 — Approved for Cloud KB & PoC Ingestion (Green):**
   * SLTMobitel product, billing, Fibre/4G support documentation hosted on the AWS KnowledgeBase API (`/prod/retrieve`).
   * Approved SLT Network Standard Operating Procedures (SOPs) and escalation matrices.
   * **Sanitized** incident tickets and queries with PII, IPs, and credentials masked.
2. **Tier 2 — Restricted / Requires Local Pre-Masking (Amber):**
   * Raw NOC trouble tickets containing internal IPv4 addresses or technician contact details — must pass through `SovereignDataSanitizer` prior to analysis.
3. **Tier 3 — Strictly Prohibited (Red):**
   * Unredacted customer CDR records, plaintext router passwords, and cryptographic private keys.

---

## 3. Phased Implementation Roadmap & Status Tracker

- [x] **Phase 1 — Research & Strategic Cost Pivot (Complete)**
  - [x] Evaluate IBM Sovereign Core v1.1.0 vs. AWS Serverless & Hybrid Cloud TCO.
  - [x] Transition infrastructure blueprint to **AWS CloudFormation + CloudFront + API Gateway + Bedrock** (`01-feasibility-and-prerequisites.md`).
- [x] **Phase 2 — Hybrid Architecture & IaC Templates (Complete)**
  - [x] Author declarative AWS CloudFormation template (`infra-config-templates/aws-cloudformation-stack.yaml.example`).
  - [x] Define 6-layer hybrid cloud architecture (`02-architecture-design.md`).
- [x] **Phase 3 — SLTMobitel AWS KnowledgeBase API Integration (Complete)**
  - [x] Integrate live HTTP API endpoint (`POST https://ww5659pvgk.execute-api.us-east-1.amazonaws.com/prod/retrieve`) with `x-auth-secret` authentication (`aws_kb_client.py`).
  - [x] Add multi-provider LLM synthesis supporting **AWS Bedrock (`boto3`)**, **Local Ollama**, **Google Gemini**, and **Direct Grounded Synthesis**.
- [x] **Phase 4 — Unified 4-Tab Streamlit Workbench & Automated Testing (Complete)**
  - [x] Build interactive SLTMobitel KnowledgeBase Q&A tab alongside NetOps Incident Triage, Local SOP Search, and RBAC Audit Trail (`app.py`).
  - [x] Validate sanitization, AWS KB client normalization, and RAG diagnostics via `pytest` (`test_mvp.py`).
