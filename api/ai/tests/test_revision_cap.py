from django.test import override_settings
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from proposals.models import Proposal, ProposalSection
from orgs.models import Organization

User = get_user_model()


def _login(client, username='capuser'):
    user = User.objects.create_user(username=username, password='test12345')
    resp = client.post('/api/token', {'username': username, 'password': 'test12345'})
    token = resp.json()['access']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return user


@override_settings(AI_PROVIDER='stub', PROPOSAL_SECTION_REVISION_CAP=5)
def test_revision_cap_enforced(db):  # noqa: D103
    client = APIClient()
    user = _login(client)
    org = Organization.objects.create(name='OrgCap', admin=user)
    proposal = Proposal.objects.create(author=user, org=org, state='draft', content={})
    section = ProposalSection.objects.create(proposal=proposal, key='s1', title='Intro')

    # Write baseline
    w = client.post('/api/ai/write', {'section_id': str(section.pk), 'answers': {'q': 'a'}}, format='json')
    assert w.status_code == 200  # noqa: PT018  # type: ignore[attr-defined]
    base_text = w.json()['draft_text']  # type: ignore[call-arg]

    # Perform 5 revisions (cap = 5) — should succeed
    for i in range(5):
        r = client.post(
            '/api/ai/revise',
            {'section_id': str(section.pk), 'base_text': base_text, 'change_request': f'Change {i}'},
            format='json',
        )
    assert r.status_code == 200  # noqa: PT018  # type: ignore[attr-defined]
    base_text = r.json()['draft_text']  # type: ignore[call-arg]

    section.refresh_from_db()
    assert len(section.revisions) == 5

    # 6th attempt: now returns 409 with error payload, no new revision appended
    r6 = client.post(
        '/api/ai/revise',
        {'section_id': str(section.pk), 'base_text': base_text, 'change_request': 'Overflow'},
        format='json',
    )
    assert r6.status_code == 409  # type: ignore[attr-defined]
    body6 = r6.json()  # type: ignore[call-arg]
    assert body6.get('error') == 'revision_cap_reached'
    assert body6.get('remaining_revision_slots') == 0
    section.refresh_from_db()
    assert len(section.revisions) == 5  # unchanged


@override_settings(AI_PROVIDER='stub', PROPOSAL_SECTION_REVISION_CAP=3)
def test_remaining_revision_slots_serializer(db):  # noqa: D103
    client = APIClient()
    user = _login(client, username='slotuser')
    org = Organization.objects.create(name='OrgSlots', admin=user)
    proposal = Proposal.objects.create(author=user, org=org, state='draft', content={})
    section = ProposalSection.objects.create(proposal=proposal, key='sec', title='T')

    # Baseline fetch (0 revisions) -> remaining = 3
    p_resp = client.get(f'/api/proposals/{proposal.id}')  # type: ignore[attr-defined]
    assert p_resp.status_code == 200  # noqa: PT018  # type: ignore[attr-defined]
    data = p_resp.json()  # type: ignore[call-arg]
    sec_entry = [s for s in data.get('sections', []) if s['id'] == section.id][0]  # type: ignore[attr-defined]
    assert sec_entry['remaining_revision_slots'] == 3

    # Add 2 revisions
    w = client.post('/api/ai/write', {'section_id': str(section.pk), 'answers': {'q': 'a'}}, format='json')
    assert w.status_code == 200  # noqa: PT018  # type: ignore[attr-defined]
    base_text = w.json()['draft_text']  # type: ignore[call-arg]
    for i in range(2):
        r = client.post(
            '/api/ai/revise',
            {'section_id': str(section.pk), 'base_text': base_text, 'change_request': f'Change {i}'},
            format='json',
        )
    assert r.status_code == 200  # noqa: PT018  # type: ignore[attr-defined]
    base_text = r.json()['draft_text']  # type: ignore[call-arg]

    p_resp2 = client.get(f'/api/proposals/{proposal.id}')  # type: ignore[attr-defined]
    sec_entry2 = [s for s in p_resp2.json().get('sections', []) if s['id'] == section.id][0]  # type: ignore[call-arg]
    assert sec_entry2['remaining_revision_slots'] == 1

    # Exceed cap (3rd revision) -> allowed (reaches cap)
    r3 = client.post(
        '/api/ai/revise',
        {'section_id': str(section.pk), 'base_text': base_text, 'change_request': 'Third'},
        format='json',
    )
    assert r3.status_code == 200  # noqa: PT018  # type: ignore[attr-defined]
    p_resp3 = client.get(f'/api/proposals/{proposal.id}')  # type: ignore[attr-defined]
    sec_entry3 = [s for s in p_resp3.json().get('sections', []) if s['id'] == section.id][0]  # type: ignore[call-arg]
    assert sec_entry3['remaining_revision_slots'] == 0

    # Another attempt beyond cap returns 409 and does not change remaining slots
    r_over = client.post(
        '/api/ai/revise',
        {'section_id': str(section.pk), 'base_text': base_text, 'change_request': 'Overflow attempt'},
        format='json',
    )
    assert r_over.status_code == 409  # noqa: PT018  # type: ignore[attr-defined]
    over_body = r_over.json()  # type: ignore[call-arg]
    assert over_body.get('error') == 'revision_cap_reached'
    assert over_body.get('remaining_revision_slots') == 0
    p_resp4 = client.get(f'/api/proposals/{proposal.id}')  # type: ignore[attr-defined]
    sec_entry4 = [s for s in p_resp4.json().get('sections', []) if s['id'] == section.id][0]  # type: ignore[call-arg]
    assert sec_entry4['remaining_revision_slots'] == 0
    # Metric assertion: failure record present
    from ai.models import AIMetric

    fail_metric_exists = AIMetric.objects.filter(
        type='revise', model_id='revision_cap_blocked', section_id=str(section.pk), success=False
    ).exists()
    assert fail_metric_exists
