# Agentic Chatbot Backend -- Mid-sem Build (~60%)

Backend for *An Agentic AI-Based Enterprise Digital Workforce for Intelligent
Customer Support in Modern Contact Centers* (M.Tech dissertation, BITS
Pilani WILP, SEZG628T). This is a **pure API service** -- it serves no
frontend of any kind. The chatbot-ui repo is a fully independent project
that consumes this backend over HTTP only.

This repo is the mid-semester milestone: e-commerce support is functional
end to end for both domains: e-commerce (orders, tracking, cancellation,
products) and insurance (policies, claims, filing a claim), each with its own
dummy data, sign-in and knowledge documents.

---

## 1. Two processes, one system

```
+-------------------------+        HTTP         +----------------------------+
|   api.main:app  (:8000) | -------------------> | fulfillment_api.server:app |
|   the LangGraph agent   |  agent/fulfillment_   |   (:8010)                  |
|                          |  client.py            |  orders / products /       |
|  + offline knowledge     |                      |  insurance policies/claims |
|    search                |                      |  (in-memory mock data)      |
+-------------------------+                       +----------------------------+
```

The agent process never imports the fulfillment layer's code directly --
it always calls out over HTTP (`FULFILLMENT_API_URL`, default
`http://localhost:8010`). If that service is down, tools degrade
gracefully (a clear message, not a crash).

## 2. Domain-fluid routing

`agent/domain_router.py`'s `classify_domain()` correctly tells an
e-commerce question from an insurance question and routes accordingly:

- **`domain == "ecommerce"`** -> the real order/product tools
  (`agent/fulfillment_client.py`'s `CUSTOMER_FACING_TOOLS` +
  `PRODUCT_TOOLS`) get bound, and the agent answers with real (mock)
  data.
- **`domain == "insurance"`** -> the real insurance tools
  (`INSURANCE_TOOLS`: `get_my_policies`, `get_policy_details`,
  `get_my_claims`, `get_claim_status`, `file_claim`) plus the knowledge base
  get bound, and the agent answers from the customer's own policy and claim
  data (mock, scoped to the signed-in customer).

See `agent/contact_center_agent.py`'s `_domain_tools()`.

## 3. Request flow, step by step

1. **`api/main.py`** looks up (or creates) a `CallCenterAgent` for the
   given `session_id`.
2. **`agent/contact_center_agent.py`**'s `.chat()` appends the new message
   to conversation history and invokes the compiled LangGraph app.
3. **`classify_domain` node** decides `ecommerce` / `insurance` / `general`
   for this turn (falling back to the previous turn's domain for
   ambiguous follow-ups).
4. **`agent` node**: `_domain_tools()` picks the tool list, the system
   prompt (`agent/system_prompt_config.py`) is built for the domain and the
   signed-in customer, and the LLM
   (`agent/llm_provider.py`'s `get_llm()` -- Gemini/OpenAI/Anthropic, or
   the zero-key `MockChatModel`) is invoked with tools bound.
5. **`should_continue`**: tool calls -> `tools` node; otherwise -> `END`.
6. **`tools` node**: each tool call is dispatched from the pre-built
   `self.available_tools` dict. Fulfillment (order and insurance) tools call out
   over HTTP to `fulfillment_api.server`; knowledge tools call
   `get_backend().retrieve()` against the offline Chroma index. Results
   become `ToolMessage`s tagged with their `tool_call_id`.
7. Back to **`agent` node** -- the LLM produces a final reply from the
   tool results.
8. `.chat()` pairs each `ToolMessage` back to its tool call **by
   `tool_call_id`** (not list position) and returns
   `{reply, domain, tool_calls}`.

## 4. Fulfillment API

`fulfillment_api/operations.py` holds the e-commerce business logic
(`get_order_status`, `get_my_orders`, `track_package`, `cancel_order`,
`search_products`, `get_product_details`) and the insurance logic
(`get_my_policies`, `get_policy_details`, `get_my_claims`,
`get_claim_status`, `file_claim`). `fulfillment_api/server.py` is a
REST/FastAPI server exposing all of these (orders under `/orders`, insurance
under `/insurance/...`, sign-in at `/auth/login`).

Mock data (`fulfillment_api/mock_data.py`) is two separate datasets:
e-commerce (5 products, orders `ORD1001`-`ORD1006`) and insurance (5 policies
`POL2001`-`POL2005` of type Health/Motor/Home, 3 claims `CLM3001`-`CLM3003`
in submitted/under-review/approved/rejected states). Both are rebuilt fresh
before every test (`tests/conftest.py`'s `reset_mock_data` fixture) by
`initialize_mock_data()` and `initialize_insurance_data()`. `Policy` and
`Claim` are defined in `fulfillment_api/models.py`.

`ShippingAddress` (in `fulfillment_api/models.py`) requires `address`,
`city`, `state`, `postal_code`, and `phone`. `Order` carries `carrier` and
`current_location` (both optional) -- `track_package()` in
`operations.py` reads these, so if you add or rename fields on either
model, update every `ShippingAddress(...)`/`Order(...)` call in
`mock_data.py` to match, or the server will fail at import time with a
Pydantic validation error.

## 5. Knowledge retrieval -- offline ChromaDB only

`agent/knowledge_search.py`'s `ChromaBackend` is the only backend in this
build: a local, persistent ChromaDB collection using
`agent/offline_embeddings.py`'s `HashedBagOfWordsEmbedding` (dependency-free,
no model download, no API key). `ingestion/local_index.py`'s
`build_local_index()` chunks `data/knowledge_base/*.md` by `## ` headers
and indexes them; reachable live via `POST /admin/reindex`.

`agent/knowledge_tools.py` wraps this with `search_faq_articles` and
`search_comprehensive_knowledge`.

## 6. LLM provider

| `LLM_PROVIDER` | Requires | Model |
|---|---|---|
| `gemini` | `GOOGLE_API_KEY` | `GEMINI_MODEL` (default `gemini-3.6-flash`) |
| `openai` | `OPENAI_API_KEY` | `OPENAI_MODEL` (default `gpt-4o-mini`) |
| `anthropic` | `ANTHROPIC_API_KEY` | `ANTHROPIC_MODEL` (default `claude-sonnet-4-5`) |
| `mock` (default) | nothing | `MockChatModel` -- deterministic keyword-based tool selection |

## 7. Directory layout

```
agentic-chatbot-be/
|-- agent/
|   |-- contact_center_agent.py   # CallCenterAgent, the LangGraph graph
|   |-- domain_router.py          # classify_domain()
|   |-- state.py                  # AgentState TypedDict
|   |-- system_prompt_config.py   # get_system_prompt(domain, fulfillment_available, identity)
|   |-- llm_provider.py           # get_llm(), MockChatModel
|   |-- fulfillment_client.py     # HTTP client + @tool wrappers -> :8010
|   |-- knowledge_search.py       # ChromaBackend (offline only)
|   |-- knowledge_tools.py        # @tool search_faq_articles / search_comprehensive_knowledge
|   `-- offline_embeddings.py     # HashedBagOfWordsEmbedding
|-- fulfillment_api/
|   |-- models.py                 # Order, Product, Policy, Claim
|   |-- mock_data.py              # in-memory dataset
|   |-- operations.py             # e-commerce + insurance operations (ownership-scoped)
|   `-- server.py                 # REST/FastAPI transport (:8010)
|-- ingestion/
|   `-- local_index.py            # offline Chroma indexing
|-- api/
|   |-- main.py                   # FastAPI app (:8000), no frontend serving
|   `-- schemas.py                # request/response Pydantic models
|-- data/
|   `-- knowledge_base/*.md       # e-commerce + general FAQ docs
|-- tests/                        # see section 9
|-- config.py                     # paths, env constants
|-- requirements.txt
|-- .env.example
`-- pytest.ini
```

## 8. Running it

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional -- everything below works with LLM_PROVIDER=mock

# Terminal 1
uvicorn fulfillment_api.server:app --port 8010

# Terminal 2
uvicorn api.main:app --reload --port 8000
```

```bash
curl localhost:8000/health
curl -X POST localhost:8000/chat -H 'Content-Type: application/json' \
     -d '{"message": "track order ORD1002"}'
curl -X POST localhost:8000/chat -H 'Content-Type: application/json' \
     -d '{"message": "whats my policy status"}'
```

## 9. Tests

```bash
python -m pytest tests/ -v
```

All tests are offline (mock LLM, offline Chroma, in-process FastAPI
`TestClient` for the fulfillment API -- no real network, no real API
keys):

- **`test_fulfillment_operations.py`** -- every e-commerce business-logic
  function and the insurance policy/claim operations (including filing a claim).
- **`test_fulfillment_api_server.py`** -- the REST routes via FastAPI's
  in-process `TestClient`.
- **`test_domain_router.py`** -- `classify_domain()`'s keyword scoring and
  fallback-to-previous-domain behavior.
- **`test_knowledge_search.py`** -- offline Chroma indexing and retrieval.
- **`test_agent_pipeline.py`** -- full `CallCenterAgent.chat()` runs:
  order lookup/tracking/cancellation, mid-conversation domain switching,
  RAG-grounded answers, graceful degradation with no fulfillment API, and
  insurance policy/claim lookups and filing a claim through the agent.

## 10. What's WIP

- Pinecone production vector store (this build is offline-Chroma-only).
- FastMCP transport for the Fulfillment API (this build is REST-only).
- LangSmith tracing configuration.

## 11. Authentication and access control

Sign-in is per domain. The Fulfillment API keeps a **separate customer store
for e-commerce and for insurance** (`fulfillment_api/customers.py`), with
separate dummy data (orders vs. policies/claims). The login screen's account
type decides which store the credentials are checked against.

- `POST /auth/login {domain, email, password}` (on the Agent API, proxied to the
  Fulfillment API) returns a signed JWT (HS256, `JWT_TTL_MINUTES`, default 4h).
  The token carries the customer id, email and **domain**.
- Both services verify the token with the same `JWT_SECRET` (set it in `.env`;
  a dev-only default is used with a warning otherwise).
- The agent forwards the signed-in customer's token on every tool call. Tools
  take no email/customer id from the model; the Fulfillment API reads the
  identity from the token, returns only that customer's records, answers
  "not found" for records that belong to someone else, and returns 403 when a
  token for one domain is used on the other domain's endpoints.
- Chat sessions are bound to their owner; a different (or anonymous) caller
  presenting someone else's session id gets a fresh session.
- Products, the knowledge base and general questions need no sign-in.
- 5 failed sign-ins on an account lock it for 60 seconds.

Dummy accounts (all use password `demo1234`): e-commerce `abc@gmail.com`,
`rahul@gmail.com`, `akhil@gmail.com`; insurance `neha@gmail.com`,
`vikram@gmail.com`, `akhil@gmail.com` (a separate account from the e-commerce
one). Tests: `tests/test_auth_access_control.py`.

## 12. Security note

Do not commit a real `.env` with live API keys. `.env.example` ships with
every value empty -- copy it to `.env` and fill in only what you need.
