from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import get_db
from app.main import app
from app.models import Category, Product, ProductImage, ProductStatus, Seller, SellerStatus


def test_catalog_cart_and_checkout_lifecycle(db_session):
    seller = Seller(name="Astra", slug="astra", status=SellerStatus.ACTIVE)
    category = Category(name="Audio", slug="audio")
    product = Product(
        seller=seller, category=category, sku="ASTRA-ORBIT-001", slug="orbit-pro-headset",
        name="Orbit Pro Headset", brand="Astra", description="Focused audio.",
        price=Decimal("420.00"), status=ProductStatus.ACTIVE, inventory_quantity=8,
    )
    product.images.append(ProductImage(url="https://example.test/headset.jpg", alt_text="Headset", sort_order=0))
    db_session.add(product)
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        listed = client.get("/api/v1/products?q=orbit")
        assert listed.status_code == 200
        product_id = listed.json()["items"][0]["id"]
        assert product_id == str(product.id)

        category_match = client.get("/api/v1/products?q=audio product")
        assert category_match.status_code == 200
        assert category_match.json()["items"][0]["id"] == str(product.id)

        registered = client.post("/api/v1/auth/register", json={"full_name": "Jeffrey Tan", "email": "commerce@example.com", "password": "Orbit2026!"})
        assert registered.status_code == 201
        added = client.post("/api/v1/cart/items", json={"product_id": product_id, "quantity": 2})
        assert added.status_code == 201
        assert added.json()["subtotal"] == "840.00"

        checkout = client.post("/api/v1/orders/checkout", json={
            "shipping_address": {"recipient_name": "Jeffrey Tan", "phone": "+60123456789", "line1": "KLCC", "city": "Kuala Lumpur", "state": "Kuala Lumpur", "postal_code": "50088", "country_code": "MY"},
            "payment_method": "card",
        })
        assert checkout.status_code == 201
        assert checkout.json()["total_amount"] == "865.45"
        history = client.get("/api/v1/orders")
        assert history.status_code == 200
        assert history.json()[0]["order_number"] == checkout.json()["order_number"]
        assert client.get("/api/v1/cart").json()["items"] == []
        assert db_session.scalar(select(Product).where(Product.id == product.id)).inventory_quantity == 6

        top_up = client.post("/api/v1/wallet/top-ups", json={"amount": "1000.00", "payment_source": "FPX Online Banking"})
        assert top_up.status_code == 201
        assert top_up.json()["balance"] == "1000.00"
        assert top_up.json()["transactions"][0]["type"] == "top_up"

        added_again = client.post("/api/v1/cart/items", json={"product_id": product_id, "quantity": 1})
        assert added_again.status_code == 201
        wallet_checkout = client.post("/api/v1/orders/checkout", json={
            "shipping_address": {"recipient_name": "Jeffrey Tan", "phone": "+60123456789", "line1": "KLCC", "city": "Kuala Lumpur", "state": "Kuala Lumpur", "postal_code": "50088", "country_code": "MY"},
            "payment_method": "shopy_pay",
            "shipping_fee": "3.00",
        })
        assert wallet_checkout.status_code == 201
        assert wallet_checkout.json()["payment_status"] == "paid"
        assert wallet_checkout.json()["total_amount"] == "423.20"
        wallet = client.get("/api/v1/wallet")
        assert wallet.status_code == 200
        assert wallet.json()["balance"] == "576.80"
        assert {item["type"] for item in wallet.json()["transactions"][:2]} == {"purchase", "top_up"}
    finally:
        app.dependency_overrides.clear()
