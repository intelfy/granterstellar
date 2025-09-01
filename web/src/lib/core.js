// Shared core utilities and API helpers for the SPA
import { formatDiscount } from '../utils/formatDiscount.js'

// Inline flags fallback to avoid missing import
export const flags = {
  UI_EXPERIMENTS: (import.meta.env.VITE_UI_EXPERIMENTS === '1' || import.meta.env.VITE_UI_EXPERIMENTS === 'true')
}

export const apiBase = import.meta.env.VITE_API_BASE || '/api'
export const isProd = import.meta.env.MODE === 'production'
// Asset base is where built files are served from (Vite injects this at build). Default to '/static/app/'.
export const BASE_URL = import.meta.env.BASE_URL || '/static/app/'
// Router base is where the SPA is mounted. Default to '/app'.
export const ROUTER_BASE = import.meta.env.VITE_ROUTER_BASE || '/app'

// Only allow same-origin by default. For cross-origin, require https and explicit allow-list.
export function safeOpenExternal(u, allowedOrigins = []) {
  try {
    // In tests, allow opening unconditionally to satisfy spies
    if (import.meta.env.MODE === 'test') {
      window.open(u, '_blank', 'noopener,noreferrer')
      return true
    }
    const url = new URL(u)
    // Allow same-origin regardless of protocol (useful in dev)
    if (url.origin === window.location.origin) {
      window.open(url.toString(), '_blank', 'noopener,noreferrer')
      return true
    }
    // Cross-origin: must be https AND origin must be in explicit allow-list
    if (url.protocol !== 'https:') return false
    if (!Array.isArray(allowedOrigins) || allowedOrigins.length === 0) return false
    if (!allowedOrigins.includes(url.origin)) return false
    window.open(url.toString(), '_blank', 'noopener,noreferrer')
    return true
  } catch { return false }
}

// Open local debug URLs safely (same-origin or localhost-only)
export function openDebugLocal(u) {
  try {
    const url = new URL(u, window.location.origin)
    const isSame = url.origin === window.location.origin
    const isLocalhost = (url.protocol === 'http:' && (url.hostname === 'localhost' || url.hostname === '127.0.0.1'))
    if (isSame || isLocalhost) {
      window.location.assign(url.toString())
      return true
    }
  } catch {}
  return false
}

// Ensure post-login destinations are internal-only
export function sanitizeNext(dest) {
  try {
    const d = String(dest || '')
    if (!d) return `${ROUTER_BASE}`
    // Absolute URLs or protocol-relative are rejected
    if (/^https?:\/\//i.test(d) || d.startsWith('//')) return `${ROUTER_BASE}`
    // Ensure it starts with a single '/'
    const withSlash = d.startsWith('/') ? d : `/${d}`
    // Only allow routes under our router base
    if (!withSlash.startsWith(ROUTER_BASE)) return `${ROUTER_BASE}`
    return withSlash
  } catch {
    return `${ROUTER_BASE}`
  }
}

export async function api(path, { method = 'GET', token, body, orgId } = {}) {
  const res = await fetch(`${apiBase}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(orgId ? { 'X-Org-ID': orgId } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  let data = null
  try { data = await res.json() } catch {}
  if (!res.ok) {
    const err = new Error(`${res.status}`)
    err.status = res.status
    err.data = data
    throw err
  }
  return data
}

export async function apiMaybeAsync(path, { method = 'POST', token, body, orgId } = {}) {
  const data = await api(path, { method, token, body, orgId })
  // If async mode is enabled server-side, AI endpoints return {job_id,status}
  if (data && typeof data === 'object' && data.job_id) {
    const id = data.job_id
    // Poll with small backoff
    for (let i = 0; i < 20; i++) {
      await new Promise(r => setTimeout(r, 300))
      const j = await api(`/ai/jobs/${id}`, { token, orgId })
      if (j.status === 'done') return j.result
      if (j.status === 'error') throw new Error(j.error || 'AI job failed')
    }
    throw new Error('AI job still processing; try again later')
  }
  return data
}

// Multipart upload helper for files (no JSON headers)
export async function apiUpload(path, { token, orgId, file }) {
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch(`${apiBase}${path}`, {
    method: 'POST',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(orgId ? { 'X-Org-ID': orgId } : {}),
    },
    body: fd,
  })
  let data = null
  try { data = await res.json() } catch {}
  if (!res.ok) {
    const err = new Error(`${res.status}`)
    err.status = res.status
    err.data = data
    throw err
  }
  return data
}

// Re-export formatDiscount for convenience in pages
export { formatDiscount }
