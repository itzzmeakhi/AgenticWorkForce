from fastapi import FastAPI
from pydantic import BaseModel

from fulfillment_api import operations as ops

app = FastAPI(title="Fulfillment API (midsem build)", version="0.6.0")


class CancelRequest(BaseModel):
    reason: str = "customer requested"


@app.get("/health")
def health():
    return {"status": "ok", "detail": ops.health_check()}

@app.get("/orders")
def my_orders(customer_email: str):
    return {"result": ops.get_my_orders(customer_email)}

@app.get("/orders/{order_id}")
def order_status(order_id: str):
    return {"result": ops.get_order_status(order_id)}


@app.get("/orders/{order_id}/track")
def track(order_id: str):
    return {"result": ops.track_package(order_id)}


@app.post("/orders/{order_id}/cancel")
def cancel(order_id: str, body: CancelRequest):
    return {"result": ops.cancel_order(order_id, body.reason)}


@app.get("/products")
def products(query: str = "", category: str = "", max_price: float = 0):
    return {"result": ops.search_products(query, category, max_price)}


@app.get("/products/{sku}")
def product_details(sku: str):
    return {"result": ops.get_product_details(sku)}


@app.get("/insurance/status")
def insurance_status():
    return {"result": ops.insurance_status_wip()}
