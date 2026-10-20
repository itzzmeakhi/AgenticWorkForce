import time
from typing import Dict, Optional, Tuple

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from fulfillment_api import customers
from fulfillment_api import operations as ops
from security.tokens import DOMAINS, Identity, TokenError, bearer_token, create_token, verify_token

load_dotenv()

app = FastAPI(title="Fulfillment API", version="0.7.0")


# --------------------------------------------------------------------------- auth
def _identity_for(domain: str):
    """Dependency: the signed-in customer, who must hold a token for `domain`.
    401 = no/invalid/expired token, 403 = valid token for the other domain."""

    def dependency(authorization: Optional[str] = Header(default=None)) -> Identity:
        token = bearer_token(authorization)
        if token is None:
            raise HTTPException(status_code=401, detail="Sign in required")
        try:
            identity = verify_token(token)
        except TokenError as e:
            raise HTTPException(status_code=401, detail=str(e))
        if identity.domain != domain:
            raise HTTPException(
                status_code=403,
                detail=f"This needs a {domain} account; you are signed in to {identity.domain}.",
            )
        return identity

    return dependency


require_ecommerce = _identity_for("ecommerce")
require_insurance = _identity_for("insurance")


class LoginRequest(BaseModel):
    domain: str
    email: str
    password: str


# Brute-force throttle: MAX_FAILURES failed sign-ins for one (domain, email)
# locks that account out for LOCKOUT_SECONDS. In memory, like the rest of the mock data.
MAX_FAILURES = 5
LOCKOUT_SECONDS = 60
_failures: Dict[Tuple[str, str], Tuple[int, float]] = {}


def _check_lockout(key: Tuple[str, str]) -> None:
    count, since = _failures.get(key, (0, 0.0))
    if count >= MAX_FAILURES:
        remaining = LOCKOUT_SECONDS - (time.time() - since)
        if remaining > 0:
            raise HTTPException(status_code=429, detail=f"Too many failed attempts. Try again in {int(remaining) + 1}s.")
        _failures.pop(key, None)


@app.post("/auth/login")
def login(body: LoginRequest):
    domain = body.domain.strip().lower()
    if domain not in DOMAINS:
        raise HTTPException(status_code=400, detail=f"domain must be one of {', '.join(DOMAINS)}")
    key = (domain, body.email.strip().lower())
    _check_lockout(key)

    customer = customers.authenticate(domain, body.email, body.password)
    if customer is None:
        count, since = _failures.get(key, (0, 0.0))
        _failures[key] = (count + 1, time.time() if count + 1 >= MAX_FAILURES else since)
        raise HTTPException(status_code=401, detail="Incorrect email or password for this account type.")

    _failures.pop(key, None)
    identity = Identity(customer_id=customer.customer_id, email=customer.email, name=customer.name, domain=domain)
    return {"token": create_token(identity), "user": identity.public()}


# --------------------------------------------------------------------------- general
@app.get("/health")
def health():
    return {"status": "ok", "detail": ops.health_check()}


# --------------------------------------------------------------------------- e-commerce (signed in)
class CancelRequest(BaseModel):
    reason: str = "customer requested"


@app.get("/orders")
def my_orders(who: Identity = Depends(require_ecommerce)):
    return {"result": ops.get_my_orders(who.email)}


@app.get("/orders/{order_id}")
def order_status(order_id: str, who: Identity = Depends(require_ecommerce)):
    return {"result": ops.get_order_status(order_id, who.email)}


@app.get("/orders/{order_id}/track")
def track(order_id: str, who: Identity = Depends(require_ecommerce)):
    return {"result": ops.track_package(order_id, who.email)}


@app.post("/orders/{order_id}/cancel")
def cancel(order_id: str, body: CancelRequest, who: Identity = Depends(require_ecommerce)):
    return {"result": ops.cancel_order(order_id, who.email, body.reason)}


# --------------------------------------------------------------------------- products (public catalogue)
@app.get("/products")
def products(query: str = "", category: str = "", max_price: float = 0):
    return {"result": ops.search_products(query, category, max_price)}


@app.get("/products/{sku}")
def product_details(sku: str):
    return {"result": ops.get_product_details(sku)}


# --------------------------------------------------------------------------- insurance (signed in)
class FileClaimRequest(BaseModel):
    policy_id: str
    claim_type: str = "General"
    amount: float
    description: str = ""


@app.get("/insurance/policies")
def my_policies(who: Identity = Depends(require_insurance)):
    return {"result": ops.get_my_policies(who.email)}


@app.get("/insurance/policies/{policy_id}")
def policy_details(policy_id: str, who: Identity = Depends(require_insurance)):
    return {"result": ops.get_policy_details(policy_id, who.email)}


@app.get("/insurance/claims")
def my_claims(who: Identity = Depends(require_insurance)):
    return {"result": ops.get_my_claims(who.email)}


@app.get("/insurance/claims/{claim_id}")
def claim_status(claim_id: str, who: Identity = Depends(require_insurance)):
    return {"result": ops.get_claim_status(claim_id, who.email)}


@app.post("/insurance/claims")
def file_claim(body: FileClaimRequest, who: Identity = Depends(require_insurance)):
    return {"result": ops.file_claim(body.policy_id, who.email, body.claim_type, body.amount, body.description)}
