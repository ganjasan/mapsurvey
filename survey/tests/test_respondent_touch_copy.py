"""Tests that no capability owns yet: respondent-touch-copy.

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from survey.models import Organization, SurveyHeader, SurveySection


class RespondentTouchCopyTest(TestCase):
    """Touch-phrased instruction copy on the respondent map (kept from the
    reverted bottom-sheet experiment — accurate copy is flag-independent)."""

    def setUp(self):
        self.org = Organization.objects.create(name="Touch Org")
        self.survey = SurveyHeader.objects.create(
            name="touch_survey",
            organization=self.org,
            available_languages=[],
            status='published',
        )
        SurveySection.objects.create(
            survey_header=self.survey, name="section1", title="S1",
            code="TC1", is_head=True,
        )

    def test_touch_instruction_strings_served(self):
        """
        GIVEN the respondent map page
        WHEN it renders
        THEN the i18n payload carries tap-phrased tooltips and the template
             picks them for coarse pointers
        """
        response = self.client.get('/surveys/touch_survey/section1/')
        html = response.content.decode()
        self.assertIn('tapToPlaceMarker', html)
        self.assertIn('pointer: coarse', html)
