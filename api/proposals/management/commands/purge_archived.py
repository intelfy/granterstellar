from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from proposals.models import Proposal


class Command(BaseCommand):
    help = 'Delete archived proposals older than 6 weeks (privacy retention).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Only count, do not delete')

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(weeks=6)
        qs = Proposal.objects.filter(state='archived', archived_at__isnull=False, archived_at__lt=cutoff)
        count = qs.count()
        if options.get('dry_run'):
            self.stdout.write(self.style.WARNING(f'Would delete: {count}'))
            return
        deleted = 0
        for p in qs.iterator():
            p.delete()
            deleted += 1
        self.stdout.write(self.style.SUCCESS(f'Archived proposals deleted: {deleted}'))
