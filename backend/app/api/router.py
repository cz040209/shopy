from fastapi import APIRouter

from .routes import chat, health, transcription, vision


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(chat.router)
api_router.include_router(transcription.router)
api_router.include_router(vision.router)
