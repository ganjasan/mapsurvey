from django.apps import AppConfig


class McpConfig(AppConfig):
    """The MCP server (change mcp-server, #306): the second resource server of
    the API platform (epic #378), after REST API v1.

    Streamable HTTP in stateless mode on `settings.MCP_RESOURCE_URL`, served by
    this process. Authentication is `api.auth.authenticate(request, 'mcp')`,
    rights, the Pro gate and limits are `api.*`, and every tool writes through
    `survey/services/` with `Actor(surface='mcp')`. Nothing survey-related is
    implemented here; see README.md.
    """
    name = 'mcp'
    default_auto_field = 'django.db.models.BigAutoField'
