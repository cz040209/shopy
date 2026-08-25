import json
import time
from uuid import uuid4

from fastapi import APIRouter, Cookie, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from app.ai_logging import log_ai_event
from app.agentic.orchestrator import ShoppingOrchestrator
from app.agentic.tools import CommerceToolRegistry
from app.ai.gemini import GeminiConnectionError, GeminiResponseError
from app.config import settings
from app.database import get_db
from app.models import AIMessage, MessageRole, User

from ..constants import VISION_PROMPTS
from ..schemas import VisionMode, VisionResponse
from .auth import get_optional_current_user
from .chat import CONVERSATION_COOKIE_NAME, get_or_create_conversation, set_conversation_cookie


router = APIRouter(tags=["shopping missions"])
MAX_VISION_IMAGE_BYTES = 10 * 1024 * 1024


@router.post("/api/v1/shopping/missions/vision", response_model=VisionResponse)
async def analyze_shopping_photo(
    http_response: Response,
    image: UploadFile = File(...),
    mode: VisionMode = Form(...),
    conversation_token: str | None = Cookie(default=None, alias=CONVERSATION_COOKIE_NAME),
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> VisionResponse:
    request_id = uuid4().hex[:12]
    started_at = time.perf_counter()
    analysis = json.dumps(state.get("vision_context", {}), ensure_ascii=False)
    try:
        conversation, token = get_or_create_conversation(
            db=db,
            token=conversation_token,
            user=current_user,
            first_message=f"Image submitted: {mode.replace('_', ' ')}",
        )
        conversation.messages.extend(
            [
                AIMessage(
                    role=MessageRole.USER,
                    content=f"[Image submitted for {mode.replace('_', ' ')}]",
                    input_type="image",
                    input_payload={
                        "mode": mode,
                        "filename": image.filename or "captured-image",
                        "mime_type": image.content_type,
                        "bytes": len(image_bytes),
                        "raw_asset_stored": False,
                    },
                    processing_metadata={"request_id": request_id, "channel": "web_camera"},
                ),
                AIMessage(
                    role=MessageRole.ASSISTANT,
                    content=analysis,
                    model=settings.gemini_model,
                    processing_metadata={"request_id": request_id, "response_source": "vision_orchestrator"},
                ),
            ]
        )
        db.commit()
        set_conversation_cookie(http_response, token)
    except Exception as error:
        db.rollback()
        log_ai_event("camera.conversation_persistence_failed", request_id=request_id, error_type=type(error).__name__)
        raise HTTPException(status_code=503, detail="The image was analyzed, but its conversation record could not be saved.") from error
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
        registry = CommerceToolRegistry(db, request_id=request_id)
        state = await ShoppingOrchestrator(tool_registry=registry).ainvoke(
            f"Shop this {mode.replace('_', ' ')} image.",
            state_overrides={"vision_input": {"image_bytes": image_bytes, "mime_type": image.content_type, "mode": mode}},
        )
    except GeminiConnectionError as error:
        log_ai_event(
            "camera.failed",
            request_id=request_id,
            reason="gemini_connection_error",
            elapsed_ms=round((time.perf_counter() - started_at) * 1000),
        )
        raise HTTPException(status_code=502, detail="Unable to reach Gemini right now. Please try again.") from error

    except GeminiResponseError:
        log_ai_event(
            "camera.failed",
            request_id=request_id,
            reason="gemini_response_error",
            elapsed_ms=round((time.perf_counter() - started_at) * 1000),
        )
        raise HTTPException(status_code=502, detail="Gemini could not analyze this photo. Please try again.")

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
