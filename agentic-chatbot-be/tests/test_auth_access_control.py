"""Authentication and access-control tests.

Covers: per-domain login, token validation, that each endpoint needs a token
for its own domain, that one customer can never read or change another's data,
that the agent only ever acts as the signed-in customer, and that chat
sessions are bound to their owner.

Dummy accounts (all password "demo1234"):
  e-commerce: abc@gmail.com, rahul@gmail.com, akhil@gmail.com
  insurance:  neha@gmail.com, vikram@gmail.com, akhil@gmail.com (a separate account)
"""
import time

import jwt
import pytest
from fastapi.testclient import TestClient

from fulfillment_api import mock_data
from security.passwords import hash_password, verify_password
from security.tokens import ALGORITHM, ISSUER, Identity, TokenError, create_token, verify_token
from tests.conftest import auth

NOT_FOUND = "no order found"


# =========================================================================== login
class TestLogin:
    def test_ecommerce_login_issues_token_for_that_domain(self, fulfillment_test_client):
        r = fulfillment_test_client.post("/auth/login", json={"domain": "ecommerce", "email": "abc@gmail.com", "password": "demo1234"})
        assert r.status_code == 200
        body = r.json()
        assert body["user"] == {"customer_id": "CUST-E-001", "email": "abc@gmail.com", "name": "Priya Nair", "domain": "ecommerce"}
        assert verify_token(body["token"]).domain == "ecommerce"

    def test_insurance_login_issues_token_for_that_domain(self, fulfillment_test_client):
        r = fulfillment_test_client.post("/auth/login", json={"domain": "insurance", "email": "neha@gmail.com", "password": "demo1234"})
        assert r.status_code == 200
        assert verify_token(r.json()["token"]).domain == "insurance"

    def test_email_is_case_insensitive(self, fulfillment_test_client):
        r = fulfillment_test_client.post("/auth/login", json={"domain": "ecommerce", "email": " ABC@Gmail.com ", "password": "demo1234"})
        assert r.status_code == 200

    def test_wrong_password_rejected(self, fulfillment_test_client):
        r = fulfillment_test_client.post("/auth/login", json={"domain": "ecommerce", "email": "abc@gmail.com", "password": "nope"})
        assert r.status_code == 401

    def test_unknown_user_gets_same_error_as_wrong_password(self, fulfillment_test_client):
        wrong_pw = fulfillment_test_client.post("/auth/login", json={"domain": "ecommerce", "email": "abc@gmail.com", "password": "x"})
        no_user = fulfillment_test_client.post("/auth/login", json={"domain": "ecommerce", "email": "ghost@gmail.com", "password": "x"})
        assert wrong_pw.status_code == no_user.status_code == 401
        assert wrong_pw.json() == no_user.json()  # no user enumeration

    def test_customer_of_one_domain_cannot_log_in_to_the_other(self, fulfillment_test_client):
        # rahul exists only in the e-commerce store, neha only in the insurance store
        r1 = fulfillment_test_client.post("/auth/login", json={"domain": "insurance", "email": "rahul@gmail.com", "password": "demo1234"})
        r2 = fulfillment_test_client.post("/auth/login", json={"domain": "ecommerce", "email": "neha@gmail.com", "password": "demo1234"})
        assert r1.status_code == r2.status_code == 401

    def test_same_email_in_both_domains_is_two_separate_accounts(self, login):
        e = verify_token(login("ecommerce", "akhil@gmail.com"))
        i = verify_token(login("insurance", "akhil@gmail.com"))
        assert (e.customer_id, e.domain) == ("CUST-E-003", "ecommerce")
        assert (i.customer_id, i.domain) == ("CUST-I-003", "insurance")

    def test_unknown_domain_is_400(self, fulfillment_test_client):
        r = fulfillment_test_client.post("/auth/login", json={"domain": "banking", "email": "abc@gmail.com", "password": "demo1234"})
        assert r.status_code == 400

    def test_repeated_failures_lock_the_account_temporarily(self, fulfillment_test_client):
        for _ in range(5):
            assert fulfillment_test_client.post(
                "/auth/login", json={"domain": "ecommerce", "email": "abc@gmail.com", "password": "bad"}).status_code == 401
        locked = fulfillment_test_client.post("/auth/login", json={"domain": "ecommerce", "email": "abc@gmail.com", "password": "demo1234"})
        assert locked.status_code == 429  # even the right password is refused while locked
        # other accounts are unaffected
        assert fulfillment_test_client.post(
            "/auth/login", json={"domain": "ecommerce", "email": "rahul@gmail.com", "password": "demo1234"}).status_code == 200

    def test_passwords_are_stored_hashed(self):
        from fulfillment_api.customers import ECOMMERCE_CUSTOMERS, INSURANCE_CUSTOMERS

        for store in (ECOMMERCE_CUSTOMERS, INSURANCE_CUSTOMERS):
            for c in store.values():
                assert "demo1234" not in c.password_hash and c.password_hash.startswith("pbkdf2_sha256$")

    def test_password_hash_roundtrip(self):
        h = hash_password("s3cret")
        assert verify_password("s3cret", h) and not verify_password("S3cret", h)
        assert hash_password("s3cret") != h  # salted
        assert not verify_password("s3cret", "garbage")


# =========================================================================== tokens
class TestTokens:
    ident = Identity("CUST-E-001", "abc@gmail.com", "Priya Nair", "ecommerce")

    def test_roundtrip(self):
        assert verify_token(create_token(self.ident)) == self.ident

    def test_expired_token_rejected(self):
        with pytest.raises(TokenError, match="expired"):
            verify_token(create_token(self.ident, ttl_seconds=-5))

    def test_tampered_token_rejected(self):
        t = create_token(self.ident)
        head, payload, sig = t.split(".")
        with pytest.raises(TokenError):
            verify_token(f"{head}.{payload}.{sig[:-2]}xx")

    def test_token_signed_with_another_secret_rejected(self):
        forged = jwt.encode({"iss": ISSUER, "sub": "CUST-E-001", "email": "abc@gmail.com", "domain": "ecommerce",
                             "iat": int(time.time()), "exp": int(time.time()) + 600}, "attacker-secret-attacker-secret-1234", algorithm=ALGORITHM)
        with pytest.raises(TokenError):
            verify_token(forged)

    def test_unsigned_alg_none_token_rejected(self):
        now = int(time.time())
        unsigned = jwt.encode({"iss": ISSUER, "sub": "x", "email": "abc@gmail.com", "domain": "ecommerce", "iat": now, "exp": now + 600},
                              key=None, algorithm="none")
        with pytest.raises(TokenError):
            verify_token(unsigned)

    def test_wrong_issuer_rejected(self):
        from security.tokens import _secret

        now = int(time.time())
        t = jwt.encode({"iss": "someone-else", "sub": "x", "email": "a@b.c", "domain": "ecommerce", "iat": now, "exp": now + 600},
                       _secret(), algorithm=ALGORITHM)
        with pytest.raises(TokenError):
            verify_token(t)

    def test_unknown_domain_claim_rejected(self):
        t = create_token(Identity("x", "a@b.c", "A", "banking"))
        with pytest.raises(TokenError):
            verify_token(t)


# =========================================================================== fulfillment API: e-commerce
ORDER_ENDPOINTS = [
    ("get", "/orders", None),
    ("get", "/orders/ORD1001", None),
    ("get", "/orders/ORD1001/track", None),
    ("post", "/orders/ORD1003/cancel", {"reason": "x"}),
]
INSURANCE_ENDPOINTS = [
    ("get", "/insurance/policies", None),
    ("get", "/insurance/policies/POL2001", None),
    ("get", "/insurance/claims", None),
    ("get", "/insurance/claims/CLM3001", None),
    ("post", "/insurance/claims", {"policy_id": "POL2001", "claim_type": "x", "amount": 100}),
]


def _call(client, method, path, body, headers=None):
    return getattr(client, method)(path, headers=headers or {}, **({"json": body} if body is not None else {}))


class TestEndpointsRequireTheRightToken:
    @pytest.mark.parametrize("method,path,body", ORDER_ENDPOINTS + INSURANCE_ENDPOINTS)
    def test_no_token_is_401(self, fulfillment_test_client, method, path, body):
        assert _call(fulfillment_test_client, method, path, body).status_code == 401

    @pytest.mark.parametrize("header", ["Bearer", "Bearer ", "Basic abc", "Bearer not.a.jwt", "token"])
    def test_malformed_authorization_is_401(self, fulfillment_test_client, header):
        r = fulfillment_test_client.get("/orders", headers={"Authorization": header})
        assert r.status_code == 401

    def test_expired_token_is_401(self, fulfillment_test_client):
        t = create_token(Identity("CUST-E-001", "abc@gmail.com", "P", "ecommerce"), ttl_seconds=-1)
        assert fulfillment_test_client.get("/orders", headers=auth(t)).status_code == 401

    @pytest.mark.parametrize("method,path,body", INSURANCE_ENDPOINTS)
    def test_ecommerce_token_cannot_use_insurance_endpoints(self, fulfillment_test_client, login, method, path, body):
        r = _call(fulfillment_test_client, method, path, body, auth(login("ecommerce", "akhil@gmail.com")))
        assert r.status_code == 403

    @pytest.mark.parametrize("method,path,body", ORDER_ENDPOINTS)
    def test_insurance_token_cannot_use_order_endpoints(self, fulfillment_test_client, login, method, path, body):
        r = _call(fulfillment_test_client, method, path, body, auth(login("insurance", "akhil@gmail.com")))
        assert r.status_code == 403

    def test_catalogue_and_health_stay_public(self, fulfillment_test_client):
        assert fulfillment_test_client.get("/products").status_code == 200
        assert fulfillment_test_client.get("/products/SKU-SW-301").status_code == 200
        assert fulfillment_test_client.get("/health").status_code == 200


class TestOneCustomerCannotSeeAnothersOrders:
    def test_my_orders_returns_only_the_callers_orders(self, fulfillment_test_client, login):
        abc = fulfillment_test_client.get("/orders", headers=auth(login("ecommerce", "abc@gmail.com"))).json()["result"]
        rahul = fulfillment_test_client.get("/orders", headers=auth(login("ecommerce", "rahul@gmail.com"))).json()["result"]
        assert "ORD1001" in abc and "ORD1005" in abc and "ORD1002" not in abc and "ORD1006" not in abc
        assert "ORD1002" in rahul and "ORD1006" in rahul and "ORD1001" not in rahul

    def test_my_orders_ignores_an_email_query_parameter(self, fulfillment_test_client, login):
        r = fulfillment_test_client.get("/orders", params={"customer_email": "rahul@gmail.com"}, headers=auth(login("ecommerce", "abc@gmail.com")))
        assert "ORD1002" not in r.json()["result"] and "ORD1001" in r.json()["result"]

    def test_cannot_read_someone_elses_order(self, fulfillment_test_client, login):
        h = auth(login("ecommerce", "abc@gmail.com"))
        theirs = fulfillment_test_client.get("/orders/ORD1002", headers=h).json()["result"]
        missing = fulfillment_test_client.get("/orders/ORD9999", headers=h).json()["result"]
        assert NOT_FOUND in theirs.lower()
        assert "Delhivery" not in theirs and "EchoBeat" not in theirs
        # indistinguishable from an order that does not exist (no ID probing)
        assert theirs.replace("ORD1002", "X") == missing.replace("ORD9999", "X")

    def test_cannot_track_someone_elses_order(self, fulfillment_test_client, login):
        r = fulfillment_test_client.get("/orders/ORD1002/track", headers=auth(login("ecommerce", "abc@gmail.com")))
        assert NOT_FOUND in r.json()["result"].lower() and "TRK7841002298" not in r.json()["result"]

    def test_cannot_cancel_someone_elses_order(self, fulfillment_test_client, login):
        h = auth(login("ecommerce", "abc@gmail.com"))
        r = fulfillment_test_client.post("/orders/ORD1003/cancel", json={"reason": "sabotage"}, headers=h)
        assert NOT_FOUND in r.json()["result"].lower()
        assert mock_data.ORDERS["ORD1003"].status.value == "processing"
        assert mock_data.ORDERS["ORD1003"].cancellation_reason is None

    def test_owner_can_cancel_their_own_order(self, fulfillment_test_client, login):
        h = auth(login("ecommerce", "akhil@gmail.com"))
        r = fulfillment_test_client.post("/orders/ORD1003/cancel", json={"reason": "mine"}, headers=h)
        assert "has been cancelled" in r.json()["result"].lower()
        assert mock_data.ORDERS["ORD1003"].status.value == "cancelled"


class TestOneCustomerCannotSeeAnothersPolicies:
    def test_policies_and_claims_are_scoped_to_the_caller(self, fulfillment_test_client, login):
        neha = auth(login("insurance", "neha@gmail.com"))
        policies = fulfillment_test_client.get("/insurance/policies", headers=neha).json()["result"]
        claims = fulfillment_test_client.get("/insurance/claims", headers=neha).json()["result"]
        assert "POL2001" in policies and "POL2002" not in policies and "POL2003" not in policies
        assert "CLM3001" in claims and "CLM3002" not in claims

    def test_cannot_read_someone_elses_policy_or_claim(self, fulfillment_test_client, login):
        neha = auth(login("insurance", "neha@gmail.com"))
        pol = fulfillment_test_client.get("/insurance/policies/POL2002", headers=neha).json()["result"]
        clm = fulfillment_test_client.get("/insurance/claims/CLM3002", headers=neha).json()["result"]
        assert "no policy found" in pol.lower() and "Swift" not in pol
        assert "no claim found" in clm.lower() and "14000" not in clm

    def test_cannot_file_a_claim_on_someone_elses_policy(self, fulfillment_test_client, login):
        before = set(mock_data.CLAIMS)
        r = fulfillment_test_client.post("/insurance/claims", headers=auth(login("insurance", "neha@gmail.com")),
                                         json={"policy_id": "POL2002", "claim_type": "Fraud", "amount": 1000})
        assert "no policy found" in r.json()["result"].lower()
        assert set(mock_data.CLAIMS) == before

    def test_filing_a_claim_attaches_it_to_the_caller(self, fulfillment_test_client, login):
        vikram = auth(login("insurance", "vikram@gmail.com"))
        r = fulfillment_test_client.post("/insurance/claims", headers=vikram,
                                         json={"policy_id": "POL2002", "claim_type": "Windscreen", "amount": 4000})
        assert "has been filed" in r.json()["result"].lower()
        new = [c for c in mock_data.CLAIMS.values() if c.claim_type == "Windscreen"][0]
        assert new.customer_email == "vikram@gmail.com"
        # visible to vikram, invisible to neha
        assert new.claim_id in fulfillment_test_client.get("/insurance/claims", headers=vikram).json()["result"]
        neha = auth(login("insurance", "neha@gmail.com"))
        assert new.claim_id not in fulfillment_test_client.get("/insurance/claims", headers=neha).json()["result"]

    def test_same_email_ecommerce_login_gets_no_insurance_data(self, fulfillment_test_client, login):
        # akhil has accounts in both domains, but each token only opens its own domain
        eco = auth(login("ecommerce", "akhil@gmail.com"))
        assert fulfillment_test_client.get("/insurance/policies", headers=eco).status_code == 403
        ins = auth(login("insurance", "akhil@gmail.com"))
        assert fulfillment_test_client.get("/orders", headers=ins).status_code == 403


# =========================================================================== the agent acts only as the signed-in customer
class TestAgentAccessControl:
    def test_anonymous_my_orders_is_told_to_sign_in(self, make_agent):
        result = make_agent().chat("Show me my orders")
        assert "AUTH_REQUIRED" in result["reply"]
        assert "ORD" not in result["reply"].replace("AUTH_REQUIRED", "")

    def test_anonymous_cannot_read_an_order_by_id(self, make_agent):
        result = make_agent().chat("What is the status of order ORD1001?")
        assert "AUTH_REQUIRED" in result["reply"] and "Nova" not in result["reply"]

    def test_anonymous_can_still_search_products(self, make_agent):
        result = make_agent().chat("Show me laptops under 100000")
        assert any(tc["tool"] == "search_products" for tc in result["tool_calls"])
        assert "AUTH_REQUIRED" not in result["reply"]

    def test_my_orders_needs_no_email_and_lists_only_own(self, make_agent):
        result = make_agent("abc@gmail.com").chat("Show me my orders")
        assert [tc["tool"] for tc in result["tool_calls"]] == ["get_my_orders"]
        assert result["tool_calls"][0]["args"] == {}  # the model passes no identity at all
        assert "ORD1001" in result["reply"] and "ORD1005" in result["reply"]
        assert "ORD1002" not in result["reply"] and "ORD1003" not in result["reply"]

    def test_my_orders_tool_takes_no_arguments(self):
        from agent.fulfillment_client import get_my_orders, get_my_policies, get_my_claims

        for t in (get_my_orders, get_my_policies, get_my_claims):
            assert t.args == {}

    def test_asking_about_another_customers_order_reveals_nothing(self, make_agent):
        result = make_agent("abc@gmail.com").chat("What is the status of order ORD1002?")
        assert NOT_FOUND in result["reply"].lower()
        assert "EchoBeat" not in result["reply"] and "Pune" not in result["reply"]

    def test_cannot_cancel_another_customers_order_even_after_confirming(self, make_agent):
        agent = make_agent("abc@gmail.com")
        agent.chat("Cancel order ORD1003")
        result = agent.chat("Yes, cancel order ORD1003")
        assert NOT_FOUND in result["reply"].lower()
        assert mock_data.ORDERS["ORD1003"].status.value == "processing"

    def test_signed_in_to_ecommerce_cannot_use_insurance_tools(self, make_agent):
        result = make_agent("akhil@gmail.com").chat("Show me my policies")
        assert "ACCESS_DENIED" in result["reply"]
        assert "POL2003" not in result["reply"]

    def test_signed_in_to_insurance_cannot_use_order_tools(self, make_agent):
        result = make_agent("akhil@gmail.com", domain="insurance").chat("Show me my orders")
        assert "ACCESS_DENIED" in result["reply"]
        assert "ORD1003" not in result["reply"]

    def test_switching_customer_drops_the_previous_customers_conversation(self, make_agent, login):
        from security.tokens import verify_token

        agent = make_agent("abc@gmail.com")
        agent.chat("Show me my orders")
        agent.chat("Cancel order ORD1005")
        assert agent.conversation_history and agent.pending_cancellation
        token = login("ecommerce", "rahul@gmail.com")
        agent.set_auth(verify_token(token), token)
        assert agent.conversation_history == [] and agent.pending_cancellation is None
        assert "ORD1001" not in agent.chat("Show me my orders")["reply"]

    def test_signing_out_clears_identity_and_history(self, make_agent):
        agent = make_agent("abc@gmail.com")
        agent.chat("Show me my orders")
        agent.set_auth(None, None)
        assert agent.identity is None and agent.token is None and agent.conversation_history == []
        assert "AUTH_REQUIRED" in agent.chat("Show me my orders")["reply"]

    def test_tool_call_without_a_token_in_scope_sends_no_credentials(self, make_agent):
        # the token is only attached while a tool runs for the signed-in agent
        from agent import fulfillment_client as fc

        assert fc._headers() == {}
        with fc.acting_as("abc"):
            assert fc._headers() == {"Authorization": "Bearer abc"}
        assert fc._headers() == {}

    def test_system_prompt_names_the_customer_but_never_the_email(self):
        from agent.system_prompt_config import get_system_prompt

        prompt = get_system_prompt("ecommerce", True, Identity("CUST-E-001", "abc@gmail.com", "Priya Nair", "ecommerce"))
        assert "Priya Nair" in prompt and "abc@gmail.com" not in prompt
        assert "NOT signed in" in get_system_prompt("general", True, None)


# =========================================================================== Agent API: login proxy, tokens, sessions
@pytest.fixture
def api(fulfillment_wired):
    from api.main import SESSION_OWNERS, SESSIONS, app

    SESSIONS.clear()
    SESSION_OWNERS.clear()
    return TestClient(app)


def _chat(api, message, token=None, session_id=None):
    return api.post("/chat", json={"message": message, "session_id": session_id}, headers=auth(token) if token else {})


class TestAgentApiAuth:
    def test_login_through_agent_api(self, api):
        r = api.post("/auth/login", json={"domain": "insurance", "email": "neha@gmail.com", "password": "demo1234"})
        assert r.status_code == 200 and r.json()["user"]["domain"] == "insurance" and r.json()["token"]

    def test_bad_login_is_401_with_message(self, api):
        r = api.post("/auth/login", json={"domain": "ecommerce", "email": "abc@gmail.com", "password": "wrong"})
        assert r.status_code == 401 and "incorrect" in r.json()["detail"].lower()

    def test_login_when_fulfillment_api_is_down_is_503(self, api, monkeypatch):
        import httpx

        def down(*a, **k):
            raise httpx.ConnectError("refused")

        monkeypatch.setattr(httpx, "post", down)
        r = api.post("/auth/login", json={"domain": "ecommerce", "email": "abc@gmail.com", "password": "demo1234"})
        assert r.status_code == 503

    def test_me_returns_identity_and_rejects_missing_or_bad_token(self, api, login):
        assert api.get("/auth/me").status_code == 401
        assert api.get("/auth/me", headers=auth("garbage")).status_code == 401
        me = api.get("/auth/me", headers=auth(login("ecommerce", "abc@gmail.com"))).json()
        assert me["email"] == "abc@gmail.com" and me["domain"] == "ecommerce"

    def test_chat_with_an_invalid_token_is_401_not_anonymous(self, api):
        assert _chat(api, "hello", token="garbage").status_code == 401

    def test_chat_with_an_expired_token_is_401(self, api):
        t = create_token(Identity("CUST-E-001", "abc@gmail.com", "P", "ecommerce"), ttl_seconds=-1)
        assert _chat(api, "hello", token=t).status_code == 401

    def test_signed_in_chat_uses_the_token_end_to_end(self, api, login):
        r = _chat(api, "Show me my orders", token=login("ecommerce", "abc@gmail.com"))
        assert r.status_code == 200 and "ORD1001" in r.json()["reply"] and "ORD1002" not in r.json()["reply"]

    def test_anonymous_chat_gets_no_account_data(self, api):
        assert "AUTH_REQUIRED" in _chat(api, "Show me my orders").json()["reply"]

    def test_streaming_chat_also_enforces_the_token(self, api, login):
        assert api.post("/chat/stream", json={"message": "hi"}, headers=auth("garbage")).status_code == 401
        r = api.post("/chat/stream", json={"message": "Show me my orders"}, headers=auth(login("ecommerce", "rahul@gmail.com")))
        assert "ORD1002" in r.text and "ORD1001" not in r.text


class TestSessionsAreBoundToTheirOwner:
    def test_another_customer_cannot_join_a_session(self, api, login):
        abc = login("ecommerce", "abc@gmail.com")
        rahul = login("ecommerce", "rahul@gmail.com")
        first = _chat(api, "Show me my orders", token=abc).json()
        stolen = _chat(api, "Show me my orders", token=rahul, session_id=first["session_id"]).json()
        assert stolen["session_id"] != first["session_id"]            # got a fresh session, not abc's
        assert "ORD1002" in stolen["reply"] and "ORD1001" not in stolen["reply"]

    def test_anonymous_caller_cannot_join_a_signed_in_session(self, api, login):
        first = _chat(api, "Show me my orders", token=login("ecommerce", "abc@gmail.com")).json()
        anon = _chat(api, "What did I just ask?", session_id=first["session_id"]).json()
        assert anon["session_id"] != first["session_id"]
        assert "ORD1001" not in anon["reply"]

    def test_owner_keeps_their_session(self, api, login):
        t = login("ecommerce", "abc@gmail.com")
        first = _chat(api, "Show me my orders", token=t).json()
        again = _chat(api, "Show me my orders", token=t, session_id=first["session_id"]).json()
        assert again["session_id"] == first["session_id"]

    def test_the_original_session_is_untouched_by_the_intruder(self, api, login):
        from api.main import SESSIONS

        abc = login("ecommerce", "abc@gmail.com")
        first = _chat(api, "Show me my orders", token=abc).json()
        n = len(SESSIONS[first["session_id"]].conversation_history)
        _chat(api, "hi", token=login("ecommerce", "rahul@gmail.com"), session_id=first["session_id"])
        assert len(SESSIONS[first["session_id"]].conversation_history) == n


# =========================================================================== greetings are personal
class TestGreeting:
    @pytest.mark.parametrize("text", ["hi", "Hi!", "hello", "Hey there", "good morning", "HELLO!!"])
    def test_signed_in_customer_is_greeted_by_first_name(self, make_agent, text):
        result = make_agent("abc@gmail.com").chat(text)
        assert result["reply"].startswith("Hi Priya!") and result["tool_calls"] == []
        assert "Nair" not in result["reply"] and "abc@gmail.com" not in result["reply"]

    def test_greeting_matches_the_account_type(self, make_agent):
        assert "orders" in make_agent("abc@gmail.com").chat("hi")["reply"]
        assert "policies" in make_agent("neha@gmail.com", domain="insurance").chat("hi")["reply"]

    def test_anonymous_greeting_has_no_name(self, make_agent):
        reply = make_agent().chat("hi")["reply"]
        assert reply.startswith("Hi! I'm Intellia") and "Priya" not in reply

    def test_greeting_is_recorded_and_does_not_break_the_next_turn(self, make_agent):
        agent = make_agent("abc@gmail.com")
        agent.chat("hi")
        assert len(agent.conversation_history) == 2
        assert "ORD1001" in agent.chat("Show me my orders")["reply"]

    def test_real_questions_that_start_with_hi_still_go_to_the_agent(self, make_agent):
        result = make_agent("abc@gmail.com").chat("hi, show me my orders")
        assert [tc["tool"] for tc in result["tool_calls"]] == ["get_my_orders"]

    def test_greeting_works_over_the_stream_too(self, api, login):
        r = api.post("/chat/stream", json={"message": "hi"}, headers=auth(login("ecommerce", "rahul@gmail.com")))
        assert "Hi Rahul!" in r.text and "event: done" in r.text


# =========================================================================== insurance is a real domain now
class TestInsuranceDomainIsReal:
    def test_the_wip_stub_is_gone(self):
        from agent import fulfillment_client as fc
        from fulfillment_api import operations as ops

        assert not hasattr(fc, "insurance_status_wip") and not hasattr(ops, "insurance_status_wip")
        assert {t.name for t in fc.INSURANCE_TOOLS} == {
            "get_my_policies", "get_policy_details", "get_my_claims", "get_claim_status", "file_claim"}

    def test_system_prompt_no_longer_says_insurance_is_unavailable(self):
        from agent.system_prompt_config import get_system_prompt

        for identity in (None, Identity("CUST-I-001", "neha@gmail.com", "Neha Kapoor", "insurance")):
            prompt = get_system_prompt("insurance", True, identity).lower()
            assert "no policy/claim lookup" not in prompt and "none yet" not in prompt and "not available" not in prompt
            assert "get_policy_details" in prompt and "file_claim" in prompt

    def test_the_old_flag_is_removed(self):
        import agent.contact_center_agent as cca

        assert not hasattr(cca, "INSURANCE_AVAILABLE")

    def test_file_a_claim_through_the_agent(self, make_agent):
        agent = make_agent("akhil@gmail.com", domain="insurance")
        result = agent.chat("File a claim on POL2003 for accidental damage, amount 5000")
        assert [tc["tool"] for tc in result["tool_calls"]] == ["file_claim"]
        assert "has been filed" in result["reply"].lower()

    def test_claim_filed_through_the_agent_is_visible_only_to_its_owner(self, make_agent):
        akhil = make_agent("akhil@gmail.com", domain="insurance")
        akhil.chat("File a claim on POL2003 for accidental damage, amount 5000")
        assert "CLM3004" in akhil.chat("Show me my claims")["reply"]
        assert "CLM3004" not in make_agent("neha@gmail.com", domain="insurance").chat("Show me my claims")["reply"]

    def test_general_insurance_question_is_answered_from_the_knowledge_base(self, make_agent, knowledge_ready):
        result = make_agent("neha@gmail.com", domain="insurance").chat("What is the premium grace period?")
        assert any(tc["tool"] == "search_comprehensive_knowledge" for tc in result["tool_calls"])
        assert "insurance_premiums_and_renewals.md" in result["reply"]
