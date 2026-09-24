from flask import Blueprint, abort, jsonify
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Conversation

conversation_bp = Blueprint("conversations", __name__)


def owned_conversation(conversation_id: int, lock=False) -> Conversation:
    query = db.select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
    if lock:
        query = query.with_for_update()
    conversation = db.session.scalar(query)
    if conversation is None:
        abort(404)
    return conversation


@conversation_bp.get("/api/conversations")
@login_required
def list_conversations():
    rows = db.session.scalars(db.select(Conversation).filter_by(user_id=current_user.id)
                              .order_by(Conversation.updated_at.desc(), Conversation.id.desc())).all()
    return jsonify(success=True, conversations=[row.to_dict() for row in rows])


@conversation_bp.post("/api/conversations/new")
@login_required
def new_conversation():
    conversation = Conversation(user_id=current_user.id)
    db.session.add(conversation)
    db.session.commit()
    return jsonify(success=True, conversation=conversation.to_dict(), conversation_id=conversation.id), 201


@conversation_bp.get("/api/conversations/<int:conversation_id>")
@login_required
def get_conversation(conversation_id):
    return jsonify(success=True, conversation=owned_conversation(conversation_id).to_dict(include_messages=True))


@conversation_bp.delete("/api/conversations/<int:conversation_id>")
@login_required
def delete_conversation(conversation_id):
    db.session.delete(owned_conversation(conversation_id, lock=True))
    db.session.commit()
    return jsonify(success=True)
