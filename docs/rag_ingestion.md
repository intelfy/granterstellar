[[AI_CONFIG]]
FILE_TYPE: 'TECH_SPEC'
INTENDED_READER: 'ENGINEERING_TEAM'
PURPOSE: ['Describe current RAG data layer & ingestion pipeline', 'Document implemented similarity dedupe heuristics', 'Clarify deterministic guarantees & follow-ups']
PRIORITY: 'HIGH'
[[/AI_CONFIG]]

# RAG Ingestion & Retrieval (Phase 1)

Status: IMPLEMENTED (Phase 1 baseline) — this document captures what exists today and the immediate follow‑ups. Treat `.github/copilot-instructions.md` as authoritative if conflicts arise.

## Goals

1. Deterministic, auditable storage of external/template/sample grant text.
2. Minimize redundant resources (exact + near duplicates) early to control cost and noise.
3. Provide simple, deterministic retrieval ordering consumable by planner/writer prompts.
4. Allow later swap-in of higher quality embedding model & vector index without changing contract.

## Data Models

`AIResource`

- Fields: `type` (template|sample|call_snapshot|other future), `title`, `source_url`, `sha256` (full text), `metadata` (JSON), timestamps.
- SHA256 used for exact duplicate short‑circuit.

`AIChunk`

- Fields: FK `resource`, `ord` (0-based), `text`, `token_len` (approx words), `embedding` (list[float]), `embedding_key` (sha256 partial for coarse dedupe), `metadata`.
- Only up to first 200 chunks created (safety cap; current chunk size target ≈800 chars grouped by paragraph/sentence splits).

## Ingestion Pipeline (`ai/ingestion.py:create_resource_with_chunks`)

1. Exact duplicate check: compute full text sha256; reuse existing `AIResource` if match.
2. Chunk (max ~800 chars) → collect provisional chunk list.
3. Similarity dedupe (Phase 1 heuristic):
   - Embed ONLY the first provisional chunk.
   - Fetch up to the 200 most recent resources of same `type`.
   - Build map of their `ord=0` chunks with existing embeddings.
   - Two-tier near-duplicate decision:
     a. Textual prefix heuristic: if shorter first-chunk is prefix of the longer and delta < 32 chars → reuse.
     b. Cosine similarity of first-chunk embeddings ≥ adaptive threshold.
4. Adaptive threshold: default 0.97; if active backend == `hash` (deterministic pseudo‑vector) threshold lowered to 0.90 to account for coarse signal.
5. If no candidate passes, create new resource + embed all chunks.
6. Store per-chunk embeddings and set `metadata.chunks` on resource.

### Determinism Guarantees

- Embedding backend (hash mode) produces stable vectors for identical text across runs.
- Retrieval ordering (see `ai/retrieval.py`) sorts by cosine desc then chunk id for tie breaks, ensuring stable prompt context.
- Similarity dedupe evaluates candidates in strict recency order (descending id); earliest passing candidate returned → deterministic reuse given identical state.

### Heuristic Rationale

- Hash embedding backend (placeholder) has low semantic resolution; cosine alone produced false negatives for small appended tokens. Prefix + small delta heuristic cheaply recovers obvious “append a word/sentence” duplicates.
- Using only first chunk keeps ingestion O(1) embeddings per resource for dedupe; full re-embedding for all chunks happens only if creating a new resource.

### Limitations / Follow-Ups

- First-chunk only similarity can miss later-paragraph duplicate documents with divergent intros.
- Prefix heuristic ignores whitespace / case variants (acceptable for now); consider normalized Levenshtein or token-level Jaccard for more robustness.
- No vector index; linear scan over ≤200 recent resources (O(n)) — acceptable at current scale; plan HNSW / Postgres pgvector later.
- No aliasing of multiple near‑duplicates to one canonical resource id for historical backfill.

## Retrieval (`ai/retrieval.py`)

Implemented Phase 1:

- Embed query (hash backend).
- Compute cosine against all chunk embeddings (current naive scan; future: index + filtered by type / tags).
- Sort: score desc, then chunk id to guarantee stability.
- Token budget trimming helper ensures cumulative `token_len` ≤ requested limit (approximate word count metric for now).

## Governance & Audit Hooks

- Prompt context inclusion records retrieval metrics placeholder in `AIJobContext` (fields present; richer metrics TBD).
- PII redaction & template checksum drift detection occur earlier in prompting layer; ingestion operates on raw text (trust boundary: ingestion sources are curated / internal fetch). Future: optional sanitization pipeline for externally fetched grant call pages.

## Testing

Key tests (green):

- `test_ingestion_retrieval.py` — embeddings persisted & retrievable.
- `test_ingestion_retrieval_dedupe.py` — exact duplicate skipped, deterministic order.
- `test_ingestion_similarity_dedupe.py` — near duplicate reuse (append minor text) and dissimilar creates new.

## Configuration

Environment (planned future — not yet wired):

- `EMBEDDINGS_BACKEND` (hash|minilm) — when switching to MiniLM adjust similarity threshold upward again (re-evaluate ROC curve; initial guess 0.97 sufficient).
- `RAG_SIMILARITY_THRESHOLD` (float) — override default; passing 1.0 disables similarity dedupe leaving only exact sha256 check.

## Roadmap (Phase 2+)

1. Replace hash backend with MiniLM sentence embeddings (deterministic pinned model) + migrate existing vectors (store model_version; re-embed task).
2. Add pgvector index (cosine) and narrow candidate set by ANN search rather than linear scan.
3. Section-aware retrieval: tag chunks (intro/background/eligibility/budget) and allow planner to reserve budget by tag.
4. Add retrieval caching layer keyed by (resource type set, query hash, top_k) with TTL.
5. Light normalization: lower‑case, strip punctuation for dedupe similarity pass (while preserving original text in chunk storage) – improves variant collapse.
6. Expose ingestion admin: list recent ingests, indicate reused vs created, show similarity score / heuristic used.
7. Add telemetry: distribution of similarity scores for accepted vs rejected candidates to tune threshold empirically.
8. Optional edit-distance refinement: if cosine just below threshold (window e.g. [t-0.02, t)), compute normalized Levenshtein; accept if > 0.95 similarity.
9. Multi-chunk duplicate detection: compare mean of first N (e.g. 3) chunk vectors; avoids false negatives when only intro changes.
10. Content safety / sanitation for externally fetched HTML (avoid script injection even though tags stripped; consider allowlists for hostnames).

## Quick Reference (Implemented)

| Aspect | Implemented | Notes |
|--------|-------------|-------|
| Exact dedupe | Yes | sha256(full_text) short‑circuit |
| Similarity dedupe | Yes | First chunk embedding + prefix heuristic |
| Adaptive threshold | Yes | 0.97 nominal; 0.90 for hash backend |
| Chunking | Yes | ~800 char groups; cap 200 |
| Embedding backend | Hash | Deterministic placeholder |
| Retrieval ordering | Yes | cosine desc then chunk id |
| Token budget trim | Yes | Approx token = words; refine later |
| Tests coverage | Yes | 3 ingestion/retrieval test modules |
| Metrics (detailed) | Partial | Hooks exist; expansion pending |

## Change Log (Doc)

- 2025-09-09: Initial spec documenting Phase 1 ingestion & retrieval.

---

Questions / improvements: add backlog item in `Todo.md` under AI/RAG or open issue referencing this doc.
