"""The connections page: tokens UI (spec personal-access-tokens) and the moved
MCP teaser (delta on agent-access-teaser)."""
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from survey import product_events as pe
from survey.models import AuditLog, CreatorPreferences, Membership, SurveyHeader

from .. import tokens
from ..models import AUDIENCE_API, TokenProfile
from .helpers import LOCMEM, bearer, make_free_org, make_member, make_org, make_pro_org, mint

PAGE = reverse('editor_account_connections')
ME = reverse('api_me')


@LOCMEM
class ConnectionsPageTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_org()
        self.client.login(username=self.owner.username, password='pass')

    def _create(self, **overrides):
        data = {
            'action': 'create', 'label': 'Claude Code',
            'scopes': ['surveys:read', 'surveys:write'], 'audiences': ['api', 'mcp'],
            'organization': '', 'expiry': tokens.EXPIRY_NEVER,
        }
        data.update(overrides)
        return self.client.post(PAGE, data, follow=True)

    def test_no_template_comment_reaches_the_page(self):
        """
        GIVEN the connections page
        WHEN it renders
        THEN no template comment leaks into the HTML ({# #} spans one line only)
        """
        html = self.client.get(PAGE).content.decode()
        self.assertNotIn('{#', html)
        self.assertNotIn('#}', html)

    def test_create_shows_the_value_once(self):
        """
        GIVEN a valid create form
        WHEN submitted
        THEN the page after the redirect shows the full value once; a reload shows only msk_…+4
        """
        with mock.patch('survey.product_events.emit') as emit:
            response = self._create()
        self.assertEqual(response.status_code, 200)
        profile = TokenProfile.objects.get()
        html = response.content.decode()
        value = html.split('id="cx-token-value">')[1].split('<')[0]
        self.assertRegex(value, r'^msk_[A-Za-z0-9_-]{40,}$')
        self.assertIn('only time it is shown', html)

        again = self.client.get(PAGE).content.decode()
        self.assertNotIn(value, again)
        self.assertIn('msk_…' + value[-4:], again)
        self.assertIn('Claude Code', again)

        self.assertEqual(self.client.get(ME, **bearer(value)).status_code, 200)
        self.assertEqual(profile.token.scope, 'surveys:read surveys:write')
        self.assertEqual([c.args[0] for c in emit.call_args_list], [pe.API_TOKEN_CREATED])
        props = emit.call_args_list[0].args[2]
        self.assertNotIn('label', props)
        self.assertNotIn(value, repr(props))

    def test_audit_on_create_and_revoke(self):
        """
        GIVEN a mint and a revoke on the page
        WHEN the audit log is read
        THEN api_token_create and api_token_revoke rows exist with the id and never the value
        """
        self._create()
        profile = TokenProfile.objects.get()
        row = AuditLog.objects.get(action='api_token_create')
        self.assertEqual(row.metadata['token_id'], profile.token_id)
        self.assertEqual(row.metadata['label'], 'Claude Code')
        self.assertEqual(row.metadata['scopes'], ['surveys:read', 'surveys:write'])
        self.assertIsNone(row.survey_uuid)
        self.assertEqual(row.actor, self.owner)
        self.assertNotIn('msk_', str(row.metadata))

        self.client.post(PAGE, {'action': 'revoke', 'token_id': profile.token_id})
        self.assertTrue(AuditLog.objects.filter(action='api_token_revoke', metadata__token_id=profile.token_id).exists())

    def test_revoke(self):
        """
        GIVEN a token
        WHEN its owner revokes it on the page
        THEN it leaves the list and the next API call is 401
        """
        value, profile = mint(self.owner, label='Old script')
        with mock.patch('survey.product_events.emit') as emit:
            response = self.client.post(PAGE, {'action': 'revoke', 'token_id': profile.token_id}, follow=True)
        self.assertNotIn('Old script', response.content.decode())
        self.assertEqual(self.client.get(ME, **bearer(value)).status_code, 401)
        self.assertEqual([c.args[0] for c in emit.call_args_list], [pe.API_TOKEN_REVOKED])

    def test_revoke_another_users_token_is_404(self):
        """
        GIVEN another user's token id
        WHEN revoked from this account
        THEN 404 and nothing changes
        """
        other_org, other = make_free_org('Other', 'other_owner')
        value, profile = mint(other)
        response = self.client.post(PAGE, {'action': 'revoke', 'token_id': profile.token_id})
        self.assertEqual(response.status_code, 404)
        profile.refresh_from_db()
        self.assertIsNone(profile.revoked_at)
        self.assertEqual(self.client.post(PAGE, {'action': 'revoke', 'token_id': 'abc'}).status_code, 404)

    def test_default_scopes_on_the_form(self):
        """
        GIVEN the page
        WHEN the form renders
        THEN read, write and responses:read are checked; publish, delete and responses:moderate
             are offered but not checked; both audiences are
        """
        html = self.client.get(PAGE).content.decode()
        for scope in ('surveys:read', 'surveys:write', 'responses:read'):
            self.assertRegex(html, rf'value="{scope}"[^>]*checked', scope)
        self.assertIn('value="responses:moderate"', html)
        for scope in ('surveys:publish', 'surveys:delete', 'responses:moderate'):
            self.assertNotRegex(html, rf'value="{scope}"[^>]*checked', scope)
        for audience in ('api', 'mcp'):
            self.assertRegex(html, rf'name="audiences"[^>]*value="{audience}"[^>]*checked')

    def test_invalid_form(self):
        """
        GIVEN an unknown scope, an empty label, a foreign workspace
        WHEN submitted
        THEN no token is created
        """
        other_org, _ = make_free_org('Other', 'other_owner')
        self._create(scopes=['admin:all'])
        self._create(label='')
        self._create(organization=str(other_org.pk))
        self._create(audiences=[])
        self.assertEqual(TokenProfile.objects.count(), 0)

    def test_workspace_binding_and_expiry(self):
        """
        GIVEN a bound token with 90-day expiry
        WHEN created
        THEN the profile is bound and the expiry is ~90 days
        """
        from datetime import timedelta

        from django.utils import timezone
        self._create(organization=str(self.org.pk), expiry=tokens.EXPIRY_90_DAYS)
        profile = TokenProfile.objects.get()
        self.assertEqual(profile.organization, self.org)
        self.assertAlmostEqual(profile.token.expires, timezone.now() + timedelta(days=90), delta=timedelta(minutes=5))
        html = self.client.get(PAGE).content.decode()
        self.assertIn(self.org.name, html)

    def test_expired_token_marked(self):
        """
        GIVEN an expired token
        WHEN the page renders
        THEN it is listed with the Expired marker
        """
        from datetime import timedelta

        from django.utils import timezone
        mint(self.owner, expires=timezone.now() - timedelta(days=1), label='Stale')
        html = self.client.get(PAGE).content.decode()
        self.assertIn('Stale', html)
        self.assertIn('Expired', html)

    def test_free_note(self):
        """
        GIVEN only Free workspaces, first one that can still start its Pro trial, then one that cannot
        WHEN the page renders
        THEN the first says the first call starts the trial, the second shows the pro_required note;
             on a Pro workspace neither shows
        """
        from billing.tests.helpers import trial_used_elsewhere
        page = self.client.get(PAGE).content.decode()
        self.assertIn('starts it', page)
        self.assertNotIn('pro_required', page)
        trial_used_elsewhere(self.org)
        self.assertIn('pro_required', self.client.get(PAGE).content.decode())
        pro, pro_owner = make_pro_org()
        self.client.login(username=pro_owner.username, password='pass')
        self.assertNotIn('pro_required', self.client.get(PAGE).content.decode())

    def test_anonymous_is_sent_to_login(self):
        """
        GIVEN a signed-out visitor
        WHEN either URL is opened
        THEN redirected to sign in
        """
        self.client.logout()
        for url in (PAGE, reverse('editor_account_mcp')):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn('login', response['Location'])


@LOCMEM
class TeaserDeltaTest(TestCase):
    """agent-access-teaser after auth-core: the old URL redirects, the block and its event live on."""

    def setUp(self):
        self.org, self.owner = make_org()
        self.client.login(username=self.owner.username, password='pass')

    def test_old_url_redirects(self):
        """
        GIVEN /editor/account/mcp/
        WHEN opened signed in
        THEN 302 to the connections page
        """
        response = self.client.get(reverse('editor_account_mcp'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], PAGE)

    def test_mcp_block_connects_and_the_notify_button_is_gone(self):
        """
        GIVEN the connections page after the MCP server shipped (change mcp-server)
        WHEN the creator reads it and an old form posts "notify"
        THEN the block shows the endpoint URL and the Claude Code command, no "Tell me when it's ready";
             the post just redirects and records nothing
        """
        from django.conf import settings
        html = self.client.get(PAGE).content.decode()
        self.assertIn('Create a Mapsurvey survey in Italian and English', html)
        self.assertIn('Personal access tokens', html)
        self.assertIn(settings.MCP_RESOURCE_URL, html)
        self.assertIn('claude mcp add --transport http mapsurvey', html)
        self.assertNotIn("Tell me when it's ready", html)
        self.assertNotIn('Coming soon', html)

        with mock.patch('survey.product_events.emit') as emit:
            response = self.client.post(PAGE, {'action': 'notify'})
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(CreatorPreferences.objects.filter(user=self.owner).first())
        self.assertEqual(emit.call_args_list, [])

    def test_entrances_in_both_bases_and_the_help_menu(self):
        """
        GIVEN the dashboard and an editor page
        WHEN both render
        THEN the account menus carry "API & connections" without a soon badge linking to the
             connections page, the "?" menu "Connect your AI agent" linking to the agent page
             (change changelog-hero), and the connections page itself links to the agent page
        """
        SurveyHeader.objects.create(name='existing', organization=self.org, created_by=self.owner)
        dashboard = self.client.get(reverse('editor')).content.decode()
        editor_page = self.client.get(reverse('editor_survey_create')).content.decode()
        agent = reverse('editor_survey_start_agent')
        for html in (dashboard, editor_page):
            self.assertIn('href="%s"' % PAGE, html)
            self.assertRegex(html, r'API &(amp;)? connections')
            self.assertNotIn('AI agents', html)
            self.assertNotIn('>soon<', html)
        self.assertIn('Connect your AI agent', editor_page)
        self.assertIn('href="%s?from=help"' % agent, editor_page)
        self.assertNotIn('href="%s"' % reverse('editor_account_mcp'), dashboard + editor_page)
        connections = self.client.get(PAGE).content.decode()
        self.assertLess(connections.index('%s?from=connections' % agent),
                        connections.index('Personal access tokens'))
