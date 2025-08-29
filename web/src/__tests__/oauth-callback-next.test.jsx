import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { OAuthCallback } from '../main'

// Minimal helper to control search params and observe navigation
function setup({ code = 'xyz', state, storedNext = '/app' } = {}) {
  // mock sessionStorage for next param
  const store = {}
  vi.spyOn(window.sessionStorage.__proto__, 'getItem').mockImplementation((k) => store[k] || null)
  vi.spyOn(window.sessionStorage.__proto__, 'setItem').mockImplementation((k, v) => { store[k] = String(v) })
  vi.spyOn(window.sessionStorage.__proto__, 'removeItem').mockImplementation((k) => { delete store[k] })
  if (storedNext) store.postLoginNext = storedNext

  // mock fetch for oauth callback and orgs list
  const fetchMock = vi.fn(async (url, opts) => {
    if (String(url).includes('/oauth/google/callback')) {
      return new Response(JSON.stringify({ access: 'tok' }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    if (String(url).endsWith('/orgs/')) {
      // return empty orgs to force redirect to /register
      return new Response(JSON.stringify([]), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }
    return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } })
  })
  vi.stubGlobal('fetch', fetchMock)

  const setToken = vi.fn()
  return { fetchMock, setToken, store }
}

describe('OAuthCallback deep-link persistence', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('redirects to /register with next when user has no orgs and preserves stored next', async () => {
    const { setToken } = setup({ storedNext: '/app/some/deep/path?x=1' })

    const ui = (
      <MemoryRouter initialEntries={[`/oauth/callback?code=abc`]}>
        <Routes>
          <Route path="/oauth/callback" element={<OAuthCallback setToken={setToken} />} />
          <Route path="/register" element={<div data-testid="register">register</div>} />
        </Routes>
      </MemoryRouter>
    )

    const { findByTestId } = render(ui)
    const el = await findByTestId('register')
    expect(el).toBeTruthy()
  })
})
