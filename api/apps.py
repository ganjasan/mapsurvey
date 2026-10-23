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

    def ready(self):
        from django.db.models.signals import pre_save
        from oauth2_provider.models import Application

        from .oauth import redirects

        def _check_redirect_uris(sender, instance, **kwargs):
            # The backstop behind DCR, CIMD and the admin: `http` is for
            # loopback hosts only, whichever way a client row is written
            # (change oauth-server, D3).
            redirects.check_registrable((instance.redirect_uris or '').split())

        pre_save.connect(_check_redirect_uris, sender=Application, weak=False,
                         dispatch_uid='api.oauth.redirect_uris')
