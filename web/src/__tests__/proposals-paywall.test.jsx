import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Proposals } from '../main'

function mockFetchSequence() {
  // First GET /usage returns can_create_proposal: false to trigger paywall
  // GET /proposals/ returns an empty list
  // POST /proposals returns 402 with reason
  const fetchMock = vi.fn(async (url, opts) => {
    const u = String(url)
    if (u.endsWith('/usage') && (!opts || opts.method === 'GET')) {
      return new Response(JSON.stringify({ tier: 'free', status: 'active', can_create_proposal: false, reason: 'active_cap_reached', usage: {}, limits: {} }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    if (u.endsWith('/proposals/') && (!opts || opts.method === 'GET')) {
      return new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    if (u.endsWith('/proposals/') && opts && opts.method === 'POST') {
      return new Response(JSON.stringify({ reason: 'active_cap_reached' }), { status: 402, headers: { 'Content-Type': 'application/json' } })
    }
    if (u.endsWith('/billing/checkout') && opts && opts.method === 'POST') {
      return new Response(JSON.stringify({ url: 'https://example.com/checkout' }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    return new Response(JSON.stringify({}), { status: 200, headers: { 'Content-Type': 'application/json' } })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('Proposals paywall flow', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('shows upgrade CTA when creation is blocked and clicking Upgrade calls checkout', async () => {
    const fetchMock = mockFetchSequence()
    // Spy on window.open
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)

    const { getByText, findByText } = render(
      <MemoryRouter initialEntries={["/app"]}>
        <Proposals token="tok" />
      </MemoryRouter>
    )

    // Wait for usage fetch to reflect blocked state
    await findByText(/New proposal blocked/i)

    const upgradeBtn = getByText('Upgrade')
    expect(upgradeBtn).toBeTruthy()

    // Click New first to show paywall alert (swallow alert in test)
    vi.spyOn(window, 'alert').mockImplementation(() => {})
    fireEvent.click(getByText('New'))

    // Click Upgrade
    fireEvent.click(upgradeBtn)

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(expect.stringMatching(/\/billing\/checkout$/), expect.objectContaining({ method: 'POST' }))
      expect(openSpy).toHaveBeenCalled()
    })
  })
})
