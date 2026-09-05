"""Celery application and durable background jobs for Shopy."""
from __future__ import annotations

import logging
from uuid import UUID

from celery import Celery
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import SessionLocal
from app.models import Order
from app.services.receipts import build_paid_receipt_pdf, send_paid_receipt_email


logger = logging.getLogger(__name__)

celery_app = Celery("shopy", broker=settings.redis_url)
celery_app.conf.update(
    task_default_queue="shopy",
    task_ignore_result=True,
    broker_connection_retry_on_startup=True,
)


@celery_app.task(name="shopy.send_paid_receipt")
def send_paid_receipt(order_id: str, recipient_email: str, recipient_name: str) -> None:
    """Generate and email a paid-order receipt outside the API process."""
    with SessionLocal() as session:
        order = session.scalar(
            select(Order)
            .where(Order.id == UUID(order_id))
            .options(selectinload(Order.items))
        )
        if order is None:
            logger.warning("Receipt task skipped because order %s no longer exists", order_id)
            return
        receipt_pdf = build_paid_receipt_pdf(order, customer_name=recipient_name)

    send_paid_receipt_email(
        recipient_email=recipient_email,
        recipient_name=recipient_name,
        order_number=order.order_number,
        receipt_pdf=receipt_pdf,
    )
