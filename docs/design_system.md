# Design system (minimal policy; full DS TBD)

This replaces the older UI overhaul checklist. Use this as the single source of truth for UI rules until a full design system ships.

Current policy (do this now)

- Keep UI markup minimal and semantic. Avoid nonessential wrappers.
- Do not add inline styles. Do not add new global CSS. No utility frameworks yet.
- Error pages (`api/templates/400.html`, `403.html`, `404.html`, `500.html`) are plain HTML wireframes.
- SPA routes render unstyled markup suitable for debugging flows only.
- Front-end visual styling is deferred until the back-end is complete. When styling starts, use `docs/style-docs.md` as the source for stable selectors and recommended class names.
- Banners and errors: prefer role-based semantics (`role="status"`, `role="alert"`, `aria-live`) and consistent classes (e.g., `.banner`, `.banner--error`, `.error`) when we introduce styling.

What we’ll decide later

- Component library or custom component set (accessibility-first).
- Theming and tokens (color, spacing, type scale) with dark mode support.
- CSS strategy (e.g., CSS Modules, Tailwind, or vanilla-extract) and build tooling.
- Responsive grid/layout primitives and form controls.

Contribution rules (until DS is in place)

- Don’t introduce new styling dependencies or CSS files.
- Keep components functional and focused on behavior and data.
- Prefer semantic HTML elements and minimal attributes.
- If a view needs temporary clarity for debugging, add plain text or minimal structure only.
- Keep `docs/style-docs.md` up-to-date when adding new UI elements or test selectors (ids/classes/testids/aria). If you introduce any new classes for styling, document them there.

Decision log (to be filled in)

- [ ] Token system chosen
- [ ] CSS strategy selected
- [ ] Component primitives finalized
- [ ] Migration plan for existing views
