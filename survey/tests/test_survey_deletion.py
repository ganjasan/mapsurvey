"""Tests for the `survey-deletion` capability (openspec/specs/survey-deletion/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
import uuid
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
from survey.tests.helpers import _make_org


class DeleteSurveyTest(TestCase):
    """Tests for survey deletion functionality."""

    def setUp(self):
        """Set up test data and client."""
        self.client = Client()
        self.org = _make_org()
        self.user = User.objects.create_user(
            username='deleteuser',
            password='testpass123'
        )
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(name="delete_test_survey", organization=self.org)
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="delete_section",
            code="DS",
            is_head=True
        )
        self.question = Question.objects.create(
            survey_section=self.section,
            code="Q_DELETE",
            name="Delete test question",
            input_type="text"
        )
        self.session = SurveySession.objects.create(survey=self.survey)
        self.answer = Answer.objects.create(
            survey_session=self.session,
            question=self.question,
            text="Test answer"
        )

    def test_delete_survey_success(self):
        """
        GIVEN an authenticated user and existing survey
        WHEN POST request to delete endpoint
        THEN survey is moved to trash (deleted_at set) and user redirected
        """
        self.client.login(username='deleteuser', password='testpass123')
        response = self.client.post(f'/editor/delete/{self.survey.uuid}/')

        self.assertEqual(response.status_code, 302)
        self.survey.refresh_from_db()
        self.assertIsNotNone(self.survey.deleted_at)
        self.assertTrue(self.survey.is_trashed)

    def test_delete_survey_unauthenticated_redirect(self):
        """
        GIVEN an unauthenticated user
        WHEN accessing delete endpoint
        THEN redirect to login page
        """
        response = self.client.post(f'/editor/delete/{self.survey.uuid}/')

        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
        # Survey should still exist
        self.assertTrue(SurveyHeader.objects.filter(name="delete_test_survey").exists())

    def test_delete_survey_not_found(self):
        """
        GIVEN an authenticated user
        WHEN attempting to delete non-existent survey by UUID
        THEN return 404
        """
        import uuid
        self.client.login(username='deleteuser', password='testpass123')
        response = self.client.post(f'/editor/delete/{uuid.uuid4()}/')

        self.assertEqual(response.status_code, 404)

    def test_trash_preserves_related_data(self):
        """
        GIVEN a survey with sessions, answers, sections, and questions
        WHEN survey is moved to trash
        THEN all related data is preserved in the database
        """
        self.client.login(username='deleteuser', password='testpass123')
        self.client.post(f'/editor/delete/{self.survey.uuid}/')

        # Trash preserves everything; cascade happens only at purge
        self.assertTrue(SurveySession.objects.filter(pk=self.session.pk).exists())
        self.assertTrue(Answer.objects.filter(pk=self.answer.pk).exists())
        self.assertTrue(SurveySection.objects.filter(pk=self.section.pk).exists())
        self.assertTrue(Question.objects.filter(pk=self.question.pk).exists())

    def test_purge_cascade_deletes_related_data(self):
        """
        GIVEN a trashed survey with sessions, answers, sections, and questions
        WHEN survey is purged via Delete forever
        THEN all related data is deleted
        """
        self.client.login(username='deleteuser', password='testpass123')
        self.client.post(f'/editor/delete/{self.survey.uuid}/')
        response = self.client.post(f'/editor/purge/{self.survey.uuid}/')

        self.assertEqual(response.status_code, 302)
        self.assertFalse(SurveyHeader.objects.filter(pk=self.survey.pk).exists())
        self.assertFalse(SurveySession.objects.filter(pk=self.session.pk).exists())
        self.assertFalse(Answer.objects.filter(pk=self.answer.pk).exists())
        self.assertFalse(SurveySection.objects.filter(pk=self.section.pk).exists())
        self.assertFalse(Question.objects.filter(pk=self.question.pk).exists())

    def test_delete_survey_get_request_rejected(self):
        """
        GIVEN an authenticated user
        WHEN GET request to delete endpoint
        THEN request is rejected and survey not deleted
        """
        self.client.login(username='deleteuser', password='testpass123')
        response = self.client.get(f'/editor/delete/{self.survey.uuid}/')

        self.assertEqual(response.status_code, 302)
        # Survey should still exist
        self.assertTrue(SurveyHeader.objects.filter(name="delete_test_survey").exists())
