from datetime import date, timedelta
from typing import Dict

from fulfillment_api.models import (
    Claim, ClaimStatus, Order, OrderItem, OrderStatus, Policy, PolicyStatus, Product, ShippingAddress,
)

TODAY = date(2026, 9, 13)


def initialize_mock_data():
    products: Dict[str, Product] = {
        p.sku: p for p in [
            Product(sku="SKU-PH-101", name="iPhone 15", category="Mobile Phones", price=42999, stock=18, rating=4.4, description="6.5in OLED, 128GB, 5G"),
            Product(sku="SKU-LT-201", name="AeroBook 14 Slim", category="Laptops", price=74999, stock=12, rating=4.3, description="14in, 16GB RAM, 512GB SSD"),
            Product(sku="SKU-SW-301", name="PulseFit Watch 3", category="Smartwatches", price=8999, stock=40, rating=4.1, description="Heart-rate + SpO2 tracking"),
            Product(sku="SKU-AU-601", name="EchoBeat ANC Headphones", category="Audio Equipment", price=11999, stock=25, rating=4.5, description="Active noise cancellation"),
            Product(sku="SKU-AC-801", name="SwiftCharge 65W GaN", category="Accessories", price=2499, stock=60, rating=4.0, description="Compact fast charger"),
        ]
    }

    orders: Dict[str, Order] = {
        o.order_id: o for o in [
            Order(order_id="ORD1001", customer_email="abc@gmail.com", status=OrderStatus.SHIPPED,
                  items=[OrderItem(name="Nova X12 Smartphone", sku="SKU-PH-101", quantity=1, price=42999)],
                  total=42999, order_date=TODAY - timedelta(days=6), expected_delivery=TODAY + timedelta(days=1),
                  tracking_number="TRK7841002233", carrier="BlueDart Express", current_location="Hyderabad Hub",
                  shipping_address=ShippingAddress(address="12 MG Road", city="Hyderabad", state="TG", postal_code="500081", phone="+91-9876500011")),
            Order(order_id="ORD1002", customer_email="rahul@gmail.com", status=OrderStatus.SHIPPED,
                  items=[OrderItem(name="EchoBeat ANC Headphones", sku="SKU-AU-601", quantity=1, price=11999)],
                  total=11999, order_date=TODAY - timedelta(days=4), expected_delivery=TODAY + timedelta(days=2),
                  tracking_number="TRK7841002298", carrier="Delhivery", current_location="Pune Sorting Facility",
                  shipping_address=ShippingAddress(address="45 FC Road", city="Pune", state="MH", postal_code="411005", phone="+91-9876500022")),
            Order(order_id="ORD1003", customer_email="akhil@gmail.com", status=OrderStatus.PROCESSING,
                  items=[OrderItem(name="AeroBook 14 Slim", sku="SKU-LT-201", quantity=1, price=74999)],
                  total=74999, order_date=TODAY - timedelta(days=1),
                  shipping_address=ShippingAddress(address="88 Residency Rd", city="Bengaluru", state="KA", postal_code="560025", phone="+91-9876500033")),
            Order(order_id="ORD1004", customer_email="akhil@gmail.com", status=OrderStatus.PROCESSING,
                  items=[OrderItem(name="PulseFit Watch 3", sku="SKU-SW-301", quantity=1, price=8999)],
                  total=8999, order_date=TODAY - timedelta(days=2),
                  shipping_address=ShippingAddress(address="88 Residency Rd", city="Bengaluru", state="KA", postal_code="560025", phone="+91-9876500033")),
            Order(order_id="ORD1005", customer_email="abc@gmail.com", status=OrderStatus.DELIVERED,
                  items=[OrderItem(name="SwiftCharge 65W GaN", sku="SKU-AC-801", quantity=2, price=2499)],
                  total=4998, order_date=TODAY - timedelta(days=15), expected_delivery=TODAY - timedelta(days=9),
                  tracking_number="TRK7841001777", carrier="BlueDart Express", current_location="Delivered",
                  shipping_address=ShippingAddress(address="12 MG Road", city="Hyderabad", state="TG", postal_code="500081", phone="+91-9876500011")),
            Order(order_id="ORD1006", customer_email="rahul@gmail.com", status=OrderStatus.PROCESSING,
                  items=[OrderItem(name="PulseFit Watch 3", sku="SKU-SW-301", quantity=1, price=8999)],
                  total=8999, order_date=TODAY - timedelta(days=1),
                  shipping_address=ShippingAddress(address="45 FC Road", city="Pune", state="MH", postal_code="411005", phone="+91-9876500022")),
        ]
    }

    return products, orders


def initialize_insurance_data():
    """Insurance dummy data -- a separate dataset from the e-commerce one."""
    policies: Dict[str, Policy] = {
        p.policy_id: p for p in [
            Policy(policy_id="POL2001", customer_email="neha@gmail.com", policy_type="Health", plan_name="Family Floater Health Plan",
                   status=PolicyStatus.ACTIVE, sum_insured=500000, annual_premium=18500, next_premium_due=date(2026, 10, 20),
                   start_date=date(2025, 11, 1), end_date=date(2026, 10, 31), insured_item="Neha Kapoor + 2 family members"),
            Policy(policy_id="POL2005", customer_email="neha@gmail.com", policy_type="Home", plan_name="Home Protect Plus",
                   status=PolicyStatus.ACTIVE, sum_insured=2500000, annual_premium=7200, next_premium_due=date(2027, 2, 1),
                   start_date=date(2026, 2, 1), end_date=date(2027, 1, 31), insured_item="2BHK apartment, Koramangala, Bengaluru"),
            Policy(policy_id="POL2002", customer_email="vikram@gmail.com", policy_type="Motor", plan_name="Comprehensive Car Cover",
                   status=PolicyStatus.ACTIVE, sum_insured=450000, annual_premium=12400, next_premium_due=date(2027, 3, 1),
                   start_date=date(2026, 3, 1), end_date=date(2027, 2, 28), insured_item="Maruti Swift (KA01AB1234)"),
            Policy(policy_id="POL2003", customer_email="akhil@gmail.com", policy_type="Health", plan_name="Individual Health Shield",
                   status=PolicyStatus.ACTIVE, sum_insured=300000, annual_premium=9800, next_premium_due=date(2026, 12, 15),
                   start_date=date(2025, 12, 15), end_date=date(2026, 12, 14), insured_item="Akhil Reddy"),
            Policy(policy_id="POL2004", customer_email="akhil@gmail.com", policy_type="Motor", plan_name="Two-Wheeler Third Party",
                   status=PolicyStatus.LAPSED, sum_insured=60000, annual_premium=2100, next_premium_due=date(2026, 8, 30),
                   start_date=date(2025, 8, 31), end_date=date(2026, 8, 30), insured_item="Honda Activa (KA05XY9876)"),
        ]
    }
    claims: Dict[str, Claim] = {
        c.claim_id: c for c in [
            Claim(claim_id="CLM3001", policy_id="POL2001", customer_email="neha@gmail.com", claim_type="Hospitalisation",
                  description="Planned knee surgery, 3-day stay", amount_claimed=42000, status=ClaimStatus.UNDER_REVIEW,
                  filed_date=TODAY - timedelta(days=8), decision_note="Documents received; awaiting hospital bill verification."),
            Claim(claim_id="CLM3002", policy_id="POL2002", customer_email="vikram@gmail.com", claim_type="Accident damage",
                  description="Rear bumper and tail-light damage", amount_claimed=15500, status=ClaimStatus.APPROVED,
                  filed_date=TODAY - timedelta(days=20), approved_amount=14000, decision_note="Approved after surveyor report; INR 1,500 deductible applied."),
            Claim(claim_id="CLM3003", policy_id="POL2003", customer_email="akhil@gmail.com", claim_type="Outpatient",
                  description="Dental treatment", amount_claimed=3200, status=ClaimStatus.REJECTED,
                  filed_date=TODAY - timedelta(days=30), decision_note="Dental treatment is not covered under this plan."),
        ]
    }
    return policies, claims


PRODUCTS, ORDERS = initialize_mock_data()
POLICIES, CLAIMS = initialize_insurance_data()


def find_orders_by_email(email: str):
    return [o for o in ORDERS.values() if o.customer_email.lower() == email.lower()]
