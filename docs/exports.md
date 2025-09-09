[[AI_CONFIG]]
FILE_TYPE: 'EXPORTS_COMBINED'
INTENDED_READER: 'AI_AGENT'
PURPOSE: ['Single source for exports architecture','Explain async vs sync operation','Document deterministic export contract','Guide future format additions']
PRIORITY: 'MEDIUM'
[[/AI_CONFIG]]

# Exports Architecture (Async + Deterministic Contract)

This unified document replaces `exports_async.md` and `deterministic_exports.md`.

## Overview

The exports subsystem converts proposal content into one of:

- Markdown (`.md`)
- PDF (`.pdf`)
- DOCX (`.docx`)

Goals:

- Deterministic (bit / checksum stable) artifacts for identical logical input.
- Optional asynchronous offloading via Celery.
- Extensible normalization pipeline for future formats.

## Sync vs Async

Default mode: synchronous in-request generation.
Optional async: set `EXPORTS_ASYNC=1` and run a Celery worker (Redis broker/backends).

When async:

1. POST `/api/exports` creates an Export job (`status=pending`).
2. Worker executes `exports.tasks.perform_export`.
3. Client polls GET `/api/exports/{id}` until `status=done` with `url`.

Environment keys:

- `EXPORTS_ASYNC=1` — enable async pathway.
- `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` — usually `redis://...` (or use `REDIS_URL`).

Worker start (repo root → `api/`):

```bash
celery -A app.celery:app worker -l info
```

Fallback semantics: If async env not satisfied the API transparently performs a synchronous export (no error).

## Deterministic Contract

Every export yields:

1. Raw artifact bytes.
2. A SHA-256 checksum computed over a normalized representation.

Normalized bytes MUST be stable for equal logical content (proposal text + ordering).
Raw bytes SHOULD also be stable; normalization is the safety net.

### Markdown

- Direct string assembly; no timestamps.
- Checksum over UTF‑8 bytes of final markdown.

### PDF

Library: ReportLab.

Potential nondeterminism: `/CreationDate`, `/ModDate`, `/ID`, xref offsets.

Mitigations:

1. Generation sets predictable metadata.
2. Post-process replaces dates with epoch `D:19700101000000Z`.
3. Normalizer canonicalizes `/ID` and `startxref` to fixed tokens.

Checksum over normalized bytes.

### DOCX

Library: python-docx (ZIP container).

Nondeterminism: ZIP entry timestamps, ordering.

Mitigations:

1. Force core properties (created/modified/printed) to epoch.
2. Rebuild ZIP with sorted filenames, fixed timestamp (1980-01-01 00:00:00), uniform perms (0600).
3. Checksum over canonical ZIP bytes (raw == normalized after rebuild).

### Normalization Principles

- Lossless for semantic meaning.
- Idempotent: multiple runs produce identical bytes.
- Localized: each format has a `_normalize_*` helper.

### Adding a New Format

1. Implement `render_*` producing raw bytes.
2. Identify nondeterministic fields; neutralize or post-process.
3. Create `_normalize_*_for_checksum` (lossless + idempotent).
4. Compute checksum via existing checksum util.
5. Add tests: double render stability, targeted normalization markers.
6. Update this document (section: New Formats) and index.

## Testing & Guarantees

Current tests assert:

- Markdown checksum stability.
- PDF normalized checksum + metadata rewrites.
- DOCX checksum (raw equality due to full canonicalization).

Future improvements:

- Pluggable normalization registry.
- Content-addressable storage keyed by checksum.
- Build CI step verifying no accidental nondeterminism regressions (e.g., diffing two sequential renders).

## Failure Modes

- If regex normalization fails, checksum may drift; tests should catch.
- Any library upgrade potentially reintroduces nondeterminism; always re-run determinism tests after dependency bumps.

## Operational Notes

- Large exports run faster async; enable worker before toggling `EXPORTS_ASYNC` in prod.
- Media backup must include exported files (under `media/`).
- Stable checksums allow safe client/proxy caching and dedupe.

## New Formats (Placeholder Log)

- (None pending) — add entry here when introducing e.g. HTML, EPUB, JSONL.

---
Merged from: `exports_async.md` + `deterministic_exports.md` (archived). Keep this file authoritative.
