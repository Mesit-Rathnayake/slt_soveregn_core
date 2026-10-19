# Phase 2: High-Level Architecture Design
**Project:** SLT Sovereign AI Platform (IBM Sovereign Core v1.1.0)  
**Prepared by:** Mesith Rathnayake (Intern AI Engineer, SLT Digital Labs)  
**Alignment:** Proposal Section 4 (Proposed Solution) & Section 5 (Initial Use Case)

---

## 1. Architectural Overview
The SLT Sovereign AI Platform is designed around a **6-layer logical architecture** deployed on-premises (or within SLT-controlled sovereign data centers) using **IBM Sovereign Core v1.1.0** atop **Red Hat OpenShift**. This ensures complete data residency, operational autonomy, and policy-as-code governance.

### High-Level Architecture Diagram
```mermaid
graph TD
    subgraph Layer_1_Application ["1. Application Layer (SLT Use Cases)"]
        UI["NetOps Assistant Web Portal / Chat UI"]
        API["FastAPI Backend & Guardrail Gateway"]
    end

    subgraph Layer_2_AI_Services ["2. AI Services Layer"]
        RAG["RAG Orchestration & Agent Engine"]
        LLM["Local / Sovereign LLM Inference Server"]
        EMB["Embedding Model & Vector Database"]
    end

    subgraph Layer_3_Control_Management ["3. Control & Service Management Layer (IBM Sovereign Core)"]
        IAM["Identity, Access (RBAC) & Secrets Vault"]
        CAT["Service Catalog & Tenant Workspaces"]
        OBS["Observability, Metering & Audit Logging"]
    end

    subgraph Layer_4_Governance_Security ["4. Governance & Security Layer (Cross-Cutting)"]
        PAC["Policy-as-Code & Continuous Compliance"]
        KYOK["Keep Your Own Key (KYOK) Encryption"]
    end

    subgraph Layer_5_Platform ["5. Platform Layer"]
        OCP["Red Hat OpenShift Container Platform (OCP)"]
        ODF["OpenShift Data Foundation (Ceph Block/Object Storage)"]
    end

    subgraph Layer_6_Infrastructure ["6. Infrastructure Layer (SLT Data Center)"]
        BM["Bare-Metal Compute & Optional GPU Nodes"]
        NET["4 Isolated Networks (Storage 40G, Control 10G, User 10G, IPMI 1G)"]
    end

    UI --> API
    API --> IAM
    API --> RAG
    RAG --> EMB
    RAG --> LLM
    RAG --> OBS
    Layer_2_AI_Services --> Layer_3_Control_Management
    Layer_3_Control_Management --> Layer_4_Governance_Security
    Layer_4_Governance_Security --> Layer_5_Platform
    Layer_5_Platform --> Layer_6_Infrastructure