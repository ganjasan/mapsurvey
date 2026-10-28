"""The Pro trial: counted uses of each Pro feature for TRIAL_DAYS after the
owner's click (change pro-trial-allowances, #471).

Three operations and one question:
- `claim(org, user)`: the owner's "Try Pro". One trial per workspace, one per
  person whichever workspace they claim it for, never on a Pro workspace.
- `consume(org, feature, actor)`: count one use the plan does not cover. One
  atomic UPDATE guarded by `used < limit`, so the gate and the count cannot
  drift apart under concurrent API calls.
- `refusal(org)`: why a refused use was refused ("exhausted" / "expired" /
  "none"), for the API envelope.
- `state_for(org, user)`: where the trial stands for the person looking, for
  Plan & billing, the refusal page and the help page.

Nothing here writes `Subscription`, sends mail, or runs on a schedule.
"""
import math
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from django.db import IntegrityError, connection, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from . import entitlements as ents
from . import events as ev
from .features import FEATURES, TRIAL_ALLOWANCES, TRIAL_DAYS
from .models import GRANT_KIND_TRIAL, EntitlementGrant, GrantAllowance

STATE_NONE = 'none'                  # Pro workspace, or the trial is not offered
STATE_AVAILABLE = 'available'        # can be claimed here
STATE_LIVE = 'live'                  # claimed, at least one feature left
STATE_EXHAUSTED = 'exhausted'        # claimed, every allowance used
STATE_EXPIRED = 'expired'            # past expires_at, or revoked
STATE_USED_ELSEWHERE = 'used_elsewhere'  # the viewer claimed theirs in another workspace

# What one unit of each allowance is, for "used N of M" rows and the offer.
UNIT_LABELS = {
    'api': _('API and MCP calls'),
    'unbranded': _('Surveys without the Mapsurvey badge'),
    'pro_help': _('Requests to the Mapsurvey team'),
}


# What one unit buys, where the label alone does not say it.
UNIT_DETAILS = {
    'api': _('Your own scripts through the REST API, or Claude and ChatGPT through the MCP server.'),
    'unbranded': _('The survey, its thank-you page and its public results with no link back to Mapsurvey.'),
    'pro_help': _('A check-up of your survey before launch, advice on getting it to respondents, '
                  'or a report when the survey closes.'),
}


def unit_detail(feature_key):
    return UNIT_DETAILS.get(feature_key, '')


def unit_label(feature_key):
    if feature_key in UNIT_LABELS:
        return UNIT_LABELS[feature_key]
    f = FEATURES.get(feature_key)
    return f.label if f else feature_key


REFUSED_NOT_OFFERED = 'not_offered'
REFUSED_PRO = 'pro'
REFUSED_ORG_USED = 'org_used'
REFUSED_USER_USED = 'user_used'


class TrialRefused(Exception):
    def __init__(self, reason, other=None):
        super().__init__(reason)
        self.reason = reason
        self.other = other  # the workspace where the user already claimed one


def offered():
    """True when new trials are given out: some registry feature has an allowance."""
    return any(key in FEATURES for key in TRIAL_ALLOWANCES)


def trial_grant(organization):
    """The organisation's trial grant, live or not."""
    return EntitlementGrant.objects.filter(organization=organization, kind=GRANT_KIND_TRIAL).first()


def users_trial(user):
    if user is None or not user.is_authenticated:
        return None
    return (EntitlementGrant.objects.select_related('organization')
            .filter(claimed_by=user, kind=GRANT_KIND_TRIAL).first())


def claim(organization, user, now=None):
    """Create the trial grant and its allowances, or raise TrialRefused.
    Role checks belong to the view; this enforces the rules of the trial."""
    now = now or timezone.now()
    if not offered():
        raise TrialRefused(REFUSED_NOT_OFFERED)
    if ents.for_organization(organization).is_pro:
        raise TrialRefused(REFUSED_PRO)
    if trial_grant(organization) is not None:
        raise TrialRefused(REFUSED_ORG_USED)
    mine = users_trial(user)
    if mine is not None:
        raise TrialRefused(REFUSED_USER_USED, other=mine.organization)
    try:
        with transaction.atomic():
            grant = EntitlementGrant.objects.create(
                organization=organization, kind=GRANT_KIND_TRIAL, claimed_by=user,
                starts_at=now, expires_at=now + timedelta(days=TRIAL_DAYS),
            )
            GrantAllowance.objects.bulk_create([
                GrantAllowance(grant=grant, feature=key, limit=limit)
                for key, limit in TRIAL_ALLOWANCES.items() if key in FEATURES
            ])
    except IntegrityError:
        # A double click or a parallel claim lost the race to the constraint.
        raise TrialRefused(REFUSED_ORG_USED)
    ents.forget(organization)
    ev.emit(ev.TRIAL_CLAIMED, user.pk, {'org_id': organization.pk})
    return grant


def consume(organization, feature, actor=None):
    """Count one use of `feature` the plan does not cover. True when the use is
    allowed (the plan includes it, or a call was left), False when not."""
    ent = ents.for_organization(organization)
    if ent.has(feature):
        return True
    allowance = ent.allowances.get(feature)
    if allowance is None or allowance.pk is None:
        return False
    table = GrantAllowance._meta.db_table
    # One statement on one row: Postgres re-checks `used < "limit"` on the row
    # version it locks, so two requests racing for the last use cannot both win.
    with connection.cursor() as cursor:
        cursor.execute(
            f'UPDATE {table} SET used = used + 1 WHERE id = %s AND used < "limit" RETURNING used, "limit"',
            [allowance.pk],
        )
        row = cursor.fetchone()
    ents.forget(organization)
    if row is None:
        return False
    used, limit = row
    if used == limit:
        user_id = getattr(actor, 'pk', None)
        ev.emit(ev.TRIAL_EXHAUSTED, user_id, {'org_id': organization.pk, 'feature': feature})
    return True


def refusal(organization, now=None):
    """Why the organisation's trial did not cover a use: "exhausted" (live, this
    feature spent), "expired" (ended or revoked) or "none" (never claimed)."""
    grant = trial_grant(organization)
    if grant is None:
        return STATE_NONE
    return STATE_EXHAUSTED if grant.is_live(now) else STATE_EXPIRED


@dataclass
class TrialState:
    state: str
    grant: Optional[EntitlementGrant] = None
    allowances: list = field(default_factory=list)   # [Allowance] in registry order
    other_organization: Optional[object] = None      # for used_elsewhere

    def feature_exhausted(self, feature_key):
        """The trial is live but this feature's allowance is spent."""
        if self.state not in (STATE_LIVE, STATE_EXHAUSTED):
            return False
        for a in self.allowances:
            if a.feature == feature_key:
                return a.remaining == 0
        return False

    @property
    def offer(self):
        """What a new trial contains: [(unit label, limit, detail)] in registry order."""
        return [(unit_label(k), limit, unit_detail(k)) for k, limit in TRIAL_ALLOWANCES.items() if k in FEATURES]

    @property
    def rows(self):
        """A claimed trial, per feature: [(unit label, used, limit)]."""
        return [(unit_label(a.feature), a.used, a.limit) for a in self.allowances]

    @property
    def meters(self):
        """A claimed trial, per feature, for the Plan & billing tiles."""
        return [{'label': unit_label(a.feature), 'detail': unit_detail(a.feature),
                 'used': a.used, 'limit': a.limit, 'remaining': a.remaining,
                 'pct': min(100, round(100 * a.used / a.limit)) if a.limit else 100}
                for a in self.allowances]

    @property
    def days_left(self):
        if self.grant is None:
            return 0
        seconds = (self.grant.expires_at - timezone.now()).total_seconds()
        return max(0, math.ceil(seconds / 86400))   # a trial started today reads "90 days left"

    @property
    def days(self):
        return TRIAL_DAYS


def state_for(organization, user=None, now=None):
    """Where the trial stands for `user` looking at `organization`."""
    now = now or timezone.now()
    if ents.for_organization(organization).is_pro:
        return TrialState(STATE_NONE)
    grant = trial_grant(organization)
    if grant is not None:
        rows = {a.feature: a for a in grant.allowances.all()}
        # The offer's order (TRIAL_ALLOWANCES), then anything a grant holds beyond it.
        order = list(TRIAL_ALLOWANCES) + [k for k in FEATURES if k not in TRIAL_ALLOWANCES]
        allowances = [ents.Allowance(a.feature, a.limit, a.used, a.pk)
                      for key in order if (a := rows.get(key)) is not None]
        if not grant.is_live(now):
            return TrialState(STATE_EXPIRED, grant, allowances)
        if allowances and all(a.remaining == 0 for a in allowances):
            return TrialState(STATE_EXHAUSTED, grant, allowances)
        return TrialState(STATE_LIVE, grant, allowances)
    mine = users_trial(user)
    if mine is not None:
        return TrialState(STATE_USED_ELSEWHERE, mine, other_organization=mine.organization)
    if offered():
        return TrialState(STATE_AVAILABLE)
    return TrialState(STATE_NONE)
