# Phase 1: Feasibility & Prerequisites Assessment (AWS Hybrid Pivot)
**Project:** SLTMobitel Hybrid Cloud & Sovereign AI Platform (AWS CloudFormation / CloudFront / API Gateway + Bedrock & Ollama)  
**Prepared by:** Mesith Rathnayake (Intern AI Engineer, SLT Digital Labs)  
**Status:** Active — Pivoted from IBM Sovereign Core to Cost-Optimized AWS Cloud + Local Hybrid Stack

---

## 1. Strategic Architecture Pivot: IBM Sovereign Core to AWS Hybrid Cloud
Originally, this platform was scoped around **IBM Sovereign Core v1.1.0** atop bare-metal Red Hat OpenShift. Due to the prohibitive licensing and bare-metal CapEx costs of acquiring an IBM Sovereign Core entitlement key, SLT Digital Labs transitioned the architecture to a **Cost-Optimized AWS Hybrid Sovereign AI Architecture**:

1. **Data Sovereignty & Pre-Flight Sanitization:** All incident tickets and customer queries pass through a local **Sovereign Data Sanitizer** (`sanitizer.py`) that strips Sri Lankan phone numbers, emails, internal IPv4 addresses, and credentials *before* any payload is transmitted to AWS API Gateway or Amazon Bedrock. Storage encryption uses **AWS KMS Customer-Managed Keys (KYOK)**.
2. **Serverless Knowledge Retrieval (SLTMobitel AWS KB API):** Knowledge retrieval uses the live **SLTMobitel KnowledgeBase Access HTTP API** (`POST https://ww5659pvgk.execute-api.us-east-1.amazonaws.com/prod/retrieve`) fronted by **Amazon CloudFront / AWS API Gateway** and authenticated via `x-auth-secret`, paired with a local vector store (`nomic-embed-text`) for internal NetOps SOP manuals.
3. **Digital Sovereignty & Governance:** Enforces Role-Based Access Control (RBAC), read-only network advisory guardrails, mandatory citations, and an immutable local/S3 JSONL audit trail (`audit_trail.jsonl`).

---

## 2. Credentials & Entitlement Checklist
- [x] **SLTMobitel KnowledgeBase HTTP API Endpoint:** `https://ww5659pvgk.execute-api.us-east-1.amazonaws.com/prod/retrieve`
- [x] **SLTMobitel KnowledgeBase Auth Secret (`x-auth-secret`):** Configured in `.env` (`SLT_KB_AUTH_SECRET`).
- [x] **Local Sovereign Fallback Models (Ollama):** `granite3.1-dense:2b` and `nomic-embed-text:latest` (Zero licensing cost).
- [ ] **AWS IAM Credentials for Amazon Bedrock (`boto3`):** `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` with `bedrock:InvokeModel` permission in `us-east-1` (Optional; system automatically falls back to Local Ollama or Direct AWS KB Chunk Synthesis when offline).

---

## 3. Infrastructure & Software Prerequisites

### A. Developer / Operator Workstation or EC2 Host
* **OS:** Windows 10/11, Linux (Ubuntu / Amazon Linux 2023), or macOS
* **Python Runtime:** Python 3.10+ with `streamlit`, `boto3`, and `pytest`
* **Local Sovereign Inference (Optional):** [Ollama](https://ollama.com) daemon running on port `11434`

### B. AWS Cloud Stack (Provisioned via AWS CloudFormation)
Instead of 4 isolated bare-metal networks and RHEL 10.1 Landing Zones, infrastructure is defined declaratively in [`aws-cloudformation-stack.yaml.example`](file:///d:/Education/INternship/SLT/AI%20Intern/slt-sovereign-ai-platform/infra-config-templates/aws-cloudformation-stack.yaml.example):
* **Amazon CloudFront:** Edge TLS termination, caching, and custom header forwarding (`x-auth-secret`).
* **Amazon API Gateway (HTTP API):** Exposes the `POST /prod/retrieve` route in `us-east-1`.
* **AWS Lambda:** Serverless retrieval handler connecting API Gateway to the vector index.
* **Amazon Bedrock:** Managed foundation model inference (`anthropic.claude-3-haiku-20240307-v1:0`, `amazon.titan-text-express-v1`, `meta.llama3-8b-instruct-v1:0`).
* **AWS KMS & Amazon S3:** Customer-managed encryption keys (KYOK) and encrypted document/audit storage.
