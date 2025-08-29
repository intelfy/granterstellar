import { describe, it, expect } from 'vitest'
import { formatDiscount } from '../utils/formatDiscount.js'

describe('formatDiscount', () => {
  it('returns empty for null/invalid', () => {
    expect(formatDiscount(null)).toBe('')
    expect(formatDiscount(undefined)).toBe('')
    expect(formatDiscount('x')).toBe('')
  })

  it('formats percent off once', () => {
    const d = { percent_off: 25, duration: 'once' }
    expect(formatDiscount(d)).toBe('25% off (once)')
  })

  it('formats amount off repeating with months and currency', () => {
    const d = { amount_off: 1000, currency: 'usd', duration: 'repeating', duration_in_months: 3 }
    expect(formatDiscount(d)).toBe('1000 USD off (for 3 mo)')
  })

  it('handles forever duration', () => {
    const d = { percent_off: 10, duration: 'forever' }
    expect(formatDiscount(d)).toBe('10% off (forever)')
  })
})
