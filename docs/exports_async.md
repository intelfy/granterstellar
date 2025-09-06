[[AI_CONFIG]]
FILE_TYPE: 'EXPORTS_RUNBOOK'
INTENDED_READER: 'AI_AGENT'
PURPOSE: ['Explain async export setup', 'Guide Celery worker configuration', 'Ensure reliable export processing']
PRIORITY: 'LOW'
[[/AI_CONFIG]]

# Async exports and Celery

This app supports exporting proposals to Markdown, PDF, and DOCX.
By default, exports are generated synchronously within the request.
You can enable asynchronous processing via Celery.

## Enable async mode

- Set environment variable `EXPORTS_ASYNC=1`.
- Provide a broker and result backend (Redis recommended):
  - `CELERY_BROKER_URL=redis://localhost:6379/0`
  - `CELERY_RESULT_BACKEND=redis://localhost:6379/1`
- Start a Celery worker alongside the Django API.

When enabled, POST `/api/exports` returns a job JSON with `status=pending`.
Poll GET `/api/exports/{id}` until `status=done` and `url` is present.

## Local quickstart (macOS)

- Install Redis (for example with Homebrew):
  - `brew install redis`
  - `brew services start redis`
- Ensure your Django environment variables are set, for example:
  - `EXPORTS_ASYNC=1`
  - `CELERY_BROKER_URL=redis://localhost:6379/0`
  - `CELERY_RESULT_BACKEND=redis://localhost:6379/1`
- Start the API server and a worker. In VS Code, you can use the task "API: celery worker".

## Celery worker command

In the `api/` directory:

- Start worker:
  - `celery -A app.celery:app worker -l info`
- Optional beat (if you add periodic tasks later):
  - `celery -A app.celery:app beat -l info`

## Notes

- If the broker/backends are missing or `EXPORTS_ASYNC` is not set, the API falls back to synchronous export generation automatically.
- The async pathway uses `exports.tasks.perform_export` to generate and persist the export artifact.
- Ensure media storage is reachable to serve export URLs.
