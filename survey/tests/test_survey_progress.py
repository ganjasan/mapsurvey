"""Tests for the `survey-progress` capability (openspec/specs/survey-progress/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from survey.models import Organization, SurveyHeader, SurveySection, Question


class SurveyProgressIndicatorTest(TestCase):
    """Tests for survey section progress indicator."""

    def setUp(self):
        """Set up a survey with three linked sections."""
        self.client = Client()
        self.org = Organization.objects.create(name="Progress Test Org")
        self.survey = SurveyHeader.objects.create(
            name="progress_survey",
            organization=self.org,
            redirect_url="/thanks/",
            status='published',
        )
        self.section1 = SurveySection.objects.create(
            survey_header=self.survey,
            name="sec1",
            title="First",
            code="S1",
            is_head=True,
        )
        self.section2 = SurveySection.objects.create(
            survey_header=self.survey,
            name="sec2",
            title="Second",
            code="S2",
        )
        self.section3 = SurveySection.objects.create(
            survey_header=self.survey,
            name="sec3",
            title="Third",
            code="S3",
        )
        # Link sections: sec1 → sec2 → sec3
        self.section1.next_section = self.section2
        self.section1.save()
        self.section2.prev_section = self.section1
        self.section2.next_section = self.section3
        self.section2.save()
        self.section3.prev_section = self.section2
        self.section3.save()

        # Each section needs at least one question
        for section in [self.section1, self.section2, self.section3]:
            Question.objects.create(
                survey_section=section,
                name=f"Q in {section.name}",
                input_type="text",
                order_number=1,
            )

    def test_progress_on_first_section(self):
        """
        GIVEN a 3-section survey
        WHEN the user opens the first section
        THEN section_current is 1 and section_total is 3
        """
        response = self.client.get('/surveys/progress_survey/sec1/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['section_current'], 1)
        self.assertEqual(response.context['section_total'], 3)

    def test_progress_on_middle_section(self):
        """
        GIVEN a 3-section survey
        WHEN the user opens the second section
        THEN section_current is 2 and section_total is 3
        """
        response = self.client.get('/surveys/progress_survey/sec2/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['section_current'], 2)
        self.assertEqual(response.context['section_total'], 3)

    def test_progress_on_last_section(self):
        """
        GIVEN a 3-section survey
        WHEN the user opens the last section
        THEN section_current is 3 and section_total is 3
        """
        response = self.client.get('/surveys/progress_survey/sec3/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['section_current'], 3)
        self.assertEqual(response.context['section_total'], 3)

    def test_progress_displayed_in_html(self):
        """
        GIVEN a 3-section survey
        WHEN the user opens the second section
        THEN the HTML contains "2 / 3" in a progress element
        """
        response = self.client.get('/surveys/progress_survey/sec2/')
        self.assertContains(response, '2 / 3')
