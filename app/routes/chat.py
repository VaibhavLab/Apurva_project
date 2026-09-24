from flask import Blueprint, abort, current_app, jsonify, render_template, request
from flask_login import login_required

from app.extensions import db
from app.models import Message
from app.models.user import utcnow
from app.routes.conversations import owned_conversation
from app.services.chatbot_service import ChatbotService
from app.services.intent_service import IntentService
from app.services.recommendation_service import RecommendationService
from app.services.safety_service import SafetyService
from app.services.sentiment_service import SentimentService

chat_bp = Blueprint("chat", __name__)
sentiment_service = SentimentService()


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
    conversation = owned_conversation(conversation_id, lock=True)
    turn = db.session.scalar(db.select(db.func.count(Message.id)).where(
        Message.conversation_id == conversation.id, Message.sender == "bot"))
    user_message = Message(conversation=conversation, sender="user", content=text)
    db.session.add(user_message)
    # Flush records the user message first; a single commit keeps the entire turn atomic.
    db.session.flush()
    risk = SafetyService().analyze(text)["risk_level"]
    sentiment = sentiment_service.analyze(text)
    intent_service = IntentService()
    topic = intent_service.detect_topic(text)
    reply = ChatbotService().respond(text, sentiment, topic, risk, turn)
    recommendations = [] if risk == "high" else RecommendationService().recommend(topic, sentiment["label"])
    user_message.sentiment = sentiment["label"]
    user_message.sentiment_score = sentiment["score"]
    user_message.risk_level = risk
    user_message.topic = topic
    bot_message = Message(conversation=conversation, sender="bot", content=reply,
                          sentiment=sentiment["label"], sentiment_score=sentiment["score"],
                          risk_level=risk, topic=topic, recommendations=recommendations)
    db.session.add(bot_message)
    if conversation.title == "New Conversation" and intent_service.detect_intent(text) not in {"greet", "thanks", "goodbye"}:
        conversation.title = intent_service.title(text, sentiment["label"], risk)
    conversation.updated_at = utcnow()
    db.session.commit()
    return jsonify(success=True, conversation_id=conversation.id, title=conversation.title,
                   reply=reply, sentiment=sentiment, risk_level=risk, topic=topic,
                   recommendations=recommendations, messages=[user_message.to_dict(), bot_message.to_dict()])
