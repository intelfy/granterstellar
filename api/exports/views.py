from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.urls import reverse  # noqa: F401
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings

from proposals.models import Proposal
from .models import ExportJob
from .utils import proposal_json_to_markdown, render_pdf_from_text, render_docx_from_markdown
from .tasks import perform_export


@api_view(["POST"])
@permission_classes([AllowAny if settings.DEBUG else IsAuthenticated])
def create_export(request):
    proposal_id = request.data.get("proposal_id")
    fmt = (request.data.get("format") or "md").lower()
    if fmt not in ("md", "pdf", "docx"):
        return Response({"error": "invalid_format"}, status=status.HTTP_400_BAD_REQUEST)
    # Scope access: personal (author=user, org is null) or org scope via X-Org-ID
    org = None
    org_id = request.headers.get("X-Org-ID")
    if org_id and str(org_id).isdigit():
        from orgs.models import Organization
        org = Organization.objects.filter(id=int(org_id)).first()
    try:
        qs = Proposal.objects.all()
        if org is not None:
            qs = qs.filter(org=org)
        else:
            qs = qs.filter(author=request.user, org__isnull=True)
        proposal = qs.get(id=proposal_id)
    except Proposal.DoesNotExist:
        return Response({"error": "not_found"}, status=status.HTTP_404_NOT_FOUND)

    job = ExportJob.objects.create(proposal=proposal, format=fmt, status='pending')

    # Async path when enabled and broker configured
    if getattr(settings, 'EXPORTS_ASYNC', False) and getattr(settings, 'CELERY_BROKER_URL', ''):
        try:
            perform_export.delay(job.id)
            return Response({"id": job.id, "status": job.status})
        except Exception:
            # Fall through to sync if enqueue fails
            pass

    # Synchronous render (default)
    content = proposal.content or {}
    md = proposal_json_to_markdown(content)
    checksum = ''
    if fmt == 'md':
        data = md.encode('utf-8')
        ext = 'md'
        import hashlib
        checksum = hashlib.sha256(data).hexdigest()
    elif fmt == 'pdf':
        data, checksum = render_pdf_from_text(md)
        ext = 'pdf'
    else:
        data, checksum = render_docx_from_markdown(md)
        ext = 'docx'

    path = f"exports/proposal-{proposal.id}-{job.id}.{ext}"
    default_storage.save(path, ContentFile(data))
    url = f"{settings.MEDIA_URL}{path}"
    job.status = 'done'
    job.url = url
    job.checksum = checksum or ''
    job.save(update_fields=['status', 'url', 'checksum'])
    # Increment proposal downloads counter
    try:
        proposal.downloads = (proposal.downloads or 0) + 1
        proposal.save(update_fields=['downloads'])
    except Exception:
        pass
    return Response({"id": job.id, "status": job.status, "url": job.url, "checksum": job.checksum})


@api_view(["GET"])
@permission_classes([AllowAny if settings.DEBUG else IsAuthenticated])
def get_export(request, job_id: int):
    # Only allow fetching jobs for proposals the user can access (personal or org scope)
    org = None
    org_id = request.headers.get("X-Org-ID")
    if org_id and str(org_id).isdigit():
        from orgs.models import Organization
        org = Organization.objects.filter(id=int(org_id)).first()
    try:
        qs = ExportJob.objects.select_related('proposal')
        if org is not None:
            qs = qs.filter(proposal__org=org)
        else:
            qs = qs.filter(proposal__author=request.user, proposal__org__isnull=True)
        job = qs.get(id=job_id)
    except ExportJob.DoesNotExist:
        return Response({"error": "not_found"}, status=status.HTTP_404_NOT_FOUND)
    return Response({"id": job.id, "status": job.status, "url": job.url, "format": job.format})
