from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

try:
    from proposals.models import Proposal
except Exception:  # pragma: no cover - proposals app always present in normal runs
    Proposal = None


class Command(BaseCommand):
    help = 'Seed a demo user and a sample proposal for local development'

    def handle(self, *args, **options):
        User = get_user_model()
        demo, created = User.objects.get_or_create(username='demo', defaults={'email': 'demo@example.com'})
        # Always reset password for convenience in local dev
        demo.set_password('demo12345')
        demo.save()

        if created:
            self.stdout.write(self.style.SUCCESS("Created demo user 'demo'"))
        else:
            self.stdout.write('Demo user already existed; password reset.')

        if Proposal is None:
            self.stdout.write('Proposals app not available; skipping sample proposal.')
            return

        if not Proposal.objects.filter(author=demo).exists():
            Proposal.objects.create(
                author=demo,
                content={
                    'meta': {'title': 'Sample Proposal'},
                    'sections': {
                        'summary': {
                            'title': 'Executive Summary',
                            'content': ('Lorem ipsum dolor sit amet, consectetur adipiscing elit.'),
                        },
                        'plan': {
                            'title': 'Project Plan',
                            'content': 'Step 1: Do X\nStep 2: Do Y',
                        },
                    },
                },
            )
            self.stdout.write(self.style.SUCCESS("Created a sample proposal for 'demo'."))
        else:
            self.stdout.write('Demo user already has a proposal; skipping creation.')

        self.stdout.write(self.style.SUCCESS('Seeding complete.'))
