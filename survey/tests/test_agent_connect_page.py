"""Tests for the `agent-connect-page` capability (openspec/specs/agent-connect-page/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, SimpleTestCase, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch
import json
import re
import uuid
from survey.models import Membership
import os
import datetime
from urllib.parse import unquote
from survey.tests.helpers import _make_org


class AgentClientRegistryTest(SimpleTestCase):
    """The one list of AI assistants the agent page offers (change agent-onboarding)."""

    URL = 'https://preview.example/mcp'

    def test_every_built_string_follows_the_server_address(self):
        """
        GIVEN a server address that is not production
        WHEN every client's panel is built from it
        THEN install links, commands and config carry that address and never mapsurvey.org
        """
        from survey import agent_clients
        for c in agent_clients.CLIENTS:
            panel = c.panel(self.URL)
            built = ' '.join([panel['install_url'], panel['config']] + panel['commands'])
            self.assertNotIn('mapsurvey.org', built, c.slug)
            if c.method == agent_clients.METHOD_COMMAND:
                self.assertTrue(any(self.URL in cmd for cmd in panel['commands']), c.slug)
            if c.method == agent_clients.METHOD_LINK:
                self.assertTrue(panel['install_url'], c.slug)

    def test_claude_link_prefills_name_and_address(self):
        """
        GIVEN the Claude client
        WHEN its install link is built
        THEN it is claude.ai's add-connector dialog with the name and the encoded address
        """
        from urllib.parse import parse_qs, urlsplit
        from survey.agent_clients import claude_install_url
        url = claude_install_url(self.URL)
        parts = urlsplit(url)
        self.assertEqual((parts.scheme, parts.netloc, parts.path), ('https', 'claude.ai', '/customize/connectors'))
        q = parse_qs(parts.query)
        self.assertEqual(q['modal'], ['add-custom-connector'])
        self.assertEqual(q['connectorName'], ['Mapsurvey'])
        self.assertEqual(q['connectorUrl'], [self.URL])
        self.assertIn('connectorUrl=https%3A%2F%2Fpreview.example%2Fmcp', url)

    def test_cursor_config_decodes_to_the_server(self):
        """
        GIVEN the Cursor client
        WHEN its install link is built
        THEN the `config` parameter is base64 of {"url": <server>}
        """
        import base64
        from urllib.parse import parse_qs, urlsplit
        from survey.agent_clients import cursor_install_url
        url = cursor_install_url(self.URL)
        self.assertTrue(url.startswith('cursor://anysphere.cursor-deeplink/mcp/install?'))
        config = parse_qs(urlsplit(url).query)['config'][0]
        self.assertEqual(json.loads(base64.b64decode(config)), {'url': self.URL})

    def test_vscode_link_carries_the_server_definition(self):
        """
        GIVEN the VS Code client
        WHEN its install link is built
        THEN it is vscode:mcp/install with the URL-encoded http server definition
        """
        from urllib.parse import unquote
        from survey.agent_clients import vscode_install_url
        url = vscode_install_url(self.URL)
        self.assertTrue(url.startswith('vscode:mcp/install?'))
        self.assertEqual(json.loads(unquote(url.split('?', 1)[1])),
                         {'name': 'mapsurvey', 'type': 'http', 'url': self.URL})

    def test_registry_shape(self):
        """
        GIVEN the registry
        WHEN it is read
        THEN slugs are unique, chat assistants come first, the spec's clients are all there
             and every vendor fact was read within the allowed age
        """
        import datetime
        from survey import agent_clients
        slugs = [c.slug for c in agent_clients.CLIENTS]
        self.assertEqual(len(slugs), len(set(slugs)))
        for slug in ('claude', 'chatgpt', 'gemini', 'le-chat', 'perplexity', 'copilot-studio', 'other-chat',
                     'something-else', 'cursor', 'vscode', 'claude-code', 'codex', 'windsurf', 'gemini-cli'):
            self.assertIn(slug, slugs)
        groups = [key for key, _label, _clients in agent_clients.grouped()]
        self.assertEqual(groups, ['chat', 'code'])
        today = datetime.date.today()
        for c in agent_clients.CLIENTS:
            age = (today - c.verified).days
            self.assertLessEqual(age, agent_clients.VERIFY_MAX_AGE_DAYS,
                                 '%s: vendor steps read %d days ago -- read them again' % (c.slug, age))

    def test_step_marks_are_escaped(self):
        """
        GIVEN a step string with a key mark, the address mark and an angle bracket
        WHEN it is drawn
        THEN the key becomes a key, the address a copy field, and the rest is escaped
        """
        from survey.templatetags.agent_tags import agent_step
        html = agent_step('Press [[Allow]] <b>now</b>: {url}', self.URL)
        self.assertIn('<span class="ag-key">Allow</span>', html)
        self.assertIn('&lt;b&gt;now&lt;/b&gt;', html)
        self.assertIn('data-copy="%s"' % self.URL, html)


@override_settings(MCP_RESOURCE_URL='https://testserver/mcp')
class AgentPageTest(TestCase):
    """Use your AI assistant: the page, the status poll, "Tell us which" (change agent-onboarding)."""

    def setUp(self):
        self.org = _make_org('AgentOrg')
        self.user = User.objects.create_user('agentuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='agentuser', password='pass')

    def _oauth_grant(self, user=None, audiences=('mcp',), name='Claude'):
        import datetime as dt
        from oauth2_provider.models import AccessToken, Application
        from api.models import TokenProfile, KIND_OAUTH
        user = user or self.user
        app = Application.objects.create(
            name=name, client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris='https://claude.ai/api/mcp/auth_callback',
        )
        token = AccessToken.objects.create(user=user, application=app, scope='surveys:read',
                                           token='msa_test_%s' % uuid.uuid4().hex,
                                           expires=timezone.now() + dt.timedelta(hours=1))
        return TokenProfile.objects.create(token=token, kind=KIND_OAUTH, audiences=list(audiences))

    def _status(self, since):
        return self.client.get(reverse('editor_survey_start_agent_status'), {'since': since.isoformat()})

    # ── the page ──

    def test_editor_sees_tiles_and_steps(self):
        """
        GIVEN an editor-or-higher creator
        WHEN the agent page is opened
        THEN it shows the three steps, one tile per registry client (chat first), the Claude
             panel visible with its install link, and a way back to the start page
        """
        from survey import agent_clients
        response = self.client.get(reverse('editor_survey_start_agent'))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        for label in ('Connect', 'Ask for a survey', 'Edit & publish'):
            self.assertIn(label, html)
        for c in agent_clients.CLIENTS:
            self.assertEqual(html.count('data-client="%s"' % c.slug), 1, c.slug)
        self.assertLess(html.index('data-client="claude"'), html.index('data-client="cursor"'))
        claude_panel = html[html.index('id="ag-panel-claude"'):html.index('id="ag-panel-chatgpt"')]
        self.assertNotIn('hidden', claude_panel[:250])
        self.assertIn('https://claude.ai/customize/connectors?modal=add-custom-connector', claude_panel)
        self.assertNotIn('msk_', claude_panel)
        self.assertIn('href="%s"' % reverse('editor_survey_start'), html)

    def test_from_parameter_sets_the_back_link_and_the_event_origin(self):
        """
        GIVEN links from the dashboard hero, the "?" menu and an unknown origin
        WHEN the page renders with ?from=dashboard, ?from=help, ?from=<script>
        THEN the dashboard one leads back to the dashboard and exposes
             data-from; help keeps "Ways to start" with data-from; the unknown
             value is dropped and never echoed (change changelog-hero)
        """
        url = reverse('editor_survey_start_agent')
        html = self.client.get(url + '?from=dashboard').content.decode()
        self.assertIn('data-from="dashboard"', html)
        self.assertIn('href="%s?dashboard=1"' % reverse('editor'), html)
        self.assertNotIn('Ways to start', html)
        html = self.client.get(url + '?from=help').content.decode()
        self.assertIn('data-from="help"', html)
        self.assertIn('Ways to start', html)
        html = self.client.get(url + '?from=%3Cscript%3E').content.decode()
        self.assertNotIn('data-from', html)
        self.assertNotIn('script&gt;', html)

    def test_client_parameter_selects_a_panel(self):
        """
        GIVEN a link to the ChatGPT panel
        WHEN the page is opened with ?client=chatgpt
        THEN the ChatGPT panel is the one not hidden and shows numbered steps with the address and OAuth
        """
        html = self.client.get(reverse('editor_survey_start_agent') + '?client=chatgpt').content.decode()

        self.assertIn('data-requested="chatgpt"', html)
        chatgpt = html[html.index('id="ag-panel-chatgpt"'):html.index('id="ag-panel-gemini"')]
        self.assertNotIn('hidden', chatgpt[:250])
        self.assertIn('<span class="ag-key">OAuth</span>', chatgpt)
        self.assertIn('data-copy="https://testserver/mcp"', chatgpt)
        claude = html[html.index('id="ag-panel-claude"'):html.index('id="ag-panel-claude"') + 250]
        self.assertIn('hidden', claude)

    def test_unknown_client_falls_back(self):
        """
        GIVEN a stale or mistyped link
        WHEN the page is opened with ?client=nonexistent
        THEN it renders with no requested client and the default panel visible
        """
        response = self.client.get(reverse('editor_survey_start_agent') + '?client=nonexistent')

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('data-requested=""', html)
        self.assertIn('data-default="claude"', html)

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test')
    def test_unsupported_panel_offers_the_wizard_and_claude(self):
        """
        GIVEN a server with an LLM provider
        WHEN the "DeepSeek, Grok…" panel renders
        THEN it offers the wizard, a control selecting Claude and the "Tell us which" form
        """
        html = self.client.get(reverse('editor_survey_start_agent')).content.decode()

        panel = html[html.index('id="ag-panel-other-chat"'):html.index('id="ag-panel-something-else"')]
        self.assertIn('href="%s?from=start"' % reverse('editor_survey_create'), panel)
        self.assertIn('data-select="claude"', panel)
        self.assertIn('data-request', panel)

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='', GEMINI_API_KEY='')
    def test_unsupported_panel_without_a_provider(self):
        """
        GIVEN no LLM provider
        WHEN the "DeepSeek, Grok…" panel renders
        THEN the wizard is not offered and Claude still is
        """
        html = self.client.get(reverse('editor_survey_start_agent')).content.decode()

        panel = html[html.index('id="ag-panel-other-chat"'):html.index('id="ag-panel-something-else"')]
        self.assertNotIn('?from=start', panel)
        self.assertIn('data-select="claude"', panel)

    def test_pro_notice_on_free_only(self):
        """
        GIVEN a workspace on Free, then the same workspace on Pro
        WHEN the page is opened
        THEN the notice and the plans link show on Free and not on Pro
        """
        from billing.tests.helpers import make_sub
        html = self.client.get(reverse('editor_survey_start_agent')).content.decode()
        self.assertIn('class="ag-pro"', html)
        self.assertIn(reverse('org_billing', args=[self.org.slug]), html)

        make_sub(self.org)
        html = self.client.get(reverse('editor_survey_start_agent')).content.decode()
        self.assertNotIn('class="ag-pro"', html)

    def test_viewer_anonymous_and_post_refused(self):
        """
        GIVEN a viewer, an anonymous visitor, and a POST
        WHEN each reaches the page
        THEN the viewer gets the editor refusal, the visitor the login page and the POST a 405
        """
        url = reverse('editor_survey_start_agent')
        self.assertEqual(self.client.post(url).status_code, 405)

        viewer = User.objects.create_user('agentviewer', password='pass')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        self.client.login(username='agentviewer', password='pass')
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.logout()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    # ── connection detected without a click ──

    def test_status_false_before_and_true_after_a_new_grant(self):
        """
        GIVEN the page was rendered at time T
        WHEN no grant exists, then the creator approves an MCP OAuth app
        THEN status answers connected=false, then connected=true with the app's name
        """
        since = timezone.now()
        self.assertEqual(self._status(since).json(), {'connected': False, 'client': None})

        self._oauth_grant(name='Claude')

        self.assertEqual(self._status(since).json(), {'connected': True, 'client': 'Claude'})

    def test_older_grant_does_not_count(self):
        """
        GIVEN a grant made yesterday
        WHEN the page polls with today's time
        THEN status stays connected=false
        """
        import datetime as dt
        profile = self._oauth_grant()
        type(profile).objects.filter(pk=profile.pk).update(created_at=timezone.now() - dt.timedelta(days=1))

        self.assertFalse(self._status(timezone.now() - dt.timedelta(minutes=1)).json()['connected'])

    def test_api_only_grant_does_not_count(self):
        """
        GIVEN a new OAuth grant for the REST API only
        WHEN the page polls
        THEN status stays connected=false (the page waits for the MCP server)
        """
        since = timezone.now()
        self._oauth_grant(audiences=('api',))

        self.assertFalse(self._status(since).json()['connected'])

    def test_personal_token_use_counts(self):
        """
        GIVEN a personal MCP token created earlier
        WHEN it is used after the page opened
        THEN status answers connected=true with no client name, and no token value or scope
        """
        from api import tokens as token_store
        since = timezone.now()
        value, profile = token_store.mint_personal_token(self.user, 'cli', ['surveys:read'], ['mcp'])
        self.assertFalse(self._status(since).json()['connected'])

        type(profile).objects.filter(pk=profile.pk).update(last_used_at=timezone.now())

        body = self._status(since).content.decode()
        self.assertEqual(json.loads(body), {'connected': True, 'client': None})
        self.assertNotIn(value, body)
        self.assertNotIn('surveys:read', body)

    def test_other_users_grant_is_invisible(self):
        """
        GIVEN another user connects an app while this creator's page polls
        WHEN status is asked
        THEN this creator's status stays connected=false
        """
        since = timezone.now()
        other = User.objects.create_user('agentother', password='pass')
        self._oauth_grant(user=other)

        self.assertFalse(self._status(since).json()['connected'])

    def test_status_needs_a_valid_since_and_a_session(self):
        """
        GIVEN a request without a parseable `since`, and an anonymous one
        WHEN status is asked
        THEN the first is 400 and the second is sent to sign in
        """
        self.assertEqual(self.client.get(reverse('editor_survey_start_agent_status')).status_code, 400)
        self.client.logout()
        self.assertEqual(self._status(timezone.now()).status_code, 302)

    # ── "Tell us which" ──

    def test_request_emits_a_truncated_name(self):
        """
        GIVEN an assistant that cannot connect yet
        WHEN the creator submits its name
        THEN one agent_client_requested event carries the name cut to 40 characters, nothing else
        """
        from survey import product_events as pe
        with patch('survey.agent_views.pe.emit') as emit:
            response = self.client.post(reverse('editor_survey_start_agent_request'), {'name': 'D' * 60})

        self.assertEqual(response.status_code, 204)
        emit.assert_called_once_with(pe.AGENT_CLIENT_REQUESTED, self.user.pk, {'name': 'D' * 40})

    def test_request_refuses_empty_and_get(self):
        """
        GIVEN an empty name, and a GET
        WHEN they reach the request endpoint
        THEN 400 and 405, and no event
        """
        with patch('survey.agent_views.pe.emit') as emit:
            self.assertEqual(self.client.post(reverse('editor_survey_start_agent_request'), {'name': ' '}).status_code, 400)
            self.assertEqual(self.client.get(reverse('editor_survey_start_agent_request')).status_code, 405)
        emit.assert_not_called()

    def test_prompt_never_reaches_events(self):
        """
        GIVEN the page script
        WHEN its events are read
        THEN no event property carries the goal, the prompt or a ?q= URL
        """
        import os
        from django.conf import settings as dj
        path = os.path.join(dj.BASE_DIR, 'survey', 'assets', 'js', 'survey_start_agent.js')
        with open(path) as fh:
            src = fh.read()
        calls = re.findall(r"track\('agent_[a-z_]+', \{([^}]*)\}", src)
        self.assertTrue(calls)
        for call in calls:
            keys = set(re.findall(r'(\w+):', call))
            self.assertLessEqual(keys, {'client', 'target', 'via'}, call)


class AgentHelpGuideTest(SimpleTestCase):
    """The help centre's assistant guide follows the agent page (change agent-onboarding)."""

    DOCS = 'help/src/content/docs'

    def _read(self, rel):
        import os
        from django.conf import settings as dj
        with open(os.path.join(dj.BASE_DIR, self.DOCS, rel)) as fh:
            return fh.read()

    @staticmethod
    def _slug(heading):
        return re.sub(r'\s+', '-', re.sub(r'[^\w\s-]', '', heading.strip().lower()))

    def test_every_client_anchor_is_a_heading(self):
        """
        GIVEN the clients the agent page links to the guide
        WHEN the guide's headings are slugged the way Starlight does
        THEN every client's help anchor is one of them
        """
        from survey import agent_clients
        guide = self._read('how-to/use-the-mcp-server.md')
        anchors = {self._slug(h) for h in re.findall(r'^#{2,3} (.+)$', guide, re.M)}
        for c in agent_clients.CLIENTS:
            if c.help_anchor:
                self.assertIn(c.help_anchor, anchors, c.slug)

    def test_no_desktop_config_with_a_url(self):
        """
        GIVEN every help page
        WHEN it is read
        THEN none tells readers to put a remote "url" into claude_desktop_config.json
             (Claude Desktop ignores it and can wipe its mcpServers block)
        """
        import os
        from django.conf import settings as dj
        root = os.path.join(dj.BASE_DIR, self.DOCS)
        for dirpath, _dirs, files in os.walk(root):
            for name in files:
                if not name.endswith(('.md', '.mdx')):
                    continue
                with open(os.path.join(dirpath, name)) as fh:
                    text = fh.read()
                if 'claude_desktop_config.json' in text:
                    self.assertNotIn('"url"', text, os.path.join(dirpath, name))

    def test_start_guide_names_the_third_way(self):
        """
        GIVEN the start guide
        WHEN it is read
        THEN it describes "Use your AI assistant" and links to the MCP guide
        """
        guide = self._read('how-to/choose-how-to-start.md')
        self.assertIn('Use your AI assistant', guide)
        self.assertIn('/how-to/use-the-mcp-server/', guide)
        self.assertNotIn('is coming', guide)
