from app.extensions import db
from app.models.user import utcnow


class Conversation(db.Model):
    __tablename__ = "conversations"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(100), default="New Conversation", nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    user = db.relationship("User", back_populates="conversations")
    messages = db.relationship("Message", back_populates="conversation", cascade="all, delete-orphan",
                               order_by="Message.id")

    def to_dict(self, include_messages=False):
        result = {"id": self.id, "title": self.title,
                  "created_at": self.created_at.isoformat() + "Z",
                  "updated_at": self.updated_at.isoformat() + "Z"}
        if include_messages:
            result["messages"] = [message.to_dict() for message in self.messages]
        return result
