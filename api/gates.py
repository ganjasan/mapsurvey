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
from survey.models import Membership

from .errors import PRO_REQUIRED, ApiError

FEATURE = 'api'


def upgrade_url(organization):
    return settings.SITE_URL.rstrip('/') + reverse('org_billing', args=[organization.slug])


def require_pro_api(principal, organization):
    """Raise 403 pro_required unless `organization` holds the `api` feature."""
    if organization is None or not for_organization(organization).has(FEATURE):
        raise ApiError(
            403, PRO_REQUIRED,
            'The API is a Pro feature; this workspace is on the Free plan.',
            organization=getattr(organization, 'slug', None),
            upgrade_url=upgrade_url(organization) if organization is not None else None,
        )


def pro_organizations(principal):
    """(organisations of the principal that hold `api`, count of those that do not).
    Honours a token bound to one workspace."""
    memberships = Membership.objects.filter(user=principal.user).select_related('organization')
    if principal.organization is not None:
        memberships = memberships.filter(organization=principal.organization)
    allowed, hidden = [], 0
    for m in memberships:
        if for_organization(m.organization).has(FEATURE):
            allowed.append(m.organization)
        else:
            hidden += 1
    return allowed, hidden
