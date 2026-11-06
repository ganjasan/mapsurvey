"""The application sidebar (change app-sidebar, #538): what it lists and where it shows.

One registry for the creator navigation. Templates render `partials/_app_sidebar.html` from the
`app_nav` context processor and never decide from `request.path` which item is active or
whether the sidebar is there at all.

A new module is one row in MODULES; `test_every_module_resolves` checks its URL name.
"""
from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _

# Paths whose pages are creator surfaces. Everything else — sign-in, registration, the
# respondent pages under /surveys/ (status pages included), /r/, /oauth/ — keeps the
# header it had, whoever is signed in.
APP_NAV_PREFIXES = ('/editor/', '/org/', '/billing/')


@dataclass(frozen=True)
class NavItem:
    key: str
    label: str
    url_name: str
    icon: str
    # The URL takes the active workspace's slug.
    org_scoped: bool = False
    # Shown only to these workspace roles; None = every member.
    roles: tuple = None
    # Query string appended to the URL (no leading "?").
    query: str = ''


MODULES = (
    NavItem('surveys', _('Surveys'), 'editor', 'fas fa-map-marked-alt', query='dashboard=1'),
)

# Two items, not one "API & connections" (owner, 2026-11-06): tokens and connected apps for
# scripts and GIS tools; the guided assistant set-up for MCP clients. Both spend the `api`
# allowance, so both carry its Pro mark. The MCP page needs the editor role (its view says so).
INTEGRATIONS = (
    NavItem('api', _('API'), 'editor_account_connections', 'fas fa-plug'),
    NavItem('mcp', _('MCP'), 'editor_survey_start_agent', 'fas fa-robot', query='from=sidebar',
            roles=('owner', 'admin', 'editor')),
)

WORKSPACE = (
    NavItem('members', _('Members'), 'org_members', 'fas fa-user-friends', org_scoped=True),
    NavItem('billing', _('Plan & billing'), 'org_billing', 'far fa-credit-card', org_scoped=True,
            roles=('owner', 'admin')),
    # "General", not "Settings": the page holds the name, the slug and the plan (owner, 2026-11-06).
    NavItem('settings', _('General'), 'org_settings', 'fas fa-cog', org_scoped=True),
)

# URL name → item key, for the pages that are not "a survey or the survey list".
_ACTIVE_BY_URL_NAME = {
    'editor_account_connections': 'api',
    'editor_survey_start_agent': 'mcp',
    'whats_new': 'whats_new',
    'org_settings': 'settings',
    'org_create': None,
    'editor_account_preferences': None,
    'editor_account_mcp': 'api',
}
_ACTIVE_BY_PREFIX = (
    ('org_members', 'members'),
    ('org_change_role', 'members'),
    ('org_remove_member', 'members'),
    ('org_send_invitation', 'members'),
    ('org_billing', 'billing'),
    ('org_checkout', 'billing'),
)


def shows_sidebar(request):
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return False
    return request.path.startswith(APP_NAV_PREFIXES)


def active_item(request):
    match = getattr(request, 'resolver_match', None)
    name = match.url_name if match else None
    if name in _ACTIVE_BY_URL_NAME:
        return _ACTIVE_BY_URL_NAME[name]
    for prefix, key in _ACTIVE_BY_PREFIX:
        if name and name.startswith(prefix):
            return key
    if request.path.startswith('/editor/'):
        return 'surveys'
    return None


def plan_chip(organization, user=None):
    """'pro' | 'trial' | None for the workspace row: the plan Plan & billing shows."""
    if organization is None:
        return None
    from billing import entitlements, trial
    if entitlements.for_organization(organization).is_pro:
        return 'pro'
    if trial.state_for(organization, user).state == trial.STATE_LIVE:
        return 'trial'
    return None


def items_for(org_role, items=WORKSPACE):
    """The rows of `items` this role sees."""
    return tuple(i for i in items if i.roles is None or org_role in i.roles)
