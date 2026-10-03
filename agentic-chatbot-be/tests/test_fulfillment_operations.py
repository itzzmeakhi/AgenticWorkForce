"""Unit tests for fulfillment_api/operations.py -- the business logic the
REST server (server.py) calls into."""
from fulfillment_api import operations as ops


class TestOrders:
    def test_get_order_status_found(self):
        result = ops.get_order_status("ORD1001")
        assert "ORD1001" in result
        assert "shipped" in result.lower()

    def test_get_order_status_not_found(self):
        result = ops.get_order_status("ORD9999")
        assert "no order found" in result.lower()

    def test_get_order_status_case_insensitive(self):
        assert "ORD1001" in ops.get_order_status("ord1001")

    def test_get_my_orders(self):
        result = ops.get_my_orders("priya.nair@example.com")
        assert "ORD1001" in result

    def test_get_my_orders_none(self):
        result = ops.get_my_orders("nobody@example.com")
        assert "no orders found" in result.lower()

    def test_track_package(self):
        result = ops.track_package("ORD1002")
        assert "TRK7841002298" in result
        assert "Delhivery" in result

    def test_track_package_no_tracking_yet(self):
        result = ops.track_package("ORD1003")  # still Processing, no tracking
        assert "does not have tracking" in result.lower()

    def test_cancel_order_success(self):
        result = ops.cancel_order("ORD1003", reason="changed my mind")
        assert "has been cancelled" in result.lower()
        assert ops.ORDERS["ORD1003"].status.value == "cancelled"

    def test_cancel_order_already_shipped_fails(self):
        result = ops.cancel_order("ORD1001")  # already Shipped
        assert "can no longer be cancelled" in result.lower()
        assert ops.ORDERS["ORD1001"].status.value == "shipped"

    def test_cancel_order_not_found(self):
        result = ops.cancel_order("ORD9999")
        assert "not found" in result.lower()


class TestProducts:
    def test_search_products_by_query(self):
        result = ops.search_products(query="laptop")
        assert "AeroBook" in result

    def test_search_products_by_max_price(self):
        result = ops.search_products(max_price=5000)
        assert "SwiftCharge" in result

    def test_search_products_no_match(self):
        result = ops.search_products(query="nonexistent-widget-xyz")
        assert "no products found" in result.lower()

    def test_get_product_details_found(self):
        result = ops.get_product_details("SKU-LT-201")
        assert "AeroBook 14 Slim" in result

    def test_get_product_details_not_found(self):
        result = ops.get_product_details("SKU-XX-999")
        assert "no product found" in result.lower()


class TestInsuranceStub:
    def test_insurance_status_wip_is_honest(self):
        result = ops.insurance_status_wip()
        assert "under active development" in result.lower() or "not available" in result.lower()


class TestHealth:
    def test_health_check(self):
        result = ops.health_check()
        assert "OK" in result
        assert "orders" in result.lower()
