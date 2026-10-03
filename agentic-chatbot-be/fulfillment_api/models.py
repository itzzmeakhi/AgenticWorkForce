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