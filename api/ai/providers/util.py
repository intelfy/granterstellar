from typing import List, Dict, Any, Optional


def summarize_file_refs(file_refs: Optional[List[Dict[str, Any]]]) -> str:
    if not file_refs:
        return ''
    lines: List[str] = []
    for ref in file_refs[:5]:
        try:
            label = str(ref.get('name') or '').strip() or f"file#{ref.get('id', '?')}"
            ocr = str(ref.get('ocr_text') or '').strip().replace('\n', ' ')
            if len(ocr) > 200:
                ocr = ocr[:200]
            if label or ocr:
                lines.append(f'- {label}: {ocr}'.rstrip())
        except Exception:
            continue
    if not lines:
        return ''
    return '\n\n[context:sources]\n' + '\n'.join(lines)
