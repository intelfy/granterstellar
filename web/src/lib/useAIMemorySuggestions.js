import { useCallback, useEffect, useState } from 'react'
import { api } from './core.js'

// Lightweight hook to fetch AI memory suggestions for the active section.
// Params: token (auth), orgId (optional scope), sectionId (optional), limit, refreshKey (change to refetch)
export function useAIMemorySuggestions({ token, orgId, sectionId, limit = 5, refreshKey }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchSuggestions = useCallback(async () => {
    if (!token) return
    setLoading(true)
    setError('')
    try {
      const params = []
      if (sectionId) params.push(`section_id=${encodeURIComponent(sectionId)}`)
      if (limit) params.push(`limit=${limit}`)
      const qs = params.length ? `?${params.join('&')}` : ''
      const data = await api(`/ai/memory/suggestions${qs}`, { token, orgId: orgId || undefined })
      if (data && Array.isArray(data.items)) setItems(data.items)
      else setItems([])
    } catch (e) { // eslint-disable-line no-unused-vars
      setError('Failed to load')
    } finally {
      setLoading(false)
    }
  }, [token, orgId, sectionId, limit])

  useEffect(() => { fetchSuggestions() }, [fetchSuggestions, refreshKey])

  return { items, loading, error, refresh: fetchSuggestions }
}

export default useAIMemorySuggestions
