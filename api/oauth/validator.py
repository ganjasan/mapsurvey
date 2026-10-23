"""The one `OAuth2Validator` subclass (change oauth-server, D4).

Four hooks into the toolkit, each a few lines:

- `validate_redirect_uri`   the loopback rule (`redirects.matches`)
- `_create_access_token`    a `TokenProfile(kind="oauth")` beside every token,
                            so `authenticate()`, rights, the Pro gate and the
                            limits apply to an OAuth token exactly as to a
                            personal one; audiences from `resource`
- `validate_code`           RFC 6749 §4.1.2: a code redeemed twice revokes
                            everything it produced (the toolkit only answers
                            `invalid_grant`)
- `_check_and_set_request_resource` / `validate_refresh_token`
                            unknown resource -> `invalid_target`; inactive
                            user -> no refresh; the code checksum follows the
                            family across rotations
"""
import hashlib

from oauth2_provider.models import RefreshToken
from oauth2_provider.oauth2_validators import OAuth2Validator

from .. import tokens as token_store
from ..models import KIND_OAUTH, TokenProfile
from . import audiences, redirects


def code_checksum(code):
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def revoke_by_code(checksum, application):
    """Revoke every token that descends from an authorization code: the refresh
    families through the toolkit (deletes their access tokens) and whatever
    access tokens remain through the profile flag `authenticate()` reads."""
    profiles = TokenProfile.objects.filter(code_checksum=checksum, token__application=application)
    families = set(
        RefreshToken.objects.filter(access_token__profile__in=profiles, revoked__isnull=True)
        .values_list('token_family', flat=True)
    )
    for family in families:
        RefreshToken.revoke_family(family)
    for profile in profiles:
        token_store.revoke(profile)


class MapsurveyOAuth2Validator(OAuth2Validator):

    def validate_redirect_uri(self, client_id, redirect_uri, request, *args, **kwargs):
        registered = (request.client.redirect_uris or '').split()
        return redirects.matches(redirect_uri, registered)

    def validate_code(self, client_id, code, client, request, *args, **kwargs):
        ok = super().validate_code(client_id, code, client, request, *args, **kwargs)
        if not ok:
            # Gone or expired. If tokens were ever issued from this code, the
            # second redemption is an attacker with a stolen code (or a stolen
            # verifier): end the whole lineage. One indexed query otherwise.
            revoke_by_code(code_checksum(code), client)
            return False
        # The toolkit checks `resource` against the grant while SAVING the
        # token, outside oauthlib's error handling, so a mismatch comes back as
        # a JSON body with no JSON content type. Checked here, inside
        # validate_token_request, it is an ordinary 400 invalid_target.
        self._check_and_set_request_resource(request)
        return True

    def validate_refresh_token(self, refresh_token, client, request, *args, **kwargs):
        ok = super().validate_refresh_token(refresh_token, client, request, *args, **kwargs)
        if not ok:
            return False
        if request.user is not None and not request.user.is_active:
            return False
        # The source access token (and its profile) is revoked -- deleted --
        # before the new pair is minted; keep the lineage while it is readable.
        rt = getattr(request, 'refresh_token_instance', None)
        at = getattr(rt, 'access_token', None)
        profile = getattr(at, 'profile', None) if at is not None else None
        request._ms_code_checksum = getattr(profile, 'code_checksum', None)
        self._check_and_set_request_resource(request)  # see validate_code
        return True

    def _check_and_set_request_resource(self, request):
        super()._check_and_set_request_resource(request)
        try:
            audiences.for_resources(getattr(request, 'resource', []) or [])
        except audiences.UnknownResource as exc:
            raise audiences.invalid_target(exc.resource, request=request)

    def _create_access_token(self, expires, request, token, source_refresh_token=None):
        access_token = super()._create_access_token(expires, request, token, source_refresh_token)
        application = request.client
        if request.grant_type == 'authorization_code' and getattr(request, 'code', None):
            checksum = code_checksum(request.code)
        else:
            checksum = getattr(request, '_ms_code_checksum', None)
        TokenProfile.objects.create(
            token=access_token,
            kind=KIND_OAUTH,
            label=(application.name or application.client_id)[:80],
            suffix=token['access_token'][-4:],
            audiences=audiences.for_resources(access_token.resource or []),
            organization=None,
            code_checksum=checksum,
        )
        return access_token
