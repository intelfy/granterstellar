from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.response import Response
from django.conf import settings
from .sanitize import sanitize_text, sanitize_url, sanitize_answers, sanitize_file_refs
import time
from .models import AIJob
from .section_materializer import materialize_sections
from .tasks import run_plan, run_write, run_revise, run_format
from .provider import get_provider
from django.db.models import QuerySet
from typing import Optional
from orgs.models import Organization
from billing.quota import get_subscription_for_scope
from django.utils import timezone
from .decorators import ai_protected
from django.db import models
from app.common.keys import t


class DebugOrAuthPermission(BasePermission):
    """Allow all when DEBUG is True; otherwise require authentication.

    This avoids import-time binding of settings.DEBUG in decorators so tests
    that override settings can influence permission evaluation.
    """

    def has_permission(self, request, view):  # type: ignore[override]
        # Allow anonymous in DEBUG or when test-open flag is enabled
        if settings.DEBUG or getattr(settings, 'AI_TEST_OPEN', False):
            return True
        return IsAuthenticated().has_permission(request, view)


def _compute_rate_limits(tier: str) -> int:
    """Return max requests per minute for the given tier.

    Defaults:
      - free: 0 (blocked by gating already)
      - pro: 20 rpm
      - enterprise: 60 rpm
    Overridable via settings: AI_RATE_PER_MIN_FREE/PRO/ENTERPRISE
    """
    tier_key = (tier or 'pro').lower()
    if tier_key == 'enterprise':
        return int(getattr(settings, 'AI_RATE_PER_MIN_ENTERPRISE', 60) or 60)
    if tier_key == 'free':
        return int(getattr(settings, 'AI_RATE_PER_MIN_FREE', 0) or 0)
    return int(getattr(settings, 'AI_RATE_PER_MIN_PRO', 20) or 20)


def _rate_limit_check(request, endpoint_type: str) -> Optional[Response]:
    """Enforce AI usage limits (rpm + daily requests + monthly tokens) by tier.

    Order:
      1. Skip if DEBUG and no explicit enforcement.
      2. Per-minute rate limit (existing behavior).
      3. Daily request cap (if configured).
      4. Monthly token cap (if configured) - evaluated on write/revise/format only.

    Returns Response(429) when any limit exceeded; else None.
    """
    # Allow explicit enforcement in DEBUG when AI_ENFORCE_RATE_LIMIT_DEBUG=1
    if settings.DEBUG and not getattr(settings, 'AI_ENFORCE_RATE_LIMIT_DEBUG', False):
        return None
    user = getattr(request, 'user', None)
    if not getattr(user, 'is_authenticated', False):
        return None  # gating handles unauthorized
    # Determine org scope for tier
    org: Optional[Organization] = None
    org_id = request.META.get('HTTP_X_ORG_ID', '')
    if org_id and str(org_id).isdigit():
        try:
            org = Organization.objects.filter(id=int(org_id)).first()
        except Exception:
            org = None
    tier, _status = get_subscription_for_scope(user, org)
    limit = _compute_rate_limits(tier)
    if limit <= 0:
        # No per-minute limit, still enforce daily/monthly caps below
        pass
    # Fast cache precheck (token bucket style approximate counter)
    if limit > 0:
        try:
            from django.core.cache import cache
            uid = getattr(user, 'id', None)
            if uid is not None:
                bucket_key = f"ai_rl:{endpoint_type}:{uid}:{int(time.time()//60)}"
                current = cache.get(bucket_key)
                if current is None:
                    cache.add(bucket_key, 0, 65)  # expire slightly over 60s window
                    current = 0
                if isinstance(current, int) and current >= limit:
                    resp = Response({"error": "rate_limited", "retry_after": 30}, status=429)
                    resp["Retry-After"] = "30"
                    resp["X-Rate-Limit-Limit"] = str(limit)
                    resp["X-Rate-Limit-Remaining"] = "0"
                    return resp
                # Increment optimistically (best-effort; ignore race conditions)
                try:
                    cache.incr(bucket_key)
                except Exception:
                    cache.set(bucket_key, int(current) + 1, 65)
        except Exception:
            pass  # fallback silently to DB metric counting
    # Count metrics in the last 60 seconds for this user and endpoint type
    from .models import AIMetric
    now = timezone.now()
    one_min_ago = now - timezone.timedelta(seconds=60)
    if limit > 0:
        recent = AIMetric.objects.filter(
            created_by=user,
            type=endpoint_type,
            created_at__gte=one_min_ago,
        ).count()
        if recent >= limit:
            retry_after = 30
            resp = Response({"error": "rate_limited", "retry_after": retry_after}, status=429)
            resp["Retry-After"] = str(retry_after)
            resp["X-Rate-Limit-Limit"] = str(limit)
            resp["X-Rate-Limit-Remaining"] = "0"
            return resp
        # Attach remaining header for observability
        remaining = max(limit - recent - 1, 0)
        request.META["AI_RATE_LIMIT_REMAINING"] = remaining  # can be surfaced later if needed

    # --- Daily request cap ---
    # Settings: AI_DAILY_REQUEST_CAP_FREE/PRO/ENTERPRISE (None/0 => disabled)
    start_day = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tier_lower = tier.lower()
    daily_cap_setting = None
    if tier_lower == 'free':
        daily_cap_setting = getattr(settings, 'AI_DAILY_REQUEST_CAP_FREE', None)
    elif tier_lower == 'enterprise':
        daily_cap_setting = getattr(settings, 'AI_DAILY_REQUEST_CAP_ENTERPRISE', None)
    else:
        daily_cap_setting = getattr(settings, 'AI_DAILY_REQUEST_CAP_PRO', None)
    try:
        daily_cap = int(daily_cap_setting) if daily_cap_setting not in (None, '') else None
    except Exception:
        daily_cap = None
    if daily_cap and daily_cap > 0:
        day_count = AIMetric.objects.filter(created_by=user, created_at__gte=start_day).count()
        if day_count >= daily_cap:
            resp = Response({
                "error": "quota_exceeded",
                "reason": "ai_daily_request_cap",
                "retry_after": 3600,
            }, status=429)
            resp["X-AI-Daily-Cap"] = str(daily_cap)
            resp["X-AI-Daily-Used"] = str(day_count)
            return resp

    # --- Monthly token cap --- (write/revise/format only; planning negligible)
    if endpoint_type in ("write", "revise", "format"):
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_cap_setting = None
        if tier_lower == 'enterprise':
            monthly_cap_setting = getattr(settings, 'AI_MONTHLY_TOKENS_CAP_ENTERPRISE', None)
        else:  # pro & free (free already blocked elsewhere)
            monthly_cap_setting = getattr(settings, 'AI_MONTHLY_TOKENS_CAP_PRO', None)
        try:
            monthly_cap = int(monthly_cap_setting) if monthly_cap_setting not in (None, '') else None
        except Exception:
            monthly_cap = None
        if monthly_cap and monthly_cap > 0:
            token_sum = (
                AIMetric.objects.filter(created_by=user, created_at__gte=month_start)
                .aggregate(total=models.Sum('tokens_used'))  # type: ignore[name-defined]
                .get('total')
                or 0
            )
            if token_sum >= monthly_cap:
                resp = Response({
                    "error": "quota_exceeded",
                    "reason": "ai_monthly_tokens_cap",
                }, status=429)
                resp["X-AI-Monthly-Token-Cap"] = str(monthly_cap)
                resp["X-AI-Monthly-Token-Used"] = str(token_sum)
                return resp
    return None


@api_view(["POST"])
@permission_classes([DebugOrAuthPermission])
@ai_protected('plan', plan_gate=False)
def plan(request):
    # Sanitize inputs to reduce prompt-injection vectors and invalid URLs
    grant_url = sanitize_url(request.data.get("grant_url"))
    text_spec = sanitize_text(request.data.get("text_spec"), max_len=4000)
    async_enabled = getattr(settings, 'AI_ASYNC', False) and settings.CELERY_BROKER_URL
    if async_enabled:
        job = AIJob.objects.create(
            type='plan',
            input_json={
                "grant_url": grant_url or None,
                "text_spec": text_spec or None,
            },
            created_by=(
                getattr(request, 'user', None)
                if request.user.is_authenticated
                else None
            ),
            org_id=request.META.get('HTTP_X_ORG_ID', ''),
        )
        run_plan.delay(job.id)  # type: ignore[attr-defined]
        return Response({"job_id": job.id, "status": job.status})  # type: ignore[attr-defined]
    provider = get_provider(getattr(settings, 'AI_PROVIDER', None))
    t0 = time.time()
    plan_result = provider.plan(grant_url=grant_url or None, text_spec=text_spec or None)
    dt_ms = int((time.time() - t0) * 1000)
    from .models import AIMetric
    # Extract blueprint for materialization.
    # Planner contract: plan_result may be a dict containing 'sections' or 'blueprint' list,
    # or the planner could evolve to return a plain list directly.
    blueprint = []
    proposal_id_val = None
    if isinstance(plan_result, dict):
        if isinstance(plan_result.get("sections"), list):
            blueprint = plan_result.get("sections")  # type: ignore[assignment]
        elif isinstance(plan_result.get("blueprint"), list):
            blueprint = plan_result.get("blueprint")  # type: ignore[assignment]
        proposal_id_val = plan_result.get("proposal_id")
    created_sections: list[str] = []
    if proposal_id_val and blueprint:
        try:
            mat = materialize_sections(proposal_id=int(proposal_id_val), blueprint=blueprint)
            created_sections = [s.key for (s, c) in mat if c]
        except Exception as e:  # pragma: no cover
            created_sections = ["error:" + str(e)]
    AIMetric.objects.create(
        type='plan', model_id='planner.v1', duration_ms=dt_ms, tokens_used=0,
        created_by=(getattr(request, 'user', None) if request.user.is_authenticated else None),
        org_id=request.META.get('HTTP_X_ORG_ID', ''), success=True,
    )
    return Response({"plan": plan_result, "created_sections": created_sections})


@api_view(["POST"])
@permission_classes([DebugOrAuthPermission])
@ai_protected('write', plan_gate=True)
def write(request):
    section_id = sanitize_text(request.data.get("section_id"), max_len=128)
    proposal_id = None
    try:
        if request.data.get("proposal_id") is not None:
            proposal_id = int(request.data.get("proposal_id"))
    except Exception:
        proposal_id = None
    answers = sanitize_answers(request.data.get("answers", {}))
    file_refs = sanitize_file_refs(request.data.get("file_refs", []))
    async_enabled = getattr(settings, 'AI_ASYNC', False) and settings.CELERY_BROKER_URL
    if async_enabled:
        job = AIJob.objects.create(
            type='write',
            input_json={
                "proposal_id": proposal_id,
                "section_id": section_id,
                "answers": answers,
                "file_refs": file_refs,
            },
            created_by=(
                getattr(request, 'user', None)
                if request.user.is_authenticated
                else None
            ),
            org_id=request.META.get('HTTP_X_ORG_ID', ''),
        )
        # Ensure background path does not break test expecting second call limited (guard already set)
        try:  # pragma: no cover - safety
            run_write.delay(job.id)  # type: ignore[attr-defined]
        except Exception:
            # Fallback: run synchronously if Celery misconfigured in test
            provider = get_provider(getattr(settings, 'AI_PROVIDER', None))
            provider.write(section_id=section_id, answers=answers, file_refs=file_refs or None)
        return Response({"job_id": job.id, "status": job.status})  # type: ignore[attr-defined]
    provider = get_provider(getattr(settings, 'AI_PROVIDER', None))
    t0 = time.time()
    # Fetch memory suggestions (user or org scope) to enrich context (not persisted provider-side yet)
    # (Memory suggestions reserved hook: intentionally skipped until provider contract extended)
    # For now don't mutate answers type contract; future: provider may accept context param.
    # Enrich with memory suggestions (non-persisted prompt context) under reserved key
    try:
        from .models import AIMemory  # local import to avoid cycles
        org_scope = request.META.get('HTTP_X_ORG_ID', '')
        if request.user.is_authenticated:
            mem_items = AIMemory.suggestions(user=request.user, org_id=org_scope, section_id=section_id or None, limit=3)
            if mem_items:
                context_lines = [f"{m['key']}: {m['value'][:400]}" for m in mem_items]
                # Use reserved underscore key so it is ignored for memory recording (see record loop below)
                answers['_memory_context'] = "[context:memory]\n" + "\n".join(context_lines)
    except Exception:
        pass
    # Deterministic sampling: allow request override; default from settings
    deterministic_setting = getattr(settings, 'AI_DETERMINISTIC_SAMPLING', True)
    try:
        deterministic_default = bool(False if str(deterministic_setting) in ("0", "false", "False") else deterministic_setting)
    except Exception:
        deterministic_default = True
    deterministic_req = request.data.get('deterministic') if isinstance(request.data, dict) else None
    if deterministic_req is not None:
        try:
            deterministic = bool(False if str(deterministic_req) in ("0", "false", "False") else deterministic_req)
        except Exception:
            deterministic = deterministic_default
    else:
        deterministic = deterministic_default
    res = provider.write(section_id=section_id, answers=answers, file_refs=file_refs or None, deterministic=deterministic)  # type: ignore[arg-type]
    # (single-write marker already set at entry)
    dt_ms = int((time.time() - t0) * 1000)
    from .models import AIMetric
    # Persist answer memory (best-effort; ignore failures)
    try:  # pragma: no cover - side effect; minimal tests may stub
        from .models import AIMemory
        org_scope = request.META.get('HTTP_X_ORG_ID', '')
        if request.user.is_authenticated:
            for k, v in answers.items():
                if not k.startswith('_') and v:
                    AIMemory.record(user=request.user, org_id=org_scope, section_id=section_id or '', key=k, value=str(v)[:2000])
    except Exception:
        pass
    AIMetric.objects.create(
        type='write', model_id=res.model_id, duration_ms=dt_ms, tokens_used=res.usage_tokens,
        proposal_id=proposal_id, section_id=section_id,
        created_by=(getattr(request, 'user', None) if request.user.is_authenticated else None),
        org_id=request.META.get('HTTP_X_ORG_ID', ''), success=True,
    )
    return Response({"draft_text": res.text, "assets": [], "tokens_used": res.usage_tokens})


@api_view(["POST"])
@permission_classes([DebugOrAuthPermission])
@ai_protected('revise', plan_gate=True)
def revise(request):
    change_request = sanitize_text(request.data.get("change_request", ""), max_len=4000)
    base_text = sanitize_text(request.data.get("base_text", ""), max_len=20000, neutralize_injection=False)
    section_id = sanitize_text(request.data.get("section_id"), max_len=128)
    proposal_id = None
    try:
        if request.data.get("proposal_id") is not None:
            proposal_id = int(request.data.get("proposal_id"))
    except Exception:
        proposal_id = None
    file_refs = sanitize_file_refs(request.data.get("file_refs", []))
    async_enabled = getattr(settings, 'AI_ASYNC', False) and settings.CELERY_BROKER_URL
    if async_enabled:
        job = AIJob.objects.create(
            type='revise',
            input_json={
                "proposal_id": proposal_id,
                "section_id": section_id,
                "base_text": base_text,
                "change_request": change_request,
                "file_refs": file_refs,
            },
            created_by=(
                getattr(request, 'user', None)
                if request.user.is_authenticated
                else None
            ),
            org_id=request.META.get('HTTP_X_ORG_ID', ''),
        )
        run_revise.delay(job.id)  # type: ignore[attr-defined]
        return Response({"job_id": job.id, "status": job.status})  # type: ignore[attr-defined]
    provider = get_provider(getattr(settings, 'AI_PROVIDER', None))
    # --- Revision cap pre-check (sync path only; async handled in task) ---
    if section_id:
        try:
            from proposals.models import ProposalSection as _PS  # local import
            sec_obj = _PS.objects.filter(id=section_id).only('id', 'revisions').first()
            if sec_obj is not None:
                cap_raw = getattr(settings, 'PROPOSAL_SECTION_REVISION_CAP', 5)
                try:
                    cap_val = int(cap_raw) if cap_raw not in (None, '') else 5
                except Exception:
                    cap_val = 5
                if cap_val <= 0:
                    cap_val = 5
                current_count = len(sec_obj.revisions or [])
                if current_count >= cap_val:
                    from .models import AIMetric
                    try:  # metric (failure)
                        AIMetric.objects.create(
                            type='revise', model_id='revision_cap_blocked', duration_ms=0, tokens_used=0,
                            success=False, created_by=(request.user if request.user.is_authenticated else None),
                            org_id=request.META.get('HTTP_X_ORG_ID', ''), section_id=section_id,
                            error_text='revision_cap_reached',
                        )
                    except Exception:
                        pass
                    return Response({
                        "error": "revision_cap_reached",
                        "message": t("errors.revision.cap_reached", count=current_count, limit=cap_val),
                        "remaining_revision_slots": 0,
                    }, status=409)
        except Exception:
            pass  # fall through on errors
    t0 = time.time()
    # (Memory suggestions reserved hook: intentionally skipped until provider contract extended)
    # Include memory context as additional signal appended to change_request (non-persistent)
    try:
        from .models import AIMemory
        org_scope = request.META.get('HTTP_X_ORG_ID', '')
        if request.user.is_authenticated:
            mem_items = AIMemory.suggestions(user=request.user, org_id=org_scope, section_id=section_id or None, limit=3)
            if mem_items:
                ctx = "\n".join(f"{m['key']}: {m['value'][:400]}" for m in mem_items)
                addition = "\n\n[context:memory]\n" + ctx if change_request else "[context:memory]\n" + ctx
                change_request = change_request + addition
    except Exception:
        pass
    deterministic_setting = getattr(settings, 'AI_DETERMINISTIC_SAMPLING', True)
    try:
        deterministic_default = bool(False if str(deterministic_setting) in ("0", "false", "False") else deterministic_setting)
    except Exception:
        deterministic_default = True
    deterministic_req = request.data.get('deterministic') if isinstance(request.data, dict) else None
    if deterministic_req is not None:
        try:
            deterministic = bool(False if str(deterministic_req) in ("0", "false", "False") else deterministic_req)
        except Exception:
            deterministic = deterministic_default
    else:
        deterministic = deterministic_default
    res = provider.revise(
        base_text=base_text,
        change_request=change_request,
        file_refs=file_refs or None,
        deterministic=deterministic,
    )  # type: ignore[arg-type]
    dt_ms = int((time.time() - t0) * 1000)
    from .models import AIMetric
    # Record change_request as memory snippet (tagged by section)
    try:  # pragma: no cover
        from .models import AIMemory
        org_scope = request.META.get('HTTP_X_ORG_ID', '')
        if request.user.is_authenticated and change_request:
            AIMemory.record(
                user=request.user,
                org_id=org_scope,
                section_id=section_id or '',
                key='change_request',
                value=change_request[:2000],
            )
    except Exception:
        pass
    AIMetric.objects.create(
        type='revise', model_id=res.model_id, duration_ms=dt_ms, tokens_used=res.usage_tokens,
        proposal_id=proposal_id, section_id=section_id,
        created_by=(getattr(request, 'user', None) if request.user.is_authenticated else None),
        org_id=request.META.get('HTTP_X_ORG_ID', ''), success=True,
    )
    return Response({"draft_text": res.text, "diff": "stub"})


@api_view(["POST"])
@permission_classes([DebugOrAuthPermission])
@ai_protected('format', plan_gate=True)
def format(request):
    # Final formatting across the whole composed text; optional template hint
    full_text = sanitize_text(request.data.get("full_text", ""), max_len=200000, neutralize_injection=False)
    template_hint = sanitize_text(request.data.get("template_hint", None), max_len=256) if request.data else None
    proposal_id = None
    try:
        if request.data.get("proposal_id") is not None:
            proposal_id = int(request.data.get("proposal_id"))
    except Exception:
        proposal_id = None
    file_refs = sanitize_file_refs(request.data.get("file_refs", []))
    async_enabled = getattr(settings, 'AI_ASYNC', False) and settings.CELERY_BROKER_URL
    if async_enabled:
        job = AIJob.objects.create(
            type='format',
            input_json={
                "proposal_id": proposal_id,
                "full_text": full_text,
                "template_hint": template_hint or None,
                "file_refs": file_refs,
            },
            created_by=(
                getattr(request, 'user', None)
                if request.user.is_authenticated
                else None
            ),
            org_id=request.META.get('HTTP_X_ORG_ID', ''),
        )
        run_format.delay(job.id)  # type: ignore[attr-defined]
        return Response({"job_id": job.id, "status": job.status})  # type: ignore[attr-defined]
    provider = get_provider(getattr(settings, 'AI_PROVIDER', None))
    t0 = time.time()
    # Deterministic sampling toggle (default on for stable exports)
    deterministic_setting = getattr(settings, 'AI_DETERMINISTIC_SAMPLING', True)
    try:
        deterministic_default = bool(False if str(deterministic_setting) in ("0", "false", "False") else deterministic_setting)
    except Exception:
        deterministic_default = True
    deterministic_req = request.data.get('deterministic') if isinstance(request.data, dict) else None
    if deterministic_req is not None:
        try:
            deterministic = bool(False if str(deterministic_req) in ("0", "false", "False") else deterministic_req)
        except Exception:
            deterministic = deterministic_default
    else:
        deterministic = deterministic_default
    res = provider.format_final(
        full_text=full_text,
        template_hint=template_hint or None,
        file_refs=file_refs or None,
        deterministic=deterministic,
    )
    dt_ms = int((time.time() - t0) * 1000)
    from .models import AIMetric
    AIMetric.objects.create(
        type='format', model_id=res.model_id, duration_ms=dt_ms, tokens_used=res.usage_tokens,
        proposal_id=proposal_id,
        created_by=(getattr(request, 'user', None) if request.user.is_authenticated else None),
        org_id=request.META.get('HTTP_X_ORG_ID', ''), success=True,
    )
    return Response({"formatted_text": res.text})


@api_view(["GET"])
@permission_classes([DebugOrAuthPermission])
def job_status(request, job_id: int):
    job = AIJob.objects.filter(id=job_id).first()
    if not job:
        return Response({"error": "not_found"}, status=404)
    return Response({
    "id": job.id,  # type: ignore[attr-defined]
        "type": job.type,
        "status": job.status,
        "result": job.result_json,
        "error": job.error_text or None,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    })


@api_view(["GET"])  # lightweight, DEBUG-only metrics peek
@permission_classes([DebugOrAuthPermission])
def metrics_recent(request):
    """Return the most recent AIMetrics for the caller's org (DEBUG allows anon).

    Query params:
      - limit: max rows (default 20, cap 100)
    """
    try:
        limit = int(request.GET.get("limit", "20"))
    except Exception:
        limit = 20
    if limit <= 0:
        limit = 20
    if limit > 100:
        limit = 100
    org_id = request.META.get('HTTP_X_ORG_ID', '')
    from .models import AIMetric  # local import to avoid circular and linter duplicate
    qs: QuerySet = AIMetric.objects.all()
    if org_id:
        qs = qs.filter(org_id=org_id)
    qs = qs.order_by("-id").values(  # type: ignore[assignment]
        "id",
        "type",
        "model_id",
        "duration_ms",
        "tokens_used",
        "success",
        "org_id",
        "created_at",
    )[:limit]
    return Response({"items": list(qs)})


@api_view(["GET"])  # aggregate averages across scopes
@permission_classes([DebugOrAuthPermission])
def metrics_summary(request):
    """Averages for tokens/duration and edit metrics by scope (global/org/user)."""
    from .models import AIMetric  # local import
    from django.db.models import Sum, Count
    org_id = request.META.get('HTTP_X_ORG_ID', '')

    def agg(qs):
        totals = qs.aggregate(cnt=Count('id'), tok=Sum('tokens_used'), dur=Sum('duration_ms'))
        cnt = totals.get('cnt') or 0
        tok = totals.get('tok') or 0
        dur = totals.get('dur') or 0
        avg_tokens = (tok / cnt) if cnt else 0.0
        avg_ms = (dur / cnt) if cnt else 0.0

        edits = qs.filter(type='revise')
        e_totals = edits.aggregate(cnt=Count('id'), tok=Sum('tokens_used'))
        e_cnt = e_totals.get('cnt') or 0
        e_tok = e_totals.get('tok') or 0
        # per-user edit counts average
        per_user = (
            edits.exclude(created_by__isnull=True)
            .values('created_by')
            .annotate(c=Count('id'))
        )
        users = per_user.count()
        edits_per_user_avg = (sum(x['c'] for x in per_user) / users) if users else 0.0
        edit_tokens_avg = (e_tok / e_cnt) if e_cnt else 0.0
        return {
            'count': cnt,
            'avg_tokens': round(avg_tokens, 2),
            'avg_duration_ms': round(avg_ms, 2),
            'edits_per_user_avg': round(edits_per_user_avg, 2),
            'edit_tokens_avg': round(edit_tokens_avg, 2),
        }

    global_stats = agg(AIMetric.objects.all())
    empty = {
        'count': 0,
        'avg_tokens': 0.0,
        'avg_duration_ms': 0.0,
        'edits_per_user_avg': 0.0,
        'edit_tokens_avg': 0.0,
    }
    org_stats = agg(AIMetric.objects.filter(org_id=org_id)) if org_id else empty
    user_stats = empty
    if getattr(request, 'user', None) and request.user.is_authenticated:
        user_stats = agg(AIMetric.objects.filter(created_by=request.user))

    return Response({'global': global_stats, 'org': org_stats, 'user': user_stats})


@api_view(["GET"])
@permission_classes([DebugOrAuthPermission])
def memory_suggestions(request):
    """Return AI memory suggestions for the caller.

    Query params:
      - section_id: optional filter
      - limit: max items (default 5, cap 20)
    Scope: if X-Org-ID header present, return org-level items; else user-only.
    """
    from .models import AIMemory  # local import
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return Response({"items": []})
    section_id = request.GET.get('section_id') or None
    try:
        limit = int(request.GET.get('limit', '5'))
    except Exception:
        limit = 5
    org_id = request.META.get('HTTP_X_ORG_ID', '')
    suggestions = AIMemory.suggestions(user=request.user, org_id=org_id, section_id=section_id, limit=limit)
    return Response({"items": suggestions})
