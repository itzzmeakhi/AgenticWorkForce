/**
 * Fake authentication "API" -- a single entry point that authenticates a
 * user for EITHER domain (e-commerce or insurance), not two separate APIs.
 * It's shaped like a real API call (async, simulated latency, can
 * succeed/reject) so swapping it for a real `fetch('/auth/login', ...)`
 * later is a one-function change; nothing else in the app needs to know the
 * difference (see context/AuthContext.jsx and pages/LoginPage, which only
 * see the returned session object: { token, user }).
 *
 * There is no real backend behind this: "known" accounts below match the
 * order/policy ids seeded in data/mock_db/*.json so a demo login feels
 * connected to real data, and any other id is accepted too (this is a
 * prototype, not an identity system) as long as a password is supplied.
 */
const MOCK_ACCOUNTS = {
  ORD1001: { password: 'demo1234', name: 'Priya Nair', accountType: 'ecommerce' },
  ORD1002: { password: 'demo1234', name: 'Rahul Verma', accountType: 'ecommerce' },
  ORD1003: { password: 'demo1234', name: 'Sara Khan', accountType: 'ecommerce' },
  ORD1004: { password: 'demo1234', name: 'Arjun Mehta', accountType: 'ecommerce' },
  POL2001: { password: 'demo1234', name: 'Neha Kapoor', accountType: 'insurance' },
  POL2002: { password: 'demo1234', name: 'Vikram Singh', accountType: 'insurance' },
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function fakeToken(id) {
  return `dw_${id.toLowerCase()}_${Math.random().toString(36).slice(2, 10)}_${Date.now().toString(36)}`
}

/**
 * @param {string} customerId an order id (ORD1001), policy id (POL2001), or
 *   any free-text account id for the demo accounts not seeded above.
 * @param {string} password any non-empty value for unseeded ids; the exact
 *   seeded password ("demo1234") for the ids listed in MOCK_ACCOUNTS.
 * @param {'ecommerce' | 'insurance' | 'both'} preferredAccountType used only
 *   when `customerId` isn't a known seeded account -- lets the login form's
 *   "I need help with" choice pick the domain for a fresh demo id.
 * @returns {Promise<{ token: string, user: { name: string, customerId: string, accountType: string } }>}
 */
export async function fakeAuthenticate(customerId, password, preferredAccountType) {
  await delay(600) // simulate network latency, like a real API call

  const id = customerId.trim().toUpperCase()
  if (!id || !password) {
    throw new Error('Enter your customer/policy ID and password.')
  }

  const known = MOCK_ACCOUNTS[id]
  if (known) {
    if (password !== known.password) {
      throw new Error('Incorrect password for this ID.')
    }
    return { token: fakeToken(id), user: { name: known.name, customerId: id, accountType: known.accountType } }
  }

  if (password.length < 4) {
    throw new Error('Password must be at least 4 characters.')
  }

  return {
    token: fakeToken(id),
    user: { name: `Customer ${id}`, customerId: id, accountType: preferredAccountType },
  }
}
