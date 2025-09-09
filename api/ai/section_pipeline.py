"""Section pipeline helpers (Phase 3).

Encapsulates reading/updating ProposalSection records during write/revise cycles.
"""

from __future__ import annotations
from django.db import transaction
from proposals.models import ProposalSection


def get_section(section_id: str) -> ProposalSection | None:
    try:
        return ProposalSection.objects.get(id=section_id)
    except (ProposalSection.DoesNotExist, ValueError):  # invalid uuid/int or missing
        return None


def save_write_result(section: ProposalSection, draft_text: str):
    """Persist a write draft into the section's draft_content only.

    Does not promote to final content automatically; a later approval step can
    copy draft_content -> content.
    """
    section.draft_content = draft_text
    section.save(update_fields=['draft_content', 'updated_at'])


def apply_revision(section: ProposalSection, revised_text: str, promote: bool = False):
    """Apply a revision.

    If promote=True, move revised text into permanent content and also snapshot
    into draft_content for continuity.
    """
    section.draft_content = revised_text
    if promote:
        section.content = revised_text
        section.save(update_fields=['draft_content', 'content', 'updated_at'])
    else:
        section.save(update_fields=['draft_content', 'updated_at'])


@transaction.atomic
def upsert_section(proposal_id: int, key: str, title: str = '') -> ProposalSection:
    section, _created = ProposalSection.objects.get_or_create(
        proposal_id=proposal_id,
        key=key,
        defaults={'title': title, 'order': 0},
    )
    return section


def promote_section(section: ProposalSection):
    """Promote current draft_content to content and lock section.

    Locking prevents further AI write/revise until explicitly unlocked (future).
    """
    section.content = section.draft_content
    section.locked = True
    section.save(update_fields=['content', 'locked', 'updated_at'])
