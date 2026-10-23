"""Response headers every `/oauth/` response carries (change oauth-server, D7).

One place rather than a decorator per view: the toolkit's views, ours, and
whatever #306 mounts under the prefix all get the same four headers. The
consent page is the one that matters -- a framed consent page is a
clickjacking target -- and `SurveyEmbedMiddleware` drops `X-Frame-Options`
only on responses `check_survey_access` marked, which it never does here.
"""

OAUTH_PREFIX = '/oauth/'


class OAuthResponseHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(OAUTH_PREFIX):
            response['Cache-Control'] = 'no-store'
            response['Pragma'] = 'no-cache'
            response['X-Frame-Options'] = 'DENY'
            if not response.has_header('Content-Security-Policy'):
                response['Content-Security-Policy'] = "frame-ancestors 'none'"
        return response


API_PREFIX = '/api/'
V1_PREFIX = '/api/v1/'
CORS_ALLOW_METHODS = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
CORS_ALLOW_HEADERS = 'Authorization, Content-Type'
CORS_MAX_AGE = '86400'


class ApiResponseHeadersMiddleware:
    """CORS and caching for every `/api/` response (change rest-api-v1, D6).

    The API authenticates with a bearer header only, never a cookie, so any
    origin may call it: `Access-Control-Allow-Origin: *` and NEVER
    `Allow-Credentials` -- a browser on another site then cannot ride a
    signed-in creator's session, because there is nothing to ride. A
    preflight is answered here, before authentication (browsers send no
    Authorization header on it). Every answer is `no-store`, including the
    ones the framework produces itself (405, unknown routes).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(API_PREFIX):
            return self.get_response(request)
        if request.method == 'OPTIONS' and 'HTTP_ACCESS_CONTROL_REQUEST_METHOD' in request.META:
            from django.http import HttpResponse
            response = HttpResponse(status=204)
            response['Access-Control-Allow-Methods'] = CORS_ALLOW_METHODS
            response['Access-Control-Allow-Headers'] = CORS_ALLOW_HEADERS
            response['Access-Control-Max-Age'] = CORS_MAX_AGE
        else:
            response = self.get_response(request)
            if response.status_code == 405 and request.path.startswith(V1_PREFIX):
                response = _method_not_allowed(request, response)
            response['Cache-Control'] = 'no-store'
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Expose-Headers'] = 'Retry-After, WWW-Authenticate, ETag, Content-Disposition'
        if response.has_header('Access-Control-Allow-Credentials'):
            del response['Access-Control-Allow-Credentials']
        if response.has_header('Vary'):
            vary = [v.strip() for v in response['Vary'].split(',') if v.strip().lower() != 'cookie']
            if vary:
                response['Vary'] = ', '.join(vary)
            else:
                del response['Vary']
        return response


def _method_not_allowed(request, response):
    """The router answers a wrong method before authenticating; the contract
    (spec api-authentication) is that a request without a valid bearer is a
    401 first -- a signed-in browser's cross-site form POST must read as
    "not a credential", never as "this endpoint exists". With a valid bearer
    the 405 comes back in the envelope, with its Allow header."""
    from .auth import authenticate
    from .errors import METHOD_NOT_ALLOWED, ApiError, invalid_token
    from .models import AUDIENCE_API
    from .v1.errors import resource_metadata_url
    try:
        principal = authenticate(request, AUDIENCE_API)
    except ApiError as err:
        if err.code == 'invalid_token':
            err = invalid_token(resource_metadata_url())
        return err.as_response()
    if principal is None:
        return invalid_token(resource_metadata_url()).as_response()
    err = ApiError(405, METHOD_NOT_ALLOWED, f'{request.method} is not allowed here.')
    if response.has_header('Allow'):
        err.headers['Allow'] = response['Allow']
    return err.as_response()
