from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


class GeminiConnectionError(RuntimeError):
    """Gemini could not be reached."""


class GeminiResponseError(RuntimeError):
    """Gemini rejected a request or returned no usable text."""


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
        return text
