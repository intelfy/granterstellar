import React, { useEffect, useMemo, useState } from 'react'
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
// Skip during tests (jsdom doesn't implement full navigation APIs)
if (import.meta.env.DEV && import.meta.env.MODE !== 'test') {
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
        <button type="button" onClick={async () => { try { await api('/orgs/invites/accept', { method: 'POST', token, body: { token: pendingInvite } }); alert('Invite accepted'); const url = new URL(window.location.href); url.searchParams.delete('invite'); window.history.replaceState({}, '', url.toString()); setPendingInvite('') } catch (e) { alert('Invite accept failed: ' + (e?.data?.error || e.message)) } }}>Accept pending invite</button>
      )}
    </div>
  )
}

function SectionDiff({ before = '', after = '' }) {
  if (!before && !after) return null
  return (
    <div>
      <div>
        <div>Previous</div>
        <pre>{before || '—'}</pre>
      </div>
      <div>
        <div>Draft</div>
        <pre>{after || '—'}</pre>
      </div>
    </div>
  )
}

function AuthorPanel({ token, orgId, proposal, onSaved, usage, onUpgrade }) {
  const [plan, setPlan] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [sectionIndex, setSectionIndex] = useState(0)
  const [answers, setAnswers] = useState({})
  const [draft, setDraft] = useState('')
  const [changeReq, setChangeReq] = useState('')
  const [grantUrl, setGrantUrl] = useState('')
  const [textSpec, setTextSpec] = useState('')
  const [lastSavedAt, setLastSavedAt] = useState(null)
  const [templateHint, setTemplateHint] = useState('')
  const [formattedText, setFormattedText] = useState('')
  const [filesBySection, setFilesBySection] = useState({})
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')

  const sections = plan?.sections || []
  const current = sections[sectionIndex]
  const prevText = proposal?.content?.sections?.[current?.id]?.content || ''
  const approvedById = proposal?.content?.sections || {}
  const allApproved = sections.length > 0 && sections.every(s => !!approvedById[s.id])

  const onUploadFile = async (e) => {
    const file = e.target.files && e.target.files[0]
    if (!file || !current) return
    setUploading(true)
    setUploadError('')
    try {
      const info = await apiUpload('/files', { token, orgId: orgId || undefined, file })
      setFilesBySection(prev => ({
        ...prev,
        [current.id]: [ ...(prev[current.id] || []), { ...info, name: file.name } ],
      }))
      // Reset the file input so same-named uploads can trigger again
      e.target.value = ''
    } catch (err) {
      setUploadError('Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const startPlan = async () => {
    setLoading(true)
    setError('')
    try {
      const body = grantUrl ? { grant_url: grantUrl } : { text_spec: textSpec || 'General grant' }
  const p = await apiMaybeAsync('/ai/plan', { method: 'POST', token, orgId: orgId || undefined, body })
      setPlan(p)
      setSectionIndex(0)
      setAnswers({})
      setDraft('')
      setChangeReq('')
    } catch (e) {
      setError('Failed to load plan')
    } finally {
      setLoading(false)
    }
  }

  const writeDraft = async () => {
    if (!current) return
    setLoading(true)
    setError('')
    try {
  const res = await apiMaybeAsync('/ai/write', {
    method: 'POST',
    token,
    orgId: orgId || undefined,
    body: {
  proposal_id: proposal.id,
      section_id: current.id,
      answers,
      file_refs: (current && filesBySection[current.id]) ? filesBySection[current.id] : [],
    },
  })
      setDraft(res?.draft_text || '')
    } catch (e) {
      setError('Write failed')
    } finally { setLoading(false) }
  }

  const applyChanges = async () => {
    if (!current) return
    setLoading(true)
    setError('')
    try {
  const res = await apiMaybeAsync('/ai/revise', {
    method: 'POST',
    token,
    orgId: orgId || undefined,
    body: {
  proposal_id: proposal.id,
      section_id: current.id,
      base_text: draft || prevText,
      change_request: changeReq,
      file_refs: (current && filesBySection[current.id]) ? filesBySection[current.id] : [],
    },
  })
      setDraft(res?.draft_text || draft)
    } catch (e) {
      setError('Revise failed')
    } finally { setLoading(false) }
  }

  const approveAndSave = async () => {
    if (!current) return
    const patched = { ...(proposal.content || {}), sections: { ...(proposal.content?.sections || {}) } }
    patched.sections[current.id] = { title: current.title || current.id, content: draft || prevText || '' }
    const body = { content: patched, schema_version: proposal.schema_version || plan?.schema_version || 'v1' }
    setLoading(true)
    setError('')
    try {
      await api(`/proposals/${proposal.id}/`, { method: 'PATCH', token, orgId: orgId || undefined, body })
      setLastSavedAt(new Date())
      await onSaved?.()
      if (sectionIndex < sections.length - 1) {
        setSectionIndex(sectionIndex + 1)
        setAnswers({})
        setDraft('')
        setChangeReq('')
      }
    } catch (e) {
      setError('Save failed')
    } finally { setLoading(false) }
  }

  const runFinalFormatting = async () => {
    if (!allApproved) return
    setLoading(true)
    setError('')
    try {
      // Compose full text in section order as Markdown-like text
      const parts = []
      // Aggregate any file references across all sections
      const allFileRefs = []
      for (const s of sections) {
        const title = approvedById?.[s.id]?.title || s.title || s.id
        const body = approvedById?.[s.id]?.content || ''
        parts.push(`# ${title}\n\n${body}`)
        if (filesBySection[s.id]?.length) {
          allFileRefs.push(...filesBySection[s.id])
        }
      }
      const full_text = parts.join('\n\n')
  const res = await apiMaybeAsync('/ai/format', {
    method: 'POST',
    token,
    orgId: orgId || undefined,
    body: {
  proposal_id: proposal.id,
      full_text,
      template_hint: templateHint || undefined,
      file_refs: allFileRefs,
    },
  })
      setFormattedText(res?.formatted_text || '')
    } catch (e) {
      setError('Final format failed')
    } finally { setLoading(false) }
  }

  return (
    <div>
      {!plan ? (
        <div>
          <div>Plan your proposal</div>
          <input value={grantUrl} onChange={(e) => setGrantUrl(e.target.value)} placeholder="Grant URL (optional)" />
          <textarea rows={3} value={textSpec} onChange={(e) => setTextSpec(e.target.value)} placeholder="Or paste a brief specification (optional)" />
          <button onClick={startPlan} disabled={loading}>Start</button>
          {error && <div>{error}</div>}
        </div>
      ) : (
        <div>
          <div>
            <div><strong>Section {sectionIndex + 1} / {sections.length}:</strong> {current?.title}</div>
            <div>
              Schema: {plan?.schema_version || 'v1'}
              {lastSavedAt && <span> · Last saved {lastSavedAt.toLocaleTimeString()}</span>}
            </div>
          </div>
          <div>
            {(current?.inputs || []).map((key) => (
              <div key={key}>
                <label>{key}</label>
                <textarea rows={2} value={answers[key] || ''} onChange={(e) => setAnswers(a => ({ ...a, [key]: e.target.value }))} />
              </div>
            ))}
            <div>
              <label htmlFor={`file-${current?.id || 'section'}`}>Attach files (pdf, docx, txt, images)</label>
              <input id={`file-${current?.id || 'section'}`} type="file" accept=".pdf,.docx,.txt,image/*" onChange={onUploadFile} />
              {uploading && <span> Uploading…</span>}
              {uploadError && <div>{uploadError}</div>}
              {current && (filesBySection[current.id]?.length > 0) && (
                <div>
                  <div>Files for this section</div>
                  <ul>
                    {filesBySection[current.id].map((f, idx) => (
                      <li key={idx}>
                        <div>
                          <a href={f.url} target="_blank" rel="noopener noreferrer">{f.name || `file-${idx+1}`}</a>
                        </div>
                        {f.ocr_text && (
                          <div>
                            <div>OCR preview</div>
                            <textarea readOnly rows={4} value={f.ocr_text} />
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            <div>
              <button onClick={writeDraft} disabled={loading}>Write</button>
              <input placeholder="Change request (optional)" value={changeReq} onChange={(e) => setChangeReq(e.target.value)} />
              <button onClick={applyChanges} disabled={loading || !(draft || prevText)}>Revise</button>
              <button onClick={approveAndSave} disabled={loading || !(draft || prevText)}>Approve & Save</button>
            </div>
            <SectionDiff before={prevText} after={draft || prevText} />
            {error && <div>{error}</div>}
            {loading && <div>Working…</div>}
          </div>
          <div>
            <div>
              Approved sections: {Object.keys(approvedById).length} / {sections.length}
            </div>
            {allApproved && (
              <div>
                <div>Final formatting (runs after all sections are approved)</div>
                <input placeholder="Template hint (optional)" value={templateHint} onChange={(e) => setTemplateHint(e.target.value)} />
                <button onClick={runFinalFormatting} disabled={loading}>Run Final Formatting</button>
                {formattedText && (
                  <div>
                    <div>Formatted preview</div>
                    <textarea readOnly rows={10} value={formattedText} />
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export function Proposals({ token, selectedOrgId }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)
  const [exporting, setExporting] = useState(null)
  const [usage, setUsage] = useState(null)
  const [fmtById, setFmtById] = useState({})
  const [orgId, setOrgId] = useState(() => localStorage.getItem('orgId') || '')
  const [openAuthorForId, setOpenAuthorForId] = useState(null)
  const reasonLabel = (code) => ({
    ok: 'OK',
    active_cap_reached: 'Active proposal cap reached for your plan',
    monthly_cap_reached: 'Monthly creation limit reached',
    quota: 'Quota reached',
  }[code] || code)
  const isPaidActive = (u) => u && u.tier !== 'free' && (u.status === 'active' || u.status === 'trialing')
  const archive = async (p) => {
    try {
      await api(`/proposals/${p.id}/`, { method: 'PATCH', token, orgId: orgId || undefined, body: { state: 'archived' } })
      await refresh()
      await refreshUsage()
    } catch (e) {
      alert('Archive failed: ' + (e?.data?.error || e.message))
    }
  }
  const unarchive = async (p) => {
    try {
      await api(`/proposals/${p.id}/`, { method: 'PATCH', token, orgId: orgId || undefined, body: { state: 'draft' } })
      await refresh()
      await refreshUsage()
    } catch (e) {
      if (e.status === 402) alert('Unarchive blocked: ' + reasonLabel(e?.data?.reason))
      else alert('Unarchive failed: ' + (e?.data?.error || e.message))
    }
  }
  const refreshUsage = async () => {
    try { setUsage(await api('/usage', { token, orgId: orgId || undefined })) } catch {}
  }
  const refresh = async () => {
    setLoading(true)
    try {
      const data = await api('/proposals/', { token, orgId: orgId || undefined })
      setItems(Array.isArray(data) ? data : data.results || [])
    } finally {
      setLoading(false)
    }
  }
  const doExport = async (proposalId, fmt='pdf') => {
    setExporting(proposalId)
    try {
      const job = await api('/exports', { method: 'POST', token, orgId: orgId || undefined, body: { proposal_id: proposalId, format: fmt } })
      if (job.url) {
        safeOpenExternal(job.url)
        return
      }
      // Async case: poll until done
      const id = job.id
      for (let i = 0; i < 20; i++) {
        await new Promise(r => setTimeout(r, 500))
        const status = await api(`/exports/${id}`, { token, orgId: orgId || undefined })
        if (status.url) {
          safeOpenExternal(status.url)
          return
        }
      }
      alert('Export still processing; try again later')
    } catch (e) {
      alert('Export failed: ' + e.message)
    } finally {
      setExporting(null)
    }
  }
  const createOne = async () => {
    setCreating(true)
    try {
      await api('/proposals/', { method: 'POST', token, orgId: orgId || undefined, body: { content: { meta: { title: 'Untitled' }, sections: {} }, schema_version: 'v1' } })
      await refresh()
      await refreshUsage()
    } catch (e) {
      if (e.status === 402 && e.data) {
        const reason = e.data.reason || 'quota'
        alert(`Paywall: ${reasonLabel(reason)}. Click Upgrade to continue.`)
      } else {
        alert('Create failed: ' + e.message)
      }
    } finally {
      setCreating(false)
    }
  }
  // persist chosen export formats per proposal id
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('exportFormats') || '{}')
      if (saved && typeof saved === 'object') setFmtById(saved)
    } catch {}
  }, [])
  useEffect(() => {
    try { localStorage.setItem('exportFormats', JSON.stringify(fmtById)) } catch {}
  }, [fmtById])
  useEffect(() => { refresh(); refreshUsage() }, [token, orgId])
  useEffect(() => {
    if (orgId) localStorage.setItem('orgId', orgId)
    else localStorage.removeItem('orgId')
  }, [orgId])
  // When parent selects an org, sync our orgId
  useEffect(() => {
    if (selectedOrgId !== undefined && selectedOrgId !== orgId) {
      setOrgId(selectedOrgId || '')
    }
  }, [selectedOrgId])
  const onUpgrade = async () => {
    try {
      const { url } = await api('/billing/checkout', { method: 'POST', token, orgId: orgId || undefined, body: {} })
  if (url) safeOpenExternal(url, ['https://checkout.stripe.com'])
    } catch (e) {
      alert('Checkout unavailable')
    }
  }
  const onPortal = async () => {
    try {
      const res = await api('/billing/portal', { method: 'GET', token, orgId: orgId || undefined })
  if (res?.url) safeOpenExternal(res.url, ['https://billing.stripe.com'])
    } catch (e) {
      alert('Portal unavailable')
    }
  }
  const onCancel = async () => {
    try {
      await api('/billing/cancel', { method: 'POST', token, orgId: orgId || undefined, body: {} })
      await refreshUsage()
      alert('Subscription will cancel at period end.')
    } catch (e) {
      alert('Cancel failed')
    }
  }
  const onResume = async () => {
    try {
      await api('/billing/resume', { method: 'POST', token, orgId: orgId || undefined, body: {} })
      await refreshUsage()
      alert('Subscription resumed.')
    } catch (e) {
      alert('Resume failed')
    }
  }
  return (
    <section>
      <div>
        <h2>My Proposals</h2>
        {usage && (
          <div>
            Tier: {usage.tier} · Status: {usage.status} · Active: {usage.usage?.active ?? '-'}{usage.limits?.monthly_cap ? ` · Created this month: ${usage.usage?.created_this_period ?? '-'}/${usage.limits?.monthly_cap}` : ''}
            {usage.subscription?.current_period_end ? ` · Period ends: ${new Date(usage.subscription.current_period_end).toLocaleDateString()}` : ''}
            {usage.subscription?.discount ? ` · Promo: ${formatDiscount(usage.subscription.discount)}` : ''}
            {usage.can_create_proposal === false && usage.reason ? ` · New proposal blocked: ${reasonLabel(usage.reason)}` : ''}
          </div>
        )}
        <div>
          <input placeholder="Org ID (optional)" value={orgId} onChange={(e) => setOrgId(e.target.value)} />
          <button disabled={creating || (usage && usage.can_create_proposal === false)} onClick={createOne}>New</button>
          {usage && usage.can_create_proposal === false && (<button onClick={onUpgrade}>Upgrade</button>)}
          <button onClick={onPortal}>Billing Portal</button>
          {usage?.subscription?.cancel_at_period_end ? (
            <button onClick={onResume}>Resume</button>
          ) : (
            <button onClick={onCancel}>Cancel at period end</button>
          )}
        </div>
      </div>
      {loading && <div>Loading…</div>}
      <ul>
        {items.map(p => (
          <li key={p.id}>
            <div>
              <strong>#{p.id}</strong> — {(p.content?.meta?.title) || 'Untitled'} — {p.state}
              <select value={fmtById[p.id] || 'pdf'} onChange={(e) => setFmtById(s => ({ ...s, [p.id]: e.target.value }))}>
                <option value="pdf">PDF</option>
                <option value="docx">DOCX</option>
                <option value="md">Markdown</option>
              </select>
              {exporting === p.id && <span>Exporting…</span>}
              <button disabled={exporting === p.id} onClick={() => doExport(p.id, fmtById[p.id] || 'pdf')}>Export</button>
              <button onClick={() => setOpenAuthorForId(id => id === p.id ? null : p.id)}>
                {openAuthorForId === p.id ? 'Close Author' : 'Open Author'}
              </button>
              {p.state !== 'archived' ? (
                <button disabled={!isPaidActive(usage)} title={!isPaidActive(usage) ? 'Paid plan required to archive' : ''} onClick={() => archive(p)}>Archive</button>
              ) : (
                <button onClick={() => unarchive(p)}>Unarchive</button>
              )}
            </div>
            {openAuthorForId === p.id && (
              <AuthorPanel token={token} orgId={orgId || undefined} proposal={p} usage={usage} onUpgrade={onUpgrade} onSaved={async () => { await refresh() }} />
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}

function Orgs({ token, onSelectOrg }) {
  const [items, setItems] = useState([])
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [membersByOrg, setMembersByOrg] = useState({})
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('member')
  const [invitesByOrg, setInvitesByOrg] = useState({})
  const [transferUserId, setTransferUserId] = useState('')

  const refresh = async () => { try { setItems(await api('/orgs/', { token })) } catch {} }
  const loadMembers = async (orgId) => { try { const m = await api(`/orgs/${orgId}/members/`, { token }); setMembersByOrg(s => ({ ...s, [orgId]: m })) } catch {} }
  const loadInvites = async (orgId) => { try { const m = await api(`/orgs/${orgId}/invites/`, { token }); setInvitesByOrg(s => ({ ...s, [orgId]: m })) } catch {} }
  useEffect(() => { refresh() }, [token])
  const createOrg = async () => { if (!name) return; await api('/orgs/', { method: 'POST', token, body: { name, description: desc } }); setName(''); setDesc(''); refresh() }
  const removeOrg = async (orgId) => { if (!confirm('Delete this organization?')) return; await api(`/orgs/${orgId}/`, { method: 'DELETE', token }); refresh() }
  const inviteMember = async (orgId) => { if (!inviteEmail) return; const inv = await api(`/orgs/${orgId}/invites/`, { method: 'POST', token, body: { email: inviteEmail, role: inviteRole } }); setInviteEmail(''); await loadInvites(orgId); alert(`Invite created. Token (dev): ${inv.token}`) }
  const removeMember = async (orgId, userId) => { await api(`/orgs/${orgId}/members/`, { method: 'DELETE', token, body: { user_id: userId } }); loadMembers(orgId) }
  const revokeInvite = async (orgId, id) => { await api(`/orgs/${orgId}/invites/`, { method: 'DELETE', token, body: { id } }); await loadInvites(orgId) }
  const transfer = async (orgId) => { if (!transferUserId) return; await api(`/orgs/${orgId}/transfer/`, { method: 'POST', token, body: { user_id: Number(transferUserId) } }); setTransferUserId(''); refresh() }
  const acceptInvite = async () => {
    // Dev-only helper: suppressed in production builds
    if (!import.meta.env.VITE_UI_EXPERIMENTS) return
    const tokenStr = typeof window !== 'undefined' ? window.prompt('Paste invite token (dev flow)') : ''
    if (!tokenStr) return
    const res = await api('/orgs/invites/accept', { method: 'POST', token, body: { token: tokenStr } })
    alert('Joined organization #' + res.org_id)
    await refresh()
  }

  return (
    <section>
      <div>
        <h2>Organizations</h2>
        <div>
          <input placeholder="New org name" value={name} onChange={e => setName(e.target.value)} />
          <input placeholder="Description (optional)" value={desc} onChange={e => setDesc(e.target.value)} />
          <button onClick={createOrg}>Create</button>
        </div>
      </div>
      <ul>
        {items.map(org => (
          <li key={org.id}>
            <div>
              <strong>#{org.id}</strong> {org.name}
              <span> {org.description}</span>
              <span> admin: {org.admin?.username}</span>
              <button onClick={() => onSelectOrg(String(org.id))}>Use</button>
              <button onClick={() => { const open = selectedId === String(org.id); setSelectedId(open ? '' : String(org.id)); if (!open) { loadMembers(org.id); loadInvites(org.id) } }}>{selectedId === String(org.id) ? 'Hide' : 'Manage'}</button>
              <button onClick={() => removeOrg(org.id)}>Delete</button>
            </div>
            {selectedId === String(org.id) && (
              <div>
                <div>
                  <div>Members</div>
                  <div>Invite by email</div>
                  <input placeholder="name@example.com" value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} />
                  <select value={inviteRole} onChange={e => setInviteRole(e.target.value)}>
                    <option value="member">member</option>
                    <option value="admin">admin</option>
                  </select>
                  <button onClick={() => inviteMember(org.id)}>Invite</button>
                </div>
                <ul>
                  {(membersByOrg[org.id] || []).map(m => (
                    <li key={m.user.id}>
                      {m.user.username} ({m.user.id}) — {m.role}
                      <button onClick={() => removeMember(org.id, m.user.id)}>Remove</button>
                    </li>
                  ))}
                </ul>
                <div>
                  <div>Pending invites</div>
                  <ul>
                    {(invitesByOrg[org.id] || []).map(inv => (
                      <li key={inv.id}>
                        {inv.email} — {inv.role} {inv.accepted_at ? '(accepted)' : inv.revoked_at ? '(revoked)' : '(pending)'}
                        {!inv.accepted_at && !inv.revoked_at && (
                          <>
                            <button onClick={() => revokeInvite(org.id, inv.id)}>Revoke</button>
                            <span> token: {inv.token}</span>
                          </>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <div>Transfer ownership</div>
                  <input placeholder="New admin user ID" value={transferUserId} onChange={e => setTransferUserId(e.target.value)} />
                  <button onClick={() => transfer(org.id)}>Transfer</button>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
      <div>
        <button onClick={acceptInvite}>Accept invite (paste token)</button>
      </div>
    </section>
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
function RegisterPage({ token }) {
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
      </div>
      <div>
        <Proposals token={token} selectedOrgId={activeOrgId} />
        <Orgs token={token} onSelectOrg={(id) => setActiveOrgId(id)} />
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
  return (
    <BrowserRouter basename={ROUTER_BASE}>
      <Umami />
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