"""Tests for agent/domain_router.py's keyword-based classify_domain()."""
from agent.domain_router import classify_domain


def test_ecommerce_keywords():
    assert classify_domain("Where is my order ORD1001?") == "ecommerce"
    assert classify_domain("I want to return this laptop") == "ecommerce"


def test_insurance_keywords():
    assert classify_domain("I need to check my policy premium") == "insurance"


def test_ambiguous_falls_back_to_previous_domain():
    assert classify_domain("thanks, and one more thing", previous_domain="insurance") == "insurance"
    assert classify_domain("ok great", previous_domain="ecommerce") == "ecommerce"


def test_ambiguous_no_previous_domain_falls_back_to_general():
    assert classify_domain("hello there") == "general"


def test_plural_policies_routes_to_insurance():
    assert classify_domain("Show me my policies") == "insurance"


def test_bare_ids_route_to_their_domain():
    assert classify_domain("status of ORD1001") == "ecommerce"
    assert classify_domain("what about POL2001", previous_domain="ecommerce") == "insurance"
    assert classify_domain("how is CLM3001 going", previous_domain="ecommerce") == "insurance"


def test_refund_policy_stays_ecommerce():
    assert classify_domain("What is your refund policy?") == "ecommerce"
