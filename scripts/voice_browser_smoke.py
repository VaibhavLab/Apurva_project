"""Offline voice acceptance: real browser/worklet/WAV/playback, simulated mic and Gemini."""
import io
import os
import secrets
import sys
import tempfile
import threading
import wave
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from app import create_app
from app.extensions import db
from app.services.gemini_service import GeminiService, ProviderError
from scripts.browser_smoke import QuietHandler
from tests.test_voice import wav_audio


def main():
    screenshots = Path(__file__).resolve().parents[1] / "docs/screenshots"
    transcript = "I feel stressed about my exams."
    reply = "A short break may help you reset. What is one small task you could begin with?"
    calls = {"transcribe": 0, "chat": 0, "speech": 0, "fail_speech": False}
    def transcribe(self, audio):
        calls["transcribe"] += 1
        with wave.open(io.BytesIO(audio)) as recording:
            assert (recording.getframerate(), recording.getnchannels(), recording.getsampwidth()) == (16000, 1, 2)
            assert 0 < recording.getnframes() <= 16000 * 3
        return transcript
    def chat(self, text, history):
        calls["chat"] += 1
        return reply
    def speech(self, text):
        calls["speech"] += 1
        assert text == reply
        if calls["fail_speech"]:
            raise ProviderError("Simulated speech failure.", "provider_timeout", 504)
        return wav_audio(seconds=3, rate=24000), "audio/wav"
    def unexpected(*args, **kwargs):
        raise AssertionError("Tests must never contact Google")

    with tempfile.TemporaryDirectory(prefix="mindcare-voice-") as temporary:
        microphone = Path(temporary) / "microphone.wav"
        microphone.write_bytes(wav_audio(seconds=4, rate=48000))
        app = create_app({"TESTING": True, "PRODUCTION": False, "SECRET_KEY": secrets.token_hex(32),
                          "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(Path(temporary) / "voice.db").replace("\\", "/"),
                          "SESSION_COOKIE_SECURE": False, "GEMINI_ENABLED": True, "VOICE_ENABLED": True,
                          "GEMINI_API_KEY": "mock-only", "VOICE_MAX_SECONDS": 3, "VOICE_REQUESTS_PER_MINUTE": 100})
        server = make_server("127.0.0.1", 5052, app, threaded=True, request_handler=QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(GeminiService, "transcribe", transcribe), patch.object(GeminiService, "reply", chat), patch.object(GeminiService, "synthesize", speech), patch.object(GeminiService, "_generate", unexpected), sync_playwright() as playwright:
                chrome = Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe"
                browser = playwright.chromium.launch(executable_path=str(chrome) if chrome.exists() else None,
                    headless=True, args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                                        "--use-file-for-fake-audio-capture=" + str(microphone)])
                context = browser.new_context(viewport={"width": 1440, "height": 1000})
                context.add_init_script("""
                    window.testStreams = []; window.testAudio = []; window.testURLs = new Set();
                    const getMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
                    window.originalGetMedia = getMedia;
                    navigator.mediaDevices.getUserMedia = async options => {
                        const stream = await getMedia(options); window.testStreams.push(stream); return stream;
                    };
                    const NativeAudio = window.Audio;
                    window.Audio = function(url) { const audio = new NativeAudio(url); window.testAudio.push(audio); return audio; };
                    const createURL = URL.createObjectURL.bind(URL), revokeURL = URL.revokeObjectURL.bind(URL);
                    URL.createObjectURL = blob => { const url = createURL(blob); window.testURLs.add(url); return url; };
                    URL.revokeObjectURL = url => { window.testURLs.delete(url); revokeURL(url); };
                    const nativePlay = HTMLMediaElement.prototype.play;
                    HTMLMediaElement.prototype.play = function() {
                        if (window.rejectPlay) { window.rejectPlay = false; return Promise.reject(new DOMException('Blocked', 'NotAllowedError')); }
                        return nativePlay.call(this);
                    };
                """)
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                base = "http://127.0.0.1:5052"
                page.goto(base + "/register")
                password = secrets.token_urlsafe(20)
                for label, value in [("Full name", "Voice Tester"), ("Username", "voice_test"),
                                     ("Email address", "voice@example.com"), ("Password", password), ("Confirm password", password)]:
                    page.get_by_label(label, exact=True).fill(value)
                page.get_by_role("button", name="Create account", exact=True).click()
                page.get_by_label("Email or username").fill("voice_test")
                page.get_by_label("Password", exact=True).fill(password)
                page.get_by_role("button", name="Log in", exact=True).click()
                expect(page.locator("#dictation-button")).to_be_enabled()
                assert page.evaluate("testStreams.length") == 0

                # Declining first text consent sends a local turn without calling Google.
                page.locator("#message-input").fill("Hello")
                page.locator("#send-button").click()
                expect(page.locator("#voice-consent")).to_be_visible()
                page.locator("#consent-decline").click()
                expect(page.locator(".message-bot")).to_have_count(1)
                assert calls["chat"] == 0
                page.locator("#new-conversation").click()
                expect(page.locator("#message-input")).to_be_enabled()

                # Consent precedes microphone access. Simulated permission denial remains recoverable.
                page.evaluate("() => { navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException('Denied', 'NotAllowedError')); }")
                page.locator("#dictation-button").click()
                expect(page.locator("#voice-consent")).to_be_visible()
                assert page.evaluate("testStreams.length") == 0
                page.locator("#consent-accept").click()
                expect(page.locator("#voice-status")).to_contain_text("denied")
                expect(page.locator("#message-input")).to_be_enabled()
                page.evaluate("""() => { navigator.mediaDevices.getUserMedia = async options => {
                    const stream = await originalGetMedia(options); testStreams.push(stream); return stream;
                }; }""")

                def record(button="#dictation-button"):
                    page.locator(button).click()
                    expect(page.locator("#voice-panel")).to_have_attribute("data-state", "recording")
                    page.wait_for_function("() => document.querySelector('#voice-level').value > 0")

                def stopped():
                    assert page.evaluate("testStreams.every(stream => stream.getTracks().every(track => track.readyState === 'ended'))")
                    assert page.evaluate("testAudio.filter(audio => !audio.paused).length") <= 1

                # Capture from the browser's 48 kHz fixture, actual resampling and multipart validation.
                record()
                page.locator("#voice-stop").click()
                expect(page.locator("#message-input")).to_have_value(transcript)
                expect(page.locator("#message-input")).to_be_enabled()
                expect(page.locator(".message")).to_have_count(0)
                stopped()
                page.locator("#message-input").fill("")
                record()
                page.locator("#voice-cancel").click()
                expect(page.locator("#voice-panel")).to_have_attribute("data-state", "idle")
                stopped()
                assert calls["transcribe"] == 1

                # Voice captions survive failed automatic playback; manual Play works.
                page.evaluate("window.rejectPlay = true")
                record("#voice-button")
                page.locator("#voice-stop").click()
                expect(page.locator(".message-user .message-body")).to_have_text(transcript)
                expect(page.locator(".message-bot .message-body")).to_have_text(reply)
                expect(page.locator("#voice-play")).to_be_visible()
                expect(page.locator(".message")).to_have_count(2)
                page.locator("#voice-play").click()
                expect(page.locator("#voice-panel")).to_have_attribute("data-state", "playing")
                stopped()
                page.locator("#voice-end").click()
                expect(page.locator("#voice-panel")).to_have_attribute("data-state", "idle")
                assert page.evaluate("testAudio.every(audio => audio.paused) && testURLs.size === 0")

                # Read-aloud retry hits only speech; text history is unchanged.
                before_chat = calls["chat"]
                calls["fail_speech"] = True
                page.locator(".speech-button").click()
                expect(page.locator("#voice-status")).to_contain_text("text reply is saved")
                expect(page.locator("#voice-replay")).to_be_visible()
                calls["fail_speech"] = False
                page.locator("#voice-replay").click()
                expect(page.locator("#voice-panel")).to_have_attribute("data-state", "playing")
                page.locator("#voice-cancel").click()
                assert calls["chat"] == before_chat
                expect(page.locator(".message")).to_have_count(2)

                # A second explicit turn automatically stops at the configured duration.
                record("#voice-button")
                expect(page.locator(".message-bot")).to_have_count(2, timeout=12000)
                expect(page.locator("#voice-panel")).to_have_attribute("data-state", "playing")
                stopped()
                page.screenshot(path=str(screenshots / "voice-conversation.png"), full_page=True)
                page.locator("#voice-end").click()

                # Ignore a deliberately late transcription after switching conversations.
                pending = []
                page.route("**/api/voice/transcribe", lambda route: pending.append(route))
                record()
                with page.expect_request("**/api/voice/transcribe"):
                    page.locator("#voice-stop").click()
                page.locator("#new-conversation").click()
                expect(page.locator("#empty-state")).to_be_visible()
                pending[0].fulfill(json={"success": True, "transcript": "Stale words"})
                page.unroute("**/api/voice/transcribe")
                expect(page.locator("#message-input")).to_have_value("")
                expect(page.locator(".message")).to_have_count(0)
                stopped()
                assert page.evaluate("testURLs.size") == 0

                # A lost response after commit must reuse the voice request ID from the text composer.
                lost = []
                def lose_saved_response(route):
                    lost.append(route.request.post_data_json)
                    saved = route.fetch()
                    assert saved.status == 200
                    route.abort("failed")
                page.route("**/api/chat", lose_saved_response)
                before_chat = calls["chat"]
                record("#voice-button")
                page.locator("#voice-stop").click()
                expect(page.locator("#voice-status")).to_contain_text("Unable to connect")
                expect(page.locator("#message-input")).to_have_value(transcript)
                page.unroute("**/api/chat")
                retried = []
                def observe_retry(route):
                    retried.append(route.request.post_data_json)
                    route.continue_()
                page.route("**/api/chat", observe_retry)
                page.locator("#send-button").click()
                expect(page.locator(".message-bot")).to_have_count(1)
                assert retried[0]["request_id"] == lost[0]["request_id"]
                assert retried[0]["input_mode"] == "voice"
                assert calls["chat"] == before_chat + 1
                expect(page.locator(".message")).to_have_count(2)
                page.unroute("**/api/chat")

                # A late speech response cannot start playback in another conversation.
                late_speech = []
                before_audio = page.evaluate("testAudio.length")
                page.route("**/api/messages/*/speech", lambda route: late_speech.append(route))
                with page.expect_request("**/api/messages/*/speech"):
                    page.locator(".speech-button").click()
                page.locator("#new-conversation").click()
                expect(page.locator("#empty-state")).to_be_visible()
                late_speech[0].fulfill(body=wav_audio(), content_type="audio/wav")
                page.unroute("**/api/messages/*/speech")
                expect(page.locator("#voice-panel")).to_have_attribute("data-state", "idle")
                assert page.evaluate("testAudio.length") == before_audio
                assert page.evaluate("testURLs.size") == 0

                # Hidden-page, pending-permission, and mobile keyboard cancellation.
                record()
                page.evaluate("Object.defineProperty(document, 'hidden', {configurable:true, value:true}); document.dispatchEvent(new Event('visibilitychange'))")
                expect(page.locator("#voice-panel")).to_have_attribute("data-state", "idle")
                stopped()
                page.evaluate("delete document.hidden")
                page.evaluate("""() => { navigator.mediaDevices.getUserMedia = () => new Promise(resolve => window.resolvePermission = resolve); }""")
                page.locator("#dictation-button").click()
                expect(page.locator("#voice-panel")).to_have_attribute("data-state", "requesting_permission")
                page.locator("#voice-cancel").click()
                page.evaluate("""async () => {
                    const stream = await originalGetMedia({audio:true});
                    testStreams.push(stream); resolvePermission(stream);
                }""")
                page.wait_for_function("() => testStreams.every(stream => stream.getTracks().every(track => track.readyState === 'ended'))")
                page.evaluate("""() => { navigator.mediaDevices.getUserMedia = async options => {
                    const stream = await originalGetMedia(options); testStreams.push(stream); return stream;
                }; }""")
                page.set_viewport_size({"width": 390, "height": 844})
                page.locator("#dictation-button").focus()
                page.keyboard.press("Enter")
                expect(page.locator("#voice-panel")).to_have_attribute("data-state", "recording")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(path=str(screenshots / "voice-mobile.png"), full_page=True)
                page.locator("#voice-cancel").focus()
                page.keyboard.press("Enter")
                stopped()
                assert not errors, errors
                browser.close()
                print("Voice browser checks passed: consent, local choice, permission denial, real worklet capture/resampling, editable dictation, cancel/end, bounded voice turns, captions, real WAV playback, autoplay recovery, speech-only retry, stale response isolation, hidden-page and late-permission cleanup, mobile keyboard controls.")
        finally:
            server.shutdown()
            thread.join(timeout=5)
            with app.app_context():
                db.session.remove()
                db.engine.dispose()


if __name__ == "__main__":
    main()
