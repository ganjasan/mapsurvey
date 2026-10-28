"""Subscriptions, the raw webhook log, checkout intents and Pro help requests.

`Subscription` is a *projection* of what PayPro told us, never an opinion of
our own: every field that decides access (`status`, `current_period_end`) is
written only by `billing.ipn.apply` from a verified webhook. The billing page's
API actions ask PayPro to change something and wait for the webhook that
confirms it -- they never write these fields themselves.
"""
import uuid as uuid_module

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .features import PLAN_PRO

# PayPro's subscription statuses plus the three order outcomes that end access
# regardless of the subscription's own status.
STATUS_ACTIVE = 'active'
STATUS_PAST_DUE = 'past_due'          # a rebill failed, PayPro is retrying
STATUS_SUSPENDED = 'suspended'        # PayPro status 2: renewable
STATUS_TERMINATED = 'terminated'      # PayPro status 3: not renewable by us
STATUS_FINISHED = 'finished'          # PayPro status 4: cycles exhausted
STATUS_REFUNDED = 'refunded'
STATUS_CHARGED_BACK = 'charged_back'

STATUS_CHOICES = (
    (STATUS_ACTIVE, _('Active')),
    (STATUS_PAST_DUE, _('Payment failed')),
    (STATUS_SUSPENDED, _('Suspended')),
    (STATUS_TERMINATED, _('Terminated')),
    (STATUS_FINISHED, _('Finished')),
    (STATUS_REFUNDED, _('Refunded')),
    (STATUS_CHARGED_BACK, _('Charged back')),
)

# Statuses under which the paid period still counts (PayPro's own rule: keep
# access until SUBSCRIPTION_NEXT_CHARGE_DATE after a suspension/termination).
PERIOD_HONOURED_STATUSES = frozenset({STATUS_ACTIVE, STATUS_PAST_DUE, STATUS_SUSPENDED, STATUS_TERMINATED})

RENEWAL_AUTO = 'auto'
RENEWAL_MANUAL = 'manual'
RENEWAL_CHOICES = ((RENEWAL_AUTO, _('Automatic')), (RENEWAL_MANUAL, _('By invoice')), ('', _('Unknown')))

# PayPro cancellation reason ids (webhook SUBSCRIPTION_CANCELLATION_REASON_ID,
# API cancellationReasonId). 7 is webhook-only.
CANCELLATION_REASONS = (
    (1, _('The price is too high')),
    (2, _('I no longer need this product')),
    (3, _('I am not satisfied with the product')),
    (4, _('I switched to another product')),
    (5, _("It isn't a priority right now")),
    (6, _('I subscribed by mistake')),
    (7, _('Other reason')),
    (8, _('I am switching to another subscription plan')),
)


class SubscriptionQuerySet(models.QuerySet):
    def current(self):
        return self.filter(superseded_at__isnull=True)


class Subscription(models.Model):
    organization = models.ForeignKey('survey.Organization', on_delete=models.CASCADE, related_name='subscriptions')
    plan_code = models.CharField(max_length=16, default=PLAN_PRO)
    # Key into settings.PPG_PRODUCTS ("pro_monthly"); the product id itself is
    # also kept so a product renamed in settings still reads correctly.
    product_key = models.CharField(max_length=32, blank=True)
    ppg_product_id = models.CharField(max_length=32, blank=True)
    ppg_subscription_id = models.CharField(max_length=32, blank=True, db_index=True)
    ppg_initial_order_id = models.CharField(max_length=32, blank=True)
    ppg_last_order_id = models.CharField(max_length=32, blank=True)
    ppg_customer_id = models.CharField(max_length=32, blank=True)
    customer_email = models.EmailField(blank=True)

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    renewal_type = models.CharField(max_length=8, choices=RENEWAL_CHOICES, blank=True)
    # The date PayPro gave us, parsed and raw. The raw string is kept because
    # the webhook's date format is not documented; if parsing ever drifts the
    # admin can see what was actually sent.
    current_period_end = models.DateTimeField(null=True, blank=True)
    current_period_end_raw = models.CharField(max_length=64, blank=True)
    trial_until = models.DateTimeField(null=True, blank=True)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    # Order id of the rebill whose first failure we already reported, so one
    # dunning cycle yields one plan_payment_failed however many attempts PayPro makes.
    payment_failed_reported_for = models.CharField(max_length=32, blank=True)
    cancellation_reason_id = models.PositiveSmallIntegerField(null=True, blank=True)
    action_reason = models.TextField(blank=True)
    last_invoice_url = models.URLField(max_length=500, blank=True)
    # A chargeback flags the organisation for a human look; OrderChargedBackWon
    # never restores access on its own.
    needs_review = models.BooleanField(default=False)

    # A second purchase (monthly, then yearly) replaces the current row; the old
    # one stays for the admin and for the duplicate warning on the billing page.
    superseded_at = models.DateTimeField(null=True, blank=True)
    # Set by an API action on the billing page ("cancel requested"), cleared by
    # the next applied webhook or by time. Copy only -- never an entitlement input.
    pending_change = models.CharField(max_length=32, blank=True)
    pending_change_until = models.DateTimeField(null=True, blank=True)
    lapse_notified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SubscriptionQuerySet.as_manager()

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.organization} {self.plan_code} {self.status} (#{self.ppg_subscription_id or "-"})'

    @property
    def period_honoured(self):
        return self.status in PERIOD_HONOURED_STATUSES

    @property
    def pending_change_active(self):
        return bool(self.pending_change) and self.pending_change_until is not None \
            and self.pending_change_until > timezone.now()


class BillingEvent(models.Model):
    """One row per webhook delivery that passed verification. Append-only.

    The uniqueness key is what makes PayPro's resends (every 30 min on failure,
    and any time from the control panel) harmless: the same body for the same
    order and type is acknowledged and never applied twice.
    """
    ipn_type_id = models.PositiveSmallIntegerField()
    ipn_type_name = models.CharField(max_length=64, blank=True)
    order_id = models.CharField(max_length=32, blank=True)
    ppg_subscription_id = models.CharField(max_length=32, blank=True, db_index=True)
    product_id = models.CharField(max_length=32, blank=True)
    test_mode = models.BooleanField(default=False)
    is_resent = models.BooleanField(default=False)
    # Stored but not applied: a test-mode event on an environment that does not
    # accept them (production).
    ignored_test = models.BooleanField(default=False)
    body_sha256 = models.CharField(max_length=64)
    payload = models.JSONField()
    verified_by = models.JSONField(default=list)
    organization = models.ForeignKey('survey.Organization', null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='billing_events')
    subscription = models.ForeignKey(Subscription, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='events')
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ('-received_at',)
        constraints = [
            models.UniqueConstraint(fields=('order_id', 'ipn_type_id', 'body_sha256'), name='billing_event_once'),
        ]

    def __str__(self):
        return f'{self.ipn_type_name or self.ipn_type_id} order={self.order_id} sub={self.ppg_subscription_id}'


class CheckoutIntent(models.Model):
    """"Upgrade" was clicked: who, for which organisation, for which product.

    The nonce travels to PayPro as `x-nonce` and comes back in
    ORDER_CUSTOM_FIELDS, so a webhook can be tied to the click even if
    `x-org_id` were lost, and the return page can show the right organisation
    without a session.
    """
    nonce = models.UUIDField(default=uuid_module.uuid4, unique=True, editable=False)
    organization = models.ForeignKey('survey.Organization', on_delete=models.CASCADE, related_name='checkout_intents')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    product_key = models.CharField(max_length=32)
    quote = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    order_id = models.CharField(max_length=32, blank=True)

    def __str__(self):
        return f'{self.organization} {self.product_key} {self.nonce}'


class ProHelpRequest(models.Model):
    """A Pro organisation asking for the service it pays for."""
    KIND_CHOICES = (
        ('consulting', _('Project consulting')),
        ('analysis', _('Analysis of responses')),
        ('report', _('A report for a council, client or funder')),
        ('other', _('Something else')),
    )
    organization = models.ForeignKey('survey.Organization', on_delete=models.CASCADE, related_name='help_requests')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    survey = models.ForeignKey('survey.SurveyHeader', null=True, blank=True, on_delete=models.SET_NULL)
    message = models.TextField(max_length=5000)
    contact_email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    handled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.organization} {self.kind} {self.created_at:%Y-%m-%d}'


GRANT_KIND_TRIAL = 'trial'
GRANT_KIND_CHOICES = ((GRANT_KIND_TRIAL, _('Pro trial')),)


class EntitlementGrant(models.Model):
    """The second entitlement source, next to `Subscription` (change
    pro-trial-allowances, #471; the academic programme #322 adds a kind).

    The paywall's "one grant path" rule is about `Subscription`: only the
    webhook writes it, and that stays true. A grant is a different row with a
    different writer -- the owner's "Try Pro" click for a trial -- and gives
    counted uses of features (`GrantAllowance`), never a plan. Access is a
    comparison on every read (`starts_at <= now < expires_at`, not revoked);
    nothing flips state on a schedule.
    """
    organization = models.ForeignKey('survey.Organization', on_delete=models.CASCADE, related_name='grants')
    kind = models.CharField(max_length=16, choices=GRANT_KIND_CHOICES)
    # The person a trial belongs to: one trial per user whichever workspace they
    # claim it for, because a user can create any number of workspaces.
    claimed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='claimed_grants')
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='issued_grants')
    starts_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(fields=('organization', 'kind'), name='grant_one_kind_per_org'),
            models.UniqueConstraint(fields=('claimed_by',), condition=models.Q(kind=GRANT_KIND_TRIAL),
                                    name='grant_one_trial_per_user'),
        ]

    def __str__(self):
        return f'{self.organization} {self.kind} until {self.expires_at:%Y-%m-%d}'

    def is_live(self, now=None):
        now = now or timezone.now()
        return self.revoked_at is None and self.starts_at <= now < self.expires_at


class GrantAllowance(models.Model):
    """How many uses of one feature a grant gives and how many are spent.
    `used` is only ever changed by `billing.trial.consume`, one atomic UPDATE."""
    grant = models.ForeignKey(EntitlementGrant, on_delete=models.CASCADE, related_name='allowances')
    feature = models.CharField(max_length=32)
    limit = models.PositiveIntegerField()
    used = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('feature',)
        constraints = [
            models.UniqueConstraint(fields=('grant', 'feature'), name='allowance_one_per_feature'),
        ]

    def __str__(self):
        return f'{self.feature} {self.used}/{self.limit}'
