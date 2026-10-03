from datetime import date, timedelta
from typing import Dict

from fulfillment_api.models import (
    Order, OrderItem, OrderStatus, Product, ShippingAddress,
)

TODAY = date(2026, 9, 13)


def initialize_mock_data():
    products: Dict[str, Product] = {
        p.sku: p for p in [
            Product(sku="SKU-PH-101", name="Nova X12 Smartphone", category="Mobile Phones", price=42999, stock=18, rating=4.4, description="6.5in AMOLED, 128GB, 5G"),
            Product(sku="SKU-LT-201", name="AeroBook 14 Slim", category="Laptops", price=74999, stock=12, rating=4.3, description="14in, 16GB RAM, 512GB SSD"),
            Product(sku="SKU-SW-301", name="PulseFit Watch 3", category="Smartwatches", price=8999, stock=40, rating=4.1, description="Heart-rate + SpO2 tracking"),
            Product(sku="SKU-AU-601", name="EchoBeat ANC Headphones", category="Audio Equipment", price=11999, stock=25, rating=4.5, description="Active noise cancellation"),
            Product(sku="SKU-AC-801", name="SwiftCharge 65W GaN", category="Accessories", price=2499, stock=60, rating=4.0, description="Compact fast charger"),
        ]
    }

    orders: Dict[str, Order] = {
        o.order_id: o for o in [
            Order(order_id="ORD1001", customer_email="priya.nair@example.com", status=OrderStatus.SHIPPED,
                  items=[OrderItem(name="Nova X12 Smartphone", sku="SKU-PH-101", quantity=1, price=42999)],
                  total=42999, order_date=TODAY - timedelta(days=6), expected_delivery=TODAY + timedelta(days=1),
                  tracking_number="TRK7841002233", carrier="BlueDart Express", current_location="Hyderabad Hub",
                  shipping_address=ShippingAddress(address="12 MG Road", city="Hyderabad", state="TG", postal_code="500081", phone="+91-9876500011")),
            Order(order_id="ORD1002", customer_email="rahul.verma@example.com", status=OrderStatus.SHIPPED,
                  items=[OrderItem(name="EchoBeat ANC Headphones", sku="SKU-AU-601", quantity=1, price=11999)],
                  total=11999, order_date=TODAY - timedelta(days=4), expected_delivery=TODAY + timedelta(days=2),
                  tracking_number="TRK7841002298", carrier="Delhivery", current_location="Pune Sorting Facility",
                  shipping_address=ShippingAddress(address="45 FC Road", city="Pune", state="MH", postal_code="411005", phone="+91-9876500022")),
            Order(order_id="ORD1003", customer_email="arjun.mehta@example.com", status=OrderStatus.PROCESSING,
                  items=[OrderItem(name="AeroBook 14 Slim", sku="SKU-LT-201", quantity=1, price=74999)],
                  total=74999, order_date=TODAY - timedelta(days=1),
                  shipping_address=ShippingAddress(address="88 Residency Rd", city="Bengaluru", state="KA", postal_code="560025", phone="+91-9876500033")),
        ]
    }

    return products, orders


PRODUCTS, ORDERS = initialize_mock_data()


def find_orders_by_email(email: str):
    return [o for o in ORDERS.values() if o.customer_email.lower() == email.lower()]
