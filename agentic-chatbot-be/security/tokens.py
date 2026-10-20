"""JWT access tokens shared by the Agent API (:8000) and the Fulfillment API (:8010).

The Fulfillment API (which owns the customer records) issues tokens at
POST /auth/login. Both services verify them with the same JWT_SECRET, so the
Fulfillment API can enforce ownership itself and never has to trust the agent.

Set JWT_SECRET in .env for anything beyond local development; without it a
built-in dev secret is used (and a warning is logged).
"""
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

import jwt

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
ISSUER = "intellia-fulfillment"
DOMAINS = ("ecommerce", "insurance")
_DEV_SECRET = "dev-only-secret-set-JWT_SECRET-in-your-env-file"
_warned = False


class TokenError(Exception):
    """Token missing, malformed, expired or otherwise not acceptable."""


@dataclass(frozen=True)
class Identity:
    customer_id: str
    email: str
    name: str
    domain: str  # 'ecommerce' | 'insurance' -- the domain this customer signed in to

    def public(self) -> dict:
        return {"customer_id": self.customer_id, "email": self.email, "name": self.name, "domain": self.domain}


def _secret() -> str:
    global _warned
    secret = os.getenv("JWT_SECRET")
    if secret:
        return secret
    if not _warned:
        logger.warning("JWT_SECRET is not set -- using the built-in development secret. Set it in .env.")
        _warned = True
    return _DEV_SECRET


def _ttl_seconds() -> int:
    return int(os.getenv("JWT_TTL_MINUTES", "240")) * 60


def create_token(identity: Identity, ttl_seconds: Optional[int] = None) -> str:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "sub": identity.customer_id,
        "email": identity.email,
        "name": identity.name,
        "domain": identity.domain,
        "iat": now,
        "exp": now + (ttl_seconds if ttl_seconds is not None else _ttl_seconds()),
    }
    return jwt.encode(claims, _secret(), algorithm=ALGORITHM)


def verify_token(token: str) -> Identity:
    try:
        claims = jwt.decode(
            token, _secret(), algorithms=[ALGORITHM], issuer=ISSUER,
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
    except jwt.ExpiredSignatureError as e:
        raise TokenError("Session expired -- please sign in again") from e
    except jwt.PyJWTError as e:
        raise TokenError("Invalid token") from e
    if claims.get("domain") not in DOMAINS or not claims.get("email"):
        raise TokenError("Invalid token")
    return Identity(customer_id=claims["sub"], email=claims["email"], name=claims.get("name", ""), domain=claims["domain"])


def bearer_token(authorization_header: Optional[str]) -> Optional[str]:
    """Extract the token from an 'Authorization: Bearer <token>' header value."""
    if not authorization_header:
        return None
    scheme, _, value = authorization_header.partition(" ")
    return value.strip() if scheme.lower() == "bearer" and value.strip() else None
