from django.urls import path

from . import views

urlpatterns = [
    # The one resource endpoint of change auth-core: what the token is and
    # which workspaces, on which plan, it reaches. #380 re-homes it.
    path('api/v1/me', views.me, name='api_me'),
    # The creator's tokens (and, after #313, connected apps). Session-authenticated
    # like every editor page; it is not an API path.
    path('editor/account/connections/', views.connections, name='editor_account_connections'),
]
