from fulfillment_api.mock_data import ORDERS, PRODUCTS, find_orders_by_email
from fulfillment_api.models import OrderStatus

CANCELLABLE_STATUSES = {OrderStatus.PENDING, OrderStatus.PROCESSING, OrderStatus.CONFIRMED}


# --------------------------------------------------------------------------- orders
def get_order_status(order_id: str) -> str:
    order = ORDERS.get(order_id.upper())
    if not order:
        return f"No order found with ID {order_id}. Please double-check the order ID."
    items = ", ".join(f"{i.quantity}x {i.name}" for i in order.items)
    return (
        f"Order {order.order_id} ({items}) is currently '{order.status.value}'. "
        f"Placed on {order.order_date}, expected delivery "
        f"{order.expected_delivery or 'N/A'}. Total: INR {order.total}."
    )


def get_my_orders(customer_email: str) -> str:
    orders = find_orders_by_email(customer_email)
    if not orders:
        return f"No orders found for {customer_email}."
    lines = [f"- {o.order_id}: {o.status.value}, placed {o.order_date}, total INR {o.total}" for o in orders]
    return f"Orders for {customer_email}:\n" + "\n".join(lines)


def track_package(order_id: str) -> str:
    order = ORDERS.get(order_id.upper())
    if not order:
        return f"No order found with ID {order_id}."
    if not order.tracking_number:
        return f"Order {order.order_id} does not have tracking information yet (status: {order.status.value})."
    return (
        f"Order {order.order_id} ({order.status.value}): tracking number {order.tracking_number} "
        f"via {order.carrier}. Current location: {order.current_location}. "
        f"Expected delivery: {order.expected_delivery or 'N/A'}."
    )


def cancel_order(order_id: str, reason: str = "customer requested") -> str:
    order = ORDERS.get(order_id.upper())
    if not order:
        return f"Order {order_id} not found."
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


# --------------------------------------------------------------------------- products
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


# --------------------------------------------------------------------------- insurance (WIP)
def insurance_status_wip() -> str:
    return (
        "Insurance support (policy lookup, claims status, coverage details) is under "
        "active development and not available yet."
        "Please check back soon, or ask about an order or product instead."
    )


# --------------------------------------------------------------------------- health
def health_check() -> str:
    return f"Fulfillment API OK. {len(ORDERS)} orders, {len(PRODUCTS)} products loaded. Insurance: WIP stub only."
