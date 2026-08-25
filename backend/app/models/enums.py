import enum


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class AddressKind(str, enum.Enum):
    SHIPPING = "shipping"
    BILLING = "billing"
    BOTH = "both"


class SellerStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class ProductStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ProductBadge(str, enum.Enum):
    NEW = "new"
    HOT = "hot"
    SALE = "sale"


class CartStatus(str, enum.Enum):
    ACTIVE = "active"
    CONVERTED = "converted"
    ABANDONED = "abandoned"
    EXPIRED = "expired"


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentMethod(str, enum.Enum):
    CARD = "card"
    SHOPY_PAY = "shopy_pay"
    FPX = "fpx"
    DUITNOW = "duitnow"


class MissionMode(str, enum.Enum):
    TEXT = "text"
    SHOP_ROOM = "shop_room"
    COMPLETE_LOOK = "complete_look"
    SHOP_OBJECT = "shop_object"


class MissionStatus(str, enum.Enum):
    DRAFT = "draft"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class RecommendationFeedback(str, enum.Enum):
    NONE = "none"
    LIKED = "liked"
    DISLIKED = "disliked"
    ADDED_TO_CART = "added_to_cart"
    PURCHASED = "purchased"


class TransactionType(str, enum.Enum):
    TOP_UP = "top_up"
    PURCHASE = "purchase"
    REFUND = "refund"
    CASHBACK = "cashback"
    ADJUSTMENT = "adjustment"


class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"
