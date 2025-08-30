import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { BillingPage } from '../main.jsx'

function mockApiSequence(responses) {
  let call = 0
  global.fetch = vi.fn((url, opts) => {
    const path = url.toString()
    // usage GET
    if (path.endsWith('/api/usage')) {
      return Promise.resolve(new Response(JSON.stringify(responses.usage || {}), { status: 200 }))
    }
    // cancel/resume POST
    if (path.endsWith('/api/billing/cancel') || path.endsWith('/api/billing/resume')) {
      call++
      return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }))
    }
    // portal GET
    if (path.endsWith('/api/billing/portal')) {
      return Promise.resolve(new Response(JSON.stringify({ url: 'https://billing.stripe.com/p/session' }), { status: 200 }))
    }
    // checkout POST
    if (path.endsWith('/api/billing/checkout')) {
      return Promise.resolve(new Response(JSON.stringify({ url: 'https://checkout.stripe.com/c/pay/test' }), { status: 200 }))
    }
    return Promise.resolve(new Response('{}', { status: 200 }))
  })
}

// Simple Response polyfill for Node test env
class Response {
  constructor(body, init) {
    this._body = body
    this.status = init?.status || 200
    this.ok = this.status >= 200 && this.status < 300
  }
  async json() { try { return JSON.parse(this._body || '{}') } catch { return {} } }
}

// Avoid opening new windows during tests
const openSpy = vi.spyOn(window, 'open').mockImplementation(() => {})

// Ensure DOM is cleaned between tests in this file to avoid duplicate sections
afterEach(() => {
  cleanup()
})

describe('BillingPage controls', () => {
  it('renders cancel or resume based on usage and triggers action', async () => {
    mockApiSequence({ usage: { tier: 'pro', status: 'active', subscription: { cancel_at_period_end: false, current_period_end: new Date().toISOString() }, seats: { capacity: 2 } } })

    render(
      <MemoryRouter initialEntries={[ '/app/billing' ]}>
        <BillingPage token="t" />
      </MemoryRouter>
    )

    // Wait for usage display
    await screen.findByText(/Tier: pro/i)

    // Should show Cancel at period end
    const cancelBtn = screen.getByRole('button', { name: /Cancel at period end/i })
    expect(cancelBtn).toBeInTheDocument()

    // Click cancel
    fireEvent.click(cancelBtn)
    await waitFor(() => {
      // fetch called for cancel and then usage refresh
      expect(global.fetch).toHaveBeenCalledWith('/api/billing/cancel', expect.objectContaining({ method: 'POST' }))
    })
  })

  it('shows resume when cancel_at_period_end is true', async () => {
    mockApiSequence({ usage: { tier: 'pro', status: 'active', subscription: { cancel_at_period_end: true } } })

    render(
      <MemoryRouter initialEntries={[ '/app/billing' ]}>
        <BillingPage token="t" />
      </MemoryRouter>
    )

    await screen.findByText(/Tier: pro/i)
    const resumeBtn = screen.getByRole('button', { name: /Resume/i })
    expect(resumeBtn).toBeInTheDocument()

    fireEvent.click(resumeBtn)
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/billing/resume', expect.objectContaining({ method: 'POST' }))
    })
  })

  it('surfaces promo banner when discount is present and hides when absent', async () => {
    // First call returns a discount, second call after clicking Checkout returns no discount
    let phase = 0
    global.fetch = vi.fn((url) => {
      const path = url.toString()
      if (path.endsWith('/api/usage')) {
        phase++
        if (phase === 1) {
          return Promise.resolve(new Response(JSON.stringify({ tier: 'pro', status: 'active', subscription: { discount: { source: 'coupon', id: 'coupon_20', percent_off: 20, duration: 'once' } } })))}
        return Promise.resolve(new Response(JSON.stringify({ tier: 'pro', status: 'active', subscription: { discount: null } })))
      }
      if (path.endsWith('/api/billing/checkout')) {
        return Promise.resolve(new Response(JSON.stringify({ url: 'https://checkout.stripe.com/c/pay/test' })))
      }
      if (path.endsWith('/api/billing/portal')) {
        return Promise.resolve(new Response(JSON.stringify({ url: 'https://billing.stripe.com/p/session' })))
      }
      return Promise.resolve(new Response('{}'))
    })

    render(
      <MemoryRouter initialEntries={[ '/app/billing' ]}>
        <BillingPage token="t" />
      </MemoryRouter>
    )

  // Promo banner present initially using the dedicated test id
  await screen.findByTestId('promo-banner')

    // Trigger a checkout request — component will refetch usage after
    const upgradeBtn = screen.getByRole('button', { name: /Upgrade/i })
    fireEvent.click(upgradeBtn)

    // Promo banner should disappear after refetch
    await waitFor(() => {
      const promos = screen.queryAllByTestId('promo-banner')
      expect(promos.length).toBe(0)
    })
  })
})
