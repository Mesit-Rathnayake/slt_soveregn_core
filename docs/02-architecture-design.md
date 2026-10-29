# Phase 2: High-Level Architecture Design (AWS Hybrid Sovereign Stack)
**Project:** SLTMobitel Hybrid Cloud & Sovereign AI Platform  
**Prepared by:** Mesith Rathnayake (Intern AI Engineer, SLT Digital Labs)  
**Architecture Stack:** AWS CloudFormation + Amazon CloudFront + AWS API Gateway (`/prod/retrieve`) + Amazon Bedrock + Local Ollama

---

## 1. Architectural Overview
Following the transition away from the costly IBM Sovereign Core key, the platform uses a **6-layer Hybrid Cloud & Sovereign AI Architecture**. It combines **AWS Serverless & Edge Services** (provisioned via **AWS CloudFormation** and protected by **Amazon CloudFront**) with **On-Premises Sovereign Controls** (pre-flight PII/IP sanitization, local Ollama LLM/embedding execution, and RBAC audit logging).

### High-Level Architecture Diagram
```mermaid
graph TD
    subgraph Layer_1_Application ["1. Application & Workbench Layer (SLT Digital Labs)"]
        UI["Streamlit 4-Tab AI Workbench (Customer KB + NetOps Triage)"]
        SAN["Pre-Flight PII / IP / Secret Sanitizer (sanitizer.py)"]
    end

    subgraph Layer_2_Edge_API ["2. AWS Edge & API Gateway Layer"]
        CF["Amazon CloudFront Edge Distribution (TLS 1.2+ / WAF)"]
        APIGW["AWS API Gateway HTTP API (POST /prod/retrieve + x-auth-secret)"]
    end

    subgraph Layer_3_Retrieval ["3. Dual Hybrid RAG Retrieval Layer"]
        AWSKB["SLTMobitel Cloud KnowledgeBase Lambda & Vector Index (us-east-1)"]
        LOCALVEC["Local NetOps SOP Vector Store (nomic-embed-text)"]
    end

    subgraph Layer_4_Inference ["4. Multi-Provider LLM Inference Layer"]
        BEDROCK["Amazon Bedrock (Claude 3 Haiku / Sonnet / Titan / Llama 3)"]
        OLLAMA["Local Sovereign Ollama Server (granite3.1-dense:2b)"]
        RULES["Deterministic Grounded Rule & Chunk Synthesis Fallback"]
    end

    subgraph Layer_5_Governance ["5. Sovereign Governance & Security Layer"]
        RBAC["Role-Based Access Control (Tier-1, Tier-2, Auditor)"]
        AUDIT["Immutable JSONL Audit Trail (audit_trail.jsonl)"]
        KMS["AWS KMS Customer-Managed Encryption (KYOK)"]
    end

    subgraph Layer_6_IaC ["6. Infrastructure-as-Code Layer"]
        CFN["AWS CloudFormation Stack (aws-cloudformation-stack.yaml)"]
    end

    UI --> SAN
    SAN --> RBAC
    SAN --> CF
    CF --> APIGW
    APIGW --> AWSKB
    SAN --> LOCALVEC
    AWSKB --> BEDROCK
    AWSKB --> OLLAMA
    AWSKB --> RULES
    LOCALVEC --> BEDROCK
    LOCALVEC --> OLLAMA
    LOCALVEC --> RULES
    BEDROCK --> AUDIT
    OLLAMA --> AUDIT
    RULES --> AUDIT
    CFN -. Provisions .-> CF
    CFN -. Provisions .-> APIGW
    CFN -. Provisions .-> AWSKB
    CFN -. Provisions .-> KMS
```

---

## 2. SLTMobitel AWS KnowledgeBase HTTP API Specification
The cloud retrieval pipeline integrates directly with the production SLTMobitel KnowledgeBase API in `us-east-1`:
* **Endpoint:** `POST https://ww5659pvgk.execute-api.us-east-1.amazonaws.com/prod/retrieve`
* **Authentication Header:** `x-auth-secret: <SLT_KB_AUTH_SECRET>`
* **Request Payload:**
  ```json
  {
    "query": "How do I check data balance?",
    "top_k": 3
  }
  ```
* **Response Payload (200 OK):**
  ```json
  {
    "query": "How do I check data balance?",
    "chunks": [
      {
        "content": "Relevant knowledge base text...",
        "score": 0.89
      }
    ],
    "count": 1
  }
  ```
