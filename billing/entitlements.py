"""The one answer to "what may this organisation do".

`for_organization(org)` reads the organisation's current `Subscription` row and
the feature registry and nothing else -- no PayPro, no network. Every gate in
the product (`require_feature`, `{% has_feature %}`, `survey.ai.quota`) goes
through here, so a plan rule changes in exactly one place.

The access rule is PayPro's own: Pro while `now < current_period_end` in a
status where the paid period still counts (active, payment failed, suspended,
terminated); not Pro once that date passes, and not Pro at all after a refund,
a chargeback or a finished subscription. No cron flips anything -- the
comparison is made on every call.
"""
from dataclasses import dataclass
from typing import Optional

from django.utils import timezone

from .features import PLAN_FREE, PLAN_PRO, features_for_plan
from .models import (
    STATUS_ACTIVE, STATUS_PAST_DUE, STATUS_SUSPENDED, STATUS_TERMINATED, Subscription,
)

STATE_NONE = 'none'            # never had a subscription
STATE_ACTIVE = 'active'
STATE_PAST_DUE = 'past_due'    # Pro, but PayPro is retrying a failed rebill
STATE_CANCELLING = 'cancelling'  # Pro until `until`, no renewal coming
STATE_LAPSED = 'lapsed'        # had Pro, period over or ended by refund/chargeback/finish


@dataclass(frozen=True)
class Entitlements:
    plan: str
    state: str
    until: Optional[object]
    features: frozenset
    subscription: Optional[Subscription] = None

    @property
    def is_pro(self):
        return self.plan == PLAN_PRO

    def has(self, feature_key):
        return feature_key in self.features


FREE = Entitlements(PLAN_FREE, STATE_NONE, None, features_for_plan(PLAN_FREE))


def current_subscription(organization):
    if organization is None:
        return None
    return Subscription.objects.current().filter(organization=organization).order_by('-created_at').first()


def for_organization(organization, now=None):
    """Entitlements of an organisation, cached on the instance for the request."""
    if organization is None:
        return FREE
    cached = getattr(organization, '_entitlements', None)
    if cached is not None and now is None:
        return cached
    ent = _compute(current_subscription(organization), now or timezone.now())
    if now is None:
        organization._entitlements = ent
    return ent


def for_subscription(subscription, now=None):
    return _compute(subscription, now or timezone.now())


def _compute(sub, now):
    if sub is None:
        return FREE
    period_end = sub.current_period_end
    honoured = sub.period_honoured and period_end is not None and now < period_end
    if not honoured:
        return Entitlements(PLAN_FREE, STATE_LAPSED, None, features_for_plan(PLAN_FREE), sub)
    if sub.status == STATUS_ACTIVE:
        state = STATE_ACTIVE
    elif sub.status == STATUS_PAST_DUE:
        state = STATE_PAST_DUE
    else:  # suspended / terminated: paid up, nothing coming
        state = STATE_CANCELLING
    return Entitlements(sub.plan_code, state, period_end, features_for_plan(sub.plan_code), sub)


def has_feature(organization, feature_key):
    return for_organization(organization).has(feature_key)
