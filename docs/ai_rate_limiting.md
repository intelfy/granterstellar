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

Primary modules:

- `api/ai/decorators.py` — houses `ai_protected`, a decorator that centralizes plan gating, single‑write debug guard, and rate limiting before delegating to the wrapped view.
- `api/ai/views.py` — endpoint bodies (plan / write / revise / format) and the `_rate_limit_check` helper plus metric creation.

Key helpers & flow (simplified):

1. Request enters decorated endpoint (`@ai_protected(endpoint_type="write")`).
2. Decorator performs (in order):
    - Auth / anonymous debug bypass (`DEBUG` or `AI_TEST_OPEN`).
    - Plan gating (reject Free tier outside bypass modes).
    - Single‑write debug guard (optional deterministic 429 path).
    - Rate limit fast path (cache bucket precheck) then authoritative DB count.
3. If allowed, control passes to original view which triggers provider logic (sync or async job) and records an `AIMetric` row.

Metric model: `AIMetric` stores `type`, `model_id`, `duration_ms`, `tokens_used`, `ok` boolean, linking to `created_by` for per‑user window counts.

### Decorator (`ai_protected`)

Motivations:

- Remove duplicated gating logic across four AI endpoints.
- Provide a *single edit point* for future enhancements (org‑pool limits, burst buckets, tracing).
- Ensure identical ordering of checks for consistent user experience and test determinism.

Behavior summary:

| Phase | Outcome on failure | Notes |
|-------|--------------------|-------|
| Plan Gate | 402 quota_exceeded | Skipped if DEBUG or `AI_TEST_OPEN=1` |
| Single‑Write Guard | 429 rate_limited | Only when deterministic debug enforcement enabled |
| Cache Fast Path | 429 rate_limited | Approximate early rejection; DB count still authoritative |
| DB Count | 429 rate_limited | Final authoritative limit check |

### Cache Fast Path (Bucket Precheck)

Inside `_rate_limit_check` a lightweight *approximate* limiter executes before hitting the database:

```python
uid = getattr(request.user, "id", None)
bucket_key = f"ai_rl:{endpoint_type}:{uid}:{int(now().timestamp() // 60)}"
count = cache.incr(bucket_key)  # key auto-created with value=1 if absent (backend dependent)
cache.expire(bucket_key, 120)   # keep key for at most 2 minutes (covers current + slight drift)
if count > limit: return early 429
```

Rationale:

- Reduces database reads under bursty load.
- Over-count risk (race increments) is acceptable because DB pass still executes on success path and may *not* yield 429 (so user may get one extra request through in pathological race conditions—tolerated for now).
- Keeps implementation trivial; can evolve into token bucket later.

Fallback behavior: If cache backend is unavailable, code silently skips fast path (database check still enforces limits).

### Deterministic Single‑Write Guard (via Decorator)

The guard now lives in the decorator, not inline in each endpoint. It still sets a per‑user cache key (`ai_dbg_single_write:<user_id>`) for 60 seconds under the same activation conditions, returning an immediate 429 on the *second* call. This guarantees stable test assertions without waiting for rolling 60‑second windows to elapse.

## Single-Write Guard (Deterministic Test Behavior)

See updated Decorator section. The semantics are unchanged; only the location moved for maintainability. Tests asserting a second 429 continue to rely on setting:

```bash
DEBUG=1
AI_ENFORCE_RATE_LIMIT_DEBUG=1
AI_RATE_PER_MIN_PRO=1
```

The guard remains intentionally simple and *does not* attempt sliding windows—its purpose is predictability, not production efficiency.

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
