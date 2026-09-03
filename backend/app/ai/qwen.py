"""Alibaba Cloud Model Studio client for Qwen's OpenAI-compatible API."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from app.agentic.observability import active_recorder
from app.config import settings


class QwenConnectionError(RuntimeError):
    """Qwen could not be reached."""


class QwenResponseError(RuntimeError):
    """Qwen rejected a request or returned no usable text."""


@dataclass(frozen=True)
class QwenGeneration:
    text: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


class QwenClient:
    """Shared Qwen client for text, vision, and audio-caption requests."""

    def __init__(self, *, timeout_seconds: float) -> None:
        self.timeout = httpx.Timeout(timeout_seconds, connect=10.0)

    async def generate(
        self,
        *,
        system_instruction: str,
        contents: list[dict[str, Any]],
        max_output_tokens: int,
        response_mime_type: str | None = None,
        enable_thinking: bool | None = None,
    ) -> str:
        return (await self.generate_with_usage(
            system_instruction=system_instruction,
            contents=contents,
            max_output_tokens=max_output_tokens,
            response_mime_type=response_mime_type,
            enable_thinking=enable_thinking,
        )).text

    async def generate_with_usage(
        self,
        *,
        system_instruction: str,
        contents: list[dict[str, Any]],
        max_output_tokens: int,
        response_mime_type: str | None = None,
        enable_thinking: bool | None = None,
    ) -> QwenGeneration:
        messages = [{"role": "system", "content": system_instruction}]
        messages.extend(self._messages_from_contents(contents))
        return await self._complete(
            model=settings.qwen_model,
            messages=messages,
            max_output_tokens=max_output_tokens,
            response_mime_type=response_mime_type,
            enable_thinking=settings.qwen_enable_thinking if enable_thinking is None else enable_thinking,
        )

    async def caption_audio(
        self,
        *,
        audio_bytes: bytes,
        mime_type: str,
        prompt: str,
        max_output_tokens: int,
    ) -> str:
        audio_data = base64.b64encode(audio_bytes).decode("ascii")
        generation = await self._complete(
            model=settings.qwen_audio_model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "input_audio", "input_audio": {"data": f"data:{mime_type};base64,{audio_data}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json",
            enable_thinking=False,
        )
        return generation.text

    async def _complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        max_output_tokens: int,
        response_mime_type: str | None,
        enable_thinking: bool,
    ) -> QwenGeneration:
        if not settings.qwen_api_key:
            raise QwenConnectionError("Qwen API key is not configured.")
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.5,
            "max_tokens": max_output_tokens,
            "enable_thinking": enable_thinking,
        }
        if response_mime_type == "application/json":
            body["response_format"] = {"type": "json_object"}
        started_at = datetime.now(timezone.utc)
        endpoint = f"{settings.qwen_base_url.rstrip('/')}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {settings.qwen_api_key}"},
                    json=body,
                )
        except httpx.HTTPError as error:
            raise QwenConnectionError from error
        if response.is_error:
            raise QwenResponseError(f"Qwen returned HTTP {response.status_code}")
        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            text = content if isinstance(content, str) else "".join(
                str(part.get("text", "")) for part in content if isinstance(part, dict)
            )
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise QwenResponseError("Qwen returned an invalid response.") from error
        if not text.strip():
            raise QwenResponseError("Qwen returned an empty response.")
        usage = data.get("usage", {})
        generation = QwenGeneration(
            text=text.strip(),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
        )
        recorder = active_recorder.get()
        if recorder is not None:
            recorder.record_llm_call(
                input_tokens=generation.input_tokens,
                output_tokens=generation.output_tokens,
                total_tokens=generation.total_tokens,
                started_at=started_at,
            )
        return generation

    @staticmethod
    def _messages_from_contents(contents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for content in contents:
            parts: list[dict[str, Any]] = []
            for part in content.get("parts", []):
                if "text" in part:
                    parts.append({"type": "text", "text": str(part["text"])})
                elif isinstance(part.get("inlineData"), dict):
                    media = part["inlineData"]
                    mime_type = str(media.get("mimeType", "application/octet-stream"))
                    encoded = str(media.get("data", ""))
                    if mime_type.startswith("image/"):
                        parts.append({"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}})
            if parts:
                messages.append({"role": "assistant" if content.get("role") == "model" else "user", "content": parts})
        return messages
