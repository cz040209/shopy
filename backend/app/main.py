from pathlib import Path
from shutil import copy2

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import api_router
from .config import settings


LEGACY_UPLOAD_DIRECTORY = Path("/tmp/shopy-uploads")


def prepare_upload_directory() -> None:
    """Create durable storage and retain avatars uploaded under the old default."""
    settings.upload_directory.mkdir(parents=True, exist_ok=True)

    # Earlier versions stored avatars in /tmp. Copying (rather than moving)
    # keeps an in-place upgrade safe while making existing database URLs work
    # after the application changes to durable storage.
    legacy_avatars = LEGACY_UPLOAD_DIRECTORY / "avatars"
    target_avatars = settings.upload_directory / "avatars"
    if settings.upload_directory == LEGACY_UPLOAD_DIRECTORY or not legacy_avatars.is_dir():
        return
    target_avatars.mkdir(parents=True, exist_ok=True)
    for source in legacy_avatars.iterdir():
        if source.is_file():
            target = target_avatars / source.name
            if not target.exists():
                copy2(source, target)


def create_app() -> FastAPI:
    application = FastAPI(title="Shopy AI API", version="1.0.0")
    prepare_upload_directory()
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
