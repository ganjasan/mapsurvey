"""The OAuth settings block stays RFC 9700-compliant (change auth-core, D2)."""
from django.conf import settings
from django.core import checks
from django.test import SimpleTestCase, override_settings


def _oauth_messages():
    msgs = checks.run_checks(tags=[checks.Tags.security], include_deployment_checks=True)
    return [m for m in msgs if str(m.id).startswith('oauth2_provider.')]


class OAuthSettingsTest(SimpleTestCase):
    def test_toolkit_checks_pass(self):
        """
        GIVEN the OAUTH2_PROVIDER block in settings
        WHEN django-oauth-toolkit's deploy-time system check runs
        THEN it reports nothing: every RFC 9700 gate is on and hashed storage is compatible
        """
        self.assertEqual(_oauth_messages(), [])

    def test_compliance_values_are_pinned(self):
        """
        GIVEN the settings block
        WHEN its values are read
        THEN hashed storage, PKCE, reuse protection and https-only redirects are set
        """
        block = settings.OAUTH2_PROVIDER
        self.assertTrue(block['COMPLIANT_BCP_RFC9700_TOKEN_STORAGE'])
        self.assertEqual(block['REFRESH_TOKEN_GRACE_PERIOD_SECONDS'], 0)
        self.assertTrue(block['PKCE_REQUIRED'])
        self.assertTrue(block['REFRESH_TOKEN_REUSE_PROTECTION'])
        self.assertEqual(block['ALLOWED_REDIRECT_URI_SCHEMES'], ['https'])
        self.assertEqual(block['ACCESS_TOKEN_EXPIRE_SECONDS'], 3600)

    def test_drift_fails_the_check(self):
        """
        GIVEN PKCE switched off while its config gate stays on
        WHEN the toolkit's check runs
        THEN it reports an error, so a drift fails the suite rather than a check nobody runs
        """
        insecure = dict(settings.OAUTH2_PROVIDER, PKCE_REQUIRED=False)
        with override_settings(OAUTH2_PROVIDER=insecure):
            ids = {m.id for m in _oauth_messages()}
        self.assertTrue(ids, 'expected the toolkit to flag PKCE_REQUIRED=False')
        self.assertEqual(_oauth_messages(), [], 'the override must not leak past the block')

    def test_scopes_come_from_the_registry(self):
        """
        GIVEN api.scopes.SCOPES
        WHEN OAUTH2_PROVIDER['SCOPES'] is read
        THEN they are the same keys, so the consent page and the token form agree
        """
        from api import scopes
        self.assertEqual(list(settings.OAUTH2_PROVIDER['SCOPES']), list(scopes.SCOPES))
