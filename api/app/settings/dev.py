from . import base

# Re-export uppercase symbols from base
for k, v in base.__dict__.items():
    if k.isupper():
        globals()[k] = v

# Development overrides
DEBUG = True
_allowed = list(getattr(base, 'ALLOWED_HOSTS', []))
if '*' not in _allowed:
    for h in ['127.0.0.1', 'localhost']:
        if h not in _allowed:
            _allowed.append(h)
ALLOWED_HOSTS = _allowed
