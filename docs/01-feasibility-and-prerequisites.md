# Phase 1: Feasibility & Prerequisites Assessment
**Project:** SLT Sovereign AI Platform (IBM Sovereign Core v1.1.0)  
**Prepared by:** Mesith Rathnayake (Intern AI Engineer, SLT Digital Labs)  
**Status:** Pre-Deployment Readiness Checklist (Awaiting Entitlement Keys)

---

## 1. Sovereign Cloud Alignment for SLT
Based on IBM's Sovereign Cloud framework, this platform addresses three foundational pillars for SLT:
1. **Data Sovereignty:** Ensures all SLT network manuals, incident reports, and operational data remain stored and processed strictly within SLT premises. Uses customer-controlled encryption keys (*Keep Your Own Key - KYOK*).
2. **Operational Sovereignty:** Ensures high availability and resiliency so internal AI tools function independently of external international cloud outages, managed strictly by authorized SLT personnel.
3. **Digital Sovereignty:** Enforces governance, Role-Based Access Control (RBAC), and continuous compliance auditing via *Policy-as-Code*.

---

## 2. Licensing & Entitlement Checklist (Pending)
Before running the installer, the following entitlements must be acquired and verified:
- [ ] **IBM Sovereign Core v1.1.0 Entitlement Key** (Required to pull `icr.io/cpopen/sovereign-cloud-platform/sovcore-install:v1.1.0`).
- [ ] **Red Hat OpenShift Container Platform (OCP)** subscription & pull secret.
- [ ] **Red Hat Enterprise Linux (RHEL) 10.1** subscription for the Landing Zone host.
- [ ] **Red Hat OpenShift Data Foundation (ODF)** license (or Ceph evaluation for non-production PoC).

---

## 3. Infrastructure & Hardware Prerequisites
The SLT Infrastructure Team must provision the following bare-metal environment prior to Phase 3 deployment:

### A. The "Landing Zone" Bootstrap Machine
* **OS:** Red Hat Enterprise Linux (RHEL) 10.1
* **User Permissions:** Dedicated non-root user configured with passwordless `sudo` (Installer cannot be run directly as `root`).
* **Required CLI Tools:**
  * `podman` & `make`
  * `oras` (OCI Registry As Storage CLI - v1.3.0+)
  * `oc` and `oc-mirror` (OpenShift CLI tools)

### B. Compute & Storage Nodes
* [ ] Bare-metal servers identified for OpenShift Control Plane and Worker nodes.
* [ ] Dedicated GPU nodes (Optional for Phase 3/4 depending on local LLM selection vs. CPU-optimized quantized models for PoC).
* [ ] Local disks provisioned for OpenShift Data Foundation (ODF) block and object storage.

### C. Network Topology (4 Isolated Networks Required)
| Network Type | Minimum Bandwidth | Purpose |
| :--- | :--- | :--- |
| **Storage Network** | 40 Gbps+ (Recommended) | High-speed object/block storage replication |
| **Control Network** | 10 Gbps+ | Internal platform & cluster node communication |
| **User/Data Network** | 10 Gbps+ | SLT engineer access & AI workload traffic |
| **Out-of-Band (IPMI/BMC)** | 1 Gbps+ | Bare-metal hardware power & boot management |

---

## 4. Security, DNS & Certificate Prerequisites
- [ ] **Base Domain Defined:** (e.g., `sovereign-ai.slt.lk`)
- [ ] **TLS Certificates:** Wildcard/SAN certificates issued with **at least 90 days validity** remaining (`certificates.yaml`).
- [ ] **DNS Records:** Configured for OpenShift API, Ingress, and Sovereign Core portals.