import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { api, apiBase, isProd, sanitizeNext, ROUTER_BASE } from '../lib/core.js'

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

export function LoginPage({ token, setToken }) {
  const [username, setUsername] = useState('demo')
  const [password, setPassword] = useState('demo12345')
  const [email, setEmail] = useState('')
  const [pendingInvite, setPendingInvite] = useState('')
  const [oauthError, setOauthError] = useState('')
  const navigate = useNavigate()
  const location = useLocation()
  const next = useMemo(() => new URLSearchParams(location.search).get('next') || `${ROUTER_BASE}`, [location.search])
  const safeNext = useMemo(() => sanitizeNext(next), [next])
  useEffect(() => {
    if (token) {
      navigate(safeNext, { replace: true })
    }
  }, [token, safeNext, navigate])
  useEffect(() => {
    const url = new URL(window.location.href)
    const inv = url.searchParams.get('invite')
    if (inv) setPendingInvite(inv)
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
      if (safeNext) sessionStorage.setItem('postLoginNext', safeNext)
      sessionStorage.setItem('oauthProvider', 'google')
      const url = new URL(window.location.href)
      const inv = url.searchParams.get('invite')
      const qs = inv ? `?invite=${encodeURIComponent(inv)}` : ''
      const data = await api(`/oauth/google/start${qs}`, { token })
      if (data?.auth_url) {
        try {
          const u = new URL(data.auth_url)
          const isGoogle = (u.origin === 'https://accounts.google.com' && u.pathname === '/o/oauth2/v2/auth')
          const isGitHub = (u.origin === 'https://github.com' && u.pathname === '/login/oauth/authorize')
          const isFacebook = (u.origin === 'https://www.facebook.com' && (/^\/v\d+(?:\.\d+)?\/dialog\/oauth$/.test(u.pathname) || u.pathname === '/dialog/oauth'))
          if (isGoogle || isGitHub || isFacebook) {
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
      if (invite) {
        await api('/orgs/invites/accept', { method: 'POST', token, body: { token: invite } })
      } else if (orgName) {
        await api('/orgs/', { method: 'POST', token, body: { name: orgName } })
      }
      if (plan === 'pro' || plan === 'enterprise') {
        try {
          const { url } = await api('/billing/checkout', { method: 'POST', token, body: {} })
          if (url) window.open(url, '_blank')
        } catch {}
      }
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
