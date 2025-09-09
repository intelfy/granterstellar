import re
from typing import Any, Tuple
from urllib.parse import urlparse
from django.conf import settings


# Basic controls/invisible characters to strip (keep tabs/newlines)
_CTRL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
_INVISIBLE_RE = re.compile(r'[\u200B-\u200F\u202A-\u202E\u2060\u2061\u2062\u2063\u2064\u206A-\u206F\uFEFF]')

# Legacy simple injection patterns (kept for backward compatibility)
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


def sanitize_text(
    value: Any, *, max_len: int = 10000, neutralize_injection: bool = True, use_shield: bool = True
) -> Tuple[str, dict]:
    """Return a sanitized string safe to forward to LLMs or logs.

    - Coerces to str
    - Strips control/invisible characters
    - Trims length
    - Optionally neutralizes common prompt-injection phrases
    - Optionally uses advanced prompt shield (if enabled)
    
    Returns: (sanitized_text, metadata)
    """
    if value is None:
        return '', {}
    
    s = str(value)
    metadata = {'original_length': len(s)}
    
    # Normalize newlines
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    s = _CTRL_RE.sub('', s)
    s = _INVISIBLE_RE.sub('', s)
    
    # Apply prompt shield if enabled and configured
    if use_shield and getattr(settings, 'AI_PROMPT_SHIELD_ENABLED', True):
        try:
            from .prompt_shield import prompt_shield_middleware
            allowed, s, shield_metadata = prompt_shield_middleware(s)
            metadata.update(shield_metadata)
            if not allowed:
                # Return empty string if blocked by shield, let caller handle appropriately
                metadata['blocked_by_shield'] = True
                return '', metadata
        except ImportError:
            # Fallback to legacy injection detection if shield not available
            pass
    
    # Legacy injection neutralization (fallback or supplement)
    if neutralize_injection:
        s = _INJECTION_RE.sub('[redacted]', s)
        
    if len(s) > max_len:
        s = s[:max_len]
        metadata['truncated'] = True
        
    metadata['final_length'] = len(s)
    return s, metadata


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
            sanitized_text, metadata = sanitize_text(v)
            # Skip entries that were blocked by the shield
            if not metadata.get('blocked_by_shield', False):
                cleaned[key] = sanitized_text
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
                ocr_text, metadata = sanitize_text(item['ocr_text'], max_len=20000, neutralize_injection=True)
                # Only include OCR text if it wasn't blocked
                if not metadata.get('blocked_by_shield', False):
                    ref['ocr_text'] = ocr_text
            out.append(ref)
        except Exception:
            continue
    return out
