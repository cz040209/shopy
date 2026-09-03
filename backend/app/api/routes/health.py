from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.config import settings
from app.database import check_database_connection


router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "model": settings.active_llm_model}


@router.get("/health/database")
async def database_health() -> dict[str, str]:
    try:
        await run_in_threadpool(check_database_connection)
    except Exception as error:
        raise HTTPException(status_code=503, detail="Database connection unavailable.") from error
    return {"status": "ok", "database": "postgresql"}
