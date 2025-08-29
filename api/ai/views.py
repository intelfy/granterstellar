from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.conf import settings
from .sanitize import sanitize_text, sanitize_url, sanitize_answers, sanitize_file_refs
import time
from .models import AIJob
from .tasks import run_plan, run_write, run_revise, run_format
from .provider import get_provider
from django.db.models import QuerySet


@api_view(["POST"])
@permission_classes([AllowAny if settings.DEBUG else IsAuthenticated])
def plan(request):
    # Sanitize inputs to reduce prompt-injection vectors and invalid URLs
    grant_url = sanitize_url(request.data.get("grant_url"))
    text_spec = sanitize_text(request.data.get("text_spec"), max_len=4000)
    if getattr(settings, 'AI_ASYNC', False) and settings.CELERY_BROKER_URL:
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
        run_plan.delay(job.id)
        return Response({"job_id": job.id, "status": job.status})
    provider = get_provider(getattr(settings, 'AI_PROVIDER', None))
    t0 = time.time()
    plan = provider.plan(grant_url=grant_url or None, text_spec=text_spec or None)
    dt_ms = int((time.time() - t0) * 1000)
    from .models import AIMetric
    AIMetric.objects.create(
        type='plan', model_id='n/a', duration_ms=dt_ms, tokens_used=0,
        created_by=(getattr(request, 'user', None) if request.user.is_authenticated else None),
        org_id=request.META.get('HTTP_X_ORG_ID', ''), success=True,
    )
    return Response(plan)


@api_view(["POST"])
@permission_classes([AllowAny if settings.DEBUG else IsAuthenticated])
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
    if getattr(settings, 'AI_ASYNC', False) and settings.CELERY_BROKER_URL:
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
        run_write.delay(job.id)
        return Response({"job_id": job.id, "status": job.status})
    provider = get_provider(getattr(settings, 'AI_PROVIDER', None))
    t0 = time.time()
    res = provider.write(section_id=section_id, answers=answers, file_refs=file_refs or None)
    dt_ms = int((time.time() - t0) * 1000)
    from .models import AIMetric
    AIMetric.objects.create(
        type='write', model_id=res.model_id, duration_ms=dt_ms, tokens_used=res.usage_tokens,
        proposal_id=proposal_id, section_id=section_id,
        created_by=(getattr(request, 'user', None) if request.user.is_authenticated else None),
        org_id=request.META.get('HTTP_X_ORG_ID', ''), success=True,
    )
    return Response({"draft_text": res.text, "assets": [], "tokens_used": res.usage_tokens})


@api_view(["POST"])
@permission_classes([AllowAny if settings.DEBUG else IsAuthenticated])
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
    if getattr(settings, 'AI_ASYNC', False) and settings.CELERY_BROKER_URL:
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
        run_revise.delay(job.id)
        return Response({"job_id": job.id, "status": job.status})
    provider = get_provider(getattr(settings, 'AI_PROVIDER', None))
    t0 = time.time()
    res = provider.revise(base_text=base_text, change_request=change_request, file_refs=file_refs or None)
    dt_ms = int((time.time() - t0) * 1000)
    from .models import AIMetric
    AIMetric.objects.create(
        type='revise', model_id=res.model_id, duration_ms=dt_ms, tokens_used=res.usage_tokens,
        proposal_id=proposal_id, section_id=section_id,
        created_by=(getattr(request, 'user', None) if request.user.is_authenticated else None),
        org_id=request.META.get('HTTP_X_ORG_ID', ''), success=True,
    )
    return Response({"draft_text": res.text, "diff": "stub"})


@api_view(["POST"])
@permission_classes([AllowAny if settings.DEBUG else IsAuthenticated])
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
    if getattr(settings, 'AI_ASYNC', False) and settings.CELERY_BROKER_URL:
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
        run_format.delay(job.id)
        return Response({"job_id": job.id, "status": job.status})
    provider = get_provider(getattr(settings, 'AI_PROVIDER', None))
    t0 = time.time()
    res = provider.format_final(full_text=full_text, template_hint=template_hint or None, file_refs=file_refs or None)
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
@permission_classes([AllowAny if settings.DEBUG else IsAuthenticated])
def job_status(request, job_id: int):
    job = AIJob.objects.filter(id=job_id).first()
    if not job:
        return Response({"error": "not_found"}, status=404)
    return Response({
        "id": job.id,
        "type": job.type,
        "status": job.status,
        "result": job.result_json,
        "error": job.error_text or None,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    })


@api_view(["GET"])  # lightweight, DEBUG-only metrics peek
@permission_classes([AllowAny if settings.DEBUG else IsAuthenticated])
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
    qs = qs.order_by("-id").values(
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
@permission_classes([AllowAny if settings.DEBUG else IsAuthenticated])
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
