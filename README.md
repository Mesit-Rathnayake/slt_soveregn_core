# SLT Sovereign AI Platform (IBM Sovereign Core v1.1.0)

**Organization:** SLT Digital Labs  
**Author:** Mesith Rathnayake (Intern AI Engineer)  
**Status:** Phase 1 & 2 Complete | Phase 4 Local PoC In Progress (Awaiting Infrastructure & Entitlement Keys)

## 📌 Overview
This repository contains the feasibility study, architectural blueprints, infrastructure readiness templates, and the Proof-of-Concept (PoC) implementation for establishing an **SLT Sovereign AI Platform** using **IBM Sovereign Core v1.1.0**.

The initial telecommunications use case is an **AI Network Operations (NetOps) Assistant** designed to help engineers search approved technical manuals, summarize incidents, and follow grounded troubleshooting steps without exposing sensitive operational data.

## 📂 Repository Structure
* `docs/`
  * [`01-feasibility-and-prerequisites.md`](docs/01-feasibility-and-prerequisites.md) — Hardware, RHEL 10.1 Landing Zone, 4-network topology, and licensing checklist.
  * [`02-architecture-design.md`](docs/02-architecture-design.md) — 6-layer logical architecture & Mermaid system diagram.
  * [`03-risk-and-governance.md`](docs/03-risk-and-governance.md) — Risk mitigation matrix, data classification tiers, and phased roadmap.
* `infra-config-templates/` — Safe `.example` templates for IBM Sovereign Core bootstrap configuration (`global.yaml`, `odf.yaml`, `certificates.yaml`, `template.env`).
* `poc-netops-assistant/` — Modular Python RAG application for the AI Network Operations Assistant PoC.