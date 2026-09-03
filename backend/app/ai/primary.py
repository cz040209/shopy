"""Primary Qwen provider with Gemini fallback for text and vision generation."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from app.config import settings

from .gemini import GeminiClient, GeminiConnectionError, GeminiResponseError
from .qwen import QwenClient, QwenConnectionError, QwenResponseError


class AIConnectionError(RuntimeError):
    """No configured LLM provider could be reached."""


class AIResponseError(RuntimeError):
    """Configured LLM providers returned no usable response."""


@dataclass(frozen=True)
class PrimaryGeneration:
    text: str
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


class PrimaryLLMClient:
    """Try Qwen first and transparently fall back to Gemini when necessary."""

    def __init__(self, *, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds

    async def generate(self, **kwargs: Any) -> str:
        return (await self.generate_with_usage(**kwargs)).text

    async def generate_with_usage(self, **kwargs: Any) -> PrimaryGeneration:
        try:
            async with asyncio.timeout(self.timeout_seconds):
                return await self._generate_with_usage(**kwargs)
        except TimeoutError as error:
            raise AIConnectionError(
                "Configured LLM providers exceeded the total request deadline."
            ) from error

    async def _generate_with_usage(self, **kwargs: Any) -> PrimaryGeneration:
        failures: list[Exception] = []
        if settings.qwen_api_key:
            try:
                result = await QwenClient(timeout_seconds=self.timeout_seconds).generate_with_usage(**kwargs)
                return PrimaryGeneration(**result.__dict__)
            except (QwenConnectionError, QwenResponseError) as error:
                failures.append(error)
        if settings.gemini_api_key:
            try:
                gemini_kwargs = {key: value for key, value in kwargs.items() if key != "enable_thinking"}
                result = await GeminiClient(timeout_seconds=self.timeout_seconds).generate_with_usage(**gemini_kwargs)
                return PrimaryGeneration(**result.__dict__)
            except (GeminiConnectionError, GeminiResponseError) as error:
                failures.append(error)
        if not failures:
            raise AIConnectionError("No LLM API key is configured.")
        if all(isinstance(error, (QwenConnectionError, GeminiConnectionError)) for error in failures):
            raise AIConnectionError("Configured LLM providers are unavailable.") from failures[-1]
        raise AIResponseError("Configured LLM providers returned no usable response.") from failures[-1]
