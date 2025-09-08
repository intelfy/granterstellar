# Prompt Contracts & Rendering System

## Purpose

Provide deterministic, auditable prompts for AI roles (planner, writer, formatter, etc.) with:

- Strict variable contracts (no missing, no extra keys)
- Versioned, stored templates (DB via `AIPromptTemplate`)
- Redacted persisted snapshot (`AIJobContext.rendered_prompt_redacted`)
- Safe fallback prompt when no active template
- Test coverage to prevent regression

## Data Model

### AIPromptTemplate

| Field | Description |
|-------|-------------|
| name | Canonical template name (e.g. `planner.base`) |
| version | Monotonic integer; combined (name, version, role) identifies variant |
| role | AI role this template applies to (e.g. `planner`, `writer`) |
| template | Mustache-style body with `{{variable}}` placeholders |
| variables | Explicit ordered list of allowed variable identifiers |
| active | Only one active variant per (name, role) expected; inactive variants retained for audit |
| checksum | Integrity / tamper detection hash (sha256 of template text) |
| blueprint_schema | Optional JSON schema-like structure guiding formatter output |
| blueprint_instructions | Human-authored instructions appended for formatter role |
| created_at / updated_at | Audit timestamps |

### AIJobContext (prompt-related fields)

| Field | Description |
|-------|-------------|
| job | FK to `AIJob` executing the role task |
| prompt_template | FK to `AIPromptTemplate` used (nullable if fallback) |
| prompt_version | Copy of template version (immutable snapshot) |
| rendered_prompt_redacted | Persisted redacted render stored for audit & replay |
| template_sha256 | Snapshot of template text hash at job time (drift detection) |
| redaction_map | Mapping of redacted token → classification category |
| model_params | Model configuration used (temperature, top_p, etc.) |
| snippet_ids | Reference list for injected snippets (future richer relation) |
| retrieval_metrics | Embedding / retrieval stats for traceability |

## Rendering Flow

1. Role code calls `render_role_prompt(role=..., variables=...)`.
2. Fetch active `AIPromptTemplate` for role if present; else construct fallback template:

   ```text
   ROLE: <role>\nINPUT: {{input_json}}\n
   ```

3. Validate variable contract:
   - Missing required var -> raise `PromptTemplateError`
   - Extra unexpected var -> raise `PromptTemplateError`
4. Perform variable substitution (simple mustache style, no logic blocks). All variables treated as plain text (callers pre-sanitize complex objects to JSON strings if needed).
5. Redaction pass over final rendered prompt.
6. Return object containing: original template (or None), rendered text, redacted text, variable set.
7. Caller persists `AIJobContext` with redacted snapshot + template FK + version.

## Redaction System (Deterministic Taxonomy)

Extended deterministic redaction replaces simple `[REDACTED_*]` tokens with category + stable hash fragments:

```text
[EMAIL_<hash10>]
[NUMBER_<hash10>]
[PHONE_<hash10>]
[ID_CODE_<hash10>]
[SIMPLE_NAME_<hash10>]
[ADDRESS_LINE_<hash10>]
```

Where `<hash10>` = first 10 hex chars of sha256(original_match). This provides:

- Determinism: identical source value → identical token across renders for correlation.
- Non-reversibility (without original text) while preserving frequency & position signals.
- Compactness: bounded token length even for long originals.

`AIJobContext.redaction_map` stores token → classification (never the raw value) enabling audits to quantify redacted entity types.

Truncation: if redacted prompt exceeds 20k chars it is truncated with an ellipsis.

Adding a New Classification:

1. Add pattern & label to `AIJobContext.redact_with_mapping` patterns list (order matters: earlier patterns win on overlaps).
2. Add/update tests in `ai/tests/test_prompt_rendering.py` asserting category presence (avoid hardcoding hash fragment).
3. Update this doc section.

Design Constraints:

- No overlapping group names that produce ambiguous tokens.
- Hash fragment length chosen to keep collision probability negligible for expected corpus size.

Legacy Compatibility: `AIJobContext.redact` remains as a thin wrapper for callers expecting the legacy API.

Future Improvements:

- Optional reversible encryption (internal only) for regulated audit reconstruction.
- Statistical reporting of category counts per job for anomaly detection.

## Blueprint Injection (Formatter Role)

Formatter prompts can include structured output guidance to reduce shape drift between formatting passes:

- `blueprint_instructions` (free-form text) appended under a `STRUCTURE BLUEPRINT INSTRUCTIONS` separator.
- `blueprint_schema` (JSON) serialized deterministically with sorted keys beneath a `SCHEMA JSON:` header.

Injection occurs only when role == `formatter` and at least one of the blueprint fields is non-empty. Other roles are unaffected, keeping prompts minimal.

Rationale:

- Enforces a canonical layout contract (sections hierarchy, required fields) without embedding parsing logic client-side.
- Allows incremental evolution: new schema keys require a new template version; tests assert presence.

Guardrails:

- Schema JSON serialization errors are swallowed (defensive) but should be prevented via pre-save validation in future.
- Instructions trimmed to avoid trailing whitespace bloat.

## Template Drift Detection

Silent edits to template text (mutation of `template` field for an existing version) are detectable by comparing:

```text
stored_ctx.template_sha256  vs  sha256(current_template_text)
```

`detect_template_drift(ctx)` refetches current template text from the DB each call to avoid stale in-memory objects masking drift. A mismatch signals drift (True) and should trigger investigation:

Recommended Response:

1. Diff DB row against VCS history (template text should be immutable post-release).
2. If intentional emergency hotfix: create a new version and migrate consumers; mark prior version inactive; document change.
3. If unintentional: revert DB text to match committed version; rotate affected contexts if necessary.

Limitations:

- If both DB and context were modified with the same tampered text before any job ran, drift for those jobs is undetectable (use VCS/migrations discipline).

## Developer Workflow Additions

When updating or adding prompt templates with blueprints / new redaction classes:

1. Create new `AIPromptTemplate` row (never mutate old text) with incremented `version`.
2. Include `blueprint_schema` (minimal JSON schema fragment) & `blueprint_instructions` where structural output matters.
3. Run AI test suite: `API: test (ai)` ensuring prompt rendering & drift tests pass.
4. If adding redaction classification, update tests and this doc.
5. Update CHANGELOG (Unreleased → Added / Changed) summarizing impact.
6. Run link checker to ensure new anchors/links are valid.

Testing Guidance:

- Avoid asserting full token (hash portion). Use `assertIn('[EMAIL_', text)` patterns.
- For drift tests: modify `template` field after context creation without altering `template_sha256` to force detection.

Operational Monitoring (Proposed):

- Count drift detections per 24h; non-zero should alert.
- Aggregate redaction category counts to spot unexpected spikes (e.g., sudden surge in ID_CODE).


## Strict Variable Contract

Rationale:

- Prevent silent template drift when new variables introduced
- Guarantee reproducibility & test determinism
- Guard against prompt injection via unsanctioned fields

Mechanics:

- Template stores canonical variable list
- Supplied `variables` dict must match exactly (set equality)
- Order not required; equality done on set semantics

## Fallback Prompt

Used when:

- No active template exists for the role
- Avoids runtime failure in early development / migration windows

Characteristics:

- Minimal shape; includes role & JSON serialized input payload
- `prompt_template` field is `NULL` in context for clarity

## Versioning Strategy

- Increment `version` manually when making semantically meaningful changes (wording tweaks that could affect model behavior)
- Never mutate existing `template` text for an already deployed version; create a new row
- Deactivate older version only after new passes tests; keep row for audit
- Future: enhance with cryptographic checksum + optional signing

## Testing

`ai/tests/test_prompt_rendering.py` covers:

- Happy path strict substitution
- Missing variable raises
- Extra variable raises
- Fallback path when no template
- Integration: context persistence with correct FK + redacted snapshot
- Redaction of email + long number

Other related tests exercise downstream usage (metrics, provider routing, section locking) ensuring prompt integration side-effects remain stable.

## Operational Guidance

- When introducing new role variables: create new template version, update tests, deploy migrations if necessary.
- Add explicit test asserting new variable presence to force awareness.
- Keep variable names concise, snake_case, semantic.
- Prefer transforming complex nested objects into curated, size-limited strings before passing to renderer to avoid bloat.

## Future Roadmap

| Area | Plan |
|------|------|
| Formatting Blueprint | Shift from free-form text to structured AST -> constrained markdown/HTML -> PDF/DocX pipeline with deterministic layout tokens. |
| Metadata Ingestion | Normalize multi-source domain info; produce stable JSON blocks injected as context segments. |
| Structural Similarity | Hash + vector compare rendered prompt segments for drift detection & auto-retries. |
| Extended Redaction | Add PII taxonomy, deterministic entity tags, reversible (internal) anonymization map. |
| Template Governance | Admin UI: diff view between versions, promote/canary workflows, checksum verification. |
| Replay & Debug | Endpoint to reconstruct exact historical prompt (using stored version + variables + redaction rules snapshot). |

## Example

```python
rp = render_role_prompt(
   role="planner",
   variables={"grant_url": "https://grant.example", "text_spec": "Short summary"},
)
print(rp.redacted)
# Persist via AIJobContext(... rendered_prompt_redacted=rp.redacted ...)
```

## Best Practices Checklist

- [ ] New template version added instead of mutating existing
- [ ] Variables set updated & tests adjusted
- [ ] Redaction still preserves semantic intent
- [ ] Context snapshot stored before model call
- [ ] Fallback path not relied on in production (monitor occurrences)

## Monitoring Ideas

- Count fallback prompt usages (should trend toward zero)
- Alert if variable contract failure spikes
- Track average rendered prompt length per role & flag outliers

---
Questions / extensions: open an issue referencing this doc section headings.
