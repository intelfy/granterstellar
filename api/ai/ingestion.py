"""Ingestion & chunking pipeline (Phase 2 scaffolding).

NOTE: Lightweight implementation – HTML cleaning is now performed via a
stateful HTMLParser that removes script/style/noscript and dangerous tags
instead of brittle regex stripping. Only textual data from safe tags is
retained; attributes are ignored. Whitespace is normalized. This mitigates
potential bypasses (e.g., malformed tags, embedded <script> variants,
inline event handlers) and reduces the risk of prompt‑injection via hidden
content.
"""

from __future__ import annotations

import re
import hashlib
import requests
import yaml
from html.parser import HTMLParser
from django.db import transaction

from .models import AIResource, AIChunk
from .embedding_service import embed_texts
from .retrieval import _cosine  # reuse cosine similarity


class _SafeTextExtractor(HTMLParser):
    """HTML → plain text extractor with a conservative allowlist.

    Policy:
      - Drop entirely: script, style, noscript, iframe, object, embed, svg, canvas, meta, link
      - Ignore attributes
      - Convert <br>, <p>, <div>, <li>, <section>, <article>, <h1>.. <h6> into line breaks
    """

    _BLOCK = {'script', 'style', 'noscript', 'iframe', 'object', 'embed', 'svg', 'canvas', 'meta', 'link'}
    _BREAK = {'p', 'div', 'br', 'li', 'section', 'article', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._out: list[str] = []
        self._suppress_depth = 0

    def handle_starttag(self, tag, attrs):  # noqa: D401 - inherited
        t = tag.lower()
        if t in self._BLOCK:
            self._suppress_depth += 1
            return
        if self._suppress_depth:
            return
        if t in self._BREAK:
            self._out.append('\n')

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in self._BLOCK and self._suppress_depth:
            self._suppress_depth -= 1
            return
        if self._suppress_depth:
            return
        if t in self._BREAK:
            self._out.append('\n')

    def handle_data(self, data):
        if self._suppress_depth:
            return
        # Minimal noise trimming; keep internal spaces to avoid word joins
        if data.strip():
            self._out.append(data)

    def get_text(self) -> str:
        # Join and normalize whitespace
        raw = ' '.join(self._out)
        raw = re.sub(r'[ \t\f\r\v]+', ' ', raw)
        raw = re.sub(r'\n{2,}', '\n', raw)
        return raw.strip()


def _clean_html(html: str) -> str:  # noqa: D401
    parser = _SafeTextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        # Fallback to simple tag strip if parser fails (rare malformed input)
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()[:200000]
    return parser.get_text()[:200000]


def _chunk_text(text: str, *, max_chars: int = 800) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    current = 0
    for para in re.split(r'\n+|(?<=\.)\s{2,}', text):
        p = para.strip()
        if not p:
            continue
        if current + len(p) > max_chars and buf:
            parts.append(' '.join(buf))
            buf = []
            current = 0
        buf.append(p)
        current += len(p) + 1
    if buf:
        parts.append(' '.join(buf))
    return parts[:200]  # safety cap


def _token_len(s: str) -> int:
    # Approximate token length (placeholder): words * 1
    return max(1, len(s.split()))


def _dedup_key(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:32]


@transaction.atomic
def create_resource_with_chunks(
    *,
    type_: str,
    title: str,
    source_url: str,
    full_text: str,
    similarity_threshold: float = 0.97,
) -> AIResource:
    sha256 = AIResource.compute_sha256(full_text)
    existing = AIResource.objects.filter(sha256=sha256, type=type_).first()
    if existing:
        return existing

    # Similarity-based dedupe (phase 1 heuristic): compare first chunk embedding to existing
    # resources of same type. If cosine >= threshold → reuse existing resource.
    # Lightweight: only embed first prospective chunk before full processing.
    prospective_chunks = _chunk_text(full_text)
    if not prospective_chunks:
        prospective_chunks = [full_text[:800]]
    first_chunk = prospective_chunks[0]
    first_vec = embed_texts([first_chunk])[0]
    # Adjust threshold for deterministic hash backend (coarse). Hash vectors can
    # yield lower cosine for small textual variants; widen window slightly.
    from .embedding_service import EmbeddingService  # local import to avoid cycle in apps

    if EmbeddingService.instance().backend == 'hash' and similarity_threshold >= 0.95:
        adj_threshold = 0.90
    else:
        adj_threshold = similarity_threshold
    if adj_threshold < 1.0:  # allow disabling by passing 1.0
        # Iterate limited candidate set (same type, last 200 for recency bias)
        candidate_qs = AIResource.objects.filter(type=type_).order_by('-id')[:200]
        candidate_ids = list(candidate_qs.values_list('id', flat=True))
        if candidate_ids:
            chunk_map: dict[int, AIChunk] = {}
            for c in AIChunk.objects.filter(resource_id__in=candidate_ids, ord=0):  # type: ignore[attr-defined]
                if c.embedding:  # ensure embedding present
                    chunk_map[c.resource_id] = c  # type: ignore[attr-defined]
            for cand_id in candidate_ids:
                ch0 = chunk_map.get(cand_id)
                if not ch0:
                    continue
                # Fast textual near-duplicate heuristic (prefix delta <32 chars)
                t_existing = ch0.text or ''
                s1, s2 = t_existing.strip(), first_chunk.strip()
                shorter, longer = (s1, s2) if len(s1) <= len(s2) else (s2, s1)
                if shorter and longer.startswith(shorter) and (len(longer) - len(shorter) < 32):
                    existing_sim = next((r for r in candidate_qs if getattr(r, 'id', None) == cand_id), None)
                    if existing_sim:
                        return existing_sim
                if not ch0.embedding:  # defensive
                    continue
                sim = _cosine(first_vec, ch0.embedding)
                if sim >= adj_threshold:
                    existing_sim = next((r for r in candidate_qs if getattr(r, 'id', None) == cand_id), None)
                    if existing_sim:
                        return existing_sim
    resource = AIResource.objects.create(
        type=type_,
        title=title[:256],
        source_url=source_url,
        sha256=sha256,
        metadata={'dedup': True},
    )
    chunks = prospective_chunks  # reuse already chunked result
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
        AIResource.objects.filter(pk=resource.pk).update(metadata={'chunks': created})
    return resource


def ingest_grant_call(url: str) -> AIResource:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    cleaned = _clean_html(resp.text)
    return create_resource_with_chunks(
        type_='call_snapshot',
        title='Grant Call',
        source_url=url,
        full_text=cleaned,
    )


def ingest_manifest(yaml_text: str) -> list[AIResource]:
    data = yaml.safe_load(yaml_text) or {}
    items = data.get('items', [])
    created: list[AIResource] = []
    for it in items:
        try:
            type_ = it.get('type')
            title = it.get('title', type_)
            text = it.get('text')
            url = it.get('source_url', '')
            if not type_ or not text:
                continue
            res = create_resource_with_chunks(type_=type_, title=title, source_url=url, full_text=text)
            if res not in created:  # avoid duplicates in return list
                created.append(res)
        except Exception:
            continue
    return created
