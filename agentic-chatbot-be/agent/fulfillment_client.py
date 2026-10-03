import os

import httpx
from langchain_core.tools import tool

FULFILLMENT_API_URL = os.getenv("FULFILLMENT_API_URL", "http://localhost:8010")
_TIMEOUT = 5.0


def _get(path: str, **params) -> str:
    try:
        resp = httpx.get(f"{FULFILLMENT_API_URL}{path}", params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()["result"]
    except httpx.HTTPError as e:
        return (
            f"Fulfillment API is not reachable at {FULFILLMENT_API_URL} ({e}). "
            f"Start it with: uvicorn fulfillment_api.server:app --port 8010"
        )


def _post(path: str, **body) -> str:
    try:
        resp = httpx.post(f"{FULFILLMENT_API_URL}{path}", json=body, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()["result"]
    except httpx.HTTPError as e:
        return (
            f"Fulfillment API is not reachable at {FULFILLMENT_API_URL} ({e}). "
            f"Start it with: uvicorn fulfillment_api.server:app --port 8010"
        )


def check_fulfillment_api_health() -> bool:
    try:
        resp = httpx.get(f"{FULFILLMENT_API_URL}/health", timeout=2.0)
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


# --------------------------------------------------------------------------- e-commerce tools
@tool
def get_order_status(order_id: str) -> str:
    """Look up the current status, items, and delivery date of an e-commerce order.
    Args:
        order_id: The order identifier, e.g. 'ORD1001'.
    """
    return _get(f"/orders/{order_id}")


@tool
def get_my_orders(customer_email: str) -> str:
    """List every order placed by a customer. Use this FIRST when a customer wants to
    cancel/track/ask about 'my order' but hasn't given an order ID -- never ask them
    for the order ID directly, show their orders and let them choose.
    Args:
        customer_email: The customer's email address.
    """
    return _get("/orders", customer_email=customer_email)


@tool
def track_package(order_id: str) -> str:
    """Get real-time shipment tracking details (carrier, current location, tracking number).
    Args:
        order_id: The order identifier, e.g. 'ORD1001'.
    """
    return _get(f"/orders/{order_id}/track")


@tool
def cancel_order(order_id: str, reason: str = "customer requested") -> str:
    """Cancel an order, if it's still in a cancellable state (not yet shipped).
    Args:
        order_id: The order identifier, e.g. 'ORD1003'.
        reason: Why the customer wants to cancel.
    """
    return _post(f"/orders/{order_id}/cancel", reason=reason)


@tool
def search_products(query: str = "", category: str = "", max_price: float = 0) -> str:
    """Search the product catalog by name/keyword, and optionally filter by category and/or max price.
    Args:
        query: Free-text search term or product name.
        category: Optional category filter, e.g. 'Laptops'.
        max_price: Optional maximum price in INR (0 = no limit).
    """
    return _get("/products", query=query, category=category, max_price=max_price)


@tool
def get_product_details(sku: str) -> str:
    """Get full details for one product by SKU.
    Args:
        sku: The product SKU, e.g. 'SKU-LT-201'.
    """
    return _get(f"/products/{sku}")


CUSTOMER_FACING_TOOLS = [get_order_status, get_my_orders, track_package, cancel_order]
PRODUCT_TOOLS = [search_products, get_product_details]


# --------------------------------------------------------------------------- insurance (WIP stub)
@tool
def insurance_status_wip() -> str:
    """Use this for ANY insurance question (policy, claim, premium, coverage). Insurance
    support is under development in this build -- this tool honestly tells the customer
    that, instead of guessing at policy or claim data.
    """
    return _get("/insurance/status")


INSURANCE_TOOLS = [insurance_status_wip]
