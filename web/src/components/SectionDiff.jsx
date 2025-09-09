import { useMemo } from 'react'
import { t } from '../keys.generated'

export default function SectionDiff({ before = '', after = '' }) {
  if (!before && !after) return null
  // Simple word-level diff with LCS to highlight insertions/deletions
  const tokens = useMemo(() => {
    const a = (before || '').split(/(\s+)/)
    const b = (after || '').split(/(\s+)/)
    const n = a.length, m = b.length
    const dp = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0))
    for (let i = n - 1; i >= 0; i--) {
      for (let j = m - 1; j >= 0; j--) {
        dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
      }
    }
    const out = []
    let i = 0, j = 0
    while (i < n && j < m) {
      if (a[i] === b[j]) { out.push({ t: 'eq', v: a[i] }); i++; j++; }
      else if (dp[i + 1][j] >= dp[i][j + 1]) { out.push({ t: 'del', v: a[i] }); i++; }
      else { out.push({ t: 'ins', v: b[j] }); j++; }
    }
    while (i < n) out.push({ t: 'del', v: a[i++] })
    while (j < m) out.push({ t: 'ins', v: b[j++] })
    return out
  }, [before, after])

  const wrap = (tok, idx) => {
    if (tok.t === 'ins') return <span key={idx} data-testid="diff-ins" style={{ background: '#e6ffed' }}>{tok.v}</span>
    if (tok.t === 'del') return <span key={idx} data-testid="diff-del" style={{ background: '#ffeef0', textDecoration: 'line-through' }}>{tok.v}</span>
    return <span key={idx}>{tok.v}</span>
  }

  return (
    <div>
      <div>{t('ui.diff.heading')}</div>
      <div style={{ border: '1px solid #ddd', padding: 8 }}>
        {tokens.map(wrap)}
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
        <div style={{ flex: 1 }}>
          <div>{t('ui.diff.previous')}</div>
          <pre>{before || '—'}</pre>
        </div>
        <div style={{ flex: 1 }}>
          <div>{t('ui.diff.draft')}</div>
          <pre>{after || '—'}</pre>
        </div>
      </div>
    </div>
  )
}
