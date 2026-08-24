import base64
import os
import tempfile
import time
from uuid import uuid4
from functools import lru_cache
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from .config import settings
from .ai_logging import customer_input_for_log, log_ai_event


SYSTEM_INSTRUCTION = """You are Shopy Assistant, a concise and helpful shopping assistant for Shopy.
Help customers discover products, compare items, understand carts, orders, and ShopyPay.
Do not invent stock, order status, policies, prices, or account data that was not supplied.
Use clear, friendly language and ask one useful follow-up when needed."""

VISION_PROMPTS = {
    "shop_room": "Analyze this room for furniture, colours, style, empty spaces, and practical product recommendations. Give a concise shopping brief with 3-5 ideas.",
    "complete_look": "Analyze the clothing and accessories in this photo. Suggest complementary items, colours, and styling choices in a concise shopping brief.",
    "shop_object": "Identify the main object in this photo and suggest similar or complementary products. Give a concise shopping brief with 3-5 ideas.",
}
MAX_VISION_IMAGE_BYTES = 10 * 1024 * 1024
MAX_AUDIO_BYTES = 25 * 1024 * 1024
ALLOWED_AUDIO_TYPES = {
    "audio/webm",
    "video/webm",
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/ogg",
    "audio/mp4",
    "audio/x-m4a",
}
ALLOWED_AUDIO_SUFFIXES = {".webm", ".wav", ".mp3", ".ogg", ".m4a", ".mp4"}


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)


class ChatResponse(BaseModel):
    reply: str


class VisionResponse(BaseModel):
    mode: Literal["shop_room", "complete_look", "shop_object"]
    analysis: str


class TranscriptionResponse(BaseModel):
    transcript: str
    language: str | None = None
    duration_seconds: float | None = None


@lru_cache(maxsize=1)
def get_whisper_model():
    """Load the local Whisper model only when speech-to-text is first requested."""
    try:
        from faster_whisper import WhisperModel

        return WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
    except Exception as error:
        raise RuntimeError("Local Whisper could not be initialized.") from error


def transcribe_local_audio(audio_path: str) -> TranscriptionResponse:
    model = get_whisper_model()
    segments, info = model.transcribe(audio_path, vad_filter=True, beam_size=5)
    transcript = " ".join(segment.text.strip() for segment in segments).strip()
    duration = getattr(info, "duration", None)
    return TranscriptionResponse(
        transcript=transcript,
        language=getattr(info, "language", None),
        duration_seconds=round(duration, 2) if duration is not None else None,
    )


app = FastAPI(title="Shopy AI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "model": settings.gemini_model}


@app.post("/api/v1/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(audio: UploadFile = File(...)) -> TranscriptionResponse:
    """Transcribe a user-confirmed recording locally with Faster-Whisper.

    Audio is written to a temporary file only for decoding and removed immediately
    after transcription. No recording is retained by the application.
    """
    request_id = uuid4().hex[:12]
    started_at = time.perf_counter()
    suffix = Path(audio.filename or "recording.webm").suffix.lower()
    log_ai_event(
        "voice.received",
        request_id=request_id,
        input_type="voice",
        filename=audio.filename or "recording.webm",
        mime_type=audio.content_type,
        extension=suffix or ".webm",
    )
    if audio.content_type not in ALLOWED_AUDIO_TYPES and suffix not in ALLOWED_AUDIO_SUFFIXES:
        log_ai_event("voice.rejected", request_id=request_id, reason="unsupported_audio_format")
        raise HTTPException(status_code=415, detail="Use a WebM, WAV, MP3, M4A, MP4, or OGG audio recording.")

    audio_bytes = await audio.read(MAX_AUDIO_BYTES + 1)
    if not audio_bytes:
        log_ai_event("voice.rejected", request_id=request_id, reason="empty_audio")
        raise HTTPException(status_code=400, detail="The audio recording is empty. Please record your question again.")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        log_ai_event("voice.rejected", request_id=request_id, reason="audio_too_large", bytes=len(audio_bytes))
        raise HTTPException(status_code=413, detail="Use an audio recording smaller than 25 MB.")

    temp_path = ""
    try:
        log_ai_event(
            "voice.processing",
            request_id=request_id,
            stage="validating_and_decoding_audio",
            bytes=len(audio_bytes),
            whisper_model=settings.whisper_model,
            device=settings.whisper_device,
            reasoning_trace="Audio is validated, decoded, and passed to local Whisper with voice-activity detection.",
        )
        with tempfile.NamedTemporaryFile(suffix=suffix or ".webm", delete=False) as temporary_audio:
            temporary_audio.write(audio_bytes)
            temp_path = temporary_audio.name

        result = await run_in_threadpool(transcribe_local_audio, temp_path)
    except RuntimeError as error:
        log_ai_event("voice.failed", request_id=request_id, reason="whisper_initialization_failed", elapsed_ms=round((time.perf_counter() - started_at) * 1000))
        raise HTTPException(
            status_code=503,
            detail="Local Whisper is unavailable. Install Faster-Whisper and check the configured model.",
        ) from error
    except Exception as error:
        log_ai_event("voice.failed", request_id=request_id, reason="transcription_failed", elapsed_ms=round((time.perf_counter() - started_at) * 1000))
        raise HTTPException(status_code=422, detail="We could not transcribe that recording. Please try again.") from error
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass

    if not result.transcript:
        log_ai_event("voice.failed", request_id=request_id, reason="no_speech_detected", elapsed_ms=round((time.perf_counter() - started_at) * 1000))
        raise HTTPException(status_code=422, detail="No speech was detected. Please record your question again.")

    log_ai_event(
        "voice.completed",
        request_id=request_id,
        input_type="voice",
        customer_input=customer_input_for_log(result.transcript),
        language=result.language,
        audio_duration_seconds=result.duration_seconds,
        elapsed_ms=round((time.perf_counter() - started_at) * 1000),
        final_output="Transcript returned to the customer for editing and confirmation.",
    )
    return result


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    request_id = uuid4().hex[:12]
    started_at = time.perf_counter()
    latest_customer_input = next((message.content for message in reversed(payload.messages) if message.role == "user"), "")
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
        log_ai_event("text.failed", request_id=request_id, reason="gemini_connection_error", elapsed_ms=round((time.perf_counter() - started_at) * 1000))
        raise HTTPException(status_code=502, detail="Unable to reach Gemini right now. Please try again.") from error

    if response.is_error:
        log_ai_event("text.failed", request_id=request_id, reason="gemini_response_error", status_code=response.status_code, elapsed_ms=round((time.perf_counter() - started_at) * 1000))
        raise HTTPException(status_code=502, detail="Gemini could not complete that request. Please try again.")

    data = response.json()
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    reply = "".join(part.get("text", "") for part in parts).strip()
    if not reply:
        log_ai_event("text.failed", request_id=request_id, reason="empty_model_response", elapsed_ms=round((time.perf_counter() - started_at) * 1000))
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


@app.post("/api/v1/shopping/missions/vision", response_model=VisionResponse)
async def analyze_shopping_photo(
    image: UploadFile = File(...),
    mode: Literal["shop_room", "complete_look", "shop_object"] = Form(...),
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
        "contents": [{
            "role": "user",
            "parts": [
                {"inlineData": {"mimeType": image.content_type, "data": base64.b64encode(image_bytes).decode("ascii")}},
                {"text": VISION_PROMPTS[mode]},
            ],
        }],
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
        log_ai_event("camera.failed", request_id=request_id, reason="gemini_connection_error", elapsed_ms=round((time.perf_counter() - started_at) * 1000))
        raise HTTPException(status_code=502, detail="Unable to reach Gemini right now. Please try again.") from error

    if response.is_error:
        log_ai_event("camera.failed", request_id=request_id, reason="gemini_response_error", status_code=response.status_code, elapsed_ms=round((time.perf_counter() - started_at) * 1000))
        raise HTTPException(status_code=502, detail="Gemini could not analyze this photo. Please try again.")

    data = response.json()
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    analysis = "".join(part.get("text", "") for part in parts).strip()
    if not analysis:
        log_ai_event("camera.failed", request_id=request_id, reason="empty_model_response", elapsed_ms=round((time.perf_counter() - started_at) * 1000))
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
