"""Tests for the `survey-language-selection` capability (openspec/specs/survey-language-selection/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from survey.models import Organization, SurveyHeader, SurveySection, SurveySession


class LanguageSelectionTest(TestCase):
    """Tests for language selection view and flow."""

    def setUp(self):
        """Set up test data for language selection tests."""
        self.client = Client()
        self.org = Organization.objects.create(name="Lang Test Org")
        self.multilang_survey = SurveyHeader.objects.create(
            name="multilang_test",
            organization=self.org,
            available_languages=["en", "ru", "de"],
            status='published',
        )
        self.single_lang_survey = SurveyHeader.objects.create(
            name="singlelang_test",
            organization=self.org,
            available_languages=[],
            status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.multilang_survey,
            name="section1",
            title="Test Section",
            code="S1",
            is_head=True
        )
        self.single_section = SurveySection.objects.create(
            survey_header=self.single_lang_survey,
            name="section1",
            title="Single Lang Section",
            code="SL1",
            is_head=True
        )

    def test_language_selection_page_displays_for_multilang_survey(self):
        """
        GIVEN a multilingual survey
        WHEN user visits language selection URL
        THEN language options are displayed
        """
        response = self.client.get('/surveys/multilang_test/language/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'English')
        self.assertContains(response, 'Русский')
        self.assertContains(response, 'Deutsch')

    def test_language_selection_redirects_for_single_lang_survey(self):
        """
        GIVEN a single-language survey
        WHEN user visits language selection URL
        THEN user is redirected to survey entry (using UUID)
        """
        response = self.client.get('/surveys/singlelang_test/language/')

        self.assertEqual(response.status_code, 302)
        self.assertIn(str(self.single_lang_survey.uuid), response.url)

    def test_one_language_survey_entry_skips_picker(self):
        """
        GIVEN a survey with exactly one language
        WHEN a respondent enters the survey
        THEN they go straight to the first section, not the language picker
        """
        survey = SurveyHeader.objects.create(
            name="one_lang_entry", organization=self.org,
            available_languages=["de"], status='published',
        )
        SurveySection.objects.create(
            survey_header=survey, name="s1", title="S", code="S1", is_head=True,
        )
        response = self.client.get('/surveys/one_lang_entry/')
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('language', response.url)
        self.assertIn('s1', response.url)

    def test_one_language_section_records_that_language_on_session(self):
        """
        GIVEN a survey with exactly one language and no chosen language
        WHEN a respondent opens its first section
        THEN it renders and the created SurveySession stores that language
        """
        survey = SurveyHeader.objects.create(
            name="one_lang_section", organization=self.org,
            available_languages=["de"], status='published',
        )
        SurveySection.objects.create(
            survey_header=survey, name="s1", title="S", code="S1", is_head=True,
        )
        response = self.client.get(f'/surveys/{survey.uuid}/s1/')
        self.assertEqual(response.status_code, 200)
        session = SurveySession.objects.filter(survey=survey).latest('id')
        self.assertEqual(session.language, 'de')

    def test_two_language_survey_entry_redirects_to_picker(self):
        """
        GIVEN a survey with two or more languages
        WHEN a respondent enters the survey
        THEN they are redirected to the language selection screen
        """
        response = self.client.get('/surveys/multilang_test/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('language', response.url)

    def test_language_selection_creates_session_with_language(self):
        """
        GIVEN a multilingual survey
        WHEN user selects a language
        THEN session is created with selected language
        """
        response = self.client.post(
            '/surveys/multilang_test/language/',
            {'language': 'ru'}
        )

        self.assertEqual(response.status_code, 302)
        session_id = self.client.session.get('survey_session_id')
        self.assertIsNotNone(session_id)

        session = SurveySession.objects.get(pk=session_id)
        self.assertEqual(session.language, 'ru')

    def test_language_selection_stores_language_in_django_session(self):
        """
        GIVEN a multilingual survey
        WHEN user selects a language
        THEN Django session contains selected language
        """
        self.client.post(
            '/surveys/multilang_test/language/',
            {'language': 'de'}
        )

        self.assertEqual(self.client.session.get('survey_language'), 'de')

    def test_language_selection_redirects_to_first_section(self):
        """
        GIVEN a multilingual survey with sections
        WHEN user selects a language
        THEN user is redirected to first section
        """
        response = self.client.post(
            '/surveys/multilang_test/language/',
            {'language': 'en'}
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('section1', response.url)

    def test_language_selection_ignores_invalid_language(self):
        """
        GIVEN a multilingual survey
        WHEN user submits invalid language code
        THEN selection page is shown again (no redirect)
        """
        response = self.client.post(
            '/surveys/multilang_test/language/',
            {'language': 'invalid'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.client.session.get('survey_session_id'))


class SurveyFlowIntegrationTest(TestCase):
    """Tests for survey flow with multilingual support."""

    def setUp(self):
        """Set up test data for flow tests."""
        self.client = Client()
        self.org = Organization.objects.create(name="Flow Test Org")
        self.multilang_survey = SurveyHeader.objects.create(
            name="flow_multilang",
            organization=self.org,
            available_languages=["en", "ru"],
            status='published',
        )
        self.single_lang_survey = SurveyHeader.objects.create(
            name="flow_singlelang",
            organization=self.org,
            available_languages=[],
            status='published',
        )
        self.multi_section = SurveySection.objects.create(
            survey_header=self.multilang_survey,
            name="section1",
            title="Multi Section",
            code="MS1",
            is_head=True
        )
        self.single_section = SurveySection.objects.create(
            survey_header=self.single_lang_survey,
            name="section1",
            title="Single Section",
            code="SS1",
            is_head=True
        )

    def test_survey_header_redirects_to_language_select_for_multilang(self):
        """
        GIVEN a multilingual survey
        WHEN user visits survey entry URL
        THEN user is redirected to language selection
        """
        response = self.client.get('/surveys/flow_multilang/')

        self.assertEqual(response.status_code, 302)
        self.assertIn('language', response.url)

    def test_survey_header_redirects_to_section_for_singlelang(self):
        """
        GIVEN a single-language survey
        WHEN user visits survey entry URL
        THEN user is redirected directly to first section
        """
        response = self.client.get('/surveys/flow_singlelang/')

        self.assertEqual(response.status_code, 302)
        self.assertIn('section1', response.url)

    def test_section_redirects_to_language_select_if_no_language(self):
        """
        GIVEN a multilingual survey
        WHEN user visits section directly without language selection
        THEN user is redirected to language selection
        """
        response = self.client.get('/surveys/flow_multilang/section1/')

        self.assertEqual(response.status_code, 302)
        self.assertIn('language', response.url)

    def test_section_accessible_after_language_selection(self):
        """
        GIVEN a multilingual survey with language selected
        WHEN user visits section
        THEN section is displayed
        """
        # First select language
        self.client.post('/surveys/flow_multilang/language/', {'language': 'en'})

        # Then access section
        response = self.client.get('/surveys/flow_multilang/section1/')

        self.assertEqual(response.status_code, 200)

    def test_section_accessible_for_singlelang_without_language(self):
        """
        GIVEN a single-language survey
        WHEN user visits section directly
        THEN section is displayed (no language selection needed)
        """
        response = self.client.get('/surveys/flow_singlelang/section1/')

        self.assertEqual(response.status_code, 200)

    def test_selected_language_passed_to_section_context(self):
        """
        GIVEN a multilingual survey with Russian selected
        WHEN section is rendered
        THEN template context contains selected_language='ru'
        """
        self.client.post('/surveys/flow_multilang/language/', {'language': 'ru'})
        response = self.client.get('/surveys/flow_multilang/section1/')

        self.assertEqual(response.context['selected_language'], 'ru')
