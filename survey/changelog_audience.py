"""Who a hero changelog entry is for (change changelog-hero, issue #423).

A hero entry names its audience in its header (`show_if: has_surveys,no_mcp_connection`)
and the line under its buttons (`note_if: free_plan`). The names resolve here, to one
callable each, so the condition lives in Python and the loader can refuse a name nobody
defined. Adding a condition is one row in `PREDICATES`; the template never tests anything.

`Audience` memoises each predicate for one request: the context processor asks for the
show conditions and the note condition of the same entry, and the dashboard must not pay
for the same EXISTS twice.
"""


def has_surveys(user, org):
    """The active workspace has at least one survey outside the trash -- the same
    test the dashboard uses to send an empty workspace to the start page."""
    from .models import SurveyHeader
    if org is None:
        return False
    return SurveyHeader.objects.filter(
        organization=org, is_canonical=True, deleted_at__isnull=True,
    ).exists()


def no_mcp_connection(user, org):
    """The creator has no live MCP connection: no unrevoked token profile with the
    `mcp` audience, OAuth grant or personal token alike. The rows
    `agent_views._new_mcp_connection` reads, without the `since`."""
    from api.models import AUDIENCE_MCP, TokenProfile
    return not TokenProfile.objects.filter(
        token__user=user, revoked_at__isnull=True, audiences__contains=[AUDIENCE_MCP],
    ).exists()


def free_plan(user, org):
    """The active workspace's entitlement lacks the API feature (= not on Pro)."""
    from billing.entitlements import for_organization
    if org is None:
        return True
    return not for_organization(org).has('api')


PREDICATES = {
    'has_surveys': has_surveys,
    'no_mcp_connection': no_mcp_connection,
    'free_plan': free_plan,
}


class Audience:
    """The signed-in creator and their active workspace, with each predicate
    computed at most once."""

    def __init__(self, user, org):
        self.user = user
        self.org = org
        self._memo = {}

    def holds(self, name):
        if name not in self._memo:
            self._memo[name] = bool(PREDICATES[name](self.user, self.org))
        return self._memo[name]

    def all(self, names):
        return all(self.holds(name) for name in names)
