from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    AIConversation,
    AIMessage,
    AIRecommendation,
    Cart,
    CartItem,
    Category,
    MessageRole,
    MissionMode,
    MissionStatus,
    Order,
    OrderItem,
    Payment,
    PaymentMethod,
    Product,
    ProductStatus,
    RecommendationFeedback,
    Review,
    Seller,
    SellerStatus,
    ShoppingMission,
    TransactionStatus,
    TransactionType,
    User,
    Wallet,
    WalletTransaction,
)


def test_commerce_and_ai_relationships(db_session):
    user = User(email="member@example.com", full_name="Jeffrey Tan")
    seller = Seller(name="Astra", slug="astra", status=SellerStatus.ACTIVE, owner=user)
    category = Category(name="Audio", slug="audio")
    product = Product(
        seller=seller,
        category=category,
        sku="ASTRA-ORBIT-001",
        slug="orbit-pro-headset",
        name="Orbit Pro Headset",
        brand="Astra",
        description="Adaptive noise control headset.",
        price=Decimal("420.00"),
        status=ProductStatus.ACTIVE,
        inventory_quantity=20,
        specs=[{"label": "Battery", "value": "42h"}],
    )
    cart = Cart(user=user)
    cart.items.append(CartItem(product=product, quantity=2, unit_price=product.price))
    order = Order(
        user=user,
        cart=cart,
        order_number="SHP-100001",
        subtotal=Decimal("840.00"),
        tax_amount=Decimal("50.40"),
        handling_amount=Decimal("24.00"),
        discount_amount=Decimal("0.00"),
        total_amount=Decimal("914.40"),
        shipping_address_snapshot={"city": "Kuala Lumpur", "country_code": "MY"},
    )
    order_item = OrderItem(
        order=order,
        product=product,
        seller=seller,
        sku=product.sku,
        product_name=product.name,
        quantity=2,
        unit_price=product.price,
        line_total=Decimal("840.00"),
    )
    review = Review(user=user, product=product, order_item=order_item, rating=5, is_verified_purchase=True)
    payment = Payment(order=order, method=PaymentMethod.CARD, amount=order.total_amount)

    mission = ShoppingMission(
        user=user,
        mode=MissionMode.SHOP_OBJECT,
        status=MissionStatus.COMPLETED,
        prompt="Find headphones like this one",
        analysis={"style": "over-ear"},
    )
    recommendation = AIRecommendation(
        mission=mission,
        product=product,
        rank=1,
        score=Decimal("0.9500"),
        rationale="Strong feature and style match.",
        feedback=RecommendationFeedback.ADDED_TO_CART,
    )
    conversation = AIConversation(user=user, mission=mission, model="gemini-2.5-flash-lite")
    conversation.messages.append(AIMessage(role=MessageRole.USER, content="Find headphones"))
    conversation.messages.append(AIMessage(role=MessageRole.ASSISTANT, content="Try Orbit Pro"))

    wallet = Wallet(user=user, balance=Decimal("420.00"), is_verified=True)
    transaction = WalletTransaction(
        wallet=wallet,
        reference="SP-100001",
        type=TransactionType.TOP_UP,
        status=TransactionStatus.COMPLETED,
        amount=Decimal("420.00"),
    )

    db_session.add_all([payment, recommendation, review, transaction])
    db_session.commit()

    assert user.carts[0].items[0].product is product
    assert order.items[0].seller is seller
    assert product.reviews[0].is_verified_purchase is True
    assert mission.recommendations[0].product is product
    assert [message.role for message in conversation.messages] == [MessageRole.USER, MessageRole.ASSISTANT]
    assert user.wallet.transactions[0].reference == "SP-100001"


def test_review_rating_constraint(db_session):
    user = User(email="reviewer@example.com", full_name="Reviewer")
    seller = Seller(name="Pulse", slug="pulse", status=SellerStatus.ACTIVE)
    category = Category(name="Imaging", slug="imaging")
    product = Product(
        seller=seller,
        category=category,
        sku="PULSE-001",
        slug="vector-drone",
        name="Vector Drone",
        brand="Pulse",
        description="A compact drone.",
        price=Decimal("680.00"),
        status=ProductStatus.ACTIVE,
        inventory_quantity=5,
    )
    db_session.add(Review(user=user, product=product, rating=6))

    with pytest.raises(IntegrityError):
        db_session.commit()
