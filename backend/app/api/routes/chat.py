import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai_logging import customer_input_for_log, log_ai_event
from app.agentic.observability import OrchestrationRecorder
from app.agentic.memory import build_memory_scope, get_shopping_memory_store
from app.agentic.orchestrator import ShoppingOrchestrator
from app.agentic.state import ShoppingAgentState
from app.agentic.tools import CommerceToolRegistry
from app.config import settings
from app.database import get_db
from app.models import AIConversation, AIMessage, MessageRole, User
from app.security import create_session_token

from ..schemas import ChatRequest, ChatResponse
from .auth import SESSION_COOKIE_NAME, get_optional_current_user


router = APIRouter(tags=["assistant"])
CONVERSATION_COOKIE_NAME = "shopy_ai_conversation"
STREAM_WORD_DELAY_SECONDS = 0.030


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
    conversation: AIConversation,
    memory_session_scope: str,
) -> ChatOrchestrationTrace:
    """Run the widget through the only permitted response-generation path."""

    recorder = OrchestrationRecorder(db, request_id=request_id, user=user, conversation=conversation)
    registry = CommerceToolRegistry(db, request_id=request_id, recorder=recorder)
    try:
        state = await ShoppingOrchestrator(
            tool_registry=registry,
            recorder=recorder,
            memory_store=get_shopping_memory_store(),
        ).ainvoke(
            user_request,
            state_overrides={"memory_session_scope": memory_session_scope},
            defer_finish=True,
        )
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
            model=getattr(settings, "active_llm_model", settings.gemini_model),
            context={"channel": "web_chat"},
        )
        db.add(conversation)
    elif user is not None and conversation.user_id is None:
        conversation.user = user

    return conversation, token


def persist_exchange(
    db: Session,
    conversation: AIConversation,
    conversation_token: str,
    customer_message: str,
    assistant_reply: str,
    attachments: list[dict[str, object]],
    request_id: str,
    input_type: str,
    input_payload: dict[str, object],
) -> tuple[AIConversation, str]:
    conversation.messages.extend(
        [
            AIMessage(
                role=MessageRole.USER,
                content=customer_message,
                input_type=input_type,
                input_payload=input_payload,
                processing_metadata={"request_id": request_id, "channel": "web_chat"},
                extra_data={"request_id": request_id},
            ),
            AIMessage(
                role=MessageRole.ASSISTANT,
                content=assistant_reply,
                model=getattr(settings, "active_llm_model", settings.gemini_model),
                processing_metadata={"request_id": request_id, "response_source": "audited_orchestrator"},
                extra_data={"request_id": request_id, "attachments": attachments},
            ),
        ]
    )
    db.commit()
    db.refresh(conversation)
    return conversation, conversation_token


@router.post("/api/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    http_response: Response,
    conversation_token: Annotated[
        str | None, Cookie(alias=CONVERSATION_COOKIE_NAME)
    ] = None,
    auth_session_token: Annotated[
        str | None, Cookie(alias=SESSION_COOKIE_NAME)
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
        input_type=payload.input_type,
        customer_input=customer_input_for_log(latest_customer_input),
        conversation_messages=len(payload.messages),
    )
    if not (getattr(settings, "qwen_api_key", "") or settings.gemini_api_key):
        log_ai_event("text.failed", request_id=request_id, reason="llm_api_key_missing")
        raise HTTPException(status_code=503, detail="No LLM API key is configured.")

    conversation, active_conversation_token = get_or_create_conversation(
        db=db,
        token=conversation_token,
        user=current_user,
        first_message=latest_customer_input.strip(),
    )
    memory_session_scope = build_memory_scope(
        user_id=current_user.id if current_user is not None else None,
        auth_session_token=auth_session_token,
        conversation_token=active_conversation_token,
    )

    try:
        trace = await start_chat_orchestration(
            db,
            request_id=request_id,
            user=current_user,
            user_request=latest_customer_input.strip(),
            conversation=conversation,
            memory_session_scope=memory_session_scope,
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
            conversation=conversation,
            conversation_token=active_conversation_token,
            customer_message=latest_customer_input.strip(),
            assistant_reply=reply,
            attachments=attachments,
            request_id=request_id,
            input_type=payload.input_type,
            input_payload={"text": latest_customer_input.strip(), **payload.input_payload},
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
        input_type=payload.input_type,
        customer_input=customer_input_for_log(latest_customer_input),
        ai_process="The Shopping Orchestrator generated a tool-backed response and the Auditor approved its catalog claims.",
        final_output=reply,
        elapsed_ms=round((time.perf_counter() - started_at) * 1000),
    )
    mission = {
        "goal": trace.state.get("goal"),
        "mission_type": trace.state.get("mission_type"),
        "recommendation_mode": trace.state.get("recommendation_mode"),
        "budget": trace.state.get("budget"),
        "preferences": trace.state.get("preferences", []),
        "key_requirements": trace.state.get("key_requirements", []),
        "owned_items": trace.state.get("owned_items", []),
        "priorities": trace.state.get("priorities", []),
    }
    workspace = {
        "bundle": trace.state.get("bundle"),
        "compatibility": trace.state.get("compatibility_results", []),
        "product_rankings": trace.state.get("product_rankings", []),
        "audit": trace.state.get("audit_result", {}),
        "fulfillment_gaps": trace.state.get("fulfillment_gaps", []),
        "unfulfilled_requirements": trace.state.get("unfulfilled_requirements", []),
    }
    return ChatResponse(
        reply=reply, conversation_id=conversation.id, attachments=attachments,
        mission=mission, workspace=workspace,
    )


def _stream_event(event_type: str, **payload: object) -> bytes:
    """Encode one independently parseable chat-stream event."""
    return (json.dumps({"type": event_type, **payload}, ensure_ascii=False, default=str) + "\n").encode()


@router.post("/api/chat/stream")
async def stream_chat(
    payload: ChatRequest,
    conversation_token: Annotated[
        str | None, Cookie(alias=CONVERSATION_COOKIE_NAME)
    ] = None,
    auth_session_token: Annotated[
        str | None, Cookie(alias=SESSION_COOKIE_NAME)
    ] = None,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream an audited chat response as word-preserving NDJSON deltas."""
    latest_customer_input = next(
        (message.content for message in reversed(payload.messages) if message.role == "user"),
        "",
    )
    if not latest_customer_input.strip():
        raise HTTPException(status_code=400, detail="A customer message is required.")
    if not (getattr(settings, "qwen_api_key", "") or settings.gemini_api_key):
        raise HTTPException(status_code=503, detail="No LLM API key is configured.")

    # Resolve the session before returning the StreamingResponse so its HttpOnly
    # cookie is present in the initial headers. The regular chat path reuses the
    # same pending conversation through this token and commits it with the reply.
    _, active_conversation_token = get_or_create_conversation(
        db=db,
        token=conversation_token,
        user=current_user,
        first_message=latest_customer_input.strip(),
    )
    db.flush()

    async def events():
        yield _stream_event("start")
        try:
            result = await chat(
                payload=payload,
                http_response=Response(),
                conversation_token=active_conversation_token,
                auth_session_token=auth_session_token,
                current_user=current_user,
                db=db,
            )
        except HTTPException as error:
            db.rollback()
            yield _stream_event("error", detail=str(error.detail))
            return
        except Exception:
            db.rollback()
            yield _stream_event(
                "error",
                detail="The shopping assistant could not complete a response. Please try again.",
            )
            return

        for word in re.findall(r"\S+\s*", result.reply):
            yield _stream_event("delta", delta=word)
            await asyncio.sleep(STREAM_WORD_DELAY_SECONDS)
        completed = result.model_dump(mode="json")
        completed.pop("reply", None)
        yield _stream_event("done", **completed)

    response = StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )
    set_conversation_cookie(response, active_conversation_token)
    return response
