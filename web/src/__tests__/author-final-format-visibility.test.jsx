import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import React from 'react'
import { Proposals } from '../main.jsx'

function mockFetch(routes) {
  const fn = vi.fn(async (url, opts) => {
    const path = String(url).replace(/^[^/]*\/api/, '')
    const key = `${opts?.method || 'GET'} ${path}`
    const handler = routes[key]
    if (!handler) return new Response(JSON.stringify({}), { status: 404 })
    const body = opts?.body ? JSON.parse(opts.body) : null
    const res = await handler({ path, body, opts })
    return new Response(JSON.stringify(res.body || {}), { status: res.status || 200, headers: { 'Content-Type': 'application/json' } })
  })
  global.fetch = fn
  return fn
}

describe('Author final-format visibility', () => {
  it('hides final-format controls until all sections approved', async () => {
    const token = 't'
    const proposal = { id: 1, content: { meta: { title: 'T' }, sections: {} }, schema_version: 'v1', state: 'draft' }
    const serverState = { proposal: JSON.parse(JSON.stringify(proposal)) }
    const routes = {
      'GET /proposals/': async () => ({ body: [serverState.proposal] }),
      'GET /usage': async () => ({ body: { tier: 'pro', status: 'active' } }),
      'POST /ai/plan': async () => ({ body: { schema_version: 'v1', sections: [ { id: 'summary', title: 'Executive Summary', inputs: [] }, { id: 'narrative', title: 'Project Narrative', inputs: [] } ] } }),
      'POST /ai/write': async () => ({ body: { draft_text: 'Draft S' } }),
      'PATCH /proposals/1/': async ({ body }) => { serverState.proposal = { ...(serverState.proposal || {}), ...body, id: 1 }; return { body: serverState.proposal, status: 200 } },
    }
    mockFetch(routes)

    render(<Proposals token={token} />)

    await screen.findByText(/My Proposals/i)
    fireEvent.click(await screen.findByRole('button', { name: /Open Author/i }))
    fireEvent.click(await screen.findByRole('button', { name: /^Start$/ }))
    await screen.findByText(/Section 1 \/ 2/i)
    fireEvent.click(await screen.findByRole('button', { name: /^Write$/ }))
    await screen.findByText(/Draft/i)
    fireEvent.click(await screen.findByRole('button', { name: /Approve & Save/i }))
    await screen.findByText(/Section 2 \/ 2/i)

    // Final-format controls should NOT be visible yet (one section remaining)
    const runBtns = screen.queryAllByRole('button', { name: /Run Final Formatting/i })
    expect(runBtns.length).toBe(0)
  })
})
