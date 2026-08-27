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


def top_up_wallet(db: Session, user: User, *, amount: Decimal, payment_source: str) -> Wallet:
    wallet = get_wallet(db, user, lock=True)
    now = datetime.now(timezone.utc)
    daily_total = db.scalar(
        select(func.coalesce(func.sum(WalletTransaction.amount), Decimal("0"))).where(
            WalletTransaction.wallet_id == wallet.id,
            WalletTransaction.type == TransactionType.TOP_UP,
            WalletTransaction.status == TransactionStatus.COMPLETED,
            WalletTransaction.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0),
        )
    ) or Decimal("0")
    if daily_total + amount > wallet.daily_limit:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This top-up exceeds your daily wallet limit.")

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
