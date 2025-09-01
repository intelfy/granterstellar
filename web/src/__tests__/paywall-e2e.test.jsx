import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, fireEvent, waitFor, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Proposals } from '../main.jsx'

describe('Paywall E2E: blocked → upgrade → create succeeds', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('unblocks creation after Upgrade and shows the new proposal', async () => {
    let allowCreate = false
    let nextId = 101
    const items = []

    const fetchMock = vi.fn(async (url, opts) => {
      const u = String(url)
      const method = (opts?.method || 'GET').toUpperCase()
      // Usage reflects whether creation is allowed
      if (u.endsWith('/usage') && method === 'GET') {
        return new Response(JSON.stringify({
          tier: allowCreate ? 'pro' : 'free',
          status: 'active',
          can_create_proposal: allowCreate,
          // Provide a reason when creation is blocked so the UI shows the paywall banner text
          ...(allowCreate ? {} : { reason: 'active_cap_reached' }),
          usage: { active: items.filter(p => p.state !== 'archived').length, created_this_period: items.length },
          limits: { monthly_cap: 20 },
        }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (u.endsWith('/proposals/') && method === 'GET') {
        return new Response(JSON.stringify(items.slice()), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (u.endsWith('/proposals/') && method === 'POST') {
        if (!allowCreate) {
          return new Response(JSON.stringify({ reason: 'active_cap_reached' }), { status: 402, headers: { 'Content-Type': 'application/json' } })
        }
        const created = { id: nextId++, state: 'draft', content: { meta: { title: 'Untitled' }, sections: {} }, schema_version: 'v1' }
        items.push(created)
        return new Response(JSON.stringify(created), { status: 201, headers: { 'Content-Type': 'application/json' } })
      }
      if (u.endsWith('/billing/checkout') && method === 'POST') {
        // Simulate successful checkout and promote plan
        allowCreate = true
        return new Response(JSON.stringify({ url: 'https://example.com/checkout' }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response(JSON.stringify({}), { status: 200, headers: { 'Content-Type': 'application/json' } })
    })
    vi.stubGlobal('fetch', fetchMock)
  const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)

    render(
      <MemoryRouter initialEntries={["/app"]}>
        <Proposals token="tok" />
      </MemoryRouter>
    )

  // Initially blocked: banner text visible and New button disabled
  await screen.findByText(/New proposal blocked/i)
  const newBtn = screen.getByText('New')
  expect(newBtn).toBeDisabled()

    // Upgrade triggers checkout and window.open
    fireEvent.click(screen.getByText('Upgrade'))
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(expect.stringMatching(/\/billing\/checkout$/), expect.objectContaining({ method: 'POST' }))
      expect(openSpy).toHaveBeenCalled()
    })

  // Wait until usage refresh unblocks creation, then click New
  await waitFor(() => expect(screen.getByText('New')).not.toBeDisabled())
  fireEvent.click(screen.getByText('New'))

    // List refresh shows the new proposal
    await waitFor(() => {
      expect(screen.getByText(/#101/)).toBeTruthy()
    })
  })
})
