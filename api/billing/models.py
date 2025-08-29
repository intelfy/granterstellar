from django.conf import settings
from django.db import models


class Subscription(models.Model):
    TIER_CHOICES = (
        ('free', 'Free'),
        ('pro', 'Pro'),
        ('enterprise', 'Enterprise'),
    )
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('trialing', 'Trialing'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
        ('incomplete', 'Incomplete'),
        ('incomplete_expired', 'Incomplete Expired'),
    )

    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='subscriptions',
    )
    owner_org = models.ForeignKey(
        'orgs.Organization',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='subscriptions',
    )
    stripe_customer_id = models.CharField(max_length=64, blank=True, default='')
    stripe_subscription_id = models.CharField(max_length=64, blank=True, default='')
    tier = models.CharField(max_length=16, choices=TIER_CHOICES, default='free')
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='incomplete')
    current_period_end = models.DateTimeField(null=True, blank=True)
    # Number of paid seats for this subscription (quantity of the seat price)
    seats = models.IntegerField(default=0)
    # Lifecycle flags
    cancel_at_period_end = models.BooleanField(default=False)
    canceled_at = models.DateTimeField(null=True, blank=True)
    # Optional discount information (coupon/promotion)
    # Stores a summary like:
    # {
    #   "source": "promotion_code|coupon",
    #   "id": "promo_...|coupon_...",
    #   "percent_off": 10,
    #   "amount_off": 0,
    #   "currency": "usd",
    #   "duration": "once|repeating|forever",
    #   "duration_in_months": 1,
    # }
    discount = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=~(models.Q(owner_user__isnull=True) & models.Q(owner_org__isnull=True)),
                name='subscription_owner_present',
            ),
            models.CheckConstraint(
                check=~(models.Q(owner_user__isnull=False) & models.Q(owner_org__isnull=False)),
                name='subscription_owner_xor',
            ),
        ]


class ExtraCredits(models.Model):
    """Tracks extra proposals purchased for a given month, scoped to a user or an org.
    These credits extend the monthly_cap for proposal creation.
    """
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='extra_credits',
    )
    owner_org = models.ForeignKey(
        'orgs.Organization',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='extra_credits',
    )
    month = models.DateField()
    proposals = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=~(models.Q(owner_user__isnull=True) & models.Q(owner_org__isnull=True)),
                name='extra_owner_present',
            ),
            models.CheckConstraint(
                check=~(models.Q(owner_user__isnull=False) & models.Q(owner_org__isnull=False)),
                name='extra_owner_xor',
            ),
            models.UniqueConstraint(fields=['owner_user', 'owner_org', 'month'], name='extra_unique_owner_month'),
        ]
