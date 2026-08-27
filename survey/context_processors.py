from django.conf import settings

from .models import Membership

# Mirrors the settings.py default. Duplicated deliberately: the point is to have a
# value that survives an empty setting, so deriving it from the setting is circular.
POSTHOG_API_HOST_DEFAULT = 'https://eu.i.posthog.com'


def mapbox(request):
    return {
        'MAPBOX_URL': settings.MAPBOX_URL,
        'MAPBOX_ACCESS_TOKEN': settings.MAPBOX_ACCESS_TOKEN,
    }


def contact(request):
    return {
        'CONTACT_EMAIL': getattr(settings, 'CONTACT_EMAIL', ''),
        'CONTACT_TELEGRAM': getattr(settings, 'CONTACT_TELEGRAM', ''),
        'GITHUB_REPO_URL': getattr(settings, 'GITHUB_REPO_URL', ''),
        'DEMO_SURVEY_URL': getattr(settings, 'DEMO_SURVEY_URL', ''),
        'DISCORD_INVITE_URL': getattr(settings, 'DISCORD_INVITE_URL', ''),
    }


def mobile_adaptive(request):
    return {
        'MOBILE_EDITOR_NAV': getattr(settings, 'MOBILE_EDITOR_NAV', False),
        'EDITOR_AUTOSAVE': getattr(settings, 'EDITOR_AUTOSAVE', False),
        'CREATE_STEER_AI': getattr(settings, 'CREATE_STEER_AI', False),
        'CONDITIONAL_VISIBILITY': getattr(settings, 'CONDITIONAL_VISIBILITY', False),
    }


def analytics(request):
    return {
        'PLAUSIBLE_SCRIPT_URL': getattr(settings, 'PLAUSIBLE_SCRIPT_URL', ''),
        # Google Search Console URL-prefix verification (meta-tag method).
        # Empty (default) renders nothing; set the env var to the token GSC shows.
        'GOOGLE_SITE_VERIFICATION': getattr(settings, 'GOOGLE_SITE_VERIFICATION', ''),
        'POSTHOG_PROJECT_KEY': _posthog_key_for(request),
        # The browser gets the client host -- the first-party proxy when one is
        # provisioned, the PostHog host otherwise. The server-side client keeps
        # POSTHOG_API_HOST (survey/apps.py); the two are separate on purpose.
        #
        # The whole chain is resolved here, at request time, rather than in
        # settings.py at import time -- otherwise an override of POSTHOG_API_HOST
        # would move the server and leave the browser on the value frozen at
        # startup. The last link matters because an empty api_host initialises the
        # SDK against nothing, which is indistinguishable from working analytics
        # until someone notices the project has no events.
        'POSTHOG_CLIENT_HOST': (
            getattr(settings, 'POSTHOG_CLIENT_HOST', '')
            or getattr(settings, 'POSTHOG_API_HOST', '')
            or POSTHOG_API_HOST_DEFAULT
        ),
        'POSTHOG_PERSON': _posthog_person(request),
        # Off unless switched on; see settings.py for why it is an environment variable.
        'POSTHOG_SESSION_REPLAY': bool(getattr(settings, 'POSTHOG_SESSION_REPLAY', False)),
    }


def _posthog_key_for(request):
    """The PostHog key, or '' on surfaces that belong to somebody else's audience.

    Returning an empty key rather than a separate template flag reuses the
    "unset means off" shape the other trackers already have, so one `{% if %}`
    in `_analytics.html` covers both "not configured" and "not our page".
    """
    key = getattr(settings, 'POSTHOG_PROJECT_KEY', '')
    if not key:
        return ''
    path = getattr(request, 'path', '') or ''
    excluded = getattr(settings, 'POSTHOG_EXCLUDED_PREFIXES', ())
    if any(path.startswith(prefix) for prefix in excluded):
        return ''
    # Respondent surfaces the prefix test cannot see: the editor's preview iframes serve a real
    # respondent page from under `/editor/`, where we do want tracking on the page around them.
    # `resolver_match` is None before URL resolution (an error page rendered by middleware, say);
    # treat that as not excluded -- tracking a page we meant to track is the recoverable
    # direction, silently losing the editor is not.
    match = getattr(request, 'resolver_match', None)
    excluded_views = getattr(settings, 'POSTHOG_EXCLUDED_VIEW_NAMES', ())
    if match is not None and match.url_name in excluded_views:
        return ''
    return key


def _posthog_person(request):
    """Identify data for a signed-in creator, or None.

    `distinct_id` is the primary key, not the email or username: both of those
    are editable, and re-identifying an existing person under a new id would
    split one creator's history into two.
    """
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return None
    date_joined = getattr(user, 'date_joined', None)
    return {
        'distinct_id': str(user.pk),
        'email': user.email or '',
        'username': user.get_username(),
        'date_joined': date_joined.isoformat() if date_joined else '',
    }


def active_org(request):
    """Inject active organization and user's org list into template context."""
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {}

    org = getattr(request, 'active_org', None)
    memberships = (
        Membership.objects
        .filter(user=request.user)
        .select_related('organization')
        .order_by('joined_at')
    )
    user_orgs = [m.organization for m in memberships]
    org_role = None
    for m in memberships:
        if org and m.organization_id == org.id:
            org_role = m.role
            break

    return {
        'active_org': org,
        'user_orgs': user_orgs,
        'org_role': org_role,
    }
