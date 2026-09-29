from sqlalchemy import inspect, text
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from app.extensions import db
from app.migrations import upgrade_voice_schema
from app.models import ChatRequest, Message
from tests.test_chat import send


def test_additive_migration_preserves_data_and_is_repeatable(app, account, headers, conversation):
    data = send(account, headers, conversation, "My original conversation.").json
    with app.app_context():
        db.session.remove()
        # Simulate the actual pre-feature schema while preserving the stored turn.
        with db.engine.begin() as connection:
            connection.execute(text("DROP TABLE chat_requests"))
            connection.execute(text("ALTER TABLE messages DROP COLUMN input_mode"))
            connection.execute(text("ALTER TABLE messages DROP COLUMN provider"))
        for _ in range(2):
            upgrade_voice_schema()
        messages = db.session.scalars(db.select(Message).order_by(Message.id)).all()
        assert [row.id for row in messages] == [row["id"] for row in data["messages"]]
        assert [row.content for row in messages] == [row["content"] for row in data["messages"]]
        assert all(row.input_mode == "text" and row.provider == "local" for row in messages)
        assert inspect(db.engine).has_table("chat_requests")
    assert account.get(f"/api/conversations/{conversation}").status_code == 200
    assert send(account, headers, conversation, "After migration").status_code == 200


def test_mysql_schema_has_durable_uniqueness_and_metadata():
    request_ddl = str(CreateTable(ChatRequest.__table__).compile(dialect=mysql.dialect()))
    message_ddl = str(CreateTable(Message.__table__).compile(dialect=mysql.dialect()))
    assert "UNIQUE (conversation_id, request_key)" in request_ddl
    assert "UNIQUE (active_conversation_id)" in request_ddl
    assert "ON DELETE CASCADE" in request_ddl
    assert "input_mode" in message_ddl and "provider" in message_ddl
