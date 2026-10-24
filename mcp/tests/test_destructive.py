"""`mcp-server`: what cannot be undone asks first."""
from unittest import mock

from django.test import TestCase

from survey.models import Answer, Question, SurveyHeader, SurveySession

from .helpers import LOCMEM, MCP_SETTINGS, McpClient, data_of, error_of, make_pro_org, make_v1_survey, mint


def _answered_session(survey, question, kind='external'):
    session = SurveySession.objects.create(survey=survey, opened_by_kind=kind)
    Answer.objects.create(survey_session=session, question=question, text='hello')
    return session


@LOCMEM
@MCP_SETTINGS
class DestructiveTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner)
        self.question = Question.objects.create(survey_section=self.section, name='Q', input_type='text', order_number=1)
        self.mcp = McpClient(self.client, mint(self.owner)[0])
        self.mcp.initialize()
        self.ref = {'survey': str(self.survey.uuid)}

    def test_delete_without_confirm(self):
        """
        GIVEN a survey
        WHEN delete_survey is called without confirm
        THEN confirmation_required and the survey is untouched
        """
        envelope = error_of(self.mcp.call('delete_survey', self.ref))
        self.assertEqual(envelope['error'], 'confirmation_required')
        self.assertIsNone(SurveyHeader.objects.get(pk=self.survey.pk).deleted_at)

    def test_delete_with_responses_is_refused_with_the_count(self):
        """
        GIVEN three answered external sessions, one empty external and one answered preview session
        WHEN delete_survey is called with confirm
        THEN has_responses with count 3 and the survey is untouched
        """
        for _ in range(3):
            _answered_session(self.survey, self.question)
        SurveySession.objects.create(survey=self.survey, opened_by_kind='external')
        _answered_session(self.survey, self.question, kind='preview')
        envelope = error_of(self.mcp.call('delete_survey', {**self.ref, 'confirm': True}))
        self.assertEqual(envelope['error'], 'has_responses')
        self.assertEqual(envelope['count'], 3)
        self.assertIsNone(SurveyHeader.objects.get(pk=self.survey.pk).deleted_at)

    def test_delete_with_confirm_trashes(self):
        """
        GIVEN a survey nobody answered
        WHEN delete_survey is called with confirm
        THEN it is in the trash and list_surveys no longer shows it
        """
        data = data_of(self.mcp.call('delete_survey', {**self.ref, 'confirm': True}))
        self.assertTrue(data['deleted'])
        self.assertIsNotNone(SurveyHeader.objects.get(pk=self.survey.pk).deleted_at)
        self.assertEqual(data_of(self.mcp.call('list_surveys'))['items'], [])

    def test_unpublished_changes_are_discarded_in_one_step(self):
        """
        GIVEN a published survey with unpublished changes
        WHEN discard_unpublished_changes is called
        THEN the copy is gone and the live survey stays
        """
        live, _ = make_v1_survey(self.org, self.owner, 'live', status='published')
        draft = data_of(self.mcp.call('start_unpublished_changes', {'survey': str(live.uuid)}))
        data = data_of(self.mcp.call('discard_unpublished_changes', {'survey': str(live.uuid)}))
        self.assertEqual(data['live_survey'], str(live.uuid))
        self.assertFalse(SurveyHeader.objects.filter(uuid=draft['uuid']).exists())
        self.assertEqual(SurveyHeader.objects.get(pk=live.pk).status, 'published')

    def test_publish_needs_confirm_and_screens(self):
        """
        GIVEN an unpublished survey
        WHEN publish_survey is called without confirm, then with it
        THEN confirmation_required first; then screen_survey ran and the survey is published
        """
        envelope = error_of(self.mcp.call('publish_survey', self.ref))
        self.assertEqual(envelope['error'], 'confirmation_required')
        self.assertEqual(SurveyHeader.objects.get(pk=self.survey.pk).status, 'draft')
        with mock.patch('survey.services.publishing.screen_survey') as screen:
            data = data_of(self.mcp.call('publish_survey', {**self.ref, 'confirm': True}))
        screen.assert_called_once()
        self.assertEqual(data['status'], 'published')
        self.assertEqual(SurveyHeader.objects.get(pk=self.survey.pk).status, 'published')

    def test_publish_unpublished_changes_needs_confirm(self):
        """
        GIVEN a published survey with unpublished changes
        WHEN publish_unpublished_changes is called without confirm, then with it
        THEN confirmation_required first; then the live survey carries the new version
        """
        live, _ = make_v1_survey(self.org, self.owner, 'live', status='published')
        data_of(self.mcp.call('start_unpublished_changes', {'survey': str(live.uuid)}))
        envelope = error_of(self.mcp.call('publish_unpublished_changes', {'survey': str(live.uuid)}))
        self.assertEqual(envelope['error'], 'confirmation_required')
        data = data_of(self.mcp.call('publish_unpublished_changes', {'survey': str(live.uuid), 'confirm': True}))
        self.assertEqual(data['uuid'], str(live.uuid))
        self.assertIsNone(data['unpublished_changes'])
        self.assertEqual(SurveyHeader.objects.get(pk=live.pk).version_number, 2)

    def test_close_survey(self):
        """
        GIVEN a published survey
        WHEN close_survey is called
        THEN it is closed
        """
        live, _ = make_v1_survey(self.org, self.owner, 'live', status='published')
        self.assertEqual(data_of(self.mcp.call('close_survey', {'survey': str(live.uuid)}))['status'], 'closed')
