"""`mcp-server` (change api-v2-structure, #412 PR 2): group, copy, move, version
and icon tools over the services and checks REST uses."""
from django.test import TestCase

from survey.models import Answer, Question, QuestionGroup, SurveyHeader, SurveySection, SurveySession

from api import scopes
from .helpers import LOCMEM, MCP_SETTINGS, McpClient, data_of, error_of, make_pro_org, make_v1_survey, mint


def _q(section, code, order, input_type='text_line', **kw):
    return Question.objects.create(survey_section=section, code=code, name=code, order_number=order,
                                   input_type=input_type, **kw)


@LOCMEM
@MCP_SETTINGS
class StructureToolsTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner)
        self.mcp = McpClient(self.client, mint(self.owner)[0])
        self.mcp.initialize()
        self.ref = {'survey': str(self.survey.uuid)}

    def test_update_section_layout(self):
        """
        GIVEN a section
        WHEN update_section sets layout image with the panel on the right at half width
        THEN the section stores them and the result shows them
        """
        result = data_of(self.mcp.call('update_section', {**self.ref, 'section_id': self.section.pk,
                                                          'layout': 'image', 'panel_side': 'right',
                                                          'panel_width': 'half', 'content_width': 'column',
                                                          'content_valign': 'middle', 'keep_panel_open': True}))
        self.assertIs(result['keep_panel_open'], True)
        self.assertEqual((result['layout'], result['panel_side'], result['panel_width']), ('image', 'right', 'half'))
        self.assertEqual((result['content_width'], result['content_valign']), ('column', 'middle'))
        self.section.refresh_from_db()
        self.assertEqual((self.section.panel_width, self.section.content_valign), ('half', 'middle'))

    def test_group_questions_from_a_chat(self):
        """
        GIVEN three questions
        WHEN create_group is called with their ids, then update_group keeps two of them
        THEN the group holds them in order and get_survey shows it; the left-out one is ungrouped
        """
        qs = [_q(self.section, f'Q{i}', i) for i in range(3)]
        group = data_of(self.mcp.call('create_group', {**self.ref, 'section_id': self.section.pk,
                                                       'title': 'About you', 'question_ids': [q.pk for q in qs]}))
        self.assertEqual(group['question_ids'], [q.pk for q in qs])
        detail = data_of(self.mcp.call('get_survey', self.ref))
        self.assertEqual([g['id'] for g in detail['sections'][0]['groups']], [group['id']])
        data_of(self.mcp.call('update_group', {**self.ref, 'group_id': group['id'],
                                               'question_ids': [qs[0].pk, qs[1].pk]}))
        qs[2].refresh_from_db()
        self.assertIsNone(qs[2].group_id)
        listed = data_of(self.mcp.call('list_groups', {**self.ref, 'section_id': self.section.pk}))['items']
        self.assertEqual(listed[0]['question_ids'], [qs[0].pk, qs[1].pk])

    def test_delete_group_with_questions_needs_confirmation(self):
        """
        GIVEN a group with one question
        WHEN delete_group is called with with_questions and no confirm, then with confirm
        THEN the first is confirmation_required and nothing is gone; the second deletes both;
             deleting another group without with_questions needs no confirm and keeps its question
        """
        q = _q(self.section, 'Q1', 1)
        group = data_of(self.mcp.call('create_group', {**self.ref, 'section_id': self.section.pk,
                                                       'title': 'G', 'question_ids': [q.pk]}))
        error = error_of(self.mcp.call('delete_group', {**self.ref, 'group_id': group['id'], 'with_questions': True}))
        self.assertEqual(error['error'], 'confirmation_required')
        self.assertTrue(Question.objects.filter(pk=q.pk).exists())
        data_of(self.mcp.call('delete_group', {**self.ref, 'group_id': group['id'], 'with_questions': True,
                                               'confirm': True}))
        self.assertFalse(Question.objects.filter(pk=q.pk).exists())
        kept = _q(self.section, 'Q2', 2)
        other = data_of(self.mcp.call('create_group', {**self.ref, 'section_id': self.section.pk,
                                                       'title': 'H', 'question_ids': [kept.pk]}))
        data_of(self.mcp.call('delete_group', {**self.ref, 'group_id': other['id']}))
        self.assertTrue(Question.objects.filter(pk=kept.pk, group__isnull=True).exists())
        self.assertFalse(QuestionGroup.objects.filter(pk=other['id']).exists())

    def test_copies_and_whole_survey(self):
        """
        GIVEN a question in this survey and a second survey of the same owner
        WHEN the question and section are duplicated, the question is copied into the other survey,
             and the survey is duplicated
        THEN each returns the new object; the survey copy is an unpublished "(copy)" with the structure
        """
        q = _q(self.section, 'Q1', 1)
        dup = data_of(self.mcp.call('duplicate_question', {**self.ref, 'question_id': q.pk}))
        self.assertEqual(dup['name'], 'Q1 (copy)')
        sec = data_of(self.mcp.call('duplicate_section', {**self.ref, 'section_id': self.section.pk}))
        self.assertEqual(sec['title'], 'Section 1 (copy)')
        other, other_section = make_v1_survey(self.org, self.owner, name='other')
        copied = data_of(self.mcp.call('copy_question', {'survey': str(other.uuid), 'section_id': other_section.pk,
                                                         'source_question_id': q.pk}))
        self.assertEqual(copied['section_id'], other_section.pk)
        data_of(self.mcp.call('copy_section', {'survey': str(other.uuid), 'source_section_id': self.section.pk}))
        self.assertEqual(SurveySection.objects.filter(survey_header=other).count(), 2)
        whole = data_of(self.mcp.call('duplicate_survey', self.ref))
        self.assertEqual((whole['name'], whole['status'], whole['sections']), ('v1_survey (copy)', 'draft', 2))
        self.assertTrue(SurveyHeader.objects.filter(uuid=whole['uuid']).exists())

    def test_move_reports_answer_loss_and_broken_rules(self):
        """
        GIVEN an answered text question, a point question and a second section
        WHEN move_question sends the text question into the pop-up without acknowledgement, then moves
             a controller below its dependent
        THEN the first is answers_at_risk; the second succeeds and names the cleared rule
        """
        text = _q(self.section, 'T', 1)
        point = _q(self.section, 'P', 2, 'point')
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=session, question=text, text='x')
        error = error_of(self.mcp.call('move_question', {**self.ref, 'question_id': text.pk, 'parent_id': point.pk}))
        self.assertEqual(error['error'], 'answers_at_risk')
        controller = _q(self.section, 'C', 3, 'choice', choices=[{'code': 1, 'name': 'Yes'}])
        _q(self.section, 'D', 4, visibility_rule={'question_code': 'C', 'choice_codes': [1]})
        second = SurveySection.objects.create(survey_header=self.survey, name='s2', title='Two', code='S2',
                                              prev_section=self.section)
        self.section.next_section = second
        self.section.save(update_fields=['next_section'])
        with self.settings(CONDITIONAL_VISIBILITY=True):
            moved = data_of(self.mcp.call('move_question', {**self.ref, 'question_id': controller.pk,
                                                            'section_id': second.pk}))
        self.assertEqual(moved['question']['section_id'], second.pk)
        self.assertEqual(moved['removed_rules'], ['D'])

    def test_versions_and_restore(self):
        """
        GIVEN a published survey at version 2 with archived version 1
        WHEN list_versions and restore_version are called
        THEN versions are [2 current, 1]; the restore returns an unpublished-changes uuid without confirm
        """
        self.survey.status = 'published'
        self.survey.version_number = 2
        self.survey.save(update_fields=['status', 'version_number'])
        archived = SurveyHeader.objects.create(organization=self.org, name='v1_survey', status='closed',
                                               canonical_survey=self.survey, is_canonical=False, version_number=1)
        SurveySection.objects.create(survey_header=archived, name='old', title='Old', code='S1', is_head=True)
        versions = data_of(self.mcp.call('list_versions', self.ref))['items']
        self.assertEqual([(v['version'], v['current']) for v in versions], [(2, True), (1, False)])
        restored = data_of(self.mcp.call('restore_version', {**self.ref, 'version': 1}))
        draft = SurveyHeader.objects.get(uuid=restored['unpublished_changes'])
        self.assertEqual(SurveySection.objects.get(survey_header=draft).title, 'Old')

    def test_search_icons_then_set_it(self):
        """
        GIVEN the icon catalog
        WHEN search_icons looks for "bus stop" and the first value is set as a point question's icon_class
        THEN the value is maki:bus and update_question accepts it
        """
        point = _q(self.section, 'P', 1, 'point')
        items = data_of(self.mcp.call('search_icons', {'q': 'bus stop'}))['items']
        self.assertEqual(items[0]['value'], 'maki:bus')
        updated = data_of(self.mcp.call('update_question', {**self.ref, 'question_id': point.pk,
                                                            'icon_class': items[0]['value']}))
        self.assertEqual(updated['icon_class'], 'maki:bus')

    def test_read_only_token_lists_only_read_tools(self):
        """
        GIVEN a token with surveys:read only
        WHEN tools/list is asked
        THEN list_groups, list_versions and search_icons are offered and no structure write tool is
        """
        reader = McpClient(self.client, mint(self.owner, scopes_=(scopes.SURVEYS_READ,))[0])
        reader.initialize()
        names = set(reader.tools())
        self.assertTrue({'list_groups', 'list_versions', 'search_icons'} <= names)
        self.assertFalse({'create_group', 'move_question', 'duplicate_survey', 'restore_version'} & names)
