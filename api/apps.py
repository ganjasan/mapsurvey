from django.apps import AppConfig


class ApiConfig(AppConfig):
    """The authorization layer under every programmatic client (change auth-core, #379).

    One token table (django-oauth-toolkit's, with our `TokenProfile` beside it),
    one `authenticate()`, scopes, the Pro gate and per-token rate limits. The
    REST API (#380), the MCP server (#306) and the OAuth 2.1 endpoints (#313)
    are resource servers and an issuer on top of this app; none of them carries
    security logic of its own.
    """
    name = 'api'
    default_auto_field = 'django.db.models.BigAutoField'
