"""Backward compatibility shim for legacy import path.

External code previously importing from `ai.provider` will continue to work.
New implementations live in `ai.providers` package.
"""

from .providers import (  # noqa: F401
    AIResult,
    BaseProvider,
    LocalStubProvider,
    Gpt5Provider,
    GeminiProvider,
    CompositeProvider,
    get_provider,
)
