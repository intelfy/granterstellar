from django.test import TestCase
from django.contrib.auth import get_user_model

from ai.models import AIPromptTemplate, AIJob, AIJobContext
from ai.prompting import render_role_prompt, PromptTemplateError, detect_template_drift


class PromptRenderingTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username='p', password='x')

    def test_render_with_db_template_and_strict_vars(self):
        tpl = AIPromptTemplate.objects.create(
            name='planner.base',
            version=1,
            role='planner',
            template='PLAN TEMPLATE\nGrant: {{grant_url}}\nSpec: {{text_spec}}\n',
            checksum='',
            variables=['grant_url', 'text_spec'],
            active=True,
        )
        rp = render_role_prompt(role='planner', variables={'grant_url': 'http://x', 'text_spec': 'Short'})
        self.assertIn('http://x', rp.rendered)
        self.assertIsNotNone(rp.template)
        self.assertEqual(rp.template.id, tpl.id)  # type: ignore[attr-defined]
        self.assertTrue(rp.redacted.startswith('PLAN TEMPLATE'))

    def test_missing_variable_raises(self):
        AIPromptTemplate.objects.create(
            name='planner.base',
            version=2,
            role='planner',
            template='{{grant_url}} {{text_spec}}',
            checksum='',
            variables=['grant_url', 'text_spec'],
            active=True,
        )
        with self.assertRaises(PromptTemplateError):
            render_role_prompt(role='planner', variables={'grant_url': 'http://only'})

    def test_extra_variable_raises(self):
        AIPromptTemplate.objects.create(
            name='planner.base',
            version=3,
            role='planner',
            template='{{grant_url}}',
            checksum='',
            variables=['grant_url'],
            active=True,
        )
        with self.assertRaises(PromptTemplateError):
            render_role_prompt(role='planner', variables={'grant_url': 'x', 'extra': 'y'})

    def test_fallback_template_when_none(self):
        rp = render_role_prompt(role='writer', variables={'input_json': {'a': 1}})
        self.assertIn('ROLE: writer', rp.rendered)
        self.assertIsNone(rp.template)

    def test_integration_context_created(self):
        AIPromptTemplate.objects.create(
            name='planner.base',
            version=4,
            role='planner',
            template='URL={{grant_url}}; SPEC={{text_spec}}',
            checksum='',
            variables=['grant_url', 'text_spec'],
            active=True,
        )
        job = AIJob.objects.create(
            type='plan',
            created_by=self.user,
            input_json={'grant_url': 'http://g', 'text_spec': 'abc'},
        )
        rp = render_role_prompt(role='planner', variables=job.input_json)
        AIJobContext.objects.create(
            job=job,
            prompt_template=rp.template,
            prompt_version=rp.template.version if rp.template else 1,
            rendered_prompt_redacted=rp.redacted,
            model_params={},
            snippet_ids=[],
            retrieval_metrics={},
        )
        ctx = AIJobContext.objects.get(job=job)
        self.assertIn('http://g', ctx.rendered_prompt_redacted)
        self.assertEqual(getattr(ctx.prompt_template, 'id', None), getattr(rp.template, 'id', None))

    def test_redaction_email_and_number(self):
        AIPromptTemplate.objects.create(
            name='writer.base',
            version=1,
            role='writer',
            template='Contact {{email}} ref {{refnum}}',
            checksum='',
            variables=['email', 'refnum'],
            active=True,
        )
        rp = render_role_prompt(role='writer', variables={'email': 'user@example.org', 'refnum': '1234567'})
        self.assertIn('[EMAIL_', rp.redacted)
        self.assertIn('[NUMBER_', rp.redacted)
        red2, mapping = AIJobContext.redact_with_mapping(rp.rendered)
        self.assertIn('EMAIL', mapping.values())
        self.assertIn('NUMBER', mapping.values())
        self.assertEqual(red2, rp.redacted)

    def test_blueprint_append_for_formatter(self):
        AIPromptTemplate.objects.create(
            name='formatter.base',
            version=1,
            role='formatter',
            template='FORMAT:\n{{full_text}}',
            checksum='',
            variables=['full_text', 'template_hint'],
            active=True,
            blueprint_schema={'type': 'object', 'properties': {'sections': {'type': 'array'}}},
            blueprint_instructions='Return markdown matching schema.',
        )
        rp = render_role_prompt(role='formatter', variables={'full_text': 'Hello', 'template_hint': ''})
        self.assertIn('STRUCTURE BLUEPRINT INSTRUCTIONS', rp.rendered)
        self.assertIn('SCHEMA JSON', rp.rendered)

    def test_context_includes_checksum_and_drift_detection(self):
        tpl = AIPromptTemplate.objects.create(
            name='planner.base',
            version=10,
            role='planner',
            template='URL={{grant_url}}',
            checksum='',
            variables=['grant_url', 'text_spec'],
            active=True,
        )
        job = AIJob.objects.create(
            type='plan',
            created_by=self.user,
            input_json={'grant_url': 'http://z', 'text_spec': 't'},
        )
        rp = render_role_prompt(role='planner', variables=job.input_json)
        redacted, red_map = AIJobContext.redact_with_mapping(rp.rendered)
        stored_checksum = AIPromptTemplate.compute_checksum(tpl.template)
        ctx = AIJobContext.objects.create(
            job=job,
            prompt_template=rp.template,
            prompt_version=rp.template.version if rp.template else 1,
            rendered_prompt_redacted=redacted,
            model_params={},
            snippet_ids=[],
            retrieval_metrics={},
            template_sha256=stored_checksum,
            redaction_map=red_map,
        )
        self.assertFalse(detect_template_drift(ctx))
        AIPromptTemplate.objects.filter(pk=tpl.pk).update(template=tpl.template + ' CHANGED')
        ctx_fresh = AIJobContext.objects.get(pk=ctx.pk)
        self.assertTrue(detect_template_drift(ctx_fresh))
