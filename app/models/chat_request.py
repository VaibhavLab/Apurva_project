from app.extensions import db
from app.models.user import utcnow


class ChatRequest(db.Model):
    """A short-lived lease plus durable idempotency receipt; no audio is stored."""
    __tablename__ = "chat_requests"
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    request_key = db.Column(db.String(64), nullable=False)
    fingerprint = db.Column(db.String(64), nullable=False)
    lease_token = db.Column(db.String(32), nullable=False)
    status = db.Column(db.String(12), nullable=False, default="pending")
    # NULL values let completed turns coexist; a non-NULL value serializes pending turns.
    active_conversation_id = db.Column(db.Integer, unique=True, nullable=True)
    updated_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    response = db.Column(db.JSON, nullable=True)
    conversation = db.relationship("Conversation", back_populates="requests")
    __table_args__ = (db.UniqueConstraint("conversation_id", "request_key", name="uq_chat_request_key"),)
