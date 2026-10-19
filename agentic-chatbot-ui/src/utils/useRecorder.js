import { useCallback, useEffect, useRef, useState } from 'react'

// End-of-speech detection tuning
const POLL_MS = 50
const CALIBRATE_MS = 300        // measure room noise before judging speech
const SILENCE_MS = 1000         // this long below threshold after speech => stop
const NO_SPEECH_MS = 7000       // nothing said at all => give up
const MAX_RECORD_MS = 30000
const MIN_THRESHOLD = 0.02      // RMS floor so a quiet room is not "speech"

/**
 * Microphone recorder built on MediaRecorder, with automatic end-of-speech
 * detection: it watches the mic level (WebAudio analyser) and stops by itself
 * once you have spoken and then been quiet for SILENCE_MS. toggle() still
 * starts/stops manually. Passes the audio Blob to onRecorded.
 * state: 'idle' | 'recording' | 'unsupported'.
 */
export default function useRecorder(onRecorded, onError) {
  const supported =
    typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== 'undefined'
  const [state, setState] = useState(supported ? 'idle' : 'unsupported')
  const recorderRef = useRef(null)
  const streamRef = useRef(null)
  const chunksRef = useRef([])
  const vadRef = useRef(null)
  const cbRef = useRef({ onRecorded, onError })

  useEffect(() => {
    cbRef.current = { onRecorded, onError }
  })

  const stopVad = () => {
    if (vadRef.current) {
      clearInterval(vadRef.current.timer)
      vadRef.current.ctx.close().catch(() => {})
      vadRef.current = null
    }
  }

  const startVad = (stream, stop) => {
    const AudioCtx = window.AudioContext || window.webkitAudioContext
    if (!AudioCtx) return // no analyser: manual stop only
    const ctx = new AudioCtx()
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 1024
    ctx.createMediaStreamSource(stream).connect(analyser)
    const samples = new Float32Array(analyser.fftSize)
    const startedAt = Date.now()
    let noiseSum = 0
    let noiseN = 0
    let threshold = null
    let heardSpeech = false
    let lastLoud = startedAt

    const timer = setInterval(() => {
      analyser.getFloatTimeDomainData(samples)
      let sum = 0
      for (let i = 0; i < samples.length; i += 1) sum += samples[i] * samples[i]
      const rms = Math.sqrt(sum / samples.length)
      const now = Date.now()

      if (now - startedAt < CALIBRATE_MS) {
        noiseSum += rms
        noiseN += 1
        return
      }
      if (threshold === null) threshold = Math.max(MIN_THRESHOLD, (noiseSum / Math.max(noiseN, 1)) * 3)

      if (rms > threshold) {
        heardSpeech = true
        lastLoud = now
      }
      if (heardSpeech && now - lastLoud > SILENCE_MS) stop()
      else if (!heardSpeech && now - startedAt > NO_SPEECH_MS) stop()
      else if (now - startedAt > MAX_RECORD_MS) stop()
    }, POLL_MS)
    vadRef.current = { ctx, timer }
  }

  const release = () => {
    stopVad()
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    recorderRef.current = null
  }

  useEffect(() => () => {
    try { recorderRef.current?.stop() } catch { /* already stopped */ }
    release()
  }, [])

  const toggle = useCallback(async () => {
    if (!supported) return
    if (recorderRef.current) {
      recorderRef.current.stop()
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const rec = new MediaRecorder(stream)
      chunksRef.current = []
      rec.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || 'audio/webm' })
        release()
        setState('idle')
        if (blob.size > 0) cbRef.current.onRecorded?.(blob)
      }
      rec.start()
      startVad(stream, () => { if (rec.state === 'recording') rec.stop() })
      recorderRef.current = rec
      setState('recording')
    } catch (err) {
      release()
      setState('idle')
      cbRef.current.onError?.(err?.name === 'NotAllowedError' ? 'Microphone permission was denied.' : 'Could not start the microphone.')
    }
  }, [supported])

  return { state, toggle }
}
