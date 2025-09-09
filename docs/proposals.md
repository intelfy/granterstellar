[[AI_CONFIG]]
FILE_TYPE: 'PROPOSALS_MANAGEMENT_OVERVIEW'
INTENDED_READER: 'AI_AGENT'
PURPOSE: ['Describe Proposals API usage', 'Explain scoping and quotas', 'Detail autosave functionality', 'Guide backend developers']
PRIORITY: 'MEDIUM'
[[/AI_CONFIG]]

# Proposals API — Section Authoring, Quotas & Autosave

This document describes the current proposals + sections API used by the SPA. It reflects the active `ProposalSection` data model (draft/approved separation, revision logs) and clarifies quota + upcoming revision cap enforcement.

## Scope and headers
New proposals are organization-scoped. If a user does not supply a valid `X-Org-ID` header or is not a member of the provided org, the backend automatically provisions (or reuses) a personal organization and assigns the proposal there. This replaces the legacy nullable `org` pattern. Creation without an actual org row no longer occurs.

- Preferred: send `X-Org-ID: <org_id>` for an org the user is a member of.
- Fallback: omit header (or provide an org where the user lacks membership) and the request will transparently use the user's personal org.
- Legacy personal proposals (pre-migration) were backfilled; they behave identically to newly provisioned personal org proposals now.

## Endpoints

- List proposals
  - GET `/api/proposals/`
  - Scope determined by header as above
- Create proposal (quota-enforced)
  - POST `/api/proposals/`
  - Body (current minimal): `{ "schema_version": "v1", "content": {} }` (legacy `content` field accepted but will be superseded by explicit section materialization; new flows should rely on subsequent planner → section creation endpoint once implemented).
  - On quota exceed, returns `402` with JSON `{ error: "quota_exceeded", reason, limits, usage }` and header `X-Quota-Reason`.
- Retrieve
  - GET `/api/proposals/{id}/`
- Autosave (legacy content path)
  - PATCH `/api/proposals/{id}/`
  - Body: partial updates to `content` still supported for legacy proposals created before section materialization migration.
  - New section-centric flow: section draft edits persist via section endpoints (planned incremental serializer pivot) and will not rely on bulk proposal `content` mutation beyond metadata.
- Delete/archive
  - DELETE `/api/proposals/{id}/` (consider soft-archive by setting `state: archived` to free up active cap).
- Section promotion (lifecycle)
  - POST `/api/sections/{id}/promote` — Copies `draft_content` → `approved_content` (and syncs legacy `content` field), sets `locked=true`, `state=approved`.
  - DELETE `/api/sections/{id}/promote` — Unlocks the section (`locked=false`) allowing additional write/revise operations (policy may tighten post‑alpha). State remains `approved` (idempotent) until future design dictates reversion semantics.
  - Emits AIMetric record with `type: "promote"`, `proposal_id`, `section_id` for observability.
  - Authorization: user must be the proposal author (legacy personal) or an org member in the proposal's organization (RLS + view check). Non-members receive 403 `{"error":"forbidden"}`.
  - Clients should ensure any pending draft edits are flushed to `draft_content` prior to promotion to avoid losing unsaved changes.

Implementation notes

- Serializer/ViewSet: `api/proposals/serializers.py` + `api/proposals/views.py`. The Proposal serializer now includes a lightweight `sections` array (`id,key,title,order,state`)—large draft/approved texts are not embedded.
- Section model: `ProposalSection` includes `draft_content`, `approved_content`, `locked`, `revisions[]` (JSON list capped to 50, plus a hard small cap default 5 for acceptance of new revisions).
- Revision logging: `ProposalSection.append_revision()` truncates diff blocks (≤25) and revision list (≤50) and enforces a hard configurable cap (`PROPOSAL_SECTION_REVISION_CAP`, default 5). When the cap is reached, synchronous and async revise operations now return **409** with `{ "error": "revision_cap_reached", "remaining_revision_slots": 0 }` and a failure AIMetric (`model_id: revision_cap_blocked`). The Proposal serializer exposes `remaining_revision_slots` per section so the UI can disable further edits preemptively.
- Quota service: `api/billing/quota.py`; usage: `GET /api/usage`.

## Quotas and usage

- Check current limits and usage with `GET /api/usage` (optional `X-Org-ID`).
- Free: lifetime single proposal (archiving does NOT restore ability to create another); enforced via total count + active cap check.
- Paid (Pro/Enterprise): monthly creation cap only; no active cap. Archiving does not affect ability to create new proposals within month allowance.
- Un-archiving checks only active cap (free tier) via `can_unarchive`; monthly counters unaffected.

## Notes

- Proposal legacy aggregate `content` JSONB remains for backward compatibility only; canonical per‑section text lives in `ProposalSection` rows (approved_content). Keep `schema_version` for forward compatibility.
- Prefer section-specific operations (write / revise / promote) for new proposals; use legacy PATCH only for pre-migration items.
- RLS is enforced at the DB level; always include the correct scope header so policies and quotas evaluate correctly.
- Formatting pass (`/api/ai/format`) operates over approved sections; export pipeline renders deterministic markdown → PDF/DOCX.

## Recently Shipped vs Upcoming

| Area | Status | Notes |
|------|--------|-------|
| Section materialization | Shipped | Planner (sync + async) creates/updates sections idempotently. Blueprint keys preserved; title/order updated only. |
| Immutable call_url | Shipped | `call_url` write-once; ignored on PATCH after initial set. |
| Personal org auto-provision | Shipped | Replaces nullable `org`; second proposal still subject to free cap. |
| Serializer sections field | Shipped | Lightweight listing for UI composition. |
| Revision cap enforcement | Shipped | Hard cap (default 5) with 409 responses once exhausted; metric logged (`revision_cap_blocked`). Serializer provides `remaining_revision_slots`. 409 payload: `{ "error": "revision_cap_reached", "remaining_revision_slots": 0, "revision_count": <int>, "revision_cap": <int> }` |
| Metrics structure/question hashes | Pending | Planned for planner output integrity tracking. |
| Quota middleware cleanup | Pending | Consolidate gating in permission layer only. |

See `backend_proposal_flow_audit.md` (if present) or roadmap documents for deeper architectural alignment.
