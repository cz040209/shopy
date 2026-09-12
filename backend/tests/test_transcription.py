import asyncio

from app.ai.qwen import QwenClient, QwenGeneration
from app.api.routes import transcription
from app.config import settings


def test_qwen_asr_uses_transcript_output_without_a_chat_prompt(monkeypatch):
    captured: dict[str, object] = {}

    class FakeQwen:
        def __init__(self, *, timeout_seconds: float) -> None:
            captured["timeout_seconds"] = timeout_seconds

        async def transcribe_audio(
            self,
            *,
            audio_bytes: bytes,
            mime_type: str,
            language: str | None,
        ) -> str:
            captured.update(
                audio_bytes=audio_bytes,
                mime_type=mime_type,
                language=language,
            )
            return "I need a laptop under RM 3,000."

    monkeypatch.setattr(transcription, "QwenClient", FakeQwen)

    result = asyncio.run(transcription.transcribe_with_qwen(
        audio_bytes=b"recording-bytes",
        mime_type="audio/webm",
        requested_language="en",
    ))

    assert result.transcript == "I need a laptop under RM 3,000."
    assert result.language is None
    assert captured["audio_bytes"] == b"recording-bytes"
    assert captured["mime_type"] == "audio/webm"
    assert captured["language"] == "en"


def test_qwen_asr_does_not_force_a_language_when_auto_detecting(monkeypatch):
    captured: dict[str, object] = {}

    class FakeQwen:
        def __init__(self, *, timeout_seconds: float) -> None:
            pass

        async def transcribe_audio(self, **kwargs: object) -> str:
            captured.update(kwargs)
            return "Saya mahu telefon baharu."

    monkeypatch.setattr(transcription, "QwenClient", FakeQwen)

    result = asyncio.run(transcription.transcribe_with_qwen(
        audio_bytes=b"recording-bytes",
        mime_type="audio/webm",
        requested_language="auto",
    ))

    assert result.transcript == "Saya mahu telefon baharu."
    assert captured["language"] is None


def test_qwen_asr_uses_the_model_specific_audio_contract(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_complete(_self: QwenClient, **kwargs: object) -> QwenGeneration:
        captured.update(kwargs)
        return QwenGeneration(text="Need a phone under RM 2,000", input_tokens=1, output_tokens=1, total_tokens=2)

    monkeypatch.setattr(QwenClient, "_complete", fake_complete)

    transcript = asyncio.run(QwenClient(timeout_seconds=5).transcribe_audio(
        audio_bytes=b"audio-bytes",
        mime_type="audio/webm",
        language="en",
    ))

    assert transcript == "Need a phone under RM 2,000"
    assert settings.qwen_audio_model == "qwen3-asr-flash-2025-09-08"
    assert captured["max_output_tokens"] is None
    assert captured["response_mime_type"] is None
    assert captured["enable_thinking"] is None
    assert captured["extra_body"] == {
        "stream": False,
        "asr_options": {"enable_itn": True, "language": "en"},
    }
    assert captured["messages"] == [{
        "role": "user",
        "content": [{
            "type": "input_audio",
            "input_audio": {"data": "data:audio/webm;base64,YXVkaW8tYnl0ZXM="},
        }],
    }]


def test_qwen_generate_forwards_the_per_request_vision_model(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_generate_with_usage(
        _self: QwenClient, **kwargs: object,
    ) -> QwenGeneration:
        captured.update(kwargs)
        return QwenGeneration(
            text='{"detected_objects":[]}', input_tokens=1,
            output_tokens=1, total_tokens=2,
        )

    monkeypatch.setattr(
        QwenClient, "generate_with_usage", fake_generate_with_usage,
    )

    result = asyncio.run(QwenClient(timeout_seconds=5).generate(
        system_instruction="vision schema",
        contents=[],
        max_output_tokens=700,
        response_mime_type="application/json",
        enable_thinking=False,
        qwen_model="vision-model",
    ))

    assert result == '{"detected_objects":[]}'
    assert captured["qwen_model"] == "vision-model"
