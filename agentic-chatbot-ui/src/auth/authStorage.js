/**
 * Persists the signed-in user to sessionStorage so a page refresh doesn't
 * drop them back to a signed-out state. This is client-side-only storage
 * for a client-side-only "auth" flow -- see context/AuthContext.jsx for the
 * caveat that this is NOT real authentication.
 */
const AUTH_STORAGE_KEY = 'dw_auth_user'

/** @returns {{ name: string, customerId: string, accountType: string } | null} */
export function getStoredUser() {
  try {
    const raw = sessionStorage.getItem(AUTH_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed.name !== 'string' || typeof parsed.customerId !== 'string') {
      return null
    }
    return parsed
  } catch {
    return null
  }
}

/** @param {{ name: string, customerId: string, accountType: string }} user */
export function storeUser(user) {
  try {
    sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user))
  } catch {
    /* sessionStorage unavailable (e.g. private mode) -- non-fatal */
  }
}

export function clearStoredUser() {
  try {
    sessionStorage.removeItem(AUTH_STORAGE_KEY)
  } catch {
    /* ignore */
  }
}
