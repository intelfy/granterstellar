// Formats a Subscription.discount summary from /api/usage for display
// Shape example:
// {
//   source: 'promotion_code'|'coupon',
//   id: 'promo_...'|'coupon_...',
//   percent_off: 10,
//   amount_off: 0,
//   currency: 'usd',
//   duration: 'once'|'repeating'|'forever',
//   duration_in_months: 1
// }
export function formatDiscount(d) {
  if (!d || typeof d !== 'object') return ''
  const parts = []
  if (typeof d.percent_off === 'number' && d.percent_off > 0) {
    parts.push(`${d.percent_off}% off`)
  } else if (typeof d.amount_off === 'number' && d.amount_off > 0) {
    const cur = (d.currency || '').toUpperCase()
    parts.push(`${d.amount_off}${cur ? ' ' + cur : ''} off`)
  }
  if (d.duration) {
    if (d.duration === 'once') parts.push('(once)')
    else if (d.duration === 'forever') parts.push('(forever)')
    else if (d.duration === 'repeating' && d.duration_in_months) parts.push(`(for ${d.duration_in_months} mo)`)
  }
  return parts.join(' ')
}
