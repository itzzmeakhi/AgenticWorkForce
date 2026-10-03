/**
 * Holds the signed-in user for the current tab, backed by that tab's own
 * sessionStorage (see auth/authStorage.js). The chat itself works signed
 * out -- general questions go straight to the backend. Only a question that
 * needs the asker's own account data triggers a sign-in prompt (see
 * utils/authGate.js and pages/ChatPage), which opens pages/LoginPage in a
 * new browser tab so the chat tab is never interrupted.
 *
 * This is a fake/demo auth flow: pages/LoginPage calls the mock
 * api/authApi.js (no real backend, no real session), and each tab's
 * sessionStorage is independent -- see LoginPage for how the login tab
 * hands its result back to the chat tab via postMessage.
 */
import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { clearStoredUser, getStoredUser, storeUser } from '../auth/authStorage';

const AuthContext = createContext(undefined)

/** @param {{ children: React.ReactNode }} props */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => getStoredUser())

  const login = useCallback((nextUser) => {
    storeUser(nextUser)
    setUser(nextUser)
  }, [])

  const logout = useCallback(() => {
    clearStoredUser()
    setUser(null)
  }, [])

  const value = useMemo(() => ({ user, login, logout }), [user, login, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth() must be called within an <AuthProvider>')
  }
  return ctx
}
