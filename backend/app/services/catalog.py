from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Category, Product, ProductStatus, Seller, SellerStatus


def active_products_query() -> Select[tuple[Product]]:
    return (
        select(Product)
        .where(Product.status == ProductStatus.ACTIVE)
        .options(
            selectinload(Product.images),
            selectinload(Product.category),
            selectinload(Product.seller),
        )
    )


def list_products(
    db: Session,
    *,
    query: str | None = None,
    category_slug: str | None = None,
    seller_slug: str | None = None,
    offset: int = 0,
    limit: int = 48,
) -> Sequence[Product]:
    statement = active_products_query()
    if query:
        term = f"%{query.strip()}%"
        statement = statement.where(or_(Product.name.ilike(term), Product.brand.ilike(term), Product.description.ilike(term)))
    if category_slug:
        statement = statement.join(Product.category).where(Category.slug == category_slug, Category.is_active.is_(True))
    if seller_slug:
        statement = statement.join(Product.seller).where(Seller.slug == seller_slug, Seller.status == SellerStatus.ACTIVE)
    return db.scalars(statement.order_by(Product.created_at.desc()).offset(offset).limit(limit)).all()


def get_product(db: Session, identifier: UUID | str) -> Product | None:
    statement = active_products_query()
    if isinstance(identifier, UUID):
        statement = statement.where(Product.id == identifier)
    else:
        statement = statement.where(Product.slug == identifier)
    return db.scalar(statement)

