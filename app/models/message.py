from app.extensions import db
from app.models.user import utcnow


class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id", ondelete="CASCADE"),
                                nullable=False, index=True)
    sender = db.Column(db.String(10), nullable=False)
    content = db.Column(db.Text, nullable=False)
    sentiment = db.Column(db.String(10), nullable=False, default="neutral")
    sentiment_score = db.Column(db.Float, nullable=False, default=0)
    risk_level = db.Column(db.String(10), nullable=False, default="normal")
    topic = db.Column(db.String(30), nullable=False, default="general")
    recommendations = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    conversation = db.relationship("Conversation", back_populates="messages")
    __table_args__ = (
        db.CheckConstraint("sender IN ('user', 'bot')", name="valid_sender"),
        db.CheckConstraint("sentiment IN ('positive', 'negative', 'neutral')", name="valid_sentiment"),
        db.CheckConstraint("risk_level IN ('normal', 'high')", name="valid_risk"),
    )

    def to_dict(self):
        return {"id": self.id, "sender": self.sender, "content": self.content,
                "sentiment": {"label": self.sentiment, "score": self.sentiment_score},
                "risk_level": self.risk_level, "topic": self.topic,
                "recommendations": self.recommendations, "created_at": self.created_at.isoformat() + "Z"}
