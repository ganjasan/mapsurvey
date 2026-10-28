"""The one answer to "what may this organisation do".

`for_organization(org)` reads the organisation's current `Subscription` row,
its live `EntitlementGrant` (the Pro trial, change pro-trial-allowances) and
the feature registry and nothing else -- no PayPro, no network. Every gate in
the product (`require_feature`, `{% has_feature %}`, `api.gates`,
`survey.ai.quota`) goes through here, so a plan rule changes in exactly one
place.

Three questions, three methods:
- `has(key)`: does the PLAN include the feature. The plan cards, `is_pro`, the
  lapse task and the pricing copy reason about the plan.
- `may(key)`: can the workspace make a NEW use of the feature now -- the plan
  includes it, or a live trial still has a remainder for it. Every gate that
  decides an action asks this. A use that the plan does not cover is counted
  with `billing.trial.consume`.
- `covers(key)`: is the feature in force -- the plan includes it, or a live
  trial includes it at all. Rendering a state set earlier asks this (the badge
  on a survey switched off under the trial).

The access rule for a subscription is PayPro's own: Pro while
`now < current_period_end` in a status where the paid period still counts
(active, payment failed, suspended, terminated); not Pro once that date
passes, and not Pro at all after a refund, a chargeback or a finished
subscription. A grant is live while `starts_at <= now < expires_at` and not
revoked. No cron flips anything -- the comparison is made on every call.
"""
from dataclasses import dataclass, field
from typing import Optional

from django.utils import timezone

from .features import PLAN_FREE, PLAN_PRO, features_for_plan
from .models import (
    STATUS_ACTIVE, STATUS_PAST_DUE, STATUS_SUSPENDED, STATUS_TERMINATED, GrantAllowance, Subscription,
)

STATE_NONE = 'none'            # never had a subscription
STATE_ACTIVE = 'active'
STATE_PAST_DUE = 'past_due'    # Pro, but PayPro is retrying a failed rebill
STATE_CANCELLING = 'cancelling'  # Pro until `until`, no renewal coming
STATE_LAPSED = 'lapsed'        # had Pro, period over or ended by refund/chargeback/finish


@dataclass(frozen=True)
class Allowance:
    feature: str
    limit: int
    used: int
    pk: Optional[int] = None

    @property
    def remaining(self):
        return max(self.limit - self.used, 0)


@dataclass(frozen=True)
class Entitlements:
    plan: str
    state: str
    until: Optional[object]
    features: frozenset
    subscription: Optional[Subscription] = None
    # The live trial grant and its allowances by feature; None / {} without one.
    trial: Optional[object] = None
    allowances: dict = field(default_factory=dict)

    @property
    def is_pro(self):
        return self.plan == PLAN_PRO

    def has(self, feature_key):
        """The plan includes the feature."""
        return feature_key in self.features

    def covers(self, feature_key):
        """The feature is in force: by plan, or a live trial includes it, spent or
        not. For honouring a state set earlier -- a survey unbranded under the
        trial stays unbranded until the trial ends, though its one switch-off
        is spent."""
        return feature_key in self.features or feature_key in self.allowances

    def may(self, feature_key):
        """The workspace can make a NEW use of the feature now: by plan, or from a
        live trial's remainder."""
        if feature_key in self.features:
            return True
        allowance = self.allowances.get(feature_key)
        return allowance is not None and allowance.remaining > 0


FREE = Entitlements(PLAN_FREE, STATE_NONE, None, features_for_plan(PLAN_FREE))


def current_subscription(organization):
    if organization is None:
        return None
    return Subscription.objects.current().filter(organization=organization).order_by('-created_at').first()


def live_allowances(organization, now):
    """(live grant, {feature: Allowance}) in one query; (None, {}) without a live grant."""
    rows = list(GrantAllowance.objects.select_related('grant').filter(
        grant__organization=organization, grant__revoked_at__isnull=True,
        grant__starts_at__lte=now, grant__expires_at__gt=now,
    ))
    if not rows:
        return None, {}
    return rows[0].grant, {r.feature: Allowance(r.feature, r.limit, r.used, r.pk) for r in rows}


def for_organization(organization, now=None):
    """Entitlements of an organisation, cached on the instance for the request."""
    if organization is None:
        return FREE
    cached = getattr(organization, '_entitlements', None)
    if cached is not None and now is None:
        return cached
    at = now or timezone.now()
    grant, allowances = live_allowances(organization, at)
    ent = _compute(current_subscription(organization), at, grant, allowances)
    if now is None:
        organization._entitlements = ent
    return ent


def forget(organization):
    """Drop the request-level cache, after a write that changes the answer."""
    if organization is not None and hasattr(organization, '_entitlements'):
        del organization._entitlements


def for_subscription(subscription, now=None):
    return _compute(subscription, now or timezone.now())


def _compute(sub, now, grant=None, allowances=None):
    extra = {'trial': grant, 'allowances': allowances or {}}
    if sub is None:
        return Entitlements(PLAN_FREE, STATE_NONE, None, features_for_plan(PLAN_FREE), **extra) if grant else FREE
    period_end = sub.current_period_end
    honoured = sub.period_honoured and period_end is not None and now < period_end
    if not honoured:
        return Entitlements(PLAN_FREE, STATE_LAPSED, None, features_for_plan(PLAN_FREE), sub, **extra)
    if sub.status == STATUS_ACTIVE:
        state = STATE_ACTIVE
    elif sub.status == STATUS_PAST_DUE:
        state = STATE_PAST_DUE
    else:  # suspended / terminated: paid up, nothing coming
        state = STATE_CANCELLING
    return Entitlements(sub.plan_code, state, period_end, features_for_plan(sub.plan_code), sub, **extra)


def has_feature(organization, feature_key):
    """The organisation's plan includes the feature."""
    return for_organization(organization).has(feature_key)


def may_feature(organization, feature_key):
    """The organisation can use the feature now (plan or live trial remainder)."""
    return for_organization(organization).may(feature_key)
