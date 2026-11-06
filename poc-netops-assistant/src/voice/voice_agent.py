from array import array
import hashlib
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import wave
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
    1. Speech-to-Text (STT / Voice Input): Transcribes user microphone WAV audio (`st.chat_input(accept_audio=True)`)
       into text using a zero-dependency stdlib PCM wave recognizer (plus optional `SpeechRecognition` fallback).
    2. Spoken Script Normalization: Converts Markdown RAG / NetOps answers into natural spoken scripts
       (pronouncing USSD codes like `#1456#` as 'hash 1 4 5 6 hash', stripping URLs/markdown symbols).
    3. W3C SSML Generation: Produces `<speak>...</speak>` SSML for Amazon Connect / Amazon Polly Neural TTS.
    4. Text-to-Speech (TTS / Voice Output): Synthesizes real MP3 audio bytes via Amazon Polly (`Kajal` Neural),
       `gTTS`, or zero-dependency stdlib HTTPS MP3 synthesis so the assistant speaks back in every environment.
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

    _CHROMIUM_SPEECH_ENDPOINT = "http://www.google.com/speech-api/v2/recognize"
    _CHROMIUM_SPEECH_KEY = "AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw"

    def __init__(self, default_voice_id: str | None = None, aws_region: str | None = None):
        self.voice_id = default_voice_id or os.getenv("AWS_POLLY_VOICE_ID", "Kajal")
        self.aws_region = aws_region or os.getenv("AWS_REGION", "us-east-1")
        self._tts_cache: dict[str, bytes] = {}

    @classmethod
    def _extract_pcm16_mono(cls, wav_bytes: bytes) -> tuple[bytes, int]:
        """Extracts 16-bit mono PCM audio frames and sample rate using Python's built-in `wave` module."""
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            nchannels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            raw_frames = wf.readframes(wf.getnframes())

        if sampwidth == 1:
            samples16 = array("h", ((b - 128) << 8 for b in raw_frames))
        elif sampwidth == 2:
            samples16 = array("h")
            samples16.frombytes(raw_frames)
            if sys.byteorder == "big":
                samples16.byteswap()
        elif sampwidth == 4:
            samples32 = array("i")
            samples32.frombytes(raw_frames)
            if sys.byteorder == "big":
                samples32.byteswap()
            samples16 = array("h", (s >> 16 for s in samples32))
        else:
            return raw_frames, framerate

        if nchannels > 1:
            mono = array(
                "h",
                (
                    sum(samples16[i + ch] for ch in range(nchannels)) // nchannels
                    for i in range(0, len(samples16) - nchannels + 1, nchannels)
                )
            )
            samples16 = mono

        if sys.byteorder == "big":
            samples16.byteswap()
        return samples16.tobytes(), framerate

    @classmethod
    def _recognize_pcm16_stdlib(cls, pcm16_bytes: bytes, sample_rate: int, language: str) -> str:
        """Calls the Chromium Speech Recognition endpoint directly using Python's standard library."""
        params = urllib.parse.urlencode({
            "client": "chromium",
            "lang": language,
            "key": cls._CHROMIUM_SPEECH_KEY,
            "pFilter": 0
        })
        url = f"{cls._CHROMIUM_SPEECH_ENDPOINT}?{params}"
        req = urllib.request.Request(
            url,
            data=pcm16_bytes,
            headers={
                "Content-Type": f"audio/l16; rate={sample_rate}",
                "User-Agent": "Mozilla/5.0"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            resp_text = resp.read().decode("utf-8", errors="ignore")

        for line in resp_text.splitlines():
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            results = data.get("result", [])
            if results and results[0].get("alternative"):
                alts = results[0]["alternative"]
                best = max(alts, key=lambda a: a.get("confidence", 0.5))
                transcript = best.get("transcript", "").strip()
                if transcript:
                    return transcript
        return ""

    @classmethod
    def transcribe_audio_bytes(cls, wav_bytes: bytes, language: str = "en-LK") -> dict:
        """
        Transcribes WAV audio recorded from the user's microphone (`st.chat_input(accept_audio=True)`) into text.
        Works out-of-the-box using Python's built-in `wave` + `urllib.request` with zero external packages required,
        and also supports `speech_recognition` if installed.
        """
        if not wav_bytes:
            return {"success": False, "transcript": "", "error": "Empty audio buffer."}

        # 1. Primary Zero-Dependency Stdlib WAV -> L16 Speech Recognition (works on all Streamlit Cloud runtimes)
        try:
            pcm16_bytes, sample_rate = cls._extract_pcm16_mono(wav_bytes)
            for lang in (language, "en-US"):
                try:
                    transcript = cls._recognize_pcm16_stdlib(pcm16_bytes, sample_rate, lang)
                    if transcript:
                        return {"success": True, "transcript": transcript, "error": None}
                except Exception:
                    continue
        except Exception:
            pass

        # 2. Optional fallback via `speech_recognition` package if installed
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
                audio_data = recognizer.record(source)

            for lang in (language, "en-US"):
                try:
                    transcript = recognizer.recognize_google(audio_data, language=lang)
                    if transcript and transcript.strip():
                        return {"success": True, "transcript": transcript.strip(), "error": None}
                except Exception:
                    continue
        except Exception:
            pass

        return {
            "success": False,
            "transcript": "",
            "error": "Could not hear clear speech in the recording. Please speak clearly into the microphone and try again."
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
        if spoken_text and spoken_text[-1] not in ".!?":
            spoken_text += "."
        return spoken_text

    @classmethod
    def build_ssml(cls, spoken_text: str) -> str:
        """
        Wraps a spoken script in W3C SSML (<speak>...</speak>) for Amazon Connect & Amazon Polly.
        """
        escaped = (
            spoken_text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        with_pauses = re.sub(r"\.\s+", '. <break time="250ms"/> ', escaped)
        return f'<speak><prosody rate="98%">{with_pauses}</prosody></speak>'

    @classmethod
    def build_ivr_response(
        cls,
        answer_markdown: str,
        key_points: list[str] | None = None,
        escalation_required: bool = False,
        intent_route: str = "AWS_CLOUD_KB"
    ) -> dict:
        """
        Builds a complete Voice / IVR payload for Amazon Connect, Polly, and Web Speech playback.
        """
        spoken_text = cls.format_for_speech(answer_markdown, key_points)
        ssml = cls.build_ssml(spoken_text)

        if escalation_required:
            ivr_queue_action = "SLT_NOC_TIER3_EMERGENCY_QUEUE"
        elif intent_route == "NETOPS_INCIDENT":
            ivr_queue_action = "SLT_NOC_TIER2_TECHNICAL_DESK"
        else:
            ivr_queue_action = "SELF_SERVICE_COMPLETED"

        return {
            "spoken_text": spoken_text,
            "ssml": ssml,
            "ivr_queue_action": ivr_queue_action,
            "voice_engine": "AMAZON_POLLY_NEURAL_AND_GTTS"
        }

    @staticmethod
    def _synthesize_mp3_stdlib(spoken_text: str) -> bytes | None:
        """Zero-dependency stdlib fallback for MP3 synthesis when boto3 and gTTS are unavailable."""
        words = spoken_text.split()
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0
        for w in words:
            if current_len + len(w) + 1 > 180 and current:
                chunks.append(" ".join(current))
                current = [w]
                current_len = len(w)
            else:
                current.append(w)
                current_len += len(w) + 1
        if current:
            chunks.append(" ".join(current))

        mp3_parts = []
        for chunk in chunks[:4]:
            params = urllib.parse.urlencode({
                "ie": "UTF-8",
                "client": "tw-ob",
                "tl": "en",
                "q": chunk
            })
            url = f"https://translate.google.com/translate_tts?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                mp3_parts.append(resp.read())
        return b"".join(mp3_parts) if mp3_parts else None

    def synthesize_speech_mp3(self, spoken_text: str) -> bytes | None:
        """
        Synthesizes real MP3 audio bytes from spoken_text.
        1. Attempts Amazon Polly Neural TTS (`Kajal` / `Joanna`) if AWS credentials are configured.
        2. Falls back to `gTTS` if installed.
        3. Falls back to zero-dependency stdlib HTTPS MP3 synthesis so voice output works in all environments.
        Caches generated MP3 bytes in memory to keep repeat playback instant.
        """
        if not spoken_text or not spoken_text.strip():
            return None

        cache_key = hashlib.sha256(spoken_text.strip().encode("utf-8")).hexdigest()[:24]
        if cache_key in self._tts_cache:
            return self._tts_cache[cache_key]

        # 1. Try Amazon Polly if AWS credentials exist
        if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
            try:
                import boto3
                polly = boto3.client("polly", region_name=self.aws_region)
                resp = polly.synthesize_speech(
                    Text=self.build_ssml(spoken_text),
                    TextType="ssml",
                    OutputFormat="mp3",
                    VoiceId=self.voice_id,
                    Engine="neural"
                )
                audio_stream = resp.get("AudioStream")
                if audio_stream:
                    mp3_bytes = audio_stream.read()
                    self._tts_cache[cache_key] = mp3_bytes
                    return mp3_bytes
            except Exception:
                pass

        # 2. Try gTTS if installed
        try:
            from gtts import gTTS
            mp3_buf = io.BytesIO()
            tts = gTTS(text=spoken_text, lang="en", tld="co.in", slow=False)
            tts.write_to_fp(mp3_buf)
            mp3_bytes = mp3_buf.getvalue()
            if mp3_bytes:
                self._tts_cache[cache_key] = mp3_bytes
                return mp3_bytes
        except Exception:
            pass

        # 3. Zero-dependency stdlib MP3 synthesis fallback
        try:
            mp3_bytes = self._synthesize_mp3_stdlib(spoken_text)
            if mp3_bytes:
                self._tts_cache[cache_key] = mp3_bytes
                return mp3_bytes
        except Exception:
            pass

        return None
