"""Business operations behind the Fulfillment API.

Every customer-data operation takes the signed-in customer's email
(`owner_email`, taken from the verified token by the server -- never from the
request) and only ever sees that customer's records. A record that exists but
belongs to someone else gets the same "not found" answer as one that does not
exist, so IDs cannot be probed.
"""
from typing import Optional

from fulfillment_api.mock_data import (
    CLAIMS, ORDERS, POLICIES, PRODUCTS, TODAY, find_orders_by_email,
)
from fulfillment_api.models import Claim, ClaimStatus, Order, OrderStatus, Policy, PolicyStatus

CANCELLABLE_STATUSES = {OrderStatus.PENDING, OrderStatus.PROCESSING, OrderStatus.CONFIRMED}


def _own_order(order_id: str, owner_email: str) -> Optional[Order]:
    order = ORDERS.get((order_id or "").upper())
    if order is None or order.customer_email.lower() != (owner_email or "").lower():
        return None
    return order


def _own_policy(policy_id: str, owner_email: str) -> Optional[Policy]:
    policy = POLICIES.get((policy_id or "").upper())
    if policy is None or policy.customer_email.lower() != (owner_email or "").lower():
        return None
    return policy


def _own_claim(claim_id: str, owner_email: str) -> Optional[Claim]:
    claim = CLAIMS.get((claim_id or "").upper())
    if claim is None or claim.customer_email.lower() != (owner_email or "").lower():
        return None
    return claim


# --------------------------------------------------------------------------- orders
def get_order_status(order_id: str, owner_email: str) -> str:
    order = _own_order(order_id, owner_email)
    if not order:
        return f"No order found with ID {order_id} on your account. Please double-check the order ID."
    items = ", ".join(f"{i.quantity}x {i.name}" for i in order.items)
    return (
        f"Order {order.order_id} ({items}) is currently '{order.status.value}'. "
        f"Placed on {order.order_date}, expected delivery "
        f"{order.expected_delivery or 'N/A'}. Total: INR {order.total}."
    )


def get_my_orders(owner_email: str) -> str:
    orders = find_orders_by_email(owner_email)
    if not orders:
        return "You have no orders on your account."
    lines = [f"- {o.order_id}: {o.status.value}, placed {o.order_date}, total INR {o.total}" for o in orders]
    return "Your orders:\n" + "\n".join(lines)


def track_package(order_id: str, owner_email: str) -> str:
    order = _own_order(order_id, owner_email)
    if not order:
        return f"No order found with ID {order_id} on your account."
    if not order.tracking_number:
        return f"Order {order.order_id} does not have tracking information yet (status: {order.status.value})."
    return (
        f"Order {order.order_id} ({order.status.value}): tracking number {order.tracking_number} "
        f"via {order.carrier}. Current location: {order.current_location}. "
        f"Expected delivery: {order.expected_delivery or 'N/A'}."
    )


def cancel_order(order_id: str, owner_email: str, reason: str = "customer requested") -> str:
    order = _own_order(order_id, owner_email)
    if not order:
        return f"No order found with ID {order_id} on your account."
    if order.status not in CANCELLABLE_STATUSES:
        return (
            f"Order {order_id} is '{order.status.value}' and can no longer be cancelled "
            f"(only Pending/Processing/Confirmed orders can be cancelled -- once shipped, "
            f"use a return instead)."
        )
    order.status = OrderStatus.CANCELLED
    order.cancellation_reason = reason
    return (
        f"Order {order_id} has been cancelled. A refund of INR {order.total} will be "
        f"processed to the original payment method within 5-7 business days."
    )


# --------------------------------------------------------------------------- products (public)
def search_products(query: str = "", category: str = "", max_price: float = 0) -> str:
    query_l = (query or "").lower()
    results = []
    for p in PRODUCTS.values():
        if query_l and query_l not in p.name.lower() and query_l not in p.category.lower():
            continue
        if category and category.lower() not in p.category.lower():
            continue
        if max_price and p.price > max_price:
            continue
        results.append(p)
    if not results:
        return "No products found matching those criteria."
    lines = [
        f"- {p.name} (SKU {p.sku}, {p.category}): INR {p.price}, "
        f"{'In Stock (' + str(p.stock) + ')' if p.stock > 0 else 'Out of Stock'}, rating {p.rating}/5"
        for p in results
    ]
    return "\n".join(lines)


def get_product_details(sku: str) -> str:
    p = PRODUCTS.get(sku.upper())
    if not p:
        return f"No product found with SKU {sku}."
    return f"{p.name} (SKU {p.sku}, {p.category}): INR {p.price}. {p.description} Stock: {p.stock}. Rating: {p.rating}/5."


# --------------------------------------------------------------------------- insurance
def _policy_line(p: Policy) -> str:
    due = f", next premium INR {p.annual_premium} due {p.next_premium_due}" if p.next_premium_due else ""
    return f"- {p.policy_id}: {p.plan_name} ({p.policy_type}), {p.status.value}, sum insured INR {p.sum_insured}{due}"


def get_my_policies(owner_email: str) -> str:
    policies = [p for p in POLICIES.values() if p.customer_email.lower() == owner_email.lower()]
    if not policies:
        return "You have no policies on your account."
    return "Your policies:\n" + "\n".join(_policy_line(p) for p in policies)


def get_policy_details(policy_id: str, owner_email: str) -> str:
    p = _own_policy(policy_id, owner_email)
    if not p:
        return f"No policy found with ID {policy_id} on your account."
    return (
        f"Policy {p.policy_id}: {p.plan_name} ({p.policy_type}) covering {p.insured_item}. Status: {p.status.value}. "
        f"Sum insured INR {p.sum_insured}; annual premium INR {p.annual_premium}"
        f"{', next due ' + str(p.next_premium_due) if p.next_premium_due else ''}. "
        f"Valid {p.start_date} to {p.end_date}."
    )


def _claim_line(c: Claim) -> str:
    return f"- {c.claim_id} on {c.policy_id}: {c.claim_type}, INR {c.amount_claimed}, {c.status.value}, filed {c.filed_date}"


def get_my_claims(owner_email: str) -> str:
    claims = [c for c in CLAIMS.values() if c.customer_email.lower() == owner_email.lower()]
    if not claims:
        return "You have no claims on your account."
    return "Your claims:\n" + "\n".join(_claim_line(c) for c in claims)


def get_claim_status(claim_id: str, owner_email: str) -> str:
    c = _own_claim(claim_id, owner_email)
    if not c:
        return f"No claim found with ID {claim_id} on your account."
    out = (
        f"Claim {c.claim_id} on policy {c.policy_id} ({c.claim_type}): {c.status.value}. "
        f"Claimed INR {c.amount_claimed}, filed {c.filed_date}."
    )
    if c.approved_amount is not None:
        out += f" Approved amount: INR {c.approved_amount}."
    if c.decision_note:
        out += f" Note: {c.decision_note}"
    return out


def file_claim(policy_id: str, owner_email: str, claim_type: str, amount: float, description: str = "") -> str:
    p = _own_policy(policy_id, owner_email)
    if not p:
        return f"No policy found with ID {policy_id} on your account."
    if p.status != PolicyStatus.ACTIVE:
        return f"Policy {p.policy_id} is '{p.status.value}', so a new claim cannot be filed on it."
    if amount <= 0:
        return "The claim amount must be greater than zero."
    if amount > p.sum_insured:
        return f"The claim amount INR {amount} exceeds the sum insured of INR {p.sum_insured} for policy {p.policy_id}."
    next_no = max((int(c.claim_id[3:]) for c in CLAIMS.values()), default=3000) + 1
    claim = Claim(
        claim_id=f"CLM{next_no}", policy_id=p.policy_id, customer_email=p.customer_email, claim_type=claim_type or "General",
        description=description, amount_claimed=amount, status=ClaimStatus.SUBMITTED, filed_date=TODAY,
    )
    CLAIMS[claim.claim_id] = claim
    return (
        f"Claim {claim.claim_id} has been filed on policy {p.policy_id} ({claim.claim_type}, INR {amount}). "
        f"Status: submitted. You will be updated once it is reviewed."
    )


# --------------------------------------------------------------------------- health
def health_check() -> str:
    return (
        f"Fulfillment API OK. {len(ORDERS)} orders, {len(PRODUCTS)} products, "
        f"{len(POLICIES)} policies, {len(CLAIMS)} claims loaded."
    )
