from __future__ import annotations

from collections.abc import Sequence
import re
from uuid import UUID

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Category, Product, ProductStatus, Review, Seller, SellerStatus


SEARCH_STOP_WORDS = {
    "a", "an", "and", "best", "build", "for", "from", "in", "item", "items", "of", "or", "product", "products", "the", "to", "under", "value", "with",
}

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
    strict_predicates = []
    fallback_predicates = []
    if query:
        # Search meaningful words independently and include category metadata.
        # A shopper asking for "skincare facial product" should find a
        # "Facial Cleanser" in the "Skincare" category even when that exact
        # phrase does not occur in one database column.
        terms = [
            term for term in re.findall(r"[\w-]+", query.lower())
            if len(term) > 2 and term not in SEARCH_STOP_WORDS and not term.startswith("rm") and not term.isdigit()
        ]
        for term in terms:
            variant_predicates = []
            pattern = f"%{term}%"
            variant_predicates.extend(
                [
                    Product.name.ilike(pattern),
                    Product.brand.ilike(pattern),
                    Product.description.ilike(pattern),
                    Category.name.ilike(pattern),
                    Category.slug.ilike(pattern),
                ]
            )
            strict_predicates.append(or_(*variant_predicates))
            fallback_predicates.extend(variant_predicates)
    if category_slug:
        statement = statement.join(Product.category).where(Category.slug == category_slug, Category.is_active.is_(True))
    elif strict_predicates:
        statement = statement.join(Product.category)
    if seller_slug:
        statement = statement.join(Product.seller).where(Seller.slug == seller_slug, Seller.status == SellerStatus.ACTIVE)
    if strict_predicates:
        strict_results = db.scalars(
            statement.where(and_(*strict_predicates)).order_by(Product.created_at.desc()).offset(offset).limit(limit)
        ).all()
        if strict_results:
            return strict_results
        # Preserve typo tolerance for a query such as "Mirrorlesscamera", but
        # only after an all-concepts search found nothing. This prevents broad
        # partial matches from crowding out relevant bundle candidates.
        return db.scalars(
            statement.where(or_(*fallback_predicates)).order_by(Product.created_at.desc()).offset(offset).limit(limit)
        ).all()
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
