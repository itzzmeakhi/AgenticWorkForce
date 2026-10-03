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

export async function checkHealth() {
  const res = await fetch('/health')
  if (!res.ok) throw new Error('Backend unhealthy')
  return res.json()
}
