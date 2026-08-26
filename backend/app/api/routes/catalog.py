from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Category, Product, Review, Seller, SellerStatus
from app.services.catalog import get_product, list_products

from ..schemas import CategoryResponse, ProductListResponse, ProductResponse, ReviewResponse, SellerResponse


router = APIRouter(prefix="/api/v1", tags=["catalog"])


def product_response(product: Product) -> ProductResponse:
    return ProductResponse(
        id=product.id, slug=product.slug, name=product.name, brand=product.brand,
        description=product.description, price=product.price, compare_at_price=product.compare_at_price,
        currency=product.currency, badge=product.badge, emoji=product.emoji, specs=product.specs,
        attributes=product.attributes, rating_average=product.rating_average, review_count=product.review_count,
        inventory_quantity=max(0, product.inventory_quantity - product.reserved_quantity),
        category=CategoryResponse.model_validate(product.category), seller=SellerResponse.model_validate(product.seller),
        images=[{"url": image.url, "alt_text": image.alt_text} for image in sorted(product.images, key=lambda item: item.sort_order)],
    )


@router.get("/products", response_model=ProductListResponse)
def products(
    q: str | None = Query(default=None, max_length=160),
    category: str | None = Query(default=None, max_length=140),
    seller: str | None = Query(default=None, max_length=180),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> ProductListResponse:
    records = list_products(db, query=q, category_slug=category, seller_slug=seller, offset=(page - 1) * page_size, limit=page_size)
    return ProductListResponse(items=[product_response(record) for record in records], page=page, page_size=page_size)


@router.get("/products/{product_id}", response_model=ProductResponse)
def product(product_id: UUID, db: Session = Depends(get_db)) -> ProductResponse:
    record = get_product(db, product_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    return product_response(record)


@router.get("/products/slug/{slug}", response_model=ProductResponse)
def product_by_slug(slug: str, db: Session = Depends(get_db)) -> ProductResponse:
    record = get_product(db, slug)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    return product_response(record)


@router.get("/categories", response_model=list[CategoryResponse])
def categories(db: Session = Depends(get_db)) -> list[CategoryResponse]:
    return [CategoryResponse.model_validate(category) for category in db.scalars(select(Category).where(Category.is_active.is_(True)).order_by(Category.sort_order, Category.name)).all()]


@router.get("/sellers", response_model=list[SellerResponse])
def sellers(db: Session = Depends(get_db)) -> list[SellerResponse]:
    return [SellerResponse.model_validate(seller) for seller in db.scalars(select(Seller).where(Seller.status == SellerStatus.ACTIVE).order_by(Seller.name)).all()]


@router.get("/products/{product_id}/reviews", response_model=list[ReviewResponse])
def reviews(product_id: UUID, db: Session = Depends(get_db)) -> list[ReviewResponse]:
    records = db.scalars(select(Review).where(Review.product_id == product_id, Review.is_published.is_(True)).order_by(Review.created_at.desc())).all()
    return [ReviewResponse(id=review.id, rating=review.rating, title=review.title, body=review.body, is_verified_purchase=review.is_verified_purchase, created_at=review.created_at, author_name=review.user.full_name) for review in records]
