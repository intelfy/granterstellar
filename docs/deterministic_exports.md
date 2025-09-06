# Deterministic Exports Contract

This document describes how export formats achieve deterministic (reproducible) output and how to extend the system safely.

Determinism matters for:

- Caching & de-duplication (stable content addressable checksum)
- Auditing & provenance (verifiable reproduction)
- Test reliability

## Contract Overview

For every export operation we produce:

1. Raw bytes (the downloadable artifact)
2. A checksum (current: SHA-256 hex) computed over a normalized representation

The checksum MUST be stable across runs for identical logical proposal content.
Raw bytes SHOULD be stable. Where an upstream library injects volatile data, we post-process to enforce stability. Normalization acts as a final safety net.

## Format Specifics

### Markdown (.md)

- Generated directly from proposal JSON (`proposal_json_to_markdown`).
- Pure string assembly; output is inherently deterministic given stable input ordering.
- Checksum is simply over the UTF-8 bytes.

### PDF (.pdf)

Library: ReportLab.

Potential nondeterminism sources: document ID, xref offset, creation/modification timestamps, internal object ordering.

Mitigations:

1. During generation we set predictable metadata (title, author, etc.).
2. Post-generation in `render_pdf_from_text` we regex-rewrite `/CreationDate` and `/ModDate` to epoch `D:19700101000000Z` ensuring raw bytes no longer carry wall-clock time.
3. `_normalize_pdf_for_checksum` further canonicalizes:
   - `/ID [<...><...>]` → `/ID [<000000><000000>]`
   - `startxref <number>` → `startxref 0`
   - (Idempotently re-applies date normalization in case upstream changes revert step 2.)

The checksum is computed on the normalized bytes. Raw bytes are now also stable after step 2 (dates) plus ReportLab's otherwise consistent layout for our simple usage.

### DOCX (.docx)

Library: python-docx (zip container).

Nondeterminism sources: ZIP entry timestamps, ordering, metadata times.

Mitigations:

1. Core properties (title, author, created, modified, last_printed) forced to epoch.
2. After saving, we rebuild the DOCX zip with:
   - Sorted entry names
   - Fixed timestamp (1980-01-01 00:00:00) for every file
   - Uniform permissions `0o600`

The checksum uses the canonicalized zip bytes (raw bytes already canonical after transformation).

## Normalization Idempotence

Normalization operations are written to be idempotent: running them multiple times produces the same bytes. This allows tests to safely re-normalize artifacts.

## Adding a New Export Format

1. Generate raw bytes in a dedicated `render_*` function.
2. Identify nondeterministic fields (timestamps, random IDs, ordering) and neutralize them either during generation or via a `_normalize_*_for_checksum` helper.
3. Ensure normalization is:
   - Lossless for semantic meaning
   - Idempotent
4. Compute checksum using `from app.common.files import compute_checksum` on normalized bytes.
5. Add tests:
   - Double render → same checksum
   - Spot check key normalized markers
6. Update this document with the new format section.

## Testing Strategy

Current tests cover:

- Markdown checksum stability
- PDF deterministic checksum + metadata markers
- DOCX checksum + raw equality (due to full canonicalization)

Future additions should mimic this pattern.

## Rationale for Separate Raw vs Normalized

We preserve original raw bytes (when already deterministic) for user download while using a stricter canonical form for hashing. This allows future expansion (e.g., embedding generation timestamps for user context) without breaking caching or equality tests—provided normalization can remove or standardize those fields.

## Extending Checksum Semantics

If we later switch algorithms (e.g., BLAKE3), we should:

- Version the checksum scheme (e.g., `blake3:<hex>`)
- Maintain backward compatibility for stored historical values

## Safety & Failure Modes

- If normalization regex fails (unexpected structure) we fall back silently; checksum might then vary. Tests would expose this regression.
- Defensive try/except blocks are limited to normalization, not core rendering.

## Open Follow-Ups

- Formal interface for normalization helpers (protocol / registry)
- Optional content-addressable storage keyed by checksum
- Structured logging of export operations including checksum

---
Maintainer note: keep this document aligned with implementation changes (enforced via review checklist).
