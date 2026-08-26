from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.ai.gemini import GeminiClient


def _gemini_contents(messages: list[BaseMessage]) -> tuple[str, list[dict[str, Any]]]:
    system_parts: list[str] = []
    contents: list[dict[str, Any]] = []
    for message in messages:
        text = str(message.content)
        if message.type == "system":
            system_parts.append(text)
        else:
            contents.append({"role": "model" if message.type == "ai" else "user", "parts": [{"text": text}]})
    return "\n\n".join(system_parts), contents


class GeminiLangChainChatModel(BaseChatModel):
    """LangChain chat-model adapter backed by the existing Gemini HTTP client."""

    timeout_seconds: float = 30.0
    max_output_tokens: int = 700
    response_mime_type: str | None = "application/json"

    @property
    def _llm_type(self) -> str:
        return "shopy-gemini"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "timeout_seconds": self.timeout_seconds,
            "max_output_tokens": self.max_output_tokens,
            "response_mime_type": self.response_mime_type,
        }

    def _generate(self, *args: Any, **kwargs: Any) -> ChatResult:
        raise RuntimeError("GeminiLangChainChatModel is async-only; call ainvoke().")

    async def _agenerate(self, messages: list[BaseMessage], stop: list[str] | None = None, **kwargs: Any) -> ChatResult:
        system_instruction, contents = _gemini_contents(messages)
        generation = await GeminiClient(timeout_seconds=self.timeout_seconds).generate_with_usage(
            system_instruction=system_instruction,
            contents=contents,
            max_output_tokens=self.max_output_tokens,
            response_mime_type=self.response_mime_type,
        )
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=generation.text))])
