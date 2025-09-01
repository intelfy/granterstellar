import { useEffect, useState } from 'react'
import { api } from '../lib/core.js'

export default function AccountPage({ token }) {
  const [profile, setProfile] = useState({ username: '', email: '', first_name: '', last_name: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [ok, setOk] = useState(false)
  useEffect(() => { (async () => {
    try {
      const me = await api('/me', { token })
      const u = me?.user || {}
      setProfile({
        username: String(u.username || ''),
        email: String(u.email || ''),
        first_name: String(u.first_name || ''),
        last_name: String(u.last_name || ''),
      })
    } catch {}
  })() }, [token])
  const save = async (e) => {
    e.preventDefault()
    setLoading(true); setError(''); setOk(false)
    try {
      await api('/me', { method: 'PATCH', token, body: profile })
      setOk(true)
    } catch (e2) {
      const code = e2?.data?.error
      const map = {
        invalid_email: 'Please enter a valid email address.',
        invalid_username: 'Username must be 2-64 chars (letters, numbers, _ . -).',
        username_taken: 'That username is already taken.',
        no_changes: 'Make a change before saving.',
      }
      setError(map[code] || 'Save failed')
    } finally { setLoading(false) }
  }
  return (
    <section>
      <h2>Account</h2>
      <form onSubmit={save}>
        <div>
          <label htmlFor="pf-username">Username</label>
          <input id="pf-username" data-testid="pf-username" value={profile.username} onChange={(e) => setProfile(p => ({ ...p, username: e.target.value }))} />
        </div>
        <div>
          <label htmlFor="pf-email">Email</label>
          <input id="pf-email" data-testid="pf-email" value={profile.email} onChange={(e) => setProfile(p => ({ ...p, email: e.target.value }))} />
        </div>
        <div>
          <label htmlFor="pf-first">First name</label>
          <input id="pf-first" data-testid="pf-first" value={profile.first_name} onChange={(e) => setProfile(p => ({ ...p, first_name: e.target.value }))} />
        </div>
        <div>
          <label htmlFor="pf-last">Last name</label>
          <input id="pf-last" data-testid="pf-last" value={profile.last_name} onChange={(e) => setProfile(p => ({ ...p, last_name: e.target.value }))} />
        </div>
        <button type="submit" data-testid="pf-save" disabled={loading}>Save</button>
      </form>
      {ok && <div data-testid="pf-ok">Saved</div>}
      {error && <div role="alert">{error}</div>}
    </section>
  )
}
