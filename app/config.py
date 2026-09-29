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
    GEMINI_HISTORY_MESSAGES = 12
    GEMINI_HISTORY_CHARACTERS = 12000
    VOICE_REQUESTS_PER_MINUTE = 6
    CHAT_REQUEST_LEASE_SECONDS = 180

    @staticmethod
    def environment() -> dict:
        return {
            "SECRET_KEY": os.getenv("SECRET_KEY"),
            "SQLALCHEMY_DATABASE_URI": os.getenv("DATABASE_URL") or "sqlite:///mental_health_chatbot.db",
            "SESSION_COOKIE_SECURE": os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
            "PRODUCTION": os.getenv("FLASK_ENV") == "production",
            "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
            "GEMINI_ENABLED": os.getenv("GEMINI_ENABLED", "false").lower() == "true",
            "VOICE_ENABLED": os.getenv("VOICE_ENABLED", "false").lower() == "true",
            "GEMINI_CHAT_MODEL": os.getenv("GEMINI_CHAT_MODEL") or "gemini-flash-latest",
            "GEMINI_TRANSCRIBE_MODEL": os.getenv("GEMINI_TRANSCRIBE_MODEL") or "gemini-flash-latest",
            "GEMINI_TTS_MODEL": os.getenv("GEMINI_TTS_MODEL") or "gemini-3.1-flash-tts-preview",
            "GEMINI_TTS_VOICE": os.getenv("GEMINI_TTS_VOICE") or "Kore",
            "GEMINI_TIMEOUT_SECONDS": min(60, max(5, int(os.getenv("GEMINI_TIMEOUT_SECONDS", "30")))),
            "VOICE_MAX_SECONDS": min(30, max(1, int(os.getenv("VOICE_MAX_SECONDS", "30")))),
            "VOICE_MAX_UPLOAD_BYTES": min(2097152, max(1024, int(os.getenv("VOICE_MAX_UPLOAD_BYTES", "2097152")))),
        }
