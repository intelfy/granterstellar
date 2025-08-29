import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import React from 'react'
import { Proposals } from '../main.jsx'

// Minimal fetch mock with routing logic used in main.jsx's api()
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

describe('Author final-format flow', () => {
  it('shows final-format only after all sections approved and calls /ai/format', async () => {
    const token = 't'
  const proposal = { id: 1, content: { meta: { title: 'T' }, sections: { summary: { title: 'Executive Summary', content: 'S' } } }, schema_version: 'v1', state: 'draft' }
  const serverState = { proposal: JSON.parse(JSON.stringify(proposal)) }
    const routes = {
  'GET /proposals/': async () => ({ body: [serverState.proposal] }),
      'GET /usage': async () => ({ body: { tier: 'pro', status: 'active' } }),
      'POST /ai/plan': async () => ({ body: { schema_version: 'v1', sections: [ { id: 'summary', title: 'Executive Summary', inputs: [] }, { id: 'narrative', title: 'Project Narrative', inputs: [] } ] } }),
      'POST /ai/write': async () => ({ body: { draft_text: 'Draft...' } }),
      'PATCH /proposals/1/': async ({ body }) => {
        serverState.proposal = { ...(serverState.proposal || {}), ...body, id: 1 }
        return { body: serverState.proposal, status: 200 }
      },
      'POST /ai/format': async ({ body }) => ({ body: { formatted_text: `[gemini:final_format]\n\n${body.full_text}` } }),
    }
    const fetchSpy = mockFetch(routes)

    render(<Proposals token={token} />)

    // Wait for list
    await screen.findByText(/My Proposals/i)

    // Open author
    const openBtn = await screen.findByRole('button', { name: /Open Author/i })
    fireEvent.click(openBtn)

  // Start plan and wait for section 1 to appear
  const startBtn = await screen.findByRole('button', { name: /^Start$/ })
  fireEvent.click(startBtn)
  await screen.findByText(/Section 1 \/ 2/i)

    // Approve first section (already present in proposal.content)
  const approveBtn = await screen.findByRole('button', { name: /Approve & Save/i })
  fireEvent.click(approveBtn)
  // After save, UI advances to section 2
  await screen.findByText(/Section 2 \/ 2/i)

    // Move to next section (narrative), author a draft and approve it
  const writeBtn = await screen.findByRole('button', { name: /^Write$/ })
  fireEvent.click(writeBtn)
  // Wait for draft to be available which enables Approve & Save
  await screen.findByText(/Draft/i)
  const approveBtn2 = await screen.findByRole('button', { name: /Approve & Save/i })
    fireEvent.click(approveBtn2)

  // Final-format controls should now be visible
  const runBtn = await screen.findByRole('button', { name: /Run Final Formatting/i })
    fireEvent.click(runBtn)

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalled()
      const called = fetchSpy.mock.calls.some(([url]) => String(url).includes('/api/ai/format'))
      expect(called).toBe(true)
    })
    // Preview should render
    await screen.findByText(/Formatted preview/i)
  })
})
