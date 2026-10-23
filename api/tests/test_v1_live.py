"""`rest-api-v1`: live surveys -- content in place, structure via unpublished
changes, publish reports content review."""
from unittest import mock

from django.test import TestCase

from survey.models import AuditLog, ContentReview, Question, SurveyHeader, SurveySection

from .helpers import LOCMEM, V1Client, make_pro_org, make_v1_survey, mint


@LOCMEM
class V1LiveSurveyTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner, status='published')
        self.question = Question.objects.create(survey_section=self.section, name='Colour?', input_type='choice',
                                                order_number=1, choices=[{'code': 1, 'name': 'Red'}])
        self.token, _ = mint(self.owner)
        self.api = V1Client(self.client, self.token)
        self.base = f'/surveys/{self.survey.uuid}'

    def test_structural_edit_answers_draft_required(self):
        """
        GIVEN a published survey without unpublished changes
        WHEN a section is added through the API
        THEN 409 draft_required with draft null, and no section is created
        """
        response = self.api.post(f'{self.base}/sections', {})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error'], 'draft_required')
        self.assertIsNone(response.json()['draft'])
        self.assertEqual(SurveySection.objects.filter(survey_header=self.survey).count(), 1)

    def test_type_change_answers_draft_required(self):
        """
        GIVEN a published survey
        WHEN a question's input_type is patched
        THEN 409 draft_required naming the question type, and the type is unchanged
        """
        response = self.api.patch(f'{self.base}/questions/{self.question.pk}', {'input_type': 'text'})
        self.assertEqual(response.status_code, 409, response.content)
        self.assertIn('the question type', response.json()['reasons'])
        self.question.refresh_from_db()
        self.assertEqual(self.question.input_type, 'choice')

    def test_content_edit_applied_and_rescreened(self):
        """
        GIVEN a published survey
        WHEN a question's name is patched
        THEN it is stored and content screening runs with the live_edit trigger
        """
        with mock.patch('survey.services.locks.screen_survey') as screen:
            response = self.api.patch(f'{self.base}/questions/{self.question.pk}', {'name': 'Favourite colour?'})
        self.assertEqual(response.status_code, 200, response.content)
        self.question.refresh_from_db()
        self.assertEqual(self.question.name, 'Favourite colour?')
        screen.assert_called_once_with(self.survey, trigger='live_edit')

    def test_draft_flow(self):
        """
        GIVEN a published survey
        WHEN the caller starts unpublished changes, adds a section to them and publishes them
        THEN the live survey has two sections and version 2, with an audit row of the publish
        """
        draft = self.api.post(f'{self.base}/draft')
        self.assertEqual(draft.status_code, 201, draft.content)
        draft_uuid = draft.json()['uuid']
        self.assertTrue(draft.json()['is_unpublished_changes'])
        self.assertEqual(self.api.post(f'/surveys/{draft_uuid}/sections', {'title': 'More'}).status_code, 201)
        live = self.api.get(self.base).json()
        self.assertEqual(live['unpublished_changes'], draft_uuid)
        published = self.api.post(f'{self.base}/draft/publish', {})
        self.assertEqual(published.status_code, 200, published.content)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.version_number, 2)
        self.assertEqual(SurveySection.objects.filter(survey_header=self.survey).count(), 2)
        self.assertTrue(AuditLog.objects.filter(action='draft_publish', actor=self.owner).exists())

    def test_live_edit_refused_while_draft_exists(self):
        """
        GIVEN a published survey with unpublished changes
        WHEN the live survey's question is renamed
        THEN 409 draft_required carrying the draft's uuid
        """
        draft = self.api.post(f'{self.base}/draft').json()
        response = self.api.patch(f'{self.base}/questions/{self.question.pk}', {'name': 'x'})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['draft'], draft['uuid'])

    def test_publishing_a_draft_copy_directly_is_a_conflict(self):
        """
        GIVEN unpublished changes
        WHEN /publish is called on the draft's own uuid
        THEN 409 conflict
        """
        draft = self.api.post(f'{self.base}/draft').json()
        response = self.api.post(f'/surveys/{draft["uuid"]}/publish', {})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error'], 'conflict')


@LOCMEM
class V1PublishReviewTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner)
        Question.objects.create(survey_section=self.section, name='Q', input_type='text', order_number=1)
        self.api = V1Client(self.client, mint(self.owner)[0])

    def test_held_publish_reports_pending_and_hides_the_survey(self):
        """
        GIVEN a survey whose content screening holds it
        WHEN it is published through the API
        THEN the response says published with review pending, and the respondent URL is unavailable
        """
        def hold(survey, trigger):
            ContentReview.objects.create(survey=survey, status='pending')
        with mock.patch('survey.services.publishing.screen_survey', side_effect=hold):
            response = self.api.post(f'/surveys/{self.survey.uuid}/publish', {})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual((response.json()['status'], response.json()['review']), ('published', 'pending'))
        self.client.logout()
        page = self.client.get(f'/surveys/{self.survey.uuid}/', follow=True)
        self.assertEqual(page.status_code, 404)

    def test_translation_gaps_need_acknowledgement(self):
        """
        GIVEN a survey offered in two languages with no translations
        WHEN it is published without and then with acknowledgement
        THEN first 409 translation_gaps, then published
        """
        SurveyHeader.objects.filter(pk=self.survey.pk).update(available_languages=['en', 'de'])
        first = self.api.post(f'/surveys/{self.survey.uuid}/publish', {})
        self.assertEqual(first.status_code, 409)
        self.assertEqual(first.json()['error'], 'translation_gaps')
        second = self.api.post(f'/surveys/{self.survey.uuid}/publish', {'acknowledge_translation_gaps': True})
        self.assertEqual(second.status_code, 200, second.content)
