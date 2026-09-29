import array
import io
import math
import sys
import wave

from flask import current_app

from app.services.gemini_service import GeminiService, ProviderError


class TranscriptionService:
    """Validate a bounded PCM WAV in memory before sending it to Google."""
    def transcribe(self, audio: bytes) -> str:
        if not audio or len(audio) > current_app.config["VOICE_MAX_UPLOAD_BYTES"]:
            raise ProviderError("The recording is empty or too large.", "invalid_upload", 413)
        try:
            if audio[:4] != b"RIFF" or audio[8:12] != b"WAVE" or int.from_bytes(audio[4:8], "little") + 8 != len(audio):
                raise ValueError()
            with wave.open(io.BytesIO(audio), "rb") as recording:
                frames = recording.getnframes()
                if (recording.getnchannels(), recording.getsampwidth(), recording.getframerate(), recording.getcomptype()) != (1, 2, 16000, "NONE"):
                    raise ValueError()
                if not 0 < frames <= 16000 * current_app.config["VOICE_MAX_SECONDS"]:
                    raise ValueError()
                pcm = recording.readframes(frames)
                if len(pcm) != frames * 2:
                    raise ValueError()
        except (ValueError, wave.Error, EOFError, OverflowError):
            raise ProviderError("Use a valid mono 16 kHz, 16-bit WAV recording of at most 30 seconds.", "invalid_audio", 400) from None
        samples = array.array("h", pcm)
        if sys.byteorder != "little":
            samples.byteswap()
        if math.sqrt(sum(sample * sample for sample in samples) / len(samples)) < 20:
            raise ProviderError("The recording is silent or too quiet. Please try again.", "no_speech", 422)
        return GeminiService().transcribe(audio)
