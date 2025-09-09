import { useEffect, useState } from 'react'
import { api, openDebugLocal, safeOpenExternal, formatDiscount } from '../lib/core.js'
import { t } from '../keys.generated'

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
  } catch { setError(t('ui.dashboard.checkout_unavailable')) } finally { setLoading(false) }
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
  } catch { setError(t('ui.dashboard.portal_unavailable')) } finally { setLoading(false) }
  }
  const onCancel = async () => {
    setLoading(true); setError('')
    try {
      await api('/billing/cancel', { method: 'POST', token, body: {} })
      await refresh()
  alert(t('ui.dashboard.subscription_cancelled_schedule'))
  } catch {
  setError(t('errors.billing.cancel_failed'))
    } finally { setLoading(false) }
  }
  const onResume = async () => {
    setLoading(true); setError('')
    try {
      await api('/billing/resume', { method: 'POST', token, body: {} })
      await refresh()
      alert(t('ui.dashboard.subscription_resumed'))
  } catch {
      setError(t('errors.billing.resume_failed'))
    } finally { setLoading(false) }
  }
  return (
    <section>
      <h2>{t('ui.billing.heading')}</h2>
      {usage && (
        <div>
          {t('ui.dashboard.tier_status', { tier: usage.tier, status: usage.status })}
          {usage.subscription?.cancel_at_period_end ? ` · ${t('ui.billing.cancel_at_period_end_flag')}` : ''}
          {usage.subscription?.current_period_end ? ` · ${t('ui.dashboard.period_ends', { date: new Date(usage.subscription.current_period_end).toLocaleDateString() })}` : ''}
          {usage.seats?.capacity ? ` · ${t('ui.billing.seats_line', { count: usage.seats.capacity })}` : ''}
          {usage.subscription?.discount ? (
            <> · <span data-testid="promo-banner" aria-label="active-promo">{t('ui.dashboard.promo_active', { discount: formatDiscount(usage.subscription.discount) })}</span></>
          ) : ''}
        </div>
      )}
      <div>
        <div>
          <label>{t('ui.billing.coupon_label')} </label>
          <input value={coupon} onChange={(e) => setCoupon(e.target.value)} placeholder={t('ui.billing.coupon_placeholder')} />
        </div>
        <div>
          <label>{t('ui.billing.price_id_label')} </label>
          <input value={priceId} onChange={(e) => setPriceId(e.target.value)} placeholder={t('ui.billing.price_id_placeholder')} />
        </div>
        <div>
          <label>{t('ui.billing.seats_label')} </label>
          <input type="number" min={1} value={quantity} onChange={(e) => setQuantity(e.target.value)} style={{ width: 80 }} />
        </div>
      </div>
      <div>
        <button onClick={startCheckout} disabled={loading}>{t('ui.dashboard.upgrade_button')}</button>
        <button onClick={openPortal} disabled={loading}>{t('ui.dashboard.billing_portal_button')}</button>
        {usage?.subscription?.cancel_at_period_end ? (
          <button onClick={onResume} disabled={loading}>{t('ui.dashboard.resume_button')}</button>
        ) : (
          <button onClick={onCancel} disabled={loading}>{t('ui.dashboard.cancel_at_period_end_button')}</button>
        )}
      </div>
      {error && <div>{error}</div>}
    </section>
  )
}
