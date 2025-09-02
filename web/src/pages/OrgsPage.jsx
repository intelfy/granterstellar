import { useEffect, useState } from 'react'
import { api } from '../lib/core.js'

export default function OrgsPage({ token }) {
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
    </section>
  )
}
