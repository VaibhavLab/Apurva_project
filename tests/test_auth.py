import pytest
from werkzeug.security import check_password_hash

from app.extensions import db
from app.models import User
from tests.conftest import login, register, token


def test_registration_hashes_password_and_redirects(client, app):
    response = register(client)
    assert response.status_code == 302
    assert response.location.endswith("/login")
    with app.app_context():
        user = db.session.scalar(db.select(User))
        assert user.password_hash != "correct-horse-123"
        assert check_password_hash(user.password_hash, "correct-horse-123")
        assert user.created_at is not None


@pytest.mark.parametrize("username,email,error", [
    ("ALEX", "other@example.com", b"username is already taken"),
    ("other", "ALEX@example.com", b"email already exists"),
])
def test_duplicate_identity(client, username, email, error):
    register(client)
    response = register(client, username, email)
    assert response.status_code == 400
    assert error in response.data


@pytest.mark.parametrize("overrides", [{"full_name": ""}, {"username": "ab"}, {"username": "bad name"},
    {"email": "bad-email"}, {"password": "short"}, {"confirm_password": "different"},
    {"password": "x" * 129, "confirm_password": "x" * 129}])
def test_validation(client, overrides):
    assert register(client, **overrides).status_code == 400


@pytest.mark.parametrize("identifier", ["alex", "ALEX", "alex@example.com"])
def test_login(client, identifier):
    register(client)
    assert login(client, identifier).location.endswith("/chat")
    assert client.get("/chat").status_code == 200


def test_invalid_password(client):
    register(client)
    assert login(client, password="wrong").status_code == 400
    assert client.get("/chat").status_code == 302


def test_unknown_account(client):
    assert login(client, identifier="missing").status_code == 400


def test_logout(account, headers):
    assert account.get("/logout").status_code == 405
    assert account.post("/logout", headers=headers).status_code == 302
    assert account.get("/chat").status_code == 302
    assert account.get("/api/conversations").status_code == 401


@pytest.mark.parametrize("path", ["/chat", "/conversations/1"])
def test_protected_pages(client, path):
    assert client.get(path).location.endswith("/login")


def test_csrf_enforced(client, account, conversation):
    assert account.post("/api/chat", json={"conversation_id": conversation, "message": "Hello"}).status_code == 400
    assert account.delete(f"/api/conversations/{conversation}").status_code == 400
    assert account.post("/logout").status_code == 400


def test_auth_csrf(client):
    assert client.post("/register", data={}).status_code == 400
    assert client.post("/login", data={}).status_code == 400


def test_session_cookie_flags(account):
    response = account.get("/chat")
    assert "HttpOnly" in response.headers["Set-Cookie"]
    assert "SameSite=Lax" in response.headers["Set-Cookie"]
    assert response.headers["Cache-Control"] == "no-store"
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]


def test_external_next_is_ignored(client):
    register(client)
    response = client.post("/login?next=https://example.com", data={"identifier": "alex", "password": "correct-horse-123", "csrf_token": token(client)})
    assert response.location.endswith("/chat")
