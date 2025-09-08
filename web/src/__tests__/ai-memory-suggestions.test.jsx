import { renderHook, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import useAIMemorySuggestions from '../lib/useAIMemorySuggestions.js'

// Mock api module
vi.mock('../lib/core.js', () => ({
  api: vi.fn(async (path, { token, orgId } = {}) => {
    // simple router simulation
    const url = new URL('http://local' + path)
    const section = url.searchParams.get('section_id')
    const limit = parseInt(url.searchParams.get('limit') || '5', 10)
    if (!token) return { items: [] }
    // dataset keyed by org vs personal
    const base = [
      { key: 'mission', value: 'Reduce waste', usage_count: 2, section_id: 'intro' },
      { key: 'beneficiaries', value: '2000 students', usage_count: 1, section_id: 'impact', org: '123' },
      { key: 'budget_total', value: '$10k', usage_count: 0, section_id: 'budget' },
    ]
    let items = base.filter(r => !!token)
    if (orgId) items = items.filter(r => r.org === orgId)
    else items = items.filter(r => !r.org) // personal only
    if (section) items = items.filter(r => r.section_id === section)
    items = items.slice(0, Math.min(Math.max(limit, 1), 20))
    return { items: items.map(({ key, value, usage_count }) => ({ key, value, usage_count })) }
  })
}))

describe('useAIMemorySuggestions', () => {
  it('returns empty when no token', async () => {
    const { result } = renderHook(() => useAIMemorySuggestions({ token: '', sectionId: 'intro' }))
    expect(result.current.items).toEqual([])
  })

  it('loads personal suggestions for section', async () => {
    const { result } = renderHook(() => useAIMemorySuggestions({ token: 't', sectionId: 'intro', limit: 5 }))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.items).toEqual([
      { key: 'mission', value: 'Reduce waste', usage_count: 2 }
    ])
  })

  it('respects limit parameter', async () => {
    const { result } = renderHook(() => useAIMemorySuggestions({ token: 't', limit: 1 }))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.items.length).toBe(1)
  })

  it('filters by org when orgId provided', async () => {
    const { result } = renderHook(() => useAIMemorySuggestions({ token: 't', orgId: '123', sectionId: 'impact' }))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.items).toEqual([
      { key: 'beneficiaries', value: '2000 students', usage_count: 1 }
    ])
  })

  it('refresh refetches with new sectionId', async () => {
    const { result, rerender } = renderHook((props) => useAIMemorySuggestions(props), {
      initialProps: { token: 't', sectionId: 'intro' }
    })
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.items[0].key).toBe('mission')
    rerender({ token: 't', sectionId: 'budget' })
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.items[0].key).toBe('budget_total')
  })
})
