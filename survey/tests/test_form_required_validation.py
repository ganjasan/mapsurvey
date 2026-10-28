"""Tests that no capability owns yet: form-required-validation.

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
import re
from survey.models import SurveyHeader, SurveySection, Question
from survey.tests.helpers import _make_org


class RequiredValidationRenderTest(TestCase):
    """The survey-answering form renders the client-side required-validation scaffolding."""

    def setUp(self):
        self.client = Client()
        self.org = _make_org()
        self.survey = SurveyHeader.objects.create(
            name="reqval_survey",
            organization=self.org,
            redirect_url="/thanks/",
            status="published",
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="Only Section", code="S1", is_head=True,
        )
        self.required_q = Question.objects.create(
            survey_section=self.section, name="Agree?", input_type="choice",
            choices=[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}],
            required=True, order_number=1,
        )
        self.optional_q = Question.objects.create(
            survey_section=self.section, name="Comment", input_type="text",
            required=False, order_number=2,
        )

    def test_form_has_novalidate_and_summary(self):
        """
        GIVEN a published survey section
        WHEN a respondent opens it
        THEN the form is novalidate and the required-summary banner exists
        """
        response = self.client.get("/surveys/reqval_survey/s1/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("novalidate", html)
        self.assertIn('id="required-summary"', html)
        # translated inline-message string is exposed to the JS on the form
        self.assertIn("data-msg-required", html)

    def test_only_required_question_card_is_marked(self):
        """
        GIVEN a section with one required and one optional question
        WHEN it renders
        THEN exactly one question card carries data-required="true"
        """
        import re
        html = self.client.get("/surveys/reqval_survey/s1/").content.decode()
        card_tags = re.findall(r'<div class="question-card[^>]*>', html)
        self.assertEqual(len(card_tags), 2)  # one required + one optional
        marked = [t for t in card_tags if 'data-required="true"' in t]
        self.assertEqual(len(marked), 1)
