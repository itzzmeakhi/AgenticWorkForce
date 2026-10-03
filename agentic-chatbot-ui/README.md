# chatbot-ui (React + JavaScript + Vite + SCSS + React Router)

React chat frontend (plain JavaScript/JSX — no TypeScript) for the Agentic AI Enterprise Digital
Workforce backend.

Requires **Node.js >= 20** (tested against Node v22.5.1 / npm 10). Pinned to Vite 6.x and
@vitejs/plugin-react 4.x specifically because Vite 7/8 require Node >=22.12, which is newer than
v22.5.1 — this UI is built to run as-is on that version, no Node upgrade needed.

This folder is UI-only: it expects a backend exposing `POST /chat` and `GET /health` at the same
origin — in dev, the Vite proxy below forwards `/chat`, `/health`, and `/admin` to
`http://localhost:8000`; in production, whatever serves the built `dist/` should also serve those
routes, **plus a catch-all fallback to `index.html`** for client-side routes like `/login` (see
"React Router + the sign-in flow" below, and `app/main.py`'s `serve_frontend_routes` in the full
project, which already does this).

Quick reference:

```bash
npm install
npm run dev     # dev server on :5173, proxies API calls to FastAPI on :8000
# or
npm run build   # compiles SCSS, outputs dist/, served directly by FastAPI at "/"
```

## The chat works signed out

Intellia answers general e-commerce and insurance questions (refund policy, shipping, claims process,
product search, …) with no sign-in required — every message just goes to `POST /chat` as before.

## React Router + the sign-in flow

Two routes, via `react-router-dom`'s `<BrowserRouter>` (set up once in `src/main.jsx`):

- `/` — `src/pages/ChatPage/ChatPage.jsx`, the chat itself
- `/login` — `src/pages/LoginPage/LoginPage.jsx`, the sign-in screen

**A question that needs the asker's own account data** — a specific order/policy/claim id (e.g.
"status of ORD1001"), or a phrase like "my order" / "my policy" — is detected client-side
(`src/utils/authGate.js`) *before* it's sent to the backend. If no one is signed in yet, ChatPage
doesn't send it; instead it shows a "Sign in to continue" button on that message
(`MessageBubble`'s `authPrompt`) and opens `/login` **in a new browser tab**
(`window.open(...)`, deliberately without `noopener` so the two tabs can talk to each other) —
the chat tab is never navigated away or interrupted. The pending question and any detected id
travel along as query params (`?returnId=ORD1001&domain=ecommerce&pending=...`).

On a successful sign-in, the login tab:

1. saves the session to **its own `sessionStorage`** (`src/auth/authStorage.js`)
2. posts the result back to the tab that opened it via `window.opener.postMessage(...)`
3. shows a "you can close this tab" confirmation (or, if it wasn't opened from another tab — e.g.
   someone bookmarked `/login` — redirects to `/` in the same tab instead)

The original chat tab listens for that `message` event, saves the same session to **its own**
`sessionStorage` too, and automatically resends the pending question — now with the signed-in
customer/policy id folded in if the question didn't already name one — so the answer appears right
back in the conversation. "Sign out" (header) clears the session and the app goes back to working
signed-out/general.

## Fake authentication API

`src/api/authApi.js`'s `fakeAuthenticate(customerId, password, accountType)` is a single function
that authenticates a user for **either** domain — not two separate e-commerce/insurance APIs. It's
shaped like a real API call (`async`, simulated network latency, can reject with an `Error`) so a
real backend endpoint is a drop-in swap later; nothing else in the app needs to know the
difference. There's no real backend behind it: a handful of ids matching the seeded mock data
(`ORD1001`–`ORD1004`, `POL2001`/`POL2002`, password `demo1234`) validate against a real name and
account type, and any other id/password combo is accepted too (4+ character password) since this
is a prototype, not an identity system.

`src/context/AuthContext.jsx` holds the signed-in user for the current tab (backed by that tab's
`sessionStorage`) and is what `Header`, `ChatPage`, and `LoginPage` read/write through `useAuth()`.
**Adding real authentication**: swap `fakeAuthenticate` for a real `fetch('/auth/login', ...)`,
have `AuthContext` store a real token, and attach it as an `Authorization` header in
`src/api/chatApi.js` — the rest of the app only depends on the shape of the user/session objects
those two files pass around.

## Plain JavaScript — no TypeScript

Everything is `.jsx`/`.js`; there's no `tsconfig.json`, no `.ts`/`.tsx` file, and no `typescript`
dependency. A few files carry lightweight `/** @param {...} */` JSDoc comments on function
signatures purely as inline documentation for editors — they're comments only, not a build step,
and nothing here requires a type checker to run.

## One folder per component, with its own SCSS colocated

Every component and page lives in its own folder containing exactly its `.jsx` file and its
`.scss` file. There's no `index.js` barrel -- every import names the file directly (e.g. `import
Header from '../components/Header/Header'`), so there's exactly one file to open when you go
looking for either half of a component:

```
src/components/Header/
  Header.jsx
  Header.scss
```

Each component's `.scss` only defines the classes *that component* renders (e.g. `Header.scss`
owns `.app-header`, `.header-title`, `.user-badge`, …; `MessageBubble.scss` owns `.bubble`,
`.message-row`, `.auth-prompt-btn`). Nothing aggregates them into one entry stylesheet — Vite
bundles whatever `.scss` files get `import`ed by the `.jsx` files that are actually rendered, in
import order. `src/styles/` holds only what's genuinely global and can't be scoped to one
component:

- `src/styles/_tokens.scss` — compile-time design tokens (Sass variables: spacing, radii, font
  sizes, breakpoints, the chat's max-width)
- `src/styles/_mixins.scss` — reusable style mixins (`outline-chip`, `field-input`,
  `primary-button`, `dot`, `custom-scrollbar`, …) that component stylesheets `@use`
- `src/styles/global.scss` — the CSS reset and the `:root` CSS custom properties for theme colors
  (kept as *CSS* custom properties, not Sass variables, because `DomainBadge` and
  `CapabilitiesPanel` set one per-item at runtime via inline `style={{ '--badge-color': ... }}`);
  imported exactly once, from `src/main.jsx`

There is no CSS framework or component-styling package anywhere in this app (no Bootstrap,
Tailwind, MUI, styled-components, CSS Modules, etc.) — every class name is a plain global class,
same as before this restructure, just organized by component now instead of by UI area.

## Structure

- `src/context/AuthContext.jsx` + `src/auth/authStorage.js` — signed-in user state, per-tab (no
  scss of their own, so they stay flat rather than folder-per-file)
- `src/api/authApi.js` — the fake authenticate call described above
- `src/api/chatApi.js` — fetch client for `/chat` and `/health`
- `src/utils/authGate.js` — detects whether a chat question needs sign-in
- `src/pages/ChatPage/` — the chat screen (`/`): messages, session id, backend health, the
  sign-in-gate + postMessage handshake described above
- `src/pages/LoginPage/` — the sign-in screen (`/login`)
- `src/App.jsx` — the two `<Route>`s
- `src/components/Header/`, `ChatWindow/`, `ChatInput/`, `MessageBubble/` (renders the sign-in
  prompt button), `ToolTrace/`, `DomainBadge/`, `TypingIndicator/`, `CapabilitiesPanel/` — one
  folder per component, each with its `.jsx` and its `.scss` (imported directly, no barrel)
- `src/styles/` — the three global files described above
