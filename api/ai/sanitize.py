import re
from typing import Any
from urllib.parse import urlparse


# Basic controls/invisible characters to strip (keep tabs/newlines)
_CTRL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
_INVISIBLE_RE = re.compile(r'[\u200B-\u200F\u202A-\u202E\u2060\u2061\u2062\u2063\u2064\u206A-\u206F\uFEFF]')

# Heuristic prompt-injection phrases to neutralize
_INJECTION_PATTERNS = [
    r'ignore (all|any|previous) (instructions|prompts)',
    r'disregard (the|any) above',
    r'you are (now )?(chatgpt|an ai|a large language model)',
    r'system (prompt|message)',
    r'developer (message|instructions)',
    r'act as ',
    r'jailbreak',
    r'do anything now|dan mode',
    r'chain ?of ?thought',
    r'tool (call|usage)',
]
_INJECTION_RE = re.compile('|'.join(_INJECTION_PATTERNS), re.IGNORECASE)


def sanitize_text(value: Any, *, max_len: int = 10000, neutralize_injection: bool = True) -> str:
    """Return a sanitized string safe to forward to LLMs or logs.

    - Coerces to str
    - Strips control/invisible characters
    - Trims length
    - Optionally neutralizes common prompt-injection phrases
    """
    if value is None:
        return ''
    s = str(value)
    # Normalize newlines
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    s = _CTRL_RE.sub('', s)
    s = _INVISIBLE_RE.sub('', s)
    if neutralize_injection:
        s = _INJECTION_RE.sub('[redacted]', s)
    if len(s) > max_len:
        s = s[:max_len]
    return s


def sanitize_url(value: Any, *, max_len: int = 2048) -> str:
    """Allow only http/https URLs and trim length; return empty string if invalid."""
    if not value:
        return ''
    try:
        s = str(value).strip()
        if len(s) > max_len:
            return ''
        parsed = urlparse(s)
        if parsed.scheme not in {'http', 'https'}:
            return ''
        if not parsed.netloc:
            return ''
        return s
    except Exception:
        return ''


def sanitize_answers(answers: Any) -> dict[str, str]:
    """Sanitize a dict of free-text answers."""
    if not isinstance(answers, dict):
        return {}
    cleaned: dict[str, str] = {}
    for k, v in answers.items():
        try:
            key = str(k)
            cleaned[key] = sanitize_text(v)
        except Exception:
            continue
    return cleaned


def sanitize_file_refs(value: Any) -> list[dict[str, Any]]:
    """Sanitize optional file references passed from the SPA.

    Shape (per item): {id, url, name, content_type, size, ocr_text}
    - Keep only known fields; coerce types; cap counts and lengths
    - Trim ocr_text to a safe size
    """
    out: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return out
    for item in value[:5]:  # cap number of files per request
        try:
            if not isinstance(item, dict):
                continue
            ref: dict[str, Any] = {}
            if 'id' in item:
                try:
                    ref['id'] = int(item['id'])
                except Exception:
                    continue
            if 'url' in item:
                ref['url'] = str(item['url'])[:2048]
            if 'name' in item:
                ref['name'] = str(item['name'])[:256]
            if 'content_type' in item:
                ref['content_type'] = str(item['content_type'])[:128]
            if 'size' in item:
                try:
                    ref['size'] = int(item['size'])
                except Exception:
                    ref['size'] = 0
            if 'ocr_text' in item and item['ocr_text']:
                # Reuse sanitize_text for content with higher cap
                ref['ocr_text'] = sanitize_text(item['ocr_text'], max_len=20000, neutralize_injection=True)
            out.append(ref)
        except Exception:
            continue
    return out
