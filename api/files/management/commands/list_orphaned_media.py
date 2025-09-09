import os
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand

from files.models import FileUpload
from exports.models import ExportJob


def _url_to_media_rel(url: str) -> str | None:
    """Convert a MEDIA_URL-based URL to a relative media path (if possible)."""
    if not url:
        return None
    media_url = settings.MEDIA_URL or '/media/'
    # Normalize to path-only
    path = url
    try:
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            path = parsed.path or ''
    except Exception:
        pass
    if not path:
        return None
    # Strip leading media_url if present
    if path.startswith(media_url):
        return path[len(media_url) :].lstrip('/')
    # Fallback: accept known prefixes
    for prefix in ('uploads/', 'exports/'):
        if path.lstrip('/').startswith(prefix):
            return path.lstrip('/')
    return None


class Command(BaseCommand):
    help = 'List files under MEDIA_ROOT that are not referenced by FileUpload or ExportJob records.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--prefix',
            action='append',
            default=['uploads/', 'exports/'],
            help='Media subpath prefixes to scan (default: uploads/, exports/). Can be provided multiple times.',
        )

    def handle(self, *args, **options):
        prefixes = options.get('prefix') or ['uploads/', 'exports/']
        media_root = settings.MEDIA_ROOT
        if not media_root or not os.path.isdir(media_root):
            self.stdout.write(self.style.WARNING('MEDIA_ROOT not configured or not a directory'))
            return

        # Gather referenced relative paths
        referenced: set[str] = set()
        for up in FileUpload.objects.only('file').iterator():
            try:
                name = getattr(up.file, 'name', '')
                if name:
                    referenced.add(name)
            except Exception:
                continue
        for job in ExportJob.objects.only('url').iterator():
            rel = _url_to_media_rel(job.url)
            if rel:
                referenced.add(rel)

        scanned: list[str] = []
        orphans: list[str] = []
        for prefix in prefixes:
            root = os.path.join(media_root, prefix)
            if not os.path.isdir(root):
                continue
            for dirpath, _, filenames in os.walk(root):
                for fn in filenames:
                    full = os.path.join(dirpath, fn)
                    # Compute relative to media root with forward slashes
                    rel = os.path.relpath(full, media_root).replace(os.sep, '/')
                    scanned.append(rel)
                    if rel not in referenced:
                        orphans.append(rel)

        self.stdout.write(f'Scanned files: {len(scanned)}')
        self.stdout.write(f'Referenced files: {len(referenced)}')
        self.stdout.write(self.style.WARNING(f'Orphaned files: {len(orphans)}'))
        if orphans:
            for rel in sorted(orphans):
                self.stdout.write(rel)
