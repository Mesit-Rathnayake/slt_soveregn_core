# Risk Assessment, Governance & Implementation Roadmap
**Project:** SLTMobitel Cloud & Sovereign AI Platform (AWS CloudFront + KnowledgeBase API + Bedrock)  
**Prepared by:** Mesith Rathnayake (Intern AI Engineer, SLT Digital Labs)  

---

## 1. Risk Register & Technical Mitigation Matrix

| Risk Category | Specific Threat / Challenge | Impact | Technical Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **Sensitive Data Exposure to Cloud** | Incident tickets or user queries sent to AWS API Gateway or Bedrock may contain customer PII, SL phone numbers, or internal IPs. | High | Run mandatory **Pre-Flight Sanitization (`sanitizer.py`)** locally before any external HTTP call to `/prod/retrieve` or AWS Bedrock. |
| **High Licensing Cost (IBM Sovereign Core)** | Acquiring dedicated IBM Sovereign Core & bare-metal OpenShift entitlements is cost-prohibitive for PoC/MVP deployment. | High | **Resolved via AWS Pivot:** Replaced IBM Sovereign Core with serverless **AWS CloudFormation, Amazon CloudFront, API Gateway (`/prod/retrieve`), and Amazon Bedrock**. |
| **Out-of-Scope Hallucinations & Noisy Scrapes** | Vector DB returns low-score or multilingual CSV/JSON chunks when asked an unknown question. | High | Enforce **Relevance Thresholding & Honest Abstention** (`"I don't have enough knowledge..."`), automatic CSV/JSON chunk cleaning (`clean_raw_kb_text`), and language-aware reranking (`_rerank_chunk_score`). |
| **Unauthorized Autonomous Action** | The assistant could modify live production network configurations. | Critical | **Read-only advisory boundary**: provide no network-device credentials or write-capable integrations. All actions require human engineer review. |
| **Origin Latency (`us-east-1`)** | Cross-region HTTPS calls from Sri Lanka to `us-east-1` take `~1–5s`. | Medium | **Amazon CloudFront Edge Caching (`cloudfront_gateway.py`)** caches repeat KB queries at the edge (`<5ms` cache hit) and injects `x-auth-secret` at the origin boundary. |

---

## 2. Data Classification & Governance Policy

1. **Tier 1 — Approved for Cloud KB & PoC Ingestion (Green):**
   * SLTMobitel product, billing, USSD (`#1456#`, `#888#`, `#170#`), 4G LTE / PEOTV, and support documentation hosted on the AWS KnowledgeBase API (`/prod/retrieve`).
   * Approved SLT Network Standard Operating Procedures (SOPs) and escalation matrices.
   * **Sanitized** incident tickets and queries with PII, IPs, and credentials masked.
2. **Tier 2 — Restricted / Requires Pre-Masking (Amber):**
   * Raw NOC trouble tickets containing internal IPv4 addresses or technician contact details — must pass through `SovereignDataSanitizer` prior to analysis.
3. **Tier 3 — Strictly Prohibited (Red):**
   * Unredacted customer CDR records, plaintext router passwords, and cryptographic private keys.

---

## 3. Phased Implementation Roadmap & Status Tracker

- [x] **Phase 1 — Research & Strategic Cost Pivot (Complete)**
  - [x] Evaluate IBM Sovereign Core v1.1.0 vs. AWS Serverless & Edge Cloud TCO.
  - [x] Transition infrastructure blueprint to **AWS CloudFormation + CloudFront + API Gateway + Bedrock** (`01-feasibility-and-prerequisites.md`).
- [x] **Phase 2 — CloudFront Edge & IaC Templates (Complete)**
  - [x] Author declarative AWS CloudFormation template with CloudFront Distribution & Security Headers Policy (`infra-config-templates/aws-cloudformation-stack.yaml.example`).
  - [x] Implement `SLTCloudFrontEdgeGateway` (`src/retrieval/cloudfront_gateway.py`) and 6-layer architecture (`02-architecture-design.md`).
- [x] **Phase 3 — SLTMobitel AWS KnowledgeBase API & Bedrock Integration (Complete)**
  - [x] Integrate live HTTP API endpoint (`POST https://ww5659pvgk.execute-api.us-east-1.amazonaws.com/prod/retrieve`) with `x-auth-secret` authentication, document discovery, and CSV/JSON chunk cleaning (`aws_kb_client.py`).
  - [x] Configure **AWS Bedrock (`boto3`)** gateway and remove test-only Ollama dependencies (`llm_gateway.py`).
- [x] **Phase 4 — Conversational Chat Agent, Guardrails & Automated Testing (Complete)**
  - [x] Build user-friendly **Conversational Chat Agent UI** (`app.py`) with `SLTMobitelUnifiedAgent` (`orchestrator.py`), perimeter guardrails (`guardrails_evals.py`), and honest abstention.
  - [x] Validate sanitization, CloudFront caching, AWS KB normalization, and guardrails via `pytest` (`test_mvp.py`).
