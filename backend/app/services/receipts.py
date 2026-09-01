"""Paid-order receipt generation and delivery.

Receipt delivery intentionally happens after the order transaction commits: a
mail-provider outage must never charge a customer twice or roll back a payment.
"""
from __future__ import annotations

import logging
import smtplib
from datetime import timezone
from email.message import EmailMessage
from io import BytesIO

from app.config import settings
from app.models import Order


logger = logging.getLogger(__name__)


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_paid_receipt_pdf(order: Order, *, customer_name: str) -> bytes:
    """Create a compact, dependency-free PDF receipt from immutable order data."""
    issued_at = (order.placed_at or order.created_at).astimezone(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    lines = [
        "SHOPY — PAID RECEIPT",
        f"Order: {order.order_number}",
        f"Paid on: {issued_at}",
        f"Customer: {customer_name}",
        "",
        "ITEMS",
    ]
    for item in order.items:
        lines.append(f"{item.product_name} × {item.quantity}    {order.currency} {item.line_total:.2f}")
    lines.extend([
        "",
        f"Merchandise subtotal: {order.currency} {order.subtotal:.2f}",
        f"Shipping: {order.currency} {order.handling_amount:.2f}",
        f"Tax: {order.currency} {order.tax_amount:.2f}",
        f"TOTAL PAID: {order.currency} {order.total_amount:.2f}",
        "",
        "Thank you for shopping with Shopy.",
    ])
    content_lines = ["BT", "/F1 11 Tf", "50 790 Td", "14 TL"]
    for index, line in enumerate(lines):
        if index:
            content_lines.append("T*")
        content_lines.append(f"({_pdf_escape(line)}) Tj")
    content_lines.append("ET")
    content = "\n".join(content_lines).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = [0]
    for number, value in enumerate(objects, start=1):
        offsets.append(output.tell())
        output.write(f"{number} 0 obj\n".encode())
        output.write(value)
        output.write(b"\nendobj\n")
    xref = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode())
    output.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return output.getvalue()


def send_paid_receipt_email(*, recipient_email: str, recipient_name: str, order_number: str, receipt_pdf: bytes) -> None:
    if not settings.receipt_email_enabled:
        logger.info("Receipt email skipped for %s because SMTP is not configured.", order_number)
        return
    message = EmailMessage()
    message["Subject"] = f"Your Shopy paid receipt — {order_number}"
    message["From"] = settings.smtp_from_email
    message["To"] = recipient_email
    message.set_content(
        f"Hi {recipient_name},\n\nYour payment for order {order_number} was successful. "
        "Your PDF receipt is attached.\n\nThank you for shopping with Shopy."
    )
    message.add_attachment(receipt_pdf, maintype="application", subtype="pdf", filename=f"shopy-receipt-{order_number}.pdf")
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        logger.exception("Unable to send paid receipt for %s", order_number)
