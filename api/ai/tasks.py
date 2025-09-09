from celery import shared_task
from django.conf import settings
from .provider import get_provider
import time
from .models import AIJob, AIMetric, AIJobContext
from .prompting import render_role_prompt, PromptTemplateError
from . import retrieval
from .section_pipeline import get_section, save_write_result, apply_revision
from .validators import validate_role_output, SchemaError
from .diff_engine import diff_texts
from .section_materializer import materialize_sections


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
        snippets = retrieval.retrieve_for_plan(job.input_json.get('grant_url'), job.input_json.get('text_spec'))
        plan = prov.plan(grant_url=job.input_json.get('grant_url'), text_spec=job.input_json.get('text_spec'))
        validation = {}
        try:
            validate_role_output('plan', plan)
            validation = {"plan_valid": True}
        except SchemaError as ve:  # pragma: no cover - simple failure path
            validation = {"plan_valid": False, "error": str(ve)[:200]}
        # Render and store prompt snapshot
        try:
            rp = render_role_prompt(
                role='planner',
                variables={
                    'grant_url': job.input_json.get('grant_url'),
                    'text_spec': job.input_json.get('text_spec'),
                },
            )
            # Recompute redaction with mapping for persisted context
            redacted, red_map = AIJobContext.redact_with_mapping(rp.rendered)
            from .models import AIPromptTemplate as _PT  # local import to avoid circular
            template_sha = _PT.compute_checksum(rp.template.template) if rp.template else ''
            AIJobContext.objects.create(
                job=job,
                prompt_template=rp.template,
                prompt_version=rp.template.version if rp.template else 1,
                rendered_prompt_redacted=redacted,
                model_params={"deterministic": True},
                snippet_ids=[s['chunk_id'] for s in snippets],
                retrieval_metrics={"snippet_count": len(snippets), **validation},
                template_sha256=template_sha,
                redaction_map=red_map,
            )
        except PromptTemplateError as pe:  # pragma: no cover - unusual path
            AIJobContext.objects.create(
                job=job,
                rendered_prompt_redacted=AIJobContext.redact(f'PLAN TEMPLATE ERROR: {pe}')[:5000],
                model_params={"deterministic": True},
                snippet_ids=[s['chunk_id'] for s in snippets],
                retrieval_metrics={"snippet_count": len(snippets), **validation},
            )
        # Extract blueprint (same logic as sync endpoint) and materialize sections if proposal id present.
        created_sections: list[str] = []
        try:
            blueprint = []
            proposal_id_val = None
            if isinstance(plan, dict):
                if isinstance(plan.get('sections'), list):
                    blueprint = plan.get('sections')  # type: ignore[assignment]
                elif isinstance(plan.get('blueprint'), list):
                    blueprint = plan.get('blueprint')  # type: ignore[assignment]
                proposal_id_val = plan.get('proposal_id')
            if proposal_id_val and blueprint:
                mat = materialize_sections(proposal_id=int(proposal_id_val), blueprint=blueprint)
                created_sections = [s.key for (s, c) in mat if c]
        except Exception as me:  # pragma: no cover - defensive
            created_sections = ["error:" + str(me)[:120]]
        job.result_json = {  # type: ignore[assignment]
            "plan": plan,
            "created_sections": created_sections,
        }
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
        section_id = job.input_json.get('section_id') or ''
        section_locked = False
        section_obj = get_section(section_id) if section_id else None
        if section_obj and section_obj.locked:
            section_locked = True
        if section_locked:
            job.status = 'error'
            job.error_text = 'section_locked'
            job.save(update_fields=['status', 'error_text'])
            return

        # Retrieval & (future) budgeting
        res_snippets = retrieval.retrieve_for_section(section_id, job.input_json.get('answers') or {})
        allocation = {"snippets": res_snippets}  # placeholder until context budgeting integrated here

        # Provider call
        res = prov.write(
            section_id=section_id,
            answers=job.input_json.get('answers') or {},
            file_refs=job.input_json.get('file_refs') or None,
            deterministic=det_default,
        )

        # Validation
        validation = {}
        try:
            validate_role_output('write', {"draft": res.text})
            validation = {"write_valid": True}
        except SchemaError as ve:  # pragma: no cover
            validation = {"write_valid": False, "error": str(ve)[:200]}

        # Persist prompt context
        try:
            rp = render_role_prompt(
                role='writer',
                variables={
                    'section_id': section_id,
                    'answers_json': job.input_json.get('answers') or {},
                    'file_refs_json': job.input_json.get('file_refs') or [],
                },
            )
            redacted, red_map = AIJobContext.redact_with_mapping(rp.rendered)
            from .models import AIPromptTemplate as _PT
            template_sha = _PT.compute_checksum(rp.template.template) if rp.template else ''
            AIJobContext.objects.create(
                job=job,
                prompt_template=rp.template,
                prompt_version=rp.template.version if rp.template else 1,
                rendered_prompt_redacted=redacted,
                model_params={"deterministic": det_default},
                snippet_ids=[s['chunk_id'] for s in res_snippets],
                retrieval_metrics={
                    "snippet_count": len(res_snippets),
                    "used_snippets": len(allocation['snippets']),
                    **validation,
                },
                template_sha256=template_sha,
                redaction_map=red_map,
            )
        except PromptTemplateError as pe:  # pragma: no cover
            AIJobContext.objects.create(
                job=job,
                rendered_prompt_redacted=AIJobContext.redact(f'WRITE TEMPLATE ERROR: {pe}')[:5000],
                model_params={"deterministic": det_default},
                snippet_ids=[s['chunk_id'] for s in res_snippets],
                retrieval_metrics={
                    "snippet_count": len(res_snippets),
                    "used_snippets": len(allocation['snippets']),
                    **validation,
                },
            )

        # Result & persistence
        job.result_json = {  # type: ignore[assignment]
            "draft_text": res.text,
            "assets": [],
            "tokens_used": res.usage_tokens,
        }
        section = get_section(section_id)
        if section:
            save_write_result(section, res.text)
        job.status = 'done'

        # Metrics
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
                section_id=section_id,
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
        section_locked = False
        sec_id = job.input_json.get('section_id') or ''
        sec_obj = get_section(sec_id) if sec_id else None
        if sec_obj and sec_obj.locked:
            section_locked = True
        if section_locked:
            job.status = 'error'
            job.error_text = 'section_locked'
            job.save(update_fields=['status', 'error_text'])
            return
        # Revision cap enforcement (async path).
        try:
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
                    job.status = 'error'
                    job.error_text = 'revision_cap_reached'
                    job.save(update_fields=['status', 'error_text'])
                    try:
                        AIMetric.objects.create(
                            type='revise', model_id='revision_cap_blocked', duration_ms=0, tokens_used=0,
                            success=False, created_by=job.created_by, org_id=job.org_id,
                            proposal_id=job.input_json.get('proposal_id'), section_id=sec_id,
                            error_text='revision_cap_reached',
                        )
                    except Exception:
                        pass
                    return
        except Exception:  # pragma: no cover
            pass
        rev_snippets = retrieval.retrieve_for_section(
            job.input_json.get('section_id') or '',
            {"change_request": job.input_json.get('change_request') or ''},
        )
        allocation = {"snippets": rev_snippets}
        base_text = job.input_json.get('base_text') or ''
        section_id = job.input_json.get('section_id') or ''
        res = prov.revise(
            base_text=base_text,
            change_request=job.input_json.get('change_request') or '',
            file_refs=job.input_json.get('file_refs') or None,
            deterministic=det_default,
        )
        diff_res = diff_texts(base_text, res.text)
        validation = {}
        try:
            validate_role_output('revise', {"revised": res.text, "diff": diff_res})
            validation = {"revise_valid": True}
        except SchemaError as ve:  # pragma: no cover
            validation = {"revise_valid": False, "error": str(ve)[:200]}
        try:
            rp = render_role_prompt(
                role='reviser',
                variables={
                    'section_id': section_id,
                    'base_text': base_text,
                    'change_request': job.input_json.get('change_request') or '',
                    'file_refs_json': job.input_json.get('file_refs') or [],
                },
            )
            redacted, red_map = AIJobContext.redact_with_mapping(rp.rendered)
            from .models import AIPromptTemplate as _PT
            template_sha = _PT.compute_checksum(rp.template.template) if rp.template else ''
            AIJobContext.objects.create(
                job=job,
                prompt_template=rp.template,
                prompt_version=rp.template.version if rp.template else 1,
                rendered_prompt_redacted=redacted,
                model_params={"deterministic": det_default},
                snippet_ids=[s['chunk_id'] for s in rev_snippets],
                retrieval_metrics={
                    "snippet_count": len(rev_snippets),
                    "used_snippets": len(allocation['snippets']),
                    "change_ratio": round(diff_res.get('change_ratio', 0), 4),
                    **validation,
                },
                template_sha256=template_sha,
                redaction_map=red_map,
            )
        except PromptTemplateError as pe:  # pragma: no cover
            AIJobContext.objects.create(
                job=job,
                rendered_prompt_redacted=AIJobContext.redact(f'REVISE TEMPLATE ERROR: {pe}')[:5000],
                model_params={"deterministic": det_default},
                snippet_ids=[s['chunk_id'] for s in rev_snippets],
                retrieval_metrics={
                    "snippet_count": len(rev_snippets),
                    "used_snippets": len(allocation['snippets']),
                    "change_ratio": round(diff_res.get('change_ratio', 0), 4),
                    **validation,
                },
            )
        job.result_json = {"draft_text": res.text, "diff": diff_res}  # type: ignore[assignment]
        # Apply revision to section (keep as draft, don't auto-promote)
        section = get_section(section_id)
        if section:
            apply_revision(section, res.text, promote=False)
            try:
                # Append revision log (user context optional if job.created_by absent)
                section.append_revision(
                    user_id=getattr(job.created_by, 'id', None),
                    from_text=base_text,
                    to_text=res.text,
                    diff=diff_res,
                    change_ratio=diff_res.get('change_ratio'),
                )
            except Exception:  # pragma: no cover - logging suppressed
                pass
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
        fmt_snippets = []  # formatting currently not retrieval-driven
        res = prov.format_final(
            full_text=job.input_json.get('full_text') or '',
            template_hint=job.input_json.get('template_hint') or None,
            file_refs=job.input_json.get('file_refs') or None,
            deterministic=True,
        )
        validation = {}
        try:
            validate_role_output('format', {"formatted_markdown": res.text})
            validation = {"format_valid": True}
        except SchemaError as ve:  # pragma: no cover
            validation = {"format_valid": False, "error": str(ve)[:200]}
        try:
            rp = render_role_prompt(
                role='formatter',
                variables={
                    'template_hint': job.input_json.get('template_hint') or '',
                    'full_text': job.input_json.get('full_text') or '',
                },
            )
            redacted, red_map = AIJobContext.redact_with_mapping(rp.rendered)
            from .models import AIPromptTemplate as _PT
            template_sha = _PT.compute_checksum(rp.template.template) if rp.template else ''
            AIJobContext.objects.create(
                job=job,
                prompt_template=rp.template,
                prompt_version=rp.template.version if rp.template else 1,
                rendered_prompt_redacted=redacted,
                model_params={"deterministic": True},
                snippet_ids=[s['chunk_id'] for s in fmt_snippets],
                retrieval_metrics={"snippet_count": 0, **validation},
                template_sha256=template_sha,
                redaction_map=red_map,
            )
        except PromptTemplateError as pe:  # pragma: no cover
            AIJobContext.objects.create(
                job=job,
                rendered_prompt_redacted=AIJobContext.redact(f'FORMAT TEMPLATE ERROR: {pe}')[:5000],
                model_params={"deterministic": True},
                snippet_ids=[s['chunk_id'] for s in fmt_snippets],
                retrieval_metrics={"snippet_count": 0, **validation},
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
