from decimal import Decimal

import pytest

from app.agentic.tools import CommerceToolRegistry
from app.models import Category, Product, ProductStatus, Seller, SellerStatus
from app.services.catalog import list_products


def _product(db_session, *, sku: str, name: str, category_name: str, description: str) -> Product:
    seller = Seller(name=f"Seller {sku}", slug=f"seller-{sku.lower()}", status=SellerStatus.ACTIVE)
    category = Category(name=category_name, slug=category_name.lower().replace(" ", "-"))
    product = Product(
        seller=seller,
        category=category,
        sku=sku,
        slug=sku.lower(),
        name=name,
        brand="Test Brand",
        description=description,
        price=Decimal("20.00"),
        status=ProductStatus.ACTIVE,
        inventory_quantity=10,
    )
    db_session.add(product)
    return product


def test_multi_word_search_requires_all_meaningful_terms_without_hardcoded_aliases(db_session):
    shampoo = _product(
        db_session,
        sku="CAR-SHAMPOO",
        name="Gold Class Car Wash Shampoo",
        category_name="Car Shampoo",
        description="pH-balanced wash concentrate.",
    )
    _product(
        db_session,
        sku="UNRELATED",
        name="Car Interior Cleaner",
        category_name="Interior Cleaner",
        description="A wash-safe cleaner for dashboard surfaces.",
    )
    db_session.commit()

    results = list_products(db_session, query="car wash shampoo", limit=8)

    assert [product.id for product in results] == [shampoo.id]


def test_catalog_listing_returns_all_active_products_without_a_query(db_session):
    shampoo = _product(db_session, sku="SOAP", name="Car Wash Shampoo", category_name="Car Shampoo", description="Wash soap.")
    mitt = _product(db_session, sku="MITT", name="Car Wash Mitt", category_name="Wash Mitt", description="Microfibre wash mitt.")
    towels = _product(db_session, sku="TOWELS", name="Microfibre Drying Towel Set", category_name="Drying Towels", description="Drying towels.")
    wheel_cleaner = _product(db_session, sku="WHEEL", name="Wheel Cleaner Plus", category_name="Wheel Cleaner", description="Wheel cleaner.")
    db_session.commit()

    assert {product.id for product in list_products(db_session)} == {shampoo.id, mitt.id, towels.id, wheel_cleaner.id}


@pytest.mark.anyio
async def test_catalog_tool_returns_full_verified_snapshot_without_query_terms(db_session):
    skincare = _product(db_session, sku="SKIN", name="Gentle Cleanser", category_name="Skincare", description="Daily cleanser.")
    makeup = _product(db_session, sku="MAKEUP", name="Cream Blush", category_name="Makeup", description="Blendable cheek colour.")
    db_session.commit()

    result = await CommerceToolRegistry(db_session, "catalog-snapshot").execute("search_products", {"limit": 500})

    products = {item["id"]: item for item in result["products"]}
    assert set(products) == {str(skincare.id), str(makeup.id)}
    assert products[str(skincare.id)]["specs"] == []
    assert products[str(makeup.id)]["attributes"] == {}
