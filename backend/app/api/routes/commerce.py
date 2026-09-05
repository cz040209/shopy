from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.config import settings
from app.models import Order, OrderItem, PaymentMethod, Review, User, Wallet, WalletTransaction
from app.services.cart import add_cart_item, cart_subtotal, get_active_cart, remove_cart_item, update_cart_item
from app.services.orders import create_order_from_cart
from app.worker import send_paid_receipt
from app.services.wallets import get_wallet, pay_order_with_wallet, top_up_wallet

from ..schemas import (
    AddCartItemRequest, CartItemResponse, CartResponse, CheckoutRequest, OrderItemResponse,
    OrderResponse, ReviewRequest, ReviewResponse, UpdateCartItemRequest, WalletResponse,
    WalletTopUpRequest, WalletTransactionResponse,
)
from .auth import get_current_user
from .catalog import product_response


router = APIRouter(prefix="/api/v1", tags=["commerce"])
logger = logging.getLogger(__name__)


def cart_response(cart) -> CartResponse:
    return CartResponse(
        id=cart.id,
        currency=cart.currency,
        subtotal=cart_subtotal(cart),
        items=[CartItemResponse(id=item.id, product=product_response(item.product), quantity=item.quantity, unit_price=item.unit_price, line_total=item.unit_price * item.quantity) for item in cart.items],
    )


def order_response(order: Order, *, receipt_email_queued: bool = False) -> OrderResponse:
    return OrderResponse(
        id=order.id, order_number=order.order_number, status=order.status, payment_status=order.payment_status,
        currency=order.currency, subtotal=order.subtotal, tax_amount=order.tax_amount,
        handling_amount=order.handling_amount, discount_amount=order.discount_amount,
        total_amount=order.total_amount, shipping_address_snapshot=order.shipping_address_snapshot,
        placed_at=order.placed_at, created_at=order.created_at,
        items=[OrderItemResponse(id=item.id, product_id=item.product_id, sku=item.sku, product_name=item.product_name, quantity=item.quantity, unit_price=item.unit_price, line_total=item.line_total, product_snapshot=item.product_snapshot) for item in order.items], receipt_email_queued=receipt_email_queued,
    )


@router.get("/cart", response_model=CartResponse)
def cart(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CartResponse:
    return cart_response(get_active_cart(db, user))


@router.post("/cart/items", response_model=CartResponse, status_code=status.HTTP_201_CREATED)
def add_item(payload: AddCartItemRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CartResponse:
    return cart_response(add_cart_item(db, user, payload.product_id, payload.quantity))


@router.patch("/cart/items/{item_id}", response_model=CartResponse)
def change_item(item_id: UUID, payload: UpdateCartItemRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CartResponse:
    return cart_response(update_cart_item(db, user, item_id, payload.quantity))


@router.delete("/cart/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    remove_cart_item(db, user, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/orders/checkout", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def checkout(payload: CheckoutRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> OrderResponse:
    order = create_order_from_cart(
        db, user, shipping_address=payload.shipping_address.model_dump(), notes=payload.notes,
        payment_method=payload.payment_method, shipping_fee=payload.shipping_fee,
    )
    if payload.payment_method == PaymentMethod.SHOPY_PAY:
        pay_order_with_wallet(db, user, order)
    db.commit()
    db.refresh(order)
    receipt_email_queued = order.payment_status.value == "paid" and settings.receipt_email_enabled
    if receipt_email_queued:
        try:
            send_paid_receipt.delay(str(order.id), user.email, user.full_name)
        except Exception:
            # A receipt outage must not turn an already-committed checkout into
            # a failed purchase. The worker can be restored independently.
            logger.exception("Unable to queue paid receipt for %s", order.order_number)
            receipt_email_queued = False
    return order_response(order, receipt_email_queued=receipt_email_queued)


@router.get("/orders", response_model=list[OrderResponse])
def orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[OrderResponse]:
    records = db.scalars(select(Order).where(Order.user_id == user.id).options(selectinload(Order.items)).order_by(Order.created_at.desc())).all()
    return [order_response(order) for order in records]


@router.get("/orders/{order_id}", response_model=OrderResponse)
def order(order_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> OrderResponse:
    record = db.scalar(select(Order).where(Order.id == order_id, Order.user_id == user.id).options(selectinload(Order.items)))
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    return order_response(record)


@router.get("/wallet", response_model=WalletResponse)
def wallet(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> WalletResponse:
    record = get_wallet(db, user)
    db.commit()
    db.refresh(record, attribute_names=["transactions"])
    transactions = sorted(record.transactions, key=lambda item: item.created_at, reverse=True)
    return WalletResponse(
        id=record.id, currency=record.currency, balance=record.balance, daily_limit=record.daily_limit,
        monthly_limit=record.monthly_limit, is_verified=record.is_verified,
        transactions=[WalletTransactionResponse(id=item.id, reference=item.reference, type=item.type.value, status=item.status.value, amount=item.amount, currency=item.currency, description=item.description, created_at=item.created_at) for item in transactions],
    )


@router.post("/wallet/top-ups", response_model=WalletResponse, status_code=status.HTTP_201_CREATED)
def wallet_top_up(payload: WalletTopUpRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> WalletResponse:
    record = top_up_wallet(db, user, amount=payload.amount, payment_source=payload.payment_source)
    db.commit()
    db.refresh(record, attribute_names=["transactions"])
    transactions = sorted(record.transactions, key=lambda item: item.created_at, reverse=True)
    return WalletResponse(
        id=record.id, currency=record.currency, balance=record.balance, daily_limit=record.daily_limit,
        monthly_limit=record.monthly_limit, is_verified=record.is_verified,
        transactions=[WalletTransactionResponse(id=item.id, reference=item.reference, type=item.type.value, status=item.status.value, amount=item.amount, currency=item.currency, description=item.description, created_at=item.created_at) for item in transactions],
    )


@router.post("/products/{product_id}/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create_review(product_id: UUID, payload: ReviewRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ReviewResponse:
    purchased_item = db.scalar(select(OrderItem).join(Order).where(Order.user_id == user.id, OrderItem.product_id == product_id))
    if purchased_item is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only customers who purchased this product can review it.")
    review = Review(user_id=user.id, product_id=product_id, order_item_id=purchased_item.id, rating=payload.rating, title=payload.title, body=payload.body, is_verified_purchase=True)
    db.add(review)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You have already reviewed this product.") from error
    average, count = db.execute(select(func.avg(Review.rating), func.count(Review.id)).where(Review.product_id == product_id, Review.is_published.is_(True))).one()
    product = purchased_item.product
    product.rating_average = Decimal(str(average or 0)).quantize(Decimal("0.01"))
    product.review_count = count or 0
    db.commit()
    db.refresh(review)
    return ReviewResponse(id=review.id, rating=review.rating, title=review.title, body=review.body, is_verified_purchase=True, created_at=review.created_at, author_name=user.full_name)
