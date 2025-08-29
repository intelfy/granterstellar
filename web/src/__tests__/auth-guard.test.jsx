import React from 'react'
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { RequireAuth } from '../main'

function Guarded() { return <div data-testid="ok">OK</div> }

describe('RequireAuth', () => {
  it('redirects to /login when no token', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/app']}>
        <Routes>
          <Route path="/login" element={<div data-testid="login">LOGIN</div>} />
          <Route path="/app" element={
            <RequireAuth token="">
              <Guarded />
            </RequireAuth>
          } />
        </Routes>
      </MemoryRouter>
    )
    expect(container.querySelector('[data-testid="login"]')).toBeInTheDocument()
  })

  it('renders children when token present', () => {
    const { getByTestId } = render(
      <MemoryRouter initialEntries={['/app']}>
        <Routes>
          <Route path="/app" element={
            <RequireAuth token="abc">
              <Guarded />
            </RequireAuth>
          } />
        </Routes>
      </MemoryRouter>
    )
    expect(getByTestId('ok')).toBeInTheDocument()
  })
})
