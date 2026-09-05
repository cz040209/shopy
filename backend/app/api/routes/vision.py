import json
import time
from uuid import uuid4

from fastapi import APIRouter, Cookie, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from app.ai_logging import log_ai_event
from app.agentic.observability import OrchestrationRecorder
from app.agentic.memory import build_memory_scope, get_shopping_memory_store
from app.agentic.orchestrator import ShoppingOrchestrator
from app.agentic.tools import CommerceToolRegistry
from app.ai.primary import AIConnectionError, AIResponseError
from app.config import settings
from app.database import get_db
from app.models import AIMessage, MessageRole, User

from ..constants import VISION_PROMPTS
from ..schemas import VisionMode, VisionResponse
from .auth import SESSION_COOKIE_NAME, get_optional_current_user
from .chat import CONVERSATION_COOKIE_NAME, get_or_create_conversation, set_conversation_cookie


router = APIRouter(tags=["shopping missions"])
MAX_VISION_IMAGE_BYTES = 10 * 1024 * 1024


@router.post("/api/v1/shopping/missions/vision", response_model=VisionResponse)
async def analyze_shopping_photo(
    http_response: Response,
    image: UploadFile = File(...),
    mode: VisionMode = Form(...),
    style: str | None = Form(default=None, max_length=80),
    conversation_token: str | None = Cookie(default=None, alias=CONVERSATION_COOKIE_NAME),
    auth_session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
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
    if not settings.llm_provider_configured:
        log_ai_event("camera.failed", request_id=request_id, reason="llm_api_key_missing")
        raise HTTPException(status_code=503, detail="No LLM API key is configured.")
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

    recorder: OrchestrationRecorder | None = None
    try:
        log_ai_event(
            "camera.processing",
            request_id=request_id,
            stage="preparing_vision_analysis",
            bytes=len(image_bytes),
            model=settings.qwen_vision_model if settings.qwen_api_key else settings.gemini_model,
            vision_goal=VISION_PROMPTS[mode],
            reasoning_trace="The selected shopping mode determines the image-analysis goal and product recommendation format.",
        )
        conversation, token = get_or_create_conversation(
            db=db,
            token=conversation_token,
            user=current_user,
            first_message=f"Image submitted: {mode.replace('_', ' ')}",
        )
        recorder = OrchestrationRecorder(db, request_id=request_id, user=current_user, conversation=conversation)
        registry = CommerceToolRegistry(db, request_id=request_id, recorder=recorder)
        memory_session_scope = build_memory_scope(
            user_id=current_user.id if current_user is not None else None,
            auth_session_token=auth_session_token,
            conversation_token=token,
        )
        style_direction = f" Use a {style.strip()} style direction." if style and style.strip() else ""
        state = await ShoppingOrchestrator(
            tool_registry=registry,
            recorder=recorder,
            memory_store=get_shopping_memory_store(),
        ).ainvoke(
            f"Shop this {mode.replace('_', ' ')} image.{style_direction}",
            state_overrides={
                "vision_input": {"image_bytes": image_bytes, "mime_type": image.content_type, "mode": mode},
                "memory_session_scope": memory_session_scope,
            },
            defer_finish=True,
        )
    except AIConnectionError as error:
        log_ai_event(
            "camera.failed",
            request_id=request_id,
            reason="llm_connection_error",
            error_type=type(error).__name__,
            error_message=str(error)[:500],
            elapsed_ms=round((time.perf_counter() - started_at) * 1000),
        )
        raise HTTPException(status_code=502, detail="Unable to reach an AI provider right now. Please try again.") from error

    except AIResponseError as error:
        log_ai_event(
            "camera.failed",
            request_id=request_id,
            reason="llm_response_error",
            error_type=type(error).__name__,
            error_message=str(error)[:500],
            elapsed_ms=round((time.perf_counter() - started_at) * 1000),
        )
        raise HTTPException(status_code=502, detail="The AI provider could not analyze this photo. Please try again.")
    except Exception as error:
        if recorder is not None and recorder.run is not None and recorder.run.status == "running":
            recorder.fail(error)
        log_ai_event(
            "camera.failed", request_id=request_id, reason="orchestration_failed",
            error_type=type(error).__name__, error_message=str(error)[:1000],
            run_id=str(recorder.run.id) if recorder is not None and recorder.run is not None else None,
            elapsed_ms=round((time.perf_counter() - started_at) * 1000),
        )
        raise HTTPException(status_code=503, detail="The image shopping assistant could not complete a verified response.") from error

    if state.get("audit_result", {}).get("status") != "pass" or not state.get("final_response"):
        audit_error = ValueError("Image recommendation audit did not pass.")
        if recorder is not None and recorder.run is not None and recorder.run.status == "running":
            recorder.fail(audit_error)
        raise HTTPException(status_code=503, detail="The shopping assistant could not validate an image recommendation.")
    analysis = str(state["final_response"])
    attachments = list(state.get("attachments", []))
    try:
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
                    model=settings.active_llm_model,
                    processing_metadata={"request_id": request_id, "response_source": "vision_orchestrator"},
                    extra_data={"request_id": request_id, "attachments": attachments, "vision_context": state.get("vision_context", {})},
                ),
            ]
        )
        db.commit()
        set_conversation_cookie(http_response, token)
        recorder.finish(
            state,
            final_response=analysis,
            response_context={
                "conversation_id": str(conversation.id),
                "input_type": "image",
                "response_source": "audited_orchestrator",
            },
        )
    except Exception as error:
        db.rollback()
        if recorder is not None and recorder.run is not None and recorder.run.status == "running":
            recorder.fail(error)
        log_ai_event("camera.conversation_persistence_failed", request_id=request_id, error_type=type(error).__name__)
        raise HTTPException(status_code=503, detail="The image was analyzed, but its conversation record could not be saved.") from error

    log_ai_event(
        "camera.completed",
        request_id=request_id,
        input_type="camera",
        mode=mode,
        ai_process="The configured primary AI provider analyzed the submitted image according to the selected shopping mode.",
        final_output=analysis,
        elapsed_ms=round((time.perf_counter() - started_at) * 1000),
    )
    mission = {
        "goal": state.get("goal"),
        "mission_type": state.get("mission_type"),
        "recommendation_mode": state.get("recommendation_mode"),
        "budget": state.get("budget"),
        "preferences": state.get("preferences", []),
        "key_requirements": state.get("key_requirements", []),
        "owned_items": state.get("owned_items", []),
        "priorities": state.get("priorities", []),
    }
    workspace = {
        "bundle": state.get("bundle"),
        "compatibility": state.get("compatibility_results", []),
        "product_rankings": state.get("product_rankings", []),
        "audit": state.get("audit_result", {}),
        "fulfillment_gaps": state.get("fulfillment_gaps", []),
        "unfulfilled_requirements": state.get("unfulfilled_requirements", []),
    }
    return VisionResponse(
        mode=mode, analysis=analysis, attachments=attachments,
        vision_context=dict(state.get("vision_context", {})),
        mission=mission, workspace=workspace,
    )
