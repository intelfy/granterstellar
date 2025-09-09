import useAIMemorySuggestions from '../lib/useAIMemorySuggestions.js'
import { t } from '../keys.generated'

// Minimal, unstyled suggestions list. Styling explicitly deferred.
export default function MemorySuggestions({ token, orgId, sectionId, refreshKey, onInsert }) {
  const { items, loading, error, refresh } = useAIMemorySuggestions({ token, orgId, sectionId, limit: 5, refreshKey })

  if (!token) return null
  return (
    <div data-testid="memory-suggestions" style={{ border: '1px solid #eee', padding: 8, marginTop: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <strong>{t('ui.memory.heading')}</strong>
        <button onClick={refresh} disabled={loading} style={{ fontSize: 12 }} title={t('ui.memory.refresh')}>↻</button>
      </div>
      {loading && <div>{t('ui.memory.loading')}</div>}
      {error && <div>{t('ui.memory.error')}</div>}
      {!loading && !error && items.length === 0 && <div style={{ fontSize: 12 }}>{t('ui.memory.empty')}</div>}
      {items.length > 0 && (
        <ul style={{ listStyle: 'none', padding: 0, margin: '4px 0 0 0' }}>
          {items.map((it, idx) => (
            <li key={idx} data-testid="memory-suggestion" style={{ marginBottom: 6 }}>
              <div style={{ fontSize: 12 }}><strong>{it.key}</strong></div>
              <div style={{ whiteSpace: 'pre-wrap', fontSize: 12, maxHeight: 80, overflow: 'auto', border: '1px solid #f2f2f2', padding: 4 }}>{it.value}</div>
              <div>
                <button style={{ fontSize: 12 }} onClick={() => onInsert?.(it.key, it.value)}>{t('ui.memory.insert')}</button>
                <span style={{ fontSize: 10, opacity: 0.6, marginLeft: 4 }}>{t('ui.memory.uses', { count: it.usage_count })}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
