/**
 * Thin client for the FastAPI /chat endpoint (see app/main.py).
 * Same-origin relative paths work both in dev (via the Vite proxy in
 * vite.config.js) and in production (FastAPI serves the built app itself).
 */
const SESSION_STORAGE_KEY = 'dw_session_id'

export function getStoredSessionId() {
  try {
    return sessionStorage.getItem(SESSION_STORAGE_KEY)
  } catch {
    return null
  }
}

export function storeSessionId(id) {
  try {
    sessionStorage.setItem(SESSION_STORAGE_KEY, id)
  } catch {
    /* sessionStorage unavailable (e.g. private mode) -- non-fatal */
  }
}

export function clearStoredSessionId() {
  try {
    sessionStorage.removeItem(SESSION_STORAGE_KEY)
  } catch {
    /* ignore */
  }
}

const MESSAGES_STORAGE_KEY = 'dw_messages'

/** @returns {Array} stored messages, or [] if none are stored or they are unreadable */
export function getStoredMessages() {
  try {
    const raw = sessionStorage.getItem(MESSAGES_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (m) =>
        m &&
        typeof m.id === 'string' &&
        (m.role === 'user' || m.role === 'bot') &&
        typeof m.text === 'string'
    )
  } catch {
    return []
  }
}

export function storeMessages(messages) {
  try {
    sessionStorage.setItem(MESSAGES_STORAGE_KEY, JSON.stringify(messages))
  } catch {
    /* storage unavailable or full -- non-fatal, the chat just won't survive a reload */
  }
}

export function clearStoredMessages() {
  try {
    sessionStorage.removeItem(MESSAGES_STORAGE_KEY)
  } catch {
    /* ignore */
  }
}

/**
 * @param {string} message
 * @param {string | null} sessionId
 * @returns {Promise<{ session_id: string, reply: string, domain: string, tool_calls: Array }>}
 */
export async function sendChatMessage(message, sessionId) {
  const res = await fetch('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId || undefined }),
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Chat request failed (${res.status}): ${text || res.statusText}`)
  }

  return res.json()
}

/**
 * Streaming variant of sendChatMessage (POST /chat/stream, server-sent events).
 * onToken(text) fires for each piece of model text as it arrives; the promise
 * resolves with the same payload /chat returns. Falls back to the plain /chat
 * call if the backend has no streaming endpoint.
 */
export async function streamChatMessage(message, sessionId, onToken) {
  const res = await fetch('/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId || undefined }),
  })
  if (res.status === 404 || res.status === 405) return sendChatMessage(message, sessionId)
  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => '')
    throw new Error(`Chat request failed (${res.status}): ${text || res.statusText}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let result = null

  const handleFrame = (frame) => {
    let event = 'message'
    let data = ''
    for (const line of frame.split('\n')) {
      if (line.startsWith('event: ')) event = line.slice(7)
      else if (line.startsWith('data: ')) data += line.slice(6)
    }
    if (!data) return
    const payload = JSON.parse(data)
    if (event === 'token') onToken?.(payload.text)
    else if (event === 'done') result = payload
    else if (event === 'error') throw new Error(payload.detail || 'Stream failed')
  }

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      handleFrame(buffer.slice(0, idx))
      buffer = buffer.slice(idx + 2)
    }
  }
  if (buffer.trim()) handleFrame(buffer)
  if (!result) throw new Error('Stream ended before the reply was complete')
  return result
}

export async function checkHealth() {
  const res = await fetch('/health')
  if (!res.ok) throw new Error('Backend unhealthy')
  return res.json()
}
