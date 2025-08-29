# Design system (minimal policy; full DS TBD)

This replaces the older UI overhaul checklist. Use this as the single source of truth for UI rules until a full design system ships.

Current policy (do this now)
- Keep UI markup minimal and semantic. Avoid nonessential wrappers.
- Do not add inline styles. Do not add new global CSS. No utility frameworks yet.
- Error pages (`api/templates/400.html`, `403.html`, `404.html`, `500.html`) are plain HTML wireframes.
- SPA routes render unstyled markup suitable for debugging flows only.

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

Decision log (to be filled in)
- [ ] Token system chosen
- [ ] CSS strategy selected
- [ ] Component primitives finalized
- [ ] Migration plan for existing views
