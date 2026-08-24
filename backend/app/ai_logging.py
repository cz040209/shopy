"""Structured terminal logs for Shopy AI request processing.

These logs intentionally describe execution stages and observable inputs/outputs.
They never include API keys or private chain-of-thought reasoning from an AI model.
"""

import json
import logging
import sys
from typing import Any

from .config import settings


logger = logging.getLogger("shopy.ai")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def log_ai_event(event: str, *, request_id: str, **fields: Any) -> None:
    """Write a single JSON event that is easy to inspect or pipe to a log tool."""
    payload: dict[str, Any] = {"event": event, "request_id": request_id, **fields}
    logger.info(json.dumps(payload, ensure_ascii=False, default=str))


def customer_input_for_log(value: str) -> str:
    """Optionally hide content in logs while preserving debugging metadata."""
    if settings.ai_log_customer_input:
        return value
    return f"[redacted: {len(value)} characters]"
