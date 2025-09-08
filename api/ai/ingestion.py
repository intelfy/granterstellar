"""Ingestion & chunking pipeline (Phase 2 scaffolding).

NOTE: Lightweight implementation – HTML cleaning is simplistic; replace with
readability/boilerplate removal in future iteration.
"""
from __future__ import annotations

import re
import hashlib
import requests
import yaml
from django.db import transaction

from .models import AIResource, AIChunk
from .embedding_service import embed_texts


def _clean_html(html: str) -> str:
    # Remove scripts/styles
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # Strip tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _chunk_text(text: str, *, max_chars: int = 800) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    current = 0
    for para in re.split(r"\n+|(?<=\.)\s{2,}", text):
        p = para.strip()
        if not p:
            continue
        if current + len(p) > max_chars and buf:
            parts.append(" ".join(buf))
            buf = []
            current = 0
        buf.append(p)
        current += len(p) + 1
    if buf:
        parts.append(" ".join(buf))
    return parts[:200]  # safety cap


def _token_len(s: str) -> int:
    # Approximate token length (placeholder): words * 1
    return max(1, len(s.split()))


def _dedup_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


@transaction.atomic
def create_resource_with_chunks(*, type_: str, title: str, source_url: str, full_text: str) -> AIResource:
    sha256 = AIResource.compute_sha256(full_text)
    existing = AIResource.objects.filter(sha256=sha256, type=type_).first()
    if existing:
        return existing
    resource = AIResource.objects.create(
        type=type_,
        title=title[:256],
        source_url=source_url,
        sha256=sha256,
        metadata={"dedup": True},
    )
    chunks = _chunk_text(full_text)
    embeddings = embed_texts(chunks)
    created = 0
    for idx, (chunk_text, vec) in enumerate(zip(chunks, embeddings)):
        AIChunk.objects.create(
            resource=resource,
            ord=idx,
            text=chunk_text,
            token_len=_token_len(chunk_text),
            embedding_key=_dedup_key(chunk_text + str(len(vec))),
            embedding=vec,
            metadata={},
        )
        created += 1
    # Attach simple ingestion stats
    if created:
        AIResource.objects.filter(pk=resource.pk).update(metadata={"chunks": created})
    return resource


def ingest_grant_call(url: str) -> AIResource:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    cleaned = _clean_html(resp.text)
    return create_resource_with_chunks(
        type_="call_snapshot",
        title="Grant Call",
        source_url=url,
        full_text=cleaned,
    )


def ingest_manifest(yaml_text: str) -> list[AIResource]:
    data = yaml.safe_load(yaml_text) or {}
    items = data.get("items", [])
    created: list[AIResource] = []
    for it in items:
        try:
            type_ = it.get("type")
            title = it.get("title", type_)
            text = it.get("text")
            url = it.get("source_url", "")
            if not type_ or not text:
                continue
            res = create_resource_with_chunks(type_=type_, title=title, source_url=url, full_text=text)
            if res not in created:  # avoid duplicates in return list
                created.append(res)
        except Exception:
            continue
    return created
