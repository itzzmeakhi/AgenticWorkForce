import os
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional

import httpx
from langchain_core.tools import tool

FULFILLMENT_API_URL = os.getenv("FULFILLMENT_API_URL", "http://localhost:8010")
_TIMEOUT = 5.0

# The signed-in customer's token for the tool call currently running. The agent
# sets it around each tool invocation (see CallCenterAgent.tool_node); tools
# never take an email or customer id from the model, so the model cannot ask
# for someone else's data -- the Fulfillment API reads the identity from the token.
_current_token: ContextVar[Optional[str]] = ContextVar("fulfillment_token", default=None)


@contextmanager
def acting_as(token: Optional[str]):
    reset = _current_token.set(token)
    try:
        yield
    finally:
        _current_token.reset(reset)


def _headers() -> dict:
    token = _current_token.get()
    return {"Authorization": f"Bearer {token}"} if token else {}


_AUTH_REQUIRED = (
    "AUTH_REQUIRED: the customer is not signed in (or their session has expired). Tell them to use "
    "the Sign in button and choose the right account type, then ask again. Do not ask them to type "
    "an email address or order/policy number instead."
)


def _detail(resp: httpx.Response) -> str:
    try:
        return str(resp.json().get("detail", ""))
    except ValueError:
        return ""


def _result(resp: httpx.Response) -> str:
    if resp.status_code == 401:
        return _AUTH_REQUIRED
    if resp.status_code == 403:
        return (
            f"ACCESS_DENIED: {_detail(resp)} Tell the customer to sign out and sign in with the "
            f"right account type to use this."
        )
    resp.raise_for_status()
    return resp.json()["result"]


def _unreachable(e: Exception) -> str:
    return (
        f"Fulfillment API is not reachable at {FULFILLMENT_API_URL} ({e}). "
        f"Start it with: uvicorn fulfillment_api.server:app --port 8010"
    )


def _get(path: str, **params) -> str:
    try:
        return _result(httpx.get(f"{FULFILLMENT_API_URL}{path}", params=params, headers=_headers(), timeout=_TIMEOUT))
    except httpx.HTTPError as e:
        return _unreachable(e)


def _post(path: str, **body) -> str:
    try:
        return _result(httpx.post(f"{FULFILLMENT_API_URL}{path}", json=body, headers=_headers(), timeout=_TIMEOUT))
    except httpx.HTTPError as e:
        return _unreachable(e)


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
def get_my_orders() -> str:
    """List every order on the signed-in customer's account. Use this FIRST when a customer
    wants to cancel/track/ask about 'my order' but hasn't given an order ID -- never ask them
    for an order ID or email address, show their orders and let them choose. Takes no
    arguments: the customer is identified by their sign-in.
    """
    return _get("/orders")


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


# --------------------------------------------------------------------------- insurance tools
@tool
def get_my_policies() -> str:
    """List every insurance policy on the signed-in customer's account (plan, status, sum
    insured, next premium). Use this FIRST for 'my policy/policies' questions -- never ask
    for a policy number or email. Takes no arguments: the customer is identified by their sign-in.
    """
    return _get("/insurance/policies")


@tool
def get_policy_details(policy_id: str) -> str:
    """Get full details of one of the signed-in customer's policies.
    Args:
        policy_id: The policy identifier, e.g. 'POL2001'.
    """
    return _get(f"/insurance/policies/{policy_id}")


@tool
def get_my_claims() -> str:
    """List every claim the signed-in customer has filed, with its status. Takes no arguments."""
    return _get("/insurance/claims")


@tool
def get_claim_status(claim_id: str) -> str:
    """Get the status, amounts and decision note of one of the signed-in customer's claims.
    Args:
        claim_id: The claim identifier, e.g. 'CLM3001'.
    """
    return _get(f"/insurance/claims/{claim_id}")


@tool
def file_claim(policy_id: str, claim_type: str, amount: float, description: str = "") -> str:
    """File a new claim on one of the signed-in customer's active policies.
    Args:
        policy_id: The policy to claim against, e.g. 'POL2001'.
        claim_type: Short category, e.g. 'Hospitalisation' or 'Accident damage'.
        amount: Amount being claimed, in INR.
        description: What happened, in a sentence.
    """
    return _post("/insurance/claims", policy_id=policy_id, claim_type=claim_type, amount=amount, description=description)


INSURANCE_TOOLS = [get_my_policies, get_policy_details, get_my_claims, get_claim_status, file_claim]
