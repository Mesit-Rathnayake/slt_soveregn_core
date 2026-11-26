# Free-Tier Cloud Deployment Guide (Render.com)

Deploy the full **SLTMobitel Sovereign AI Portal** (React frontend + hardened FastAPI backend + Gemini LLM + SLTMobitel KnowledgeBase API) to a public HTTPS URL for free so supervisors and stakeholders can test it from any browser — **no credit card required**.

---

## 1. Deploy on Render.com (3 Minutes)

1. Go to **[https://dashboard.render.com/blueprints](https://dashboard.render.com/blueprints)** and sign in with GitHub.
2. Click **New Blueprint Instance** and select your repository:
   `Mesit-Rathnayake/slt_soveregn_core`
3. Render automatically detects `render.yaml` at the root of the repository (`plan: free`, Docker build).
4. Enter these 3 secret values when prompted (copied from your local `poc-netops-assistant/.env`):
   - **`GEMINI_API_KEY`**: Your Google AI Studio Gemini key
   - **`SLT_KB_API_URL`**: `https://ww5659pvgk.execute-api.us-east-1.amazonaws.com/prod/retrieve`
   - **`SLT_KB_AUTH_SECRET`**: The `x-auth-secret` value from `SLTMobitel KnowledgeBase Access Api.pdf`
5. Click **Apply**. Render builds the multi-stage Docker image (React + FastAPI) and publishes a public HTTPS URL such as:
   `https://slt-sovereign-ai-portal.onrender.com`

> **Note on Render Free Tier:** Free instances spin down after 15 minutes of inactivity and wake up automatically on the next request (~30–50 seconds on cold start). Subsequent requests are fast.

---

## 2. Verify Deployment

Once live, open:
- **Portal UI:** `https://<your-service>.onrender.com/`
- **Health & LLM Readiness:** `https://<your-service>.onrender.com/api/health`
  - Confirm `"status": "healthy"` and `"llm_gateway.live_llm_ready": true`.

---

## 3. Supervisor Test Cheat Sheet

Share these sample credentials and prompts with your supervisor so they can test all 3 portals immediately:

### A. New Customer Portal (No Login Needed)
Click **New Customer** and try:
- *"I am thinking of getting a new internet connection for my house — what do you suggest, Fibre or Broadband?"*
- *"What Fibre packages are under Rs. 5,000?"*
- *"What is the capital of France?"* *(verifies anti-hallucination guardrail)*

### B. Existing Customer Portal (Connection Number + OTP)
Enter any sample registered number (connection type is auto-detected after OTP verification; the 6-digit demo OTP appears right in the UI):
- **`0112456789`** — SLT Fibre (FTTH)
- **`0112889941`** — SLT Broadband (4G LTE / ADSL)
- **`0812233445`** — PEOTV
- **`0712345678`** — SLT Mobitel Mobile

Features to test:
1. **Account & Tickets Overview** (data quota, credit limit/bill balance, active & previous tickets)
2. **3-Step Fault Ticket Wizard** (auto-assigns to the least-loaded Technical Officer)
3. **AI Assistant** (grounded troubleshooting & package queries)

### C. Technical Officer Console (Staff ID + OTP)
Enter any registered SLT Staff ID and verify with the 6-digit OTP:
- **`TO-101`** — Eng. Nimal Silva (Colombo Fibre & Core)
- **`TO-102`** — Tech. Chamara Jayasinghe (Western Broadband & PEOTV)
- **`TO-103`** — Eng. Kavindu Perera (Central PEOTV & Fibre)
- **`TO-104`** — Tech. Sashini Wickramasinghe (Mobitel Mobile & 4G/5G)

Features to test:
- Review assigned fault tickets, update status (`IN_PROGRESS` / `RESOLVED`), send SMS/Email/Call updates to customers, and watch queued overflow tickets auto-promote when an officer resolves a ticket.
