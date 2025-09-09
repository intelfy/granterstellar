import { useEffect, useState } from 'react'
import { api } from '../lib/core.js'
import { t } from '../keys.generated'

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
        <h2>{t('ui.orgs.heading')}</h2>
        <div>
          <input placeholder={t('ui.orgs.new_name_placeholder')} value={name} onChange={e => setName(e.target.value)} />
          <input placeholder={t('ui.orgs.description_placeholder')} value={desc} onChange={e => setDesc(e.target.value)} />
          <button onClick={createOrg}>{t('ui.orgs.create_button')}</button>
        </div>
      </div>
      <ul>
        {items.map(org => (
          <li key={org.id}>
            <div>
              <strong>#{org.id}</strong> {org.name}
              <span> {org.description}</span>
              <span> admin: {org.admin?.username}</span>
              <button onClick={() => { const open = selectedId === String(org.id); setSelectedId(open ? '' : String(org.id)); if (!open) { loadMembers(org.id); loadInvites(org.id) } }}>{selectedId === String(org.id) ? t('ui.orgs.hide_button') : t('ui.orgs.manage_button')}</button>
              <button onClick={() => removeOrg(org.id)}>{t('ui.orgs.delete_button')}</button>
            </div>
            {selectedId === String(org.id) && (
              <div>
                <div>
                  <div>{t('ui.orgs.members_heading')}</div>
                  <div>{t('ui.orgs.invite_heading')}</div>
                  <input placeholder={t('ui.orgs.invite_email_placeholder')} value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} />
                  <select value={inviteRole} onChange={e => setInviteRole(e.target.value)}>
                    <option value="member">{t('ui.orgs.member_role_member')}</option>
                    <option value="admin">{t('ui.orgs.member_role_admin')}</option>
                  </select>
                  <button onClick={() => inviteMember(org.id)}>{t('ui.orgs.invite_button')}</button>
                </div>
                <ul>
                  {(membersByOrg[org.id] || []).map(m => (
                    <li key={m.user.id}>
                      {m.user.username} ({m.user.id}) — {m.role}
                      <button onClick={() => removeMember(org.id, m.user.id)}>{t('ui.orgs.revoke_button')}</button>
                    </li>
                  ))}
                </ul>
                <div>
                  <div>{t('ui.orgs.pending_invites_heading')}</div>
                  <ul>
                    {(invitesByOrg[org.id] || []).map(inv => (
                      <li key={inv.id}>
                        {inv.email} — {inv.role} {inv.accepted_at ? t('ui.orgs.accepted') : inv.revoked_at ? t('ui.orgs.revoked') : t('ui.orgs.pending')}
                        {!inv.accepted_at && !inv.revoked_at && (
                          <>
                            <button onClick={() => revokeInvite(org.id, inv.id)}>{t('ui.orgs.revoke_button')}</button>
                            <span> {t('ui.orgs.token_label',{ value: inv.token })}</span>
                          </>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <div>{t('ui.orgs.transfer_heading')}</div>
                  <input placeholder={t('ui.orgs.new_admin_placeholder')} value={transferUserId} onChange={e => setTransferUserId(e.target.value)} />
                  <button onClick={() => transfer(org.id)}>{t('ui.orgs.transfer_button')}</button>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
