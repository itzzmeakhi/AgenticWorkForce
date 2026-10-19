/**
 * Holds the signed-in session for the current tab (see auth/authStorage.js).
 * The chat works signed out -- general questions, product search and the
 * knowledge base need no account. A question about the customer's own
 * orders, policies or claims needs a sign-in (utils/authGate.js intercepts it
 * and opens pages/LoginPage in a new tab, which hands the session back via
 * postMessage). The backend is the real gatekeeper: it verifies the token on
 * every request and only ever returns the signed-in customer's own data.
 */
import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { clearStoredSession, getStoredSession, storeSession } from '../auth/authStorage';

const AuthContext = createContext(undefined)

/** @param {{ children: React.ReactNode }} props */
export function AuthProvider({ children }) {
  const [session, setSession] = useState(() => getStoredSession())

  const login = useCallback((nextSession) => {
    storeSession(nextSession)
    setSession(nextSession)
  }, [])

  const logout = useCallback(() => {
    clearStoredSession()
    setSession(null)
  }, [])

  const value = useMemo(
    () => ({ user: session ? session.user : null, token: session ? session.token : null, login, logout }),
    [session, login, logout]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth() must be called within an <AuthProvider>')
  }
  return ctx
}
