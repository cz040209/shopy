from fastapi import APIRouter

from .routes import auth, catalog, chat, commerce, health, transcription, vision


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(catalog.router)
api_router.include_router(commerce.router)
api_router.include_router(chat.router)
api_router.include_router(transcription.router)
api_router.include_router(vision.router)
