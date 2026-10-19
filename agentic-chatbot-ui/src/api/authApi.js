/**
 * Real sign-in against the backend (POST /auth/login). The chosen account
 * type ("ecommerce" | "insurance") decides which customer store the
 * credentials are checked against; the returned JWT only works for that domain.
 *
 * Resolves to a session { token, user }, where
 * user = { name, email, customerId, accountType }.
 */
export async function login(accountType, email, password) {
  if (!email.trim() || !password) {
    throw new Error('Enter your email and password.')
  }

  let res
  try {
    res = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ domain: accountType, email: email.trim(), password }),
    })
  } catch {
    throw new Error('Could not reach the server. Is the backend running?')
  }

  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Sign-in failed. Please try again.')
  }

  return {
    token: data.token,
    user: {
      name: data.user.name,
      email: data.user.email,
      customerId: data.user.customer_id,
      accountType: data.user.domain,
    },
  }
}
