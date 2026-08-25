from typing import Literal

from pydantic import BaseModel, Field


VisionMode = Literal["shop_room", "complete_look", "shop_object"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)


class ChatResponse(BaseModel):
    reply: str


class VisionResponse(BaseModel):
    mode: VisionMode
    analysis: str


class TranscriptionResponse(BaseModel):
    transcript: str
    language: str | None = None
    duration_seconds: float | None = None
