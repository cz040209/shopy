from __future__ import annotations

from collections.abc import Sequence
import re
from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Category, Product, ProductStatus, Review, Seller, SellerStatus


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
        # Search meaningful words independently and include category metadata.
        # A shopper asking for "skincare facial product" should find a
        # "Facial Cleanser" in the "Skincare" category even when that exact
        # phrase does not occur in one database column.
        terms = re.findall(r"[\w-]+", query.lower())
        predicates = []
        for term in terms:
            pattern = f"%{term}%"
            predicates.extend(
                [
                    Product.name.ilike(pattern),
                    Product.brand.ilike(pattern),
                    Product.description.ilike(pattern),
                    Category.name.ilike(pattern),
                    Category.slug.ilike(pattern),
                ]
            )
        if predicates:
            statement = statement.join(Product.category).where(or_(*predicates))
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


def get_seller(db: Session, identifier: UUID | str) -> Seller | None:
    statement = select(Seller).where(Seller.status == SellerStatus.ACTIVE)
    statement = statement.where(Seller.id == identifier) if isinstance(identifier, UUID) else statement.where(Seller.slug == identifier)
    return db.scalar(statement)


def get_product_reviews(db: Session, product_id: UUID, *, limit: int = 20) -> Sequence[Review]:
    return db.scalars(
        select(Review)
        .where(Review.product_id == product_id, Review.is_published.is_(True))
        .order_by(Review.created_at.desc())
        .limit(limit)
    ).all()
