# UI Selectors Reference (style-docs)

Purpose: Give front-end engineers stable selectors (ids/classes/testids/aria) to target for styling and tests. Prefer adding classes sparingly; use data-testid for tests only. Avoid inline styles in production stylesheets.

Notes

- SPA mount: `#root` inside `web/index.html` and dist.
- Router base: `/app`; asset base: `/static/app/`.
- Current SPA code has minimal classes; target elements via semantic structure and add classes as needed.

Scope and status

- Front-end visual styling is intentionally deferred until the back-end is complete. This document exists to make the eventual styling pass efficient and precise by cataloging stable selectors and recommending low-risk class names to introduce.
- Section root: ``<section>`` with ``<h2>Billing</h2>``
- Usage summary line contains: "Tier:", "Status:", optional "Cancel at period end", "Period ends", "Seats".
- Promo banner: ``span[data-testid="promo-banner"][aria-label="active-promo"]`` — displays "Promo: {formatted}" when a discount is active.
- Inputs:
  - Price ID: label "Price ID (optional):" + adjacent input
  - Seats: label "Seats (quantity):" + ``<input type="number">``
- Buttons:
  - Upgrade (Checkout): button text "Upgrade (Checkout)"
  - Open Billing Portal: button text "Open Billing Portal"
- Account: profile form inputs carry data-testids pf-username, pf-email, pf-first, pf-last and a pf-save button; a pf-ok element appears on successful save.
Proposals

- Section root: ``<section>`` with ``<h2>My Proposals</h2>``
- Usage strip: similar to Billing, includes discount banner when present
  - Promo banner selector reused: ``span[data-testid="promo-banner"][aria-label="active-promo"]``
- Controls row:
  - Org selector: ``input[placeholder="Org ID (optional)"]``
  - New: ``<button>New</button>``
  - Upgrade CTA: ``<button>Upgrade</button>`` (renders when blocked by quota)
  - Billing Portal: ``<button>Billing Portal</button>``
  - Cancel/Resume: text as above
- Proposals list: ``<ul>`` of ``<li>``
  - Each item: contains ``<strong>#{id}</strong>``, title text, state text
  - Export format ``<select>`` with values: pdf|docx|md
  - Export button: ``<button>Export</button>``, optional ``<span>Exporting…</span>``
  - Author toggle: ``<button>Open Author|Close Author</button>``
  - Archive/Unarchive buttons

Authoring (AuthorPanel)

- Section header: "Section {i}/{n}: {title}"; schema line includes "Schema:" and optional "Last saved"
- Inputs list: for each input key, ``<label>{key}</label>`` + ``<textarea>``
  - Internal note: ``<textarea data-testid="note-text">`` persists to proposal meta for collaborators
- File attach:
  - Label: ``<label for="file-{sectionId|section}">Attach files…</label>``
  - File input id: `#file-{sectionId|section}`
  - Upload state: inline "Uploading…" and error div
  - Files list: ``<ul>`` with file link and optional OCR preview textarea
- Draft actions:
  - Write: ``<button>Write</button>``
  - Change request: ``<input placeholder="Change request (optional)">``
  - Revise: ``<button>Revise</button>``
  - Approve & Save: ``<button>Approve & Save</button>``
- Diff panel (SectionDiff): two ``<pre>`` blocks under "Previous" and "Draft"
- Final formatting (when all approved):
  - "Final formatting" label
  - Template hint: ``<input placeholder="Template hint (optional)">``
  - Run Final Formatting: ``<button>Run Final Formatting</button>``
  - Formatted preview: ``<textarea readOnly>``

Organizations

- Section: ``<h2>Organizations</h2>``
- Create row: inputs "New org name", "Description (optional)", ``<button>Create</button>``
- Org list: ``<ul>`` with ``<li>`` per org
  - Primary line: ``<strong>#{id}</strong> {name} {description}`` admin: `{username}`
  - Buttons: Use, Manage/Hide, Delete
  - When managing:
    - Members: heading "Members"; invite controls with email input, role ``<select>`` (member|admin), ``<button>Invite</button>``
    - Member rows: username (id) — role, ``<button>Remove</button>``
    - Pending invites: list with revoke ``<button>`` and token span (dev)
    - Transfer ownership: input "New admin user ID", ``<button>Transfer</button>``
- Accept invite (dev helper): ``<button>Accept invite (paste token)</button>``

Auth & Registration

- Login page:
  - Dev-only credentials form: username/password inputs; ``<button>Login</button>``
  - OAuth buttons: ``<button>Sign in with Google|GitHub|Facebook</button>``
  - Debug Google login form: ``input[placeholder="debug: you@example.com"]``, ``<button>Debug Google Login</button>``
  - Error container: inline div with message
  - Create account (dev): ``<button>Create an account</button>``
  - Accept pending invite: ``<button>Accept pending invite</button>``
- OAuth callback: ``<div>Signing you in…</div>``
- Register page:
  - Inputs: name, organization name, invite token
  - Plan radios: ``input[type=radio][name=plan][value=free|pro|enterprise]``
  - Submit: ``<button>Continue</button>``

App Shell

- UI Experiments banner (when enabled): text "UI Experiments enabled…"
- Header: ``<h1>Granterstellar</h1>``
- Buttons: ``<button>Logout</button>``, ``<button>Billing</button>``
- Org tip: "Tip: Select an organization…" + ``<select>`` with org options + buttons
- Global invite banner: container ``div[data-testid="invite-banner"][aria-label="org-invite"]`` with accept/dismiss buttons

Errors & Misc

- NotFound page: ``<h1>404 — Page not found</h1>``; links to app and homepage
- Loading states: "Loading…" text in RequireOrg and Proposals

Static pages (landing)

- `index.html`, `privacy.html`, `confirmed.html` share classes:
  - `.container`, `.nav`, `.logo`, `.logo-pill[aria-label="Granterstellar"]`, `.brand`, `.caret`, `.cta`, `.pad`, `.section`, `.copy`, `.sub`, `.foot`
- Footer year: `#year` in `privacy.html`

Django error templates (api/templates)

- Files: `400.html`, `403.html`, `404.html`, `500.html` (plain HTML; no IDs/classes specified in repo snippet)

Testing hooks

- Promo banner: ``[data-testid="promo-banner"][aria-label="active-promo"]``
- Auth/Org guards: ``[data-testid="login"]``, ``[data-testid="register"]``, ``[data-testid="ok"]`` (test components)

Invite acceptance banner (new)

- Container: ``[data-testid="invite-banner"]``
- Accept button: ``[data-testid="invite-accept"]``
- Dismiss button: ``[data-testid="invite-dismiss"]``

Banners, errors, and dynamic content

- Status/usage banners
  - Billing and Proposals surfaces a compact usage line (Tier/Status/Seats/Period). Target the container ``section > div:first-of-type`` or introduce a future class like `.usage-strip` (recommended).
  - Active promotion badge: ``span[data-testid="promo-banner"][aria-label="active-promo"]`` renders text like "Promo: 20% off (once)".
- Error messages
  - Login errors: inline error container appears below the form (no class). For styling, select the container following the form or add a future class `.error` (recommended). Consider adding `role="alert"`.
  - Billing errors: an inline div shows error text (e.g., checkout/portal failures). Target the immediate sibling in the actions block or add `.error`.
  - Authoring file upload errors: an inline error div within the file attach area. Add `.error` for consistent styling when the styling pass begins.
- Dynamic content indicators
  - Loading: plain "Loading…" text in guards and views. Prefer adding `aria-busy="true"` on the container when styling and a `.loading` class if needed.
  - Exporting: ``<span>Exporting…</span>`` next to the Export button per item.
  - Uploading: inline "Uploading…" indicator in the file attach area.
  - OAuth callback: ``<div>Signing you in…</div>``.
- Accessibility hints (to adopt during styling)
  - For error containers, use `role="alert"` (assertive) or `aria-live="polite"` for non-blocking banners.
  - For success/info banners, consider `role="status"`.
- Future class conventions (recommended, not yet present)
  - `.banner`, `.banner--info`, `.banner--success`, `.banner--warning`, `.banner--error`
  - `.error` for inline error text near controls
  - `.usage-strip` for the Tier/Status row
  - `.loading` for containers with ongoing async work; optionally pair with `aria-busy="true"`
  - When you introduce any of these classes, add them to this doc.

Testing notes for banners/errors

- Prefer test IDs only for elements with ambiguous text (e.g., promo badge): ``data-testid="promo-banner"``.
- For errors and banners, prefer role-based queries if `role`/`aria-live` is added later; otherwise, query by text scoped to the relevant section/container to avoid ambiguity.

Recommendations (non-binding)

- For consistent styling, consider adding:
  - `.app-header`, `.app-actions`, `.usage-strip`
  - `.billing-form` and `.billing-actions`
  - `.proposals-list`, `.proposal-item`, `.proposal-actions`
  - `.orgs-header`, `.orgs-list`, `.org-actions`, `.org-manage`
  - `.author-panel`, `.author-controls`, `.diff`, `.final-format`
- Keep data-testid for tests, not styling; prefer classes for CSS.
