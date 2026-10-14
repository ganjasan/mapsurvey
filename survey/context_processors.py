import hashlib
import hmac
import json
from django.conf import settings

from .models import Membership

# Mirrors the settings.py default. Duplicated deliberately: the point is to have a
# value that survives an empty setting, so deriving it from the setting is circular.
POSTHOG_API_HOST_DEFAULT = 'https://eu.i.posthog.com'


def mapbox(request):
    return {
        'MAPBOX_URL': settings.MAPBOX_URL,
        'MAPBOX_OUTDOORS_URL': settings.MAPBOX_OUTDOORS_URL,
        'MAPBOX_ACCESS_TOKEN': settings.MAPBOX_ACCESS_TOKEN,
    }


def contact(request):
    return {
        'CONTACT_EMAIL': getattr(settings, 'CONTACT_EMAIL', ''),
        'CONTACT_TELEGRAM': getattr(settings, 'CONTACT_TELEGRAM', ''),
        'GITHUB_REPO_URL': getattr(settings, 'GITHUB_REPO_URL', ''),
        'DEMO_SURVEY_URL': getattr(settings, 'DEMO_SURVEY_URL', ''),
    }


def survey_start(request):
    """The creator's remembered way to start (change first-survey-onboarding).

    `survey_start_default` drives how the dashboard renders "+ New Survey":
    '' = the start page, 'ai' = the create page, 'blank' = a one-click POST.
    Lazy like `whats_new`: one small query, and only when a template reads it.
    """
    from django.utils.functional import SimpleLazyObject

    def build():
        from .models import CreatorPreferences
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return ''
        row = (CreatorPreferences.objects
               .filter(user=user).values_list('survey_start_default', flat=True)
               .first())
        return row or ''

    return {'survey_start_default': SimpleLazyObject(build)}


def mobile_adaptive(request):
    return {
        'MOBILE_EDITOR_NAV': getattr(settings, 'MOBILE_EDITOR_NAV', False),
        'EDITOR_AUTOSAVE': getattr(settings, 'EDITOR_AUTOSAVE', False),
        'LIVE_SURVEY_EDITING': getattr(settings, 'LIVE_SURVEY_EDITING', False),
        'CREATE_STEER_AI': getattr(settings, 'CREATE_STEER_AI', False),
        'CONDITIONAL_VISIBILITY': getattr(settings, 'CONDITIONAL_VISIBILITY', False),
        'FILE_UPLOAD_QUESTIONS': getattr(settings, 'FILE_UPLOAD_QUESTIONS', False),
        'RESPONSES_V2': getattr(settings, 'RESPONSES_V2', False),
    }


def analytics(request):
    return {
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


def icon_sprites(request):
    """Hashed sprite URLs and the picker catalog URL for the browser-side marker icon resolver.

    Rendered into `data-icon-sprites` on <body> by the base templates, so `MarkerIcon` never
    hard-codes a static path that the manifest storage has renamed.
    """
    from django.templatetags.static import static
    from survey import marker_icons
    return {
        'ICON_SPRITES_JSON': json.dumps(marker_icons.sprite_urls()),
        'ICON_CATALOG_URL': static(marker_icons.CATALOG_STATIC_PATH),
    }


def whats_new(request):
    """In-app changelog state for the editor chrome (change in-app-changelog).

    Lazy on purpose: this processor runs for every template, respondent pages
    included, and only `editor_base.html` reads the value. Nothing is computed
    -- and no query runs -- until a template touches `whats_new`. Anonymous
    users resolve to the empty shape without a query either.
    """
    from django.utils.functional import SimpleLazyObject

    def build():
        from . import changelog
        from .models import CreatorPreferences
        empty = {'latest': None, 'unseen': (), 'unseen_count': 0,
                 'show_card': False, 'cards': True}
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return empty
        # A creator opening their own survey, its password gate or a public
        # results page is on a respondent surface: no changelog chrome there,
        # whichever base template the page happens to extend.
        path = getattr(request, 'path', '') or ''
        if any(path.startswith(prefix) for prefix in changelog.RESPONDENT_PREFIXES):
            return empty
        newest = changelog.latest()
        if newest is None:
            return empty
        prefs = (CreatorPreferences.objects
                 .filter(user=user)
                 .values('changelog_seen', 'changelog_cards')
                 .first()) or {'changelog_seen': '', 'changelog_cards': True}
        unseen = changelog.unseen(prefs['changelog_seen'])
        return {
            'latest': newest,
            'unseen': unseen,
            'unseen_count': len(unseen),
            'show_card': bool(unseen) and prefs['changelog_cards'],
            'cards': prefs['changelog_cards'],
        }

    return {'whats_new': SimpleLazyObject(build)}


def support_chat(request):
    """Chatwoot widget config and, for a signed-in creator, the identity to hand it.

    The identifier is the primary key, not the email -- same reason as
    `_posthog_person`: an edited email would split one creator into two contacts.
    `identifier_hash` is what Chatwoot's identity validation checks; it is computed
    here so the HMAC token never leaves the server. `attributes` is what the agent
    sees next to the conversation (workspace, plan); the page and survey are added
    in the browser, where they are known.
    """
    token = getattr(settings, 'CHATWOOT_WEBSITE_TOKEN', '')
    if not token:
        return {'SUPPORT_CHAT': None}
    user = getattr(request, 'user', None)
    identity = None
    attributes = {}
    if user is not None and user.is_authenticated:
        identifier = str(user.pk)
        identity = {
            'identifier': identifier,
            'email': user.email or '',
            'name': user.get_full_name() or user.get_username(),
        }
        secret = getattr(settings, 'CHATWOOT_HMAC_TOKEN', '')
        if secret:
            identity['identifier_hash'] = hmac.new(
                secret.encode(), identifier.encode(), hashlib.sha256,
            ).hexdigest()
        org = getattr(request, 'active_org', None)
        if org is not None:
            from billing.entitlements import for_organization
            attributes = {'workspace': org.slug, 'plan': for_organization(org).plan}
    # `?support=1` (the help centre's "Still stuck?" link, openspec: help-site) opens
    # the chat on load -- for a signed-in creator only; anonymous visitors are ignored.
    open_on_load = identity is not None and request.GET.get('support') == '1'
    return {
        'SUPPORT_CHAT': {
            'base_url': settings.CHATWOOT_BASE_URL,
            'website_token': token,
            'identity': identity,
            'attributes': attributes,
            'open_on_load': open_on_load,
        },
    }


def help_site(request):
    """Absolute help-centre URLs by registry key (openspec: help-site, #298).

    `HELP_URL.reference_layers` in a template; empty dict when HELP_SITE_URL is unset,
    so `{% if HELP_URL %}` is the switch for every help link at once.
    """
    from .help_links import help_urls
    return {'HELP_URL': help_urls()}
