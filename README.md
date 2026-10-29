# SLTMobitel Cloud & Sovereign AI Platform (AWS CloudFront + KnowledgeBase API + Bedrock)

**Organization:** SLT Digital Labs  
**Author:** Mesith Rathnayake (Intern AI Engineer)  
**Status:** Phase 1–4 Complete | Conversational AI Chat Agent + AWS CloudFront / API Gateway / Bedrock Operational

---

## 📌 Overview
Originally scoped around **IBM Sovereign Core v1.1.0**, this platform was strategically re-architected into a **Cost-Optimized AWS Cloud & Sovereign AI Platform** (eliminating costly IBM Sovereign Core entitlement licensing while preserving data sovereignty, pre-flight PII/IP sanitization, perimeter guardrails, RBAC, and immutable audit logging).

The platform combines **AWS CloudFormation, Amazon CloudFront, AWS API Gateway, and Amazon Bedrock** to power a unified **Conversational AI Chat Agent** covering two core SLTMobitel domains:
1. **🌐 SLTMobitel Cloud KnowledgeBase Assistant:** Queries the live SLTMobitel KnowledgeBase HTTP API (`POST https://ww5659pvgk.execute-api.us-east-1.amazonaws.com/prod/retrieve`) through **Amazon CloudFront Edge Caching & Origin Header Protection (`x-auth-secret`)**, cleans multilingual/JSON website scrapes, and synthesizes natural answers (or politely abstains when a question is outside the knowledge base).
2. **🚨 AI Network Operations (NetOps) Assistant:** Helps NOC engineers automatically mask PII/IP data from incident tickets, diagnose faults against approved technical SOP manuals (BGP, OSPF, GPON), and generate read-only troubleshooting steps.

---

## 📂 Repository Directory Structure
* `docs/` — AWS Cloud feasibility study (`01-feasibility-and-prerequisites.md`), 6-layer architecture design (`02-architecture-design.md`), and risk/governance matrix (`03-risk-and-governance.md`).
* `infra-config-templates/` — Declarative **AWS CloudFormation** stack (`aws-cloudformation-stack.yaml.example`), global platform config (`global.yaml.example`), and environment variable templates (`template.env.example`).
* `poc-netops-assistant/`
  * `data/approved_manuals/` — Ingested SLT Standard Operating Procedures (`SLT-NET-SOP-042` BGP, `SLT-NET-SOP-043` OSPF, `SLT-NET-SOP-044` GPON).
  * `data/synthetic_incidents/` — Raw and sanitized NOC incident tickets.
  * `src/ingestion/sanitizer.py` — Automated PII, Sri Lankan phone number, IPv4, and credential sanitization pipeline.
  * `src/retrieval/`
    * `cloudfront_gateway.py` — **Amazon CloudFront Edge Gateway** with TTL response caching (`Hit from cloudfront`), origin custom header injection (`x-auth-secret`), and cache invalidation (`/*`).
    * `aws_kb_client.py` — HTTP API client for the **SLTMobitel KnowledgeBase Access API** (`/prod/retrieve`) with trilingual CSV/JSON chunk cleaning, language-aware reranking, and full KB document discovery.
    * `rag_engine.py` — Dual RAG engine combining the SLTMobitel AWS KnowledgeBase API and local NetOps SOP manuals with honest out-of-scope abstention.
  * `src/agent/`
    * `orchestrator.py` — Unified Conversational Agent (`SLTMobitelUnifiedAgent`) with intent routing, conversational greeting/capability handling, follow-up failure detection, and anti-repeat guardrails.
    * `guardrails_evals.py` — Input/output perimeter guardrails (prompt injection blocking, read-only CLI safety) and 4-pillar RAG evaluation engine.
    * `llm_gateway.py` — Cloud LLM gateway supporting **AWS Bedrock (`boto3`)** (`Claude 3 Haiku / Sonnet`, `Amazon Titan`, `Meta Llama 3`) and **Google Gemini**.
    * `governance.py` — Role-Based Access Control (RBAC) and immutable JSONL audit trail (`audit_trail.jsonl`).
  * `src/api/app.py` — Clean, user-friendly Streamlit **Conversational Chat Agent UI**.
  * `tests/test_mvp.py` — Automated `pytest` test suite.

---

## 🚀 Quick-Start Guide

### 1. Install Dependencies
```bash
pip install -r poc-netops-assistant/requirements.txt
```

### 2. Configure Environment (`.env`)
`poc-netops-assistant/.env` is pre-configured with the SLTMobitel AWS KnowledgeBase API endpoint and `x-auth-secret` from `SLTMobitel KnowledgeBase Access Api.pdf`:
```env
AI_INFERENCE_MODE=AWS_BEDROCK
SLT_KB_API_URL=https://ww5659pvgk.execute-api.us-east-1.amazonaws.com/prod/retrieve
SLT_KB_AUTH_SECRET=d215af7a649fe83938414634e789b39cb3ed4ad0a1077c2d
SLT_KB_DEFAULT_TOP_K=3
AWS_REGION=us-east-1
AWS_BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
GEMINI_MODEL=gemini-2.5-flash
```

### 3. Run the Conversational Chat Agent
```bash
streamlit run poc-netops-assistant/src/api/app.py
```

### 4. Run Automated Tests
```bash
pytest poc-netops-assistant/tests/test_mvp.py -v
```
