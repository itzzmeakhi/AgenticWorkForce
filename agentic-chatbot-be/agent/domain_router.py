from typing import Literal

Domain = Literal["ecommerce", "insurance", "general"]

ECOMMERCE_KEYWORDS = [
    "order", "delivery", "delivered", "shipped", "return", "refund", "product",
    "sku", "cart", "shipping", "exchange", "cancel", "track", "buy", "purchase",
    "stock", "catalog", "price", "laptop", "phone", "smartwatch",
]
INSURANCE_KEYWORDS = [
    "policy", "claim", "premium", "coverage", "insured", "insurance", "renewal",
]


def classify_domain(text: str, previous_domain: str = "general") -> Domain:
    """Classify which business domain a user message belongs to, falling
    back to the previous turn's domain for ambiguous/short follow-ups."""
    t = text.lower()
    ecommerce_hits = sum(1 for k in ECOMMERCE_KEYWORDS if k in t)
    insurance_hits = sum(1 for k in INSURANCE_KEYWORDS if k in t)

    if ecommerce_hits == 0 and insurance_hits == 0:
        return previous_domain if previous_domain in ("ecommerce", "insurance") else "general"
    return "ecommerce" if ecommerce_hits >= insurance_hits else "insurance"
