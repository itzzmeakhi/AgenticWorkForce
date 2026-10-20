"""HTTP-layer tests for fulfillment_api/server.py, using FastAPI's
TestClient (in-process ASGI, no real socket). Orders and insurance need a
token; the catalogue and /health are public. Access-control cases live in
test_auth_access_control.py."""
from tests.conftest import auth


class TestHealthAndOrders:
    def test_health(self, fulfillment_test_client):
        resp = fulfillment_test_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_order_status(self, fulfillment_test_client, login):
        h = auth(login("ecommerce", "abc@gmail.com"))
        resp = fulfillment_test_client.get("/orders/ORD1001", headers=h)
        assert resp.status_code == 200
        assert "ORD1001" in resp.json()["result"]

    def test_my_orders(self, fulfillment_test_client, login):
        h = auth(login("ecommerce", "abc@gmail.com"))
        resp = fulfillment_test_client.get("/orders", headers=h)
        assert resp.status_code == 200
        assert "ORD1001" in resp.json()["result"]

    def test_track(self, fulfillment_test_client, login):
        h = auth(login("ecommerce", "rahul@gmail.com"))
        resp = fulfillment_test_client.get("/orders/ORD1002/track", headers=h)
        assert resp.status_code == 200
        assert "TRK7841002298" in resp.json()["result"]

    def test_cancel(self, fulfillment_test_client, login):
        h = auth(login("ecommerce", "akhil@gmail.com"))
        resp = fulfillment_test_client.post("/orders/ORD1003/cancel", json={"reason": "test"}, headers=h)
        assert resp.status_code == 200
        assert "cancelled" in resp.json()["result"].lower()


class TestProductsPublic:
    def test_products_search(self, fulfillment_test_client):
        resp = fulfillment_test_client.get("/products", params={"query": "watch"})
        assert resp.status_code == 200
        assert "PulseFit" in resp.json()["result"]

    def test_product_details(self, fulfillment_test_client):
        resp = fulfillment_test_client.get("/products/SKU-SW-301")
        assert resp.status_code == 200
        assert "PulseFit Watch 3" in resp.json()["result"]


class TestInsuranceEndpoints:
    def test_policies_and_claims(self, fulfillment_test_client, login):
        h = auth(login("insurance", "neha@gmail.com"))
        assert "POL2001" in fulfillment_test_client.get("/insurance/policies", headers=h).json()["result"]
        assert "CLM3001" in fulfillment_test_client.get("/insurance/claims", headers=h).json()["result"]
        assert "under_review" in fulfillment_test_client.get("/insurance/claims/CLM3001", headers=h).json()["result"]

    def test_file_claim(self, fulfillment_test_client, login):
        h = auth(login("insurance", "akhil@gmail.com"))
        resp = fulfillment_test_client.post(
            "/insurance/claims", headers=h,
            json={"policy_id": "POL2003", "claim_type": "Hospitalisation", "amount": 5000, "description": "x"},
        )
        assert resp.status_code == 200 and "has been filed" in resp.json()["result"].lower()
