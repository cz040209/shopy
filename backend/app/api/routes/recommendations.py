from __future__ import annotations

import hashlib
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Cookie, Depends
from sqlalchemy.orm import Session

from app.agentic.behavioral_recommendations import BehavioralRecommendationAgent
from app.agentic.llm import PrimaryLangChainChatModel
from app.agentic.memory import MemoryUnavailableError, build_memory_scope, get_shopping_memory_store
from app.agentic.observability import OrchestrationRecorder, active_recorder
from app.ai_logging import log_ai_event
from app.config import settings
from app.database import get_db
from app.models import User

from ..schemas import (
    BehavioralRecommendationProductResponse,
    BehavioralReminderResponse,
)
from .auth import SESSION_COOKIE_NAME, get_current_user
from .catalog import product_response
from .chat import CONVERSATION_COOKIE_NAME


router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])


@router.post("/reminder", response_model=BehavioralReminderResponse)
async def claim_behavioral_reminder(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
    conversation_token: Annotated[str | None, Cookie(alias=CONVERSATION_COOKIE_NAME)] = None,
) -> BehavioralReminderResponse:
    if not session_token:
        return BehavioralReminderResponse(message="", products=[])

    scope = build_memory_scope(
        user_id=user.id,
        auth_session_token=session_token,
        conversation_token=conversation_token or "authenticated",
    )
    store = get_shopping_memory_store()
    try:
        memory = await store.load(scope)
    except MemoryUnavailableError:
        return BehavioralReminderResponse(message="", products=[])
    if memory is None:
        return BehavioralReminderResponse(message="", products=[])

    request_id = uuid4().hex[:12]
    recorder = OrchestrationRecorder(
        db,
        request_id=request_id,
        user=user,
        run_type="behavioral_reminder",
    )
    recorder.start({
        "user_request": "Behavioral reminder eligibility check",
        "run_type": "behavioral_reminder",
        "user_id": str(user.id),
        # The authenticated session scope is intentionally hashed before it is
        # persisted; the raw cookie/session secret never enters audit storage.
        "memory_session_scope_hash": hashlib.sha256(scope.encode("utf-8")).hexdigest(),
    })
    log_ai_event("agent.behavioral_recommendation.started", request_id=request_id, user_id=str(user.id))
    recorder_token = active_recorder.set(recorder)
    try:
        result = await BehavioralRecommendationAgent(
            PrimaryLangChainChatModel(timeout_seconds=settings.agent_optional_model_timeout_seconds)
        ).recommend(db, memory, limit=3, request_id=request_id, recorder=recorder)
    except Exception as error:
        recorder.fail(error)
        log_ai_event(
            "agent.behavioral_recommendation.run_finished",
            request_id=request_id, status="failed", reason=type(error).__name__,
        )
        return BehavioralReminderResponse(message="", products=[])
    finally:
        active_recorder.reset(recorder_token)

    if result.status == "failed":
        recorder.fail(RuntimeError(result.error_message or "Behavioral recommendation failed."))
        log_ai_event(
            "agent.behavioral_recommendation.run_finished",
            request_id=request_id, status="failed", reason="selection_failed",
        )
        return BehavioralReminderResponse(message="", products=[])
    recommendations = result.recommendations
    if not recommendations:
        recorder.finish({
            "audit_result": {"status": "pass"},
            "final_response": "",
            "behavioral_reminder": {"selected_product_ids": [], "popup_message": ""},
        })
        log_ai_event(
            "agent.behavioral_recommendation.run_finished",
            request_id=request_id,
            status="completed",
            recommendation_count=0,
            total_tokens=recorder.run.total_tokens if recorder.run is not None else 0,
        )
        return BehavioralReminderResponse(message="", products=[])

    delivered_ids = [str(item.product.id) for item in recommendations]
    notified_ids = list(dict.fromkeys([*memory.notified_product_ids, *delivered_ids]))[-30:]
    try:
        await store.save(scope, memory.model_copy(update={"notified_product_ids": notified_ids}))
        recorder.record(
            "behavioral_notification_delivery",
            node_name="behavioral_reminder",
            input_data={"selected_product_ids": delivered_ids},
            output_data={"notified_product_ids": notified_ids, "memory_updated": True},
        )
    except MemoryUnavailableError:
        # A notification is optional and must never disrupt the storefront.
        recorder.record(
            "behavioral_notification_delivery",
            node_name="behavioral_reminder",
            status="completed",
            input_data={"selected_product_ids": delivered_ids},
            output_data={"memory_updated": False},
            error_message="Short-term memory could not record delivered reminder IDs.",
        )
    recorder.finish({
        "audit_result": {"status": "pass"},
        "final_response": result.message,
        "behavioral_reminder": {
            "selected_product_ids": delivered_ids,
            "reasons": [
                {"product_id": str(item.product.id), "reason": item.reason}
                for item in recommendations
            ],
            "popup_message": result.message,
        },
    })
    log_ai_event(
        "agent.behavioral_recommendation.run_finished",
        request_id=request_id,
        status="completed",
        recommendation_count=len(delivered_ids),
        total_tokens=recorder.run.total_tokens if recorder.run is not None else 0,
    )

    return BehavioralReminderResponse(
        message=result.message,
        products=[
            BehavioralRecommendationProductResponse(
                product=product_response(item.product),
                reason=item.reason,
            )
            for item in recommendations
        ],
    )
