"""Database-backed wallet operations.

All balance mutations and their ledger entries are created in the same database
transaction. Callers must commit only after their larger workflow succeeds.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Order,
    OrderStatus,
    PaymentStatus,
    TransactionStatus,
    TransactionType,
    User,
    Wallet,
    WalletTransaction,
)


def get_wallet(db: Session, user: User, *, lock: bool = False) -> Wallet:
    statement = select(Wallet).where(Wallet.user_id == user.id)
    if lock:
        statement = statement.with_for_update()
    wallet = db.scalar(statement)
    if wallet is None:
        wallet = Wallet(user_id=user.id, currency="MYR")
        db.add(wallet)
        db.flush()
    return wallet


def wallet_top_up_capacity(db: Session, wallet: Wallet, *, now: datetime | None = None) -> tuple[Decimal, Decimal]:
    """Return the server-authoritative daily and monthly top-up capacity.

    The ledger can be paginated or contain historical entries, so this must be
    calculated in the same timezone and from the same completed records as the
    top-up guard.  Clients receive these values instead of trying to recreate
    the rule from the activity list.
    """
    current_time = now or datetime.now(timezone.utc)
    today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    totals = db.execute(
        select(
            func.coalesce(func.sum(WalletTransaction.amount).filter(WalletTransaction.created_at >= today_start), Decimal("0")),
            func.coalesce(func.sum(WalletTransaction.amount).filter(WalletTransaction.created_at >= month_start), Decimal("0")),
        ).where(
            WalletTransaction.wallet_id == wallet.id,
            WalletTransaction.type == TransactionType.TOP_UP,
            WalletTransaction.status == TransactionStatus.COMPLETED,
        )
    ).one()
    daily_total, monthly_total = (Decimal(value or 0) for value in totals)
    return max(wallet.daily_limit - daily_total, Decimal("0")), max(wallet.monthly_limit - monthly_total, Decimal("0"))


def top_up_wallet(db: Session, user: User, *, amount: Decimal, payment_source: str) -> Wallet:
    wallet = get_wallet(db, user, lock=True)
    daily_remaining, monthly_remaining = wallet_top_up_capacity(db, wallet)
    if amount > daily_remaining:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This top-up exceeds your daily wallet limit.")
    if amount > monthly_remaining:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This top-up exceeds your monthly wallet limit.")

    wallet.balance += amount
    db.add(WalletTransaction(
        wallet=wallet,
        reference=f"WALLET-TOPUP-{uuid4().hex[:12].upper()}",
        type=TransactionType.TOP_UP,
        status=TransactionStatus.COMPLETED,
        amount=amount,
        currency=wallet.currency,
        description=f"Top up via {payment_source}",
        extra_data={"payment_source": payment_source},
    ))
    db.flush()
    return wallet


def pay_order_with_wallet(db: Session, user: User, order: Order) -> Wallet:
    wallet = get_wallet(db, user, lock=True)
    if wallet.currency != order.currency:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wallet currency does not match this order.")
    if wallet.balance < order.total_amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Your ShopyPay balance is insufficient for this order.")

    wallet.balance -= order.total_amount
    transaction = WalletTransaction(
        wallet=wallet,
        order=order,
        reference=f"WALLET-PURCHASE-{uuid4().hex[:12].upper()}",
        type=TransactionType.PURCHASE,
        status=TransactionStatus.COMPLETED,
        amount=order.total_amount,
        currency=wallet.currency,
        description=f"ShopyPay payment for {order.order_number}",
        extra_data={"order_number": order.order_number},
    )
    db.add(transaction)
    order.status = OrderStatus.CONFIRMED
    order.payment_status = PaymentStatus.PAID
    for payment in order.payments:
        payment.status = PaymentStatus.PAID
        payment.provider = "shopy_pay_wallet"
        payment.provider_reference = transaction.reference
        payment.captured_at = datetime.now(timezone.utc)
    db.flush()
    return wallet
