"""Connected apps: what a creator sees and disconnects (change oauth-server, D9).

A "connected app" is an `Application` for which the user holds an unrevoked
refresh token or a live access token. The connections page shows one row per
application, not per token: rotation makes tokens, the creator made one
decision.
"""
from urllib.parse import urlsplit

from django.db.models import Max, Min
from django.utils import timezone
from oauth2_provider.models import AccessToken, RefreshToken

from .. import tokens as token_store
from ..models import KIND_OAUTH, TokenProfile
from .redirects import is_loopback


def client_host(application):
    """The host the consent page and the row name: the CIMD `client_id` URL's
    host, else the first registered redirect URI's host."""
    if application.client_id.startswith('https://'):
        return urlsplit(application.client_id).hostname or ''
    first = (application.redirect_uris or '').split()
    if first:
        p = urlsplit(first[0])
        host = p.hostname or ''
        return f'{host} (this computer)' if is_loopback(first[0]) else host
    return ''


def display_name(application):
    return (application.name or '').strip()[:60] or client_host(application) or application.client_id[:60]


def _live_access_tokens(user):
    return (
        AccessToken.objects
        .filter(user=user, profile__kind=KIND_OAUTH, profile__revoked_at__isnull=True,
                expires__gt=timezone.now(), application__isnull=False)
    )


def connected_applications(user):
    """Application ids the user is connected to."""
    ids = set(RefreshToken.objects.filter(user=user, revoked__isnull=True, application__isnull=False)
              .values_list('application_id', flat=True))
    ids |= set(_live_access_tokens(user).values_list('application_id', flat=True))
    return ids


def connected_apps(user):
    """Rows for the page, newest connection first."""
    from oauth2_provider.models import Application
    ids = connected_applications(user)
    if not ids:
        return []
    rows = []
    for app in Application.objects.filter(pk__in=ids):
        profiles = TokenProfile.objects.filter(token__user=user, token__application=app, kind=KIND_OAUTH)
        agg = profiles.aggregate(first=Min('created_at'), used=Max('last_used_at'))
        newest = (profiles.filter(revoked_at__isnull=True, token__expires__gt=timezone.now())
                  .select_related('token').order_by('-created_at').first())
        rows.append({
            'application': app,
            'name': display_name(app),
            'host': client_host(app),
            'scopes': newest.token.scope.split() if newest else [],
            'audiences': list(newest.audiences) if newest else [],
            'created': agg['first'],
            'last_used': agg['used'],
        })
    rows.sort(key=lambda r: r['created'] or timezone.now(), reverse=True)
    return rows


def disconnect(user, application):
    """Revoke every refresh token (the toolkit revokes their access tokens) and
    flag the access tokens that remain. Returns the scopes that were held."""
    scopes = set()
    for rt in RefreshToken.objects.filter(user=user, application=application, revoked__isnull=True):
        if rt.access_token_id:
            scopes.update(rt.access_token.scope.split())
        rt.revoke()
    for profile in TokenProfile.objects.filter(token__user=user, token__application=application,
                                               kind=KIND_OAUTH, revoked_at__isnull=True).select_related('token'):
        scopes.update(profile.token.scope.split())
        token_store.revoke(profile)
    return sorted(scopes)
