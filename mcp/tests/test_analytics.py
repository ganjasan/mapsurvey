"""`mcp-server`: the PostHog MCP Analytics events and the client context in the session id
(change `mcp-analytics-events`, #649)."""
import uuid
from unittest import mock

from django.core import signing
from django.test import SimpleTestCase, TestCase

from api import scopes

from .. import analytics, sessions
from .helpers import LOCMEM, MCP_SETTINGS, McpClient, data_of, error_of, make_pro_org, make_v1_survey, mint, rpc

FORBIDDEN_KEYS = ('$mcp_parameters', '$mcp_response', '$mcp_intent')


def events(emit, name):
    """Properties of every `name` event the mocked `product_events.emit` received."""
    return [c.args[2] for c in emit.call_args_list if c.args[0] == name]


class SessionContextTest(SimpleTestCase):
    def test_client_context_round_trips(self):
        """
        GIVEN a session id issued with clientInfo and a protocol version
        WHEN it is verified under the same token
        THEN the session carries the trimmed name, version, protocol version and the issue time
        """
        sid = sessions.issue(7, client={'name': '  claude-code ', 'version': '2.1.0'}, protocol_version='2025-11-25')
        session = sessions.verify(sid, 7)
        self.assertEqual((session.client_name, session.client_version), ('claude-code', '2.1.0'))
        self.assertEqual(session.protocol_version, '2025-11-25')
        self.assertIsInstance(session.issued_ms, int)

    def test_client_strings_are_capped_and_non_strings_dropped(self):
        """
        GIVEN clientInfo with an over-long name and a numeric version
        WHEN the session id is issued and verified
        THEN the name is cut to its cap and the version is empty
        """
        session = sessions.verify(sessions.issue(7, client={'name': 'x' * 500, 'version': 3}), 7)
        self.assertEqual(len(session.client_name), sessions.CLIENT_NAME_MAX)
        self.assertEqual(session.client_version, '')

    def test_session_id_from_before_the_change_verifies(self):
        """
        GIVEN a session id signed with only token id and nonce
        WHEN it is verified
        THEN it verifies, with no issue time, no client context and no analytics id
        """
        old = signing.dumps({'t': 7, 'n': 'abc'}, salt=sessions.SALT, compress=False)
        session = sessions.verify(old, 7)
        self.assertEqual(session.nonce, 'abc')
        self.assertIsNone(session.issued_ms)
        self.assertEqual(session.client_name, '')
        self.assertIsNone(session.analytics_id())

    def test_analytics_id_is_a_stable_uuid7_per_session(self):
        """
        GIVEN two session ids
        WHEN each is verified twice
        THEN one session always yields the same UUIDv7 and the two sessions differ
        """
        a, b = sessions.issue(7), sessions.issue(7)
        first = sessions.verify(a, 7).analytics_id()
        self.assertEqual(first, sessions.verify(a, 7).analytics_id())
        self.assertNotEqual(first, sessions.verify(b, 7).analytics_id())
        parsed = uuid.UUID(first)
        self.assertEqual(parsed.version, 7)
        self.assertEqual(parsed.variant, uuid.RFC_4122)
        self.assertEqual(parsed.int >> 80, sessions.verify(a, 7).issued_ms)

    def test_error_type_map(self):
        """
        GIVEN our outcome codes
        WHEN each is mapped
        THEN permission, rate limit, validation, missing context and internal get their buckets; others api_4xx
        """
        expected = {
            'scope_missing': 'permission', 'forbidden_role': 'permission', 'pro_required': 'permission',
            'rate_limited': 'rate_limited', 'invalid_arguments': 'validation', 'validation': 'validation',
            'confirmation_required': 'missing_context', 'server_error': 'internal',
            'not_found': 'api_4xx', 'draft_required': 'api_4xx',
        }
        self.assertEqual({code: analytics.error_type(code) for code in expected}, expected)


@LOCMEM
@MCP_SETTINGS
class McpAnalyticsEventsTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner)
        token, self.profile = mint(self.owner)
        self.mcp = McpClient(self.client, token)
        self.ref = {'survey': str(self.survey.uuid)}
        patcher = mock.patch('survey.product_events.emit')
        self.emit = patcher.start()
        self.addCleanup(patcher.stop)

    def assert_no_content(self, props, *values):
        for key in FORBIDDEN_KEYS:
            self.assertNotIn(key, props)
        for value in values:
            self.assertNotIn(value, repr(props))

    def test_initialize_event_and_client_on_later_calls(self):
        """
        GIVEN a client that initialises with clientInfo claude-code 2.1.0
        WHEN it then calls get_survey with the returned session id
        THEN $mcp_initialize and $mcp_tool_call both name that client and share one $session_id
        """
        self.mcp.post(rpc('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {},
                                         'clientInfo': {'name': 'claude-code', 'version': '2.1.0'}}))
        init = events(self.emit, analytics.INITIALIZE)
        self.assertEqual(len(init), 1)
        self.assertEqual(init[0]['$mcp_client_name'], 'claude-code')
        self.assertEqual(init[0]['$mcp_protocol_version'], '2025-11-25')
        self.assertEqual(init[0]['$mcp_server_name'], 'mapsurvey')
        self.assertEqual(init[0]['$mcp_source'], analytics.SOURCE)

        response = self.mcp.initialize()   # McpClient keeps this session id
        sid = response['Mcp-Session-Id']
        self.emit.reset_mock()
        data_of(self.mcp.call('get_survey', self.ref, session=sid))
        data_of(self.mcp.call('get_survey', self.ref, session=sid))
        calls = events(self.emit, analytics.TOOL_CALL)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]['$mcp_client_name'], 'tests')
        self.assertEqual(calls[0]['$session_id'], calls[1]['$session_id'])
        self.assertEqual(calls[0]['$session_id'], sessions.verify(sid, self.profile.token_id).analytics_id())

    def test_successful_call(self):
        """
        GIVEN an initialised session
        WHEN get_survey succeeds
        THEN $mcp_tool_call has the tool name, is_error false, a duration, no error type, no content
        """
        self.mcp.initialize()
        data_of(self.mcp.call('get_survey', self.ref))
        (props,) = events(self.emit, analytics.TOOL_CALL)
        self.assertEqual(props['$mcp_tool_name'], 'get_survey')
        self.assertIs(props['$mcp_is_error'], False)
        self.assertIsInstance(props['$mcp_duration_ms'], float)
        self.assertNotIn('$mcp_error_type', props)
        self.assertIn('$session_id', props)
        self.assert_no_content(props, str(self.survey.uuid))

    def test_refusal_is_missing_context_with_status(self):
        """
        GIVEN delete_survey without confirm
        WHEN the call is refused with confirmation_required
        THEN $mcp_tool_call is an error of type missing_context with the envelope's status and code, no uuid
        """
        envelope = error_of(self.mcp.call('delete_survey', self.ref))
        self.assertEqual(envelope['error'], 'confirmation_required')
        (props,) = events(self.emit, analytics.TOOL_CALL)
        self.assertIs(props['$mcp_is_error'], True)
        self.assertEqual(props['$mcp_error_type'], 'missing_context')
        self.assertEqual(props['$mcp_error_message'], 'confirmation_required')
        self.assertIsInstance(props['$mcp_error_status'], int)
        self.assert_no_content(props, str(self.survey.uuid))
        self.assertEqual(len(events(self.emit, 'mcp_tool_called')), 1)

    def test_schema_failure_keeps_argument_values_out(self):
        """
        GIVEN update_survey with an unknown field carrying a distinctive string
        WHEN the arguments fail the schema
        THEN $mcp_tool_call is a validation error and the string is in no emitted event
        """
        marker = 'ZEBRA-7731-secret'
        response = self.mcp.call('update_survey', {**self.ref, 'bogus_field': marker})
        self.assertEqual(response.json()['error']['code'], -32602)
        (props,) = events(self.emit, analytics.TOOL_CALL)
        self.assertEqual(props['$mcp_error_type'], 'validation')
        self.assertNotIn('$mcp_error_status', props)
        for call in self.emit.call_args_list:
            self.assertNotIn(marker, repr(call))

    def test_missing_scope_is_permission(self):
        """
        GIVEN a read-only token
        WHEN it calls create_section anyway
        THEN $mcp_tool_call is an error of type permission
        """
        reader = McpClient(self.client, mint(self.owner, scopes_=(scopes.SURVEYS_READ,))[0])
        self.assertEqual(error_of(reader.call('create_section', {**self.ref, 'title': 'A'}))['error'],
                         'scope_missing')
        (props,) = events(self.emit, analytics.TOOL_CALL)
        self.assertEqual(props['$mcp_error_type'], 'permission')

    def test_unknown_tool_emits_nothing(self):
        """
        GIVEN a tool name that is not registered
        WHEN it is called
        THEN no $mcp_tool_call is emitted
        """
        self.mcp.call('no_such_tool')
        self.assertEqual(events(self.emit, analytics.TOOL_CALL), [])

    def test_tools_list_names_what_the_token_sees(self):
        """
        GIVEN a read-only token
        WHEN it calls tools/list
        THEN $mcp_tools_list lists exactly the names in the response and tool_count is their number
        """
        reader = McpClient(self.client, mint(self.owner, scopes_=(scopes.SURVEYS_READ,))[0])
        names = reader.tools()
        (props,) = events(self.emit, analytics.TOOLS_LIST)
        self.assertEqual(props['$mcp_listed_tool_names'], names)
        self.assertEqual(props['tool_count'], len(names))
        self.assertNotIn('create_section', names)

    def test_harness_headers(self):
        """
        GIVEN a request with a Claude Code user agent and the x-anthropic-client header
        WHEN a tool is called
        THEN the event carries both, and a request without a session id has no $session_id
        """
        data_of(self.mcp.call('get_survey', self.ref, HTTP_USER_AGENT='claude-code/2.1.0 (cli)',
                              HTTP_X_ANTHROPIC_CLIENT='ClaudeCode'))
        (props,) = events(self.emit, analytics.TOOL_CALL)
        self.assertEqual(props['$mcp_client_user_agent'], 'claude-code/2.1.0 (cli)')
        self.assertEqual(props['$mcp_vendor_client'], 'ClaudeCode')
        self.assertNotIn('$session_id', props)
        self.assertNotIn('$mcp_client_name', props)
