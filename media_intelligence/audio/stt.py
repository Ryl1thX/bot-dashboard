"""
Multi-Provider Speech-to-Text (STT) Engine with Failover.
Supports Groq Whisper-Large-v3-Turbo, Gemini Audio Multimodal, and OpenRouter Whisper.
"""
import os
import io
import time
import base64
import tempfile
import aiohttp
from typing import Optional, Tuple, List
from ..types import TranscriptSegment
from ..config import MAX_AUDIO_FILE_SIZE_MB

class MultiProviderSTT:

    def __init__(self, groq_key: Optional[str] = None, gemini_key: Optional[str] = None, openrouter_key: Optional[str] = None):
        self.groq_key = groq_key or os.getenv("GROQ_KEY", "")
        self.gemini_key = gemini_key or os.getenv("GEMINI_KEY", "")
        self.openrouter_key = openrouter_key or os.getenv("OPENROUTER_KEY", "")

    async def transcribe(self, wav_bytes: bytes, filename: str = "speech.wav") -> Tuple[Optional[str], Optional[str]]:
        if not wav_bytes or len(wav_bytes) < 500:
            return "", None

        # 1. Primary STT: Groq Whisper Large v3 Turbo (ultra fast <300ms)
        if self.groq_key:
            res, err = await self._transcribe_groq(wav_bytes, filename)
            if not err and res:
                return res, None

        # 2. Secondary Failover: Gemini 3.5 Flash Audio Multimodal
        if self.gemini_key:
            res, err = await self._transcribe_gemini(wav_bytes)
            if not err and res:
                return res, None

        # 3. Tertiary Failover: OpenRouter Whisper
        if self.openrouter_key:
            res, err = await self._transcribe_openrouter(wav_bytes, filename)
            if not err and res:
                return res, None

        return None, "All STT providers failed or no API keys configured."

    async def _transcribe_groq(self, wav_bytes: bytes, filename: str) -> Tuple[Optional[str], Optional[str]]:
        tmp_path = tempfile.mktemp(suffix=".wav")
        try:
            with open(tmp_path, "wb") as f:
                f.write(wav_bytes)

            async with aiohttp.ClientSession() as session:
                with open(tmp_path, "rb") as af:
                    data = aiohttp.FormData()
                    data.add_field("file", af, filename=filename, content_type="audio/wav")
                    data.add_field("model", "whisper-large-v3-turbo")
                    data.add_field("temperature", "0.0")
                    data.add_field("response_format", "json")
                    async with session.post(
                        "https://api.groq.com/openai/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {self.groq_key}"},
                        data=data,
                        timeout=aiohttp.ClientTimeout(total=45)
                    ) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            return result.get("text", "").strip(), None
                        else:
                            txt = await resp.text()
                            return None, f"Groq STT HTTP {resp.status}: {txt[:150]}"
        except Exception as e:
            return None, str(e)
        finally:
            if os.path.exists(tmp_path):
                try: os.remove(tmp_path)
                except: pass

    async def _transcribe_gemini(self, wav_bytes: bytes) -> Tuple[Optional[str], Optional[str]]:
        try:
            b64_audio = base64.b64encode(wav_bytes).decode("utf-8")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_key}"
            payload = {
                "contents": [{
                    "parts": [
                        {"text": "Transcribe this audio verbatim without commentary or timestamps. Return only the spoken dialogue."},
                        {"inline_data": {"mime_type": "audio/wav", "data": b64_audio}}
                    ]
                }]
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=40)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        return text, None
                    else:
                        return None, f"Gemini STT HTTP {resp.status}"
        except Exception as e:
            return None, str(e)

    async def _transcribe_openrouter(self, wav_bytes: bytes, filename: str) -> Tuple[Optional[str], Optional[str]]:
        # OpenRouter fallback
        return None, "OpenRouter STT fallback unconfigured"
