"""`authenticate(request, audience)`: the only way a token becomes a user.

Order matters and is deliberate -- the cheapest refusals first, and no step
answers differently for "unknown" and "revoked":

1. `Authorization: Bearer <value>`; anything else is anonymous. The session
   cookie is never consulted: an API path that accepted it would be a CSRF
   target from any site (the cookie is `SameSite=None` for embedding).
2. The per-IP failed-attempt budget, consulted before touching the database.
3. The value looks like one of ours (prefix, length) -- else a failure, no query.
4. One lookup by checksum with the user and profile joined.
5. Expiry, revocation, audience.
6. `email_verification.can_sign_in(user)`: a ban (`confirm_phishing` sets
   `is_active` False) or an address still unconfirmed after the sign-in grace
   period (change login-grace-period) ends API access on the next call.
7. `last_used_at`, at most once a minute.

Every refusal in 3-6 is the same `401 invalid_token` and counts as one failed
attempt for the IP.
"""
from dataclasses import dataclass

from survey.email_verification import can_sign_in
from datetime import timedelta

from django.utils import timezone
from oauth2_provider.models import AccessToken

from survey import product_events as pe
from survey.abuse import client_ip

from . import limits, tokens
from .errors import ApiError, invalid_token

LAST_USED_INTERVAL = timedelta(seconds=60)


@dataclass(frozen=True)
class Principal:
    user: object
    scopes: frozenset
    organization: object  # Organization or None (token bound to one workspace)
    token_id: int
    kind: str
    profile: object

    def has_scope(self, scope):
        return scope in self.scopes


def bearer_value(request):
    header = request.META.get('HTTP_AUTHORIZATION', '')
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        return None
    return parts[1].strip()


def _refuse(request):
    limits.auth_failure(client_ip(request) or '')
    raise invalid_token()


def authenticate(request, audience):
    """Return a Principal for a valid bearer, None for no bearer at all, and
    raise ApiError(401) for a bearer that is present but not valid (429 when
    the IP has exhausted its failed attempts)."""
    value = bearer_value(request)
    if value is None:
        return None

    exceeded, time_left = limits.auth_failures_exceeded(client_ip(request) or '')
    if exceeded:
        err = ApiError(429, 'rate_limited', 'Too many failed authentication attempts.',
                       limit='api.auth_fail', retry_after=time_left)
        err.headers['Retry-After'] = str(time_left)
        raise err

    if not tokens.looks_like_token(value):
        _refuse(request)

    token = (
        AccessToken.objects
        .filter(token_checksum=tokens.checksum(value))
        .select_related('user', 'profile', 'profile__organization')
        .first()
    )
    if token is None or token.user_id is None or not hasattr(token, 'profile'):
        _refuse(request)
    profile = token.profile
    now = timezone.now()
    if token.expires is None or token.expires <= now or profile.revoked_at is not None:
        _refuse(request)
    if audience not in (profile.audiences or []):
        _refuse(request)
    if not can_sign_in(token.user):
        _refuse(request)

    _touch(profile, token.user_id, now)
    return Principal(
        user=token.user,
        scopes=frozenset(token.scope.split()),
        organization=profile.organization,
        token_id=token.pk,
        kind=profile.kind,
        profile=profile,
    )


def _touch(profile, user_id, now):
    first_use = profile.last_used_at is None
    if first_use or profile.last_used_at < now - LAST_USED_INTERVAL:
        profile.last_used_at = now
        profile.save(update_fields=['last_used_at'])
        if first_use:
            pe.emit(pe.API_TOKEN_FIRST_USE, user_id, {'kind': profile.kind, 'token_id': profile.token_id})
