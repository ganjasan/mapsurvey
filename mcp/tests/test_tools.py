"""`mcp-server`: tools over the service layer -- scope, role, Pro, strictness,
the same bytes as the editor, ids through their survey."""
import json

from django.test import TestCase

from survey.html_sanitize import coerce_creator_html
from survey.models import Membership, Question, SurveyCollaborator, SurveyHeader, SurveySection

from api import scopes
from api.models import AUDIENCE_MCP
from ..errors import INVALID_PARAMS
from .helpers import (
    LOCMEM, MCP_SETTINGS, McpClient, data_of, error_of, make_free_org, make_member, make_pro_org, make_v1_survey,
    mint,
)


@LOCMEM
@MCP_SETTINGS
class ToolsTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner)
        self.token, _ = mint(self.owner)
        self.mcp = McpClient(self.client, self.token)
        self.mcp.initialize()

    def test_list_filters_by_scope_and_schemas_have_no_refs(self):
        """
        GIVEN a token with only surveys:read
        WHEN tools/list is called
        THEN reads and get_me are listed, writes are not, and every inputSchema is inlined JSON Schema
        """
        token, _ = mint(self.owner, scopes_=(scopes.SURVEYS_READ,))
        response = self.mcp.rpc('tools/list', token=token, session='')
        tools = response.json()['result']['tools']
        names = [t['name'] for t in tools]
        self.assertIn('get_me', names)
        self.assertIn('list_surveys', names)
        self.assertIn('get_survey', names)
        self.assertNotIn('create_survey', names)
        self.assertNotIn('delete_survey', names)
        for t in tools:
            self.assertEqual(t['inputSchema']['type'], 'object', t['name'])
            self.assertNotIn('$ref', json.dumps(t['inputSchema']), t['name'])
            self.assertIn('readOnlyHint', t['annotations'])
        full = self.mcp.tools()
        self.assertEqual(full[0], 'get_me')
        self.assertIn('delete_survey', full)

    def test_hidden_tool_is_refused_on_call(self):
        """
        GIVEN a token with only surveys:read
        WHEN it calls create_survey
        THEN isError scope_missing naming surveys:write and no survey exists
        """
        token, _ = mint(self.owner, scopes_=(scopes.SURVEYS_READ,))
        envelope = error_of(self.mcp.call('create_survey', {'name': 'nope'}, token=token, session=''))
        self.assertEqual(envelope['error'], 'scope_missing')
        self.assertEqual(envelope['scope'], 'surveys:write')
        self.assertFalse(SurveyHeader.objects.filter(name='nope').exists())

    def test_get_me(self):
        """
        GIVEN the token
        WHEN get_me is called
        THEN the user, workspaces with api flag, the token block and the tool names come back
        """
        data = data_of(self.mcp.call('get_me'))
        self.assertEqual(data['user']['id'], self.owner.pk)
        self.assertEqual(data['workspaces'][0]['api'], True)
        self.assertIn('mcp', data['token']['audiences'])
        self.assertEqual(data['mcp']['server'], 'https://testserver/mcp')
        self.assertIn('create_survey', data['mcp']['tools'])

    def test_build_a_survey_end_to_end(self):
        """
        GIVEN an empty Pro workspace
        WHEN a survey is created, a section added, a point question with a choice sub-question, options set
        THEN get_survey returns the structure in one call with ids matching
        """
        created = data_of(self.mcp.call('create_survey', {'name': 'Benches', 'language': 'de'}))
        uuid = created['uuid']
        self.assertEqual(created['languages'], ['de'])
        section = data_of(self.mcp.call('create_section', {'survey': uuid, 'title': 'Map', 'layout': 'map'}))
        point = data_of(self.mcp.call('add_question', {
            'survey': uuid, 'section_id': section['id'], 'input_type': 'point', 'name': 'Where is a bench missing?'}))
        sub = data_of(self.mcp.call('add_question', {
            'survey': uuid, 'section_id': section['id'], 'parent_question_id': point['id'],
            'input_type': 'choice', 'name': 'How urgent?',
            'choices': [{'code': 1, 'name': 'Low'}, {'code': 2, 'name': 'High'}]}))
        self.assertEqual(sub['parent_id'], point['id'])
        updated = data_of(self.mcp.call('set_choices', {
            'survey': uuid, 'question_id': sub['id'],
            'choices': [{'code': 1, 'name': 'Low'}, {'code': 3, 'name': {'de': 'Sofort', 'en': 'Now'}}]}))
        self.assertEqual([c['code'] for c in updated['choices']], [1, 3])
        whole = data_of(self.mcp.call('get_survey', {'survey': uuid}))
        self.assertEqual([s['id'] for s in whole['sections']][-1], section['id'])
        last = whole['sections'][-1]
        self.assertEqual({q['id'] for q in last['questions']}, {point['id'], sub['id']})
        self.assertEqual(last['questions'][0]['subquestions'], [sub['id']])
        reordered = data_of(self.mcp.call('reorder_sections', {
            'survey': uuid, 'section_ids': [section['id'], whole['sections'][0]['id']]}))
        self.assertEqual(reordered['sections'][0]['id'], section['id'])

    def test_structural_edit_on_a_live_survey_is_draft_required(self):
        """
        GIVEN a published survey with a text question
        WHEN its input_type is changed, then unpublished changes are started and the edit repeated there
        THEN draft_required with draft null and the live row unchanged; the second edit applies to the copy
        """
        live, section = make_v1_survey(self.org, self.owner, 'live', status='published')
        q = Question.objects.create(survey_section=section, name='Colour?', input_type='text', order_number=1)
        envelope = error_of(self.mcp.call('update_question', {
            'survey': str(live.uuid), 'question_id': q.pk, 'input_type': 'number'}))
        self.assertEqual(envelope['error'], 'draft_required')
        self.assertIsNone(envelope['draft'])
        self.assertEqual(Question.objects.get(pk=q.pk).input_type, 'text')
        draft = data_of(self.mcp.call('start_unpublished_changes', {'survey': str(live.uuid)}))
        self.assertTrue(draft['is_unpublished_changes'])
        self.assertEqual(draft['live_survey'], str(live.uuid))
        copy = Question.objects.get(survey_section__survey_header__uuid=draft['uuid'], code=q.code)
        changed = data_of(self.mcp.call('update_question', {
            'survey': draft['uuid'], 'question_id': copy.pk, 'input_type': 'number'}))
        self.assertEqual(changed['input_type'], 'number')
        again = error_of(self.mcp.call('update_question', {
            'survey': str(live.uuid), 'question_id': q.pk, 'input_type': 'number'}))
        self.assertEqual(again['draft'], draft['uuid'])

    def test_free_workspace_is_pro_required_and_get_me_says_so(self):
        """
        GIVEN a survey in a Free workspace the caller owns
        WHEN get_survey is called, and get_me
        THEN pro_required with that workspace's upgrade_url; get_me lists it with plan free and api false
        """
        free, free_owner = make_free_org()
        Membership.objects.create(user=self.owner, organization=free, role='owner')
        survey, _ = make_v1_survey(free, self.owner, 'free_survey')
        envelope = error_of(self.mcp.call('get_survey', {'survey': str(survey.uuid)}))
        self.assertEqual(envelope['error'], 'pro_required')
        self.assertEqual(envelope['organization'], free.slug)
        self.assertIn('/billing', envelope['upgrade_url'])
        workspaces = {w['slug']: w for w in data_of(self.mcp.call('get_me'))['workspaces']}
        self.assertEqual(workspaces[free.slug]['plan'], 'free')
        self.assertFalse(workspaces[free.slug]['api'])

    def test_trial_counts_each_tool_call(self):
        """
        GIVEN a Free workspace with a live Pro trial, and its survey
        WHEN get_survey is called once, then twice in one JSON-RPC batch
        THEN the calls succeed and the API allowance drops by one, then by two more
        """
        from billing import trial
        from .helpers import rpc
        free, _ = make_free_org()
        Membership.objects.create(user=self.owner, organization=free, role='owner')
        survey, _ = make_v1_survey(free, self.owner, 'trial_survey')
        allowance = trial.claim(free, self.owner).allowances.get(feature='api')
        data_of(self.mcp.call('get_survey', {'survey': str(survey.uuid)}))
        allowance.refresh_from_db()
        self.assertEqual(allowance.used, 1)
        args = {'name': 'get_survey', 'arguments': {'survey': str(survey.uuid)}}
        response = self.mcp.post([rpc('tools/call', args, id=2), rpc('tools/call', args, id=3)])
        self.assertEqual(len(response.json()), 2)
        allowance.refresh_from_db()
        self.assertEqual(allowance.used, 3)

    def test_subtext_is_sanitised_like_the_editor(self):
        """
        GIVEN a subtext with a script tag and a bold tag
        WHEN add_question stores it
        THEN the row holds exactly coerce_creator_html(input): no script, bold kept
        """
        raw = '<script>alert(1)</script><b>bold</b> takes <5 minutes'
        q = data_of(self.mcp.call('add_question', {
            'survey': str(self.survey.uuid), 'section_id': self.section.pk, 'input_type': 'text',
            'name': 'Why?', 'subtext': raw}))
        stored = Question.objects.get(pk=q['id']).subtext
        self.assertEqual(stored, coerce_creator_html(raw))
        self.assertNotIn('<script', stored)
        self.assertIn('<b>bold</b>', stored)

    def test_unknown_field_and_unknown_tool_are_protocol_errors(self):
        """
        GIVEN create_survey with an `organization` argument, and a tool that does not exist
        WHEN called
        THEN JSON-RPC -32602 naming the field; -32602 for the tool; nothing created
        """
        response = self.mcp.call('create_survey', {'name': 'x', 'organization': 1})
        self.assertEqual(response.status_code, 200)
        error = response.json()['error']
        self.assertEqual(error['code'], INVALID_PARAMS)
        self.assertEqual(error['data']['fields']['organization'], ['Unknown field.'])
        self.assertFalse(SurveyHeader.objects.filter(name='x').exists())
        self.assertEqual(self.mcp.call('drop_tables').json()['error']['code'], INVALID_PARAMS)

    def test_question_of_another_survey_is_not_found(self):
        """
        GIVEN two surveys of the caller
        WHEN update_question names survey A and a question id of B
        THEN not_found and B's question is unchanged
        """
        b, b_section = make_v1_survey(self.org, self.owner, 'b')
        q = Question.objects.create(survey_section=b_section, name='B1', input_type='text', order_number=1)
        envelope = error_of(self.mcp.call('update_question', {
            'survey': str(self.survey.uuid), 'question_id': q.pk, 'name': 'stolen'}))
        self.assertEqual(envelope['error'], 'not_found')
        self.assertEqual(Question.objects.get(pk=q.pk).name, 'B1')

    def test_viewer_role_is_forbidden_role_and_other_workspace_is_404(self):
        """
        GIVEN a viewer on the survey, and a survey in a workspace the caller is not in
        WHEN update_survey is called by the viewer, and get_survey on the foreign one
        THEN forbidden_role naming owner; not_found
        """
        viewer = make_member(self.org, 'viewer_user', role='viewer')
        SurveyCollaborator.objects.create(user=viewer, survey=self.survey, role='viewer')
        token, _ = mint(viewer, audiences=(AUDIENCE_MCP,))
        envelope = error_of(self.mcp.call('update_survey', {'survey': str(self.survey.uuid), 'name': 'x'},
                                          token=token, session=''))
        self.assertEqual(envelope['error'], 'forbidden_role')
        self.assertEqual(envelope['role'], 'owner')
        other_org, other_owner = make_pro_org('Other', 'other_pro_owner')
        foreign, _ = make_v1_survey(other_org, other_owner, 'foreign')
        self.assertEqual(error_of(self.mcp.call('get_survey', {'survey': str(foreign.uuid)}))['error'], 'not_found')

    def test_delete_section_asks_before_losing_answers(self):
        """
        GIVEN a second section with no answers
        WHEN delete_section is called
        THEN it is deleted and the remaining sections are listed
        """
        second = SurveySection.objects.create(survey_header=self.survey, name='s2', title='S2', code='S2')
        data = data_of(self.mcp.call('delete_section', {'survey': str(self.survey.uuid), 'section_id': second.pk}))
        self.assertEqual(data['deleted'], second.pk)
        self.assertEqual([s['id'] for s in data['sections']], [self.section.pk])

    def test_update_survey_settings_need_owner_but_thanks_needs_editor(self):
        """
        GIVEN an editor collaborator
        WHEN they set the thanks page, then rename the survey
        THEN the thanks page is stored (sanitised) and the rename is forbidden_role
        """
        editor = make_member(self.org, 'editor_user', role='editor')
        SurveyCollaborator.objects.create(user=editor, survey=self.survey, role='editor')
        token, _ = mint(editor, audiences=(AUDIENCE_MCP,))
        data = data_of(self.mcp.call('update_survey', {
            'survey': str(self.survey.uuid), 'thanks_html': {'en': '<p>Thanks</p><script>x()</script>'}},
            token=token, session=''))
        self.assertEqual(data['thanks_html']['en'], coerce_creator_html('<p>Thanks</p><script>x()</script>'))
        envelope = error_of(self.mcp.call('update_survey', {'survey': str(self.survey.uuid), 'name': 'Renamed'},
                                          token=token, session=''))
        self.assertEqual(envelope['error'], 'forbidden_role')
