import pytest
from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.models import Conversation, Message
from app.services.recommendation_service import RecommendationService
from tests.conftest import login, register, token


def send(account, headers, conversation, message):
    return account.post("/api/chat", headers=headers, json={"conversation_id": conversation, "message": message})


def test_full_chat_turn(account, headers, conversation, app):
    result = send(account, headers, conversation, "I feel stressed because of my exams.")
    assert result.status_code == 200
    data = result.json
    assert data["success"]
    assert data["sentiment"]["label"] == "negative"
    assert data["risk_level"] == "normal"
    assert data["topic"] == "study"
    assert 1 <= len(data["recommendations"]) <= 3
    assert data["title"] != "New Conversation"
    with app.app_context():
        records = db.session.scalars(db.select(Message).order_by(Message.id)).all()
        assert [row.sender for row in records] == ["user", "bot"]
        assert records[1].content == data["reply"]
        assert records[0].sentiment == "negative"
        assert records[1].recommendations == data["recommendations"]
    history = account.get(f"/api/conversations/{conversation}").json["conversation"]
    assert history["messages"] == data["messages"]
    assert "password" not in str(history)


def test_high_risk_skips_recommendation_service(account, headers, conversation, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Recommendations must not run for high risk")
    monkeypatch.setattr(RecommendationService, "recommend", fail)
    data = send(account, headers, conversation, "I am going to kill myself tonight").json
    assert data["risk_level"] == "high"
    assert data["recommendations"] == []
    assert "emergency" in data["reply"]


def test_response_variety(account, headers, conversation):
    first = send(account, headers, conversation, "I feel stressed").json
    second = send(account, headers, conversation, "I feel stressed").json
    assert first["reply"] != second["reply"]
    assert first["title"] == second["title"]


def test_first_meaningful_message_sets_title(account, headers, conversation):
    assert send(account, headers, conversation, "Hello").json["title"] == "New Conversation"
    assert send(account, headers, conversation, "I am stressed about my exam").json["title"] == "Study & Exam Reflection"


@pytest.mark.parametrize("message", ["", "  ", None, 12, [], "a" * 4001])
def test_invalid_message(account, headers, conversation, message, app):
    assert send(account, headers, conversation, message).status_code == 400
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Message.id))) == 0


@pytest.mark.parametrize("payload", [[], None, {"message": "Hello"}, {"message": "Hi", "conversation_id": True}, {"message": "Hi", "conversation_id": "1"}])
def test_invalid_json_shape(account, headers, payload):
    assert account.post("/api/chat", headers=headers, json=payload).status_code in (400, 415)


def test_ownership_on_all_operations(account, headers, conversation, app):
    other = app.test_client()
    register(other, "jordan", "jordan@example.com")
    login(other, "jordan")
    other_headers = {"X-CSRFToken": token(other, "/chat")}
    assert other.get(f"/api/conversations/{conversation}").status_code == 404
    assert other.get(f"/conversations/{conversation}").status_code == 404
    assert other.delete(f"/api/conversations/{conversation}", headers=other_headers).status_code == 404
    assert send(other, other_headers, conversation, "hello").status_code == 404
    assert other.get("/api/conversations").json["conversations"] == []
    assert account.get(f"/api/conversations/{conversation}").status_code == 200


def test_delete_cascades(account, headers, conversation, app):
    send(account, headers, conversation, "Hello")
    assert account.delete(f"/api/conversations/{conversation}", headers=headers).json["success"]
    assert account.get(f"/api/conversations/{conversation}").status_code == 404
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Message.id))) == 0
        assert db.session.get(Conversation, conversation) is None


def test_database_failure_rolls_back_whole_turn(account, headers, conversation, app, monkeypatch):
    def fail(*args, **kwargs):
        raise OperationalError("sensitive sql", {}, Exception("secret password"))
    monkeypatch.setattr(RecommendationService, "recommend", fail)
    response = send(account, headers, conversation, "hello")
    assert response.status_code == 503
    assert "sensitive" not in response.text and "secret" not in response.text
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Message.id))) == 0


def test_unauthenticated_api(client):
    headers = {"X-CSRFToken": token(client)}
    assert client.get("/api/conversations").status_code == 401
    assert client.get("/api/conversations/1").status_code == 401
    assert client.post("/api/conversations/new", headers=headers).status_code == 401
    assert client.post("/api/chat", headers=headers, json={"message": "hi"}).status_code == 401


def test_xss_is_returned_as_data(account, headers, conversation):
    text = '<img src=x onerror="alert(1)">'
    data = send(account, headers, conversation, text).json
    assert data["messages"][0]["content"] == text
    assert data["title"] != text


@pytest.mark.parametrize("path", ["/", "/about", "/register", "/login"])
def test_public_pages(client, path):
    assert client.get(path).status_code == 200


def test_404(client):
    page = client.get("/missing")
    assert page.status_code == 404
    assert "Looks like this conversation got lost" in page.text
