from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.ai.primary import PrimaryLLMClient
from app.config import settings


def _provider_contents(messages: list[BaseMessage]) -> tuple[str, list[dict[str, Any]]]:
    system_parts: list[str] = []
    contents: list[dict[str, Any]] = []
    for message in messages:
        text = str(message.content)
        if message.type == "system":
            system_parts.append(text)
        else:
            contents.append({"role": "model" if message.type == "ai" else "user", "parts": [{"text": text}]})
    return "\n\n".join(system_parts), contents


class PrimaryLangChainChatModel(BaseChatModel):
    """LangChain adapter backed by Qwen with Gemini fallback."""

    timeout_seconds: float = 30.0
    max_output_tokens: int = settings.agent_model_max_output_tokens
    response_mime_type: str | None = "application/json"

    @property
    def _llm_type(self) -> str:
        return "shopy-primary-llm"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "timeout_seconds": self.timeout_seconds,
            "max_output_tokens": self.max_output_tokens,
            "response_mime_type": self.response_mime_type,
        }

    def _generate(self, *args: Any, **kwargs: Any) -> ChatResult:
        raise RuntimeError("PrimaryLangChainChatModel is async-only; call ainvoke().")

    async def _agenerate(self, messages: list[BaseMessage], stop: list[str] | None = None, **kwargs: Any) -> ChatResult:
        system_instruction, contents = _provider_contents(messages)
        generation = await PrimaryLLMClient(timeout_seconds=self.timeout_seconds).generate_with_usage(
            system_instruction=system_instruction,
            contents=contents,
            max_output_tokens=int(kwargs.get("max_output_tokens", self.max_output_tokens)),
            response_mime_type=kwargs.get("response_mime_type", self.response_mime_type),
            enable_thinking=kwargs.get("enable_thinking"),
        )
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=generation.text))])
