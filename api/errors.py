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
# REST API v1 (change rest-api-v1, #380).
FORBIDDEN_ROLE = 'forbidden_role'
VALIDATION = 'validation'
DRAFT_REQUIRED = 'draft_required'
ANSWERS_AT_RISK = 'answers_at_risk'
DELETE_BLOCKED = 'delete_blocked'
TRANSLATION_GAPS = 'translation_gaps'
INCOMPATIBLE_DRAFT = 'incompatible_draft'
TRANSITION_REFUSED = 'transition_refused'
CONFLICT = 'conflict'
BAD_CURSOR = 'bad_cursor'
METHOD_NOT_ALLOWED = 'method_not_allowed'

# Every code a client may switch on, in the order the reference lists them.
ALL_CODES = (
    INVALID_TOKEN, SCOPE_MISSING, PRO_REQUIRED, FORBIDDEN_ROLE, NOT_FOUND, VALIDATION,
    DRAFT_REQUIRED, ANSWERS_AT_RISK, DELETE_BLOCKED, TRANSLATION_GAPS, INCOMPATIBLE_DRAFT,
    TRANSITION_REFUSED, CONFLICT, BAD_CURSOR, METHOD_NOT_ALLOWED, RATE_LIMITED, SERVER_ERROR,
)

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


def invalid_token(resource_metadata=None):
    """401 with the RFC 6750 challenge; a resource server passes its RFC 9728
    metadata URL so a client can discover where to get a token."""
    err = ApiError(401, INVALID_TOKEN, 'Authentication required: send a valid bearer token.')
    challenge = 'Bearer realm="mapsurvey"'
    if resource_metadata:
        challenge += f', resource_metadata="{resource_metadata}"'
    err.headers['WWW-Authenticate'] = challenge
    return err


def not_found():
    return ApiError(404, NOT_FOUND, 'Not found.')
