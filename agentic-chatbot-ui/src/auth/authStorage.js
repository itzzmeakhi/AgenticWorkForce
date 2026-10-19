/**
 * Keeps the signed-in session ({ token, user }) in this tab's sessionStorage
 * so a page refresh does not sign the customer out. sessionStorage is per
 * tab and cleared when the tab closes, and the token expires on the server
 * (see JWT_TTL_MINUTES), so a stored session is never trusted by itself:
 * every request is checked by the backend.
 */
const AUTH_STORAGE_KEY = 'dw_auth_session'

/** @returns {{ token: string, user: { name: string, email: string, customerId: string, accountType: string } } | null} */
export function getStoredSession() {
  try {
    const raw = sessionStorage.getItem(AUTH_STORAGE_KEY)
    if (!raw) return null
    const s = JSON.parse(raw)
    if (!s || typeof s.token !== 'string' || !s.user || typeof s.user.name !== 'string' || typeof s.user.accountType !== 'string') {
      return null
    }
    return s
  } catch {
    return null
  }
}

export function getStoredToken() {
  return getStoredSession()?.token ?? null
}

export function storeSession(session) {
  try {
    sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session))
  } catch {
    /* sessionStorage unavailable (e.g. private mode) -- non-fatal */
  }
}

export function clearStoredSession() {
  try {
    sessionStorage.removeItem(AUTH_STORAGE_KEY)
  } catch {
    /* ignore */
  }
}
