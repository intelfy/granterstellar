import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import React from 'react'
import { Proposals } from '../main.jsx'

function mockFetch(routes) {
  const fn = vi.fn(async (url, opts = {}) => {
    const path = String(url).replace(/^[^/]*\/api/, '')
    const key = `${opts.method || 'GET'} ${path}`
    const handler = routes[key]
    if (!handler) return new Response(JSON.stringify({}), { status: 404 })
    const body = opts.body ? JSON.parse(opts.body) : null
    const res = await handler({ path, body, opts })
    return new Response(JSON.stringify(res.body || {}), { status: res.status || 200, headers: { 'Content-Type': 'application/json' } })
  })
  global.fetch = fn
  return fn
}

describe('Export after final-formatting', () => {
  it('runs final-format then exports the proposal (opens URL)', async () => {
    const token = 't'
    // Proposal already has both sections approved; plan will match these ids
    const proposal = {
      id: 7,
      content: {
        meta: { title: 'Complete Draft' },
        sections: {
          summary: { title: 'Executive Summary', content: 'S' },
          narrative: { title: 'Project Narrative', content: 'N' },
        },
      },
      schema_version: 'v1',
      state: 'draft',
    }
    const routes = {
      'GET /proposals/': async () => ({ body: [proposal] }),
      'GET /usage': async () => ({ body: { tier: 'pro', status: 'active' } }),
      'POST /ai/plan': async () => ({ body: { schema_version: 'v1', sections: [ { id: 'summary', title: 'Executive Summary', inputs: [] }, { id: 'narrative', title: 'Project Narrative', inputs: [] } ] } }),
      'POST /ai/format': async ({ body }) => ({ body: { formatted_text: `FINAL\n\n${body.full_text}` } }),
      'POST /exports': async ({ body }) => {
        expect(body).toEqual({ proposal_id: 7, format: 'pdf' })
        return { body: { id: 1, url: 'http://localhost/downloads/7.pdf' } }
      },
    }
    const fetchSpy = mockFetch(routes)
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)

    render(<Proposals token={token} />)

    // Wait for list and controls
    await screen.findByText(/My Proposals/i)
    const openBtn = await screen.findByRole('button', { name: /Open Author/i })
    fireEvent.click(openBtn)

    // Start plan; since sections are already approved in proposal, final-formatting should be available
    const startBtn = await screen.findByRole('button', { name: /^Start$/ })
    fireEvent.click(startBtn)
    await screen.findByText(/Section 1 \/ 2/i)

    // Run final formatting
    const runBtn = await screen.findByRole('button', { name: /Run Final Formatting/i })
    fireEvent.click(runBtn)

    await waitFor(() => {
      const called = fetchSpy.mock.calls.some(([url]) => String(url).includes('/api/ai/format'))
      expect(called).toBe(true)
    })
    await screen.findByText(/Formatted preview/i)

    // Now export from the list item
    const exportBtn = await screen.findByRole('button', { name: /^Export$/ })
    fireEvent.click(exportBtn)

    await waitFor(() => {
      const posted = fetchSpy.mock.calls.some(([url, opts]) => String(url).includes('/api/exports') && (opts?.method === 'POST'))
      expect(posted).toBe(true)
      expect(openSpy).toHaveBeenCalled()
      const openedUrl = openSpy.mock.calls[0]?.[0]
      expect(String(openedUrl)).toContain('/downloads/7.pdf')
    })

    openSpy.mockRestore()
  })
})
