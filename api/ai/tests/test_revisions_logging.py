from django.test import override_settings
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from proposals.models import Proposal, ProposalSection
from orgs.models import Organization

User = get_user_model()


def _login(client, username='revuser'):
    user = User.objects.create_user(username=username, password='test12345')
    resp = client.post('/api/token', {'username': username, 'password': 'test12345'})
    token = resp.json()['access']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return user


@override_settings(AI_PROVIDER='stub')
def test_revise_appends_revision_log(db):  # noqa: D103
    client = APIClient()
    user = _login(client)
    # Need a proposal + section record because append_revision saves via model
    org = Organization.objects.create(name='Org', admin=user)
    proposal = Proposal.objects.create(author=user, org=org, state='draft', content={})
    section = ProposalSection.objects.create(proposal=proposal, key='s1', title='Intro')
    # Perform a write to set draft baseline
    w = client.post('/api/ai/write', {'section_id': str(section.pk), 'answers': {'q': 'a'}}, format='json')
    assert w.status_code == 200  # noqa: PT018
    base_text = w.json()['draft_text']  # type: ignore[index]
    # Revise with a change request
    r = client.post(
        '/api/ai/revise',
        {'section_id': str(section.pk), 'base_text': base_text, 'change_request': 'Add more details'},
        format='json',
    )
    assert r.status_code == 200  # noqa: PT018
    # Reload section to inspect revisions log
    section.refresh_from_db()
    assert isinstance(section.revisions, list)
    assert len(section.revisions) >= 1
    last = section.revisions[-1]
    # Schema expectations
    assert 'ts' in last and 'from' in last and 'to' in last
    assert 'change_ratio' in last
    # Blocks optional - but if present validate minimal shape
    if 'blocks' in last:
        assert isinstance(last['blocks'], list)
        if last['blocks']:
            b0 = last['blocks'][0]
            assert {'type', 'before', 'after'}.issubset(b0.keys())
