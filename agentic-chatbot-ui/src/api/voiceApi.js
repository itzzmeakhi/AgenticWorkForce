/**
 * Client for the backend voice endpoints (Deepgram STT/TTS, see
 * agentic-chatbot-be/api/main.py). Audio never goes to Deepgram from the
 * browser -- the backend holds the API key.
 */

/** @returns {Promise<{enabled: boolean, voices: Object, default_voice: string}>} */
export async function getVoiceStatus() {
  try {
    const res = await fetch('/voice/status')
    if (!res.ok) return { enabled: false, voices: {}, default_voice: '' }
    return await res.json()
  } catch {
    return { enabled: false, voices: {}, default_voice: '' }
  }
}

/** Sends a recorded Blob to the backend, resolves to the transcript ("" if no speech). */
export async function transcribeAudio(blob) {
  const res = await fetch('/voice/transcribe', {
    method: 'POST',
    headers: { 'Content-Type': blob.type || 'audio/webm' },
    body: blob,
  })
  if (!res.ok) {
    const detail = await res.json().then((d) => d.detail).catch(() => res.statusText)
    throw new Error(detail || `HTTP ${res.status}`)
  }
  const data = await res.json()
  return data.text || ''
}

/** Resolves to an object URL for the spoken reply; caller should revoke it when done. */
export async function fetchSpeech(text, voice) {
  const res = await fetch('/voice/speak', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, voice: voice || null }),
  })
  if (!res.ok) {
    const detail = await res.json().then((d) => d.detail).catch(() => res.statusText)
    throw new Error(detail || `HTTP ${res.status}`)
  }
  return URL.createObjectURL(await res.blob())
}
