from django.urls import include, path, re_path
from oauth2_provider import views as dot_views

from . import views
from .errors import not_found
from .v1 import api as api_v1
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

def v1_not_found(request):
    return not_found().as_response()


# `reverse('api_me')` predates the router; keep the name (tests, the
# connections page's curl example).
def _api_me_name():
    return path('api/v1/me', lambda request: v1_not_found(request), name='api_me')


urlpatterns = [
    # RFC 8414: at the origin root, nowhere else.
    path('.well-known/oauth-authorization-server', dot_views.OAuthServerMetadataView.as_view(),
         name='oauth_server_metadata'),
    path('oauth/', include(oauth_patterns)),
    # REST API v1 (change rest-api-v1, #380): django-ninja. Unknown paths
    # under it answer the envelope 404, never the site's HTML page.
    path('api/v1/', api_v1.urls),
    re_path(r'^api/v1/.*$', v1_not_found),
    # RFC 9728: the API's protected-resource metadata, path-inserted for the
    # resource `<issuer>/api/` (the API's 401 names it in WWW-Authenticate).
    path('.well-known/oauth-protected-resource/api/', views.protected_resource_metadata,
         name='api_protected_resource'),
    # The creator's tokens and connected apps. Session-authenticated like
    # every editor page; it is not an API path.
    path('editor/account/connections/', views.connections, name='editor_account_connections'),
    # Never reached (the router above answers first); it only names the path.
    _api_me_name(),
]
