"""Centralized key-value copy loader (pre-i18n).

Loads `locales/en.yml`, flattens nested dictionaries into dot keys, and exposes a
`t(key, **kwargs)` helper for interpolation. Designed to be minimal now while
allowing future locale expansion.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import yaml

_LOCK = threading.RLock()
_KEYS: dict[str, str] = {}
_LOCALE_FILE = Path(__file__).resolve().parents[3] / 'locales' / 'en.yml'
_LAST_MTIME: float | None = None


def _flatten(prefix: str, data: dict[str, Any], out: dict[str, str]) -> None:
    for k, v in data.items():
        key = f'{prefix}.{k}' if prefix else k
        if isinstance(v, dict):
            _flatten(key, v, out)
        else:
            if not isinstance(v, str):
                v = str(v)
            out[key] = v


def _load(force: bool = False) -> None:
    global _KEYS, _LAST_MTIME
    if not _LOCALE_FILE.exists():  # pragma: no cover - defensive
        return
    mtime = _LOCALE_FILE.stat().st_mtime
    if not force and _LAST_MTIME is not None and mtime == _LAST_MTIME:
        return
    with _LOCK:
        with _LOCALE_FILE.open('r', encoding='utf-8') as f:
            raw = yaml.safe_load(f) or {}
        flat: dict[str, str] = {}
        if isinstance(raw, dict):
            _flatten('', raw, flat)
        _KEYS = flat
        _LAST_MTIME = mtime


def t(key: str, **kwargs: Any) -> str:
    """Translate (fetch) a key and format with kwargs.

    Fallback strategy: if key missing, return the key itself (visible sentinel).
    Missing interpolation variables are left unformatted.
    """
    # Hot reload in DEBUG (simple mtime check). Avoid importing settings at module import time.
    from django.conf import settings  # local import to avoid early settings access

    if getattr(settings, 'DEBUG', False):
        try:
            _load()
        except Exception:  # pragma: no cover - never raise in production path
            pass
    msg = _KEYS.get(key, key)
    if not kwargs:
        return msg
    try:
        return msg.format(**kwargs)
    except Exception:  # leave placeholders intact if mismatch
        return msg


def ready() -> None:
    """Initialize key store (call from AppConfig.ready)."""
    try:
        _load(force=True)
    except Exception:  # pragma: no cover - never break app startup over copy
        pass


__all__ = ['t', 'ready']
