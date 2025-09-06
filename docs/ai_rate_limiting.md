# AI Rate Limiting & Gating

This document describes how AI feature access is gated and rate limited.

## Goals

- Protect upstream model usage (cost control)
- Enforce plan-based access (Free vs. Pro vs. Enterprise)
- Provide deterministic behavior for tests (single‑write guard)
- Offer clear operational levers via environment variables

## Layers

| Layer | Purpose | Applies To | Env / Setting |
|-------|---------|-----------|---------------|
| Plan Gating | Block AI endpoints for Free tier (except when DEBUG / test bypass) | write / revise / format / plan* | Subscription tier via `billing.quota.get_subscription_for_scope` |
| Per‑Minute Rate Limit | Cap requests per user per endpoint type (tier dependent) | write / revise / format / plan | `AI_RATE_PER_MIN_FREE`, `AI_RATE_PER_MIN_PRO`, `AI_RATE_PER_MIN_ENTERPRISE` |
| Debug Single‑Write Guard | Deterministic test guard to ensure second write gets 429 when limit=1 | write (sync + async paths) | `AI_ENFORCE_RATE_LIMIT_DEBUG=1` with `AI_RATE_PER_MIN_PRO=1` and `DEBUG=1` |
| Async Job Path | Offload long model calls to Celery if enabled | all endpoints | `AI_ASYNC=1` + valid `CELERY_BROKER_URL` |
| Anonymous/Test Bypass | Allow unauthenticated calls in local debug & explicit test mode | all endpoints | `DEBUG=1` or `AI_TEST_OPEN=1` |

*`plan` endpoint is informational and may later receive plan-based gating if cost increases.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_ASYNC` | unset / falsy | Enable Celery job creation for AI endpoints. Requires broker/backend envs. |
| `AI_RATE_PER_MIN_FREE` | 0 | Free tier RPM (0 = effectively blocked by gating). |
| `AI_RATE_PER_MIN_PRO` | 20 | Pro tier RPM. Set to 1 in tests to exercise limiter. |
| `AI_RATE_PER_MIN_ENTERPRISE` | 60 | Enterprise tier RPM. |
| `AI_ENFORCE_RATE_LIMIT_DEBUG` | 0 | When `1`, enforces rate limiting logic even with `DEBUG=1`. |
| `AI_TEST_OPEN` | 0 | Allow anonymous access to AI endpoints for integration testing. |
| `AI_PROVIDER` | (runtime default) | Select provider implementation (`gpt5+gemini` composite at present). |


## Implementation Overview

File: `api/ai/views.py`

Key helpers:

- `_rate_limit_check(request, endpoint_type)` — per-minute, tier-derived cap using recent `AIMetric` rows.
- Inline single-write guard inside `write` — uses Django cache to mark first write per user for 60s when debug guard active.

Metric recording model: `AIMetric` captures `type`, `model_id`, `duration_ms`, `tokens_used`, and success status for observability.

## Single-Write Guard (Deterministic Test Behavior)

Purpose: Provide a stable, reproducible way to assert rate limiting in tests without timing flakiness.

Activation Conditions:

```text
DEBUG=1 AND AI_ENFORCE_RATE_LIMIT_DEBUG=1 AND AI_RATE_PER_MIN_PRO=1
```
Behavior:

1. First `/api/ai/write` for a user sets cache key `ai_dbg_single_write:<user_id>` for 60 seconds.
2. Second call within TTL returns `429 {"error": "rate_limited", "retry_after": 60}`.

This guard is independent of the general per-minute metric counting so that tests don't depend on synchronous metric persistence ordering.

## Per-Minute Limiter

Counting logic (simplified):

```python
recent = AIMetric.objects.filter(
    created_by=user,
    type=endpoint_type,
    created_at__gte=now - 60s,
).count()
if recent >= limit: 429
```
Headers set when allowed:

- `Retry-After` (only on 429)
- `X-Rate-Limit-Limit`
- `X-Rate-Limit-Remaining` (internal meta; can be surfaced later)

## Plan Gating

- Evaluated (outside DEBUG / test-open) for each AI endpoint (write/revise/format).
- Free tier requests receive `402 {"error":"quota_exceeded","reason":"ai_requires_pro"}`.

## Async Jobs

When `AI_ASYNC` is true (and Celery broker configured):

- Endpoint creates an `AIJob` row with `input_json` payload.
- Celery task (`run_write`, `run_revise`, etc.) processes job; job status queryable at `/api/ai/job/<id>`.
- Single-write guard still applies before job creation.

## Observability & Metrics

- Recent metrics endpoint: `GET /api/ai/metrics/recent` (DEBUG permission model allows anon in local dev).
- Summary endpoint: `GET /api/ai/metrics/summary` provides basic aggregates.

## Operational Playbook

Symptoms & Actions:

| Symptom | Likely Cause | Action |
|---------|--------------|--------|
| Unexpected 429 on first write (DEBUG) | Stale cache key from earlier test | Flush Django cache (e.g. restart dev server) or wait TTL. |
| No 429 on second write in tests | Missing `AI_ENFORCE_RATE_LIMIT_DEBUG=1` or `AI_RATE_PER_MIN_PRO` > 1 | Adjust test settings/env. |
| Async job never completes | Celery worker not running / broker unreachable | Start worker (`API: celery worker` task) and verify `CELERY_BROKER_URL`. |
| Free plan returns 402 despite debug expectation | Missing `DEBUG=1` or `AI_TEST_OPEN=1` | Set one of them during local testing. |

## Future Enhancements

- Surface `X-Rate-Limit-Remaining` in successful responses.
- Org-scope rate budgeting (shared pool).
- Burst + token bucket algorithm for smoother traffic.
- Admin override header (audited) for emergency writes.

Maintain this doc when modifying `api/ai/views.py` or rate-limiting behavior.
