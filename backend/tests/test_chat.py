from importlib import import_module
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import get_db
from app.main import app
from app.models import AIConversation, AIMessage, MessageRole, OrchestrationRun, User


class FakeShoppingOrchestrator:
    def __init__(self, *, tool_registry, recorder, memory_store=None):
        self.recorder = recorder

    async def ainvoke(self, user_request, *, state_overrides=None, defer_finish=False):
        assert defer_finish is True
        state = {
            "user_request": user_request,
            "run_id": self.recorder.request_id,
            "audit_result": {"status": "pass", "errors": []},
            "final_response": f"Verified response for {user_request}.",
        }
        self.recorder.start(state)
        self.recorder.record(
            "node_completed",
            node_name="intent_agent",
            output_data={"goal": "desk lamp"},
        )
        return state


def install_fake_orchestrator(monkeypatch, chat_route):
    monkeypatch.setattr(chat_route, "ShoppingOrchestrator", FakeShoppingOrchestrator)


def test_authenticated_chat_is_persisted_and_continued(db_session, monkeypatch):
    chat_route = import_module("app.api.routes.chat")
    install_fake_orchestrator(monkeypatch, chat_route)
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
        assert first.json()["reply"] == "Verified response for Find a desk lamp."
        assert first.json()["conversation_id"]
        assert "shopy_ai_conversation" in first.cookies

        second = client.post(
            "/api/chat",
            json={
                "messages": [
                    {"role": "user", "content": "Find a desk lamp"},
                    {"role": "assistant", "content": "Verified response for Find a desk lamp."},
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
        first_input = conversation.messages[0]
        assert first_input.input_type == "text"
        assert first_input.input_payload == {"text": "Find a desk lamp"}
        assert first_input.processing_metadata["channel"] == "web_chat"
    finally:
        app.dependency_overrides.clear()


def test_anonymous_chat_is_persisted_without_a_user(db_session, monkeypatch):
    chat_route = import_module("app.api.routes.chat")
    install_fake_orchestrator(monkeypatch, chat_route)
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


def test_voice_transcript_is_persisted_with_its_modality_metadata(db_session, monkeypatch):
    chat_route = import_module("app.api.routes.chat")
    install_fake_orchestrator(monkeypatch, chat_route)
    monkeypatch.setattr(
        chat_route,
        "settings",
        SimpleNamespace(gemini_api_key="test-key", gemini_model="test-model", auth_session_days=7, auth_cookie_secure=False),
    )

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).post(
            "/api/chat",
            json={
                "messages": [{"role": "user", "content": "Find a blue sofa"}],
                "input_type": "voice",
                "input_payload": {"transcript": "Find a blue sofa", "language": "en", "duration_seconds": 2.4},
            },
        )
        assert response.status_code == 200
        message = db_session.scalar(select(AIMessage).where(AIMessage.role == MessageRole.USER))
        assert message is not None
        assert message.input_type == "voice"
        assert message.input_payload["duration_seconds"] == 2.4
        assert message.input_payload["text"] == "Find a blue sofa"
    finally:
        app.dependency_overrides.clear()


def test_chat_creates_a_completed_orchestration_trace(db_session, monkeypatch):
    chat_route = import_module("app.api.routes.chat")
    install_fake_orchestrator(monkeypatch, chat_route)
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
            json={"messages": [{"role": "user", "content": "Find a desk lamp"}]},
        )

        assert response.status_code == 200
        run = db_session.scalar(select(OrchestrationRun))
        assert run is not None
        assert run.status == "completed"
        assert run.final_response == "Verified response for Find a desk lamp."
        assert [event.event_type for event in run.events] == [
            "run_started",
            "node_completed",
            "assistant_response_generated",
            "run_finished",
        ]
        assert run.events[-2].output_data["response_source"] == "audited_orchestrator"
    finally:
        app.dependency_overrides.clear()


def test_chat_does_not_fall_back_when_orchestration_fails(db_session, monkeypatch):
    chat_route = import_module("app.api.routes.chat")

    class FailingShoppingOrchestrator:
        def __init__(self, *, tool_registry, recorder, memory_store=None):
            self.recorder = recorder

        async def ainvoke(self, user_request, *, state_overrides=None, defer_finish=False):
            self.recorder.start({"user_request": user_request, "run_id": self.recorder.request_id})
            raise RuntimeError("intent agent unavailable")

    monkeypatch.setattr(chat_route, "ShoppingOrchestrator", FailingShoppingOrchestrator)
    monkeypatch.setattr(
        chat_route,
        "settings",
        SimpleNamespace(gemini_api_key="test-key", gemini_model="test-model", auth_session_days=7, auth_cookie_secure=False),
    )

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).post("/api/chat", json={"messages": [{"role": "user", "content": "Find a desk lamp"}]})

        assert response.status_code == 503
        assert db_session.scalar(select(func.count()).select_from(AIMessage)) == 0
        run = db_session.scalar(select(OrchestrationRun))
        assert run is not None and run.status == "failed"
    finally:
        app.dependency_overrides.clear()
