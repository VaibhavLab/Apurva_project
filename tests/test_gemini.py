import json
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors, types

from app.services.gemini_service import GeminiService, ProviderError


def response(text="A gentle response.", finish="STOP", parts=None):
    return types.GenerateContentResponse(candidates=[types.Candidate(finish_reason=finish,
        content=types.Content(role="model", parts=parts or [types.Part(text=text)]))])


@pytest.fixture
def sdk(app, monkeypatch):
    app.config.update(GEMINI_ENABLED=True, GEMINI_API_KEY="mock-secret-never-exposed")
    state = {"result": response(), "calls": []}
    class Client:
        def __init__(self, **kwargs):
            state["options"] = kwargs
            self.models = self
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def generate_content(self, **kwargs):
            state["calls"].append(kwargs)
            if isinstance(state["result"], Exception):
                raise state["result"]
            return state["result"]
    monkeypatch.setattr("app.services.gemini_service.genai.Client", Client)
    return state


def test_sdk_configuration_history_and_system_prompt(app, sdk):
    with app.app_context():
        result = GeminiService().reply("Latest", [{"role": "user", "text": "Earlier"}, {"role": "model", "text": "Earlier reply"}])
    assert result == "A gentle response."
    call = sdk["calls"][0]
    assert [item.parts[0].text for item in call["contents"]] == ["Earlier", "Earlier reply", "Latest"]
    assert "not a therapist" in call["config"].system_instruction
    assert sdk["options"]["http_options"].timeout == 30000
    assert sdk["options"]["http_options"].retry_options.attempts == 1


@pytest.mark.parametrize("result,code,status", [
    (httpx.ReadTimeout("mock-secret-never-exposed"), "provider_timeout", 504),
    (errors.APIError(429, {"message": "mock-secret-never-exposed"}), "provider_rate_limit", 429),
    (errors.APIError(403, {"message": "mock-secret-never-exposed"}), "provider_configuration", 503),
    (errors.APIError(404, {"message": "model missing"}), "provider_configuration", 503),
    (errors.APIError(500, {"message": "private prompt"}), "provider_unavailable", 503),
    (RuntimeError("mock-secret-never-exposed"), "provider_unavailable", 503),
    (types.GenerateContentResponse(), "incomplete_response", 502),
    (response(finish="SAFETY"), "incomplete_response", 502),
    (response(finish="MAX_TOKENS"), "incomplete_response", 502),
    (response(text=""), "invalid_response", 502),
    (response(text="x" * 4001), "invalid_response", 502),
])
def test_errors_sanitized(app, sdk, result, code, status):
    sdk["result"] = result
    with app.app_context(), pytest.raises(ProviderError) as caught:
        GeminiService().reply("private user message", [])
    assert caught.value.code == code and caught.value.status == status
    assert "mock-secret-never-exposed" not in str(caught.value)
    assert "private" not in str(caught.value)


@pytest.mark.parametrize("body,valid", [
    ({"transcript": "I need a break", "speech_detected": True, "language": "en"}, True),
    ({"transcript": "", "speech_detected": False, "language": "en"}, False),
    ({"transcript": "invented", "speech_detected": "true", "language": "en"}, False),
    ({"transcript": "hola", "speech_detected": True, "language": "es"}, False),
    ({"transcript": "x" * 4001, "speech_detected": True, "language": "en"}, False),
    (["wrong shape"], False), ("not json", False),
])
def test_transcription_contract(app, sdk, body, valid):
    sdk["result"] = response(text=json.dumps(body) if not isinstance(body, str) else body)
    with app.app_context():
        if valid:
            assert GeminiService().transcribe(b"bounded wav") == "I need a break"
        else:
            with pytest.raises(ProviderError):
                GeminiService().transcribe(b"bounded wav")
    call = sdk["calls"][0]
    assert call["contents"][0].inline_data.mime_type == "audio/wav"
    assert "Do not answer" in call["config"].system_instruction


def test_tts_inline_data_and_voice(app, sdk):
    sdk["result"] = response(parts=[types.Part(inline_data=types.Blob(data=b"\x01\x00", mime_type="audio/L16;rate=24000"))])
    with app.app_context():
        assert GeminiService().synthesize("Saved answer") == (b"\x01\x00", "audio/L16;rate=24000")
    config = sdk["calls"][0]["config"]
    assert config.response_modalities == ["AUDIO"]
    assert config.speech_config.voice_config.prebuilt_voice_config.voice_name == "Kore"
    assert sdk["calls"][0]["contents"].endswith("Saved answer")


def test_tts_missing_audio(app, sdk):
    with app.app_context(), pytest.raises(ProviderError, match="audio"):
        GeminiService().synthesize("Saved answer")
