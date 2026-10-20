"""Customer accounts -- one SEPARATE store per domain.

An e-commerce customer and an insurance customer are different records in
different stores (the same email can exist in both with different ids and
passwords). Signing in to a domain only checks that domain's store, and the
resulting token is only valid for that domain's endpoints.

All demo accounts use DEMO_PASSWORD (dummy data, not real credentials).
"""
from dataclasses import dataclass
from typing import Dict, Optional

from security.passwords import hash_password, verify_password

DEMO_PASSWORD = "demo1234"


@dataclass(frozen=True)
class Customer:
    customer_id: str
    name: str
    email: str
    password_hash: str


def _store(*rows) -> Dict[str, Customer]:
    return {
        email.lower(): Customer(customer_id=cid, name=name, email=email.lower(), password_hash=hash_password(DEMO_PASSWORD))
        for cid, name, email in rows
    }


ECOMMERCE_CUSTOMERS: Dict[str, Customer] = _store(
    ("CUST-E-001", "Priya Nair", "abc@gmail.com"),
    ("CUST-E-002", "Rahul Verma", "rahul@gmail.com"),
    ("CUST-E-003", "Akhil Reddy", "akhil@gmail.com"),
)

INSURANCE_CUSTOMERS: Dict[str, Customer] = _store(
    ("CUST-I-001", "Neha Kapoor", "neha@gmail.com"),
    ("CUST-I-002", "Vikram Singh", "vikram@gmail.com"),
    ("CUST-I-003", "Akhil Reddy", "akhil@gmail.com"),
)

CUSTOMER_STORES = {"ecommerce": ECOMMERCE_CUSTOMERS, "insurance": INSURANCE_CUSTOMERS}

# Verified against when the email is unknown, so "no such user" and "wrong
# password" take the same time.
_DUMMY_HASH = hash_password("not-a-real-password")


def authenticate(domain: str, email: str, password: str) -> Optional[Customer]:
    """The customer if (domain, email, password) is valid, else None."""
    store = CUSTOMER_STORES.get(domain)
    if store is None:
        return None
    customer = store.get((email or "").strip().lower())
    if customer is None:
        verify_password(password or "", _DUMMY_HASH)
        return None
    return customer if verify_password(password or "", customer.password_hash) else None
