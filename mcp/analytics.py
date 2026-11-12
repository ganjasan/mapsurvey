"""PostHog MCP Analytics events (change `mcp-analytics-events`, #649).

PostHog's MCP Analytics screens (dashboard, tool quality, harness breakdown,
sessions) read `$mcp_tool_call`, `$mcp_initialize` and `$mcp_tools_list` with
`$mcp_*` properties -- the format the Node-only `@posthog/mcp` SDK emits. This
server is hand-written, so this module emits that format itself, next to our
own `mcp_tool_called` (which stays as it is).

What never goes in: `$mcp_parameters`, `$mcp_response`, `$mcp_intent`, an
error's `detail` -- tool arguments and results hold survey content, and the
rule of `mcp-server` is that arguments never reach events. `$mcp_error_message`
carries our error CODE only.

Emission goes through `survey.product_events.emit`: `distinct_id` is the
user's pk, nothing happens without a PostHog key, and nothing here can break a
request.
"""
from survey import product_events as pe

TOOL_CALL = '$mcp_tool_call'
INITIALIZE = '$mcp_initialize'
TOOLS_LIST = '$mcp_tools_list'

#: Claimed for compatibility: some PostHog per-tool cuts filter on the SDK's
#: identifier, and a different value would hide our events from them (design D6).
SOURCE = 'posthog_mcp_analytics'
USER_AGENT_MAX = 256
VENDOR_CLIENT_MAX = 64

INVALID_ARGUMENTS = 'invalid_arguments'

#: Our outcome codes → PostHog's semantic failure buckets (design D4).
#: Any other error code is `api_4xx`.
ERROR_TYPES = {
    'scope_missing': 'permission',
    'forbidden_role': 'permission',
    'pro_required': 'permission',
    'rate_limited': 'rate_limited',
    INVALID_ARGUMENTS: 'validation',
    'validation': 'validation',
    'bad_cursor': 'validation',
    'confirmation_required': 'missing_context',
    'server_error': 'internal',
}


def error_type(code):
    return ERROR_TYPES.get(code, 'api_4xx')


def _header(request, name, limit):
    value = request.META.get(name, '')
    return value.strip()[:limit] if isinstance(value, str) else ''


def _protocol_version(request, session):
    from .protocol import DEFAULT_VERSION
    return (request.META.get('HTTP_MCP_PROTOCOL_VERSION')
            or (session.protocol_version if session else '')
            or DEFAULT_VERSION)


def base_properties(request, session=None, protocol_version=None):
    """What every MCP Analytics event carries: server, protocol, client, session."""
    from .protocol import SERVER_INFO
    name, version = (session.client_name, session.client_version) if session else ('', '')
    props = {
        '$mcp_source': SOURCE,
        '$mcp_server_name': SERVER_INFO['name'],
        '$mcp_server_version': SERVER_INFO['version'],
        '$mcp_protocol_version': protocol_version or _protocol_version(request, session),
    }
    optional = {
        '$mcp_client_name': name,
        '$mcp_client_version': version,
        '$mcp_client_user_agent': _header(request, 'HTTP_USER_AGENT', USER_AGENT_MAX),
        '$mcp_vendor_client': _header(request, 'HTTP_X_ANTHROPIC_CLIENT', VENDOR_CLIENT_MAX),
        '$session_id': session.analytics_id() if session else None,
    }
    props.update({key: value for key, value in optional.items() if value})
    return props


def _session(request):
    return getattr(request, 'mcp_session', None)


def tool_call(request, tool_name, outcome, status, duration_ms):
    """`$mcp_tool_call` for one `tools/call` of a registered tool.

    `outcome` is `ok` or our error code; `status` the HTTP status of the error
    envelope (None for a JSON-RPC error or a success).
    """
    props = base_properties(request, _session(request))
    props.update({
        '$mcp_tool_name': tool_name,
        '$mcp_is_error': outcome != 'ok',
        '$mcp_duration_ms': round(duration_ms, 1),
    })
    if outcome != 'ok':
        props['$mcp_error_type'] = error_type(outcome)
        props['$mcp_error_message'] = outcome
        if status:
            props['$mcp_error_status'] = status
    pe.emit(TOOL_CALL, request.principal.user.pk, props)


def initialize(request, session, protocol_version):
    """`$mcp_initialize` after a successful `initialize`, described by the
    session it just issued (client context and `$session_id` included)."""
    props = base_properties(request, session, protocol_version=protocol_version)
    pe.emit(INITIALIZE, request.principal.user.pk, props)


def tools_list(request, names):
    """`$mcp_tools_list` after a successful `tools/list`: the catalog the token is offered."""
    props = base_properties(request, _session(request))
    props.update({'$mcp_listed_tool_names': list(names), 'tool_count': len(names)})
    pe.emit(TOOLS_LIST, request.principal.user.pk, props)
