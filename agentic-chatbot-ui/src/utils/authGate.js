/**
 * Decides whether a chat question needs the asker's own account data --
 * a specific order/policy/claim id, or a personal phrase like "my order" --
 * before it's safe to answer. General questions ("what's your refund
 * policy?") don't need this and go straight to the backend; a question that
 * matches gets intercepted client-side and turned into a sign-in prompt
 * instead (see pages/ChatPage's handleSend).
 */
const ORDER_ID_RE = /\bORD\d{3,}\b/i
const POLICY_ID_RE = /\bPOL\d{3,}\b/i
const CLAIM_ID_RE = /\bCLM\d{3,}\b/i
const PERSONAL_PHRASE_RE = /\bmy (order|orders|package|delivery|deliveries|account|policy|policies|claim|claims|refund|subscription)\b/i
const INSURANCE_WORD_RE = /\b(polic|claim)/i

/**
 * @param {string} text
 * @returns {{ requiresAuth: boolean, id?: string, domain?: 'ecommerce' | 'insurance' }}
 */
export function checkAuthGate(text) {
  const orderMatch = text.match(ORDER_ID_RE)
  if (orderMatch) {
    return { requiresAuth: true, id: orderMatch[0].toUpperCase(), domain: 'ecommerce' }
  }

  const policyMatch = text.match(POLICY_ID_RE)
  if (policyMatch) {
    return { requiresAuth: true, id: policyMatch[0].toUpperCase(), domain: 'insurance' }
  }

  const claimMatch = text.match(CLAIM_ID_RE)
  if (claimMatch) {
    return { requiresAuth: true, id: claimMatch[0].toUpperCase(), domain: 'insurance' }
  }

  if (PERSONAL_PHRASE_RE.test(text)) {
    return { requiresAuth: true, domain: INSURANCE_WORD_RE.test(text) ? 'insurance' : 'ecommerce' }
  }

  return { requiresAuth: false }
}
