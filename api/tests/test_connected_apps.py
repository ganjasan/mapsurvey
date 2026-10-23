"""Connected apps on the connections page (spec connected-apps, change oauth-server, #313)."""
from unittest import mock

from django.test import TestCase

from survey import product_events as pe
from survey.models import AuditLog

from .helpers import ME, bearer, grant, make_app, make_pro_org, make_user, mint, oauth_settings, refresh

OAUTH = oauth_settings()
PAGE = '/editor/account/connections/'


@OAUTH
class ConnectedAppsTest(TestCase):
    def setUp(self):
        self.org, self.user = make_pro_org()
        self.app = make_app(name='Claude', redirect_uris='https://claude.ai/api/mcp/auth_callback', source='dcr')
        self.client.force_login(self.user)

    def test_one_row_for_two_token_generations(self):
        """
        GIVEN a client authorised once and refreshed once
        WHEN the page renders
        THEN one row with the newest token's scopes and the host
        """
        first = grant(self.client, self.app, scope='surveys:read responses:read')
        refresh(self.client, self.app, first['refresh_token'])
        html = self.client.get(PAGE).content.decode()
        self.assertEqual(html.count('name="action" value="disconnect"'), 1)
        self.assertIn('claude.ai', html)
        self.assertIn('responses:read', html)
        self.assertNotIn('No connected apps yet', html)
        self.assertNotIn('once that is available', html)

    def test_personal_tokens_are_not_apps(self):
        """
        GIVEN personal tokens and no grant
        WHEN the page renders
        THEN the Connected apps section is empty and the tokens are in their own table
        """
        mint(self.user)
        html = self.client.get(PAGE).content.decode()
        self.assertIn('No connected apps yet', html)
        self.assertIn('msk_…', html)

    def test_disconnect(self):
        """
        GIVEN a connected client
        WHEN the user posts Disconnect
        THEN the row is gone, the access token is 401 and the refresh token invalid_grant; audit + event written
        """
        token = grant(self.client, self.app)
        with mock.patch('survey.product_events.emit') as emit:
            response = self.client.post(PAGE, {'action': 'disconnect', 'application_id': self.app.pk})
        self.assertEqual(response.status_code, 302)
        html = self.client.get(PAGE).content.decode()
        self.assertIn('No connected apps yet', html)
        self.assertEqual(self.client.get(ME, **bearer(token['access_token'])).status_code, 401)
        self.assertEqual(refresh(self.client, self.app, token['refresh_token']).status_code, 400)
        row = AuditLog.objects.get(action='oauth_disconnect')
        self.assertEqual(row.metadata['application_id'], self.app.pk)
        self.assertEqual([c.args[0] for c in emit.call_args_list], [pe.OAUTH_APP_DISCONNECTED])
        self.assertNotIn('name', emit.call_args_list[0].args[2])

    def test_another_users_grant_is_404(self):
        """
        GIVEN user A connected to the app
        WHEN user B posts Disconnect with that application id
        THEN 404 and A's token still validates
        """
        token = grant(self.client, self.app)
        other = make_user('other')
        self.client.force_login(other)
        response = self.client.post(PAGE, {'action': 'disconnect', 'application_id': self.app.pk})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get(ME, **bearer(token['access_token'])).status_code, 200)

    def test_unknown_id_is_404(self):
        """
        GIVEN no grant
        WHEN Disconnect is posted with a bogus id
        THEN 404
        """
        self.assertEqual(self.client.post(PAGE, {'action': 'disconnect', 'application_id': 'x'}).status_code, 404)
        self.assertEqual(self.client.post(PAGE, {'action': 'disconnect', 'application_id': 999}).status_code, 404)

    def test_help_link_waits_for_the_mcp_server(self):
        """
        GIVEN the help site configured
        WHEN the page renders
        THEN no "How to connect an app" link is shown: the page is a draft until #306 (no `connected_apps` key)
        """
        from django.test import override_settings
        with override_settings(HELP_SITE_URL='https://help.example'):
            html = self.client.get(PAGE).content.decode()
        self.assertNotIn('connect-an-app', html)
        self.assertNotIn('How to connect an app', html)
