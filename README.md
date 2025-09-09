[[AI_CONFIG]]
FILE_TYPE: 'MARKETING_README'
INTENDED_READER: 'NON_TECHNICAL_PUBLIC'
PURPOSE: ['Provide an overview of the application', 'Highlight key features and technologies', 'Guide users to relevant documentation', 'Facilitate understanding for non-technical stakeholders']
PRIORITY: 'HIGH'
[[/AI_CONFIG]]

<!-- User-facing product README -->

# ForGranted (codename: Granterstellar)

AI-assisted grant proposal writing for organizations that can't afford a full-time grant writer.

Live Dev: <https://grants.intelfy.dk>
Planned Production: <https://forgranted.io>

---

## 1. Problem

Small nonprofits, research teams, and early-stage founders lose funding opportunities because:

1. Grant calls are long, jargon-heavy, and change structure across funders.
2. Teams lack an internal playbook of past winning language and templates.
3. Drafting + reformatting cycles consume scarce time; errors creep in under deadline.
4. Generic AI chat tools don't understand grant-specific structure, compliance, or reuse past context safely.

## 2. Our Solution

ForGranted turns a raw grant call (URL or text) plus your organization profile into a guided, section-by-section authoring workflow. The platform plans required sections, asks only the clarifying questions that matter, drafts each section with context, tracks revisions, and outputs a clean, funder-aligned proposal you can export (PDF / DOCX) deterministically.

## 3. How It Works (High-Level Flow)

1. Input the grant call URL (or paste requirements).
2. The planning agent researches + matches templates/samples (RAG) and builds a section blueprint.
3. For each section: we ask concise questions to fill real gaps (org metadata reused automatically).
4. The writing agent drafts; you review, revise, or request changes (diffs coming).
5. Approved sections lock their content (still revisable after unlock while revisions remaining); future memory snippets (usage_count scored) will boost context relevance.
6. Formatting agent assembles a final structured proposal (semantic markdown → PDF/DOCX).
7. Exports are deterministic: same inputs → same hash (integrity you can trust).

## 4. Key Features

### Core (Alpha)

- Guided Q&A planning (single-run; fallback universal template when retrieval empty)
- AI drafting & revision cycles per section (proposal already sectionized)
- Deterministic formatting & export (PDF/DOCX)
- Organizational usage quotas & plan-based limits (lifetime free + monthly paid)
- Stripe-powered subscriptions (seats, bundles, discounts)
- Secure file uploads (content-type, magic-byte & size checks)
- PII redaction layer in prompt assembly (hashed category tokens)
- (Planned) Memory snippet suggestions (usage_count scoring; not yet enforced in prompts)

### Coming Next (Short Horizon)

- Planner → Section materialization improvements (auto instantiate sections from blueprint)
- Enforce 5 revision cap per section (currently truncates to 50)
- Dynamic question generation engine (template + retrieval + web fallback)
- Provider fallback + circuit breaker
- Prompt injection shield
- Memory injection block (top K usage_count snippets)
- Metrics hashes (structure_hash, question_hash, fallback_mode flag)

### Later (Roadmap Highlights)

- RAG expansion: scheduled ingestion of public grant calls & sample libraries
- Retrieval caching + semantic reranking
- Streaming drafting (SSE)
- i18n & accessibility expansion

## 5. Why It’s Different

- Purpose-built workflow (not free-form chat)
- Deterministic exports & audit trail of prompts
- Strict separation of user answers vs engineered prompts (no raw prompt injection)
- Privacy-first redaction & memory scoping per user/org
- Security and compliance guardrails baked into architecture (RLS, CSP, rate limits)

## 6. Privacy & Security (Snapshot)

Layered controls to keep proposal data safe:

- Data Segregation: Postgres Row-Level Security (RLS) enforces per-user/org access.
- Secrets Hygiene: Distinct signing vs framework secrets; automated env doctor checks.
- Content Sandboxing: File type/MIME validation + optional virus scan hooks.
- Prompt Safety: Deterministic redaction of PII categories before logging; future injection shield.
- Network & Headers: Strict CSP, HSTS, referrer, and CORS controls (no wildcard in production).
- Rate Limits & Quotas: Per-plan AI request caps; daily/monthly token thresholds; 429 responses expose retry guidance.
- Backups: Automated media + database routines (retention window & restore drills documented).
- Export Integrity: Re-computable hash for deterministic outputs (detect silent tampering).

For extended details see: `docs/security_hardening.md`, `docs/ops_coolify_deployment_guide.md`.

## 7. Plans & Pricing (Preview)

- Free: Limited proposals & AI calls (fair trial of core flow)
- Pro: Higher monthly AI/token caps, priority formatting, collaboration basics
- Enterprise / Org Seats: Multi-seat allocation, advanced RAG ingestion cadence, extended retention

Pricing tiers finalize prior to public launch; billing is powered by Stripe for transparency and self-service management.

## 8. Getting Started (Early Access)

Request early access: (placeholder form / email)
While in private alpha, accounts are provisioned manually. OAuth (Google, GitHub, Facebook) is supported; local password auth is disabled for reduced attack surface.

## 9. Using the App (Alpha Walkthrough)

1. Sign in via OAuth & create or join your organization.
2. Start a proposal; paste the grant call URL.
3. Answer focused questions per section; reuse suggested memory chips.
4. Review draft; request revision if needed.
5. Approve all sections → generate formatted draft → export.
6. Upgrade if you approach quota caps (usage panel shows live consumption).

## 10. Data Handling & Privacy FAQ

Q: Do you train on my proposal text?
A: No. Your data is used only to serve your organization; RAG ingestion of user content is opt-in and scoped.

Q: Can staff access my drafts?
A: Only for explicit support cases with logged, auditable access (policy to be published).

Q: How are personal identifiers treated in prompts?
A: Redacted into stable hashed category tokens before logging or evaluation.

Q: Can I delete my account & data?
A: Yes—hard delete pipeline (with short grace) scheduled; exports can be downloaded first.

## 11. Roadmap (Selected Near-Term Items)

- Section workflow model & revision diff engine
- Injection shield & provider fallback
- Dynamic question generation
- Token/phase metrics & enhanced quota binding
- RAG ingestion scheduling & retrieval caching

Full engineering backlog lives in `Todo.md` (developer oriented).

## 12. Responsible AI Principles

- User answers are never silently rephrased without audit context.
- Prompts are versioned & checksummed; changes are traceable.
- Deterministic pathways favored where quality permits; randomness is controlled & documented.
- Fallback logic designed to fail safe (partial degradation instead of silent misuse).

## 13. Contributing

External contribution guidelines will open post-alpha. Until then, internal engineering standards: conventional commits, strict lint, deterministic tests, security-first reviews. See `CONTRIBUTING.md` (subject to revision pre-public).

## 14. Contact / Early Feedback

Questions, partnership, or early access request: [thomas@intelfy.dk](mailto:thomas@intelfy.dk)
Security disclosures: see `SECURITY.md` for coordinated disclosure instructions.

## 15. Legal & Compliance (Preview)

- Privacy Policy (draft) emphasizes minimal data retention & transparent user control.
- Data export & deletion endpoints shipping before public launch.
- Future: optional data processing addendum for enterprise clients.

## 16. Trademarks & Naming

"ForGranted" is the public-facing product name; "Granterstellar" may appear in code/internal docs during transition.

---

### At a Glance

| Aspect | Status |
| ------ | ------ |
| Core authoring workflow | Alpha (iterating) |
| Deterministic exports | Implemented |
| RLS data isolation | Implemented |
| AI memory & redaction | Redaction implemented; memory injection pending |
| Section diff engine | Implemented (structured block logging) |
| Dynamic Q generation | Pending |
| Provider fallback | Pending |
| Billing & quotas | Implemented |
| i18n | Planned |

---

This document is user-facing. Developer/deployment specifics live under `docs/`.
