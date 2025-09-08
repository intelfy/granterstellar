from celery import shared_task
from django.conf import settings
from .provider import get_provider
import time
from .models import AIJob, AIMetric


def _provider():
    return get_provider(getattr(settings, 'AI_PROVIDER', None))


@shared_task
def run_plan(job_id: int):
    job = AIJob.objects.get(id=job_id)
    job.status = 'processing'
    job.save(update_fields=['status'])
    try:
        prov = _provider()
        t0 = time.time()
        plan = prov.plan(
            grant_url=job.input_json.get('grant_url'),
            text_spec=job.input_json.get('text_spec'),
        )
        job.result_json = plan  # type: ignore[assignment]
        job.status = 'done'
        dt_ms = int((time.time() - t0) * 1000)
        try:
            AIMetric.objects.create(
                type='plan',
                model_id='n/a',
                duration_ms=dt_ms,
                tokens_used=0,
                success=True,
                created_by=job.created_by,
                org_id=job.org_id,
            )
        except Exception:
            pass
        job.save(update_fields=['result_json', 'status'])
    except Exception as e:  # noqa: BLE001
        job.status = 'error'
        job.error_text = str(e)
        try:
            AIMetric.objects.create(
                type='plan',
                model_id='n/a',
                duration_ms=0,
                tokens_used=0,
                success=False,
                error_text=job.error_text,
                created_by=job.created_by,
                org_id=job.org_id,
            )
        except Exception:
            pass
        job.save(update_fields=['status', 'error_text'])


@shared_task
def run_write(job_id: int):
    job = AIJob.objects.get(id=job_id)
    job.status = 'processing'
    job.save(update_fields=['status'])
    try:
        prov = _provider()
        t0 = time.time()
        det_setting = getattr(settings, 'AI_DETERMINISTIC_SAMPLING', True)
        try:
            det_default = bool(False if str(det_setting) in ("0", "false", "False") else det_setting)
        except Exception:
            det_default = True
        res = prov.write(
            section_id=job.input_json.get('section_id') or '',
            answers=job.input_json.get('answers') or {},
            file_refs=job.input_json.get('file_refs') or None,
            deterministic=det_default,
        )
        job.result_json = {  # type: ignore[assignment]
            "draft_text": res.text,
            "assets": [],
            "tokens_used": res.usage_tokens,
        }
        job.status = 'done'
        dt_ms = int((time.time() - t0) * 1000)
        try:
            AIMetric.objects.create(
                type='write',
                model_id=res.model_id,
                duration_ms=dt_ms,
                tokens_used=res.usage_tokens,
                success=True,
                created_by=job.created_by,
                org_id=job.org_id,
                proposal_id=job.input_json.get('proposal_id'),
                section_id=job.input_json.get('section_id') or '',
            )
        except Exception:
            pass
        job.save(update_fields=['result_json', 'status'])
    except Exception as e:  # noqa: BLE001
        job.status = 'error'
        job.error_text = str(e)
        try:
            AIMetric.objects.create(
                type='write',
                model_id='',
                duration_ms=0,
                tokens_used=0,
                success=False,
                error_text=job.error_text,
                created_by=job.created_by,
                org_id=job.org_id,
                proposal_id=job.input_json.get('proposal_id'),
                section_id=job.input_json.get('section_id') or '',
            )
        except Exception:
            pass
        job.save(update_fields=['status', 'error_text'])


@shared_task
def run_revise(job_id: int):
    job = AIJob.objects.get(id=job_id)
    job.status = 'processing'
    job.save(update_fields=['status'])
    try:
        prov = _provider()
        t0 = time.time()
        det_setting = getattr(settings, 'AI_DETERMINISTIC_SAMPLING', True)
        try:
            det_default = bool(False if str(det_setting) in ("0", "false", "False") else det_setting)
        except Exception:
            det_default = True
        res = prov.revise(
            base_text=job.input_json.get('base_text') or '',
            change_request=job.input_json.get('change_request') or '',
            file_refs=job.input_json.get('file_refs') or None,
            deterministic=det_default,
        )
        job.result_json = {"draft_text": res.text, "diff": "stub"}  # type: ignore[assignment]
        job.status = 'done'
        dt_ms = int((time.time() - t0) * 1000)
        try:
            AIMetric.objects.create(
                type='revise',
                model_id=res.model_id,
                duration_ms=dt_ms,
                tokens_used=res.usage_tokens,
                success=True,
                created_by=job.created_by,
                org_id=job.org_id,
                proposal_id=job.input_json.get('proposal_id'),
                section_id=job.input_json.get('section_id') or '',
            )
        except Exception:
            pass
        job.save(update_fields=['result_json', 'status'])
    except Exception as e:  # noqa: BLE001
        job.status = 'error'
        job.error_text = str(e)
        try:
            AIMetric.objects.create(
                type='revise',
                model_id='',
                duration_ms=0,
                tokens_used=0,
                success=False,
                error_text=job.error_text,
                created_by=job.created_by,
                org_id=job.org_id,
                proposal_id=job.input_json.get('proposal_id'),
                section_id=job.input_json.get('section_id') or '',
            )
        except Exception:
            pass
        job.save(update_fields=['status', 'error_text'])


@shared_task
def run_format(job_id: int):
    job = AIJob.objects.get(id=job_id)
    job.status = 'processing'
    job.save(update_fields=['status'])
    try:
        prov = _provider()
        t0 = time.time()
        res = prov.format_final(
            full_text=job.input_json.get('full_text') or '',
            template_hint=job.input_json.get('template_hint') or None,
            file_refs=job.input_json.get('file_refs') or None,
            deterministic=True,
        )
        job.result_json = {"formatted_text": res.text}  # type: ignore[assignment]
        job.status = 'done'
        dt_ms = int((time.time() - t0) * 1000)
        try:
            AIMetric.objects.create(
                type='format',
                model_id=res.model_id,
                duration_ms=dt_ms,
                tokens_used=res.usage_tokens,
                success=True,
                created_by=job.created_by,
                org_id=job.org_id,
                proposal_id=job.input_json.get('proposal_id'),
            )
        except Exception:
            pass
        job.save(update_fields=['result_json', 'status'])
    except Exception as e:  # noqa: BLE001
        job.status = 'error'
        job.error_text = str(e)
        try:
            AIMetric.objects.create(
                type='format',
                model_id='',
                duration_ms=0,
                tokens_used=0,
                success=False,
                error_text=job.error_text,
                created_by=job.created_by,
                org_id=job.org_id,
                proposal_id=job.input_json.get('proposal_id'),
            )
        except Exception:
            pass
        job.save(update_fields=['status', 'error_text'])
