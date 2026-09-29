from flask import Blueprint, Response, abort, current_app, jsonify, request, session
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Conversation, Message
from app.routes.conversations import owned_conversation
from app.services.gemini_service import GeminiService, ProviderError
from app.services.speech_service import SpeechService
from app.services.transcription_service import TranscriptionService

voice_bp = Blueprint("voice", __name__)


def require_voice():
    if not GeminiService.voice_enabled():
        raise ProviderError("Voice is unavailable. You can still use text chat.", "voice_disabled")
    if not session.get("gemini_consent_v1"):
        raise ProviderError("Review the Google processing disclosure before using voice.", "consent_required", 403)


@voice_bp.get("/api/voice/capabilities")
@login_required
def capabilities():
    return jsonify(success=True, gemini_enabled=GeminiService.enabled(),
                   voice_enabled=GeminiService.voice_enabled(), consent=bool(session.get("gemini_consent_v1")),
                   max_seconds=current_app.config["VOICE_MAX_SECONDS"],
                   max_upload_bytes=current_app.config["VOICE_MAX_UPLOAD_BYTES"],
                   request_timeout_ms=(current_app.config["GEMINI_TIMEOUT_SECONDS"] + 15) * 1000)


@voice_bp.post("/api/voice/consent")
@login_required
def consent():
    payload = request.get_json()
    if not isinstance(payload, dict) or type(payload.get("accepted")) is not bool:
        abort(400)
    session["gemini_consent_v1"] = payload["accepted"]
    return jsonify(success=True, accepted=payload["accepted"])


@voice_bp.post("/api/voice/transcribe")
@login_required
def transcribe():
    require_voice()
    try:
        conversation_id = int(request.form.get("conversation_id", ""))
    except (ValueError, TypeError):
        abort(400)
    owned_conversation(conversation_id)
    upload = request.files.get("audio")
    if not upload:
        raise ProviderError("Choose a recording to transcribe.", "missing_audio", 400)
    audio = upload.read(current_app.config["VOICE_MAX_UPLOAD_BYTES"] + 1)
    user_id = current_user.id
    db.session.rollback()
    current_app.extensions["provider_limiter"].check(user_id, "transcribe")
    transcript = TranscriptionService().transcribe(audio)
    # A conversation may have been deleted while transcription ran.
    owned_conversation(conversation_id)
    return jsonify(success=True, transcript=transcript, input_mode="voice")


@voice_bp.post("/api/messages/<int:message_id>/speech")
@login_required
def speech(message_id):
    require_voice()
    message = db.session.scalar(db.select(Message).join(Conversation).where(
        Message.id == message_id, Conversation.user_id == current_user.id, Message.sender == "bot"))
    if message is None:
        abort(404)
    text, conversation_id, user_id = message.content, message.conversation_id, current_user.id
    db.session.rollback()
    current_app.extensions["provider_limiter"].check(user_id, "speech")
    audio = SpeechService().synthesize(text)
    owned_conversation(conversation_id)
    return Response(audio, mimetype="audio/wav", headers={"Cache-Control": "no-store"})
