from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Cart, CartStatus, Order, OrderItem, OrderStatus, Payment, PaymentMethod, PaymentStatus, User

from .cart import cart_subtotal, get_active_cart


def create_order_from_cart(
    db: Session,
    user: User,
    *,
    shipping_address: dict[str, str],
    notes: str | None,
    payment_method: PaymentMethod,
    shipping_fee: Decimal,
) -> Order:
    cart = get_active_cart(db, user)
    if not cart.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Your cart is empty.")
    for item in cart.items:
        available = item.product.inventory_quantity - item.product.reserved_quantity
        if item.quantity > available:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{item.product.name} no longer has enough stock.")

    subtotal = cart_subtotal(cart)
    tax_amount = ((shipping_fee * Decimal("0.06") * Decimal("20")).to_integral_value(rounding=ROUND_CEILING) / Decimal("20")).quantize(Decimal("0.01"))
    handling_amount = shipping_fee
    total = subtotal + tax_amount + handling_amount
    order = Order(
        user=user,
        cart=cart,
        order_number=f"SHP-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:8].upper()}",
        status=OrderStatus.PENDING,
        payment_status=PaymentStatus.PENDING,
        currency=cart.currency,
        subtotal=subtotal,
        tax_amount=tax_amount,
        handling_amount=handling_amount,
        discount_amount=Decimal("0"),
        total_amount=total,
        shipping_address_snapshot=shipping_address,
        notes=notes,
        placed_at=datetime.now(timezone.utc),
    )
    for item in cart.items:
        product = item.product
        product.inventory_quantity -= item.quantity
        order.items.append(OrderItem(
            product=product,
            seller=product.seller,
            sku=product.sku,
            product_name=product.name,
            quantity=item.quantity,
            unit_price=item.unit_price,
            line_total=item.unit_price * item.quantity,
            product_snapshot={"slug": product.slug, "image_url": product.images[0].url if product.images else None},
        ))
    order.payments.append(Payment(method=payment_method, amount=total, currency=cart.currency, provider="checkout_pending"))
    db.add(order)
    cart.status = CartStatus.CONVERTED
    # Flush the state transition before inserting the next active cart. This is
    # also required by SQLite test environments, which cannot mirror the
    # PostgreSQL partial unique index exactly.
    db.flush()
    db.add(Cart(user=user, currency=cart.currency))
    return order
