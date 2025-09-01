import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { InviteBanner } from '../main.jsx'

// We import Root indirectly by rendering a minimal tree that includes InviteBanner via Root export side effects
// But since Root is default-rendered to #root in main.jsx, we instead render a small shell using components
// For simplicity, render a minimal RequireAuth child and rely on InviteBanner being in Root normally; here we simulate by importing InviteBanner via the default module

function Shell({ token }) {
  // Render a placeholder region; InviteBanner is attached inside Root in real app
  return (
    <div data-testid="shell">SHELL</div>
  )
}

describe('InviteBanner', () => {
  it('shows when invite param present and accepts invite', async () => {
    // Render at a route with invite param; MemoryRouter will set location appropriately
    // Mock fetch for invite accept and a couple of usage/orgs calls that may happen
    global.fetch = vi.fn((u, opts) => {
      const path = u.toString()
      if (path.endsWith('/api/orgs/invites/accept')) {
        return Promise.resolve(new Response(JSON.stringify({ ok: true, org_id: 1 }), { status: 200 }))
      }
      if (path.endsWith('/api/orgs/')) {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
      }
      return Promise.resolve(new Response('{}', { status: 200 }))
    })

    render(
      <MemoryRouter initialEntries={[ '/app?invite=tok_abc' ]}>
        <InviteBanner token="t" />
      </MemoryRouter>
    )

    // Ensure banner shows
    const banner = await screen.findByTestId('invite-banner')
    expect(banner).toBeTruthy()
    const accept = screen.getByTestId('invite-accept')
    fireEvent.click(accept)

    await waitFor(() => {
      const current = new URL(window.location.href)
      expect(current.searchParams.get('invite')).toBe(null)
    })
  })

  it('dismiss hides banner without calling API', async () => {
    global.fetch = vi.fn()

    render(
      <MemoryRouter initialEntries={[ '/app?invite=tok_dismiss' ]}>
        <InviteBanner token="t" />
      </MemoryRouter>
    )

    const banner = await screen.findByTestId('invite-banner')
    expect(banner).toBeTruthy()
    const dismiss = screen.getByTestId('invite-dismiss')
    fireEvent.click(dismiss)

    await waitFor(() => {
      const current = new URL(window.location.href)
      expect(current.searchParams.get('invite')).toBe(null)
    })
    expect(global.fetch).not.toHaveBeenCalled()
  })
})

// Simple Response polyfill for Node test env
class Response {
  constructor(body, init) {
    this._body = body
    this.status = init?.status || 200
    this.ok = this.status >= 200 && this.status < 300
  }
  async json() { try { return JSON.parse(this._body || '{}') } catch { return {} } }
}
