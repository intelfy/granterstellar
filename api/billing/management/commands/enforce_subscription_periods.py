from django.core.management.base import BaseCommand
from django.utils import timezone

from billing.models import Subscription
from orgs.models import Organization
from billing.utils import upsert_org_subscription_from_admin


class Command(BaseCommand):
    help = "Enforce subscription end-of-period cancellations (safety net if webhooks missed)"

    def handle(self, *args, **options):
        now = timezone.now()
        qs = Subscription.objects.filter(
            cancel_at_period_end=True,
            current_period_end__isnull=False,
            current_period_end__lte=now,
            status__in=["active", "trialing", "past_due"],
        )
        updated = 0
        for sub in qs.iterator():
            sub.status = "canceled"
            if not sub.canceled_at:
                sub.canceled_at = now
            sub.save(update_fields=["status", "canceled_at", "updated_at"])
            updated += 1
            # Downgrade cascade: if this is a personal subscription, mirror free/canceled onto admin orgs
            if sub.owner_user_id:
                try:
                    admin_user = sub.owner_user
                    for org in Organization.objects.filter(admin=admin_user).iterator():
                        upsert_org_subscription_from_admin(org)
                except Exception:
                    # Do not fail the whole enforcement if cascade fails for one org
                    pass
        self.stdout.write(self.style.SUCCESS(f"Subscriptions enforced: {updated}"))
