from django.test import override_settings
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()

def login(client, username="dwuser"):
    user = User.objects.create_user(username=username, password="test12345")
    resp = client.post("/api/token", {"username": username, "password": "test12345"})
    token = resp.json()["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return user

@override_settings(AI_PROVIDER="stub")
def test_write_revise_deterministic_default():
    client = APIClient()
    login(client)
    # default setting True (project default) -> marker should appear
    r = client.post("/api/ai/write", {"section_id": "s1", "answers": {"a": "b"}}, format='json')
    assert r.status_code == 200  # type: ignore[attr-defined]
    assert "[deterministic]" in r.json()["draft_text"]  # type: ignore[attr-defined]
    # Revise
    r2 = client.post("/api/ai/revise", {"base_text": "Base", "change_request": "Add", "section_id": "s1"}, format='json')
    assert r2.status_code == 200  # type: ignore[attr-defined]
    assert "[deterministic]" in r2.json()["draft_text"]  # type: ignore[attr-defined]

@override_settings(AI_PROVIDER="stub", AI_DETERMINISTIC_SAMPLING=False)
def test_write_revise_deterministic_toggle_off():
    client = APIClient()
    login(client, username="dwuser2")
    r = client.post("/api/ai/write", {"section_id": "s1", "answers": {"a": "b"}}, format='json')
    assert r.status_code == 200  # type: ignore[attr-defined]
    assert "[deterministic]" not in r.json()["draft_text"]  # type: ignore[attr-defined]
    r2 = client.post("/api/ai/revise", {"base_text": "Base", "change_request": "Add", "section_id": "s1"}, format='json')
    assert r2.status_code == 200  # type: ignore[attr-defined]
    assert "[deterministic]" not in r2.json()["draft_text"]  # type: ignore[attr-defined]

@override_settings(AI_PROVIDER="stub", AI_DETERMINISTIC_SAMPLING=False)
def test_write_revise_request_override_true():
    client = APIClient()
    login(client, username="dwuser3")
    # Override via request param deterministic=True
    r = client.post("/api/ai/write", {"section_id": "s1", "answers": {"a": "b"}, "deterministic": True}, format='json')
    assert r.status_code == 200  # type: ignore[attr-defined]
    assert "[deterministic]" in r.json()["draft_text"]  # type: ignore[attr-defined]
    r2 = client.post("/api/ai/revise", {"base_text": "Base", "change_request": "Add", "section_id": "s1", "deterministic": True}, format='json')
    assert r2.status_code == 200  # type: ignore[attr-defined]
    assert "[deterministic]" in r2.json()["draft_text"]  # type: ignore[attr-defined]

@override_settings(AI_PROVIDER="stub", AI_DETERMINISTIC_SAMPLING=True)
def test_write_revise_request_override_false():
    client = APIClient()
    login(client, username="dwuser4")
    r = client.post("/api/ai/write", {"section_id": "s1", "answers": {"a": "b"}, "deterministic": False}, format='json')
    assert r.status_code == 200  # type: ignore[attr-defined]
    assert "[deterministic]" not in r.json()["draft_text"]  # type: ignore[attr-defined]
    r2 = client.post("/api/ai/revise", {"base_text": "Base", "change_request": "Add", "section_id": "s1", "deterministic": False}, format='json')
    assert r2.status_code == 200  # type: ignore[attr-defined]
    assert "[deterministic]" not in r2.json()["draft_text"]  # type: ignore[attr-defined]
