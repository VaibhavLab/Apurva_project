import re

import pytest

from app import create_app
from app.extensions import db


@pytest.fixture
def app():
    application = create_app({"TESTING": True, "SECRET_KEY": "test-only-not-for-deployment",
                              "SQLALCHEMY_DATABASE_URI": "sqlite://", "SESSION_COOKIE_SECURE": False,
                              "PRODUCTION": False})
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


def token(client, path="/login"):
    page = client.get(path)
    return re.search(r'name="csrf-token" content="([^"]+)"', page.text).group(1)


def register(client, username="alex", email="alex@example.com", **overrides):
    data = {"full_name": "Alex Rivera", "username": username, "email": email,
            "password": "correct-horse-123", "confirm_password": "correct-horse-123",
            "csrf_token": token(client, "/register")}
    data.update(overrides)
    return client.post("/register", data=data)


def login(client, identifier="alex", password="correct-horse-123"):
    return client.post("/login", data={"identifier": identifier, "password": password,
                                       "csrf_token": token(client)})


@pytest.fixture
def account(client):
    assert register(client).status_code == 302
    assert login(client).status_code == 302
    return client


@pytest.fixture
def headers(account):
    return {"X-CSRFToken": token(account, "/chat")}


@pytest.fixture
def conversation(account, headers):
    return account.post("/api/conversations/new", headers=headers).json["conversation_id"]
