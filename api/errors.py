"""The error envelope every API and MCP response uses.

`ApiError` is raised anywhere under `@api_endpoint` and turned into
`{"error": <code>, "detail": <text>, ...extra}` with the status it names. Codes
are stable strings a client can switch on; the detail is for a human reading
the response and may change. Never put a token value, a stack trace or a model
name in either.
"""
from django.http import JsonResponse

INVALID_TOKEN = 'invalid_token'
SCOPE_MISSING = 'scope_missing'
PRO_REQUIRED = 'pro_required'
NOT_FOUND = 'not_found'
RATE_LIMITED = 'rate_limited'
SERVER_ERROR = 'server_error'

# Every response under @api_endpoint carries this: a token-authenticated
# answer is for the caller alone, and a shared cache in front of us (or a
# browser's) must never hand it to the next one.
CACHE_CONTROL = 'no-store'


class ApiError(Exception):
    def __init__(self, status, code, detail='', **extra):
        super().__init__(code)
        self.status = status
        self.code = code
        self.detail = detail
        self.extra = extra
        self.headers = {}

    def as_response(self):
        body = {'error': self.code, 'detail': str(self.detail)}
        body.update(self.extra)
        response = JsonResponse(body, status=self.status)
        for name, value in self.headers.items():
            response[name] = value
        return finalize(response)


def finalize(response):
    response['Cache-Control'] = CACHE_CONTROL
    return response


def invalid_token():
    err = ApiError(401, INVALID_TOKEN, 'Authentication required: send a valid bearer token.')
    err.headers['WWW-Authenticate'] = 'Bearer realm="mapsurvey"'
    return err


def not_found():
    return ApiError(404, NOT_FOUND, 'Not found.')
