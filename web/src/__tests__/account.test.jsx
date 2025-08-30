import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { AccountPage } from '../main.jsx'

const apiBase = import.meta.env.VITE_API_BASE || '/api'

describe('AccountPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('loads profile and saves changes', async () => {
    const token = 't'
    // Mock GET /api/me
    vi.spyOn(global, 'fetch').mockImplementation((url, opts) => {
      if (String(url).endsWith(`${apiBase}/me`) && (!opts || opts.method === 'GET')) {
        return Promise.resolve(new Response(JSON.stringify({ ok: true, user: { username: 'demo', email: 'demo@example.com', first_name: 'De', last_name: 'Mo' } }), { status: 200 }))
      }
      if (String(url).endsWith(`${apiBase}/me`) && opts && opts.method === 'PATCH') {
        return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }))
      }
      return Promise.resolve(new Response('{}', { status: 404 }))
    })

    render(
      <BrowserRouter>
        <AccountPage token={token} />
      </BrowserRouter>
    )

    // Wait for initial load
    await waitFor(() => expect(screen.getByTestId('pf-username').value).toBe('demo'))

    fireEvent.change(screen.getByTestId('pf-email'), { target: { value: 'new@example.com' } })
    fireEvent.click(screen.getByTestId('pf-save'))

    await waitFor(() => expect(screen.getByTestId('pf-ok')).toBeInTheDocument())
  })
})
