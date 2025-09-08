"""Embedding service abstraction (Phase 1).

Initial DEV backend: placeholder deterministic hash -> pseudo-vector so downstream code
can be wired before pulling heavy dependencies. Later replace with MiniLM.
"""
from __future__ import annotations
from threading import Lock
import hashlib
from typing import Iterable

_DIM = 32  # placeholder dimension (MiniLM-L6-v2 will be 384)


class EmbeddingService:
    _instance: EmbeddingService | None = None
    _lock = Lock()

    def __init__(self):
        self.model_name = "placeholder-hash-v1"
        self.dim = _DIM

    @classmethod
    def instance(cls) -> EmbeddingService:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def embed(self, texts: Iterable[str]) -> list[list[float]]:
        vecs: list[list[float]] = []
        for t in texts:
            h = hashlib.sha256(t.encode('utf-8')).digest()
            # derive deterministic pseudo vector
            nums = list(h[: self.dim])
            # normalize to 0..1
            vec = [n / 255.0 for n in nums]
            # pad if digest shorter than dim slice (not the case here but future-proof)
            if len(vec) < self.dim:
                vec.extend([0.0] * (self.dim - len(vec)))
            vecs.append(vec)
        return vecs


def embed_texts(texts: Iterable[str]) -> list[list[float]]:
    return EmbeddingService.instance().embed(texts)
