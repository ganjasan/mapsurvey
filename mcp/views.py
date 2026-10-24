"""The MCP endpoint and its RFC 9728 document (design D1-D3).

Order of checks on `POST /mcp`, cheapest refusal first and no step before
authentication reads the body: `Origin` (403) → bearer (401 with the MCP
`resource_metadata`, 429 from the per-IP failed-bearer budget) → method (405,
`Allow: POST`: no SSE stream, no session to DELETE) → `MCP-Protocol-Version`
(400 with the supported list) → JSON body (400) → `Mcp-Session-Id` (404 when
it is not this token's) → dispatch. Every answer is `application/json` and
`Cache-Control: no-store`; a notification is `202` with no body.
"""
import json
from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from api.auth import authenticate
from api.errors import INVALID_TOKEN, ApiError, invalid_token
from api.models import AUDIENCE_MCP

from . import protocol, sessions
from .errors import (
    INVALID_REQUEST, LIMITED, ORIGIN_REFUSED, PARSE_ERROR, SESSION_UNKNOWN, UNSUPPORTED_VERSION, RpcError,
)

MAX_BODY = 2 * 1024 * 1024   # a tool call is small; import_survey has its own cap inside


def resource_metadata_url():
    return settings.OAUTH_ISSUER.rstrip('/') + '/.well-known/oauth-protected-resource/mcp'


def _origin(url):
    parts = urlsplit(url)
    return f'{parts.scheme}://{parts.netloc}'.lower()


def origin_allowed(origin):
    allowed = {_origin(settings.OAUTH_ISSUER)}
    allowed.update(_origin(o) for o in getattr(settings, 'MCP_ALLOWED_ORIGINS', ()))
    return origin.lower() in allowed


def _rpc_response(status, body, headers=None):
    response = JsonResponse(body, status=status, safe=False) if body is not None else HttpResponse(status=status)
    for name, value in (headers or {}).items():
        response[name] = value
    response['Cache-Control'] = 'no-store'
    return response


def _error(err, request_id=None, headers=None):
    return _rpc_response(err.http_status, err.body(request_id), headers)


@csrf_exempt
def endpoint(request):
    origin = request.META.get('HTTP_ORIGIN')
    if origin is not None and not origin_allowed(origin):
        return _error(RpcError(ORIGIN_REFUSED, 'Origin not allowed.', http_status=403))

    try:
        principal = authenticate(request, AUDIENCE_MCP)
    except ApiError as err:
        if err.code == INVALID_TOKEN:
            err = invalid_token(resource_metadata_url())
        return err.as_response()
    if principal is None:
        return invalid_token(resource_metadata_url()).as_response()
    request.principal = principal

    if request.method != 'POST':
        return _error(RpcError(INVALID_REQUEST, 'This endpoint takes POST only: no SSE stream is offered.',
                               http_status=405), headers={'Allow': 'POST'})

    version = request.META.get('HTTP_MCP_PROTOCOL_VERSION', protocol.DEFAULT_VERSION)
    if version not in protocol.SUPPORTED_VERSIONS:
        return _error(RpcError(UNSUPPORTED_VERSION, 'Unsupported protocol version.',
                               data={'supported': list(protocol.SUPPORTED_VERSIONS), 'requested': version},
                               http_status=400))

    if len(request.body) > MAX_BODY:
        return _error(RpcError(INVALID_REQUEST, 'Request body too large.', http_status=413))
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return _error(RpcError(PARSE_ERROR, 'Parse error.', http_status=400))

    session_key = f'tok:{principal.token_id}'
    session_id = request.META.get('HTTP_MCP_SESSION_ID')
    if session_id:
        try:
            session_key = f'sid:{sessions.verify(session_id, principal.token_id)}'
        except sessions.BadSession:
            return _error(RpcError(SESSION_UNKNOWN, 'Session not found; initialize again.', http_status=404))

    messages = payload if isinstance(payload, list) else [payload]
    if not messages:
        return _error(RpcError(INVALID_REQUEST, 'Empty batch.', http_status=400))
    responses, headers = [], {}
    for message in messages:
        if protocol.is_notification(message):
            continue
        if not protocol.is_request(message):
            if isinstance(message, dict) and ('result' in message or 'error' in message):
                continue   # a client response: accepted, nothing to answer
            return _error(RpcError(INVALID_REQUEST, 'Not a JSON-RPC request.', http_status=400))
        try:
            value, extra = protocol.dispatch(request, message, session_key)
            headers.update(extra)
            responses.append(protocol.result(message['id'], value))
        except RpcError as err:
            if len(messages) == 1:
                return _error(err, message.get('id'), headers)
            responses.append(err.body(message.get('id')))
        except ApiError as err:
            # The per-token window on initialize / tools/list, or the failed-bearer budget.
            if len(messages) == 1:
                rpc = RpcError(LIMITED, str(err.detail), data={'error': err.code, **err.extra},
                               http_status=err.status)
                return _error(rpc, message.get('id'), {**headers, **err.headers})
            responses.append(RpcError(LIMITED, str(err.detail), data={'error': err.code}).body(message.get('id')))
    if not responses:
        return _rpc_response(202, None, headers)
    body = responses[0] if not isinstance(payload, list) else responses
    return _rpc_response(200, body, headers)


def protected_resource_metadata(request):
    """RFC 9728 for the MCP resource. Public; the endpoint's 401 points here.
    `resource` is `settings.MCP_RESOURCE_URL` byte for byte -- the identifier
    clients send as RFC 8707 `resource` and the audience the issuer binds."""
    from api import scopes
    help_site = getattr(settings, 'HELP_SITE_URL', '').rstrip('/')
    response = JsonResponse({
        'resource': settings.MCP_RESOURCE_URL,
        'authorization_servers': [settings.OAUTH_ISSUER],
        'scopes_supported': list(scopes.SCOPES),
        'bearer_methods_supported': ['header'],
        'resource_name': 'Mapsurvey MCP server',
        'resource_documentation': (help_site + '/how-to/use-the-mcp-server/') if help_site else settings.MCP_RESOURCE_URL,
    })
    response['Access-Control-Allow-Origin'] = '*'
    response['Cache-Control'] = 'public, max-age=3600'
    return response
