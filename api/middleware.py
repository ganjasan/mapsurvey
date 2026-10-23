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
