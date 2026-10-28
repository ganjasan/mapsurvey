"""Tests for the `survey-page-metadata` capability (openspec/specs/survey-page-metadata/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from survey.models import Organization, SurveyHeader, SurveySection


class SurveyPageMetadataTest(TestCase):
    """Survey pages carry a real <title> and html[lang] (survey-page-metadata)."""

    def setUp(self):
        self.org = Organization.objects.create(name="Meta Org")
        self.survey = SurveyHeader.objects.create(
            name="meta_survey",
            organization=self.org,
            available_languages=[],
            status='published',
        )
        SurveySection.objects.create(
            survey_header=self.survey, name="section1", title="S1",
            code="M1", is_head=True,
        )

    def test_section_page_title_contains_survey_name(self):
        """
        GIVEN a published survey
        WHEN a respondent opens a section
        THEN the document title contains the survey name
        """
        response = self.client.get('/surveys/meta_survey/section1/')
        html = response.content.decode()
        self.assertIn('<title>meta_survey — Mapsurvey</title>', html)

    def test_section_page_declares_language(self):
        """
        GIVEN a single-language survey served in the default locale
        WHEN a respondent opens a section
        THEN the root html element declares a lang attribute
        """
        response = self.client.get('/surveys/meta_survey/section1/')
        html = response.content.decode()
        self.assertIn('<html lang="en"', html)
