"""`mcp-server`: per-token windows shared with REST, the per-session cap, the event."""
from unittest import mock

from django.test import TestCase, override_settings

from survey import product_events as pe

from .helpers import LOCMEM, MCP_SETTINGS, McpClient, data_of, error_of, make_pro_org, make_v1_survey, mint


@LOCMEM
@MCP_SETTINGS
class LimitsTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner)
        self.mcp = McpClient(self.client, mint(self.owner)[0])
        self.ref = {'survey': str(self.survey.uuid)}

    @override_settings(API_RATE_LIMITS={'mcp.session': (2, 600)})
    def test_session_cap_is_per_session(self):
        """
        GIVEN a session cap of two tool calls
        WHEN a session makes three calls, then a fresh session one more
        THEN the third is rate_limited with limit mcp.session and retry_after; the fresh session is served
        """
        self.mcp.initialize()
        data_of(self.mcp.call('get_survey', self.ref))
        data_of(self.mcp.call('get_survey', self.ref))
        envelope = error_of(self.mcp.call('get_survey', self.ref))
        self.assertEqual(envelope['error'], 'rate_limited')
        self.assertEqual(envelope['limit'], 'mcp.session')
        self.assertGreater(envelope['retry_after'], 0)
        self.mcp.initialize()
        data_of(self.mcp.call('get_survey', self.ref))

    @override_settings(API_RATE_LIMITS={'api.write': (1, 60)})
    def test_reads_do_not_consume_the_write_window(self):
        """
        GIVEN a write window of one per minute
        WHEN two reads and two section creates are made
        THEN both reads pass; the second create is rate_limited on api.write
        """
        data_of(self.mcp.call('get_survey', self.ref))
        data_of(self.mcp.call('get_survey', self.ref))
        data_of(self.mcp.call('create_section', {**self.ref, 'title': 'A'}))
        envelope = error_of(self.mcp.call('create_section', {**self.ref, 'title': 'B'}))
        self.assertEqual(envelope['error'], 'rate_limited')
        self.assertEqual(envelope['limit'], 'api.write')

    @override_settings(API_RATE_LIMITS={'api.read': (1, 60)})
    def test_protocol_methods_count_as_reads_and_answer_429(self):
        """
        GIVEN a read window of one per minute
        WHEN tools/list is called twice
        THEN the second is HTTP 429 with a JSON-RPC error naming rate_limited and Retry-After
        """
        self.assertEqual(self.mcp.rpc('tools/list').status_code, 200)
        response = self.mcp.rpc('tools/list')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()['error']['data']['error'], 'rate_limited')
        self.assertTrue(response['Retry-After'])

    def test_event_names_tool_and_outcome_only(self):
        """
        GIVEN delete_survey without confirm
        WHEN the call is refused
        THEN one mcp_tool_called with tool, outcome confirmation_required, token id and kind -- no uuid
        """
        with mock.patch('survey.product_events.emit') as emit:
            self.mcp.call('delete_survey', self.ref)
        calls = [c for c in emit.call_args_list if c.args[0] == pe.MCP_TOOL_CALLED]
        self.assertEqual(len(calls), 1)
        props = calls[0].args[2]
        self.assertEqual(props['tool'], 'delete_survey')
        self.assertEqual(props['outcome'], 'confirmation_required')
        self.assertEqual(props['kind'], 'personal')
        self.assertIn('token_id', props)
        self.assertNotIn(str(self.survey.uuid), repr(props))

    def test_unexpected_error_is_an_envelope_without_a_trace(self):
        """
        GIVEN a handler that raises
        WHEN the tool is called
        THEN isError server_error with no traceback, PostHog captured, event outcome server_error
        """
        with mock.patch('mcp.tools.surveys.out.survey_detail', side_effect=RuntimeError('SurveyHeader boom')), \
                mock.patch('mcp.protocol._capture') as capture, mock.patch('survey.product_events.emit') as emit:
            response = self.mcp.call('get_survey', self.ref)
        envelope = error_of(response)
        self.assertEqual(envelope['error'], 'server_error')
        self.assertNotIn(b'Traceback', response.content)
        self.assertNotIn(b'SurveyHeader', response.content)
        capture.assert_called_once()
        self.assertEqual(emit.call_args.args[2]['outcome'], 'server_error')
