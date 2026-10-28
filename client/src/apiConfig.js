/**
 * Backend origin for API calls.
 * - If VITE_API_URL is set (non-empty), use it (production / explicit dev).
 * - Otherwise default to same host as the SPA on port 5001 so we do NOT rely on the
 *   Vite proxy for large bodies (upload JSON + chat attachment_extracted_text can exceed proxy limits).
 */
export const API_BASE = (() => {
  const raw = import.meta.env.VITE_API_URL
  if (raw != null && String(raw).trim() !== '') {
    return String(raw).trim().replace(/\/$/, '')
  }
  if (typeof window === 'undefined') {
    return ''
  }
  const { protocol, hostname } = window.location
  const host = hostname && hostname.length > 0 ? hostname : '127.0.0.1'
  const port = import.meta.env.VITE_BACKEND_PORT || '5001'
  const proto = protocol === 'https:' ? 'https:' : 'http:'
  return `${proto}//${host}:${port}`
})()
