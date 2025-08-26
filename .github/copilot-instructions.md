# Granterstellar — AI Agent Instructions

Purpose: Equip AI coding agents to work effectively in this repo by summarizing architecture, conventions, and workflows that matter here.

## Big picture
- App: Granterstellar — guided grant-writing SaaS with export to .md/.docx/.pdf and a freemium model.
- Architecture: containerized monolith with a separated React SPA frontend and Django API backend, deployed via Coolify behind Traefik; PostgreSQL with JSONB for proposal content.
- Data model: Relational core (Users, Organizations, Grants, Proposals, Subscriptions) + JSONB column on Proposals for dynamic, sectioned content; RLS for tenant isolation and role-based org access.
- AI: Hybrid approach — paid LLM (e.g., GPT-5/Gemini) for complex multimodal generation; optional self-hosted lightweight model for simple tasks.
- Forms: SurveyJS on the client produces JSON consumed/stored by backend (no heavy transformation).

## Key flows (map to code you’ll write)
- Proposal authoring loop: client asks questions per section → POST to API (generate section) → AI drafts → user approves/requests changes → persist to JSONB.
- Save/resume: POST/GET /api/proposals persists/rehydrates SurveyJS state from JSONB.
- Exports: Generate .md/.docx/.pdf from the proposal JSON; keep formatting stable and idempotent.
- Payments: Stripe-based subscriptions; free = 1 proposal, premium = monthly quota, overage bundles; enterprise = custom.

## Backend (Django)
- Responsibilities: auth via OAuth/JWT, API endpoints, RLS session context, AI orchestration, file uploads (OCR where needed), export rendering.
- Conventions:
  - Treat proposal payloads as validated JSON that maps closely to SurveyJS schema; avoid denormalizing unless indexed.
  - Set current user/org/role into DB session for RLS policies on each request.
  - Keep AI prompts centrally defined with prompt-injection screening (Promptfoo/Rebuff or equivalent hook) before LLM calls.
  - Long-running AI tasks: prefer async job + status polling where outputs may exceed typical request latency.
- External services: Stripe, AI provider(s), optional Kroki/PlantUML/Mermaid renderer for diagrams.

## Frontend (React SPA)
- Mobile-first, stateful, multi-step form UX using SurveyJS.
- Rehydrate forms from backend JSON; keep a single source of truth in proposal JSON and derive UI state from it.
- For AI-generated sections, display diff against previous content and support approve/request-change actions.

## Data and security
- PostgreSQL with JSONB for proposal content; add GIN indexes for common JSON paths accessed by filtering/search.
- Enforce RLS: users see own proposals; org admins can see org-wide; explicit sharing supported.
- Secrets via environment variables; never commit keys.

## Exports
- Deterministic renderers from proposal JSON → markdown → docx/pdf. Prefer one canonical renderer (markdown) and convert downstream to avoid divergence.
- Keep assets (diagrams/images) addressable and embedded consistently across formats.

## Diagrams and multimodal
- AI may output diagram-as-code (Mermaid/PlantUML). Render via self-hosted Kroki service or a library; store generated images/URIs alongside section data.
- OCR pipeline for images/PDFs before feeding to LLM.

## Build, run, deploy
- Container-first. Use Docker Compose with services: web (React), api (Django), db (Postgres), optional backup (Duplicati), optional diagram renderer. In Coolify, Traefik is managed by the platform—no proxy container in compose.
- Typical lifecycle:
  1) docker compose up --build
  2) docker compose logs <service>
  3) docker compose down
- Self-hosted Linux target.

## Stripe usage
- Implement subscription lifecycle with proration; expose a customer portal link for self-serve management.
- Enforce proposal quotas in API layer; count against user/org monthly limits.

## What “good” looks like in this repo
- APIs: RESTful, auth-required, return validated JSON; wire RLS session context before DB work.
- Backcompat on proposal JSON: migrations avoid breaking old drafts; version proposal schema in metadata.
- Tests: focus on RLS policy coverage, quota enforcement, prompt shield behavior, and export determinism.

## Pointers to source docs in repo
- Product/vision: `claude.md`
- Architecture and detailed specs: `Granterstellar_ Technical Specification & Architec....md`

If something here conflicts with code you find, prefer the code and open a short note in this file with a follow-up TODO for reconciliation.
