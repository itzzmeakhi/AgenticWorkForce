import re
from typing import Literal

Domain = Literal["ecommerce", "insurance", "general"]

ECOMMERCE_KEYWORDS = [
    "order", "delivery", "delivered", "shipped", "return", "refund", "product",
    "sku", "cart", "shipping", "exchange", "cancel", "track", "buy", "purchase",
    "stock", "catalog", "price", "laptop", "phone", "smartwatch",
]
INSURANCE_KEYWORDS = [
    "polic", "claim", "premium", "coverage", "insured", "insurance", "renewal",
]


# Bare identifiers are strong signals ("status of ORD1001", "claim CLM3001", "POL2001")
_ORDER_ID = re.compile(r"\bord[- ]?\d+", re.I)
_INSURANCE_ID = re.compile(r"\b(?:pol|clm)[- ]?\d+", re.I)


def classify_domain(text: str, previous_domain: str = "general") -> Domain:
    """Classify which business domain a user message belongs to, falling
    back to the previous turn's domain for ambiguous/short follow-ups."""
    t = text.lower()
    ecommerce_hits = sum(1 for k in ECOMMERCE_KEYWORDS if k in t) + (2 if _ORDER_ID.search(t) else 0)
    insurance_hits = sum(1 for k in INSURANCE_KEYWORDS if k in t) + (2 if _INSURANCE_ID.search(t) else 0)

    if ecommerce_hits == 0 and insurance_hits == 0:
        return previous_domain if previous_domain in ("ecommerce", "insurance") else "general"
    return "ecommerce" if ecommerce_hits >= insurance_hits else "insurance"
