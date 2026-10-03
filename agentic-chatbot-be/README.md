# Agentic Chatbot Backend -- Mid-sem Build (~60%)

Backend for *An Agentic AI-Based Enterprise Digital Workforce for Intelligent
Customer Support in Modern Contact Centers* (M.Tech dissertation, BITS
Pilani WILP, SEZG628T). This is a **pure API service** -- it serves no
frontend of any kind. The chatbot-ui repo is a fully independent project
that consumes this backend over HTTP only.

This repo is the mid-semester milestone: e-commerce support is functional
end to end (~60% of the full scope), and insurance is an **honest WIP
stub** -- domain routing correctly recognizes an insurance question and
tells the customer that policy/claim support isn't built yet, rather than
guessing at an answer.

---

## 1. Two processes, one system

```
+-------------------------+        HTTP         +----------------------------+
|   api.main:app  (:8000) | -------------------> | fulfillment_api.server:app |
|   the LangGraph agent   |  agent/fulfillment_   |   (:8010)                  |
|                          |  client.py            |  orders / products /       |
|  + offline knowledge     |                      |  insurance (WIP stub only) |
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
- **`domain == "insurance"`** -> only a single stub tool,
  `insurance_status_wip`, gets bound. The agent calls it and passes its
  honest "under development" message straight through, rather than
  inventing a policy number or claim status.

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
   prompt (`agent/system_prompt_config.py`) is built with
   `insurance_available=False` baked in, and the LLM
   (`agent/llm_provider.py`'s `get_llm()` -- Gemini/OpenAI/Anthropic, or
   the zero-key `MockChatModel`) is invoked with tools bound.
5. **`should_continue`**: tool calls -> `tools` node; otherwise -> `END`.
6. **`tools` node**: each tool call is dispatched from the pre-built
   `self.available_tools` dict. Fulfillment/insurance-stub tools call out
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
`search_products`, `get_product_details`) plus `insurance_status_wip()`.
`fulfillment_api/server.py` is a plain REST/FastAPI server exposing all of
these.

Mock data (`fulfillment_api/mock_data.py`) has 5 products and 3 orders
(`ORD1001`-`ORD1003`), rebuilt fresh by `initialize_mock_data()` before
every test (`tests/conftest.py`'s `reset_mock_data` fixture).

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
|   |-- system_prompt_config.py   # get_system_prompt(domain, ..., insurance_available=False)
|   |-- llm_provider.py           # get_llm(), MockChatModel
|   |-- fulfillment_client.py     # HTTP client + @tool wrappers -> :8010
|   |-- knowledge_search.py       # ChromaBackend (offline only)
|   |-- knowledge_tools.py        # @tool search_faq_articles / search_comprehensive_knowledge
|   `-- offline_embeddings.py     # HashedBagOfWordsEmbedding
|-- fulfillment_api/
|   |-- models.py                 # Order/Product (no Policy/Claim yet)
|   |-- mock_data.py              # in-memory dataset
|   |-- operations.py             # e-commerce ops + insurance_status_wip()
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

39 tests, all offline (mock LLM, offline Chroma, in-process FastAPI
`TestClient` for the fulfillment API -- no real network, no real API
keys):

- **`test_fulfillment_operations.py`** -- every e-commerce business-logic
  function, plus a check that `insurance_status_wip()` is honest about
  being unimplemented rather than silent or misleading.
- **`test_fulfillment_api_server.py`** -- the REST routes via FastAPI's
  in-process `TestClient`.
- **`test_domain_router.py`** -- `classify_domain()`'s keyword scoring and
  fallback-to-previous-domain behavior.
- **`test_knowledge_search.py`** -- offline Chroma indexing and retrieval.
- **`test_agent_pipeline.py`** -- full `CallCenterAgent.chat()` runs:
  order lookup/tracking/cancellation, mid-conversation domain switching,
  RAG-grounded answers, graceful degradation with no fulfillment API, and
  an insurance question correctly routing to the domain and calling the
  honest WIP stub tool instead of fabricating policy data.

## 10. What's WIP

- Real insurance data model and operations (`Policy`/`Claim`, policy/claim
  lookup tools) -- this build has only the honest `insurance_status_wip`
  stub.
- Pinecone production vector store (this build is offline-Chroma-only).
- FastMCP transport for the Fulfillment API (this build is REST-only).
- Voice channel -- Deepgram Nova-3 (STT) / Aura-2 (TTS).
- Tavily web search tool.
- LangSmith tracing configuration.

## 11. Security note

Do not commit a real `.env` with live API keys. `.env.example` ships with
every value empty -- copy it to `.env` and fill in only what you need.
