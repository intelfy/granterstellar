# Granterstellar — Stealth Landing

Minimal, mobile‑first landing page with a waitlist form — self‑hosted Mailgun proxy.

Note: For the full application (API + SPA + DB) with Coolify/Traefik deployment, see `docs/README-full-app.md` (skeleton; will replace this README when the stack is ready).
___________________________






Submit options
- Mailgun (default): form posts to `/api/waitlist` handled by `server.mjs` which calls Mailgun (double opt‑in).
- External endpoint (Formspree/etc.): set `data-endpoint` on the form to override.

Dev usage
- Node (Mailgun proxy):
	- copy `.env.example` to `.env` and set `MAILGUN_API_KEY`.
	- defaults:
		- MAILGUN_DOMAIN=mg.intelfy.dk
		- MAILGUN_LIST=granterstellar@mg.intelfy.dk
		- MAILGUN_API_HOST=api.mailgun.net (set to api.eu.mailgun.net for EU regions)
		- PUBLIC_BASE_URL=http://localhost:5173
	- run: `node server.mjs` then http://localhost:5173
- Docker:
	- `docker build -t granterstellar-landing .`
	- `docker run -e MAILGUN_DOMAIN=mg.intelfy.dk -e MAILGUN_API_KEY=key-xxxx -e MAILGUN_LIST=granterstellar@mg.intelfy.dk -p 5173:5173 granterstellar-landing`

Deploy
- Self-host: run the Docker image with Mailgun env vars.
- Compose: add this as a service in the main stack and route `/` to this service at your vanity domain.
	- Quick start here:
		- `cp .env.example .env && $EDITOR .env` # set MAILGUN_API_KEY and PUBLIC_BASE_URL
		- `docker compose up --build -d`
		- Health: GET http://localhost:5173/healthz returns `ok` when ready

Traefik (Coolify) notes
- Set PUBLIC_BASE_URL to your HTTPS domain (e.g., `https://landing.intelfy.dk`) so confirm links are correct.
- Coolify usually handles Traefik config via its UI. If you need labels in compose, an example:
	- `traefik.enable=true`
	- `traefik.http.routers.landing.rule=Host(`landing.intelfy.dk`)`
	- `traefik.http.routers.landing.entrypoints=websecure`
	- `traefik.http.routers.landing.tls=true`
	- `traefik.http.services.landing.loadbalancer.server.port=5173`
	- `traefik.http.services.landing.loadbalancer.healthcheck.path=/healthz`
	- `traefik.http.services.landing.loadbalancer.healthcheck.interval=10s`

Deploy on Coolify (DigitalOcean + Traefik)
1) Prerequisites
	- A domain/subdomain for the landing (e.g., `landing.intelfy.dk`).
	- DNS: Create an A record pointing `landing.intelfy.dk` → your droplet IP.
	- Mailgun: Domain `mg.intelfy.dk` verified with SPF/DKIM/DMARC; create a mailing list (e.g., `granterstellar@mg.intelfy.dk`); have your private API key.
	- Lottie: Add `landing/vendor/lottie.min.js` and your JSON animations in `landing/animations/` before deploying (keeps CSP strict and assets local).

2) Add repository to Coolify
	- Applications → New Application → Git Repository.
	- Connect your Git provider and select this repo.
	- Since this is a monorepo, configure build context/paths:
	  - Build Type: Dockerfile (recommended) OR Docker Compose (alternative).
	  - If Dockerfile:
		 - Dockerfile Path: `landing/Dockerfile`
		 - Build Context: project root (Coolify will send the whole repo; Dockerfile copies `landing/`).
	  - If Docker Compose:
		 - Compose Path: `landing/docker-compose.yml`

3) Service configuration
	- Internal port: 5173 (the server listens on 5173).
	- Healthcheck: GET `/healthz` should return `ok`.
	- Resources: default is fine (Node static + small proxy to Mailgun).

4) Environment variables (Secrets → Environment)
	- MAILGUN_DOMAIN: `mg.intelfy.dk`
	- MAILGUN_API_KEY: your Mailgun private API key
	- MAILGUN_API_HOST: `api.mailgun.net` or `api.eu.mailgun.net` depending on your Mailgun region
	- MAILGUN_LIST: `granterstellar@mg.intelfy.dk`
	- PUBLIC_BASE_URL: `https://landing.intelfy.dk` (or your chosen domain)

5) Domain & TLS (Traefik)
	- In the Coolify application → Domains → Add Domain: `landing.intelfy.dk`.
	- Enable HTTPS/Let’s Encrypt. Traefik will route traffic to the container on port 5173.

6) Deploy
	- Click Deploy. Wait for build logs to finish and healthcheck to pass.
	- Verify: open `https://landing.intelfy.dk/healthz` → `ok`.

7) Post‑deploy checks
	- Visit the landing root and try the waitlist form with a test email.
	- Confirm you receive a confirmation email; the link should point to `PUBLIC_BASE_URL` → `/confirm?...` and render the confirmation page.
	- Verify robots at `/robots.txt` disallows indexing (stealth mode).

8) Updating animations/content
	- Commit new animations into `landing/animations/` (matching the `data-animation` filenames in `index.html`).
	- If you replace lottie-web, update `landing/vendor/lottie.min.js`.
	- Redeploy from Coolify.

9) Rollbacks & redeploys
	- Coolify: select a previous deployment and roll back, or redeploy latest commit after edits.

10) Troubleshooting
	- 4xx on `/api/waitlist`: confirm MAILGUN_* envs are set and list exists.
	- No confirmation email: check Mailgun logs; ensure `PUBLIC_BASE_URL` is the HTTPS domain and DNS for `mg.intelfy.dk` is verified.
	- Animations not playing: ensure `vendor/lottie.min.js` and the referenced JSON files exist on disk post‑deploy.

Env vars
- MAILGUN_DOMAIN: your Mailgun domain (e.g., mg.intelfy.dk)
- MAILGUN_API_KEY: your Mailgun private API key
- MAILGUN_API_HOST: Mailgun API host; use `api.mailgun.net` (US) or `api.eu.mailgun.net` (EU)
- MAILGUN_LIST: Mailgun mailing list address (e.g., granterstellar@mg.intelfy.dk). Required for double opt‑in.
- PUBLIC_BASE_URL: base URL used to build confirmation links for double opt‑in.

Security & compliance
- Honeypot: hidden text field `hp`; bots get a 200 w/o adding.
- Rate limit: in‑memory, 10 requests / 5 minutes / IP.
- Double opt‑in: list member is created unsubscribed with a token; a confirmation email is sent with a link to `/confirm`; upon success, `subscribed=yes`.
- Security headers: HSTS, CSP (self only), Referrer-Policy, X-Content-Type-Options, X-Frame-Options, Permissions-Policy, COOP/CORP.
- robots: `robots.txt` disallows indexing (stealth mode).

Illustrations & Lottie
- Place a local copy of lottie-web (UMD) at `landing/vendor/lottie.min.js`.
- Put animation JSON files under `landing/animations/` and reference filenames via `data-animation` on `.lottie-slot` elements.
- The page lazily loads `vendor/lottie.min.js` and hydrates animations when the slot scrolls into view.
- CSP stays strict (self only) because assets are served locally; no external CDNs.

Notes
- JS uses fetch POST /api/waitlist with `{ email }` JSON.
- Basic client+server validation and friendly messages.
- Styles are custom, no framework, optimized for mobile first.
