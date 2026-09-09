from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Cookie, Depends
from sqlalchemy.orm import Session

from app.agentic.behavioral_recommendations import BehavioralRecommendationAgent
from app.agentic.llm import PrimaryLangChainChatModel
from app.agentic.memory import MemoryUnavailableError, build_memory_scope, get_shopping_memory_store
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
    result = await BehavioralRecommendationAgent(
        PrimaryLangChainChatModel(timeout_seconds=settings.agent_optional_model_timeout_seconds)
    ).recommend(db, memory, limit=3, request_id=request_id)
    recommendations = result.recommendations
    if not recommendations:
        return BehavioralReminderResponse(message="", products=[])

    delivered_ids = [str(item.product.id) for item in recommendations]
    notified_ids = list(dict.fromkeys([*memory.notified_product_ids, *delivered_ids]))[-30:]
    try:
        await store.save(scope, memory.model_copy(update={"notified_product_ids": notified_ids}))
    except MemoryUnavailableError:
        # A notification is optional and must never disrupt the storefront.
        pass

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
