"""Retrieval utilities (Phase 2 scaffolding)."""
from __future__ import annotations

from typing import Sequence
from math import sqrt
from .models import AIChunk
from .embedding_service import embed_texts


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    da = sqrt(sum(x * x for x in a)) or 1.0
    db = sqrt(sum(y * y for y in b)) or 1.0
    return num / (da * db)


def retrieve_top_k(query_text: str, *, k: int = 6) -> list[dict]:
    if not query_text:
        return []
    q_vec = embed_texts([query_text])[0]
    chunks = AIChunk.objects.all().select_related("resource")[:500]  # soft cap for now
    scored = []
    for ch in chunks:
        if ch.embedding:
            c_vec = ch.embedding
        else:
            # Backfill missing embedding (older rows); store once
            c_vec = embed_texts([ch.text])[0]
            AIChunk.objects.filter(pk=ch.pk).update(embedding=c_vec)  # pragma: no cover
        score = _cosine(q_vec, c_vec)
        scored.append((score, ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for score, ch in scored[:k]:
        out.append({
            "chunk_id": ch.id,
            "resource_id": ch.resource_id,
            "score": round(score, 4),
            "text": ch.text,
            "type": ch.resource.type,
        })
    return out


def retrieve_for_plan(grant_url: str | None, text_spec: str | None) -> list[dict]:
    query = (text_spec or "") + " " + (grant_url or "")
    return retrieve_top_k(query.strip(), k=6)


def retrieve_for_section(section_id: str, answers: dict[str, str] | None) -> list[dict]:
    base = section_id + " " + " ".join((answers or {}).values())
    return retrieve_top_k(base.strip(), k=6)
