"""The Pro gate for programmatic access.

Checked at the resource, per request, on the organisation that OWNS the object
(`survey.organization`) -- never on the token's user and never at minting.
That is what makes the plan rule the same one `unbranded` follows: a Free
collaborator on a Pro workspace's survey is covered (that workspace paid), a
Pro user on a Free workspace's survey is not. A lapsed subscription stops
access on the next call without touching a single token; renewal brings the
same token back.
"""
from django.conf import settings
from django.urls import reverse

from billing.entitlements import for_organization
from billing.trial import may as trial_may
from survey.models import Membership

from .errors import PRO_REQUIRED, ApiError

FEATURE = 'api'


def upgrade_url(organization):
    return settings.SITE_URL.rstrip('/') + reverse('org_billing', args=[organization.slug])


_TRIAL_DETAIL = {
    'none': 'The API is a Pro feature; this workspace is on the Free plan.',
    'exhausted': "The API is a Pro feature; this workspace's Pro trial has used all its API calls.",
    'expired': "The API is a Pro feature; this workspace's Pro trial has ended.",
}


def require_pro_api(principal, organization):
    """Pass when `organization`'s plan includes `api`; otherwise count the call
    against its live Pro trial (change pro-trial-allowances) -- or start the
    trial with it when the workspace never had one (change pro-trial-auto) --
    and pass when one was left; else raise 403 pro_required naming the trial's
    state."""
    from billing import trial

    if organization is not None:
        if for_organization(organization).has(FEATURE):
            return
        # One request (or MCP tool call) is one use, however many objects of the
        # same workspace it touches. A Principal is built per request; it is a
        # frozen dataclass, so the memo goes into its __dict__ directly.
        counted = principal.__dict__.setdefault('_trial_counted', set()) if principal is not None else set()
        if organization.pk in counted:
            return
        if trial.use(organization, FEATURE, actor=getattr(principal, 'user', None)):
            counted.add(organization.pk)
            return
    state = trial.refusal(organization) if organization is not None else 'none'
    raise ApiError(
        403, PRO_REQUIRED, _TRIAL_DETAIL[state],
        organization=getattr(organization, 'slug', None),
        upgrade_url=upgrade_url(organization) if organization is not None else None,
        trial=state,
    )


def pro_organizations(principal):
    """(organisations of the principal that hold `api`, count of those that do not).
    Honours a token bound to one workspace."""
    memberships = Membership.objects.filter(user=principal.user).select_related('organization')
    if principal.organization is not None:
        memberships = memberships.filter(organization=principal.organization)
    allowed, hidden = [], 0
    for m in memberships:
        if trial_may(m.organization, FEATURE):
            allowed.append(m.organization)
        else:
            hidden += 1
    return allowed, hidden
