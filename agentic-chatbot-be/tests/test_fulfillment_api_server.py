"""HTTP-layer tests for fulfillment_api/server.py, using FastAPI's
TestClient (in-process ASGI, no real socket)."""


class TestHealthAndOrders:
    def test_health(self, fulfillment_test_client):
        resp = fulfillment_test_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_order_status(self, fulfillment_test_client):
        resp = fulfillment_test_client.get("/orders/ORD1001")
        assert resp.status_code == 200
        assert "ORD1001" in resp.json()["result"]

    def test_my_orders(self, fulfillment_test_client):
        resp = fulfillment_test_client.get("/orders", params={"customer_email": "priya.nair@example.com"})
        assert resp.status_code == 200
        assert "ORD1001" in resp.json()["result"]

    def test_track(self, fulfillment_test_client):
        resp = fulfillment_test_client.get("/orders/ORD1002/track")
        assert resp.status_code == 200
        assert "TRK7841002298" in resp.json()["result"]

    def test_cancel(self, fulfillment_test_client):
        resp = fulfillment_test_client.post("/orders/ORD1003/cancel", json={"reason": "test"})
        assert resp.status_code == 200
        assert "cancelled" in resp.json()["result"].lower()


class TestProductsAndInsurance:
    def test_products_search(self, fulfillment_test_client):
        resp = fulfillment_test_client.get("/products", params={"query": "watch"})
        assert resp.status_code == 200
        assert "PulseFit" in resp.json()["result"]

    def test_product_details(self, fulfillment_test_client):
        resp = fulfillment_test_client.get("/products/SKU-SW-301")
        assert resp.status_code == 200
        assert "PulseFit Watch 3" in resp.json()["result"]

    def test_insurance_status_stub(self, fulfillment_test_client):
        resp = fulfillment_test_client.get("/insurance/status")
        assert resp.status_code == 200
        assert "development" in resp.json()["result"].lower()
