import time
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException

from app.ai_logging import customer_input_for_log, log_ai_event
from app.config import settings

from ..constants import SYSTEM_INSTRUCTION
from ..schemas import ChatRequest, ChatResponse


router = APIRouter(tags=["assistant"])


@router.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    request_id = uuid4().hex[:12]
    started_at = time.perf_counter()
    latest_customer_input = next(
        (message.content for message in reversed(payload.messages) if message.role == "user"),
        "",
    )
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

    history = list(payload.messages)
    while history and history[0].role == "assistant":
        history.pop(0)

    contents = [
        {
            "role": "model" if message.role == "assistant" else "user",
            "parts": [{"text": message.content.strip()}],
        }
        for message in history
    ]
    request_body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 500},
    }
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"

    try:
        log_ai_event(
            "text.processing",
            request_id=request_id,
            stage="preparing_shopping_assistant_request",
            model=settings.gemini_model,
            history_messages=len(contents),
            reasoning_trace="System shopping guidance and recent conversation context are assembled before requesting a response.",
        )
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            response = await client.post(endpoint, params={"key": settings.gemini_api_key}, json=request_body)
    except httpx.HTTPError as error:
        log_ai_event(
            "text.failed",
            request_id=request_id,
            reason="gemini_connection_error",
            elapsed_ms=round((time.perf_counter() - started_at) * 1000),
        )
        raise HTTPException(status_code=502, detail="Unable to reach Gemini right now. Please try again.") from error

    if response.is_error:
        log_ai_event(
            "text.failed",
            request_id=request_id,
            reason="gemini_response_error",
            status_code=response.status_code,
            elapsed_ms=round((time.perf_counter() - started_at) * 1000),
        )
        raise HTTPException(status_code=502, detail="Gemini could not complete that request. Please try again.")

    data = response.json()
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    reply = "".join(part.get("text", "") for part in parts).strip()
    if not reply:
        log_ai_event(
            "text.failed",
            request_id=request_id,
            reason="empty_model_response",
            elapsed_ms=round((time.perf_counter() - started_at) * 1000),
        )
        raise HTTPException(status_code=502, detail="Gemini returned an empty response. Please try again.")

    log_ai_event(
        "text.completed",
        request_id=request_id,
        input_type="text",
        customer_input=customer_input_for_log(latest_customer_input),
        ai_process="Gemini generated a shopping-assistant response from the system guidance and conversation context.",
        final_output=reply,
        elapsed_ms=round((time.perf_counter() - started_at) * 1000),
    )
    return ChatResponse(reply=reply)
