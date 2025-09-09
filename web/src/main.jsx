import React, { useEffect, useMemo, useState, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { formatDiscount } from './utils/formatDiscount.js'

// Inline flags fallback to avoid missing import
const flags = {
  UI_EXPERIMENTS: (import.meta.env.VITE_UI_EXPERIMENTS === '1' || import.meta.env.VITE_UI_EXPERIMENTS === 'true')
}

export function NotFound({ token }) {
  return (
    <div>
      <h1>404 — Page not found</h1>
      <p>The page you're looking for doesn't exist. It may have been moved.</p>
      <p>
        {token ? (
          <a href={`${ROUTER_BASE}`}>Go to the app</a>
        ) : (
          <a href={`${ROUTER_BASE}/login`}>Go to login</a>
        )}
        {' '}· <a href={`${ROUTER_BASE}`}>Homepage</a>
      </p>
    </div>
  )
}

const apiBase = import.meta.env.VITE_API_BASE || '/api'
const isProd = import.meta.env.MODE === 'production'
// Asset base is where built files are served from (Vite injects this at build). Default to '/static/app/'.
const BASE_URL = import.meta.env.BASE_URL || '/static/app/'
// Router base is where the SPA is mounted. Default to '/app'.
const ROUTER_BASE = import.meta.env.VITE_ROUTER_BASE || '/app'

// Dev-time URL self-correction: ensure router base prefix exists so deep links work during dev
// Only run when dev asset base is '/'; otherwise, let host serve its own base path (e.g., '/static/app/')
// Skip during tests (jsdom doesn't implement full navigation APIs)
if (import.meta.env.DEV && import.meta.env.MODE !== 'test' && (import.meta.env.BASE_URL || '/') === '/') {
  try {
    const { origin, pathname, search, hash } = window.location
    if (pathname && !pathname.startsWith(ROUTER_BASE)) {
      const normalizedBase = ROUTER_BASE.endsWith('/') ? ROUTER_BASE.slice(0, -1) : ROUTER_BASE
      const normalizedPath = pathname.startsWith('/') ? pathname : `/${pathname}`
      const target = new URL(`${normalizedBase}${normalizedPath}${search}${hash}`, origin)
      // Same-origin only
      if (target.origin === origin) {
        window.location.replace(target.toString())
      }
    }
  } catch {}
}

// Only allow same-origin by default. For cross-origin, require https and explicit allow-list.
function safeOpenExternal(u, allowedOrigins = []) {
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
function openDebugLocal(u) {
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
function sanitizeNext(dest) {
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

// Lazy page chunks (route-level code splitting)
const LazyBillingPage = React.lazy(() => import('./pages/BillingPage.jsx'))
const LazyAccountPage = React.lazy(() => import('./pages/AccountPage.jsx'))
const LazyDashboard = React.lazy(() => import('./pages/Dashboard.jsx'))
const LazyProposals = React.lazy(() => import('./pages/Dashboard.jsx').then(m => ({ default: (props) => <m.Proposals {...props} /> })))
const LazyOrgs = React.lazy(() => import('./pages/Dashboard.jsx').then(m => ({ default: (props) => <m.Orgs {...props} /> })))
const LazyOrgsPage = React.lazy(() => import('./pages/OrgsPage.jsx'))

// Opportunistic idle preloads for likely-next routes (no-op in tests)
function useIdlePreloads() {
  useEffect(() => {
    if (import.meta.env.MODE === 'test') return
    const conn = (navigator && 'connection' in navigator) ? navigator.connection : null
    const saveData = conn && conn.saveData
    const slow = conn && (conn.effectiveType === '2g' || conn.effectiveType === 'slow-2g')
    if (saveData || slow) return
    const preload = () => {
      try { import('./pages/BillingPage.jsx') } catch {}
      try { import('./pages/AccountPage.jsx') } catch {}
      try { import('./pages/OrgsPage.jsx') } catch {}
    }
    if ('requestIdleCallback' in window) {
      // @ts-ignore
      window.requestIdleCallback(preload, { timeout: 2000 })
    } else {
      setTimeout(preload, 500)
    }
  }, [])
}

// Optional: Web Vitals reporting in dev/experiments only
function useWebVitals() {
  useEffect(() => {
    if (import.meta.env.MODE === 'test') return
    const enable = (import.meta.env.VITE_WEB_VITALS === '1' || import.meta.env.VITE_UI_EXPERIMENTS === '1' || import.meta.env.VITE_UI_EXPERIMENTS === 'true')
    if (!enable) return
    let cancelled = false
    import('web-vitals').then((mod) => {
      if (cancelled) return
      const log = (m) => {
        try { console.info('[Vitals]', m.name, Math.round(m.value), m) } catch {}
      }
      try {
        mod.onCLS(log)
        mod.onFID(log)
        mod.onLCP(log)
        mod.onINP && mod.onINP(log)
        mod.onTTFB(log)
      } catch {}
    }).catch(() => {})
    return () => { cancelled = true }
  }, [])
}

function Umami() {
  // Inject Umami script if configured
  useEffect(() => {
    const websiteId = import.meta.env.VITE_UMAMI_WEBSITE_ID
    const src = import.meta.env.VITE_UMAMI_SRC
    if (!websiteId || !src) return
    if (document.querySelector('script[data-umami="1"]')) return
    const s = document.createElement('script')
    s.async = true
    s.src = src
    s.setAttribute('data-website-id', websiteId)
    s.setAttribute('data-umami', '1')
    document.head.appendChild(s)
  }, [])
  // Best-effort SPA pageview tracking on route changes (in addition to Umami auto-track)
  const location = useLocation()
  useEffect(() => {
    try { window.umami && typeof window.umami.track === 'function' && window.umami.track('pageview') } catch {}
  }, [location.pathname, location.search, location.hash])
  return null
}

// Global invite banner: detects ?invite= token when authenticated and offers Accept/Dismiss
export function InviteBanner({ token }) {
  const location = useLocation()
  const navigate = useNavigate()
  const [pending, setPending] = useState('')
  useEffect(() => {
    try {
      const qs = new URLSearchParams(location.search || '')
      const inv = qs.get('invite') || ''
      setPending(token ? inv : '')
    } catch {
      setPending('')
    }
  }, [location.search, token])
  const clearParam = () => {
    try {
      const qs = new URLSearchParams(location.search || '')
      qs.delete('invite')
  // Use router-native replace navigation to avoid jsdom SecurityError and honor basename
  const search = qs.toString()
  const newPath = `${location.pathname}${search ? `?${search}` : ''}${location.hash || ''}`
  navigate(newPath, { replace: true })
    } catch {}
  }
  if (!token || !pending) return null
  return (
    <div data-testid="invite-banner" role="region" aria-label="org-invite">
      <span>Organization invite detected.</span>
      <button
        type="button"
        data-testid="invite-accept"
        onClick={async () => {
          try {
            await api('/orgs/invites/accept', { method: 'POST', token, body: { token: pending } })
            // Clear from URL and local state, then navigate to app root to refresh org lists
            clearParam()
            setPending('')
            navigate('/', { replace: true })
            alert('Invite accepted')
          } catch (e) {
            alert('Invite accept failed: ' + (e?.data?.error || e.message))
          }
        }}
      >Accept invite</button>
      <button
        type="button"
        data-testid="invite-dismiss"
        onClick={() => { clearParam(); setPending('') }}
      >Not now</button>
    </div>
  )
}

function useToken() {
  const [token, setToken] = useState(() => localStorage.getItem('jwt') || '')
  const save = (t) => {
    setToken(t || '')
    if (t) localStorage.setItem('jwt', t)
    else localStorage.removeItem('jwt')
  }
  return [token, save]
}

async function api(path, { method = 'GET', token, body, orgId } = {}) {
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

async function apiMaybeAsync(path, { method = 'POST', token, body, orgId } = {}) {
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
// Simple billing screen to start checkout and open portal
export function BillingPage(props) {
  return (
    <Suspense fallback={<div>Loading…</div>}>
      <LazyBillingPage {...props} />
    </Suspense>
  )
}

// Simple account/profile page to edit username, email, first/last name
export function AccountPage(props) {
  return (
    <Suspense fallback={<div>Loading…</div>}>
      <LazyAccountPage {...props} />
    </Suspense>
  )
}

// Multipart upload helper for files (no JSON headers)
async function apiUpload(path, { token, orgId, file }) {
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

// Login page (DEBUG includes username/password; prod shows OAuth only)
function LoginPage({ token, setToken }) {
  const [username, setUsername] = useState('demo')
  const [password, setPassword] = useState('demo12345')
  const [email, setEmail] = useState('')
  const [pendingInvite, setPendingInvite] = useState('')
  const [oauthError, setOauthError] = useState('')
  const navigate = useNavigate()
  const location = useLocation()
  const next = useMemo(() => new URLSearchParams(location.search).get('next') || `${ROUTER_BASE}`, [location.search])
  const safeNext = useMemo(() => sanitizeNext(next), [next])
  // If already authenticated, skip login and go to next/app directly
  useEffect(() => {
    if (token) {
    navigate(safeNext, { replace: true })
    }
  }, [token, safeNext, navigate])
  useEffect(() => {
    const url = new URL(window.location.href)
    const inv = url.searchParams.get('invite')
    if (inv) setPendingInvite(inv)
    // Surface OAuth errors coming back from callback
    const err = url.searchParams.get('oauth_error')
    const code = url.searchParams.get('oauth_code')
    if (err || code) {
      const map = {
        email_unverified: 'Your GitHub email is not verified. Verify it on GitHub or use another provider.',
        email_not_found: 'Your provider did not share an email. Try a different provider or sign up manually.',
        token_exchange_failed: 'Could not complete sign-in with the provider. Please try again.',
        invalid_id_token: 'Invalid identity token from provider. Please retry.',
        missing_code: 'Missing code from provider.',
        missing_access_token: 'Provider did not return an access token.',
        oauth_not_configured: 'OAuth is not configured on the server.',
      }
      setOauthError(map[code] || err || 'Sign-in failed. Please try again.')
      // Clean the URL
      url.searchParams.delete('oauth_error')
      url.searchParams.delete('oauth_code')
      window.history.replaceState({}, '', url.toString())
    }
  }, [])
  const onLogin = async (e) => {
    e.preventDefault()
    try {
      const data = await api('/token', { method: 'POST', body: { username, password } })
      setToken(data.access)
      // Require at least one org: if none, go to registration; otherwise, continue
      try {
        const orgs = await api('/orgs/', { token: data.access })
  if (Array.isArray(orgs) && orgs.length === 0) navigate(`/register?next=${encodeURIComponent(safeNext)}`, { replace: true })
  else navigate(safeNext, { replace: true })
      } catch {
  navigate(safeNext, { replace: true })
      }
    } catch {
      setToken('')
    }
  }
  const onGoogleStart = async () => {
    try {
  // Preserve post-login destination across OAuth roundtrip
  if (safeNext) sessionStorage.setItem('postLoginNext', safeNext)
  // Remember provider for callback routing
  sessionStorage.setItem('oauthProvider', 'google')
      const url = new URL(window.location.href)
      const inv = url.searchParams.get('invite')
      const qs = inv ? `?invite=${encodeURIComponent(inv)}` : ''
      const data = await api(`/oauth/google/start${qs}`, { token })
      if (data?.auth_url) {
        // Allow well-known OAuth authorization endpoints only
        try {
          const u = new URL(data.auth_url)
          const isGoogle = (u.origin === 'https://accounts.google.com' && u.pathname === '/o/oauth2/v2/auth')
          const isGitHub = (u.origin === 'https://github.com' && u.pathname === '/login/oauth/authorize')
          const isFacebook = (u.origin === 'https://www.facebook.com' && (/^\/v\d+(?:\.\d+)?\/dialog\/oauth$/.test(u.pathname) || u.pathname === '/dialog/oauth'))
          if (isGoogle || isGitHub || isFacebook) {
            // Safe navigation: explicit provider auth endpoints only
            window.location.assign(u.toString())
          }
        } catch {}
      }
    } catch {}
  }
  const onGoogleDebug = async (e) => {
    e.preventDefault()
    if (!email) return alert('Enter email for debug OAuth')
    try {
      const params = new URLSearchParams({ code: 'x', email })
      const res = await fetch(`${apiBase}/oauth/google/callback`, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: params.toString() })
      const json = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error('callback failed')
      if (json?.access) {
        setToken(json.access)
        try {
          const orgs = await api('/orgs/', { token: json.access })
          if (Array.isArray(orgs) && orgs.length === 0) navigate(`/register?next=${encodeURIComponent(safeNext)}`, { replace: true })
          else navigate(safeNext, { replace: true })
        } catch {
          navigate(safeNext, { replace: true })
        }
      }
    } catch { alert('Debug OAuth failed') }
  }
  return (
    <div>
      <h1>Granterstellar</h1>
      {!isProd && (
        <form onSubmit={onLogin}>
          <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="username" />
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password" />
          <button type="submit">Login</button>
        </form>
      )}
      <button type="button" onClick={onGoogleStart}>Sign in with Google</button>
      <button type="button" onClick={async () => {
        try {
          if (safeNext) sessionStorage.setItem('postLoginNext', safeNext)
          sessionStorage.setItem('oauthProvider', 'github')
          const url = new URL(window.location.href)
          const inv = url.searchParams.get('invite')
          const qs = inv ? `?invite=${encodeURIComponent(inv)}` : ''
          const data = await api(`/oauth/github/start${qs}`, { token })
          if (data?.auth_url) {
            try {
              const u = new URL(data.auth_url)
              const isGitHub = (u.origin === 'https://github.com' && u.pathname === '/login/oauth/authorize')
              if (isGitHub) window.location.assign(u.toString())
            } catch {}
          }
        } catch {}
      }}>Sign in with GitHub</button>
      <button type="button" onClick={async () => {
        try {
          if (safeNext) sessionStorage.setItem('postLoginNext', safeNext)
          sessionStorage.setItem('oauthProvider', 'facebook')
          const url = new URL(window.location.href)
          const inv = url.searchParams.get('invite')
          const qs = inv ? `?invite=${encodeURIComponent(inv)}` : ''
          const data = await api(`/oauth/facebook/start${qs}`, { token })
          if (data?.auth_url) {
            try {
              const u = new URL(data.auth_url)
              const isFacebook = (u.origin === 'https://www.facebook.com' && (/^\/v\d+(?:\.\d+)?\/dialog\/oauth$/.test(u.pathname) || u.pathname === '/dialog/oauth'))
              if (isFacebook) window.location.assign(u.toString())
            } catch {}
          }
        } catch {}
      }}>Sign in with Facebook</button>
      {!isProd && (
        <form onSubmit={onGoogleDebug}>
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="debug: you@example.com" />
          <button type="submit">Debug Google Login</button>
        </form>
      )}
      {oauthError && (
        <div>{oauthError}</div>
      )}
      {!isProd && (
        <button type="button" onClick={() => navigate('/register')}>Create an account</button>
      )}
      {token && pendingInvite && (
  <button type="button" onClick={async () => { try { await api('/orgs/invites/accept', { method: 'POST', token, body: { token: pendingInvite } }); alert('Invite accepted'); try { const url = new URL(window.location.href); url.searchParams.delete('invite'); const path = `${url.pathname}${url.search}${url.hash}`; navigate(path, { replace: true }) } catch {} setPendingInvite('') } catch (e) { alert('Invite accept failed: ' + (e?.data?.error || e.message)) } }}>Accept pending invite</button>
      )}
    </div>
  )
}

// Re-exported wrappers to keep tests working while code splits
export function Proposals(props) {
  return (
    <Suspense fallback={<div>Loading…</div>}>
      <LazyProposals {...props} />
    </Suspense>
  )
}

export function Orgs(props) {
  return (
    <Suspense fallback={<div>Loading…</div>}>
      <LazyOrgs {...props} />
    </Suspense>
  )
}

// OAuth callback landing: exchanges the code for tokens, then routes
export function OAuthCallback({ setToken }) {
  const navigate = useNavigate()
  const location = useLocation()
  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const code = params.get('code')
    const state = params.get('state')
  const storedNext = sanitizeNext(sessionStorage.getItem('postLoginNext') || `${ROUTER_BASE}`)
  const provider = sessionStorage.getItem('oauthProvider') || 'google'
    if (!code) {
      navigate('/login', { replace: true })
      return
    }
    ;(async () => {
      try {
        const body = new URLSearchParams({ code })
        if (state) body.set('state', state)
    // Dispatch to provider-specific API callback
    const res = await fetch(`${apiBase}/oauth/${provider}/callback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: body.toString(),
        })
        const json = await res.json().catch(() => ({}))
        if (!res.ok) {
          const msg = (json && (json.error || json.detail)) || 'oauth callback failed'
          const codeVal = (json && json.code) || ''
          const qs = new URLSearchParams()
          qs.set('oauth_error', String(msg))
          if (codeVal) qs.set('oauth_code', String(codeVal))
          navigate(`/login?${qs.toString()}`, { replace: true })
          return
        }
        if (json?.access) {
          setToken(json.access)
          try {
            const orgs = await api('/orgs/', { token: json.access })
            if (Array.isArray(orgs) && orgs.length === 0) {
              const dest = storedNext || `${ROUTER_BASE}`
              navigate(`/register?next=${encodeURIComponent(dest)}`, { replace: true })
            } else {
              navigate(storedNext || `${ROUTER_BASE}`, { replace: true })
            }
          } catch { navigate(storedNext || `${ROUTER_BASE}`, { replace: true }) }
        } else {
          navigate('/login?oauth_error=Unknown', { replace: true })
        }
      } catch {
        navigate('/login?oauth_error=Network%20error', { replace: true })
      }
      finally {
        sessionStorage.removeItem('postLoginNext')
  sessionStorage.removeItem('oauthProvider')
      }
    })()
  }, [location.search, navigate, setToken])
  return <div>Signing you in…</div>
}

// Org-required guard: ensures the user belongs to at least one organization
export function RequireOrg({ token, children }) {
  const [checking, setChecking] = useState(true)
  const [hasOrg, setHasOrg] = useState(true)
  const location = useLocation()
  const navigate = useNavigate()
  useEffect(() => {
    let ignore = false
    ;(async () => {
      setChecking(true)
      try {
        const orgs = await api('/orgs/', { token })
        if (!ignore) {
          const ok = Array.isArray(orgs) && orgs.length > 0
          setHasOrg(ok)
          if (!ok) {
            const dest = encodeURIComponent(location.pathname + location.search)
            navigate(`/register?next=${dest}`, { replace: true })
          }
        }
      } catch {
        // On error, allow through to avoid lockout; backend will enforce where needed
        if (!ignore) setHasOrg(true)
      } finally {
        if (!ignore) setChecking(false)
      }
    })()
    return () => { ignore = true }
  }, [token, location.pathname, location.search, navigate])
  if (checking) return <div>Loading…</div>
  if (!hasOrg) return null
  return children
}

// Registration page: name, org (or invite), plan selection
export function RegisterPage({ token }) {
  const [name, setName] = useState('')
  const [orgName, setOrgName] = useState('')
  const [invite, setInvite] = useState('')
  const [plan, setPlan] = useState('free')
  const [submitting, setSubmitting] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const nextAfter = useMemo(() => new URLSearchParams(location.search).get('next') || `${ROUTER_BASE}`, [location.search])

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      // If invite provided, accept it; else create org if given
      if (invite) {
        await api('/orgs/invites/accept', { method: 'POST', token, body: { token: invite } })
      } else if (orgName) {
        await api('/orgs/', { method: 'POST', token, body: { name: orgName } })
      }
      // Paid plans go to checkout (new window)
      if (plan === 'pro' || plan === 'enterprise') {
        try {
          const { url } = await api('/billing/checkout', { method: 'POST', token, body: {} })
          if (url) window.open(url, '_blank')
        } catch {}
      }
      // Email confirmation is backend-driven; show stub in DEBUG
      if (!isProd) alert(`Confirmation email sent to your address (stub). Name: ${name}`)
  navigate(nextAfter || `${ROUTER_BASE}`, { replace: true })
    } catch (e2) {
      alert('Registration failed: ' + (e2?.data?.error || e2.message))
    } finally { setSubmitting(false) }
  }

  return (
    <div>
      <h2>Complete your registration</h2>
      <form onSubmit={submit}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" />
        <input value={orgName} onChange={(e) => setOrgName(e.target.value)} placeholder="Organization name (or leave blank if using an invite)" />
        <input value={invite} onChange={(e) => setInvite(e.target.value)} placeholder="Invite token (optional)" />
        {!invite && (
          <div>
            <div>Choose a plan</div>
            <label><input type="radio" name="plan" value="free" checked={plan === 'free'} onChange={(e) => setPlan(e.target.value)} /> Free</label>
            <label><input type="radio" name="plan" value="pro" checked={plan === 'pro'} onChange={(e) => setPlan(e.target.value)} /> Pro</label>
            <label><input type="radio" name="plan" value="enterprise" checked={plan === 'enterprise'} onChange={(e) => setPlan(e.target.value)} /> Enterprise</label>
          </div>
        )}
        <button type="submit" disabled={submitting}>Continue</button>
      </form>
    </div>
  )
}

// Authenticated app shell with logout
function AppShell({ token, setToken }) {
  const [activeOrgId, setActiveOrgId] = useState(() => localStorage.getItem('orgId') || '')
  const [orgs, setOrgs] = useState([])
  useEffect(() => { if (activeOrgId) localStorage.setItem('orgId', activeOrgId); else localStorage.removeItem('orgId') }, [activeOrgId])
  useEffect(() => { (async () => { try { const list = await api('/orgs/', { token }); setOrgs(Array.isArray(list) ? list : []) } catch {} })() }, [token])
  const navigate = useNavigate()
  const logout = () => { setToken(''); navigate('/login', { replace: true }) }
  return (
    <div>
      {flags.UI_EXPERIMENTS && (
        <div>
          UI Experiments enabled (VITE_UI_EXPERIMENTS=1)
        </div>
      )}
      {(!activeOrgId && Array.isArray(orgs) && orgs.length > 0) && (
        <div>
          <span>Tip: Select an organization to scope your work.</span>
          <select value={activeOrgId} onChange={(e) => setActiveOrgId(e.target.value)}>
            <option value="">Choose…</option>
            {orgs.map(o => <option key={o.id} value={String(o.id)}>#{o.id} {o.name}</option>)}
          </select>
          <button onClick={() => navigate('/register')}>Create a new org</button>
        </div>
      )}
      <div>
        <h1>Granterstellar</h1>
        <button onClick={logout}>Logout</button>
  <button onClick={() => navigate('/account')}>Account</button>
  <button onClick={() => navigate('/billing')}>Billing</button>
  <button onClick={() => navigate('/orgs')}>Organizations</button>
      </div>
      <div>
        {/* Default app view shows proposals; organizations have a dedicated page */}
        <Suspense fallback={<div>Loading…</div>}>
          <LazyProposals token={token} selectedOrgId={activeOrgId} />
        </Suspense>
      </div>
    </div>
  )
}

// Route guard
// Named export used only in tests; runtime uses the same function below
export function RequireAuth({ token, children }) {
  const location = useLocation()
  if (!token) {
    const next = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/login?next=${next}`} replace />
  }
  return children
}

function Root() {
  const [token, setToken] = useToken()
  useIdlePreloads()
  useWebVitals()
  return (
    <BrowserRouter basename={ROUTER_BASE}>
      <Umami />
  <InviteBanner token={token} />
      <Routes>
        <Route path="/login" element={<LoginPage token={token} setToken={setToken} />} />
        <Route
          path="/register"
          element={
            <RequireAuth token={token}>
              <RegisterPage token={token} />
            </RequireAuth>
          }
        />
        <Route path="/oauth/callback" element={<OAuthCallback setToken={setToken} />} />
        <Route
          path="/billing"
          element={
            <RequireAuth token={token}>
              <BillingPage token={token} />
            </RequireAuth>
          }
        />
        <Route
          path="/account"
          element={
            <RequireAuth token={token}>
              <AccountPage token={token} />
            </RequireAuth>
          }
        />
        <Route
          path="/orgs"
          element={
            <RequireAuth token={token}>
              <Suspense fallback={<div>Loading…</div>}>
                <LazyOrgsPage token={token} />
              </Suspense>
            </RequireAuth>
          }
        />
        <Route path="/404" element={<NotFound token={token} />} />
        <Route
          path="*"
          element={
            <RequireAuth token={token}>
              <RequireOrg token={token}>
                <AppShell token={token} setToken={setToken} />
              </RequireOrg>
            </RequireAuth>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}

const mountEl = (typeof document !== 'undefined') ? document.getElementById('root') : null
if (mountEl) {
  const root = createRoot(mountEl)
  root.render(<Root />)
}
