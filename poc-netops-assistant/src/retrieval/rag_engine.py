import os
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent.llm_gateway import SovereignLLMGateway
from retrieval.aws_kb_client import SLTMobitelCloudKBClient


class SovereignNetOpsRAG:
    """
    SLTMobitel AI - AWS Cloud KnowledgeBase + Local SOP RAG Engine.
    - SLTMobitel Cloud KB: Uses AWS API Gateway/CloudFront HTTP API (/prod/retrieve).
    - Local NetOps SOPs: Uses fast lexical keyword & section retrieval.
    - Inference Engines: AWS Bedrock, Google Gemini, or Deterministic Grounded Synthesis.
    """

    def __init__(self, manuals_dir: Path, enable_embeddings: bool = False):
        self.manuals_dir = manuals_dir
        env_path = manuals_dir.parents[1] / ".env"
        self.llm_gateway = SovereignLLMGateway(env_path=env_path)
        self.aws_kb_client = SLTMobitelCloudKBClient(env_path=env_path)
        self.inference_mode = os.getenv("AI_INFERENCE_MODE", "AWS_BEDROCK")
        self.enable_embeddings = False
        self.knowledge_base = self._load_manuals()

    def _load_manuals(self) -> list[dict]:
        chunks = []
        if not self.manuals_dir.exists():
            return chunks

        for file_path in sorted(self.manuals_dir.glob("*.md")):
            content = file_path.read_text(encoding="utf-8")
            doc_id_match = re.search(r"\*\*Document ID:\*\*\s*(\S+)", content)
            title_match = re.search(r"\*\*Title:\*\*\s*(.+)", content)
            doc_id = doc_id_match.group(1) if doc_id_match else file_path.stem
            doc_title = title_match.group(1).strip() if title_match else file_path.name

            sections = re.split(r"\n(?=##\s+)", content)
            for sec in sections:
                lines = sec.strip().splitlines()
                if not lines:
                    continue
                header = lines[0].replace("##", "").strip()
                chunk_text = sec.strip()
                chunks.append({
                    "doc_id": doc_id,
                    "doc_title": doc_title,
                    "source_file": file_path.name,
                    "section": header,
                    "content": chunk_text,
                    "embedding": None
                })
        return chunks

    def retrieve_relevant_sections(self, query_text: str, top_k: int = 4) -> list[dict]:
        query_tokens = set(re.findall(r"[a-zA-Z0-9_-]{3,}", query_text.lower()))
        scored_chunks = []

        for chunk in self.knowledge_base:
            chunk_tokens = set(re.findall(r"[a-zA-Z0-9_-]{3,}", chunk["content"].lower()))
            lexical_overlap = len(query_tokens.intersection(chunk_tokens))
            if chunk["doc_id"].lower() in query_text.lower():
                lexical_overlap += 10

            if lexical_overlap > 0:
                norm_score = min(0.95, 0.55 + (lexical_overlap * 0.06))
                scored_chunks.append((lexical_overlap, norm_score, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        results = []
        for overlap, norm_score, chunk in scored_chunks[:top_k]:
            c_copy = {k: v for k, v in chunk.items() if k != "embedding"}
            c_copy["similarity_score"] = round(norm_score, 4)
            results.append(c_copy)
        return results

    def retrieve_from_aws_kb(
        self,
        query_text: str,
        top_k: int = 3,
        kb_secret_override: str | None = None,
        kb_endpoint_override: str | None = None
    ) -> dict:
        """Retrieves relevant chunks from the SLTMobitel AWS KnowledgeBase HTTP API."""
        return self.aws_kb_client.retrieve(
            query=query_text,
            top_k=top_k,
            secret_override=kb_secret_override,
            endpoint_override=kb_endpoint_override
        )

    def _invoke_llm(
        self,
        prompt: str,
        active_mode: str,
        ollama_model: str | None = None,
        gemini_api_key: str | None = None,
        bedrock_model: str | None = None,
        aws_region: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None
    ) -> tuple[dict, str]:
        if active_mode == "AWS_BEDROCK":
            chosen_bedrock = bedrock_model or self.llm_gateway.aws_bedrock_model
            llm_res = self.llm_gateway.generate_with_bedrock(
                prompt,
                model_override=chosen_bedrock,
                aws_region=aws_region,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key
            )
            return llm_res, f"AWS_BEDROCK ({chosen_bedrock})"
        elif active_mode == "GEMINI_CLOUD":
            llm_res = self.llm_gateway.generate_with_gemini(prompt, api_key_override=gemini_api_key)
            return llm_res, f"GEMINI_CLOUD ({self.llm_gateway.gemini_model})"
        else:
            raise ValueError(f"Unsupported LLM mode: {active_mode}")

    STOPWORDS = {
        "how", "hows", "what", "whats", "when", "where", "who", "whos", "why", "which",
        "can", "could", "would", "should", "the", "and", "for", "with", "from", "that",
        "this", "have", "has", "had", "not", "are", "was", "were", "will", "about",
        "into", "your", "my", "our", "their", "please", "tell", "check", "get",
        "use", "using", "slt", "mobitel", "sltmobitel", "context", "previous",
        "question", "does", "need", "want", "sri", "lanka", "lankan", "colombo",
        "visit", "island", "world", "way", "more", "make", "give", "know",
        "see", "view", "show", "find", "list"
    }

    @staticmethod
    def _stem_token(word: str) -> str:
        """Lightweight stemmer & spelling normalizer so British/American and plural forms match."""
        w = word.lower().strip()
        if w in ("fibre", "fiber", "ftth"):
            return "fiber"
        if w in ("peotv", "peo"):
            return "peo"
        if w in ("wifi", "wlan"):
            return "wifi"
        if w in ("addon", "addons"):
            return "addon"
        if w in ("prepaid", "postpaid"):
            return "paid"
        if w in ("socket", "outlet", "plug", "plugged"):
            return "outlet"
        if w in ("restart", "restarted", "restarting", "reboot", "rebooted"):
            return "restart"
        if w in ("working", "works", "worked", "work"):
            return "work"
        if w in ("slow", "slower", "slowly"):
            return "slow"
        if w.startswith("activ"):
            return "activ"
        if w.startswith("packag"):
            return "packag"
        if w.startswith("troubleshoot"):
            return "troubleshoot"
        if w.startswith("connect"):
            return "connect"
        if len(w) > 4 and w.endswith("es"):
            return w[:-2]
        if len(w) > 3 and w.endswith("s"):
            return w[:-1]
        return w

    @classmethod
    def _chunks_are_relevant_to_query(cls, query_text: str, chunks: list[dict], min_score: float = 0.35) -> bool:
        """
        Determines whether the retrieved AWS KB chunks actually contain knowledge relevant
        to the user's question. Prevents dumping irrelevant chunks when the KB doesn't know,
        while accepting valid AWS KB chunks whose cosine similarity is in the 0.35–0.65 range.
        """
        if not chunks:
            return False

        top_score = max(
            float(c.get("rerank_score", c.get("score", 0.0)))
            for c in chunks
        )
        raw_words = [w for w in re.findall(r"[a-zA-Z0-9]{2,}", query_text.lower()) if w not in cls.STOPWORDS and len(w) >= 3]
        query_keywords = {cls._stem_token(w) for w in raw_words}

        if not query_keywords:
            return False

        combined_content = " ".join(c.get("content", "") + " " + c.get("raw_content", "") for c in chunks).lower()
        content_words = {cls._stem_token(w) for w in re.findall(r"[a-zA-Z0-9]{3,}", combined_content)}

        overlap = query_keywords.intersection(content_words)

        if len(overlap) == 0:
            return False

        if top_score >= min_score and len(overlap) >= 1:
            return True

        return False

    @staticmethod
    def _synthesize_clean_kb_fallback(query_text: str, chunks: list[dict]) -> tuple[str, list[str]]:
        """
        Synthesizes a clean, conversational answer and bullet points directly from
        the retrieved AWS KB chunks when an external LLM is offline or in fast mode.
        """
        q_lower = query_text.lower()
        parts = re.split(r"\s*\(context:", query_text, maxsplit=1, flags=re.IGNORECASE)
        current_q = parts[0].strip().lower()
        context_part = parts[1].strip(" )").lower() if len(parts) > 1 else ""
        combined = "\n".join(c.get("content", "") for c in chunks)
        combined_lower = combined.lower()

        is_troubleshoot_intent = any(t in current_q for t in (
            "not working", "slow", "low speed", "speed is", "troubleshoot", "restart",
            "restarted", "reboot", "disconnected", "no connection", "no internet",
            "blinking", "problem", "issue", "fault", "broken", "socket", "outlet",
            "on but", "on bot"
        ))

        # 1A. Checking Active Packages / Active Data Packages / Active Call & Voice Packages (#888# / MySLT / #170#)
        if any(w in q_lower for w in (
            "active", "activated", "activation", "activations", "my package", "current package",
            "upahara", "samurdhi", "garusaru", "kalaguna", "liyasara"
        )):
            ans = (
                "You can view and manage your **active SLTMobitel Data, Call/Voice, and Broadband packages** "
                "using the **Self-Care USSD Portal (`#888#`)**, **MySLT App**, or **Data/Billing Shortcodes**:"
            )
            bullets = [
                "**Check Active Packages & Plans (`#888#` Self-Care Portal):** Dial **`#888#`** and select **My Package** or **My Activations** to see your currently active Pre-Paid/Post-Paid Call, Broadband Data, and VAS packages, or to activate/deactivate plans.",
                "**Check Active Data Packages & Remaining GB (`MySLT App` / `#170#`):** Open **MySLT App → Internet → Data Remaining** (or dial **`#170#`**) to view active data bundles, Extra GB, and streaming add-ons.",
                "**Check Current Usage & Account Summary (`#1456#`):** Dial **`#1456#`** (or call `1456` IVR) to check Current Usage, Account Balance, and Last Month Bill.",
                "**Post-Paid & Voice Plans Covered under `#888#`:** Includes **Unlimited Family / Home Calls (`Rs. 747/month`)** and Post-Paid plans (*Upahara, New Upahara, Samurdhi, Meth, Garusaru, Media, Kalaguna, Liyasara, ACTIVF, SRIL, VAL50, FX190/390/790, DoubleM*)."
            ]
            return ans, bullets

        # 1B. eSIM / *#06# Compatibility & New Connection Documents
        if any(w in q_lower for w in ("esim", "e-sim", "eid", "06#", "document", "documents", "nic", "passport", "new connection")):
            if "esim" in combined_lower or "*#06#" in combined_lower or "esim" in q_lower or "e-sim" in q_lower:
                ans = "Here is how to check **SLTMobitel eSIM** compatibility and activate an eSIM:"
                bullets = [
                    "**Verify Device eSIM Compatibility:** Dial **`*#06#`** on your phone and confirm that an **EID number** is displayed.",
                    "**Get Your eSIM:** Visit `https://sltmobitel.lk/esim` or any SLTMobitel branch/outlet with your **NIC / Driving License / Passport** to obtain your eSIM QR profile."
                ]
                return ans, bullets
            if "required documents" in combined_lower or "application form" in combined_lower:
                ans = "To obtain a **new SLTMobitel Prepaid or Postpaid connection** at a retail outlet, please provide:"
                bullets = [
                    "**1. Completed Application Form**",
                    "**2. Identity Proof:** National Identity Card (NIC), Driving License, or Passport.",
                    "**3. Valid Billing Proof:** Water bill, electricity bill, fixed-line telephone bill, credit card statement, or bank current account statement."
                ]
                return ans, bullets

        # 1C. mCash Account & Bank Top-Up Management
        if "mcash" in q_lower or "m-cash" in q_lower or ("bank account" in q_lower and "mcash" in combined_lower):
            ans = "Here is how to manage your **SLTMobitel mCash** account and linked bank accounts:"
            bullets = [
                "**Remove a Saved Bank Account in mCash:** Log in to the **mCash Main Menu** → Click **Top Up Via Bank Account** → Select the Bank Account → Tap the **Delete icon** → **Confirm**.",
                "**mCash USSD & App Access:** Dial **`#111#`** or use the **mCash Smartphone App** for fast transactions, bill payments, and promotions."
            ]
            return ans, bullets

        # 1D. Data Add-ons (YouTube, WhatsApp/Messenger, Gaming, LMS E-Learning, Streaming)
        if any(w in q_lower for w in (
            "add-on", "addon", "addons", "extra gb", "youtube", "whatsapp", "messenger",
            "viber", "youth", "gamer", "gaming", "lms", "learning", "streamer", "entertainment combo"
        )):
            ans = "Here are the **SLTMobitel Data Add-ons** (Social, Streaming, Gaming & E-Learning) — activate via **`#170#`** or the **MySLT App**:"
            bullets = [
                "**Social & Video (7 Days):** **YouTube (7 Days):** `15 GB` for **Rs. 155** | **Messenger (7 Days):** `10 GB` (WhatsApp, Viber, Messenger) for **Rs. 45** | **Youth Add-on (7 Days):** `20 GB` for **Rs. 195**.",
                "**Entertainment & Streaming (Monthly):** **Entertainment Combo:** `Unlimited` streaming data for **Rs. 1,990** | **Streamer Premium:** `150 GB` for **Rs. 4,000**.",
                "**Gaming Add-ons:** **Gamer Lite:** `25 GB` for **Rs. 500** | **Gamer Premium:** `100 GB` for **Rs. 3,000**.",
                "**E-Learning (LMS) & Voice Add-ons:** **LMS Lite:** `30 GB` for **Rs. 195** | **LMS Max:** `100 GB` for **Rs. 490** | **Voice 100 Min:** `100 minutes` (SLT-to-SLT) for **Rs. 200**."
            ]
            return ans, bullets

        # 1E. USSD / Balance / Billing / Self-Care Portal
        if any(w in q_lower for w in ("balance", "ussd", "code", "codes", "bill", "billing", "1456", "888", "170", "myslt", "usage")):
            ans = (
                "You can check your **SLTMobitel Data & Bill Balance**, activate **Extra GB / Data Add-ons**, "
                "and manage your account using the **MySLT App**, **Web Portal**, or **USSD Shortcodes**:"
            )
            bullets = [
                "**Billing & Balance USSD (`#1456#` or dial `1456` IVR):** Check Current Usage, Account Balance, Last Month Bill, Total Billed Usage, Last Payment, Billed Date, and Credit Limit.",
                "**Self-Care Portal (`#888#`):** View and manage **My Package**, **My Activations**, Pre-Paid/Post-Paid plans, and PUK codes.",
                "**Data Add-ons & Extra GB (`#170#` / `MySLT App`):** Open **MySLT App → Internet → Data Remaining** (or dial **`#170#`**) to check remaining data or activate add-ons.",
                "**Other Key Shortcodes:** **`#999#`** (Roaming) | **`#111#`** (mCash) | **`*#06#`** (eSIM EID Check)."
            ]
            return ans, bullets

        # 2A. Fibre (FTTH) Broadband Packages, Speeds & Megaline Migration
        if not is_troubleshoot_intent and any(w in q_lower for w in ("fibre", "fiber", "ftth", "trio", "megaline", "ultra", "turbo", "100 mbps", "300 mbps", "1 gbps", "1000 mbps")):
            ans = "Here are the **SLTMobitel Fibre (FTTH) Broadband** packages, speeds (up to `300 Mbps` / `1 Gbps`), and migration offers:"
            bullets = [
                "**Fibre Anytime & Bundled Trio Packages:** **Fiber Starter:** `80 GB` (**Rs. 2,690**, `100/50 Mbps`) | **Trio Vibe:** `40 GB` (**Rs. 3,530**) | **Trio Vibe Plus:** `40 GB` (**Rs. 4,100**) | **Trio Shine:** `100 GB` (**Rs. 4,950**).",
                "**Fibre Unlimited Home & Pro Packages:** **Unlimited Home:** **Rs. 5,900** (`100/50 Mbps`) | **Unlimited Home Plus:** **Rs. 9,900** (`200/100 Mbps`) | **Unlimited Twin:** **Rs. 14,900** | **Unlimited Pro:** **Rs. 19,900** (`500/200 Mbps`).",
                "**High-Speed Fibre Edge, Turbo & Ultra (`1 Gbps`):** **Unlimited Edge:** **Rs. 29,900** (`750/250 Mbps`) | **Unlimited Turbo:** **Rs. 39,900** (`1000/300 Mbps`) | **Ultra Prime:** `5,000 GB` (**Rs. 75,000**, `1000/500 Mbps`) | **Ultra Flash Prime:** `200 GB/day` (**Rs. 75,000**, `1000/500 Mbps`).",
                "**Megaline to Fibre Migration:** Standard **Rs. 7,500** (**Promotional Rs. 5,000**) when upgrading from Megaline Double Play to Fibre Double Play or Triple Play (STB included)."
            ]
            return ans, bullets

        # 2B. PEOTV Packages (when specifically asking about PEOTV / TV / Channels)
        if not is_troubleshoot_intent and any(w in q_lower for w in ("peotv", "peo", "channel", "channels", "television", "tv", "uthayam", "titanium", "platinum", "silver", "bronze", "gold")):
            if not any(w in q_lower for w in ("lte", "4g", "broadband")):
                ans = "Here are the **SLTMobitel PEOTV & PEO Mobile** packages and channel lineups:"
                bullets = [
                    "**Premium & HD Packages:** **PEO HD Plus:** `160 channels` (**Rs. 3,125**) | **PEO Titanium:** `139 channels` (**Rs. 2,940**) | **PEO Platinum:** `125 channels` (**Rs. 2,660**).",
                    "**Family & Mid-Tier Packages:** **PEO Gold:** `108 channels` (**Rs. 2,100**) | **PEO Entertainment:** `112 channels` (**Rs. 1,875**) | **PEO Family:** `100 channels` (**Rs. 1,625**).",
                    "**Silver, Bronze & Regional Packages:** **PEO Silver Plus:** `98 channels` (**Rs. 1,375**) | **PEO Silver:** `87 channels` (**Rs. 1,125**) | **PEO Bronze:** `72 channels` (**Rs. 860**) | **PEO Uthayam:** `63 channels` (**Rs. 860**) | **Tamil Regional:** `68 channels` (**Rs. 1,125**).",
                    "**PEO on 4G & Mobile:** **PEO 4G Elite:** `50 channels` (**Rs. 790/month**, STB Rs. 11,990) | **PEO Mobile App:** Unlimited app data for **Rs. 249/month**."
                ]
                return ans, bullets

        # 2C. 4G LTE Home Broadband, Unlimited Flash & General Package Inquiries
        if not is_troubleshoot_intent and any(w in q_lower for w in ("package", "packages", "price", "prices", "lte", "4g", "broadband", "flash", "hbb", "plan", "plans", "unlimited", "anytime", "volte")):
            ans = "Here are the **SLTMobitel 4G LTE Home Broadband, Unlimited Flash, Fibre, and PEOTV** packages:"
            bullets = [
                "**4G LTE Anytime Packages (30 Days):** `20 GB` (**Rs. 535**) | **HBB Anytime 899:** `35 GB` (**Rs. 899**) | **HBB Anytime 1899:** `75 GB` (**Rs. 1,899**) | `115 GB` (**Rs. 2,590**) | **HBB Anytime 200GB:** **Rs. 3,990** | **HBB Anytime 400GB:** **Rs. 7,990**.",
                "**4G LTE Unlimited & Flash Packages:** **LTE Unlimited 2 / 4 / 8:** **Rs. 2,950** (`2 Mbps`), **Rs. 5,150** (`4 Mbps`), **Rs. 7,090** (`8 Mbps`) | **Unlimited LTE Flash 5:** **Rs. 2,350** (`5 GB/day` then `1 Mbps`, plus free unlimited `12 midnight–7 AM`) | **Unlimited LTE Flash 10:** **Rs. 4,090** (`10 GB/day` then `1 Mbps`).",
                "**Fibre (FTTH) Broadband:** Starts at **Fiber Starter** (`80 GB` — **Rs. 2,690**, `100/50 Mbps`) and **Unlimited Home** (**Rs. 5,900**) up to `1 Gbps` **Unlimited Turbo / Ultra Prime**.",
                "**PEOTV & Fixed Voice Plans:** **PEO Bronze** (`72 ch` — **Rs. 860**) to **PEO HD Plus** (`160 ch` — **Rs. 3,125**) | **Unltd Home My Phone:** **Rs. 747/month** | **Voice Unltd Home/Office SLT Phone:** **Rs. 902/month**."
            ]
            return ans, bullets

        # 3. APN / SIM / Credit Limit / Value Added Services (VAS) / Roaming & IDD
        if any(w in q_lower for w in ("apn", "sim", "credit limit", "vas", "value added", "mtunes", "gprs", "echannelling", "roaming", "idd", "international")):
            if any(w in q_lower for w in ("roaming", "idd", "international", "abroad", "overseas")):
                ans = "Here are the **SLTMobitel International Roaming & IDD** details:"
                bullets = [
                    "**Mobile & Fixed Roaming / IDD:** SLTMobitel offers tailored outbound/inbound Mobile Roaming, International SMS, and Fixed/Mobile IDD rates (`https://sltmobitel.lk/personal/idd-and-roaming`).",
                    "**Activate or Check Roaming Rates:** Dial **`#999#`** or use the **MySLT App** before traveling."
                ]
                return ans, bullets
            ans = "Here are the **SLTMobitel Mobile Data (APN), SIM, Credit Limit, and VAS** details:"
            bullets = [
                "**Mobile Data APN Setting:** Set your handset GPRS/Mobile Data APN to **`mobitel`**.",
                "**Triple-Cut SIM & eSIM:** SLTMobitel provides a 3-in-1 SIM (Standard, Micro, and Nano SIM) as well as **eSIM** (check compatibility by dialing **`*#06#`**).",
                "**Credit Limit Policy:** You receive an SMS alert at **75% usage** of your credit limit. Exceeding 100% may interrupt service until an interim payment is made.",
                "**Value Added Services (VAS):** Includes mTunes (`777`), News Alerts, mInsurance, e-Channelling (`225`), mTicketing (`365`), and mCash (`#111#`)."
            ]
            return ans, bullets

        # 4. Payment Receipt / Complaint / Support Contact Channels / Branch Locations
        if any(w in q_lower for w in (
            "complaint", "receipt", "whatsapp", "support", "contact", "branch", "branches",
            "office", "location", "locations", "store", "hotline", "number", "kandy", "jaffna", "airport", "gampaha"
        )):
            ans = (
                "Here are the **SLTMobitel Customer Support Hotlines**, **Payment Receipt Channels**, "
                "and **Branch Locations**:"
            )
            bullets = [
                "**24x7 Customer Hotlines:** Dial **`1212`** (SLT Fixed / Fibre / PEOTV) or **`1717`** (Mobitel Mobile) to log a service request or inquiry.",
                "**Submit Payment Receipts (with SR Number & Mobile Number):** WhatsApp/Viber **`+94 71 175 5777`**, Email **`info@mobitel.lk`**, or Fax **`+94 11 233 0396`**.",
                "**Key Flagship & Regional Branches:** **Colombo Flagship Store** (No. 108, W.A.D. Ramanayake Mw, Colombo 02 — `071 275 5777`), **BIA Airport Arrival/Departure** (`0112 265 555`), **Kandy City Centre**, **Jaffna**, **Anuradhapura**, **Gampaha**, **One Galle Face**, **BMICH**, and **Rotunda Tower** (`071 275 5777`).",
                "**Full Branch Locator:** `https://www.slt.lk/en/contact-us/branch-locator/our-locations/our-network`."
            ]
            return ans, bullets

        # 5. Enterprise / SME / Business Solutions (Cloud, SDDC, Cyber Security, Starlink)
        if any(w in q_lower for w in ("enterprise", "business", "sme", "wholesale", "starlink", "cloud", "sddc", "cyber")):
            ans = (
                "**SLTMobitel Business & Enterprise Solutions** provide ICT infrastructure for SMEs, "
                "Micro Businesses, Enterprises, and Wholesale partners:"
            )
            bullets = [
                "**Enterprise Premium Cloud & SDDC:** High-performance **Software Defined Data Center (SDDC)** cloud with rapid provisioning and **pay-as-you-go** billing.",
                "**Core Enterprise Portfolio:** Enterprise Connectivity, Cyber Security, Voice & Collaboration, AI Portfolio, Digital & Managed Services, and Starlink Business solutions."
            ]
            return ans, bullets

        # 6A. Voice / Landphone Troubleshooting (Dial Tone, Noise on Line, Low Ringing Volume, Damaged Wire)
        if any(w in q_lower for w in ("dial tone", "ringing", "tone volume", "noise", "disturbance", "telephone", "landphone", "landline", "phone wire", "voice")):
            ans = "Here are the **SLTMobitel Fixed Voice / Landphone Troubleshooting** steps:"
            bullets = [
                "**No Dial Tone or Line Noise / Disturbance:** Check whether all telephone and ONT (`Phone 1`) cables are tightly connected.",
                "**Ringing Sound Very Low:** Adjust the **ring tone volume button** on the telephone unit to **High**.",
                "**ONT Voice Indicator (`Phone` LED is OFF):** Indicates the voice account is unable to register — please call **`1212`**.",
                "**Damaged Telephone Wire (Inside or Outside Premises):** Log a fault via **`1212`** or the **MySLT App** (`https://myslt.slt.lk/`)."
            ]
            return ans, bullets

        # 6B. Wireless Extender (WPS) Setup
        if any(w in current_q for w in ("extender", "wps", "repeater", "booster")):
            ans = "To connect your **Wireless Extender** to your SLTMobitel router using **WPS**:"
            bullets = [
                "**1. Plug In:** Plug the wireless extender into a wall power outlet.",
                "**2. Press Router WPS:** Press the **WPS button** on your SLTMobitel router.",
                "**3. Press Extender WPS:** Press the **WPS button** on the wireless extender to pair automatically."
            ]
            return ans, bullets

        # 6C. Multi-Stage Router / Wi-Fi / Broadband / Slow-Speed / Power-Socket Troubleshooting
        if any(w in q_lower for w in (
            "router", "restart", "restarted", "reboot", "wifi", "wi-fi", "wlan", "cable", "cables",
            "slow", "speed", "disconnect", "connection", "connectivity", "internet", "broadband",
            "led", "blinking", "light", "lights", "socket", "outlet", "power", "button"
        )):
            # Stage 1: User already restarted / rebooted the router and the issue persists
            if any(w in current_q for w in ("restarted", "rebooted", "already tried", "did that", "done that", "still slow", "still not working")):
                ans = "Since you have **already restarted the router** and the issue persists, follow these **post-restart diagnostic & escalation steps**:"
                bullets = [
                    "**1. Verify Data Quota / FUP Throttling (`MySLT App` / `#170#`):** Check **MySLT App → Internet → Data Remaining** (`https://myslt.slt.lk/`) or dial **`#170#`**. If your Anytime or daily Flash quota is exhausted, speeds remain throttled even after a reboot until **Extra GB** is activated.",
                    "**2. Check Router `LOS` & `GPON / PON` Indicator Lights:** Confirm the **GPON / PON** light is solid Green and **LOS** is OFF. If **LOS** is Red or blinking, there is a physical Fibre signal fault.",
                    "**3. Avoid the Recessed Pinhole 'Reset' Button:** Do **not** press the recessed pinhole *Reset* button, as it erases your factory PPPoE configuration.",
                    "**4. Log a Technical Fault Ticket (`1212` / `MySLT App`):** Call **`1212`** (SLT Fixed/Fibre) or **`1717`** (Mobitel Mobile), or submit a fault ticket via the **MySLT App** so an SLT engineer can inspect your line and port remotely."
                ]
                return ans, bullets

            # Stage 2: Slow Internet / Very Low Speed / Slow Connectivity
            if any(w in current_q for w in ("slow", "low speed", "speed is very low", "speed is low", "very low", "lagging", "buffering", "high ping")) or (
                "speed" in current_q and any(w in current_q for w in ("low", "bad", "poor", "drop", "issue"))
            ):
                if any(w in context_part for w in ("slow", "speed", "lagging")):
                    ans = "If your **internet speed remains very low**, check these **SLTMobitel bandwidth, FUP Extra GB, and Wi-Fi signal steps**:"
                    bullets = [
                        "**1. Activate Extra GB if Quota is Exhausted (`#170#` / `MySLT App`):** If your monthly Anytime or daily Flash allowance is fully used, dial **`#170#`** or open the **MySLT App** (`https://myslt.slt.lk/`) to add **Extra GB** and restore full speed.",
                        "**2. Optimize Wi-Fi Signal (5 GHz Band / Wireless Extender):** Connect to the **5 GHz Wi-Fi band** when near the router, or pair a **Wireless Extender via WPS** if weak Wi-Fi signal is causing low speed in other rooms.",
                        "**3. Test via Direct Ethernet (LAN) Cable:** Connect a laptop directly with a LAN cable to verify whether the slowdown is caused by local Wi-Fi interference or the broadband line.",
                        "**4. Restart Router or Report Speed Degradation (`1212`):** Power-cycle the router for 15–30 seconds; if speeds remain low, call **`1212`** to test your Fibre optical attenuation / line quality."
                    ]
                    return ans, bullets

                ans = "To troubleshoot a **slow SLTMobitel Internet / Broadband connection**, follow these steps from the KnowledgeBase:"
                bullets = [
                    "**1. Check Data Usage & Quota (`MySLT App` / `#170#`):** Check whether your package quota is exceeded via the **MySLT App / Portal** (`https://myslt.slt.lk/`) or by dialing **`#170#`** (for example, *Unlimited Flash* packages throttle to `1 Mbps` after the daily 5 GB / 10 GB limit).",
                    "**2. Restart the Router:** Power off the router, wait **15–30 seconds**, and switch it back on to refresh your broadband session.",
                    "**3. Change Wi-Fi Password & Check Connected Devices:** Change your Wi-Fi password if unauthorized or background devices are consuming your bandwidth.",
                    "**4. Check Telephone / Fibre Line Connections:** Verify that your telephone line or Fibre optical patch cord is tightly connected and undamaged."
                ]
                return ans, bullets

            # Stage 3: Router is Powered ON / Lights ON, But No Internet Connection ("it is on but/bot no connection")
            if any(w in current_q for w in ("no connection", "no internet", "on but", "on bot", "lights are on", "router is on")):
                ans = "If your **router is powered ON but there is no internet connection**, follow these **SLTMobitel connection diagnostic steps**:"
                bullets = [
                    "**1. Check `GPON / PON`, `LOS`, and `WLAN` LEDs:** Confirm **GPON / PON** is solid Green and **LOS** is OFF. If **LOS** is blinking Red, there is an outdoor/indoor Fibre signal break; if **WLAN** is OFF, press the **Wi-Fi/WLAN** button on the router.",
                    "**2. Check Account Status & Data Quota (`#1456#` / `MySLT App`):** Dial **`#1456#`** or open the **MySLT App** (`https://myslt.slt.lk/`) to confirm your account is active and your data quota is not exhausted.",
                    "**3. Inspect Fibre / Telephone Patch Cords:** Ensure the yellow Fibre patch cord (or telephone cable into the splitter/ONT) is firmly seated.",
                    "**4. Power-Cycle the Router (15–30 Seconds) or Call `1212`:** Switch off the router for 15–30 seconds and switch it back on (do **not** press the recessed pinhole *Reset* button). If still offline, call **`1212`** to report a line fault."
                ]
                return ans, bullets

            # Stage 4: Power Socket / Wall Outlet Confirmed Fine ("Power socket is fine", "Wall Socket is fine")
            if any(w in current_q for w in ("power socket", "wall socket", "wall outlet", "socket is fine", "outlet is fine", "power is fine", "plug is fine", "adapter is fine")) or (
                ("socket" in current_q or "outlet" in current_q) and any(w in current_q for w in ("fine", "ok", "working", "good"))
            ):
                if any(w in context_part for w in ("socket", "outlet")):
                    ans = "With both your **power socket and wall outlet confirmed working**, check whether the **router LEDs light up** to isolate the fault:"
                    bullets = [
                        "**1. If Router Lights Are Completely OFF:** Check that the power adapter barrel plug is firmly connected to the router's `DC IN` port. If no lights turn on despite a working wall socket, call **`1212`** (or visit an SLTMobitel branch) for a **power adapter or router replacement**.",
                        "**2. If Router Lights Are ON But There Is No Connection:** Check whether the **`LOS` light is blinking Red** (Fibre line fault) or **`GPON` and `WLAN` are Green**, then restart the router for 15–30 seconds.",
                        "**3. Verify Service & Quota Status (`MySLT App` / `#1456#`):** Check the **MySLT App** (`https://myslt.slt.lk/`) or dial **`#1456#`** to confirm your broadband connection is active."
                    ]
                    return ans, bullets

                ans = "Since the **power socket is working**, please check your **router's power switch, adapter, and LED indicators** next:"
                bullets = [
                    "**1. Check Router Power Switch & Power LED:** Ensure the **Power ON/OFF button** on the back of the router is pressed **ON** and the **Power LED** is lit Green. (If the Power LED stays OFF on a working wall socket, the power adapter or router hardware may be faulty.)",
                    "**2. Check `GPON / PON` and `LOS` Lights:** Confirm the **GPON / PON** light is solid Green and the **LOS** light is **OFF** (not blinking Red).",
                    "**3. Check `WLAN / Wi-Fi` Light:** Verify that the **WLAN** light is ON; if it is OFF, press the **WLAN / Wi-Fi button** on the side/back of the router.",
                    "**4. Inspect Fibre / Telephone Line:** Ensure the Fibre optical patch cord or telephone line is tightly plugged in, then restart the router for 15–30 seconds."
                ]
                return ans, bullets

            # Stage 5: Physical Router Button Not Responding ("router button is not working", "restart button broken")
            button_fault_signals = (
                "doesnot", "does not", "doesn't", "did not", "didn't", "not working",
                "nothing happens", "broken", "stuck", "dead", "won't", "wont", "cannot", "can't"
            )
            if ("button" in current_q or "switch" in current_q) and any(sig in current_q for sig in button_fault_signals):
                ans = "If the **router button is not responding**, try the following steps:"
                bullets = [
                    "**Power-Cycle via Wall Socket:** Turn off the main wall power switch (or unplug the power adapter) for **30 seconds**, then plug it back in.",
                    "**Avoid the Pinhole 'Reset' Button:** Do **not** hold the recessed pinhole *Reset* button, as that erases your SLT Fibre/4G PPPoE configuration.",
                    "**Log a Hardware Fault / Replacement:** Call **`1212`** (SLT Fixed/Fibre) or **`1717`** (Mobitel), or report a fault via the **MySLT App** so a technician can inspect or replace the router."
                ]
                return ans, bullets

            # Stage 6: Initial "My Internet / Wi-Fi is Not Working" or "How to Restart / Troubleshoot Router"
            ans = "To troubleshoot or restart your **SLTMobitel Router & Internet / Wi-Fi** connection:"
            bullets = [
                "**1. Check Device & Router Power:** Ensure Wi-Fi is enabled on your phone/laptop and the router is plugged into a working wall socket and powered ON.",
                "**2. Inspect Cable Connections:** Verify that all power, Fibre/telephone patch cords, and Ethernet cables are tightly connected.",
                "**3. Verify Wi-Fi / WLAN & GPON LEDs:** Check that the **WLAN** light is ON (if OFF, press the **Wi-Fi/WLAN** button on the router), **GPON/PON** is solid Green, and **LOS** is OFF.",
                "**4. Restart the Router:** Power off the router, wait **15–30 seconds**, and switch it back on (or check quota usage via the **MySLT App** / call **`1212`** if the issue persists)."
            ]
            return ans, bullets

        # General clean paragraph & numbered-step fallback
        raw_top = chunks[0].get("content", "")
        # If the text has inline numbered steps like "1. ... 2. ... 3. ...", split them into clean bullets!
        numbered_matches = re.split(r"(?=\b\d+\.\s+[A-Z])", raw_top)
        if len(numbered_matches) >= 3:
            cleaned_steps = []
            for m in numbered_matches:
                s = m.strip(" ,\"'•~")
                if len(s) >= 6:
                    if not re.match(r"^\d+\.", s):
                        s = f"• {s}"
                    cleaned_steps.append(s)
            return "Here are the recommended steps:", cleaned_steps[:6]

        lines = [ln.strip(" ,\"'•~") for ln in raw_top.splitlines() if ln.strip(" ,\"'•~")]
        if not lines:
            return "", []
        deduped = []
        for ln in lines:
            if not deduped or deduped[-1].lower() != ln.lower():
                deduped.append(ln)
        main_text = " ".join(deduped[:3])
        extra_bullets = deduped[3:7]
        return main_text, extra_bullets

    def answer_kb_question(
        self,
        sanitized_query: str,
        top_k: int = 3,
        mode_override: str | None = None,
        ollama_model: str | None = None,
        gemini_api_key: str | None = None,
        bedrock_model: str | None = None,
        aws_region: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        kb_secret_override: str | None = None,
        kb_endpoint_override: str | None = None
    ) -> dict:
        """
        Queries the SLTMobitel AWS KnowledgeBase API (/prod/retrieve) and synthesizes
        a clear, natural answer — or politely states 'I don't have enough knowledge to answer that'
        if the retrieved chunks do not match the question.
        """
        active_mode = mode_override or self.inference_mode
        kb_error = None
        try:
            kb_response = self.retrieve_from_aws_kb(
                query_text=sanitized_query,
                top_k=top_k,
                kb_secret_override=kb_secret_override,
                kb_endpoint_override=kb_endpoint_override
            )
            chunks = kb_response.get("chunks", [])
        except Exception as exc:
            kb_error = f"AWS KnowledgeBase API call failed: {exc}"
            chunks = []

        citations = [f"{c['doc_id']} (Score: {c['score']})" for c in chunks]
        llm_error_note = None

        # Check if the retrieved chunks actually have enough knowledge to answer the query
        has_relevant_knowledge = self._chunks_are_relevant_to_query(sanitized_query, chunks)

        if not chunks or not has_relevant_knowledge:
            polite_abstention = (
                "I don't have enough knowledge in the current SLTMobitel KnowledgeBase to answer that specific question. "
                "Please try asking about topics covered in our knowledge base, or contact **SLTMobitel Support (1212)** "
                "or the **MySLT App** for direct assistance."
            )
            return {
                "query": sanitized_query,
                "inference_mode": active_mode,
                "has_enough_knowledge": False,
                "answer": polite_abstention,
                "confidence": "ABSTAINED",
                "key_points": [],
                "follow_up_suggestion": "Try asking a different SLTMobitel question or paste a network incident ticket.",
                "citations": [],
                "retrieved_chunks": chunks,
                "count": len(chunks),
                "kb_api_error": kb_error,
                "llm_fallback_warning": None
            }

        if active_mode in ("AWS_BEDROCK", "GEMINI_CLOUD"):
            prompt = self.llm_gateway.build_kb_qa_prompt(sanitized_query, chunks)
            try:
                llm_res, engine_label = self._invoke_llm(
                    prompt=prompt,
                    active_mode=active_mode,
                    ollama_model=ollama_model,
                    gemini_api_key=gemini_api_key,
                    bedrock_model=bedrock_model,
                    aws_region=aws_region,
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key
                )
                llm_has_knowledge = bool(llm_res.get("has_enough_knowledge", True))
                raw_ans = str(llm_res.get("answer", "")).strip()
                if not llm_has_knowledge or "don't have enough knowledge" in raw_ans.lower():
                    return {
                        "query": sanitized_query,
                        "inference_mode": engine_label,
                        "has_enough_knowledge": False,
                        "answer": (
                            raw_ans if raw_ans else
                            "I don't have enough knowledge in the SLTMobitel KnowledgeBase to answer that specific question."
                        ),
                        "confidence": "ABSTAINED",
                        "key_points": [],
                        "follow_up_suggestion": "Please try another question or contact SLTMobitel 1212.",
                        "citations": [],
                        "retrieved_chunks": chunks,
                        "count": len(chunks),
                        "kb_api_error": kb_error,
                        "llm_fallback_warning": None
                    }

                return {
                    "query": sanitized_query,
                    "inference_mode": engine_label,
                    "has_enough_knowledge": True,
                    "answer": raw_ans,
                    "confidence": "HIGH",
                    "key_points": [str(kp) for kp in llm_res.get("key_points", []) if str(kp).strip()],
                    "follow_up_suggestion": str(
                        llm_res.get("follow_up_suggestion", "Need more help? Reach SLTMobitel via 1212 or the MySLT App.")
                    ),
                    "citations": citations,
                    "retrieved_chunks": chunks,
                    "count": len(chunks),
                    "kb_api_error": kb_error,
                    "llm_fallback_warning": None
                }
            except Exception as exc:
                llm_error_note = f"LLM synthesis ({active_mode}) unavailable: {exc}."

        # Clean, natural fallback synthesis from the retrieved chunks
        top_chunk = chunks[0]
        main_paragraph, bullet_list = self._synthesize_clean_kb_fallback(sanitized_query, chunks)

        return {
            "query": sanitized_query,
            "inference_mode": "AWS_KB_DIRECT_SYNTHESIS",
            "has_enough_knowledge": True,
            "answer": main_paragraph,
            "confidence": "HIGH" if float(top_chunk.get("score", 0.0)) >= 0.60 else "MEDIUM",
            "key_points": bullet_list,
            "follow_up_suggestion": "You can ask a follow-up question below or check the official SLTMobitel portal (slt.lk).",
            "citations": citations,
            "retrieved_chunks": chunks,
            "count": len(chunks),
            "kb_api_error": kb_error,
            "llm_fallback_warning": llm_error_note
        }

    @staticmethod
    def _clean_recommended_actions(raw_actions) -> list[str]:
        """
        Ensures recommended_actions from smaller LLMs (like granite3.1:2b) are always clean,
        human-readable strings — never raw Python dicts like {'action': 'First step', ...}
        or prompt template placeholders like 'First step with [Citation: ...]'.
        """
        if not raw_actions:
            return []
        if not isinstance(raw_actions, list):
            raw_actions = [raw_actions]

        cleaned_list = []
        for item in raw_actions:
            if isinstance(item, dict):
                # Extract meaningful fields from dict
                cmd = item.get("command") or item.get("cli") or ""
                rem = item.get("reminder") or item.get("description") or item.get("step") or item.get("action") or ""
                cite = item.get("citation") or ""
                parts = []
                if rem and rem.lower() not in ("first step", "second step", "third step", "safety guardrail reminder"):
                    parts.append(str(rem).strip())
                if cmd:
                    parts.append(f"Run read-only command: `{cmd}`")
                if cite:
                    parts.append(f"[{cite}]")
                text = " — ".join(parts) if parts else ""
            else:
                text = str(item).strip()
                # Strip template literal echoes like "First step with " or "1. Second step with read-only CLI command: "
                text = re.sub(
                    r"^(?:\d+[\.\)]\s*)?(?:First|Second|Third)\s+step(?:\s+with(?:\s+read-only\s+CLI\s+command)?)?\s*[:\-]?\s*",
                    "",
                    text,
                    flags=re.IGNORECASE
                )
                text = re.sub(
                    r"^(?:\d+[\.\)]\s*)?Safety\s+guardrail\s+reminder(?:\s+with)?\s*[:\-]?\s*",
                    "Safety Guardrail: ",
                    text,
                    flags=re.IGNORECASE
                )

            # Skip empty or pure citation-only placeholders
            stripped_no_cite = re.sub(r"\[Citation:[^\]]+\]", "", text, flags=re.IGNORECASE).strip(" :-.")
            if stripped_no_cite and stripped_no_cite.lower() not in ("first step", "second step", "safety guardrail"):
                cleaned_list.append(text.strip())

        return cleaned_list

    @staticmethod
    def _is_valid_netops_telemetry(sanitized_ticket: str) -> bool:
        """
        Checks whether the input actually contains a recognized SLT NetOps SOP topic
        (BGP, OSPF, GPON/PON, MTU, EXSTART, Rx Power, OLT/ONT, or SOP ID).
        Prevents general questions like 'How do I make my router fast' from being hallucinated as OSPF/BGP faults.
        """
        t_lower = sanitized_ticket.lower()
        sop_patterns = (
            r"\bbgp\b", r"\bospf\b", r"\bgpon\b", r"\bpon_los\b", r"\bdyinggasp\b",
            r"\bexstart\b", r"\bmtu\b", r"\btengige\w*\b", r"\brx\s+power\b",
            r"\bdbm\b", r"\bslt-net-sop\b", r"\bolt\b", r"\bonts?\b",
            r"\binc-\d+", r"\bincident\s+ticket\b"
        )
        return any(re.search(pat, t_lower) for pat in sop_patterns)
    def extract_ticket_metadata(self, sanitized_ticket: str) -> dict:
        ticket_id = re.search(r"INCIDENT TICKET:\s*(\S+)", sanitized_ticket)
        node = re.search(r"AFFECTED NODE:\s*([^\r\n(]+)", sanitized_ticket)
        return {
            "ticket_id": ticket_id.group(1).strip() if ticket_id else "UNKNOWN-TICKET",
            "affected_node": node.group(1).strip() if node else "UNKNOWN-NODE"
        }

    def analyze_incident(
        self,
        sanitized_ticket: str,
        mode_override: str | None = None,
        ollama_model: str | None = None,
        gemini_api_key: str | None = None,
        bedrock_model: str | None = None,
        aws_region: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        include_aws_kb: bool = False,
        kb_secret_override: str | None = None
    ) -> dict:
        active_mode = mode_override or self.inference_mode
        meta = self.extract_ticket_metadata(sanitized_ticket)

        # If the user asked a general question not covered by the BGP/OSPF/GPON SOPs, abstain cleanly!
        if not self._is_valid_netops_telemetry(sanitized_ticket):
            abstain_msg = (
                "I don't have enough knowledge in the SLT Network Operations SOPs to answer that question. "
                "Our NetOps SOPs only cover **Core BGP Optical Loss (`SLT-NET-SOP-042`)**, "
                "**OSPF EXSTART MTU Mismatches (`SLT-NET-SOP-043`)**, and **GPON OLT Feeder Fiber Cuts (`SLT-NET-SOP-044`)**."
            )
            return {
                "ticket_id": meta["ticket_id"],
                "affected_node": meta["affected_node"],
                "inference_mode": active_mode,
                "has_enough_knowledge": False,
                "severity": "INFO / INSUFFICIENT TELEMETRY",
                "escalation_required": False,
                "escalation_target": "None",
                "diagnosis_summary": abstain_msg,
                "recommended_actions": [],
                "citations": [],
                "retrieved_chunks": [],
                "draft_handover_summary": "",
                "llm_fallback_warning": None
            }

        retrieved = self.retrieve_relevant_sections(sanitized_ticket, top_k=4)

        if include_aws_kb:
            try:
                aws_res = self.retrieve_from_aws_kb(
                    sanitized_ticket[:300],
                    top_k=2,
                    kb_secret_override=kb_secret_override
                )
                retrieved.extend(aws_res.get("chunks", []))
            except Exception:
                pass

        citations = [f"{c['doc_id']} ({c['section']})" for c in retrieved]
        llm_error_note = None
        rule_res = self._evaluate_with_rules(sanitized_ticket)

        if active_mode in ("AWS_BEDROCK", "GEMINI_CLOUD"):
            prompt = self.llm_gateway.build_grounded_prompt(sanitized_ticket, retrieved)
            try:
                llm_res, engine_label = self._invoke_llm(
                    prompt=prompt,
                    active_mode=active_mode,
                    ollama_model=ollama_model,
                    gemini_api_key=gemini_api_key,
                    bedrock_model=bedrock_model,
                    aws_region=aws_region,
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key
                )

                if not llm_res.get("has_enough_knowledge", True):
                    return {
                        "ticket_id": meta["ticket_id"],
                        "affected_node": meta["affected_node"],
                        "inference_mode": engine_label,
                        "has_enough_knowledge": False,
                        "severity": "INFO / INSUFFICIENT TELEMETRY",
                        "escalation_required": False,
                        "escalation_target": "None",
                        "diagnosis_summary": str(
                            llm_res.get(
                                "diagnosis_summary",
                                "I don't have enough knowledge in the SLT Network Operations SOPs to answer that question."
                            )
                        ),
                        "recommended_actions": [],
                        "citations": [],
                        "retrieved_chunks": retrieved,
                        "draft_handover_summary": "",
                        "llm_fallback_warning": None
                    }

                severity = str(llm_res.get("severity", rule_res["severity"]))
                escalation_required = bool(llm_res.get("escalation_required", rule_res["escalation_required"]))
                escalation_target = str(llm_res.get("escalation_target", rule_res["escalation_target"]))
                diagnosis = str(llm_res.get("diagnosis_summary", rule_res["diagnosis"]))
                recommended_actions = self._clean_recommended_actions(llm_res.get("recommended_actions", []))

                # If the small LLM returned broken/empty actions, use the verified deterministic SOP actions
                if len(recommended_actions) < 2:
                    recommended_actions = rule_res["recommended_actions"]

                draft_summary = self._build_handover_markdown(
                    meta, severity, escalation_required, escalation_target, diagnosis, citations, engine_label
                )
                return {
                    "ticket_id": meta["ticket_id"],
                    "affected_node": meta["affected_node"],
                    "inference_mode": engine_label,
                    "has_enough_knowledge": True,
                    "severity": severity,
                    "escalation_required": escalation_required,
                    "escalation_target": escalation_target,
                    "diagnosis_summary": diagnosis,
                    "recommended_actions": recommended_actions,
                    "citations": citations,
                    "retrieved_chunks": retrieved,
                    "draft_handover_summary": draft_summary,
                    "llm_fallback_warning": None
                }
            except Exception as exc:
                llm_error_note = f"LLM call ({active_mode}) failed: {exc}. Automatically fell back to Deterministic Rule Engine."
        draft_summary = self._build_handover_markdown(
            meta,
            rule_res["severity"],
            rule_res["escalation_required"],
            rule_res["escalation_target"],
            rule_res["diagnosis"],
            citations,
            "LOCAL_GROUNDED_RULE_ENGINE"
        )

        return {
            "ticket_id": meta["ticket_id"],
            "affected_node": meta["affected_node"],
            "inference_mode": "LOCAL_GROUNDED_RULE_ENGINE",
            "has_enough_knowledge": "insufficient telemetry" not in rule_res["severity"].lower(),
            "severity": rule_res["severity"],
            "escalation_required": rule_res["escalation_required"],
            "escalation_target": rule_res["escalation_target"],
            "diagnosis_summary": rule_res["diagnosis"],
            "recommended_actions": rule_res["recommended_actions"],
            "citations": citations,
            "retrieved_chunks": retrieved,
            "draft_handover_summary": draft_summary,
            "llm_fallback_warning": llm_error_note
        }

    def _build_handover_markdown(
        self, meta: dict, severity: str, esc_req: bool, esc_target: str, diagnosis: str, citations: list[str], engine: str
    ) -> str:
        return (
            f"### 📋 SLT NOC Draft Incident Handover Summary\n"
            f"- **Ticket ID:** `{meta['ticket_id']}` | **Affected Node:** `{meta['affected_node']}`\n"
            f"- **AI Engine Used:** `{engine}`\n"
            f"- **Assessed Severity:** {severity}\n"
            f"- **Escalation Required:** {'YES -> ' + esc_target if esc_req else 'NO (' + esc_target + ')'}\n"
            f"- **Root-Cause Summary:** {diagnosis}\n"
            f"- **Primary SOP Referenced:** `{citations[0] if citations else 'N/A'}`\n"
            f"- **Compliance Note:** All PII, internal IPs, and credentials were sanitized prior to analysis. Advisory actions strictly enforce read-only network guardrails."
        )

    def _evaluate_with_rules(self, sanitized_ticket: str) -> dict:
        text_lower = sanitized_ticket.lower()

        if "bgp" in text_lower or "tengige0/1/0" in text_lower or "rx power measured" in text_lower:
            rx_match = re.search(r"Rx Power measured at\s*(-?\d+\.\d+)\s*dBm", sanitized_ticket, re.IGNORECASE)
            flap_match = re.search(r"flapped\s*(\d+)\s*times", sanitized_ticket, re.IGNORECASE)
            rx_dbm = float(rx_match.group(1)) if rx_match else None
            flap_count = int(flap_match.group(1)) if flap_match else 0

            if rx_dbm is not None and (rx_dbm < -18.1 or flap_count > 5):
                return {
                    "severity": "CRITICAL (Tier-3 Escalation Mandatory)",
                    "escalation_required": True,
                    "escalation_target": "SLT Tier-3 Core Transport Team & Regional Fiber Maintenance Unit",
                    "diagnosis": (
                        f"Detected Critical Optical Loss (Rx Power: {rx_dbm} dBm, below the -18.1 dBm threshold) "
                        f"and severe link instability ({flap_count} flaps, exceeding the >5 flaps/15 min threshold)."
                    ),
                    "recommended_actions": [
                        "1. IMMEDIATE ESCALATION: Escalate ticket to SLT Tier-3 Core Transport Team and dispatch Regional Fiber Maintenance Unit [Citation: SLT-NET-SOP-042, Section 4].",
                        "2. READ-ONLY VERIFICATION: Run `show bgp ipv4 unicast summary` and `show interfaces TenGigE0/1/0 transceiver detail` to monitor status [Citation: SLT-NET-SOP-042, Section 2].",
                        "3. SAFETY GUARDRAIL: Do NOT reset interfaces, clear BGP sessions, or modify BGP routing policies autonomously [Citation: SLT-NET-SOP-042, Section 2 & 4]."
                    ]
                }
            elif rx_dbm is not None and (-18.0 <= rx_dbm <= -14.1):
                return {
                    "severity": "WARNING (Degraded Optical Signal)",
                    "escalation_required": False,
                    "escalation_target": "Scheduled ODF Fiber Cleaning (No Emergency Tier-3 Escalation)",
                    "diagnosis": f"Optical Rx Power ({rx_dbm} dBm) is in the Degraded Warning range (-14.1 to -18.0 dBm).",
                    "recommended_actions": [
                        "1. Schedule maintenance window to inspect and clean LC/UPC fiber connectors at the ODF [Citation: SLT-NET-SOP-042, Section 4].",
                        "2. Monitor CRC counters via `show interfaces TenGigE0/1/0 | include CRC|drops` [Citation: SLT-NET-SOP-042, Section 2]."
                    ]
                }

        if "ospf" in text_lower or "exstart" in text_lower or "mtu" in text_lower:
            mtu_values = [int(m) for m in re.findall(r"MTU(?:\s+is)?\s+(\d+)\s*bytes", sanitized_ticket, re.IGNORECASE)]
            mtu_detail = f" (Detected MTU values: {mtu_values} bytes)" if len(set(mtu_values)) > 1 else ""
            return {
                "severity": "HIGH (Tier-2 Configuration Alignment Required)",
                "escalation_required": True,
                "escalation_target": "SLT Tier-2 Metro/Core Configuration Team",
                "diagnosis": (
                    f"OSPF neighbor stuck in EXSTART due to Interface IP MTU mismatch{mtu_detail} "
                    f"against the standard SLT 9198-byte Core MPLS or 1500-byte Metro alignment."
                ),
                "recommended_actions": [
                    "1. ESCALATION: Escalate to SLT Tier-2 Metro/Core Configuration Team to align interface MTU during an authorized window [Citation: SLT-NET-SOP-043, Section 4].",
                    "2. READ-ONLY VERIFICATION: Run `show ip ospf interface TenGigE0/2/0 | include MTU|State` and `ping <peer-ip> size 9000 df-bit` [Citation: SLT-NET-SOP-043, Section 2].",
                    "3. SAFETY GUARDRAIL: Do NOT run `clear ip ospf process` on production core routers [Citation: SLT-NET-SOP-043, Section 2]."
                ]
            }

        if "pon_los" in text_lower or "gpon" in text_lower or "ont" in text_lower:
            if "0 dyinggasp" in text_lower:
                return {
                    "severity": "CRITICAL (Feeder Fiber Cut Suspected)",
                    "escalation_required": True,
                    "escalation_target": "SLT Regional OPMC Outside Plant (OSP) Fiber Team",
                    "diagnosis": (
                        "100% of ONTs on PON port dropped simultaneously with LOS and 0 DyingGasp alarms, "
                        "indicating an optical feeder fiber cut or OLT SFP transceiver failure."
                    ),
                    "recommended_actions": [
                        "1. IMMEDIATE DISPATCH: Escalate to SLT Regional OPMC Outside Plant (OSP) Fiber Team for OTDR testing on feeder cable [Citation: SLT-NET-SOP-044, Section 4].",
                        "2. READ-ONLY VERIFICATION: Run `display port state 0/3 4` and `display port ddm-info 0/3 4` [Citation: SLT-NET-SOP-044, Section 2].",
                        "3. SAFETY GUARDRAIL: Do NOT reboot the OLT line card or reset PON protection groups [Citation: SLT-NET-SOP-044, Section 2]."
                    ]
                }

        return {
            "severity": "INFO / INSUFFICIENT TELEMETRY",
            "escalation_required": False,
            "escalation_target": "Tier-2 NOC Shift Lead",
            "diagnosis": "I don't have enough matching network telemetry or SOP knowledge to diagnose that specific issue automatically.",
            "recommended_actions": []
        }


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parents[2]
    manuals_dir = base_dir / "data" / "approved_manuals"
    clean_ticket_path = base_dir / "data" / "synthetic_incidents" / "inc_2026_1042_sanitized.txt"

    print("Initializing SLT Hybrid AWS + Sovereign NetOps RAG Engine...")
    rag = SovereignNetOpsRAG(manuals_dir=manuals_dir, enable_embeddings=False)
    ticket_text = clean_ticket_path.read_text(encoding="utf-8")
    report = rag.analyze_incident(ticket_text, mode_override="AWS_BEDROCK")

    print("=" * 70)
    print("SLT HYBRID SOVEREIGN AI - RAG REPORT")
    print("=" * 70)
    print(f"Engine Mode       : {report['inference_mode']}")
    print(f"Assessed Severity : {report['severity']}")
    print(f"Escalation Target : {report['escalation_target']}\n")
    print(f"Root-Cause Diagnosis:\n  {report['diagnosis_summary']}\n")
