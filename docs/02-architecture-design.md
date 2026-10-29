# Phase 2: High-Level Architecture Design (AWS CloudFront & Bedrock Stack)
**Project:** SLTMobitel Cloud & Sovereign AI Platform  
**Prepared by:** Mesith Rathnayake (Intern AI Engineer, SLT Digital Labs)  
**Architecture Stack:** AWS CloudFormation + Amazon CloudFront + AWS API Gateway (`/prod/retrieve`) + AWS Lambda + Amazon Bedrock

---

## 1. Architectural Overview
Following the transition away from the costly IBM Sovereign Core key, the platform uses a **6-layer AWS Cloud & Sovereign AI Architecture**. It combines **Amazon CloudFront Edge Security & Caching**, **AWS API Gateway + Lambda**, and **Amazon Bedrock** with **Sovereign Pre-Flight Controls** (PII/IP sanitization, prompt-injection guardrails, honest out-of-scope abstention, and RBAC audit logging).

### High-Level Architecture Diagram
```mermaid
graph TD
    subgraph Layer_1_Application ["1. Conversational Agent Layer (SLT Digital Labs)"]
        UI["Streamlit Conversational Chat Agent (app.py)"]
        ORCH["Unified Agent Orchestrator & Intent Router (orchestrator.py)"]
        SAN["Pre-Flight PII / IP Sanitizer & Guardrails (sanitizer.py / guardrails_evals.py)"]
    end

    subgraph Layer_2_Edge_API ["2. Amazon CloudFront & API Gateway Layer"]
        CF["Amazon CloudFront Edge Gateway (Edge Cache + HSTS + Origin x-auth-secret)"]
        APIGW["AWS API Gateway HTTP API (POST /prod/retrieve)"]
    end

    subgraph Layer_3_Retrieval ["3. Dual Knowledge Retrieval Layer"]
        AWSKB["SLTMobitel Cloud KnowledgeBase Lambda & Vector Index (us-east-1)"]
        LOCALSOP["Local NetOps Approved SOP Store (BGP / OSPF / GPON)"]
    end

    subgraph Layer_4_Inference ["4. Cloud LLM & Grounded Synthesis Layer"]
        BEDROCK["Amazon Bedrock (Claude 3 Haiku / Sonnet / Titan / Llama 3)"]
        SYNTH["Clean Grounded Synthesis & Abstention Engine (rag_engine.py)"]
    end

    subgraph Layer_5_Governance ["5. Sovereign Governance & Security Layer"]
        RBAC["Role-Based Access Control (Tier-1, Tier-2, Auditor)"]
        AUDIT["Immutable JSONL Audit Trail (audit_trail.jsonl)"]
        KMS["AWS KMS Customer-Managed Encryption (KYOK)"]
    end

    subgraph Layer_6_IaC ["6. Infrastructure-as-Code Layer"]
        CFN["AWS CloudFormation Stack (aws-cloudformation-stack.yaml)"]
    end

    UI --> ORCH
    ORCH --> SAN
    SAN --> RBAC
    SAN --> CF
    CF --> APIGW
    APIGW --> AWSKB
    SAN --> LOCALSOP
    AWSKB --> BEDROCK
    AWSKB --> SYNTH
    LOCALSOP --> BEDROCK
    LOCALSOP --> SYNTH
    BEDROCK --> AUDIT
    SYNTH --> AUDIT
    CFN -. Provisions .-> CF
    CFN -. Provisions .-> APIGW
    CFN -. Provisions .-> AWSKB
    CFN -. Provisions .-> KMS
```

---

## 2. SLTMobitel AWS KnowledgeBase HTTP API Specification
The cloud retrieval pipeline integrates with the production SLTMobitel KnowledgeBase API in `us-east-1` through the CloudFront Edge Gateway (`cloudfront_gateway.py`):
* **Endpoint:** `POST https://ww5659pvgk.execute-api.us-east-1.amazonaws.com/prod/retrieve`
* **Authentication Header:** `x-auth-secret: <SLT_KB_AUTH_SECRET>` (injected as a CloudFront Origin Custom Header)
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
