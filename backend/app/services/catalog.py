from __future__ import annotations

from collections.abc import Sequence
import re
from uuid import UUID

from sqlalchemy import Select, Text, and_, case, cast, literal, or_, select
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
    queries: Sequence[str] | None = None,
    category_slug: str | None = None,
    seller_slug: str | None = None,
    offset: int = 0,
    limit: int = 48,
) -> Sequence[Product]:
    statement = active_products_query()
    query_values = list(dict.fromkeys(
        value.strip() for value in [*(queries or []), query or ""] if value and value.strip()
    ))
    strict_predicates = []
    fallback_predicates = []
    relevance_parts = []
    if query_values:
        # Search meaningful words independently across all customer-visible
        # catalog evidence. Each expanded phrase is an alternative route to
        # the same product role, so phrases are ORed while terms inside a
        # phrase are ANDed.
        # A shopper asking for "skincare facial product" should find a
        # "Facial Cleanser" in the "Skincare" category even when that exact
        # phrase does not occur in one database column.
        for value in query_values:
            terms = [
                term for term in re.findall(r"[\w-]+", value.lower())
                if len(term) > 2 and term not in SEARCH_STOP_WORDS
                and not term.startswith("rm") and not term.isdigit()
            ]
            phrase_terms = []
            for term in terms:
                pattern = f"%{term}%"
                weighted_fields = (
                    (Product.name.ilike(pattern), 8),
                    (Category.name.ilike(pattern), 7),
                    (Category.slug.ilike(pattern), 6),
                    (Product.brand.ilike(pattern), 4),
                    (Product.description.ilike(pattern), 3),
                    (cast(Product.specs, Text).ilike(pattern), 2),
                    (cast(Product.attributes, Text).ilike(pattern), 2),
                )
                variants = [predicate for predicate, _ in weighted_fields]
                phrase_terms.append(or_(*variants))
                fallback_predicates.extend(variants)
                relevance_parts.extend(
                    case((predicate, weight), else_=0)
                    for predicate, weight in weighted_fields
                )
            if phrase_terms:
                strict_predicates.append(and_(*phrase_terms))
    if category_slug:
        statement = statement.join(Product.category).where(Category.slug == category_slug, Category.is_active.is_(True))
    elif strict_predicates:
        statement = statement.join(Product.category)
    if seller_slug:
        statement = statement.join(Product.seller).where(Seller.slug == seller_slug, Seller.status == SellerStatus.ACTIVE)
    if strict_predicates:
        relevance = sum(relevance_parts, literal(0))
        strict_results = db.scalars(
            statement.where(or_(*strict_predicates))
            .order_by(relevance.desc(), Product.created_at.desc()).offset(offset).limit(limit)
        ).all()
        if strict_results:
            return strict_results
        if len(query_values) > 1:
            # Expanded role searches already contain alternative vocabulary.
            # Falling back to any one word here would let incidental feature
            # mentions crowd in products from a different role.
            return []
        # Preserve typo tolerance for a query such as "Mirrorlesscamera", but
        # only after an all-concepts search found nothing. This prevents broad
        # partial matches from crowding out relevant bundle candidates.
        return db.scalars(
            statement.where(or_(*fallback_predicates))
            .order_by(relevance.desc(), Product.created_at.desc()).offset(offset).limit(limit)
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
