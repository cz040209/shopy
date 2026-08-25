import os
import tempfile
import time
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.ai_logging import customer_input_for_log, log_ai_event
from app.config import settings

from ..schemas import TranscriptionResponse


router = APIRouter(tags=["transcription"])
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


@router.post("/api/v1/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(audio: UploadFile = File(...)) -> TranscriptionResponse:
    """Transcribe confirmed audio locally and remove its temporary file."""
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
        log_ai_event(
            "voice.failed",
            request_id=request_id,
            reason="whisper_initialization_failed",
            elapsed_ms=round((time.perf_counter() - started_at) * 1000),
        )
        raise HTTPException(
            status_code=503,
            detail="Local Whisper is unavailable. Install Faster-Whisper and check the configured model.",
        ) from error
    except Exception as error:
        log_ai_event(
            "voice.failed",
            request_id=request_id,
            reason="transcription_failed",
            elapsed_ms=round((time.perf_counter() - started_at) * 1000),
        )
        raise HTTPException(status_code=422, detail="We could not transcribe that recording. Please try again.") from error
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass

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
        audio_duration_seconds=result.duration_seconds,
        elapsed_ms=round((time.perf_counter() - started_at) * 1000),
        final_output="Transcript returned to the customer for editing and confirmation.",
    )
    return result
