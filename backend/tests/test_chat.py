from importlib import import_module
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import get_db
from app.main import app
from app.models import AIConversation, AIMessage, MessageRole, User


class FakeGeminiResponse:
    is_error = False
    status_code = 200

    def json(self):
        return {
            "candidates": [
                {"content": {"parts": [{"text": "Here is a saved recommendation."}]}}
            ]
        }


class FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    async def post(self, *args, **kwargs):
        return FakeGeminiResponse()


def test_authenticated_chat_is_persisted_and_continued(db_session, monkeypatch):
    chat_route = import_module("app.api.routes.chat")
    monkeypatch.setattr(chat_route.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(
        chat_route,
        "settings",
        SimpleNamespace(
            gemini_api_key="test-key",
            gemini_model="test-model",
            auth_session_days=7,
            auth_cookie_secure=False,
        ),
    )

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        registration = client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Chat Member",
                "email": "chat@example.com",
                "password": "Chatpass2026!",
            },
        )
        assert registration.status_code == 201

        first = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "Find a desk lamp"}]},
        )
        assert first.status_code == 200
        assert first.json()["reply"] == "Here is a saved recommendation."
        assert first.json()["conversation_id"]
        assert "shopy_ai_conversation" in first.cookies

        second = client.post(
            "/api/chat",
            json={
                "messages": [
                    {"role": "user", "content": "Find a desk lamp"},
                    {"role": "assistant", "content": "Here is a saved recommendation."},
                    {"role": "user", "content": "Show me a cheaper one"},
                ]
            },
        )
        assert second.status_code == 200
        assert second.json()["conversation_id"] == first.json()["conversation_id"]

        conversation = db_session.scalar(select(AIConversation))
        user = db_session.scalar(select(User).where(User.email == "chat@example.com"))
        assert conversation is not None
        assert conversation.user_id == user.id
        assert conversation.title == "Find a desk lamp"
        assert db_session.scalar(select(func.count()).select_from(AIConversation)) == 1
        assert db_session.scalar(select(func.count()).select_from(AIMessage)) == 4
        assert [message.role for message in conversation.messages] == [
            MessageRole.USER,
            MessageRole.ASSISTANT,
            MessageRole.USER,
            MessageRole.ASSISTANT,
        ]
    finally:
        app.dependency_overrides.clear()


def test_anonymous_chat_is_persisted_without_a_user(db_session, monkeypatch):
    chat_route = import_module("app.api.routes.chat")
    monkeypatch.setattr(chat_route.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(
        chat_route,
        "settings",
        SimpleNamespace(
            gemini_api_key="test-key",
            gemini_model="test-model",
            auth_session_days=7,
            auth_cookie_secure=False,
        ),
    )

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "Recommend a chair"}]},
        )

        assert response.status_code == 200
        conversation = db_session.scalar(select(AIConversation))
        assert conversation is not None
        assert conversation.user_id is None
        assert len(conversation.messages) == 2
    finally:
        app.dependency_overrides.clear()
