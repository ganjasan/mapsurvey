"""The bearer check every v1 route runs before its body is parsed.

`Bearer(*scopes)` is a django-ninja auth callable over the authorization
layer: `api.auth.authenticate` (personal and OAuth tokens, audiences,
revocation, the per-IP failed-bearer budget, `last_used_at`, the
`api_token_first_use` event), then the route's scopes, then the per-token
rate windows. It subclasses `HttpBearer` only so the OpenAPI document carries
a bearer security scheme; the header is read by `authenticate` itself.
"""
from ninja.security import HttpBearer

from .. import limits, rights
from ..auth import authenticate
from ..errors import invalid_token
from ..models import AUDIENCE_API


class Bearer(HttpBearer):
    def __init__(self, *scopes):
        super().__init__()
        self.scopes = scopes

    def __call__(self, request):
        principal = authenticate(request, AUDIENCE_API)
        if principal is None:
            raise invalid_token()
        request.principal = principal
        for scope in self.scopes:
            rights.require_scope(principal, scope)
        limits.check_request(principal, request.method)
        return principal

    def authenticate(self, request, token):  # pragma: no cover -- __call__ replaces it
        return None
