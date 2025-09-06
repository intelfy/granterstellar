"""Environment-aware settings loader.

Select settings module via DJANGO_ENV (dev, prod, test). Falls back to base.
Keeps backward compatibility with existing 'app.settings' reference.
"""
import os
from .base import *  # noqa: F401,F403

_env = os.getenv('DJANGO_ENV', '').lower()
if _env.startswith('prod'):
    from .prod import *  # noqa: F401,F403
elif _env.startswith('test') or 'PYTEST_CURRENT_TEST' in os.environ:
    from .test import *  # noqa: F401,F403
elif _env.startswith('dev') or os.getenv('DEBUG', '0') == '1':
    from .dev import *  # noqa: F401,F403
# else: base only
