"""`get_me`: the first thing an agent should call."""
from django.conf import settings

from api.views import me_payload

from . import registry
from .registry import Args, tool


@tool(
    'get_me',
    title='Who am I',
    description=(
        'Call this first. Returns the user behind the token, their workspaces with plan and whether '
        'the API is included (the MCP server is a Pro feature: tools on a survey of a Free workspace '
        'answer pro_required with an upgrade URL), the token\'s permissions, and the tools this token '
        'can use.'
    ),
    scope=None, role='-', args=Args, read_only=True, idempotent=True,
)
def get_me(request, args):
    principal = request.principal
    payload = me_payload(principal)
    payload['mcp'] = {
        'server': settings.MCP_RESOURCE_URL,
        'tools': [t.name for t in registry.tools_for(principal)],
    }
    return payload
