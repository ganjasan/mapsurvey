from django.urls import path

from . import views

urlpatterns = [
    # `settings.MCP_RESOURCE_URL` is `<issuer>/mcp`, without a trailing slash;
    # the slashed form routes here too because APPEND_SLASH would 301 a POST.
    path('mcp', views.endpoint, name='mcp_endpoint'),
    path('mcp/', views.endpoint),
    # RFC 9728, path-inserted for the resource `<issuer>/mcp`.
    path('.well-known/oauth-protected-resource/mcp', views.protected_resource_metadata,
         name='mcp_protected_resource'),
]
