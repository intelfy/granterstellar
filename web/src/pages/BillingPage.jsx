import { useEffect, useState } from 'react'
import { api, openDebugLocal, safeOpenExternal, formatDiscount } from '../lib/core.js'

export default function BillingPage({ token }) {
  const [usage, setUsage] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [coupon, setCoupon] = useState('')
  const [priceId, setPriceId] = useState('')
  const [quantity, setQuantity] = useState(1)
  const refresh = async () => { try { setUsage(await api('/usage', { token })) } catch {} }
  useEffect(() => { refresh() }, [token])
  const startCheckout = async () => {
    setLoading(true); setError('')
    try {
      const body = {}
      if (coupon) body.coupon = coupon.trim()
      if (priceId) body.price_id = priceId.trim()
      if (Number.isFinite(Number(quantity)) && Number(quantity) > 0) body.quantity = Number(quantity)
      const { url } = await api('/billing/checkout', { method: 'POST', token, body })
      if (url) {
        try {
          const u = new URL(url)
          if (!openDebugLocal(u.toString())) {
            safeOpenExternal(u.toString(), ['https://checkout.stripe.com'])
          }
        } catch {
          openDebugLocal(url)
        }
        await refresh()
      }
  } catch { setError('Checkout unavailable') } finally { setLoading(false) }
  }
  const openPortal = async () => {
    setLoading(true); setError('')
    try {
      const res = await api('/billing/portal', { method: 'GET', token })
      if (res?.url) {
        try {
          const u = new URL(res.url)
          if (!openDebugLocal(u.toString())) {
            safeOpenExternal(u.toString(), ['https://billing.stripe.com'])
          }
        } catch {
          openDebugLocal(res.url)
        }
      }
  } catch { setError('Portal unavailable') } finally { setLoading(false) }
  }
  const onCancel = async () => {
    setLoading(true); setError('')
    try {
      await api('/billing/cancel', { method: 'POST', token, body: {} })
      await refresh()
      alert('Subscription will cancel at period end.')
  } catch {
      setError('Cancel failed')
    } finally { setLoading(false) }
  }
  const onResume = async () => {
    setLoading(true); setError('')
    try {
      await api('/billing/resume', { method: 'POST', token, body: {} })
      await refresh()
      alert('Subscription resumed.')
  } catch {
      setError('Resume failed')
    } finally { setLoading(false) }
  }
  return (
    <section>
      <h2>Billing</h2>
      {usage && (
        <div>
          Tier: {usage.tier} · Status: {usage.status}
          {usage.subscription?.cancel_at_period_end ? ' · Cancel at period end: yes' : ''}
          {usage.subscription?.current_period_end ? ` · Period ends: ${new Date(usage.subscription.current_period_end).toLocaleDateString()}` : ''}
          {usage.seats?.capacity ? ` · Seats: ${usage.seats.capacity}` : ''}
          {usage.subscription?.discount ? (
            <> · <span data-testid="promo-banner" aria-label="active-promo">Promo: {formatDiscount(usage.subscription.discount)}</span></>
          ) : ''}
        </div>
      )}
      <div>
        <div>
          <label>Coupon/Promotion code (optional): </label>
          <input value={coupon} onChange={(e) => setCoupon(e.target.value)} placeholder="SUMMER100" />
        </div>
        <div>
          <label>Price ID (optional): </label>
          <input value={priceId} onChange={(e) => setPriceId(e.target.value)} placeholder="price_123... (test)" />
        </div>
        <div>
          <label>Seats (quantity): </label>
          <input type="number" min={1} value={quantity} onChange={(e) => setQuantity(e.target.value)} style={{ width: 80 }} />
        </div>
      </div>
      <div>
        <button onClick={startCheckout} disabled={loading}>Upgrade (Checkout)</button>
        <button onClick={openPortal} disabled={loading}>Open Billing Portal</button>
        {usage?.subscription?.cancel_at_period_end ? (
          <button onClick={onResume} disabled={loading}>Resume</button>
        ) : (
          <button onClick={onCancel} disabled={loading}>Cancel at period end</button>
        )}
      </div>
      {error && <div>{error}</div>}
    </section>
  )
}
