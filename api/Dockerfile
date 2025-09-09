FROM node:20-alpine AS web-build
WORKDIR /build
# Install deps; do not assume lockfile exists
COPY web/package.json ./web/
RUN cd web && npm install --no-audit --no-fund
COPY web ./web
RUN cd web && npm run build

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN adduser --disabled-password --gecos "" appuser
ARG STRIP_PY=0
COPY api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt && \
	pip cache purge || true
# Copy only API application code
COPY api /app
RUN if [ "$STRIP_PY" = "1" ]; then \
		python -c "import compileall,sys; sys.exit(0 if compileall.compile_dir('/app', maxlevels=10, force=True, quiet=1, optimize=2) else 1)" \
		&& find /app -type f -name '*.py' -print -delete; \
	fi
# Copy built SPA into staticfiles (served via WhiteNoise)
# Built assets land at /app/staticfiles/app
COPY --from=web-build /build/web/dist /app/staticfiles/app
# Copy landing assets into staticfiles root so / serves landing
# Minimal public assets only; docs, tests, markdown, maps excluded by .dockerignore for smaller context
COPY index.html styles.css hero.svg script.js /app/staticfiles/
COPY animations /app/staticfiles/animations
COPY vendor /app/staticfiles/vendor
COPY fonts /app/staticfiles/fonts
ENV PORT=8000
EXPOSE 8000
USER appuser
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD ["python","-c","import urllib.request,sys;sys.exit(0) if urllib.request.urlopen('http://localhost:8000/healthz').status==200 else sys.exit(1)"]
CMD ["gunicorn", "app.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
