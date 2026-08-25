from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from uuid import UUID

from app.agentic.observability import OrchestrationRecorder
from app.agentic.orchestrator import ShoppingOrchestrator
from app.agentic.tools import CommerceToolRegistry
from app.database import get_db
from app.models import OrchestrationRun, User

from ..schemas import AgentRunRequest, OrchestrationRunResponse
from .auth import get_current_user


router = APIRouter(prefix="/api/v1/agentic", tags=["agentic shopping"])


def run_response(run: OrchestrationRun) -> OrchestrationRunResponse:
    return OrchestrationRunResponse.model_validate(run)


@router.post("/runs", response_model=OrchestrationRunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    payload: AgentRunRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrchestrationRunResponse:
    from uuid import uuid4

    request_id = uuid4().hex[:12]
    recorder = OrchestrationRecorder(db, request_id=request_id, user=user)
    registry = CommerceToolRegistry(db, request_id=request_id, recorder=recorder)
    orchestrator = ShoppingOrchestrator(tool_registry=registry, recorder=recorder)
    await orchestrator.ainvoke(payload.user_request)
    if recorder.run is None:
        raise HTTPException(status_code=500, detail="The orchestration run was not created.")
    db.refresh(recorder.run)
    return run_response(recorder.run)


@router.get("/runs", response_model=list[OrchestrationRunResponse])
def list_runs(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[OrchestrationRunResponse]:
    records = db.scalars(
        select(OrchestrationRun)
        .where(OrchestrationRun.user_id == user.id)
        .options(selectinload(OrchestrationRun.events))
        .order_by(OrchestrationRun.created_at.desc())
    ).all()
    return [run_response(record) for record in records]


@router.get("/runs/{run_id}", response_model=OrchestrationRunResponse)
def get_run(run_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> OrchestrationRunResponse:
    record = db.scalar(
        select(OrchestrationRun)
        .where(OrchestrationRun.id == run_id, OrchestrationRun.user_id == user.id)
        .options(selectinload(OrchestrationRun.events))
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orchestration run not found.")
    return run_response(record)
