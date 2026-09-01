import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import OrderStatus, PaymentMethod, PaymentStatus, ProductBadge, UserStatus


VisionMode = Literal["shop_room", "complete_look", "shop_object"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)
    input_type: Literal["text", "voice"] = "text"
    input_payload: dict[str, Any] = Field(default_factory=dict)


class ChatProductAttachment(BaseModel):
    product_id: UUID
    product_slug: str | None = None
    name: str = Field(min_length=1, max_length=220)
    price: Decimal
    currency: str = Field(min_length=3, max_length=3)
    image_url: str = Field(min_length=1, max_length=2048)
    image_alt_text: str | None = Field(default=None, max_length=255)
    brand: str | None = Field(default=None, max_length=220)
    category: str | None = Field(default=None, max_length=220)


class ChatResponse(BaseModel):
    reply: str
    conversation_id: UUID
    attachments: list[ChatProductAttachment] = Field(default_factory=list)
    mission: dict[str, Any] = Field(default_factory=dict)
    workspace: dict[str, Any] = Field(default_factory=dict)


class VisionResponse(BaseModel):
    mode: VisionMode
    analysis: str
    attachments: list[ChatProductAttachment] = Field(default_factory=list)
    vision_context: dict[str, Any] = Field(default_factory=dict)


class TranscriptionResponse(BaseModel):
    transcript: str
    language: str | None = None
    duration_seconds: float | None = None


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("full_name")
    @classmethod
    def clean_full_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("Full name must contain at least 2 characters.")
        return cleaned

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
            raise ValueError("Enter a valid email address.")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise ValueError("Password must contain at least one letter and one number.")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    phone: str | None
    avatar_url: str | None
    status: UserStatus
    created_at: datetime


class ProfileUpdateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=32)

    @field_validator("full_name")
    @classmethod
    def clean_full_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("Full name must contain at least 2 characters.")
        return cleaned

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, value: str | None) -> str | None:
        cleaned = value.strip() if value else None
        if cleaned and len(cleaned) < 5:
            raise ValueError("Enter a valid phone number.")
        return cleaned


class AuthResponse(BaseModel):
    user: UserResponse


class MessageResponse(BaseModel):
    message: str


class ProductImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    url: str
    alt_text: str | None


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    slug: str
    description: str | None


class SellerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    slug: str
    description: str | None
    rating_average: Decimal


class ProductResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    brand: str
    description: str
    price: Decimal
    compare_at_price: Decimal | None
    currency: str
    badge: ProductBadge | None
    emoji: str | None
    specs: list[dict[str, Any]]
    attributes: dict[str, Any]
    rating_average: Decimal
    review_count: int
    inventory_quantity: int
    category: CategoryResponse
    seller: SellerResponse
    images: list[ProductImageResponse]


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    page: int
    page_size: int


class CartItemResponse(BaseModel):
    id: UUID
    product: ProductResponse
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class CartResponse(BaseModel):
    id: UUID
    currency: str
    items: list[CartItemResponse]
    subtotal: Decimal


class AddCartItemRequest(BaseModel):
    product_id: UUID
    quantity: int = Field(default=1, ge=1, le=99)


class UpdateCartItemRequest(BaseModel):
    quantity: int = Field(ge=1, le=99)


class ShippingAddressInput(BaseModel):
    recipient_name: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=5, max_length=32)
    line1: str = Field(min_length=3, max_length=255)
    line2: str | None = Field(default=None, max_length=255)
    city: str = Field(min_length=2, max_length=120)
    state: str = Field(min_length=2, max_length=120)
    postal_code: str = Field(min_length=3, max_length=24)
    country_code: str = Field(default="MY", min_length=2, max_length=2)


class CheckoutRequest(BaseModel):
    shipping_address: ShippingAddressInput
    payment_method: PaymentMethod = PaymentMethod.CARD
    shipping_fee: Decimal = Field(default=Decimal("24.00"), ge=Decimal("3.00"), le=Decimal("30.00"))
    notes: str | None = Field(default=None, max_length=1000)


class OrderItemResponse(BaseModel):
    id: UUID
    product_id: UUID | None
    sku: str
    product_name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    product_snapshot: dict[str, Any]


class OrderResponse(BaseModel):
    id: UUID
    order_number: str
    status: OrderStatus
    payment_status: PaymentStatus
    currency: str
    subtotal: Decimal
    tax_amount: Decimal
    handling_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    shipping_address_snapshot: dict[str, Any]
    placed_at: datetime | None
    created_at: datetime
    items: list[OrderItemResponse]
    receipt_email_queued: bool = False


class WalletTransactionResponse(BaseModel):
    id: UUID
    reference: str
    type: str
    status: str
    amount: Decimal
    currency: str
    description: str | None
    created_at: datetime


class WalletResponse(BaseModel):
    id: UUID
    currency: str
    balance: Decimal
    daily_limit: Decimal
    monthly_limit: Decimal
    is_verified: bool
    transactions: list[WalletTransactionResponse]


class WalletTopUpRequest(BaseModel):
    amount: Decimal = Field(gt=Decimal("0"), max_digits=12, decimal_places=2)
    payment_source: str = Field(min_length=2, max_length=80)


class ReviewRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    title: str | None = Field(default=None, max_length=180)
    body: str | None = Field(default=None, max_length=5000)


class ReviewResponse(BaseModel):
    id: UUID
    rating: int
    title: str | None
    body: str | None
    is_verified_purchase: bool
    created_at: datetime
    author_name: str


class AgentRunRequest(BaseModel):
    user_request: str = Field(min_length=1, max_length=4000)


class OrchestrationEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sequence: int
    event_type: str
    node_name: str | None
    tool_name: str | None
    status: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    error_message: str | None
    created_at: datetime
    duration_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None


class OrchestrationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_id: str
    status: str
    user_request: str
    final_response: str | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
    input_tokens: int
    output_tokens: int
    total_tokens: int
    events: list[OrchestrationEventResponse] = Field(default_factory=list)
