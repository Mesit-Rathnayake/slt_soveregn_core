# SLTMobitel Hybrid Cloud & Sovereign AI Platform (AWS + Ollama)

**Organization:** SLT Digital Labs  
**Author:** Mesith Rathnayake (Intern AI Engineer)  
**Status:** Phase 1–4 Complete | AWS KnowledgeBase API + AWS Bedrock / Local Ollama Hybrid MVP Operational

---

## 📌 Overview
Originally scoped around **IBM Sovereign Core v1.1.0**, this platform was strategically re-architected into a **Cost-Optimized AWS Hybrid Sovereign AI Platform** (eliminating costly IBM Sovereign Core entitlement licensing while preserving data sovereignty, pre-flight PII sanitization, RBAC, and immutable audit logging).

The platform combines **AWS CloudFormation, Amazon CloudFront, AWS API Gateway, and Amazon Bedrock** with **Local Sovereign Ollama Inference (`granite3.1-dense:2b`)** to power two core SLTMobitel capabilities in one unified workbench:
1. **🌐 SLTMobitel Cloud KnowledgeBase Assistant:** Queries the live SLTMobitel KnowledgeBase HTTP API (`POST https://ww5659pvgk.execute-api.us-east-1.amazonaws.com/prod/retrieve`) authenticated via `x-auth-secret` and synthesizes citation-backed answers using **AWS Bedrock**, **Local Ollama**, or **Direct Chunk Synthesis**.
2. **🚨 AI Network Operations (NetOps) Assistant:** Helps NOC engineers sanitize PII/IP data from incident tickets, search approved technical SOP manuals (BGP, OSPF, GPON), and generate grounded, read-only troubleshooting handovers.

---

## 📂 Repository Directory Structure
* `docs/` — AWS Hybrid Cloud feasibility study, 6-layer architecture design (CloudFront + API Gateway + Bedrock + Ollama), risk matrix, and governance policies.
* `infra-config-templates/` — Declarative **AWS CloudFormation** template (`aws-cloudformation-stack.yaml.example`), global platform config (`global.yaml.example`), and environment variable templates (`template.env.example`).
* `poc-netops-assistant/`
  * `data/approved_manuals/` — Ingested SLT Standard Operating Procedures (BGP, OSPF, GPON).
  * `data/synthetic_incidents/` — Raw and sanitized NOC incident tickets.
  * `src/ingestion/` — Automated PII, Sri Lankan phone number, IPv4, and credential sanitization pipeline (`sanitizer.py`).
  * `src/retrieval/`
    * `aws_kb_client.py` — HTTP API client for the **SLTMobitel KnowledgeBase Access API** (`/prod/retrieve` with `x-auth-secret`).
    * `rag_engine.py` — Hybrid RAG orchestrator combining the SLTMobitel AWS KnowledgeBase API and local semantic vector store (`nomic-embed-text`).
  * `src/agent/` — Multi-provider LLM gateway (`llm_gateway.py`) supporting **AWS Bedrock (`boto3`)**, **Local Ollama (`granite3.1-dense:2b`)**, and **Google Gemini**, plus RBAC governance (`governance.py`).
  * `src/api/` — 4-tab Streamlit interactive web workbench (`app.py`).
  * `tests/` — Automated `pytest` suite (`test_mvp.py`).

---

## 🚀 Quick-Start Guide

### 1. Install Dependencies
```bash
pip install -r poc-netops-assistant/requirements.txt
```

### 2. Configure Environment (`.env`)
`poc-netops-assistant/.env` is pre-configured with the SLTMobitel AWS KnowledgeBase API endpoint and `x-auth-secret` from `SLTMobitel KnowledgeBase Access Api.pdf`:
```env
AI_INFERENCE_MODE=OLLAMA_LOCAL
SLT_KB_API_URL=https://ww5659pvgk.execute-api.us-east-1.amazonaws.com/prod/retrieve
SLT_KB_AUTH_SECRET=d215af7a649fe83938414634e789b39cb3ed4ad0a1077c2d
SLT_KB_DEFAULT_TOP_K=3
AWS_REGION=us-east-1
AWS_BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
```
*(Optional)* To use **AWS Bedrock**, configure your AWS CLI credentials or set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `.env` or directly in the Streamlit sidebar. To use **Local Ollama**, ensure `ollama serve` is running with `granite3.1-dense:2b` and `nomic-embed-text:latest`.

### 3. Run the Streamlit Web Workbench
```bash
streamlit run poc-netops-assistant/src/api/app.py
```

### 4. Run Automated Tests
```bash
pytest poc-netops-assistant/tests/test_mvp.py
```
