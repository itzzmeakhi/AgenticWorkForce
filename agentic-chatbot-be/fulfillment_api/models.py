from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

class OrderStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class OrderItem(BaseModel):
    name: str
    sku: str
    quantity: int
    price: float

class ShippingAddress(BaseModel):
    address: str
    city: str
    state: str
    postal_code: str
    phone: str

class Order(BaseModel):
    order_id: str
    customer_email: str
    status: OrderStatus
    items: List[OrderItem]
    total: float
    order_date: date
    expected_delivery: Optional[date] = None
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None
    current_location: Optional[str] = None
    shipping_address: ShippingAddress
    cancellation_reason: Optional[str] = None

class Product(BaseModel):
    sku: str
    name: str
    category: str
    price: float
    stock: int
    rating: float
    description: str = ""

class CancelOrderRequest(BaseModel):
    order_id: str
    reason: str = Field(default="customer requested")


# ------------------------------------------------------------------ insurance
class PolicyStatus(str, Enum):
    ACTIVE = "active"
    LAPSED = "lapsed"
    EXPIRED = "expired"


class ClaimStatus(str, Enum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class Policy(BaseModel):
    policy_id: str
    customer_email: str
    policy_type: str          # Health | Motor | Home
    plan_name: str
    status: PolicyStatus
    sum_insured: float
    annual_premium: float
    next_premium_due: Optional[date] = None
    start_date: date
    end_date: date
    insured_item: str = ""    # person / vehicle / property covered


class Claim(BaseModel):
    claim_id: str
    policy_id: str
    customer_email: str
    claim_type: str
    description: str
    amount_claimed: float
    status: ClaimStatus
    filed_date: date
    approved_amount: Optional[float] = None
    decision_note: Optional[str] = None
