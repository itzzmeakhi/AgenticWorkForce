# Intellia Chat UI

The web front end for the *Agentic AI Enterprise Digital Workforce* project. It
is written in React 19 with plain JavaScript, Vite and SCSS (no TypeScript).
It talks to the backend in `agentic-chatbot-be`.

Needs Node.js 20 or newer. Vite is pinned to 6.x so it runs on Node 22.5.

## Run it

Start the backend first (see its README), then:

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # production build into dist/
```

In development, Vite forwards `/chat`, `/health`, `/admin`, `/voice` and
`/auth` to the Agent API on `http://localhost:8000`, so there is nothing to
configure.

## What you can do

- **Chat** with Intellia. Replies appear as they are written (streaming). If
  streaming is not available, it falls back to a normal reply.
- **Sign in** as an e-commerce or an insurance customer. The sign-in is real:
  the backend checks the password and gives back a token that the UI sends with
  every message.
- **Ask about your own data** once signed in: orders and tracking for
  e-commerce accounts; policies and claims for insurance accounts. Cancelling an
  order and filing a claim ask you to confirm first.
- **Ask general questions** without signing in: products, refunds, shipping,
  claims process, coverage, premiums, and web look-ups.
- **Use your voice.** The mic button records you and stops by itself when you
  go quiet. The speaker button reads replies aloud. Voice only shows up when the
  backend has a Deepgram key.
- **See what the bot did.** A small trace under each reply shows which tools
  and domain were used.
- **Get suggestions that fit you.** The suggestion chips and the "what can I
  do" panel show everything when signed out, and only the matching features for
  your account when signed in.

Demo accounts (password `demo1234`): e-commerce `abc@gmail.com`,
`rahul@gmail.com`, `akhil@gmail.com`; insurance `neha@gmail.com`,
`vikram@gmail.com`, `akhil@gmail.com`.

## How sign-in works

There are two routes: `/` (the chat) and `/login`.

- If someone asks about their own account while signed out, the chat does not
  send the question. It shows a "Sign in to continue" button on that message and
  opens `/login` in a new tab, so the chat is not interrupted.
- After a successful sign-in the login tab shows a success screen with a
  3-second countdown, then closes itself (or goes to `/` if it was not opened
  from the chat).
- The chat tab hears about the sign-in, saves it, and sends the waiting question
  again. A personal greeting uses your first name.
- "Sign out" clears the session and the chat.
- If the backend says the token is no longer valid (401), the UI signs you out
  and asks you to sign in again.

The session is kept in each tab's `sessionStorage`.

## Where things are

```
src/
|-- api/            chatApi.js (chat, streaming, token header), authApi.js (login),
|                   voiceApi.js (status, transcribe, speak)
|-- auth/           authStorage.js (saved session)
|-- context/        AuthContext.jsx (who is signed in)
|-- pages/          ChatPage/ (the chat), LoginPage/ (sign-in + success screen)
|-- components/     Header, ChatWindow, ChatInput, MessageBubble, ToolTrace,
|                   DomainBadge, TypingIndicator, CapabilitiesPanel
|-- utils/          capabilities.js (chips and panel contents),
|                   authGate.js (does a question need sign-in?),
|                   useRecorder.js (mic + silence detection),
|                   speechQueue.js, sentences.js (speak replies sentence by sentence),
|                   renderMarkdownLite.jsx
`-- styles/         global.scss, _tokens.scss, _mixins.scss
```

Each component has its own folder with one `.jsx` and one `.scss` file, and
files are imported directly (no index files). Only truly global styles (reset,
theme colours, design tokens, mixins) live in `src/styles/`. There is no CSS
framework.

## Changing what the chips and panel show

Edit `src/utils/capabilities.js`. It is the single list used by both the
suggestion chips and the capabilities panel, and each item says which account
type it belongs to. Only list features the backend really has.
