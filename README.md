# SLT Sovereign AI Platform (IBM Sovereign Core v1.1.0)

**Organization:** SLT Digital Labs  
**Author:** Mesith Rathnayake (Intern AI Engineer)  
**Status:** Phase 1 & 2 Complete | Local MVP (Ollama + IBM Granite 3.1 + Streamlit) Operational

---

## 📌 Overview
This repository contains the technical proposal, architecture blueprints, infrastructure readiness templates, and a fully functional **Local Proof-of-Concept (PoC) Minimum Viable Product (MVP)** for the **SLT Sovereign AI Platform** using **IBM Sovereign Core v1.1.0**.

The initial telecommunications use case is an **AI Network Operations (NetOps) Assistant** designed to help engineers search approved technical manuals, sanitize PII/IP data from incident tickets, and follow grounded, citation-backed troubleshooting steps under strict read-only advisory guardrails.

---

## 📂 Repository Directory Structure
* `docs/` — Feasibility study, 6-layer architecture design, risk matrix, and governance policies.
* `infra-config-templates/` — Safe `.example` templates for IBM Sovereign Core bootstrap configuration (`global.yaml`, `odf.yaml`, `certificates.yaml`, `template.env`).
* `poc-netops-assistant/`
  * `data/approved_manuals/` — Ingested SLT Standard Operating Procedures (BGP, OSPF, GPON).
  * `data/synthetic_incidents/` — Raw and sanitized NOC incident tickets.
  * `src/ingestion/` — Automated PII, IP, and credential sanitization pipeline (`sanitizer.py`).
  * `src/retrieval/` — Hybrid semantic vector (`nomic-embed-text`) + rule-based RAG engine (`rag_engine.py`).
  * `src/agent/` — Multi-provider LLM gateway supporting local Ollama (`granite3.1-dense:2b`) and RBAC governance manager (`governance.py`).
  * `src/api/` — Streamlit interactive web workbench (`app.py`).
  * `tests/` — Automated pytest test suite (`test_mvp.py`).

---

## 🚀 Quick-Start Guide (Running the Local MVP)

### 1. Prerequisites
* Python 3.10+ installed.
* [Ollama](https://ollama.com) installed and running locally on your machine.
* Pull the required local models in your terminal:
  ```bash
  ollama pull granite3.1-dense:2b
  ollama pull nomic-embed-text:latest