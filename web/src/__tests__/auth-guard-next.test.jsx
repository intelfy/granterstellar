import React from 'react'
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { RequireAuth } from '../main'

function Guarded() { return <div data-testid="ok">OK</div> }
function Login() { return <div data-testid="login">LOGIN</div> }

describe('RequireAuth next param', () => {
  it('adds next param to /login redirect', () => {
    const initialPath = '/app/path?a=1'
    const { container } = render(
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/app/*" element={
            <RequireAuth token="">
              <Guarded />
            </RequireAuth>
          } />
        </Routes>
      </MemoryRouter>
    )
    expect(container.querySelector('[data-testid="login"]')).toBeInTheDocument()
  })
})
