from datetime import datetime, timezone
from decimal import Decimal

from app.models import Order, OrderItem, PaymentStatus
from app.services.receipts import build_paid_receipt_pdf


def test_paid_receipt_pdf_contains_order_details():
    order = Order(
        order_number="SHP-20260901-RECEIPT",
        currency="MYR",
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("0.30"),
        handling_amount=Decimal("5.00"),
        discount_amount=Decimal("0"),
        total_amount=Decimal("105.30"),
        payment_status=PaymentStatus.PAID,
        placed_at=datetime.now(timezone.utc),
        shipping_address_snapshot={},
        items=[OrderItem(sku="SKU-1", product_name="Travel Kit", quantity=1, unit_price=Decimal("100.00"), line_total=Decimal("100.00"), product_snapshot={})],
    )

    receipt = build_paid_receipt_pdf(order, customer_name="Jeffrey Tan")

    assert receipt.startswith(b"%PDF-1.4")
    assert b"SHP-20260901-RECEIPT" in receipt
    assert b"Travel Kit" in receipt
