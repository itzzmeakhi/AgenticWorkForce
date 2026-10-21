/**
 * What the assistant can really do, in one place, so the suggestion chips and
 * the capabilities panel never promise anything that does not exist. Every item
 * maps to a real tool or knowledge document in the backend.
 *
 * Signed in to a domain -> only that domain's items (plus the shared ones).
 * Signed out           -> everything, so visitors can see the full range.
 */

const ECOMMERCE_ITEMS = [
  'See all my orders',
  'Check an order\'s status',
  'Track a package (carrier and current location)',
  'Cancel an order before it ships (asks you to confirm first)',
  'Search the product catalogue and see product details',
]

const INSURANCE_ITEMS = [
  'See all my policies and premium due dates',
  'Look up the details of a policy',
  'See all my claims and check a claim\'s status',
  'File a new claim on an active policy',
]

const KNOWLEDGE = {
  ecommerce: ['Refund and return policy', 'Shipping and tracking policy'],
  insurance: ['How claims work, and what documents are needed', 'Premiums, grace period and renewals', 'What is covered, and common exclusions'],
  general: ['Sign-in, support hours and other general questions'],
}

const GROUPS = {
  ecommerce: { title: 'E-commerce', color: '#22c55e', items: ECOMMERCE_ITEMS },
  insurance: { title: 'Insurance', color: '#f59e0b', items: INSURANCE_ITEMS },
}

/** @param {'ecommerce'|'insurance'|null|undefined} accountType @param {boolean} voiceEnabled */
export function capabilityGroups(accountType, voiceEnabled = false) {
  const domains = accountType === 'ecommerce' || accountType === 'insurance' ? [accountType] : ['ecommerce', 'insurance']

  const groups = domains.map((d) => GROUPS[d])
  groups.push({
    title: 'Knowledge base',
    color: '#64748b',
    items: [...domains.flatMap((d) => KNOWLEDGE[d]), ...KNOWLEDGE.general],
  })

  const extras = ['Look up current information on the web (needs a Tavily key on the server)']
  if (voiceEnabled) extras.push('Talk instead of type: microphone input and spoken replies')
  groups.push({ title: 'Anywhere', color: '#6366f1', items: extras })
  return groups
}

// Suggestion chips. Only phrasings that work without knowing an ID, so they are
// right for whichever customer is signed in.
const CHIPS = {
  ecommerce: [
    'Show me my orders',
    'Show me gaming laptops under 150000',
    'How long does a refund take?',
    'What is your shipping policy?',
  ],
  insurance: [
    'Show me my policies',
    'Show me my claims',
    'What is the claims process?',
    'What is the premium grace period?',
    'What is excluded from coverage?',
  ],
}

const SIGNED_OUT_CHIPS = [
  'Show me gaming laptops under 150000',
  'How long does a refund take?',
  'What is the claims process?',
  'Show me my orders',
  'Show me my policies',
]

/** @returns {string[]} */
export function suggestionChips(accountType) {
  return CHIPS[accountType] ?? SIGNED_OUT_CHIPS
}
