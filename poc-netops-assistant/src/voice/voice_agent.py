import os
import re
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


class SLTMobitelVoiceAgent:
    """
    SLTMobitel Voice & Call Center IVR Agent (1212 / 1717 Telephony & Web Voice Adapter).
    Capabilities:
    1. Converts Markdown RAG / NetOps answers into natural spoken scripts for voice callers
       (pronouncing USSD codes like `#1456#` as 'hash 1 4 5 6 hash', stripping URLs/markdown symbols).
    2. Generates W3C SSML (`<speak>...</speak>`) for Amazon Connect / Amazon Polly Neural TTS.
    3. Synthesizes MP3 audio via Amazon Polly (`boto3.client('polly')`, Neural voice `Kajal` / `Joanna`)
       when AWS credentials are provided.
    4. Handles Amazon Connect Contact Flow Lambda events (`POST /voice`).
    """

    USSD_PRONUNCIATIONS = {
        "#1456#": "hash 1 4 5 6 hash",
        "#888#": "hash 8 8 8 hash",
        "#170#": "hash 1 7 0 hash",
        "#147#": "hash 1 4 7 hash",
        "#999#": "hash 9 9 9 hash",
        "#111#": "hash 1 1 1 hash",
        "#9900#": "hash 9 9 0 0 hash",
        "1212": "12 12",
        "1717": "17 17",
        "1456": "14 56"
    }

    def __init__(self, default_voice_id: str | None = None, aws_region: str | None = None):
        self.voice_id = default_voice_id or os.getenv("AWS_POLLY_VOICE_ID", "Kajal")
        self.aws_region = aws_region or os.getenv("AWS_REGION", "us-east-1")

    @classmethod
    def format_for_speech(cls, answer_markdown: str, key_points: list[str] | None = None, max_sentences: int = 5) -> str:
        """
        Transforms a visual Markdown chat response into a crisp, natural spoken script
        suitable for a phone call or voice assistant.
        """
        parts = [answer_markdown.strip()] if answer_markdown else []
        if key_points:
            parts.extend(key_points[:4])
        combined = " ".join(parts)

        # 1. Replace USSD shortcodes with natural spoken equivalents before stripping symbols
        for code, spoken in cls.USSD_PRONUNCIATIONS.items():
            combined = combined.replace(code, spoken)

        # 2. Replace generic #NNN# patterns if any remain
        combined = re.sub(
            r"#(\d+)#",
            lambda m: "hash " + " ".join(list(m.group(1))) + " hash",
            combined
        )

        # 3. Replace URLs with natural spoken domain references
        combined = re.sub(r"https?://myslt\.slt\.lk/?", "the My S L T portal", combined)
        combined = re.sub(r"https?://(?:www\.)?slt\.lk[^\s)]*", "s l t dot l k", combined)
        combined = re.sub(r"https?://[^\s)]+", "our official website", combined)

        # 4. Strip [Citation: ...] blocks so the voice agent doesn't read SOP citation IDs aloud
        combined = re.sub(r"\[Citation:[^\]]+\]", "", combined, flags=re.IGNORECASE)

        # 5. Strip Markdown formatting (**bold**, `code`, bullets, arrows, vertical bars)
        combined = re.sub(r"[*_`~]+", "", combined)
        combined = re.sub(r"\s*\|\s*", ". ", combined)
        combined = re.sub(r"\s*—\s*", ", ", combined)
        combined = re.sub(r"\s*->\s*|\s*→\s*", " then ", combined)
        combined = re.sub(r"\bRs\.\s*", "Rupees ", combined)

        # 6. Clean up whitespace and limit to a concise spoken length for voice callers
        combined = re.sub(r"\s+", " ", combined).strip()
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", combined) if s.strip()]
        spoken_text = " ".join(sentences[:max_sentences])
        return spoken_text

    @classmethod
    def build_ssml(cls, spoken_text: str) -> str:
        """
        Wraps the spoken script in W3C / Amazon Connect / Amazon Polly SSML tags
        with natural prosody and pauses between sentences.
        """
        escaped = (
            spoken_text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        # Add brief 250ms pauses after sentences for natural telephony pacing
        with_pauses = re.sub(r"([.!?])\s+", r'\1 <break time="250ms"/> ', escaped)
        return f'<speak><prosody rate="98%">{with_pauses}</prosody></speak>'

    def synthesize_polly_audio(
        self,
        spoken_text: str,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None
    ) -> bytes | None:
        """
        Synthesizes MP3 speech audio via Amazon Polly (`boto3`) when AWS credentials are configured.
        Returns None if AWS credentials are not set (allowing the UI to use Browser Web Speech API).
        """
        ak = (aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID", "")).strip()
        sk = (aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY", "")).strip()
        if not ak or not sk or "PASTE_YOUR" in ak or "INSERT_" in ak:
            return None

        try:
            import boto3
            polly = boto3.client(
                "polly",
                region_name=self.aws_region,
                aws_access_key_id=ak,
                aws_secret_access_key=sk
            )
            ssml = self.build_ssml(spoken_text)
            resp = polly.synthesize_speech(
                Text=ssml,
                TextType="ssml",
                OutputFormat="mp3",
                VoiceId=self.voice_id,
                Engine="neural"
            )
            stream = resp.get("AudioStream")
            if stream:
                return stream.read()
        except Exception:
            return None
        return None

    def process_voice_turn(self, agent, transcript: str, route_mode: str = "AUTO") -> dict:
        """
        Runs a voice transcript through the SLTMobitelUnifiedAgent and returns both
        the visual response and the telephony/voice payload (spoken script, SSML, and IVR routing).
        """
        t0 = time.perf_counter()
        turn_res = agent.run_agent(
            user_input=transcript,
            route_mode=route_mode
        )
        spoken_script = self.format_for_speech(
            turn_res.get("answer_markdown", ""),
            turn_res.get("key_points", [])
        )
        ssml_script = self.build_ssml(spoken_script)

        # Determine Amazon Connect IVR queue transfer target if escalation or out-of-scope
        if turn_res.get("escalation_required"):
            ivr_queue = "SLT_NOC_TIER3_EMERGENCY_QUEUE"
        elif not turn_res.get("has_enough_knowledge", True):
            ivr_queue = "SLT_1212_HUMAN_AGENT_QUEUE"
        else:
            ivr_queue = "SELF_SERVICE_COMPLETED"

        return {
            "transcript": transcript,
            "spoken_response": spoken_script,
            "ssml_response": ssml_script,
            "ivr_queue_action": ivr_queue,
            "intent_route": turn_res["intent_route"],
            "mcp_tool_called": turn_res.get("mcp_tool_called"),
            "has_enough_knowledge": turn_res["has_enough_knowledge"],
            "escalation_required": turn_res["escalation_required"],
            "redactions_applied": turn_res["redactions_applied"],
            "agent_response": turn_res,
            "voice_latency_ms": round((time.perf_counter() - t0) * 1000, 1)
        }
