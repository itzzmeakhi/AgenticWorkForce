"""Unit tests for fulfillment_api/operations.py -- the business logic the
REST server (server.py) calls into. Every customer-data operation is scoped to
`owner_email`; ownership/access-control behaviour is covered in
test_auth_access_control.py."""
from fulfillment_api import operations as ops

ABC = "abc@gmail.com"        # owns ORD1001 (shipped), ORD1005 (delivered)
RAHUL = "rahul@gmail.com"    # owns ORD1002 (shipped), ORD1006 (processing)
AKHIL = "akhil@gmail.com"    # owns ORD1003, ORD1004 (processing)


class TestOrders:
    def test_get_order_status_found(self):
        result = ops.get_order_status("ORD1001", ABC)
        assert "ORD1001" in result
        assert "shipped" in result.lower()

    def test_get_order_status_not_found(self):
        assert "no order found" in ops.get_order_status("ORD9999", ABC).lower()

    def test_get_order_status_case_insensitive(self):
        assert "ORD1001" in ops.get_order_status("ord1001", ABC)

    def test_get_my_orders_lists_only_own(self):
        result = ops.get_my_orders(ABC)
        assert "ORD1001" in result and "ORD1005" in result
        assert "ORD1002" not in result and "ORD1003" not in result

    def test_get_my_orders_none(self):
        assert "no orders" in ops.get_my_orders("nobody@example.com").lower()

    def test_track_package(self):
        result = ops.track_package("ORD1002", RAHUL)
        assert "TRK7841002298" in result
        assert "Delhivery" in result

    def test_track_package_no_tracking_yet(self):
        assert "does not have tracking" in ops.track_package("ORD1003", AKHIL).lower()  # still Processing

    def test_cancel_order_success(self):
        result = ops.cancel_order("ORD1003", AKHIL, reason="changed my mind")
        assert "has been cancelled" in result.lower()
        assert ops.ORDERS["ORD1003"].status.value == "cancelled"

    def test_cancel_order_already_shipped_fails(self):
        result = ops.cancel_order("ORD1001", ABC)  # already Shipped
        assert "can no longer be cancelled" in result.lower()
        assert ops.ORDERS["ORD1001"].status.value == "shipped"

    def test_cancel_order_not_found(self):
        assert "no order found" in ops.cancel_order("ORD9999", ABC).lower()


class TestProducts:
    def test_search_products_by_query(self):
        assert "AeroBook" in ops.search_products(query="laptop")

    def test_search_products_by_max_price(self):
        assert "SwiftCharge" in ops.search_products(max_price=5000)

    def test_search_products_no_match(self):
        assert "no products found" in ops.search_products(query="nonexistent-widget-xyz").lower()

    def test_get_product_details_found(self):
        assert "AeroBook 14 Slim" in ops.get_product_details("SKU-LT-201")

    def test_get_product_details_not_found(self):
        assert "no product found" in ops.get_product_details("SKU-XX-999").lower()


class TestInsurance:
    def test_my_policies(self):
        result = ops.get_my_policies("neha@gmail.com")
        assert "POL2001" in result and "POL2005" in result and "POL2002" not in result

    def test_policy_details(self):
        assert "Family Floater" in ops.get_policy_details("POL2001", "neha@gmail.com")

    def test_claim_status_with_decision(self):
        result = ops.get_claim_status("CLM3002", "vikram@gmail.com")
        assert "approved" in result.lower() and "14000" in result

    def test_file_claim_success(self):
        result = ops.file_claim("POL2003", "akhil@gmail.com", "Hospitalisation", 25000, "fracture")
        assert "has been filed" in result.lower()
        new_id = [c for c in ops.CLAIMS if c not in ("CLM3001", "CLM3002", "CLM3003")][0]
        assert ops.CLAIMS[new_id].status.value == "submitted"

    def test_file_claim_on_lapsed_policy_rejected(self):
        assert "cannot be filed" in ops.file_claim("POL2004", "akhil@gmail.com", "Theft", 1000).lower()

    def test_file_claim_above_sum_insured_rejected(self):
        assert "exceeds the sum insured" in ops.file_claim("POL2003", "akhil@gmail.com", "Surgery", 9_999_999).lower()

    def test_file_claim_needs_positive_amount(self):
        assert "greater than zero" in ops.file_claim("POL2003", "akhil@gmail.com", "Surgery", 0).lower()


class TestHealth:
    def test_health_check(self):
        result = ops.health_check()
        assert "OK" in result
        assert "orders" in result.lower() and "policies" in result.lower()
