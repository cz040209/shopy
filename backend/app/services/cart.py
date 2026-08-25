from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Cart, CartItem, CartStatus, Product, ProductStatus, User


def get_active_cart(db: Session, user: User, *, with_items: bool = True) -> Cart:
    statement = select(Cart).where(Cart.user_id == user.id, Cart.status == CartStatus.ACTIVE)
    if with_items:
        statement = statement.options(
            selectinload(Cart.items).selectinload(CartItem.product).selectinload(Product.images),
            selectinload(Cart.items).selectinload(CartItem.product).selectinload(Product.category),
            selectinload(Cart.items).selectinload(CartItem.product).selectinload(Product.seller),
        )
    cart = db.scalar(statement)
    if cart is None:
        cart = Cart(user=user)
        db.add(cart)
        db.flush()
    return cart


def add_cart_item(db: Session, user: User, product_id: UUID, quantity: int) -> Cart:
    product = db.get(Product, product_id)
    if product is None or product.status != ProductStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    cart = get_active_cart(db, user)
    available = product.inventory_quantity - product.reserved_quantity
    if available < quantity:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The requested quantity is not available.")
    item = next((candidate for candidate in cart.items if candidate.product_id == product.id), None)
    if item is None:
        cart.items.append(CartItem(product=product, quantity=quantity, unit_price=product.price))
    elif item.quantity + quantity > available:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The requested quantity is not available.")
    else:
        item.quantity += quantity
        item.unit_price = product.price
    db.commit()
    return get_active_cart(db, user)


def update_cart_item(db: Session, user: User, item_id: UUID, quantity: int) -> Cart:
    cart = get_active_cart(db, user)
    item = next((candidate for candidate in cart.items if candidate.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found.")
    available = item.product.inventory_quantity - item.product.reserved_quantity
    if quantity > available:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The requested quantity is not available.")
    item.quantity = quantity
    item.unit_price = item.product.price
    db.commit()
    return get_active_cart(db, user)


def remove_cart_item(db: Session, user: User, item_id: UUID) -> Cart:
    cart = get_active_cart(db, user)
    item = next((candidate for candidate in cart.items if candidate.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found.")
    db.delete(item)
    db.commit()
    return get_active_cart(db, user)


def cart_subtotal(cart: Cart) -> Decimal:
    return sum((item.unit_price * item.quantity for item in cart.items), Decimal("0"))
