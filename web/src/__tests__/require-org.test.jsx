import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { RequireAuth, RequireOrg } from '../main'

function AppWithRequireOrg({ token }) {
  const Child = () => <div data-testid="ok">OK</div>
  return (
    <RequireAuth token={token}>
      <RequireOrg token={token}>
        <Child />
      </RequireOrg>
    </RequireAuth>
  )
}

describe('RequireOrg', () => {
  const originalFetch = global.fetch
  beforeEach(() => { global.fetch = vi.fn() })
  afterEach(() => { global.fetch = originalFetch })

  it('redirects to /register when user has no orgs', async () => {
    // Mock /api/orgs/ with empty array
    global.fetch.mockResolvedValueOnce({ ok: true, json: async () => [] })
    render(
      <MemoryRouter initialEntries={['/app']}>
        <Routes>
          <Route path="/register" element={<div data-testid="register">REGISTER</div>} />
          <Route path="/app" element={<AppWithRequireOrg token="abc" />} />
        </Routes>
      </MemoryRouter>
    )
    // The guard redirects; we expect register placeholder to appear
    const el = await screen.findByTestId('register')
    expect(el).toBeInTheDocument()
  })
})
