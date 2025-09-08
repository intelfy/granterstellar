from django.test import override_settings
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from ai.models import AIMetric

User = get_user_model()


def _make_user(username: str = "u1"):
    return User.objects.create_user(username=username, password="test12345")


def test_daily_request_cap_blocks_after_limit(db):
    user = _make_user()
    client = APIClient()
    resp = client.post("/api/token", {"username": user.username, "password": "test12345"})
    assert resp.status_code == 200  # type: ignore[attr-defined]
    token = resp.json()["access"]  # type: ignore[attr-defined]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    with override_settings(DEBUG=False, AI_RATE_PER_MIN_PRO=1000, AI_DAILY_REQUEST_CAP_PRO=2):
        # First two succeed
        for i in range(2):
            r = client.post("/api/ai/plan", {"text_spec": f"spec {i}"}, format='json')
            assert r.status_code == 200  # type: ignore[attr-defined]
        # Third should 429
    r = client.post("/api/ai/plan", {"text_spec": "spec 3"}, format='json')
    assert r.status_code == 429  # type: ignore[attr-defined]
    body = r.json()  # type: ignore[attr-defined]
    assert body.get("reason") == "ai_daily_request_cap"
    assert r.headers.get("X-AI-Daily-Cap") == "2"  # type: ignore[attr-defined]
    assert r.headers.get("X-AI-Daily-Used") == "2"  # type: ignore[attr-defined]


def test_monthly_token_cap_blocks_write(db):
    user = _make_user("u2")
    client = APIClient()
    resp = client.post("/api/token", {"username": user.username, "password": "test12345"})
    token = resp.json()["access"]  # type: ignore[attr-defined]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    # Pre-seed token usage near cap
    AIMetric.objects.create(type='write', model_id='m', duration_ms=10, tokens_used=9, created_by=user, success=True)
    with override_settings(DEBUG=False, AI_RATE_PER_MIN_PRO=1000, AI_MONTHLY_TOKENS_CAP_PRO=10):
        r = client.post("/api/ai/write", {"section_id": "s1", "answers": {}, "file_refs": []}, format='json')
        # If first call not blocked we create a tiny metric then retry to force block
    if r.status_code == 200:  # type: ignore[attr-defined]
            AIMetric.objects.create(type='write', model_id='m', duration_ms=10, tokens_used=1, created_by=user, success=True)
            r = client.post("/api/ai/write", {"section_id": "s1", "answers": {}, "file_refs": []}, format='json')
    assert r.status_code == 429  # type: ignore[attr-defined]
    assert r.json().get("reason") == "ai_monthly_tokens_cap"  # type: ignore[attr-defined]
