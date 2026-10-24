"""`mcp-server`: one stateless Streamable HTTP endpoint -- JSON in, JSON out,
no streams, version negotiation, batches, the methods clients call anyway."""
from django.test import TestCase

from ..errors import INVALID_PARAMS, METHOD_NOT_FOUND, PARSE_ERROR, UNSUPPORTED_VERSION
from ..protocol import SUPPORTED_VERSIONS
from .helpers import LOCMEM, MCP_SETTINGS, McpClient, make_pro_org, make_v1_survey, mint, result_of, rpc


@LOCMEM
@MCP_SETTINGS
class TransportTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner)
        self.mcp = McpClient(self.client, mint(self.owner)[0])

    def test_tool_call_is_one_json_response(self):
        """
        GIVEN a valid token and Accept listing both json and event-stream
        WHEN tools/call is POSTed
        THEN 200 application/json with one JSON-RPC response, never text/event-stream, and no-store
        """
        response = self.mcp.call('get_survey', {'survey': str(self.survey.uuid)})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        self.assertNotIn('event-stream', response['Content-Type'])
        self.assertFalse(response.streaming)
        self.assertEqual(response['Cache-Control'], 'no-store')
        body = response.json()
        self.assertEqual(body['jsonrpc'], '2.0')
        self.assertEqual(body['id'], 1)
        self.assertFalse(body['result']['isError'])

    def test_initialize_negotiates_and_issues_a_session(self):
        """
        GIVEN a client on 2025-11-25
        WHEN it initialises
        THEN the server answers that version, tools capability, serverInfo, instructions and a session id
        """
        response = self.mcp.initialize()
        result = result_of(response)
        self.assertEqual(result['protocolVersion'], '2025-11-25')
        self.assertIn('tools', result['capabilities'])
        self.assertEqual(result['serverInfo']['name'], 'mapsurvey')
        self.assertIn('get_me', result['instructions'])
        self.assertTrue(response['Mcp-Session-Id'])

    def test_unknown_client_version_gets_the_newest_supported(self):
        """
        GIVEN a client asking for a version we do not implement
        WHEN it initialises
        THEN the server answers its newest supported version
        """
        response = self.mcp.rpc('initialize', {'protocolVersion': '2026-07-28', 'capabilities': {},
                                               'clientInfo': {'name': 't', 'version': '0'}}, version='')
        self.assertEqual(result_of(response)['protocolVersion'], SUPPORTED_VERSIONS[0])

    def test_get_opens_no_stream(self):
        """
        GIVEN a valid token
        WHEN the endpoint is GET with Accept text/event-stream
        THEN 405 with Allow: POST
        """
        response = self.client.get('/mcp', HTTP_ACCEPT='text/event-stream',
                                   HTTP_AUTHORIZATION=f'Bearer {self.mcp.token}')
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response['Allow'], 'POST')
        self.assertEqual(self.client.delete('/mcp', HTTP_AUTHORIZATION=f'Bearer {self.mcp.token}').status_code, 405)

    def test_notification_is_accepted_without_a_body(self):
        """
        GIVEN notifications/initialized
        WHEN it is POSTed
        THEN 202 with an empty body
        """
        response = self.mcp.post({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.content, b'')

    def test_unsupported_protocol_version_header(self):
        """
        GIVEN MCP-Protocol-Version: 2026-07-28
        WHEN any request is made
        THEN 400 with a JSON-RPC error listing the supported versions
        """
        response = self.mcp.rpc('ping', version='2026-07-28')
        self.assertEqual(response.status_code, 400)
        error = response.json()['error']
        self.assertEqual(error['code'], UNSUPPORTED_VERSION)
        self.assertEqual(error['data']['supported'], ['2025-11-25', '2025-06-18', '2025-03-26'])
        self.assertEqual(error['data']['requested'], '2026-07-28')

    def test_missing_header_is_the_oldest_version(self):
        """
        GIVEN no MCP-Protocol-Version header
        WHEN ping is POSTed
        THEN it is answered (assumed 2025-03-26)
        """
        self.assertEqual(result_of(self.mcp.rpc('ping', version='')), {})

    def test_modern_discovery_probe_is_method_not_found(self):
        """
        GIVEN a 2026-07-28 client probing server/discover
        WHEN it is POSTed
        THEN the JSON-RPC error -32601 tells it to fall back to initialize
        """
        response = self.mcp.rpc('server/discover')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['error']['code'], METHOD_NOT_FOUND)

    def test_trailing_slash_is_not_redirected(self):
        """
        GIVEN a client that typed /mcp/
        WHEN it POSTs initialize there
        THEN 200, not a 301 that would lose the POST
        """
        response = self.mcp.initialize(path='/mcp/')
        self.assertEqual(response.status_code, 200)

    def test_lists_clients_call_anyway_are_empty(self):
        """
        GIVEN resources/list, resources/templates/list and prompts/list
        WHEN they are called
        THEN each answers an empty list
        """
        self.assertEqual(result_of(self.mcp.rpc('resources/list')), {'resources': []})
        self.assertEqual(result_of(self.mcp.rpc('resources/templates/list')), {'resourceTemplates': []})
        self.assertEqual(result_of(self.mcp.rpc('prompts/list')), {'prompts': []})

    def test_parse_error_and_bad_params(self):
        """
        GIVEN a body that is not JSON, then a request whose params is a string
        WHEN POSTed
        THEN 400 -32700, then -32602
        """
        response = self.mcp.post('{not json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error']['code'], PARSE_ERROR)
        response = self.mcp.post({'jsonrpc': '2.0', 'id': 7, 'method': 'tools/call', 'params': 'x'})
        self.assertEqual(response.json()['error']['code'], INVALID_PARAMS)
        self.assertEqual(response.json()['id'], 7)

    def test_batch_for_old_clients(self):
        """
        GIVEN a 2025-03-26 client sending a batch of two requests and a notification
        WHEN POSTed
        THEN a list of two responses in order
        """
        body = [rpc('ping', id=1), {'jsonrpc': '2.0', 'method': 'notifications/initialized'}, rpc('tools/list', id=2)]
        response = self.mcp.post(body, version='2025-03-26')
        self.assertEqual(response.status_code, 200)
        answers = response.json()
        self.assertEqual([a['id'] for a in answers], [1, 2])
        self.assertIn('tools', answers[1]['result'])
