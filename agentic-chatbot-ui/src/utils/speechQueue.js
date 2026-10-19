/**
 * Plays spoken sentences back to back. enqueue() starts fetching audio
 * immediately (so sentence N+1 is ready while N plays) and playback stays in
 * order. stop() cancels everything, including audio that is mid-flight.
 */
export default class SpeechQueue {
  constructor(fetchSpeech) {
    this.fetchSpeech = fetchSpeech // (text) => Promise<objectUrl>
    this.items = []
    this.playing = false
    this.generation = 0
    this.audio = null
  }

  enqueue(text) {
    if (!text || !text.trim()) return
    this.items.push(this.fetchSpeech(text).catch(() => null))
    void this.pump()
  }

  async pump() {
    if (this.playing) return
    this.playing = true
    const gen = this.generation
    while (this.items.length && gen === this.generation) {
      const url = await this.items.shift()
      if (!url) continue
      if (gen !== this.generation) {
        URL.revokeObjectURL(url)
        break
      }
      await this.play(url)
    }
    if (gen === this.generation) this.playing = false
  }

  play(url) {
    return new Promise((resolve) => {
      const audio = new Audio(url)
      this.audio = audio
      const done = () => {
        URL.revokeObjectURL(url)
        if (this.audio === audio) this.audio = null
        resolve()
      }
      audio.onended = done
      audio.onerror = done
      audio.play().catch(done)
    })
  }

  stop() {
    this.generation += 1
    this.items = []
    this.playing = false
    if (this.audio) {
      this.audio.pause()
      this.audio.dispatchEvent(new Event('ended'))
      this.audio = null
    }
  }
}
