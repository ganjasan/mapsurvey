"""Tests that no capability owns yet: survey-password-protection.

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from survey.models import SurveyHeader, SurveySection
from survey.tests.helpers import _make_org


class LifecyclePasswordTest(TestCase):
    """Tests for survey password management methods."""

    def setUp(self):
        self.org = _make_org('PwdOrg')
        self.survey = SurveyHeader.objects.create(
            name='pwd_test', organization=self.org,
        )

    def test_set_password(self):
        """
        GIVEN a survey without password
        WHEN set_password is called
        THEN has_password returns True and check_password works
        """
        self.assertFalse(self.survey.has_password())
        self.survey.set_password('test123')
        self.assertTrue(self.survey.has_password())
        self.assertTrue(self.survey.check_password('test123'))

    def test_check_password_rejects_wrong(self):
        """
        GIVEN a survey with password set
        WHEN check_password is called with wrong password
        THEN it returns False
        """
        self.survey.set_password('correct')
        self.assertFalse(self.survey.check_password('wrong'))

    def test_has_password_no_hash(self):
        """
        GIVEN a survey without password_hash
        WHEN has_password is called
        THEN it returns False
        """
        self.assertFalse(self.survey.has_password())

    def test_clear_password(self):
        """
        GIVEN a survey with password set
        WHEN clear_password is called
        THEN has_password returns False
        """
        self.survey.set_password('test123')
        self.survey.clear_password()
        self.assertFalse(self.survey.has_password())

    def test_check_password_returns_false_no_hash(self):
        """
        GIVEN a survey without password
        WHEN check_password is called
        THEN it returns False
        """
        self.assertFalse(self.survey.check_password('anything'))


class PasswordGateViewTest(TestCase):
    """Tests for the survey_password_gate view."""

    def setUp(self):
        self.org = _make_org('GateOrg')
        self.survey = SurveyHeader.objects.create(
            name='gate_test', organization=self.org, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.survey.set_password('correct')
        self.survey.save()

    def test_get_renders_form(self):
        """
        GIVEN a published survey with password
        WHEN GET /surveys/<uuid>/password/
        THEN render password form
        """
        response = self.client.get(f'/surveys/{self.survey.uuid}/password/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'password')

    def test_correct_password_redirects(self):
        """
        GIVEN a published survey with password
        WHEN POST with correct password
        THEN redirect to survey and set session key
        """
        response = self.client.post(
            f'/surveys/{self.survey.uuid}/password/',
            {'password': 'correct'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(str(self.survey.uuid), response.url)
        self.assertTrue(self.client.session.get(f'survey_password_{self.survey.id}'))

    def test_incorrect_password_shows_error(self):
        """
        GIVEN a published survey with password
        WHEN POST with incorrect password
        THEN re-render form with error
        """
        response = self.client.post(
            f'/surveys/{self.survey.uuid}/password/',
            {'password': 'wrong'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Incorrect password')
