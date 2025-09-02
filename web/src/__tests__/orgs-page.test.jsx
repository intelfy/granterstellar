import React from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import OrgsPage from '../pages/OrgsPage.jsx'

// Simple Response polyfill for Node test env
class Response {
  constructor(body, init) {
    this._body = body
    this.status = init?.status || 200
    this.ok = this.status >= 200 && this.status < 300
  }
  async json() { try { return JSON.parse(this._body || '{}') } catch { return {} } }
}

describe('OrgsPage (standalone view)', () => {
  it('renders organizations list and supports basic actions UI', async () => {
    // Mock list orgs and nested calls to avoid network
    global.fetch = vi.fn((url, opts) => {
      const u = url.toString()
      if (u.endsWith('/api/orgs/')) {
        return Promise.resolve(new Response(JSON.stringify([
          { id: 1, name: 'Acme', description: 'A', admin: { username: 'owner1' } },
          { id: 2, name: 'Beta', description: 'B', admin: { username: 'owner2' } }
        ]), { status: 200 }))
      }
      if (u.includes('/api/orgs/') && u.endsWith('/members/')) {
        return Promise.resolve(new Response(JSON.stringify([{ user: { id: 7, username: 'm1' }, role: 'member' }]), { status: 200 }))
      }
      if (u.includes('/api/orgs/') && u.endsWith('/invites/')) {
        if (opts && opts.method === 'POST') {
          return Promise.resolve(new Response(JSON.stringify({ id: 10, token: 'tok', email: 'x@y.z', role: 'member' }), { status: 200 }))
        }
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
      }
      return Promise.resolve(new Response('{}', { status: 200 }))
    })

    render(
      <MemoryRouter initialEntries={[ '/app/orgs' ]}>
        <Routes>
          <Route path="/app/orgs" element={<OrgsPage token="t" />} />
        </Routes>
      </MemoryRouter>
    )

    // Heading present
    expect(await screen.findByText('Organizations')).toBeInTheDocument()
    // Create controls present
    expect(screen.getByRole('button', { name: 'Create' })).toBeInTheDocument()

    // Expand manage for first org to trigger nested fetches
    const manage = screen.getAllByRole('button', { name: 'Manage' })[0]
    fireEvent.click(manage)

    await waitFor(() => {
      expect(screen.getByText(/Members/i)).toBeInTheDocument()
    })
  })
})
