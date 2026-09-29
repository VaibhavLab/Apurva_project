"""Resumable additive migration for the pre-voice SQLite/MySQL schema."""
from sqlalchemy import inspect, text

from app.extensions import db


def upgrade_voice_schema():
    engine = db.engine
    if engine.dialect.name not in {"sqlite", "mysql"}:
        raise RuntimeError("The voice migration supports SQLite and MySQL.")
    if inspect(engine).has_table("messages"):
        columns = {column["name"] for column in inspect(engine).get_columns("messages")}
        # Static DDL only. Each MySQL ALTER commits independently; rerunning is safe.
        additions = {
            "input_mode": "ALTER TABLE messages ADD COLUMN input_mode VARCHAR(10) NOT NULL DEFAULT 'text'",
            "provider": "ALTER TABLE messages ADD COLUMN provider VARCHAR(20) NOT NULL DEFAULT 'local'",
        }
        for name, statement in additions.items():
            if name not in columns:
                with engine.begin() as connection:
                    connection.execute(text(statement))
    db.create_all()
