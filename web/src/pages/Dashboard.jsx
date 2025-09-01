import { useEffect, useState } from 'react'
import { api, apiMaybeAsync, apiUpload, safeOpenExternal, openDebugLocal, formatDiscount } from '../lib/core.js'

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
      const parts = []
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

function Proposals({ token, selectedOrgId }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)
  const [exporting, setExporting] = useState(null)
  const [usage, setUsage] = useState(null)
  const [usageLoaded, setUsageLoaded] = useState(false)
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
    try {
      const u = await api('/usage', { token, orgId: orgId || undefined })
      setUsage(u)
    } catch {
    } finally {
      setUsageLoaded(true)
    }
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
      if (usage && usage.can_create_proposal === false) {
        const reason = usage.reason || 'quota'
        alert(`Paywall: ${reasonLabel(reason)}. Click Upgrade to continue.`)
        return
      }
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
  useEffect(() => {
    if (selectedOrgId !== undefined && selectedOrgId !== orgId) {
      setOrgId(selectedOrgId || '')
    }
  }, [selectedOrgId])
  const onUpgrade = async () => {
    try {
      const { url } = await api('/billing/checkout', { method: 'POST', token, orgId: orgId || undefined, body: {} })
      if (url) {
        try {
          const u = new URL(url)
          if (!openDebugLocal(u.toString())) {
            safeOpenExternal(u.toString(), ['https://checkout.stripe.com'])
          }
        } catch {
          openDebugLocal(url)
        }
        await refreshUsage()
      }
    } catch (e) {
      alert('Checkout unavailable')
    }
  }
  const onPortal = async () => {
    try {
      const res = await api('/billing/portal', { method: 'GET', token, orgId: orgId || undefined })
      if (res?.url) {
        try {
          const u = new URL(res.url)
          if (!openDebugLocal(u.toString())) {
            safeOpenExternal(u.toString(), ['https://billing.stripe.com'])
          }
        } catch {
          openDebugLocal(res.url)
        }
      }
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
            {usage.subscription?.discount ? (
              <> · <span data-testid="promo-banner" aria-label="active-promo">Promo: {formatDiscount(usage.subscription.discount)}</span></>
            ) : ''}
            {usage.can_create_proposal === false && usage.reason ? ` · New proposal blocked: ${reasonLabel(usage.reason)}` : ''}
          </div>
        )}
        <div>
          <input placeholder="Org ID (optional)" value={orgId} onChange={(e) => setOrgId(e.target.value)} />
          <button disabled={creating || !usageLoaded || (usage && usage.can_create_proposal === false)} onClick={createOne}>New</button>
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

export default function Dashboard({ token, selectedOrgId, onSelectOrg }) {
  return (
    <div>
      <div>
        <Proposals token={token} selectedOrgId={selectedOrgId} />
        <Orgs token={token} onSelectOrg={onSelectOrg} />
      </div>
    </div>
  )
}
