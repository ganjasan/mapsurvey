from django.urls import include, path
from oauth2_provider import views as dot_views

from . import views
from .oauth import views as oauth_views

# The authorization server (change oauth-server, #313). The namespace MUST be
# `oauth2_provider`: the toolkit's metadata view, admin and templates reverse
# it by that name. Built by hand rather than `include('oauth2_provider.urls')`
# so that only these routes exist -- no device flow, no introspection, no
# application-management pages, no OIDC discovery, no second metadata
# document under the prefix, no protected-resource document claiming this
# host is a resource (that is each resource server's own, #380 / #306).
oauth_patterns = ([
    path('authorize/', oauth_views.AuthorizationView.as_view(), name='authorize'),
    path('token/', dot_views.TokenView.as_view(), name='token'),
    # RFC 7009. The toolkit's own path is revoke_token/; the metadata view
    # reverses the NAME, so the path is ours.
    path('revoke/', dot_views.RevokeTokenView.as_view(), name='revoke-token'),
    # RFC 7591 + 7592, behind our limiter and body normalisation.
    path('register/', oauth_views.RegistrationView.as_view(), name='dcr-register'),
    path('register/<str:client_id>/', oauth_views.ManagementView.as_view(), name='dcr-register-management'),
], 'oauth2_provider')

urlpatterns = [
    # RFC 8414: at the origin root, nowhere else.
    path('.well-known/oauth-authorization-server', dot_views.OAuthServerMetadataView.as_view(),
         name='oauth_server_metadata'),
    path('oauth/', include(oauth_patterns)),
    # The one resource endpoint of change auth-core: what the token is and
    # which workspaces, on which plan, it reaches. #380 re-homes it.
    path('api/v1/me', views.me, name='api_me'),
    # The creator's tokens and connected apps. Session-authenticated like
    # every editor page; it is not an API path.
    path('editor/account/connections/', views.connections, name='editor_account_connections'),
]
