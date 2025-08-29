// Minimal client-side sanitization utilities.
// We do not render HTML from user input today, but these helpers are available for future use.

export function sanitizeText(input: unknown, maxLen = 10000): string {
  if (input == null) return ''
  let s = String(input)
  s = s.replace(/\r\n?/g, '\n')
  // Strip control chars except tab/newline
  s = s.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '')
  // Strip common invisible unicode
  s = s.replace(/[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]/g, '')
  if (s.length > maxLen) s = s.slice(0, maxLen)
  return s
}

export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

// Example safe render usage:
// const safe = escapeHtml(sanitizeText(userString));
// <pre>{safe}</pre>
