from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import api_router
from .config import settings


def create_app() -> FastAPI:
    application = FastAPI(title="Shopy AI API", version="1.0.0")
    settings.upload_directory.mkdir(parents=True, exist_ok=True)
    application.mount("/uploads", StaticFiles(directory=settings.upload_directory), name="uploads")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["POST", "GET", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )
    application.include_router(api_router)
    return application


app = create_app()
