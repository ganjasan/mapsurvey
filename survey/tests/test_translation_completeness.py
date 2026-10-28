"""Tests for the `translation-completeness` capability (openspec/specs/translation-completeness/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from survey.models import SurveyHeader, SurveySection, Question, Membership
from survey.models import SurveySectionTranslation, QuestionTranslation
from survey.tests.helpers import _make_org


class TranslationCompletenessTest(TestCase):
    """Editor-side visibility of translation gaps (spec: translation-completeness)."""

    def setUp(self):
        self.org = _make_org('CompletenessOrg')
        self.user = User.objects.create_user(username='gapsuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='gapsuser', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='gaps_survey', visibility='private', organization=self.org,
            available_languages=['pt', 'es', 'en'],
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Base', code='S1', is_head=True,
        )
        SurveySectionTranslation.objects.create(
            section=self.section, language='es', title='Base es',
        )
        SurveySectionTranslation.objects.create(
            section=self.section, language='en', title='Base en',
        )

    def test_untranslated_question_reports_all_non_primary_languages(self):
        """
        GIVEN a question with no translation rows on a trilingual survey
        WHEN missing languages are computed
        THEN both non-primary languages are reported (the survey-467 manual
             question shape) and the primary is not
        """
        from survey.translation_gaps import question_missing_languages

        question = Question.objects.create(
            survey_section=self.section, name='Identifique-se', input_type='text',
        )
        self.assertEqual(question_missing_languages(question, self.survey), ['es', 'en'])

    def test_choice_dict_missing_one_language_flags_that_language(self):
        """
        GIVEN a choice question translated everywhere except one choice's en key
        WHEN missing languages are computed
        THEN only en is reported
        """
        from survey.translation_gaps import question_missing_languages

        question = Question.objects.create(
            survey_section=self.section, name='Escolha', input_type='choice',
            choices=[{'code': 1, 'name': {'pt': 'Sim', 'es': 'Sí'}}],
        )
        QuestionTranslation.objects.create(question=question, language='es', name='Elige')
        QuestionTranslation.objects.create(question=question, language='en', name='Choose')
        self.assertEqual(question_missing_languages(question, self.survey), ['en'])

    def test_optional_subtext_counts_only_when_base_is_non_empty(self):
        """
        GIVEN a translated question whose base subtext is empty
        WHEN missing languages are computed
        THEN nothing is reported — an empty optional field is not a gap
        """
        from survey.translation_gaps import question_missing_languages

        question = Question.objects.create(
            survey_section=self.section, name='Nome', subtext='', input_type='text',
        )
        QuestionTranslation.objects.create(question=question, language='es', name='Nombre')
        QuestionTranslation.objects.create(question=question, language='en', name='Name')
        self.assertEqual(question_missing_languages(question, self.survey), [])

    def test_single_language_survey_reports_no_gaps(self):
        """
        GIVEN a single-language survey
        WHEN survey-wide gaps are computed
        THEN the list is empty regardless of content
        """
        from survey.translation_gaps import survey_translation_gaps

        survey = SurveyHeader.objects.create(
            name='mono', organization=self.org, available_languages=['es'],
        )
        section = SurveySection.objects.create(
            survey_header=survey, name='sec1', title='T', code='S1', is_head=True,
        )
        Question.objects.create(survey_section=section, name='Q', input_type='text')
        self.assertEqual(survey_translation_gaps(survey), [])

    def test_publish_transition_warns_once_then_respects_acknowledgement(self):
        """
        GIVEN a trilingual survey with an untranslated question
        WHEN the owner publishes without, then with, the acknowledgement flag
        THEN the first POST returns 409 naming the gap and does not publish,
             and the second publishes — the warning never blocks
        """
        Question.objects.create(
            survey_section=self.section, name='Identifique-se', input_type='text',
        )

        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/transition/',
            {'status': 'published'},
        )
        self.assertEqual(response.status_code, 409)
        gaps = response.json()['translation_gaps']
        self.assertTrue(any('Identifique-se' in g['label'] for g in gaps))
        self.survey.refresh_from_db()
        self.assertNotEqual(self.survey.status, 'published')

        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/transition/',
            {'status': 'published', 'ack_translation_gaps': 'true'},
        )
        self.assertIn(response.status_code, (200, 204, 302))
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.status, 'published')

    def test_fully_translated_survey_publishes_without_warning(self):
        """
        GIVEN a survey whose sections and questions are fully translated
        WHEN the owner publishes
        THEN no 409 warning is returned
        """
        question = Question.objects.create(
            survey_section=self.section, name='Nome', input_type='text',
        )
        QuestionTranslation.objects.create(question=question, language='es', name='Nombre')
        QuestionTranslation.objects.create(question=question, language='en', name='Name')

        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/transition/',
            {'status': 'published'},
        )
        self.assertIn(response.status_code, (200, 204, 302))

    def test_question_list_shows_missing_language_badge(self):
        """
        GIVEN an untranslated question on a trilingual survey
        WHEN the section detail partial renders
        THEN the warning badge lists the missing languages
        """
        Question.objects.create(
            survey_section=self.section, name='Identifique-se', input_type='text',
        )
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/',
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('es, en', response.content.decode())
