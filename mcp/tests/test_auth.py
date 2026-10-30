"""`mcp-server`: bearer only, the RFC 9728 document, audiences, Origin, sessions."""
from django.conf import settings
from django.test import TestCase, override_settings

from survey.models import SurveyHeader

from api.models import AUDIENCE_API
from ..errors import ORIGIN_REFUSED, SESSION_UNKNOWN
from .helpers import (
    ISSUER, LOCMEM, MCP_SETTINGS, METADATA, McpClient, make_member, make_pro_org, make_v1_survey, mint, result_of,
)


@LOCMEM
@MCP_SETTINGS
class AuthTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner)
        self.token, _ = mint(self.owner)
        self.mcp = McpClient(self.client, self.token)

    def test_no_bearer_is_401_naming_the_mcp_metadata(self):
        """
        GIVEN no Authorization header
        WHEN initialize is POSTed
        THEN 401 invalid_token with resource_metadata pointing at the MCP document
        """
        response = McpClient(self.client, None).initialize()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'invalid_token')
        self.assertIn('Bearer realm="mapsurvey"', response['WWW-Authenticate'])
        self.assertIn(f'resource_metadata="{ISSUER}/.well-known/oauth-protected-resource/mcp"',
                      response['WWW-Authenticate'])

    def test_signed_in_browser_without_a_bearer_is_401(self):
        """
        GIVEN a creator's session cookie and no bearer
        WHEN tools/call is POSTed
        THEN 401 and nothing runs
        """
        self.client.force_login(self.owner)
        response = McpClient(self.client, None).call('create_survey', {'name': 'via cookie'})
        self.assertEqual(response.status_code, 401)
        self.assertFalse(SurveyHeader.objects.filter(name='via cookie').exists())

    def test_metadata_document(self):
        """
        GIVEN the RFC 9728 document of the MCP resource
        WHEN fetched anonymously
        THEN resource equals settings.MCP_RESOURCE_URL byte for byte, issuer and scopes are listed
        """
        response = self.client.get(METADATA)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['resource'], settings.MCP_RESOURCE_URL)
        self.assertEqual(body['resource'], ISSUER + '/mcp')
        self.assertEqual(body['authorization_servers'], [ISSUER])
        self.assertIn('surveys:write', body['scopes_supported'])
        self.assertEqual(body['bearer_methods_supported'], ['header'])

    def test_default_identifier_has_no_trailing_slash(self):
        """
        GIVEN the settings module's default
        WHEN MCP_RESOURCE_URL is derived from the issuer
        THEN it is <issuer>/mcp without a trailing slash, and the api audience table carries it
        """
        from mapsurvey import settings as module
        self.assertEqual(module.MCP_RESOURCE_URL, module.OAUTH_ISSUER + '/mcp')
        self.assertEqual(module.API_RESOURCE_URLS['mcp'], module.MCP_RESOURCE_URL)

    def test_rest_only_token_is_refused(self):
        """
        GIVEN a personal token with audiences ["api"]
        WHEN it POSTs tools/list
        THEN 401 invalid_token
        """
        token, _ = mint(self.owner, audiences=(AUDIENCE_API,))
        response = self.mcp.rpc('tools/list', token=token)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'invalid_token')

    def test_forged_origin_is_403(self):
        """
        GIVEN a valid token and Origin: https://evil.example
        WHEN create_survey is called
        THEN 403 and no survey exists; the issuer's own origin passes
        """
        response = self.mcp.call('create_survey', {'name': 'rebound'}, HTTP_ORIGIN='https://evil.example')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['error']['code'], ORIGIN_REFUSED)
        self.assertFalse(SurveyHeader.objects.filter(name='rebound').exists())
        self.assertEqual(self.mcp.rpc('ping', HTTP_ORIGIN=ISSUER).status_code, 200)

    @override_settings(MCP_ALLOWED_ORIGINS=['https://inspector.example'])
    def test_configured_origin_passes(self):
        """
        GIVEN MCP_ALLOWED_ORIGINS naming a browser client
        WHEN it sends its Origin
        THEN the request is served
        """
        self.assertEqual(self.mcp.rpc('ping', HTTP_ORIGIN='https://inspector.example').status_code, 200)

    def test_session_of_token_a_under_token_b_is_404(self):
        """
        GIVEN token A initialised and got a session id
        WHEN token B presents that id, and when a tampered id is presented
        THEN 404 both times and no tool runs; A's own id keeps working
        """
        self.mcp.initialize()
        other = make_member(self.org, 'other_owner', role='owner')
        token_b, _ = mint(other)
        response = self.mcp.call('create_survey', {'name': 'hijack'}, token=token_b)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error']['code'], SESSION_UNKNOWN)
        self.assertFalse(SurveyHeader.objects.filter(name='hijack').exists())
        response = self.mcp.rpc('ping', session=self.mcp.session + 'x')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(result_of(self.mcp.rpc('ping')), {})

    def test_request_without_session_is_served(self):
        """
        GIVEN a stateless client that never sends Mcp-Session-Id
        WHEN it calls a tool
        THEN it is served (the server holds no session state)
        """
        self.mcp.session = None
        self.assertEqual(self.mcp.call('get_survey', {'survey': str(self.survey.uuid)}).status_code, 200)


BROWSER_ACCEPT = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
AGENT_PAGE = '/editor/surveys/start/agent/?from=connections'


@LOCMEM
@MCP_SETTINGS
class OpenedInBrowserTest(TestCase):
    """#498: the address is clicked in letters; a browser gets a page, clients the 401."""

    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.token, _ = mint(self.owner)

    def test_browser_get_redirects_to_the_agent_page(self):
        """
        GIVEN a browser navigation (GET, Accept text/html, no Authorization)
        WHEN /mcp or /mcp/ is opened
        THEN 302 to the Connect-your-AI-agent page, from=connections
        """
        for path in ('/mcp', '/mcp/'):
            response = self.client.get(path, HTTP_ACCEPT=BROWSER_ACCEPT)
            self.assertEqual(response.status_code, 302, path)
            self.assertEqual(response['Location'], AGENT_PAGE)

    def test_signed_out_visitor_goes_through_login(self):
        """
        GIVEN a signed-out browser
        WHEN it follows the redirect from /mcp
        THEN it reaches the login page with next pointing at the agent page
        """
        response = self.client.get('/mcp', HTTP_ACCEPT=BROWSER_ACCEPT, follow=True)
        final, _status = response.redirect_chain[-1]
        self.assertIn('login', final)
        self.assertIn('next=', final)
        self.assertIn('start/agent', final)

    def test_signed_in_creator_sees_the_agent_page(self):
        """
        GIVEN a signed-in creator
        WHEN they open /mcp in the browser
        THEN the agent page renders with the server address on it
        """
        self.client.force_login(self.owner)
        response = self.client.get('/mcp', HTTP_ACCEPT=BROWSER_ACCEPT, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain, [(AGENT_PAGE, 302)])
        self.assertContains(response, ISSUER + '/mcp')

    def test_client_shaped_get_keeps_the_401(self):
        """
        GIVEN an MCP client's GET probe (Accept application/json, text/event-stream, no bearer)
        WHEN /mcp is fetched
        THEN 401 invalid_token naming the MCP metadata, as before
        """
        response = self.client.get('/mcp', HTTP_ACCEPT='application/json, text/event-stream')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'invalid_token')
        self.assertIn(f'resource_metadata="{ISSUER}{METADATA}"', response['WWW-Authenticate'])

    def test_get_without_accept_keeps_the_401(self):
        """
        GIVEN a GET with no Accept header and no bearer (curl)
        WHEN /mcp is fetched
        THEN 401, not a redirect
        """
        self.assertEqual(self.client.get('/mcp').status_code, 401)

    def test_html_get_with_a_bearer_is_a_client(self):
        """
        GIVEN a GET asking for text/html but carrying a bearer
        WHEN /mcp is fetched
        THEN 405 with Allow: POST, as any authenticated GET
        """
        response = self.client.get('/mcp', HTTP_ACCEPT=BROWSER_ACCEPT, HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response['Allow'], 'POST')

    def test_post_from_a_browser_is_not_redirected(self):
        """
        GIVEN a POST with Accept text/html and no bearer
        WHEN /mcp is hit
        THEN 401 invalid_token: only a GET navigation is redirected
        """
        response = self.client.post('/mcp', '{}', content_type='application/json', HTTP_ACCEPT=BROWSER_ACCEPT)
        self.assertEqual(response.status_code, 401)
