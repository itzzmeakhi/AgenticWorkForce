# Agentic Chatbot Backend

Backend for *An Agentic AI-Based Enterprise Digital Workforce for Intelligent
Customer Support in Modern Contact Centers* (M.Tech dissertation, BITS Pilani
WILP).

It is an API only. It has no web pages of its own. The `agentic-chatbot-ui`
project talks to it over HTTP.

---

## 1. What it can do

**E-commerce customers (signed in) can:**

- see their orders and check an order's status
- track a package
- cancel an order (the bot asks "are you sure?" first)

**Insurance customers (signed in) can:**

- see their policies and the details of one policy
- see their claims and check a claim's status
- file a new claim (the bot asks "are you sure?" first)

**Anyone, even without signing in, can:**

- search products and see product details
- ask general questions (refunds, shipping, claims process, coverage, premiums).
  Answers come from our own knowledge documents (RAG).
- ask things that are not in our documents, such as "what is a deductible?" or
  today's news. The bot can search the web (Tavily) for this. It never uses the
  web for account data.

**Other features:**

- **Two separate sign-ins.** E-commerce and insurance each have their own
  customers and their own dummy data.
- **Domain switching.** The bot works out whether you are asking about
  shopping or insurance and uses the right tools.
- **Personal greetings.** Say "hi" after signing in and it replies with your
  first name, instantly.
- **Streaming replies.** Text appears as it is written (`/chat/stream`).
- **Voice.** Speech-to-text and text-to-speech through Deepgram. Order, policy
  and claim IDs are spelled out so they are spoken clearly.
- **Choice of AI model.** Gemini, OpenAI, Anthropic, or a built-in mock model
  that needs no key.

---

## 2. How the pieces fit

```
 Browser / UI
      |
      v
+-------------------+   HTTP    +-------------------------+
| Agent API  :8000  | --------> | Fulfillment API  :8010  |
| (LangGraph agent) |           | orders, products,       |
| + knowledge base  |           | policies, claims,       |
| + web search      |           | sign-in (mock data)     |
| + voice           |           +-------------------------+
+-------------------+
```

- **Agent API** (`api/main.py`, port 8000) is what the UI calls. It runs the
  AI agent.
- **Fulfillment API** (`fulfillment_api/server.py`, port 8010) is a stand-in
  for a company's real order and insurance systems. It holds the dummy data and
  checks who is signed in.

The agent never reads the dummy data directly. It always calls the Fulfillment
API (`FULFILLMENT_API_URL`, default `http://localhost:8010`). If that service is
down, the bot says so politely instead of crashing.

---

## 3. What happens when you send a message

1. `api/main.py` finds your chat session (or makes a new one).
2. If the message is just a greeting, the agent replies at once with your name.
3. Otherwise a LangGraph flow runs:
   **pick the topic** (e-commerce, insurance or general) -> **agent** (the AI
   decides what to do) -> **tools** (look up data, search documents, search the
   web) -> back to the **agent**, which writes the final reply.
4. The reply goes back to the UI, along with which tools were used.

Main files:

| File | Job |
|---|---|
| `agent/contact_center_agent.py` | The agent and its LangGraph flow |
| `agent/domain_router.py` | Decides e-commerce, insurance or general |
| `agent/system_prompt_config.py` | The bot's instructions and rules |
| `agent/llm_provider.py` | Chooses the AI model (or the mock) |
| `agent/fulfillment_client.py` | Tools that call the Fulfillment API |
| `agent/knowledge_tools.py`, `knowledge_search.py` | Search our documents |
| `agent/web_search_tool.py` | Web search with Tavily |

---

## 4. Signing in and staying safe

- You sign in with `POST /auth/login` (`domain`, `email`, `password`). The
  domain decides which customer list is checked.
- You get a signed token (JWT). It lasts `JWT_TTL_MINUTES` (default 240).
- The agent passes your token to the Fulfillment API on every tool call. The
  AI model never chooses an email or customer ID itself.
- You only ever see your own orders, policies and claims. Someone else's record
  looks like "not found". A token from one domain is refused (403) on the other.
- Each chat session belongs to the person who started it. Another person using
  the same session id gets a new session.
- Cancelling an order and filing a claim need a clear "yes" in your very next
  message. This is checked in code, not just in the bot's instructions.
- 5 wrong passwords lock that account for 60 seconds.
- Passwords are stored hashed.

**Demo accounts** (password for all: `demo1234`)

| Domain | Email | Name |
|---|---|---|
| E-commerce | `abc@gmail.com` | Priya Nair |
| E-commerce | `rahul@gmail.com` | Rahul Verma |
| E-commerce | `akhil@gmail.com` | Akhil Reddy |
| Insurance | `neha@gmail.com` | Neha Kapoor |
| Insurance | `vikram@gmail.com` | Vikram Singh |
| Insurance | `akhil@gmail.com` | Akhil Reddy |

The e-commerce and insurance `akhil@gmail.com` accounts are separate.

---

## 5. Dummy data

- **E-commerce:** 5 products and orders `ORD1001` to `ORD1006`.
- **Insurance:** policies `POL2001` to `POL2005` (health, motor, home) and
  claims `CLM3001` to `CLM3003`. New claims start at `CLM3004`.
- The data lives in memory. It resets whenever the Fulfillment API restarts.
- "Today" in the dummy data is fixed at 2026-09-13.

---

## 6. Knowledge documents (RAG)

Six short guides live in `data/knowledge_base/`:

- `ecommerce_refund_policy.md`, `ecommerce_shipping_policy.md`
- `insurance_claims_process.md`, `insurance_coverage_and_exclusions.md`,
  `insurance_premiums_and_renewals.md`
- `general_contact_center_faq.md`

They are split by `##` headings, stored in a local ChromaDB, and searched when
a question needs them. A file name starting with `ecommerce_` or `insurance_`
tells the bot which domain it belongs to. No API key or model download is
needed for this. After editing a guide, call `POST /admin/reindex`.

---

## 7. Voice

Voice needs `DEEPGRAM_API_KEY`. Without it, voice is switched off and the rest
of the app still works.

- `GET /voice/status` tells the UI whether voice is available.
- `POST /voice/transcribe` turns recorded speech into text (Deepgram Nova-3).
- `POST /voice/speak` turns a reply into audio (Deepgram Aura voices). Replies
  are cleaned of symbols and shortened for speaking, and repeated audio is
  cached.

---

## 8. AI model choice

Set `LLM_PROVIDER` in `.env`.

| `LLM_PROVIDER` | Needs | Model setting |
|---|---|---|
| `gemini` | `GOOGLE_API_KEY` | `GEMINI_MODEL` |
| `openai` | `OPENAI_API_KEY` | `OPENAI_MODEL` |
| `anthropic` | `ANTHROPIC_API_KEY` | `ANTHROPIC_MODEL` |
| `mock` (default) | nothing | A simple keyword-based model for demos and tests |

---

## 9. API list

**Agent API (:8000)**

| Route | Purpose |
|---|---|
| `GET /health` | Is it running? |
| `POST /auth/login` | Sign in (passes through to the Fulfillment API) |
| `GET /auth/me` | Who am I? |
| `POST /chat` | Send a message, get the full reply |
| `POST /chat/stream` | Send a message, get the reply as it is written |
| `POST /admin/reindex` | Rebuild the knowledge index |
| `GET /voice/status`, `POST /voice/transcribe`, `POST /voice/speak` | Voice |

**Fulfillment API (:8010)**

| Route | Purpose |
|---|---|
| `POST /auth/login`, `GET /health` | Sign in, health check |
| `GET /orders`, `/orders/{id}`, `/orders/{id}/track`, `POST /orders/{id}/cancel` | Orders (sign-in needed) |
| `GET /products`, `/products/{sku}` | Products (open to everyone) |
| `GET /insurance/policies`, `/insurance/policies/{id}` | Policies (sign-in needed) |
| `GET /insurance/claims`, `/insurance/claims/{id}`, `POST /insurance/claims` | Claims (sign-in needed) |

---

## 10. Folder layout

```
agentic-chatbot-be/
|-- agent/              # the agent, tools, prompts, model choice
|-- api/                # Agent API (main.py) and its request/response models
|-- fulfillment_api/    # mock company systems, customers and dummy data
|-- security/           # password hashing and tokens
|-- voice/              # Deepgram speech-to-text and text-to-speech
|-- ingestion/          # builds the knowledge index
|-- data/knowledge_base/  # the six guides
|-- tests/              # automatic tests
|-- config.py, requirements.txt, .env.example, run_all.sh
```

---

## 11. Running it

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # then fill in what you need (see below)

./run_all.sh             # starts both services, Ctrl+C stops both
```

Or start them yourself in two terminals:

```bash
uvicorn fulfillment_api.server:app --port 8010
uvicorn api.main:app --reload --port 8000
```

**Settings in `.env`** (all optional unless noted)

| Name | What it is for |
|---|---|
| `LLM_PROVIDER` | `mock`, `gemini`, `openai` or `anthropic` |
| `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` | Key for the model you picked |
| `JWT_SECRET` | Secret used to sign tokens. Set your own value. Both services must use the same one. |
| `JWT_TTL_MINUTES` | How long a sign-in lasts (default 240) |
| `DEEPGRAM_API_KEY` | Turns on voice |
| `TAVILY_API_KEY` | Turns on web search |
| `FULFILLMENT_API_URL` | Where the Fulfillment API is (default `http://localhost:8010`) |

Quick try:

```bash
curl localhost:8000/health

# sign in, then ask about your orders
TOKEN=$(curl -s -X POST localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"domain":"ecommerce","email":"rahul@gmail.com","password":"demo1234"}' \
  | python -c 'import sys,json; print(json.load(sys.stdin)["token"])')

curl -X POST localhost:8000/chat -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" -d '{"message": "show my orders"}'
```

---

## 12. Tests

```bash
python -m pytest tests -q
```

The tests are all offline: they use the mock model, a local index, and an
in-process copy of the Fulfillment API. No keys or internet are needed. They
cover the business logic, the REST routes, topic routing, document search,
the full agent flow, sign-in and access rules, confirmations, streaming, voice
and web search.

---

## 13. Known limits

- The voice routes do not need a sign-in, so anyone who can reach the server
  can use your Deepgram credit.
- CORS allows every origin. Restrict it before any real deployment.
- Chat sessions stay in memory until the server restarts.
- Dummy data resets on restart.
- Do not commit a real `.env`. `.env.example` has every value empty.
