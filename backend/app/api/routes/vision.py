import base64
import time
from uuid import uuid4

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.ai_logging import log_ai_event
from app.config import settings

from ..constants import SYSTEM_INSTRUCTION, VISION_PROMPTS
from ..schemas import VisionMode, VisionResponse


router = APIRouter(tags=["shopping missions"])
MAX_VISION_IMAGE_BYTES = 10 * 1024 * 1024


@router.post("/api/v1/shopping/missions/vision", response_model=VisionResponse)
async def analyze_shopping_photo(
    image: UploadFile = File(...),
    mode: VisionMode = Form(...),
) -> VisionResponse:
    request_id = uuid4().hex[:12]
    started_at = time.perf_counter()
    log_ai_event(
        "camera.received",
        request_id=request_id,
        input_type="camera",
        filename=image.filename or "captured-image",
        mime_type=image.content_type,
        mode=mode,
        customer_input=f"[image submitted for {mode}]",
    )
    if not settings.gemini_api_key:
        log_ai_event("camera.failed", request_id=request_id, reason="gemini_api_key_missing")
        raise HTTPException(status_code=503, detail="The Gemini API key is not configured.")
    if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        log_ai_event("camera.rejected", request_id=request_id, reason="unsupported_image_format")
        raise HTTPException(status_code=415, detail="Use a JPEG, PNG, or WebP image.")

    image_bytes = await image.read(MAX_VISION_IMAGE_BYTES + 1)
    if not image_bytes:
        log_ai_event("camera.rejected", request_id=request_id, reason="empty_image")
        raise HTTPException(status_code=400, detail="Choose an image to analyze.")
    if len(image_bytes) > MAX_VISION_IMAGE_BYTES:
        log_ai_event("camera.rejected", request_id=request_id, reason="image_too_large", bytes=len(image_bytes))
        raise HTTPException(status_code=413, detail="Choose an image smaller than 10 MB.")

    request_body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"inlineData": {"mimeType": image.content_type, "data": base64.b64encode(image_bytes).decode("ascii")}},
                    {"text": VISION_PROMPTS[mode]},
                ],
            }
        ],
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 550},
    }
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"

    try:
        log_ai_event(
            "camera.processing",
            request_id=request_id,
            stage="preparing_vision_analysis",
            bytes=len(image_bytes),
            model=settings.gemini_model,
            vision_goal=VISION_PROMPTS[mode],
            reasoning_trace="The selected shopping mode determines the image-analysis goal and product recommendation format.",
        )
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
            response = await client.post(endpoint, params={"key": settings.gemini_api_key}, json=request_body)
    except httpx.HTTPError as error:
        log_ai_event(
            "camera.failed",
            request_id=request_id,
            reason="gemini_connection_error",
            elapsed_ms=round((time.perf_counter() - started_at) * 1000),
        )
        raise HTTPException(status_code=502, detail="Unable to reach Gemini right now. Please try again.") from error

    if response.is_error:
        log_ai_event(
            "camera.failed",
            request_id=request_id,
            reason="gemini_response_error",
            status_code=response.status_code,
            elapsed_ms=round((time.perf_counter() - started_at) * 1000),
        )
        raise HTTPException(status_code=502, detail="Gemini could not analyze this photo. Please try again.")

    data = response.json()
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    analysis = "".join(part.get("text", "") for part in parts).strip()
    if not analysis:
        log_ai_event(
            "camera.failed",
            request_id=request_id,
            reason="empty_model_response",
            elapsed_ms=round((time.per_counter() - started_at) * 1000),
        )
        raise HTTPException(status_code=502, detail="Gemini returned an empty analysis. Please try again.")

    log_ai_event(
        "camera.completed",
        request_id=request_id,
        input_type="camera",
        mode=mode,
        ai_process="Gemini analyzed the submitted image according to the selected shopping mode.",
        final_output=analysis,
        elapsed_ms=round((time.perf_counter() - started_at) * 1000),
    )
    return VisionResponse(mode=mode, analysis=analysis)
