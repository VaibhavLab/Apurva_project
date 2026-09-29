import hashlib
import uuid
from datetime import timedelta

from flask import abort, current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import ChatRequest, Message
from app.models.user import utcnow
from app.routes.conversations import owned_conversation
from app.services.chatbot_service import ChatbotService
from app.services.gemini_service import GeminiService, ProviderError
from app.services.intent_service import IntentService
from app.services.recommendation_service import RecommendationService
from app.services.safety_service import SafetyService
from app.services.sentiment_service import SentimentService

sentiment_service = SentimentService()


class ChatProcessingService:
    """Reserve briefly, generate outside a DB transaction, then save a whole turn."""

    def _reserve(self, conversation_id, request_key, fingerprint):
        owned_conversation(conversation_id, lock=True)
        cutoff = utcnow() - timedelta(seconds=current_app.config["CHAT_REQUEST_LEASE_SECONDS"])
        db.session.execute(db.update(ChatRequest).where(
            ChatRequest.conversation_id == conversation_id, ChatRequest.status == "pending",
            ChatRequest.updated_at < cutoff).values(status="failed", active_conversation_id=None))
        receipt = db.session.scalar(db.select(ChatRequest).filter_by(
            conversation_id=conversation_id, request_key=request_key))
        if receipt:
            if receipt.fingerprint != fingerprint:
                db.session.rollback()
                raise ProviderError("This request ID was already used for a different message.", "request_conflict", 409)
            if receipt.status == "completed":
                response = receipt.response
                db.session.rollback()
                return None, response
            if receipt.status == "pending":
                db.session.rollback()
                raise ProviderError("This message is still processing. Retry the same message shortly.", "request_pending", 409)
        else:
            receipt = ChatRequest(conversation_id=conversation_id, request_key=request_key, fingerprint=fingerprint)
            db.session.add(receipt)
        lease = uuid.uuid4().hex
        receipt.lease_token = lease
        receipt.status = "pending"
        receipt.active_conversation_id = conversation_id
        receipt.updated_at = utcnow()
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise ProviderError("A message is already processing in this conversation. Please wait.", "request_pending", 409) from None
        return lease, None

    def _history(self, conversation_id):
        rows = db.session.scalars(db.select(Message).where(Message.conversation_id == conversation_id)
                                  .order_by(Message.id.desc()).limit(current_app.config["GEMINI_HISTORY_MESSAGES"])).all()
        remaining = current_app.config["GEMINI_HISTORY_CHARACTERS"]
        history = []
        for row in rows:
            if len(row.content) > remaining:
                break
            remaining -= len(row.content)
            history.append({"role": "user" if row.sender == "user" else "model", "text": row.content})
        return list(reversed(history))

    def process(self, conversation_id, text, request_key, input_mode, use_gemini, user_id):
        fingerprint = hashlib.sha256(f"{input_mode}\0{use_gemini}\0{text}".encode()).hexdigest()
        lease, replay = self._reserve(conversation_id, request_key, fingerprint)
        if replay is not None:
            return replay
        try:
            history = self._history(conversation_id)
            turn = db.session.scalar(db.select(db.func.count(Message.id)).where(
                Message.conversation_id == conversation_id, Message.sender == "bot"))
            db.session.rollback()  # No connection transaction survives a provider call.
            risk = SafetyService().analyze(text)["risk_level"]
            sentiment = sentiment_service.analyze(text)
            intents = IntentService()
            topic = intents.detect_topic(text)
            provider = "safety" if risk == "high" else "local"
            notice = None
            reply = ChatbotService().respond(text, sentiment, topic, risk, turn)
            if risk != "high" and use_gemini and GeminiService.enabled():
                try:
                    current_app.extensions["provider_limiter"].check(user_id, "chat")
                    reply = GeminiService().reply(text, history)
                    provider = "gemini"
                except ProviderError as error:
                    provider = "local_fallback"
                    notice = f"{error} This reply uses MindCare's local support engine."
            recommendations = [] if risk == "high" else RecommendationService().recommend(topic, sentiment["label"])
            conversation = owned_conversation(conversation_id, lock=True)
            claimed = db.session.execute(db.update(ChatRequest).where(
                ChatRequest.conversation_id == conversation_id, ChatRequest.request_key == request_key,
                ChatRequest.lease_token == lease, ChatRequest.status == "pending"
            ).values(status="completed", active_conversation_id=None, updated_at=utcnow()))
            if claimed.rowcount != 1:
                db.session.rollback()
                raise ProviderError("The request expired. Reopen this conversation before retrying.", "request_expired", 409)
            common = dict(conversation_id=conversation_id, sentiment=sentiment["label"],
                          sentiment_score=sentiment["score"], risk_level=risk, topic=topic, input_mode=input_mode)
            user_message = Message(sender="user", content=text, provider="user", **common)
            bot_message = Message(sender="bot", content=reply, provider=provider, recommendations=recommendations, **common)
            db.session.add_all([user_message, bot_message])
            if conversation.title == "New Conversation" and intents.detect_intent(text) not in {"greet", "thanks", "goodbye"}:
                conversation.title = intents.title(text, sentiment["label"], risk)
            conversation.updated_at = utcnow()
            db.session.flush()
            result = dict(success=True, conversation_id=conversation_id, title=conversation.title,
                          reply=reply, sentiment=sentiment, risk_level=risk, topic=topic,
                          recommendations=recommendations, provider=provider, notice=notice,
                          request_id=request_key, messages=[user_message.to_dict(), bot_message.to_dict()])
            db.session.execute(db.update(ChatRequest).where(
                ChatRequest.conversation_id == conversation_id, ChatRequest.request_key == request_key,
                ChatRequest.lease_token == lease).values(response=result))
            db.session.commit()
            return result
        except Exception:
            db.session.rollback()
            db.session.execute(db.update(ChatRequest).where(
                ChatRequest.conversation_id == conversation_id, ChatRequest.request_key == request_key,
                ChatRequest.lease_token == lease, ChatRequest.status == "pending"
            ).values(status="failed", active_conversation_id=None, updated_at=utcnow()))
            db.session.commit()
            raise
