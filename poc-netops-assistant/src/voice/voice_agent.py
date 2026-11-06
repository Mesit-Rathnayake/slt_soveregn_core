import hashlib
import io
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
    SLTMobitel Full 2-Way Voice & Call Center IVR Agent (1212 / 1717 Telephony & Web Voice AI).
    Capabilities:
    1. Speech-to-Text (STT / Voice Input): Transcribes user microphone WAV audio (`st.audio_input`)
       into text via `SpeechRecognition` (or Amazon Transcribe).
    2. Spoken Script Normalization: Converts Markdown RAG / NetOps answers into natural spoken scripts
       (pronouncing USSD codes like `#1456#` as 'hash 1 4 5 6 hash', stripping URLs/markdown symbols).
    3. W3C SSML Generation: Produces `<speak>...</speak>` SSML for Amazon Connect / Amazon Polly Neural TTS.
    4. Text-to-Speech (TTS / Voice Output): Synthesizes real MP3 audio bytes via Amazon Polly (`Kajal` Neural)
       with automatic fallback to `gTTS` so the assistant speaks back out loud in every browser.
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
        self._tts_cache: dict[str, bytes] = {}

    @staticmethod
    def transcribe_audio_bytes(wav_bytes: bytes, language: str = "en-LK") -> dict:
        """
        Transcribes WAV audio recorded from the user's microphone (`st.audio_input`) into text.
        Uses SpeechRecognition (Google Web Speech API) with fallback to en-US.
        """
        if not wav_bytes:
            return {"success": False, "transcript": "", "error": "Empty audio buffer."}

        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
                audio_data = recognizer.record(source)

            try:
                transcript = recognizer.recognize_google(audio_data, language=language)
            except Exception:
                transcript = recognizer.recognize_google(audio_data, language="en-US")

            return {
                "success": True,
                "transcript": transcript.strip(),
                "error": None
            }
        except Exception as exc:
            return {
                "success": False,
                "transcript": "",
                "error": f"Could not recognize speech clearly ({exc}). Please try speaking closer to the microphone."
            }

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
        with_pauses = re.sub(r"([.!?])\s+", r'\1 <break time="250ms"/> ', escaped)
        return f'<speak><prosody rate="98%">{with_pauses}</prosody></speak>'

    def synthesize_speech_mp3(
        self,
        spoken_text: str,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None
    ) -> bytes | None:
        """
        Synthesizes MP3 speech audio bytes for playback in the UI (`st.audio`):
        1. Uses Amazon Polly Neural TTS (`Kajal`) when AWS IAM credentials are configured.
        2. Automatically falls back to `gTTS` (Google Text-to-Speech) so MP3 audio playback
           works out-of-the-box on Streamlit Community Cloud without paid API keys.
        """
        if not spoken_text or not spoken_text.strip():
            return None

        cache_key = hashlib.sha256(spoken_text.strip().encode("utf-8")).hexdigest()[:24]
        if cache_key in self._tts_cache:
            return self._tts_cache[cache_key]

        ak = (aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID", "")).strip()
        sk = (aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY", "")).strip()

        # 1. Try Amazon Polly first if AWS credentials are provided
        if ak and sk and "PASTE_YOUR" not in ak and "INSERT_" not in ak:
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
                    mp3_bytes = stream.read()
                    self._tts_cache[cache_key] = mp3_bytes
                    return mp3_bytes
            except Exception:
                pass

        # 2. Fallback to gTTS (Google Text-to-Speech MP3 generator)
        try:
            from gtts import gTTS
            buf = io.BytesIO()
            tts = gTTS(text=spoken_text.strip(), lang="en", tld="co.in", slow=False)
            tts.write_to_fp(buf)
            mp3_bytes = buf.getvalue()
            if mp3_bytes:
                self._tts_cache[cache_key] = mp3_bytes
                return mp3_bytes
        except Exception:
            return None
        return None
