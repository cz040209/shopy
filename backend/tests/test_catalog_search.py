from decimal import Decimal

import pytest

from app.agentic.tools import CommerceToolRegistry
from app.models import Category, Product, ProductStatus, Seller, SellerStatus
from app.services.catalog import list_products


def _product(
    db_session, *, sku: str, name: str, category_name: str, description: str,
    specs: list[dict] | None = None, attributes: dict | None = None,
) -> Product:
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
        specs=specs or [],
        attributes=attributes or {},
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


def test_expanded_search_inspects_specs_attributes_and_treats_queries_as_alternatives(db_session):
    rgb_bar = _product(
        db_session, sku="LIGHT", name="Aura Bar", category_name="Home Accessories",
        description="A slim accent fixture.",
        specs=[{"label": "Output", "value": "dimmable LED"}],
        attributes={"product_role": "lighting", "modes": ["RGB", "ambient"]},
    )
    unrelated = _product(
        db_session, sku="CABLE", name="RGB Extension Cable", category_name="Cables",
        description="Replacement cable.",
    )
    db_session.commit()

    results = list_products(
        db_session,
        queries=["lighting", "ambient lighting", "RGB light", "LED light"],
        limit=8,
    )

    assert results[0].id == rgb_bar.id
    assert unrelated.id not in {product.id for product in results}


@pytest.mark.anyio
async def test_catalog_tool_returns_full_verified_snapshot_without_query_terms(db_session):
    skincare = _product(db_session, sku="SKIN", name="Gentle Cleanser", category_name="Skincare", description="Daily cleanser.")
    makeup = _product(db_session, sku="MAKEUP", name="Cream Blush", category_name="Makeup", description="Blendable cheek colour.")
    db_session.commit()

    result = await CommerceToolRegistry(db_session, "catalog-snapshot").execute("search_products", {"limit": 500})

    products = {item["id"]: item for item in result["products"]}
    assert set(products) == {str(skincare.id), str(makeup.id)}
    assert products[str(skincare.id)]["search_terms"] == ["daily", "cleanser"]
    assert products[str(makeup.id)]["search_terms"] == ["blendable", "cheek", "colour"]
    assert products[str(skincare.id)]["specs"] == []
    assert products[str(makeup.id)]["attributes"] == {}


@pytest.mark.anyio
async def test_grouped_search_broadens_an_over_specific_role_without_global_catalog_search(db_session):
    chair = _product(
        db_session, sku="CHAIR", name="Posture Pro Ergonomic Chair",
        category_name="Office Furniture", description="Supportive chair for long sessions.",
    )
    desk = _product(
        db_session, sku="DESK", name="Utility Gaming Desk",
        category_name="Gaming", description="Stable desk with cable management.",
    )
    db_session.commit()
    registry = CommerceToolRegistry(db_session, "role-broadening")

    result = await registry.execute("search_products", {
        "query_groups": [{
            "role": "gaming chair",
            "queries": ["gaming chair", "ergonomic gaming chair", "comfortable gaming chair"],
        }],
        "limit": 6,
    })

    matched_ids = result["query_matches"]["gaming chair"]
    assert str(chair.id) in matched_ids
    assert str(desk.id) in matched_ids
    assert registry.remaining_calls == registry.max_calls - 1
