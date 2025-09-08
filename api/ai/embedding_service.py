"""Embedding service abstraction (Phase 1).

DEV baseline: deterministic hash pseudo-vectors so the rest of the pipeline can
be wired before pulling heavier embedding dependencies. Optional MiniLM switch
behind EMBEDDING_BACKEND env ("hash" | "minilm"). Fallback to hash on errors.
"""

from __future__ import annotations

import hashlib
import os
from threading import Lock
from typing import Any, Iterable, Literal, cast

_HASH_DIM = 32  # placeholder dimension (MiniLM-L6-v2 is 384)


class EmbeddingService:
    _instance: EmbeddingService | None = None
    _lock = Lock()

    def __init__(self) -> None:
        env_backend = os.getenv("EMBEDDING_BACKEND", "hash").lower()
        if env_backend not in ("hash", "minilm"):
            env_backend = "hash"
        self.backend = cast(Literal["hash", "minilm"], env_backend)

        self.model_name = (
            "placeholder-hash-v1" if self.backend == "hash" else "MiniLM-L6-v2"
        )
        self.dim = _HASH_DIM if self.backend == "hash" else 384
        self._model: Any | None = None

        if self.backend == "minilm":  # lazy heavy import; pragma: no cover (optional path)
            try:  # pragma: no cover
                from sentence_transformers import SentenceTransformer  # type: ignore

                self._model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception:  # fallback silently to hash if failure
                self.backend = cast(Literal["hash", "minilm"], "hash")
                self.model_name = "placeholder-hash-v1"
                self.dim = _HASH_DIM
                self._model = None

    # -- lifecycle -----------------------------------------------------
    @classmethod
    def instance(cls) -> EmbeddingService:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # -- public api ----------------------------------------------------
    def embed(self, texts: Iterable[str]) -> list[list[float]]:
        items = list(texts)
        if not items:
            return []

        if self.backend == "minilm" and self._model is not None:  # pragma: no cover
            try:  # pragma: no cover
                emb = self._model.encode(items, normalize_embeddings=True)
                return [[float(x) for x in row] for row in emb]
            except Exception:  # fallback to hash
                pass

        # hash backend (deterministic pseudo-vector)
        out: list[list[float]] = []
        for text in items:
            h = hashlib.sha256(text.encode("utf-8")).digest()
            nums = list(h[: self.dim])
            vec = [n / 255.0 for n in nums]
            if len(vec) < self.dim:  # defensive (should not happen with sha256 slice)
                vec.extend([0.0] * (self.dim - len(vec)))
            out.append(vec)
        return out

    def health(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "model": self.model_name,
            "dim": self.dim,
            "ready": self.backend == "hash" or (self._model is not None),
        }


def embed_texts(texts: Iterable[str]) -> list[list[float]]:
    return EmbeddingService.instance().embed(texts)
