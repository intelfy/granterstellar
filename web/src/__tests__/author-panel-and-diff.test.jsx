import React from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { AuthorPanel, SectionDiff } from '../pages/Dashboard.jsx'

// Simple Response polyfill for Node test env
class Response {
  constructor(body, init) { this._body = body; this.status = init?.status || 200; this.ok = this.status >= 200 && this.status < 300 }
  async json() { try { return JSON.parse(this._body || '{}') } catch { return {} } }
}

describe('SectionDiff', () => {
  it('highlights insertions and deletions', async () => {
    render(<SectionDiff before={'Hello world'} after={'Hello brave world'} />)
    // Should mark an insertion for 'brave'
    const ins = await screen.findAllByTestId('diff-ins')
    expect(ins.some(n => n.textContent?.includes('brave'))).toBe(true)
  })
})

describe('AuthorPanel notes', () => {
  it('saves an internal note onto proposal.meta', async () => {
    const token = 't'
    const proposal = { id: 1, author: 2, content: { meta: { title: 'T' }, sections: {} }, schema_version: 'v1', created_at: new Date().toISOString(), last_edited: new Date().toISOString() }
    // Mock /api/me and PATCH /api/proposals/1
    global.fetch = vi.fn((url, opts) => {
      const u = url.toString()
      if (u.endsWith('/api/me') && (!opts || opts.method === 'GET')) {
        return Promise.resolve(new Response(JSON.stringify({ user: { id: 2, username: 'demo' } }), { status: 200 }))
      }
      if (u.endsWith('/api/proposals/1/') && opts && opts.method === 'PATCH') {
        const body = JSON.parse(opts.body)
        // Ensure the note persisted
        if (body?.content?.meta?.note !== 'hello note') {
          return Promise.resolve(new Response('{}', { status: 400 }))
        }
        return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }))
      }
      // plan/write endpoints may be probed; return defaults
      return Promise.resolve(new Response('{}', { status: 200 }))
    })

    render(<AuthorPanel token={token} orgId={''} proposal={proposal} onSaved={() => {}} />)

    const textarea = await screen.findByTestId('note-text')
    fireEvent.change(textarea, { target: { value: 'hello note' } })

    const save = screen.getByTestId('note-save')
    fireEvent.click(save)

    await waitFor(() => {
      // Validate that our PATCH endpoint was called
      expect(global.fetch).toHaveBeenCalledWith('/api/proposals/1/', expect.objectContaining({ method: 'PATCH' }))
    })
  })
})
