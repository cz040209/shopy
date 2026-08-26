from __future__ import annotations

from typing import Any
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.agentic.observability import active_recorder


class GeminiConnectionError(RuntimeError):
    """Gemini could not be reached."""


class GeminiResponseError(RuntimeError):
    """Gemini rejected a request or returned no usable text."""


@dataclass(frozen=True)
class GeminiGeneration:
    text: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


class GeminiClient:
    """Small shared REST client; routes own their prompts and HTTP semantics."""

    def __init__(self, *, timeout_seconds: float) -> None:
        self.timeout = httpx.Timeout(timeout_seconds, connect=10.0)

    async def generate(
        self,
        *,
        system_instruction: str,
        contents: list[dict[str, Any]],
        max_output_tokens: int,
        response_mime_type: str | None = None,
    ) -> str:
        return (await self.generate_with_usage(
            system_instruction=system_instruction, contents=contents,
            max_output_tokens=max_output_tokens, response_mime_type=response_mime_type,
        )).text

    async def generate_with_usage(
        self,
        *,
        system_instruction: str,
        contents: list[dict[str, Any]],
        max_output_tokens: int,
        response_mime_type: str | None = None,
    ) -> GeminiGeneration:
        started_at = datetime.now(timezone.utc)
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
        generation_config: dict[str, Any] = {"temperature": 0.5, "maxOutputTokens": max_output_tokens}
        if response_mime_type:
            generation_config["responseMimeType"] = response_mime_type
        body = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": contents,
            "generationConfig": generation_config,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(endpoint, params={"key": settings.gemini_api_key}, json=body)
        except httpx.HTTPError as error:
            raise GeminiConnectionError from error
        if response.is_error:
            raise GeminiResponseError(f"Gemini returned HTTP {response.status_code}")
        try:
            data = response.json()
        except ValueError as error:
            raise GeminiResponseError("Gemini returned invalid JSON") from error
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts).strip()
        if not text:
            raise GeminiResponseError("Gemini returned an empty response")
        usage = data.get("usageMetadata", {})
        generation = GeminiGeneration(
            text=text,
            input_tokens=usage.get("promptTokenCount"),
            output_tokens=usage.get("candidatesTokenCount"),
            total_tokens=usage.get("totalTokenCount"),
        )
        recorder = active_recorder.get()
        if recorder is not None:
            recorder.record_llm_call(
                input_tokens=generation.input_tokens, output_tokens=generation.output_tokens,
                total_tokens=generation.total_tokens, started_at=started_at,
            )
        return generation
