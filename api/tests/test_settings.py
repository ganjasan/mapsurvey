"""The OAuth settings block stays RFC 9700-compliant (change auth-core, D2)."""
from django.conf import settings
from django.core import checks
from django.test import SimpleTestCase, override_settings


def _oauth_messages():
    msgs = checks.run_checks(tags=[checks.Tags.security], include_deployment_checks=True)
    # run_checks() does not apply SILENCED_SYSTEM_CHECKS; `manage.py check` does.
    # E003 (http in the scheme list) is silenced on purpose -- see settings.py.
    return [m for m in msgs if str(m.id).startswith('oauth2_provider.') and not m.is_silenced()]


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
        self.assertEqual(block['ACCESS_TOKEN_EXPIRE_SECONDS'], 3600)
        self.assertFalse(block['ALLOW_URI_WILDCARDS'])

    def test_http_is_for_loopback_only(self):
        """
        GIVEN `http` in the redirect scheme list (change oauth-server, D3)
        WHEN the toolkit's check runs and a non-loopback http URI is offered
        THEN the check is silenced by id, and the URI is refused by the one helper the four paths call
        """
        from django.core.exceptions import ValidationError

        from ..oauth import redirects
        block = settings.OAUTH2_PROVIDER
        self.assertEqual(block['ALLOWED_REDIRECT_URI_SCHEMES'], ['https', 'http'])
        self.assertIn('oauth2_provider.E003', settings.SILENCED_SYSTEM_CHECKS)
        with self.assertRaises(ValidationError):
            redirects.check_registrable(['http://example.com/cb'])
        self.assertIsNone(redirects.problem('http://127.0.0.1:8080/cb'))
        self.assertFalse(redirects.matches('http://example.com/cb', ['http://example.com/cb']))

    def test_server_advertises_what_it_accepts(self):
        """
        GIVEN the settings block
        WHEN read
        THEN grants, response types, auth methods, DCR, CIMD and the issuer are pinned
        """
        block = settings.OAUTH2_PROVIDER
        self.assertEqual(block['OAUTH2_GRANT_TYPES_SUPPORTED'], ['authorization_code', 'refresh_token'])
        self.assertEqual(block['OAUTH2_RESPONSE_TYPES_SUPPORTED'], ['code'])
        self.assertIn('none', block['OAUTH2_TOKEN_ENDPOINT_AUTH_METHODS_SUPPORTED'])
        self.assertEqual(block['AUTHORIZATION_CODE_EXPIRE_SECONDS'], 600)
        self.assertTrue(block['DCR_ENABLED'])
        self.assertTrue(block['CIMD_ENABLED'])
        self.assertEqual(block['OAUTH2_SERVER_CLASS'], 'api.oauth.server.Server')
        self.assertEqual(block['OAUTH2_VALIDATOR_CLASS'], 'api.oauth.validator.MapsurveyOAuth2Validator')
        self.assertEqual(block['OIDC_ISS_ENDPOINT'], settings.OAUTH_ISSUER)
        self.assertTrue(settings.API_RESOURCE_URLS['api'].startswith(settings.OAUTH_ISSUER))

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
