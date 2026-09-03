import base64
import json
import time
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.ai.gemini import GeminiClient, GeminiConnectionError, GeminiResponseError
from app.ai.qwen import QwenClient, QwenConnectionError, QwenResponseError
from app.ai_logging import customer_input_for_log, log_ai_event
from app.config import settings

from ..schemas import TranscriptionResponse


router = APIRouter(tags=["transcription"])
# Inline media requests expand audio by roughly one third when Base64-encoded,
# so this leaves room for the prompt and request metadata.
MAX_AUDIO_BYTES = 14 * 1024 * 1024
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


async def transcribe_with_gemini(
    *, audio_bytes: bytes, mime_type: str, requested_language: str
) -> TranscriptionResponse:
    """Transcribe a short recording through the configured Gemini model."""
    language_instruction = (
        f"The caller requested {requested_language}."
        if requested_language != "auto"
        else "Identify the spoken language."
    )
    prompt = (
        "Transcribe this audio exactly. Do not summarize, translate, add speaker labels, "
        "or include commentary. Return valid JSON only with this shape: "
        '{"transcript":"...","language":"ISO 639-1 code or null"}. '
        f"{language_instruction}"
    )
    response = await GeminiClient(timeout_seconds=settings.transcription_timeout_seconds).generate(
        system_instruction="You are a precise speech-to-text service.",
        contents=[{
            "role": "user",
            "parts": [
                {"inlineData": {"mimeType": mime_type, "data": base64.b64encode(audio_bytes).decode("ascii")}},
                {"text": prompt},
            ],
        }],
        max_output_tokens=2048,
        response_mime_type="application/json",
    )
    try:
        data = json.loads(response)
        transcript = str(data.get("transcript", "")).strip()
        language = data.get("language")
        language = str(language).strip().lower() if language else None
    except (TypeError, ValueError) as error:
        raise GeminiResponseError("Gemini returned an invalid transcription response.") from error
    return TranscriptionResponse(transcript=transcript, language=language, duration_seconds=None)


async def transcribe_with_qwen(
    *, audio_bytes: bytes, mime_type: str, requested_language: str
) -> TranscriptionResponse:
    """Transcribe with the configured Qwen Omni Captioner model."""
    language_instruction = (
        f"The caller requested {requested_language}."
        if requested_language != "auto"
        else "Identify the spoken language."
    )
    prompt = (
        "Transcribe this audio exactly. Do not summarize, translate, add speaker labels, "
        "or include commentary. Return valid JSON only with this shape: "
        '{"transcript":"...","language":"ISO 639-1 code or null"}. '
        f"{language_instruction}"
    )
    response = await QwenClient(timeout_seconds=settings.transcription_timeout_seconds).caption_audio(
        audio_bytes=audio_bytes,
        mime_type=mime_type,
        prompt=prompt,
        max_output_tokens=2048,
    )
    try:
        data = json.loads(response)
        transcript = str(data.get("transcript", "")).strip()
        language = data.get("language")
        language = str(language).strip().lower() if language else None
    except (TypeError, ValueError) as error:
        raise QwenResponseError("Qwen returned an invalid transcription response.") from error
    return TranscriptionResponse(transcript=transcript, language=language, duration_seconds=None)


@router.post("/api/v1/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str | None = Form(default=None, max_length=12),
) -> TranscriptionResponse:
    """Transcribe confirmed audio with Qwen and fall back to Gemini if needed."""
    request_id = uuid4().hex[:12]
    started_at = time.perf_counter()
    requested_language = (language or settings.transcription_default_language).strip().lower()
    if requested_language in {"", "auto", "detect"}:
        requested_language = "auto"
    elif not requested_language.isalpha() or len(requested_language) not in {2, 3}:
        raise HTTPException(status_code=422, detail="Language must be an ISO code such as 'en' or 'auto'.")
    suffix = Path(audio.filename or "recording.webm").suffix.lower()
    log_ai_event(
        "voice.received",
        request_id=request_id,
        input_type="voice",
        filename=audio.filename or "recording.webm",
        mime_type=audio.content_type,
        extension=suffix or ".webm",
        requested_language=requested_language,
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
        raise HTTPException(status_code=413, detail="Use an audio recording smaller than 14 MB.")

    try:
        log_ai_event(
            "voice.processing",
            request_id=request_id,
            stage="sending_audio_to_primary_provider",
            bytes=len(audio_bytes),
            provider="qwen" if settings.qwen_api_key else "gemini",
            model=settings.qwen_audio_model if settings.qwen_api_key else settings.gemini_model,
            requested_language=requested_language,
            reasoning_trace="Audio is validated and sent inline to the configured speech model for transcription.",
        )
        if settings.qwen_api_key:
            try:
                result = await transcribe_with_qwen(
                    audio_bytes=audio_bytes,
                    mime_type=audio.content_type or "audio/webm",
                    requested_language=requested_language,
                )
            except (QwenConnectionError, QwenResponseError):
                if not settings.gemini_api_key:
                    raise
                log_ai_event("voice.fallback", request_id=request_id, from_provider="qwen", to_provider="gemini")
                result = await transcribe_with_gemini(
                    audio_bytes=audio_bytes,
                    mime_type=audio.content_type or "audio/webm",
                    requested_language=requested_language,
                )
        else:
            result = await transcribe_with_gemini(
                audio_bytes=audio_bytes,
                mime_type=audio.content_type or "audio/webm",
                requested_language=requested_language,
            )
    except (QwenConnectionError, GeminiConnectionError) as error:
        log_ai_event(
            "voice.failed",
            request_id=request_id,
            reason="speech_provider_unavailable",
            elapsed_ms=round((time.perf_counter() - started_at) * 1000),
        )
        raise HTTPException(
            status_code=503,
            detail="The speech provider is unavailable. Check the API configuration and try again.",
        ) from error
    except (QwenResponseError, GeminiResponseError) as error:
        log_ai_event(
            "voice.failed",
            request_id=request_id,
            reason="speech_transcription_failed",
            elapsed_ms=round((time.perf_counter() - started_at) * 1000),
        )
        raise HTTPException(status_code=422, detail="We could not transcribe that recording. Please try again.") from error

    if not result.transcript:
        log_ai_event(
            "voice.failed",
            request_id=request_id,
            reason="no_speech_detected",
            elapsed_ms=round((time.perf_counter() - started_at) * 1000),
        )
        raise HTTPException(status_code=422, detail="No speech was detected. Please record your question again.")

    log_ai_event(
        "voice.completed",
        request_id=request_id,
        input_type="voice",
        customer_input=customer_input_for_log(result.transcript),
        language=result.language,
        requested_language=requested_language,
        audio_duration_seconds=result.duration_seconds,
        elapsed_ms=round((time.perf_counter() - started_at) * 1000),
        final_output="Transcript returned to the customer for editing and confirmation.",
    )
    return result
