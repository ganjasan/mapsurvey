"""The Pro trial: counted uses of each Pro feature for TRIAL_DAYS after it
starts (change pro-trial-allowances, #471).

It starts in one of two ways: the owner's "Try Pro" click, or -- since change
pro-trial-auto (#508) -- the first Pro use any member makes in a workspace that
has never had a trial, on behalf of an owner who has not used theirs.

The operations and questions:
- `claim(org, user)`: the owner's "Try Pro". One trial per workspace, one per
  person whichever workspace they claim it for, never on a Pro workspace.
- `may(org, feature)`: can a NEW use be offered -- by plan, from a live
  trial, or because the use would start the trial. Every control that offers
  a use asks this; `Entitlements.may` alone does not know about starting.
- `use(org, feature, actor)`: make the use -- start the trial when it can,
  then count. Every point of use calls this, never `consume` directly.
- `consume(org, feature, actor)`: count one use the plan does not cover. One
  atomic UPDATE guarded by `used < limit` (or an uncapped limit), so the gate
  and the count cannot drift apart under concurrent API calls.
- `refusal(org)`: why a refused use was refused ("exhausted" / "expired" /
  "none"), for the API envelope.
- `state_for(org, user)`: where the trial stands for the person looking, for
  Plan & billing, the refusal page and the help page.

Nothing here writes `Subscription` or runs on a schedule; the start mail is
enqueued on commit (billing.tasks).
"""
import logging
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

logger = logging.getLogger(__name__)

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
    'operator_entry': _('Paper responses entered'),
}


# What one unit buys, where the label alone does not say it.
UNIT_DETAILS = {
    'api': _('Your own scripts through the REST API, or Claude and ChatGPT through the MCP server.'),
    'unbranded': _('The survey, its thank-you page and its public results with no link back to Mapsurvey.'),
    'pro_help': _('A check-up of your survey before launch, advice on getting it to respondents, '
                  'or a report when the survey closes.'),
    'operator_entry': _('Type in answers from paper sheets, interviews and field work. No limit during the trial.'),
}


# How a first use started the trial, for "X started it …" on Plan & billing.
STARTED_HOW = {
    'unbranded': _('by removing the Mapsurvey badge from a survey'),
    'pro_help': _('by sending a request to the Mapsurvey team'),
    'api': _('with a call to the API or the MCP server'),
    'operator_entry': _('by entering a paper response'),
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
        grant = _create_grant(organization, user, user, TRIGGER_CLICK, now)
    except IntegrityError:
        # A double click or a parallel claim lost the race to the constraint.
        raise TrialRefused(REFUSED_ORG_USED)
    return grant


TRIGGER_CLICK = 'click'


def _create_grant(organization, owner, started_by, trigger, now):
    """The grant and its allowances, in a savepoint so a lost race (IntegrityError
    on the per-workspace or per-owner constraint) leaves the caller's
    transaction usable. The event goes out at once, as the click's always did;
    the owner's mail waits for the commit, so a use whose save is rolled back
    afterwards sends nothing."""
    with transaction.atomic():
        grant = EntitlementGrant.objects.create(
            organization=organization, kind=GRANT_KIND_TRIAL, claimed_by=owner,
            started_by=started_by, trigger=trigger,
            starts_at=now, expires_at=now + timedelta(days=TRIAL_DAYS),
        )
        GrantAllowance.objects.bulk_create([
            GrantAllowance(grant=grant, feature=key, limit=limit)
            for key, limit in TRIAL_ALLOWANCES.items() if key in FEATURES
        ])
    ents.forget(organization)
    _forget_startable(organization)
    actor_id = getattr(started_by, 'pk', None) or getattr(owner, 'pk', None)
    ev.emit(ev.TRIAL_CLAIMED, actor_id, {
        'org_id': organization.pk, 'trigger': trigger, 'auto': trigger != TRIGGER_CLICK,
        'started_by_owner': started_by is not None and owner is not None and started_by.pk == owner.pk,
    })

    def send_start_mail():
        from .tasks import send_trial_started
        try:
            send_trial_started.delay(grant.pk)
        except Exception:  # noqa: BLE001 -- a broker outage must not fail the use that started it
            logger.exception('trial %s: start mail not enqueued', grant.pk)

    transaction.on_commit(send_start_mail)
    return grant


def trial_owner(organization):
    """The owner a new trial of this workspace would belong to: the owner who
    joined first among those who hold no trial anywhere, or None."""
    from survey.models import Membership

    used = EntitlementGrant.objects.filter(kind=GRANT_KIND_TRIAL, claimed_by__isnull=False).values('claimed_by')
    m = (Membership.objects.select_related('user')
         .filter(organization=organization, role='owner', user__is_active=True)
         .exclude(user__in=used).order_by('joined_at', 'pk').first())
    return m.user if m is not None else None


def _forget_startable(organization):
    if organization is not None and hasattr(organization, '_trial_startable'):
        del organization._trial_startable


def startable(organization, feature_key):
    """The first use of `feature_key` here would start the trial: it is offered
    and includes the feature, the workspace is not Pro, has never had a trial,
    and has an owner who has not used theirs. Cached on the instance for the
    request (cleared with `ents.forget` callers through `_create_grant`)."""
    if organization is None or feature_key not in TRIAL_ALLOWANCES or feature_key not in FEATURES:
        return False
    cached = getattr(organization, '_trial_startable', None)
    if cached is None:
        cached = (offered() and not ents.for_organization(organization).is_pro
                  and trial_grant(organization) is None and trial_owner(organization) is not None)
        organization._trial_startable = cached
    return cached


def may(organization, feature_key):
    """A NEW use can be offered: by plan, from a live trial's remainder, or
    because it would start the trial. Decides every control that offers a use."""
    if ents.for_organization(organization).may(feature_key):
        return True
    return startable(organization, feature_key)


def use(organization, feature, actor=None, now=None):
    """Make one use of `feature`: True without counting when the plan includes
    it; else start the trial if it can start, then count one use against it.
    False when neither the plan nor a trial allows it. The grant a use started
    is left on `organization._trial_started` for the view's one-time notice."""
    ent = ents.for_organization(organization)
    if ent.has(feature):
        return True
    if not ent.may(feature) and startable(organization, feature):
        owner = trial_owner(organization)
        started = None
        if owner is not None:
            try:
                started = _create_grant(organization, owner, actor if getattr(actor, 'pk', None) else None,
                                        feature, now or timezone.now())
            except IntegrityError:
                pass
        if started is None:
            # Another request started it first (or took the owner's trial
            # elsewhere) since this request looked: count against what is there now.
            ents.forget(organization)
            _forget_startable(organization)
        organization._trial_started = started
    return consume(organization, feature, actor=actor)


def started_here(organization):
    """The grant `use` started on this instance during the request, or None."""
    return getattr(organization, '_trial_started', None)


def flash_started(request, organization):
    """The one-time notice for the person whose use just started the trial:
    rendered on their next page by the messages block of the base templates."""
    grant = started_here(organization)
    if grant is None or request is None:
        return
    from django.contrib import messages
    from django.utils.formats import date_format

    parts = []
    for a in grant.allowances.all():
        label = unit_label(a.feature)
        parts.append(f'{label}: {a.limit}' if a.limit is not None else f'{label}: {_("no limit")}')
    if grant.started_by_id is not None and grant.started_by_id == grant.claimed_by_id:
        mail = _('We sent you an e-mail with the details.')
    else:
        mail = _('The workspace owner got an e-mail about it.')
    messages.info(request, _('You started the free Pro trial of %(org)s. Until %(date)s it includes %(what)s.') % {
        'org': organization.name, 'date': date_format(grant.expires_at, 'j F Y'), 'what': '; '.join(parts)}
        + ' ' + str(mail))
    organization._trial_started = None


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
            f'UPDATE {table} SET used = used + 1 '
            f'WHERE id = %s AND ("limit" IS NULL OR used < "limit") RETURNING used, "limit"',
            [allowance.pk],
        )
        row = cursor.fetchone()
    ents.forget(organization)
    if row is None:
        return False
    used, limit = row
    if limit is not None and used == limit:
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
        return [(unit_label(k), limit if limit is not None else _('No limit'), unit_detail(k))
                for k, limit in TRIAL_ALLOWANCES.items() if k in FEATURES]

    @property
    def rows(self):
        """A claimed trial, per feature: [(unit label, used, limit)]."""
        return [(unit_label(a.feature), a.used, a.limit) for a in self.allowances]

    @property
    def meters(self):
        """A claimed trial, per feature, for the Plan & billing tiles."""
        return [{'label': unit_label(a.feature), 'detail': unit_detail(a.feature),
                 'used': a.used, 'limit': a.limit, 'remaining': a.remaining, 'capped': a.capped,
                 'pct': (min(100, round(100 * a.used / a.limit)) if a.limit else 100) if a.capped else 0}
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

    @property
    def started_how(self):
        """"Started by <name> by removing the badge." -- for a trial a first use
        started (change pro-trial-auto); '' for a click or an unknown person."""
        g = self.grant
        if g is None or g.trigger == TRIGGER_CLICK or g.started_by is None:
            return ''
        how = STARTED_HOW.get(g.trigger)
        if how is None:
            return ''
        name = g.started_by.get_full_name() or g.started_by.get_username()
        return _('%(name)s started it %(how)s.') % {'name': name, 'how': how}


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
        capped = [a for a in allowances if a.capped]
        # An uncapped allowance never runs out, so it never makes the trial "used up".
        if capped and len(capped) == len(allowances) and all(a.remaining == 0 for a in capped):
            return TrialState(STATE_EXHAUSTED, grant, allowances)
        return TrialState(STATE_LIVE, grant, allowances)
    # A trial belongs to an owner: the workspace can start one while some owner
    # has not used theirs, whoever is looking (change pro-trial-auto).
    if offered() and trial_owner(organization) is not None:
        return TrialState(STATE_AVAILABLE)
    mine = users_trial(user)
    if mine is not None:
        return TrialState(STATE_USED_ELSEWHERE, mine, other_organization=mine.organization)
    return TrialState(STATE_NONE)
