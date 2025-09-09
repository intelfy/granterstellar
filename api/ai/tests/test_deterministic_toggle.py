from django.test import override_settings
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


def login(client, username='detuser'):
    user = User.objects.create_user(username=username, password='test12345')
    resp = client.post('/api/token', {'username': username, 'password': 'test12345'})
    token = resp.json()['access']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return user


def test_format_deterministic_default(db):
    client = APIClient()
    login(client)
    r1 = client.post('/api/ai/format', {'full_text': 'Hello World'}, format='json')
    r2 = client.post('/api/ai/format', {'full_text': 'Hello World'}, format='json')
    assert r1.status_code == 200 and r2.status_code == 200  # type: ignore[attr-defined]
    assert r1.json()['formatted_text'] == r2.json()['formatted_text']  # type: ignore[attr-defined]


def test_format_non_deterministic_toggle_off(db):
    client = APIClient()
    login(client, username='detuser2')
    with override_settings(AI_DETERMINISTIC_SAMPLING=False):
        r1 = client.post('/api/ai/format', {'full_text': 'Hello World'}, format='json')
        r2 = client.post('/api/ai/format', {'full_text': 'Hello World'}, format='json')
    assert r1.status_code == 200 and r2.status_code == 200  # type: ignore[attr-defined]
    # With stub providers output is currently identical; ensure flag propagates marker in text
    # GeminiProvider / LocalStubProvider embed deterministic=1 marker when True; absence implies toggle off
    assert 'deterministic=1' not in r1.json()['formatted_text']  # type: ignore[attr-defined]
    assert 'deterministic=1' not in r2.json()['formatted_text']  # type: ignore[attr-defined]


def test_format_deterministic_toggle_on(db):
    client = APIClient()
    login(client, username='detuser3')
    with override_settings(AI_DETERMINISTIC_SAMPLING=True):
        r = client.post('/api/ai/format', {'full_text': 'Hello World'}, format='json')
    assert r.status_code == 200  # type: ignore[attr-defined]
    assert 'deterministic=1' in r.json()['formatted_text']  # type: ignore[attr-defined]
