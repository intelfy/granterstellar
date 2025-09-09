"""AI provider package with factory selection.

Backwards compatibility: existing imports from ai.provider.get_provider are
supported via a shim module (see ai/provider.py) which now re-exports here.
"""

from .base import BaseProvider, AIResult  # noqa: F401
from .stub import LocalStubProvider  # noqa: F401
from .gpt5 import Gpt5Provider  # noqa: F401
from .gemini import GeminiProvider  # noqa: F401
from .composite import CompositeProvider  # noqa: F401


def get_provider(name: str | None = None) -> BaseProvider:
    key = (name or 'composite').lower()
    if key == 'stub':
        return LocalStubProvider()
    if key == 'gpt5':
        return Gpt5Provider()
    if key == 'gemini':
        return GeminiProvider()
    return CompositeProvider()


__all__ = [
    'AIResult',
    'BaseProvider',
    'LocalStubProvider',
    'Gpt5Provider',
    'GeminiProvider',
    'CompositeProvider',
    'get_provider',
]
