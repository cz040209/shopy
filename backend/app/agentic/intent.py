from __future__ import annotations

import json
from typing import Protocol

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import ValidationError

from .schemas import MissionInterpretation


class StructuredOutputError(ValueError):
    """The model response did not conform to the required mission schema."""


class AsyncChatModel(Protocol):
    async def ainvoke(self, input: object, **kwargs: object) -> AIMessage: ...


INTENT_SYSTEM_PROMPT = """You extract a shopping mission for an e-commerce assistant.
Return only valid JSON, without Markdown. Use this exact schema:
{"mission_type": string, "goal": string, "budget": number|null,
 "preferences": [string], "constraints": [string], "owned_items": [string],
 "priorities": [string]}
Use concise normalized values. Do not invent details that the customer did not provide.
Use mission_type "information_request" for identity, capability, greeting, or other
non-shopping questions. Use a shopping mission type for catalog recommendations."""


def _json_object(content: object) -> dict[str, object]:
    text = str(content).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise StructuredOutputError("Intent model returned invalid JSON.") from error
    if not isinstance(value, dict):
        raise StructuredOutputError("Intent model must return a JSON object.")
    return value


class IntentMissionAgent:
    def __init__(self, model: AsyncChatModel) -> None:
        self.model = model

    async def interpret(self, user_request: str) -> MissionInterpretation:
        response = await self.model.ainvoke([
            SystemMessage(content=INTENT_SYSTEM_PROMPT),
            HumanMessage(content=user_request),
        ])
        try:
            return MissionInterpretation.model_validate(_json_object(response.content))
        except ValidationError as error:
            raise StructuredOutputError("Intent model response does not match the mission schema.") from error
