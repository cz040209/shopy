import time
from dataclasses import dataclass
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai_logging import customer_input_for_log, log_ai_event
from app.agentic.observability import OrchestrationRecorder
from app.agentic.orchestrator import ShoppingOrchestrator
from app.agentic.state import ShoppingAgentState
from app.agentic.tools import CommerceToolRegistry
from app.config import settings
from app.database import get_db
from app.models import AIConversation, AIMessage, MessageRole, User
from app.security import create_session_token

from ..schemas import ChatRequest, ChatResponse
from .auth import get_optional_current_user


router = APIRouter(tags=["assistant"])
CONVERSATION_COOKIE_NAME = "shopy_ai_conversation"


@dataclass
class ChatOrchestrationTrace:
    """A deferred run that is completed with the customer-facing chat reply."""

    recorder: OrchestrationRecorder
    state: ShoppingAgentState


async def start_chat_orchestration(
    db: Session,
    *,
    request_id: str,
    user: User | None,
    user_request: str,
) -> ChatOrchestrationTrace:
    """Run the widget through the only permitted response-generation path."""

    recorder = OrchestrationRecorder(db, request_id=request_id, user=user)
    registry = CommerceToolRegistry(db, request_id=request_id, recorder=recorder)
    try:
        state = await ShoppingOrchestrator(
            tool_registry=registry,
            recorder=recorder,
        ).ainvoke(user_request, defer_finish=True)
    except Exception as error:
        if recorder.run is not None and recorder.run.status == "running":
            recorder.fail(error)
        log_ai_event("agent.chat_trace.failed", request_id=request_id)
        raise
    return ChatOrchestrationTrace(recorder=recorder, state=state)


def finish_chat_orchestration(
    trace: ChatOrchestrationTrace,
    *,
    reply: str,
    conversation_id: str,
) -> None:
    trace.recorder.finish(
        trace.state,
        final_response=reply,
        response_context={"conversation_id": conversation_id, "response_source": "audited_orchestrator"},
    )


def fail_chat_orchestration(trace: ChatOrchestrationTrace, error: Exception) -> None:
    trace.recorder.fail(error)


def set_conversation_cookie(response: Response, token: str) -> None:
    max_age = settings.auth_session_days * 24 * 60 * 60
    response.set_cookie(
        key=CONVERSATION_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


def get_or_create_conversation(
    db: Session,
    token: str | None,
    user: User | None,
    first_message: str,
) -> tuple[AIConversation, str]:
    conversation = None
    if token:
        conversation = db.scalar(
            select(AIConversation).where(AIConversation.session_token == token)
        )
        if conversation is not None:
            belongs_to_user = user is not None and conversation.user_id in (None, user.id)
            belongs_to_guest = user is None and conversation.user_id is None
            if not belongs_to_user and not belongs_to_guest:
                conversation = None

    if conversation is None:
        token = create_session_token()
        conversation = AIConversation(
            user=user,
            session_token=token,
            title=first_message[:220],
            model=settings.gemini_model,
            context={"channel": "web_chat"},
        )
        db.add(conversation)
    elif user is not None and conversation.user_id is None:
        conversation.user = user

    return conversation, token


def persist_exchange(
    db: Session,
    conversation_token: str | None,
    user: User | None,
    customer_message: str,
    assistant_reply: str,
    attachments: list[dict[str, object]],
    request_id: str,
) -> tuple[AIConversation, str]:
    conversation, token = get_or_create_conversation(
        db=db,
        token=conversation_token,
        user=user,
        first_message=customer_message,
    )
    conversation.messages.extend(
        [
            AIMessage(
                role=MessageRole.USER,
                content=customer_message,
                extra_data={"request_id": request_id, "input_type": "text"},
            ),
            AIMessage(
                role=MessageRole.ASSISTANT,
                content=assistant_reply,
                model=settings.gemini_model,
                extra_data={"request_id": request_id, "attachments": attachments},
            ),
        ]
    )
    db.commit()
    db.refresh(conversation)
    return conversation, token


@router.post("/api/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    http_response: Response,
    conversation_token: Annotated[
        str | None, Cookie(alias=CONVERSATION_COOKIE_NAME)
    ] = None,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    request_id = uuid4().hex[:12]
    started_at = time.perf_counter()
    latest_customer_input = next(
        (message.content for message in reversed(payload.messages) if message.role == "user"),
        "",
    )
    if not latest_customer_input.strip():
        raise HTTPException(status_code=400, detail="A customer message is required.")
    log_ai_event(
        "text.received",
        request_id=request_id,
        input_type="text",
        customer_input=customer_input_for_log(latest_customer_input),
        conversation_messages=len(payload.messages),
    )
    if not settings.gemini_api_key:
        log_ai_event("text.failed", request_id=request_id, reason="gemini_api_key_missing")
        raise HTTPException(status_code=503, detail="The Gemini API key is not configured.")

    try:
        trace = await start_chat_orchestration(
            db,
            request_id=request_id,
            user=current_user,
            user_request=latest_customer_input.strip(),
        )
    except Exception as error:
        log_ai_event(
            "text.failed",
            request_id=request_id,
            reason="orchestration_failed",
            elapsed_ms=round((time.perf_counter() - started_at) * 1000),
        )
        raise HTTPException(status_code=503, detail="The shopping assistant could not complete a verified response. Please try again.") from error

    if trace.state.get("audit_result", {}).get("status") != "pass" or not trace.state.get("final_response"):
        trace.recorder.finish(trace.state)
        log_ai_event("text.failed", request_id=request_id, reason="response_audit_failed")
        raise HTTPException(status_code=503, detail="The shopping assistant could not validate a response. Please try again.")

    reply = str(trace.state["final_response"])
    attachments = list(trace.state.get("attachments", []))

    try:
        conversation, active_conversation_token = persist_exchange(
            db=db,
            conversation_token=conversation_token,
            user=current_user,
            customer_message=latest_customer_input.strip(),
            assistant_reply=reply,
            attachments=attachments,
            request_id=request_id,
        )
    except SQLAlchemyError as error:
        db.rollback()
        fail_chat_orchestration(trace, error)
        log_ai_event(
            "text.failed",
            request_id=request_id,
            reason="conversation_persistence_failed",
            elapsed_ms=round((time.perf_counter() - started_at) * 1000),
        )
        raise HTTPException(
            status_code=503,
            detail="The reply was generated, but the conversation could not be saved. Please try again.",
        ) from error

    set_conversation_cookie(http_response, active_conversation_token)
    finish_chat_orchestration(
        trace,
        reply=reply,
        conversation_id=str(conversation.id),
    )
    log_ai_event(
        "text.completed",
        request_id=request_id,
        input_type="text",
        customer_input=customer_input_for_log(latest_customer_input),
        ai_process="The Shopping Orchestrator generated a tool-backed response and the Auditor approved its catalog claims.",
        final_output=reply,
        elapsed_ms=round((time.perf_counter() - started_at) * 1000),
    )
    return ChatResponse(reply=reply, conversation_id=conversation.id, attachments=attachments)
