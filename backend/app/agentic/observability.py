"""Database-backed, privacy-aware audit trail for observable agent work."""
from __future__ import annotations

from datetime import datetime, timezone
from contextvars import ContextVar
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai_logging import customer_input_for_log
from app.models import Conversation, OrchestrationRun, OrchestrationRunEvent, User


SENSITIVE_KEYS = {"password", "token", "secret", "api_key", "authorization", "cookie", "card", "cvc"}
MAX_STRING_LENGTH = 4_000
active_recorder: ContextVar["OrchestrationRecorder | None"] = ContextVar("active_orchestration_recorder", default=None)


def safe_audit_data(value: Any) -> Any:
    """Retain observable data while stripping secrets and constraining payloads."""
    if isinstance(value, dict):
        return {
            str(key): (
                "[redacted]" if any(secret in str(key).lower() for secret in SENSITIVE_KEYS)
                else customer_input_for_log(str(item)) if str(key) == "user_request"
                else safe_audit_data(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [safe_audit_data(item) for item in value[:100]]
    if isinstance(value, bytes):
        return f"[binary payload omitted: {len(value)} bytes]"
    if isinstance(value, str):
        return value if len(value) <= MAX_STRING_LENGTH else f"{value[:MAX_STRING_LENGTH]}…[truncated]"
    return value


class OrchestrationRecorder:
    def __init__(self, db: Session, *, request_id: str, user: User | None = None, conversation: Conversation | None = None) -> None:
        self.db = db
        self.request_id = request_id
        self.user = user
        self.conversation = conversation
        self.run: OrchestrationRun | None = None
        self._sequence = 0

    def start(self, state: dict[str, Any]) -> OrchestrationRun:
        self.run = OrchestrationRun(
            request_id=self.request_id,
            user=self.user,
            conversation=self.conversation,
            status="running",
            user_request=customer_input_for_log(str(state["user_request"])),
            initial_state=safe_audit_data(state),
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(self.run)
        self.db.commit()
        self.db.refresh(self.run)
        self.record("run_started", status="completed", input_data={"user_request": customer_input_for_log(str(state["user_request"]))})
        return self.run

    def record(
        self,
        event_type: str,
        *,
        node_name: str | None = None,
        tool_name: str | None = None,
        status: str = "completed",
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        error_message: str | None = None,
        started_at: datetime | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> None:
        if self.run is None:
            return
        # Resynchronise from persisted events before every append. This keeps a
        # timeline monotonic even if a run is resumed or a recorder is reached
        # from a nested async context.
        persisted_sequence = self.db.scalar(
            select(func.max(OrchestrationRunEvent.sequence)).where(OrchestrationRunEvent.run_id == self.run.id)
        ) or 0
        self._sequence = max(self._sequence, int(persisted_sequence)) + 1
        completed_at = datetime.now(timezone.utc)
        duration_ms = round((completed_at - started_at).total_seconds() * 1000) if started_at else None
        self.db.add(OrchestrationRunEvent(
            run_id=self.run.id, sequence=self._sequence, event_type=event_type,
            node_name=node_name, tool_name=tool_name, status=status,
            input_data=safe_audit_data(input_data or {}), output_data=safe_audit_data(output_data or {}),
            error_message=error_message, started_at=started_at, completed_at=completed_at, duration_ms=duration_ms,
            input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens,
        ))
        self.db.commit()

    def record_llm_call(self, *, input_tokens: int | None, output_tokens: int | None, total_tokens: int | None, started_at: datetime | None = None) -> None:
        """Persist provider-reported usage for one LLM call and update run totals."""
        if self.run is None:
            return
        input_count = max(0, int(input_tokens or 0))
        output_count = max(0, int(output_tokens or 0))
        total_count = max(0, int(total_tokens if total_tokens is not None else input_count + output_count))
        self.run.input_tokens += input_count
        self.run.output_tokens += output_count
        self.run.total_tokens += total_count
        self.record(
            "llm_call", status="completed", input_data={}, output_data={}, started_at=started_at,
            input_tokens=input_count, output_tokens=output_count, total_tokens=total_count,
        )

    def finish(
        self,
        state: dict[str, Any],
        *,
        final_response: str | None = None,
        response_context: dict[str, Any] | None = None,
    ) -> None:
        if self.run is None:
            return
        self.run.status = "completed" if (state.get("audit_result") or {}).get("status") != "fail" else "failed"
        self.run.final_state = safe_audit_data(state)
        self.run.final_response = final_response if final_response is not None else state.get("final_response")
        self.run.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        if final_response is not None:
            self.record(
                "assistant_response_generated",
                status="completed",
                output_data={
                    "final_response": final_response,
                    **(response_context or {}),
                },
            )
        self.record(
            "run_finished",
            status=self.run.status,
            output_data={
                "final_response": self.run.final_response,
                "audit_result": state.get("audit_result"),
            },
        )

    def fail(self, error: Exception) -> None:
        if self.run is None:
            return
        self.run.status = "failed"
        self.run.error_message = str(error)
        self.run.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.record("run_failed", status="failed", error_message=str(error))
