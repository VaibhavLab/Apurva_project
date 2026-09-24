import os
from datetime import timedelta


class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    MAX_CONTENT_LENGTH = 32 * 1024
    MAX_MESSAGE_LENGTH = 4000
    WTF_CSRF_TIME_LIMIT = 8 * 60 * 60

    @staticmethod
    def environment() -> dict:
        return {
            "SECRET_KEY": os.getenv("SECRET_KEY"),
            "SQLALCHEMY_DATABASE_URI": os.getenv("DATABASE_URL") or "sqlite:///mental_health_chatbot.db",
            "SESSION_COOKIE_SECURE": os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
            "PRODUCTION": os.getenv("FLASK_ENV") == "production",
        }
