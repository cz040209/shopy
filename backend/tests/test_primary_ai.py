from types import SimpleNamespace
import asyncio

import pytest

from app.ai import primary
from app.ai.qwen import QwenConnectionError, QwenGeneration


class SuccessfulQwen:
    def __init__(self, *, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds

    async def generate_with_usage(self, **kwargs):
        return QwenGeneration(text="from qwen", input_tokens=3, output_tokens=2, total_tokens=5)


class UnavailableQwen:
    def __init__(self, *, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds

    async def generate_with_usage(self, **kwargs):
        raise QwenConnectionError("unavailable")


class SuccessfulGemini:
    def __init__(self, *, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds

    async def generate_with_usage(self, **kwargs):
        return SimpleNamespace(text="from gemini", input_tokens=4, output_tokens=3, total_tokens=7)


@pytest.mark.anyio
async def test_primary_client_prefers_qwen(monkeypatch):
    monkeypatch.setattr(primary, "settings", SimpleNamespace(qwen_api_key="qwen-key", gemini_api_key="gemini-key"))
    monkeypatch.setattr(primary, "QwenClient", SuccessfulQwen)
    monkeypatch.setattr(primary, "GeminiClient", SuccessfulGemini)

    generation = await primary.PrimaryLLMClient(timeout_seconds=10).generate_with_usage(
        system_instruction="system", contents=[], max_output_tokens=50
    )

    assert generation.text == "from qwen"
    assert generation.total_tokens == 5


@pytest.mark.anyio
async def test_primary_client_falls_back_to_gemini_after_qwen_connection_error(monkeypatch):
    monkeypatch.setattr(primary, "settings", SimpleNamespace(qwen_api_key="qwen-key", gemini_api_key="gemini-key"))
    monkeypatch.setattr(primary, "QwenClient", UnavailableQwen)
    monkeypatch.setattr(primary, "GeminiClient", SuccessfulGemini)

    generation = await primary.PrimaryLLMClient(timeout_seconds=10).generate_with_usage(
        system_instruction="system", contents=[], max_output_tokens=50
    )

    assert generation.text == "from gemini"
    assert generation.total_tokens == 7


@pytest.mark.anyio
async def test_primary_client_applies_one_deadline_across_all_providers(monkeypatch):
    class SlowQwen:
        def __init__(self, *, timeout_seconds: float) -> None:
            pass

        async def generate_with_usage(self, **kwargs):
            await asyncio.sleep(0.1)
            raise QwenConnectionError("late failure")

    monkeypatch.setattr(primary, "settings", SimpleNamespace(qwen_api_key="qwen-key", gemini_api_key="gemini-key"))
    monkeypatch.setattr(primary, "QwenClient", SlowQwen)
    monkeypatch.setattr(primary, "GeminiClient", SuccessfulGemini)

    with pytest.raises(primary.AIConnectionError, match="total request deadline"):
        await primary.PrimaryLLMClient(timeout_seconds=0.01).generate_with_usage(
            system_instruction="system", contents=[], max_output_tokens=50
        )
