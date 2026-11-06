# SLTMobitel Cloud & Sovereign AI Platform

**Organization:** SLT Digital Labs  
**Author:** Mesith Rathnayake (Intern AI Engineer)  
**Architecture:** AWS CloudFormation + Amazon CloudFront + AWS API Gateway + Amazon Bedrock

---

## Overview
Originally scoped around **IBM Sovereign Core v1.1.0**, this platform was transitioned to a **Cost-Optimized AWS Cloud & Sovereign AI Architecture** — eliminating costly IBM Sovereign Core licensing while preserving pre-flight PII/IP sanitization, perimeter guardrails, role-based access control (RBAC), and immutable audit logging.

The platform provides a unified **SLTMobitel Assistant** covering two core domains:
1. **SLTMobitel Cloud KnowledgeBase Assistant:** Queries the SLTMobitel KnowledgeBase HTTP API (`POST /prod/retrieve`) through **Amazon CloudFront Edge Caching & Origin Header Protection**, cleans multilingual CSV/JSON website scrapes, and answers customer and product inquiries (or abstains cleanly when a question is outside the knowledge base).
2. **Network Operations (NetOps) Incident Triage Assistant:** Automatically masks PII, Sri Lankan phone numbers, and internal IPv4 addresses from NOC incident logs, diagnoses faults against approved SLT Standard Operating Procedures (BGP, OSPF, GPON), and generates read-only verification steps.

---

## What You Can Ask the Assistant (Supported Knowledge Scope)

### 1. Customer & Product Inquiries (SLTMobitel AWS KnowledgeBase API)
The connected AWS KnowledgeBase contains verified information on the following topics:
* **Billing, Account Balance & USSD Self-Care Codes:** Checking usage and bills via `#1456#`, `1456` IVR, `#888#` Self-Care Portal, `#170#` Data Add-ons / Extra GB (including YouTube 7-Day 15 GB add-on), `#999#` Roaming, `#111#` mCash, and the **MySLT App** (`https://myslt.slt.lk/`).
* **4G LTE Home Broadband & PEOTV Packages:** Pricing and data allowances for 4G LTE packages (`20 GB`, `HBB Anytime 899`, `HBB Anytime 1899`, `Unlimited LTE Flash 5` & `Flash 10`) and PEOTV packages (`PEO HD PLUS`, `PEO TITANIUM`, `PEO PLATINUM`).
* **Mobile Data APN, SIM & Credit Limit Policies:** Handset APN configuration (`mobitel`), 3-in-1 Triple-Cut SIM details, 75% Credit Limit SMS alerts, and Value Added Services (`mTunes 777`, `e-Channelling 225`, `mTicketing 365`).
* **Home Broadband Router & Wi-Fi Troubleshooting:** Step-by-step power, cable, WLAN indicator check, and restart procedure, plus follow-up escalation steps if a router hardware button is unresponsive.
* **Customer Support & Payment Receipt Submission:** Hotlines (`1212` / `1717`), WhatsApp/Viber (`+94 71 175 5777`), email (`info@mobitel.lk`), and branch locator.
* **Business & Enterprise ICT Solutions:** SME, Wholesale, Cloud, Cyber Security, Voice & Collaboration, and Starlink offerings.

### 2. Network Operations Incident Triage (Local NetOps SOP Store)
You can paste raw NOC trouble tickets (or load sample tickets from the sidebar) for:
* **Core BGP Optical Power Loss & Link Flaps (`SLT-NET-SOP-042`):** Detects critical optical Rx power loss (`< -18.1 dBm`) and link instability (`> 5 flaps`).
* **OSPF EXSTART MTU Mismatch (`SLT-NET-SOP-043`):** Diagnoses interface MTU mismatches (`9198` bytes vs. `1500` bytes) between core and metro routers.
* **GPON OLT Feeder Fiber Cut (`SLT-NET-SOP-044`):** Identifies simultaneous PON port `LOS` drops with `0 DyingGasp` alarms.

### 3. Out-of-Scope & Security Guardrails
* **Honest Abstention:** If asked a question not covered by the KnowledgeBase or SOPs, the assistant replies: *"I don't have enough knowledge in the current SLTMobitel KnowledgeBase to answer that specific question."*
* **Secret & Credential Isolation:** API endpoints, custom authentication headers, and cloud keys are hidden from both the UI and repository, and are loaded strictly via `.env` or **Streamlit Cloud Secrets (`st.secrets`)**.

---

## Repository Directory Structure
* `docs/` — Feasibility assessment (`01-feasibility-and-prerequisites.md`), 6-layer AWS architecture design (`02-architecture-design.md`), and risk/governance matrix (`03-risk-and-governance.md`).
* `infra-config-templates/` — Declarative **AWS CloudFormation** template (`aws-cloudformation-stack.yaml.example`), global configuration (`global.yaml.example`), and environment variable template (`template.env.example`).
* `poc-netops-assistant/`
  * `data/approved_manuals/` — Approved SLT Standard Operating Procedures (`SLT-NET-SOP-042`, `SLT-NET-SOP-043`, `SLT-NET-SOP-044`).
  * `data/synthetic_incidents/` — Sample NOC incident tickets (`inc_2026_1042`, `inc_2026_1088`, `inc_2026_1105`).
  * `src/ingestion/sanitizer.py` — Automated PII, Sri Lankan phone number, IPv4, and credential masking pipeline.
  * `src/retrieval/`
    * `cloudfront_gateway.py` — **Amazon CloudFront Edge Gateway** with TTL response caching and origin custom header injection.
    * `aws_kb_client.py` — HTTP API client for the **SLTMobitel KnowledgeBase Access API** (`/prod/retrieve`) with CSV/JSON chunk cleaning and English keyword reranking.
    * `rag_engine.py` — Dual RAG engine combining the SLTMobitel AWS KnowledgeBase API and local NetOps SOP manuals.
  * `src/mcp/`
    * `slt_mcp_server.py` — **Model Context Protocol (MCP) Server (`2024-11-05` JSON-RPC 2.0)** exposing `slt_sanitize_pii`, `slt_query_cloud_kb`, `slt_diagnose_netops_incident`, and `slt_cloudfront_cache_status` as MCP tools (`tools/list`, `tools/call`) alongside SOP manual resources (`resources/list`, `resources/read`).
  * `src/agent/`
    * `orchestrator.py` — Unified Conversational Agent (`SLTMobitelUnifiedAgent`) dispatching tools via the **MCP Server** with intent routing, smalltalk handling, and follow-up context tracking.
    * `guardrails_evals.py` — Input/output perimeter guardrails (prompt injection blocking, read-only CLI safety) and 4-pillar RAG evaluation engine.
    * `llm_gateway.py` — Cloud LLM gateway supporting **AWS Bedrock (`boto3`)** and **Google Gemini**, with automatic `.env` and `st.secrets` loading.
    * `governance.py` — Role-Based Access Control (RBAC) and immutable JSONL audit trail (`audit_trail.jsonl`).
  * `src/api/`
    * `app.py` — Streamlit **Conversational Chat UI** with starter question buttons and dynamic follow-up suggestions.
    * `lambda_function.py` — **AWS Lambda Serverless Handler** (`lambda_handler`) exposing REST `/chat`, MCP JSON-RPC `/mcp`, and `/health` endpoints with CORS and function URL support.
  * `tests/`
    * `test_mvp.py` — Core RAG, CloudFront, KnowledgeBase, guardrail, and MCP protocol tests.
    * `test_lambda.py` — Serverless Lambda handler, CORS, REST payload, and error handling tests.

---

## Serverless API Endpoints (AWS Lambda / API Gateway)

When deployed via `aws-cloudformation-stack.yaml.example` or invoked directly, the Lambda function handles:

| Endpoint | Method | Purpose | Sample Request |
| :--- | :--- | :--- | :--- |
| `/chat` | `POST` | AI Assistant queries (Customer KB & NetOps SOP triage) | `{"user_input": "What are the 4G LTE packages?"}` |
| `/mcp` | `POST` | Standard Model Context Protocol (MCP) JSON-RPC 2.0 calls | `{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}` |
| `/health` | `GET` | Health check & available MCP tool diagnostics | `GET /health` |

---

## Quick-Start Guide

### 1. Install Dependencies
```bash
pip install -r poc-netops-assistant/requirements.txt
```

### 2. Configure Secrets (Local `.env` or Streamlit Cloud Secrets)
For local development, create `poc-netops-assistant/.env` from `poc-netops-assistant/.env.example`.  
For **Streamlit Community Cloud**, paste the variables into **App Settings → Secrets**:
```toml
SLT_KB_API_URL = "https://<api-id>.execute-api.us-east-1.amazonaws.com/prod/retrieve"
SLT_KB_AUTH_SECRET = "<your-kb-auth-secret>"
```

### 3. Run the Application Locally
```bash
streamlit run poc-netops-assistant/src/api/app.py
```

### 4. Run Automated Tests
```bash
pytest poc-netops-assistant/tests/test_mvp.py -v
```
