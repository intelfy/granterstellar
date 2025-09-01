import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { OAuthCallback, RegisterPage, RequireAuth } from '../main'

function setupMocks({ storedNext = '/app/deep/path?x=1' } = {}) {
  const store = {}
  vi.spyOn(window.sessionStorage.__proto__, 'getItem').mockImplementation((k) => store[k] || null)
  vi.spyOn(window.sessionStorage.__proto__, 'setItem').mockImplementation((k, v) => { store[k] = String(v) })
  vi.spyOn(window.sessionStorage.__proto__, 'removeItem').mockImplementation((k) => { delete store[k] })
  if (storedNext) store.postLoginNext = storedNext

  const fetchMock = vi.fn(async (url, opts) => {
    const u = String(url)
    if (u.includes('/oauth/google/callback')) {
      return new Response(JSON.stringify({ access: 'tok' }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    if (u.endsWith('/orgs/')) {
      // No orgs forces /register
      return new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    if (u.endsWith('/orgs/invites/accept')) {
      return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    if (u.endsWith('/orgs/')) {
      return new Response(JSON.stringify([{ id: 1, name: 'Acme' }]), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    if (u.endsWith('/billing/checkout')) {
      return new Response(JSON.stringify({ url: 'https://checkout.example' }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } })
  })
  vi.stubGlobal('fetch', fetchMock)

  const setToken = vi.fn()
  return { fetchMock, setToken, store }
}

// Minimal authenticated wrapper for RegisterPage to match app routing
function WrappedRegister({ token }) {
  return (
    <RequireAuth token={token}>
      <RegisterPage token={token} />
    </RequireAuth>
  )
}

describe('OAuth deep-link through Register preserves next and returns to app', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('goes OAuth -> /register?next=... -> submit -> navigates to next', async () => {
    const { setToken } = setupMocks()

    // Spy on alert and window.open used in RegisterPage
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {})
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)

    const ui = (
      <MemoryRouter initialEntries={[`/oauth/callback?code=abc`]}>
        <Routes>
          <Route path="/oauth/callback" element={<OAuthCallback setToken={setToken} />} />
          <Route path="/register" element={<WrappedRegister token={'tok'} />} />
          <Route path="/app/*" element={<div data-testid="app-home">APP</div>} />
        </Routes>
      </MemoryRouter>
    )

    render(ui)

    // Should land on register
    await screen.findByText(/Complete your registration/i)

    // Fill minimal fields; choose Pro to exercise checkout open
    fireEvent.change(screen.getByPlaceholderText('Your name'), { target: { value: 'Jane' } })
    fireEvent.change(screen.getByPlaceholderText(/Organization name/), { target: { value: 'Acme' } })
    fireEvent.click(screen.getByDisplayValue('pro'))

    fireEvent.click(screen.getByText('Continue'))

    // Confirmation alert stubbed
    await waitFor(() => expect(alertSpy).toHaveBeenCalled())
    // Checkout window may open in DEBUG flow
    // openSpy may or may not be called depending on branch; tolerate either

    // After submit, navigate to stored next (/app/deep/path?x=1) which matches /app/*
    await screen.findByTestId('app-home')

    // Clean spies
    alertSpy.mockRestore()
    openSpy.mockRestore()
  })
})
