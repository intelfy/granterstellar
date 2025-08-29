# Proposals API — Authoring and Autosave

This document describes the Proposals API used by the SPA. It covers scoping, quotas, and autosave.

## Scope and headers
- Personal scope (default): omit `X-Org-ID`. Queries operate on proposals where `org == null` and `author == current_user`.
- Org scope: send `X-Org-ID: <org_id>`. Queries operate on proposals with `org == <org_id>` (subject to RLS and membership).

## Endpoints
- List proposals
  - GET `/api/proposals/`
  - Scope determined by header as above
- Create proposal (quota-enforced)
  - POST `/api/proposals/`
  - Body: `{ "content": { ... }, "schema_version": "v1" }`
  - On quota exceed, returns `402` with JSON `{ error: "quota_exceeded", reason, limits, usage }` and header `X-Quota-Reason`.
- Retrieve
  - GET `/api/proposals/{id}/`
- Autosave (partial update)
  - PATCH `/api/proposals/{id}/`
  - Body (partial): `{ "content": { ... } }`
  - Updates the JSONB content and refreshes `last_edited` timestamp.
- Delete/archive
  - DELETE `/api/proposals/{id}/` (consider soft-archive by setting `state: archived` to free up active cap).

Implementation notes
- Serializer/ViewSet: see `api/proposals/serializers.py` and `api/proposals/views.py`.
- Quota service: `api/billing/quota.py`; usage: `GET /api/usage`.

## Quotas and usage
- Check current limits and usage with `GET /api/usage` (optional `X-Org-ID`).
- Free: `active_cap` proposals (defaults to 1) in personal or org scope.
- Pro/Enterprise: `monthly_cap` proposals created per calendar month (configurable via env).

## Notes
- Proposal content is stored as JSONB. Keep a `schema_version` field for forward compatibility.
- Prefer PATCH for frequent autosaves; send minimal deltas when possible.
- RLS is enforced at the DB level; always include the correct scope header so policies and quotas evaluate correctly.
