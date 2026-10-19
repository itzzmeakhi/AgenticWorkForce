/**
 * Splits streamed text into complete sentences. A sentence only counts as
 * complete once whitespace follows its end mark, so "4.5" or "ORD1001." at the
 * very end of the buffer are not cut early.
 * @returns {{ sentences: string[], rest: string }}
 */
export function takeSentences(buffer) {
  const sentences = []
  let rest = buffer
  for (;;) {
    const m = rest.match(/^([\s\S]*?[.!?])\s+/)
    if (!m) break
    const s = m[1].trim()
    if (s) sentences.push(s)
    rest = rest.slice(m[0].length)
  }
  return { sentences, rest }
}
