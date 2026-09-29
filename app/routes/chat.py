import re
import uuid

from flask import Blueprint, abort, current_app, jsonify, render_template, request, session
from flask_login import current_user, login_required

from app.routes.conversations import owned_conversation
from app.services.chat_processing_service import ChatProcessingService

chat_bp = Blueprint("chat", __name__)


@chat_bp.get("/chat")
@chat_bp.get("/conversations/<int:conversation_id>")
@login_required
def dashboard(conversation_id=None):
    if conversation_id is not None:
        owned_conversation(conversation_id)
    return render_template("chat.html", conversation_id=conversation_id or "")


@chat_bp.post("/api/chat")
@login_required
def send_message():
    payload = request.get_json()
    if not isinstance(payload, dict):
        abort(400)
    text = payload.get("message")
    if not isinstance(text, str) or not text.strip():
        return jsonify(success=False, error="Write a message before sending."), 400
    text = text.strip()
    if len(text) > current_app.config["MAX_MESSAGE_LENGTH"]:
        return jsonify(success=False, error="Please keep your message under 4,000 characters."), 400
    conversation_id = payload.get("conversation_id")
    if type(conversation_id) is not int or conversation_id < 1:
        return jsonify(success=False, error="Choose or create a conversation first."), 400
    request_key = payload.get("request_id", uuid.uuid4().hex)
    if not isinstance(request_key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", request_key):
        return jsonify(success=False, error="Use a valid request ID."), 400
    input_mode = payload.get("input_mode", "text")
    if input_mode not in ("text", "voice") or type(payload.get("use_gemini", True)) is not bool:
        abort(400)
    use_gemini = bool(session.get("gemini_consent_v1") and payload.get("use_gemini", True))
    result = ChatProcessingService().process(conversation_id, text, request_key, input_mode, use_gemini, current_user.id)
    return jsonify(result)
