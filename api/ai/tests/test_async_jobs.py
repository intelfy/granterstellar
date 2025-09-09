from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from typing import Any, cast
import time


@override_settings(
    DEBUG=True,  # AllowAny on endpoints
    AI_ASYNC=1,
    CELERY_TASK_ALWAYS_EAGER=True,  # Run Celery tasks synchronously in-process
    CELERY_BROKER_URL='memory://',
)
class AIAsyncJobTests(TestCase):
    def setUp(self):
        self.api = APIClient()

    def _wait_for_done(self, job_id: int, timeout_s: float = 2.0):
        t0 = time.time()
        last = None
        while time.time() - t0 < timeout_s:
            resp_any = cast(Any, self.api.get(f'/api/ai/jobs/{job_id}'))
            assert resp_any.status_code == 200
            last = resp_any.json()
            if last.get('status') in {'done', 'error'}:
                return last
            time.sleep(0.05)
        return last

    def test_async_write_job_succeeds(self):
        r_any = cast(
            Any,
            self.api.post(
                '/api/ai/write',
                {'section_id': 'summary', 'answers': {'objective': 'impact'}},
                format='json',
            ),
        )
        assert r_any.status_code == 200
        data = r_any.json()
        assert 'job_id' in data
        job = self._wait_for_done(data['job_id']) or {}
        assert job.get('status') == 'done', job
        result = job.get('result') or {}
        assert 'draft_text' in result, result

    def test_async_format_job_succeeds(self):
        r_any = cast(
            Any,
            self.api.post(
                '/api/ai/format',
                {'full_text': 'Hello world', 'template_hint': 'standard'},
                format='json',
            ),
        )
        assert r_any.status_code == 200
        data = r_any.json()
        assert 'job_id' in data
        job = self._wait_for_done(data['job_id']) or {}
        assert job.get('status') == 'done', job
        result = job.get('result') or {}
        assert 'formatted_text' in result, result
