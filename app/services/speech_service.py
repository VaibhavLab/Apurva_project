import io
import re
import wave

from flask import current_app
from app.services.gemini_service import GeminiService, ProviderError


class SpeechService:
    """Normalize provider audio to WAV in memory; never save speech to disk."""
    def synthesize(self, text: str) -> bytes:
        data, mime_type = GeminiService().synthesize(text)
        mime_type = (mime_type or "").lower()
        try:
            if mime_type.split(";")[0] in {"audio/wav", "audio/x-wav", "audio/wave"}:
                with wave.open(io.BytesIO(data), "rb") as recording:
                    if recording.getsampwidth() != 2 or recording.getnchannels() != 1 or recording.getnframes() == 0:
                        raise ValueError()
                    if len(recording.readframes(recording.getnframes())) != recording.getnframes() * 2:
                        raise ValueError()
                return data
            if mime_type.split(";")[0] not in {"audio/l16", "audio/pcm"} or not data or len(data) % 2:
                raise ValueError()
            rate_match = re.search(r"\brate=(\d+)", mime_type)
            rate = int(rate_match.group(1)) if rate_match else None
            if rate is None and current_app.config["GEMINI_TTS_MODEL"] == "gemini-3.1-flash-tts-preview":
                rate = 24000
            if rate not in {16000, 22050, 24000, 44100, 48000}:
                raise ValueError()
            channels = re.search(r"\bchannels=(\d+)", mime_type)
            if channels and channels.group(1) != "1":
                raise ValueError()
            output = io.BytesIO()
            with wave.open(output, "wb") as recording:
                recording.setnchannels(1)
                recording.setsampwidth(2)
                recording.setframerate(rate)
                recording.writeframes(data)
            return output.getvalue()
        except (ValueError, wave.Error, EOFError, TypeError):
            raise ProviderError("Speech returned an unsupported audio format. Your text reply is saved.", "invalid_audio", 502) from None
