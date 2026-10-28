"""Tests for the `editor-autosave` capability (openspec/specs/editor-autosave/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from survey.models import Organization, SurveyHeader, SurveySection, Question, Membership


class EditorAutosaveTest(TestCase):
    """Autosave on question edit forms behind the EDITOR_AUTOSAVE kill switch."""

    def setUp(self):
        self.org = Organization.objects.create(name="Autosave Org")
        self.user = User.objects.create_user('autosave_owner', password='pw')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(name="autosave_survey", organization=self.org)
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', title='Section 1',
        )
        self.question = Question.objects.create(
            survey_section=self.section, name='Old name', input_type='text',
        )
        self.client.force_login(self.user)

    @override_settings(EDITOR_AUTOSAVE=True)
    def test_autosave_post_persists_change(self):
        """
        GIVEN an existing text question and the autosave flag on
        WHEN the form is POSTed with the autosave marker and a new name
        THEN the change is persisted and the response is not a form re-render
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.question.id}/edit/',
            {'name': 'New name', 'input_type': 'text', 'color': '#e74c3c', 'autosave': '1'},
        )
        self.assertEqual(response.status_code, 200)
        self.question.refresh_from_db()
        self.assertEqual(self.question.name, 'New name')

    @override_settings(EDITOR_AUTOSAVE=True)
    def test_autosave_validation_error_returns_422_not_rerender(self):
        """
        GIVEN an autosave POST with invalid data (missing required input_type)
        WHEN the form fails validation
        THEN the view answers 422 JSON and never replaces the typed-in form,
             and the stored question is unchanged
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.question.id}/edit/',
            {'name': 'Half-typed', 'autosave': '1'},
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn('errors', response.json())
        self.question.refresh_from_db()
        self.assertEqual(self.question.name, 'Old name')

    @override_settings(EDITOR_AUTOSAVE=True)
    def test_edit_form_renders_indicator_instead_of_save(self):
        """
        GIVEN the autosave flag on
        WHEN an existing question's form modal renders
        THEN the saved-state indicator is present and Save/Apply buttons are not
        """
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.question.id}/edit/',
        )
        html = response.content.decode()
        self.assertIn('autosave-indicator', html)
        self.assertIn('data-autosave', html)
        self.assertNotIn('id="apply-question-btn"', html)
        self.assertNotIn('>Save</button>', html)

    @override_settings(EDITOR_AUTOSAVE=True)
    def test_new_question_form_keeps_create_button(self):
        """
        GIVEN the autosave flag on
        WHEN the new-question form renders
        THEN it still carries an explicit Create button and no autosave marker
        """
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/',
        )
        html = response.content.decode()
        self.assertIn('>Create</button>', html)
        self.assertNotIn('data-autosave', html)

    @override_settings(EDITOR_AUTOSAVE=False)
    def test_flag_off_keeps_legacy_save_buttons(self):
        """
        GIVEN the autosave flag explicitly off
        WHEN an existing question's form modal renders
        THEN the legacy Save and Apply buttons are present, no indicator
        """
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.question.id}/edit/',
        )
        html = response.content.decode()
        self.assertIn('>Save</button>', html)
        self.assertIn('id="apply-question-btn"', html)
        self.assertNotIn('autosave-indicator', html)
