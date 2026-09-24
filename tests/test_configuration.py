import pytest
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from app import create_app
from app.config import Config
from app.extensions import db


def test_mysql_configuration_and_schema_compile(app, monkeypatch):
    url = "mysql+pymysql://mindcare:example@localhost/mental_health_chatbot"
    monkeypatch.setenv("DATABASE_URL", url)
    assert Config.environment()["SQLALCHEMY_DATABASE_URI"] == url
    with app.app_context():
        ddl = "\n".join(str(CreateTable(table).compile(dialect=mysql.dialect())) for table in db.metadata.sorted_tables)
    assert "AUTO_INCREMENT" in ddl
    assert "recommendations JSON" in ddl
    assert "ON DELETE CASCADE" in ddl


def test_sqlite_fallback(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert Config.environment()["SQLALCHEMY_DATABASE_URI"] == "sqlite:///mental_health_chatbot.db"


def test_production_requires_real_secret():
    with pytest.raises(RuntimeError, match="strong SECRET_KEY"):
        create_app({"SECRET_KEY": "change-this-secret-key", "PRODUCTION": True})
