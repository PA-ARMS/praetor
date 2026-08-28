/**
 * Local spoken replies via the browser (no API keys, no cloud TTS).
 * Voice is chosen once: Cortana-adjacent US female if present, else a UK butler.
 * Users only toggle speech on/off — they do not pick voices.
 */

export const VOICE_STORAGE_KEY = 'praetor_voice_on'
export const VOICE_CHANGE_EVENT = 'praetor-voice-toggle'

const CORTANA_NAME = [
  'cortana', 'eva', 'jenny', 'aria', 'zira', 'samantha', 'susan',
]
const BUTLER_NAME = [
  'george', 'malcolm', 'ryan', 'daniel', 'oliver', 'arthur',
]

let cachedVoice = null
let voicesReady = false

function voiceHay(v) {
  return `${v?.name || ''} ${v?.voiceURI || ''} ${v?.lang || ''}`.toLowerCase()
}

function scoreVoice(v) {
  const hay = voiceHay(v)
  const lang = (v.lang || '').toLowerCase()
  let score = 0

  if (CORTANA_NAME.some((n) => hay.includes(n))) score += 100
  if (lang.startsWith('en-us') && v.gender === 'female') score += 40
  if (lang.startsWith('en-us') && /female|zira|jenny|aria/.test(hay)) score += 30
  if (hay.includes('zira')) score += 20

  if (BUTLER_NAME.some((n) => hay.includes(n)) && /en-gb|en-uk/.test(hay + lang)) score += 70
  if (lang.startsWith('en-gb') && /male|george/.test(hay)) score += 35

  if (lang.startsWith('en')) score += 5
  return score
}

function pickVoice() {
  if (typeof window === 'undefined' || !window.speechSynthesis) return null
  const voices = window.speechSynthesis.getVoices() || []
  if (!voices.length) return cachedVoice
  let best = null
  let bestScore = -1
  for (const v of voices) {
    const s = scoreVoice(v)
    if (s > bestScore) {
      best = v
      bestScore = s
    }
  }
  cachedVoice = best
  voicesReady = true
  return cachedVoice
}

function ensureVoices() {
  if (typeof window === 'undefined' || !window.speechSynthesis) return
  pickVoice()
  if (!voicesReady) {
    window.speechSynthesis.onvoiceschanged = () => {
      pickVoice()
    }
  }
}

export function isVoiceSupported() {
  return typeof window !== 'undefined' && 'speechSynthesis' in window
}

export function getVoiceEnabled() {
  try {
    return localStorage.getItem(VOICE_STORAGE_KEY) !== 'false'
  } catch {
    return true
  }
}

export function setVoiceEnabled(on) {
  try {
    localStorage.setItem(VOICE_STORAGE_KEY, on ? 'true' : 'false')
  } catch {
    /* ignore */
  }
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(VOICE_CHANGE_EVENT, { detail: { on: !!on } }))
  }
  if (!on) stopSpeaking()
}

export function stopSpeaking() {
  if (typeof window === 'undefined' || !window.speechSynthesis) return
  window.speechSynthesis.cancel()
}

/** Strip markdown and legal-memo chrome so speech is spoken prose. */
export function textForSpeech(raw) {
  if (!raw || typeof raw !== 'string') return ''
  let t = raw.replace(/\r\n/g, '\n')

  const short = t.match(/\*\*Short answer\*\*[:\s]*([\s\S]*?)(?=\n\s*\*\*|\n#{1,3}\s|$)/i)
  if (short && short[1].trim().length > 40) {
    t = `Short answer. ${short[1].trim()}`
  }

  t = t
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/!\[[^\]]*]\([^)]+\)/g, ' ')
    .replace(/\[([^\]]+)]\([^)]+\)/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/^[-*]\s+/gm, '')
    .replace(/^\d+\.\s+/gm, '')
    .replace(/https?:\/\/\S+/g, '')
    .replace(/\s+/g, ' ')
    .trim()

  if (t.length > 2200) {
    t = `${t.slice(0, 2200).replace(/\s+\S*$/, '')}. End of spoken summary. The full memo is on screen.`
  }
  return t
}

function voiceProfile(voice) {
  const hay = voiceHay(voice)
  const butler = BUTLER_NAME.some((n) => hay.includes(n)) || /en-gb|en-uk/.test(hay)
  const cortana = CORTANA_NAME.some((n) => hay.includes(n)) || hay.includes('zira')
  if (cortana && !butler) {
    return { rate: 0.94, pitch: 1.14 }
  }
  if (butler) {
    return { rate: 0.88, pitch: 0.84 }
  }
  return { rate: 0.94, pitch: 1.08 }
}

export function speakResponse(raw) {
  if (!isVoiceSupported() || !getVoiceEnabled()) return
  const text = textForSpeech(raw)
  if (!text) return

  ensureVoices()
  const synth = window.speechSynthesis
  synth.cancel()

  const utter = new SpeechSynthesisUtterance(text)
  const voice = pickVoice()
  if (voice) utter.voice = voice
  const profile = voiceProfile(voice)
  utter.rate = profile.rate
  utter.pitch = profile.pitch
  utter.volume = 1
  utter.lang = voice?.lang || 'en-US'
  synth.speak(utter)
}

ensureVoices()
