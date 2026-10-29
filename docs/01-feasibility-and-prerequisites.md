# Phase 1: Feasibility & Prerequisites Assessment (AWS Cloud Pivot)
**Project:** SLTMobitel Cloud & Sovereign AI Platform (AWS CloudFormation / CloudFront / API Gateway + Amazon Bedrock)  
**Prepared by:** Mesith Rathnayake (Intern AI Engineer, SLT Digital Labs)  
**Status:** Active — Pivoted from IBM Sovereign Core to Cost-Optimized AWS Serverless & Edge Stack

---

## 1. Strategic Architecture Pivot: IBM Sovereign Core to AWS Cloud
Originally, this platform was scoped around **IBM Sovereign Core v1.1.0** atop bare-metal Red Hat OpenShift. Due to the prohibitive licensing and bare-metal CapEx costs of acquiring an IBM Sovereign Core entitlement key, SLT Digital Labs transitioned the architecture to a **Cost-Optimized AWS Cloud & Edge Sovereign AI Architecture**:

1. **Data Sovereignty & Pre-Flight Sanitization:** All incident tickets and customer queries pass through a local **Sovereign Data Sanitizer** (`sanitizer.py`) and **Input Guardrail** (`guardrails_evals.py`) that strip Sri Lankan phone numbers, emails, internal IPv4 addresses, and credentials *before* any payload is transmitted to AWS API Gateway or Amazon Bedrock. Cloud storage encryption uses **AWS KMS Customer-Managed Keys (KYOK)**.
2. **Edge-Accelerated Knowledge Retrieval (CloudFront + SLTMobitel AWS KB API):** Knowledge retrieval uses the live **SLTMobitel KnowledgeBase Access HTTP API** (`POST https://ww5659pvgk.execute-api.us-east-1.amazonaws.com/prod/retrieve`) fronted by **Amazon CloudFront** (`cloudfront_gateway.py`) and authenticated via `x-auth-secret`, paired with a local SOP store for internal NetOps manuals.
3. **Digital Sovereignty & Governance:** Enforces Role-Based Access Control (RBAC), read-only network advisory guardrails, honest out-of-scope abstention, and an immutable JSONL audit trail (`audit_trail.jsonl`).

---

## 2. Credentials & Entitlement Checklist
- [x] **SLTMobitel KnowledgeBase HTTP API Endpoint:** `https://ww5659pvgk.execute-api.us-east-1.amazonaws.com/prod/retrieve`
- [x] **SLTMobitel KnowledgeBase Auth Secret (`x-auth-secret`):** Configured in `.env` (`SLT_KB_AUTH_SECRET`).
- [x] **Amazon CloudFront Edge Gateway (`cloudfront_gateway.py`):** Configured with edge caching and origin custom header injection.
- [ ] **AWS IAM Credentials for Amazon Bedrock (`boto3`):** `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` with `bedrock:InvokeModel` permission in `us-east-1` (Optional; system automatically falls back to clean grounded synthesis when IAM credentials are not present).

---

## 3. Infrastructure & Software Prerequisites

### A. Developer / Operator Environment
* **OS:** Windows 10/11, Linux (Ubuntu / Amazon Linux 2023), or macOS
* **Python Runtime:** Python 3.10+ with `streamlit`, `boto3`, and `pytest`

### B. AWS Cloud Stack (Provisioned via AWS CloudFormation)
Instead of 4 isolated bare-metal networks and RHEL 10.1 Landing Zones, infrastructure is defined declaratively in [`aws-cloudformation-stack.yaml.example`](file:///d:/Education/INternship/SLT/AI%20Intern/slt-sovereign-ai-platform/infra-config-templates/aws-cloudformation-stack.yaml.example):
* **Amazon CloudFront:** Edge TLS 1.2/1.3 termination, HSTS/XSS security response headers, edge caching (`PriceClass_200`), and origin custom header injection (`x-auth-secret`).
* **Amazon API Gateway (HTTP API):** Exposes the `POST /prod/retrieve` route in `us-east-1`.
* **AWS Lambda:** Serverless retrieval and agent orchestration handler.
* **Amazon Bedrock:** Managed foundation model inference (`anthropic.claude-3-haiku-20240307-v1:0`, `claude-3-5-sonnet`, `amazon.titan-text-express-v1`, `meta.llama3-8b-instruct-v1:0`).
* **AWS KMS & Amazon S3:** Customer-managed encryption keys (KYOK) and encrypted document/audit storage.
