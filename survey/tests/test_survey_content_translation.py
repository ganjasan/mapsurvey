"""Tests for the `survey-content-translation` capability (openspec/specs/survey-content-translation/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import translation
from io import BytesIO
import json
import zipfile
from survey.models import Organization, SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
from survey.serialization import export_survey_to_zip, import_survey_from_zip
from survey.forms import SurveySectionAnswerForm
from survey.models import SurveySectionTranslation, QuestionTranslation
from django.db.utils import IntegrityError
from survey.tests.helpers import _make_org


class TranslationModelsTest(TestCase):
    """Tests for multilingual translation models and helper methods."""

    def setUp(self):
        """Set up test data for translation tests."""
        from survey.models import (
            SurveySectionTranslation, QuestionTranslation,
        )
        self.SurveySectionTranslation = SurveySectionTranslation
        self.QuestionTranslation = QuestionTranslation

        self.org = Organization.objects.create(name="Test Org")
        self.survey = SurveyHeader.objects.create(
            name="multilang_survey",
            organization=self.org,
            redirect_url="/thanks/",
            available_languages=["en", "ru", "de"]
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="section1",
            title="Welcome",
            subheading="Please answer the questions",
            code="S1",
            is_head=True
        )
        self.test_choices = [
            {"code": 1, "name": {"en": "Yes", "ru": "Да"}},
            {"code": 2, "name": {"en": "No", "ru": "Нет"}},
        ]
        self.question = Question.objects.create(
            survey_section=self.section,
            name="Do you agree?",
            subtext="Select one option",
            input_type="choice",
            choices=self.test_choices,
            code="Q1"
        )

    def test_survey_is_multilingual_true(self):
        """
        GIVEN a survey with available_languages configured
        WHEN is_multilingual() is called
        THEN it returns True
        """
        self.assertTrue(self.survey.is_multilingual())

    def test_survey_is_multilingual_false_empty_list(self):
        """
        GIVEN a survey with empty available_languages
        WHEN is_multilingual() is called
        THEN it returns False
        """
        survey = SurveyHeader.objects.create(
            name="single_lang_survey",
            organization=self.org,
            available_languages=[]
        )
        self.assertFalse(survey.is_multilingual())

    def test_survey_is_multilingual_false_no_languages(self):
        """
        GIVEN a survey with no available_languages set
        WHEN is_multilingual() is called
        THEN it returns False
        """
        survey = SurveyHeader.objects.create(name="default_survey", organization=self.org)
        self.assertFalse(survey.is_multilingual())

    def test_survey_is_multilingual_false_single_language(self):
        """
        GIVEN a survey with exactly one available language
        WHEN is_multilingual() is called
        THEN it returns False (no point asking a respondent to pick one)
        """
        survey = SurveyHeader.objects.create(
            name="one_lang_survey",
            organization=self.org,
            available_languages=["de"],
        )
        self.assertFalse(survey.is_multilingual())

    def test_section_translation_creation(self):
        """
        GIVEN a survey section
        WHEN translation is created
        THEN translation is stored correctly
        """
        translation = self.SurveySectionTranslation.objects.create(
            section=self.section,
            language="ru",
            title="Добро пожаловать",
            subheading="Пожалуйста, ответьте на вопросы"
        )
        self.assertEqual(translation.section, self.section)
        self.assertEqual(translation.language, "ru")
        self.assertEqual(translation.title, "Добро пожаловать")

    def test_section_get_translated_title_with_translation(self):
        """
        GIVEN a section with Russian translation
        WHEN get_translated_title('ru') is called
        THEN returns translated title
        """
        self.SurveySectionTranslation.objects.create(
            section=self.section,
            language="ru",
            title="Добро пожаловать"
        )
        self.assertEqual(
            self.section.get_translated_title("ru"),
            "Добро пожаловать"
        )

    def test_section_get_translated_title_without_translation(self):
        """
        GIVEN a section without German translation
        WHEN get_translated_title('de') is called
        THEN returns original title
        """
        self.assertEqual(
            self.section.get_translated_title("de"),
            "Welcome"
        )

    def test_section_get_translated_title_with_none_language(self):
        """
        GIVEN a section
        WHEN get_translated_title(None) is called
        THEN returns original title
        """
        self.assertEqual(
            self.section.get_translated_title(None),
            "Welcome"
        )

    def test_section_get_translated_subheading_with_translation(self):
        """
        GIVEN a section with Russian translation
        WHEN get_translated_subheading('ru') is called
        THEN returns translated subheading
        """
        self.SurveySectionTranslation.objects.create(
            section=self.section,
            language="ru",
            subheading="Пожалуйста, ответьте"
        )
        self.assertEqual(
            self.section.get_translated_subheading("ru"),
            "Пожалуйста, ответьте"
        )

    def test_section_get_translated_subheading_fallback(self):
        """
        GIVEN a section with translation that has empty subheading
        WHEN get_translated_subheading is called
        THEN returns original subheading
        """
        self.SurveySectionTranslation.objects.create(
            section=self.section,
            language="ru",
            title="Добро пожаловать",
            subheading=""
        )
        self.assertEqual(
            self.section.get_translated_subheading("ru"),
            "Please answer the questions"
        )

    def test_question_translation_creation(self):
        """
        GIVEN a question
        WHEN translation is created
        THEN translation is stored correctly
        """
        translation = self.QuestionTranslation.objects.create(
            question=self.question,
            language="ru",
            name="Вы согласны?",
            subtext="Выберите один вариант"
        )
        self.assertEqual(translation.question, self.question)
        self.assertEqual(translation.name, "Вы согласны?")

    def test_question_get_translated_name_with_translation(self):
        """
        GIVEN a question with Russian translation
        WHEN get_translated_name('ru') is called
        THEN returns translated name
        """
        self.QuestionTranslation.objects.create(
            question=self.question,
            language="ru",
            name="Вы согласны?"
        )
        self.assertEqual(
            self.question.get_translated_name("ru"),
            "Вы согласны?"
        )

    def test_question_get_translated_name_without_translation(self):
        """
        GIVEN a question without translation
        WHEN get_translated_name('fr') is called
        THEN returns original name
        """
        self.assertEqual(
            self.question.get_translated_name("fr"),
            "Do you agree?"
        )

    def test_question_get_translated_subtext_with_translation(self):
        """
        GIVEN a question with Russian translation
        WHEN get_translated_subtext('ru') is called
        THEN returns translated subtext
        """
        self.QuestionTranslation.objects.create(
            question=self.question,
            language="ru",
            subtext="Выберите один вариант"
        )
        self.assertEqual(
            self.question.get_translated_subtext("ru"),
            "Выберите один вариант"
        )

    def test_inline_choice_get_name_with_translation(self):
        """
        GIVEN a question with inline choices with Russian translation
        WHEN get_choice_name(1, 'ru') is called
        THEN returns translated name
        """
        self.assertEqual(
            self.question.get_choice_name(1, "ru"),
            "Да"
        )

    def test_inline_choice_get_name_without_translation(self):
        """
        GIVEN a question with inline choices without German translation
        WHEN get_choice_name(1, 'de') is called
        THEN returns English name as fallback
        """
        self.assertEqual(
            self.question.get_choice_name(1, "de"),
            "Yes"
        )

    def test_translation_unique_constraint(self):
        """
        GIVEN an existing translation for section+language
        WHEN another translation with same section+language is created
        THEN IntegrityError is raised
        """
        from django.db import IntegrityError

        self.SurveySectionTranslation.objects.create(
            section=self.section,
            language="ru",
            title="Добро пожаловать"
        )
        with self.assertRaises(IntegrityError):
            self.SurveySectionTranslation.objects.create(
                section=self.section,
                language="ru",
                title="Другой перевод"
            )

    def test_session_language_field(self):
        """
        GIVEN a survey session
        WHEN language is set
        THEN language is stored correctly
        """
        session = SurveySession.objects.create(
            survey=self.survey,
            language="ru"
        )
        self.assertEqual(session.language, "ru")

    def test_session_language_nullable(self):
        """
        GIVEN a survey session without language
        WHEN session is created
        THEN language is None
        """
        session = SurveySession.objects.create(survey=self.survey)
        self.assertIsNone(session.language)


class AdminInlineTest(TestCase):
    """Tests for admin interface with translation inlines."""

    def setUp(self):
        """Set up test data and admin user."""
        from django.contrib.admin.sites import AdminSite
        from survey.admin import (
            SurveySectionAdmin, QuestionAdmin,
            SurveySectionTranslationInline, QuestionTranslationInline,
        )
        from survey.models import SurveySectionTranslation, QuestionTranslation

        self.SurveySectionTranslation = SurveySectionTranslation
        self.QuestionTranslation = QuestionTranslation

        self.site = AdminSite()
        self.section_admin = SurveySectionAdmin(SurveySection, self.site)
        self.question_admin = QuestionAdmin(Question, self.site)

        self.user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='adminpass123'
        )
        self.org = Organization.objects.create(name="Admin Test Org")
        self.survey = SurveyHeader.objects.create(
            name="admin_test_survey",
            organization=self.org,
            available_languages=["en", "ru"]
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="admin_section",
            title="Admin Section",
            code="AS1",
            is_head=True
        )
        self.question = Question.objects.create(
            survey_section=self.section,
            name="Admin Question",
            input_type="text",
            code="AQ1"
        )

    def test_section_admin_has_translation_inline(self):
        """
        GIVEN SurveySectionAdmin
        WHEN inlines are checked
        THEN SurveySectionTranslationInline is present
        """
        inline_names = [inline.__name__ for inline in self.section_admin.inlines]
        self.assertIn('SurveySectionTranslationInline', inline_names)

    def test_question_admin_has_translation_inline(self):
        """
        GIVEN QuestionAdmin
        WHEN inlines are checked
        THEN QuestionTranslationInline is present
        """
        inline_names = [inline.__name__ for inline in self.question_admin.inlines]
        self.assertIn('QuestionTranslationInline', inline_names)

    def test_create_section_translation_via_model(self):
        """
        GIVEN a survey section
        WHEN translation is created programmatically
        THEN translation is accessible via section
        """
        self.SurveySectionTranslation.objects.create(
            section=self.section,
            language="ru",
            title="Админ Секция"
        )
        self.assertEqual(self.section.translations.count(), 1)
        self.assertEqual(self.section.translations.first().title, "Админ Секция")

    def test_create_question_translation_via_model(self):
        """
        GIVEN a question
        WHEN translation is created programmatically
        THEN translation is accessible via question
        """
        self.QuestionTranslation.objects.create(
            question=self.question,
            language="ru",
            name="Админ Вопрос"
        )
        self.assertEqual(self.question.translations.count(), 1)
        self.assertEqual(self.question.translations.first().name, "Админ Вопрос")

    def test_survey_admin_displays_available_languages(self):
        """
        GIVEN SurveyAdmin
        WHEN list_display is checked
        THEN available_languages is included
        """
        from survey.admin import SurveyAdmin
        self.assertIn('available_languages', SurveyAdmin.list_display)


class TranslatedContentDisplayTest(TestCase):
    """Tests for translated content display in forms and templates."""

    def setUp(self):
        """Set up test data with translations."""
        from survey.models import (
            SurveySectionTranslation, QuestionTranslation,
        )
        self.SurveySectionTranslation = SurveySectionTranslation
        self.QuestionTranslation = QuestionTranslation

        self.client = Client()
        self.org = Organization.objects.create(name="Display Test Org")
        self.survey = SurveyHeader.objects.create(
            name="display_test",
            organization=self.org,
            available_languages=["en", "ru"],
            status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="section1",
            title="Original Title",
            subheading="Original Subheading",
            code="DT1",
            is_head=True
        )
        self.display_choices = [
            {"code": 1, "name": {"en": "Original Choice 1", "ru": "Выбор 1"}},
            {"code": 2, "name": {"en": "Original Choice 2", "ru": "Выбор 2"}},
        ]
        self.text_question = Question.objects.create(
            survey_section=self.section,
            code="Q_TEXT",
            order_number=1,
            name="Original Question",
            subtext="Original Subtext",
            input_type="text"
        )
        self.choice_question = Question.objects.create(
            survey_section=self.section,
            code="Q_CHOICE",
            order_number=2,
            name="Original Choice Question",
            input_type="choice",
            choices=self.display_choices
        )

        # Create translations
        self.SurveySectionTranslation.objects.create(
            section=self.section,
            language="ru",
            title="Русский заголовок",
            subheading="Русский подзаголовок"
        )
        self.QuestionTranslation.objects.create(
            question=self.text_question,
            language="ru",
            name="Русский вопрос",
            subtext="Русский подтекст"
        )
        self.QuestionTranslation.objects.create(
            question=self.choice_question,
            language="ru",
            name="Русский вопрос с выбором"
        )

    def test_form_uses_translated_question_labels(self):
        """
        GIVEN a form with language='ru'
        WHEN form is created
        THEN question labels use Russian translations
        """
        session = SurveySession.objects.create(survey=self.survey, language="ru")
        form = SurveySectionAnswerForm(
            initial={},
            section=self.section,
            question=None,
            survey_session_id=session.id,
            language="ru"
        )

        self.assertEqual(form.fields["Q_TEXT"].label, "Русский вопрос")
        self.assertEqual(form.fields["Q_CHOICE"].label, "Русский вопрос с выбором")

    def test_form_uses_original_labels_without_language(self):
        """
        GIVEN a form with language=None
        WHEN form is created
        THEN question labels use original names
        """
        session = SurveySession.objects.create(survey=self.survey)
        form = SurveySectionAnswerForm(
            initial={},
            section=self.section,
            question=None,
            survey_session_id=session.id,
            language=None
        )

        self.assertEqual(form.fields["Q_TEXT"].label, "Original Question")
        self.assertEqual(form.fields["Q_CHOICE"].label, "Original Choice Question")

    def test_form_uses_translated_choice_options(self):
        """
        GIVEN a form with language='ru' and choice question
        WHEN form is created
        THEN choice options use Russian translations
        """
        session = SurveySession.objects.create(survey=self.survey, language="ru")
        form = SurveySectionAnswerForm(
            initial={},
            section=self.section,
            question=None,
            survey_session_id=session.id,
            language="ru"
        )

        choices = form.fields["Q_CHOICE"].choices
        choice_labels = [label for code, label in choices]
        self.assertIn("Выбор 1", choice_labels)
        self.assertIn("Выбор 2", choice_labels)

    def test_form_uses_original_choice_options_without_language(self):
        """
        GIVEN a form with language=None and choice question
        WHEN form is created
        THEN choice options use original names
        """
        session = SurveySession.objects.create(survey=self.survey)
        form = SurveySectionAnswerForm(
            initial={},
            section=self.section,
            question=None,
            survey_session_id=session.id,
            language=None
        )

        choices = form.fields["Q_CHOICE"].choices
        choice_labels = [label for code, label in choices]
        self.assertIn("Original Choice 1", choice_labels)
        self.assertIn("Original Choice 2", choice_labels)

    def test_section_view_passes_translated_title_to_context(self):
        """
        GIVEN a multilingual survey with Russian selected
        WHEN section is rendered
        THEN context contains translated section title
        """
        self.client.post('/surveys/display_test/language/', {'language': 'ru'})
        response = self.client.get('/surveys/display_test/section1/')

        self.assertEqual(response.context['section_title'], "Русский заголовок")

    def test_section_view_passes_translated_subheading_to_context(self):
        """
        GIVEN a multilingual survey with Russian selected
        WHEN section is rendered
        THEN context contains translated section subheading
        """
        self.client.post('/surveys/display_test/language/', {'language': 'ru'})
        response = self.client.get('/surveys/display_test/section1/')

        self.assertEqual(response.context['section_subheading'], "Русский подзаголовок")

    def test_section_view_passes_original_title_without_language(self):
        """
        GIVEN a single-language survey
        WHEN section is rendered
        THEN context contains original section title
        """
        single_survey = SurveyHeader.objects.create(
            name="single_display_test",
            organization=self.org,
            available_languages=[],
            status='published',
        )
        single_section = SurveySection.objects.create(
            survey_header=single_survey,
            name="section1",
            title="Single Lang Title",
            subheading="Single Lang Subheading",
            code="SDT1",
            is_head=True
        )

        response = self.client.get('/surveys/single_display_test/section1/')

        self.assertEqual(response.context['section_title'], "Single Lang Title")
        self.assertEqual(response.context['section_subheading'], "Single Lang Subheading")

    def test_form_fallback_for_missing_translation(self):
        """
        GIVEN a question without translation for requested language
        WHEN form is created with that language
        THEN question label falls back to original name
        """
        # Create question without Russian translation
        untranslated_q = Question.objects.create(
            survey_section=self.section,
            code="Q_UNTRANS",
            order_number=3,
            name="Untranslated Question",
            input_type="text"
        )

        session = SurveySession.objects.create(survey=self.survey, language="ru")
        form = SurveySectionAnswerForm(
            initial={},
            section=self.section,
            question=None,
            survey_session_id=session.id,
            language="ru"
        )

        self.assertEqual(form.fields["Q_UNTRANS"].label, "Untranslated Question")


class MultilingualIntegrationTest(TestCase):
    """End-to-end integration tests for multilingual survey functionality."""

    def setUp(self):
        """Set up complete multilingual survey with translations."""
        from survey.models import SurveySectionTranslation, QuestionTranslation
        self.SurveySectionTranslation = SurveySectionTranslation
        self.QuestionTranslation = QuestionTranslation

        self.client = Client()
        self.org = Organization.objects.create(name="Integration Test Org")

        # Create multilingual survey
        self.survey = SurveyHeader.objects.create(
            name="integration_multilang",
            organization=self.org,
            available_languages=["en", "ru"],
            redirect_url="/completed/",
            status='published',
        )

        # Create section with translations
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="main_section",
            title="English Section Title",
            subheading="English section description",
            code="INT1",
            is_head=True
        )
        self.SurveySectionTranslation.objects.create(
            section=self.section,
            language="ru",
            title="Русский заголовок секции",
            subheading="Русское описание секции"
        )

        # Create inline choices with translated names
        self.yes_no_choices = [
            {"code": 1, "name": {"en": "Yes", "ru": "Да"}},
            {"code": 2, "name": {"en": "No", "ru": "Нет"}},
        ]

        # Create questions with translations
        self.text_question = Question.objects.create(
            survey_section=self.section,
            code="Q_INT_TEXT",
            order_number=1,
            name="What is your name?",
            subtext="Please enter your full name",
            input_type="text"
        )
        self.QuestionTranslation.objects.create(
            question=self.text_question,
            language="ru",
            name="Как вас зовут?",
            subtext="Пожалуйста, введите ваше полное имя"
        )

        self.choice_question = Question.objects.create(
            survey_section=self.section,
            code="Q_INT_CHOICE",
            order_number=2,
            name="Do you agree?",
            input_type="choice",
            choices=self.yes_no_choices
        )
        self.QuestionTranslation.objects.create(
            question=self.choice_question,
            language="ru",
            name="Вы согласны?"
        )

    def test_end_to_end_multilingual_survey_flow(self):
        """
        GIVEN a multilingual survey with Russian translations
        WHEN user selects Russian, views section
        THEN survey session is created with language='ru' and translated titles shown
        """
        # Step 1: Access survey entry - should redirect to language selection
        response = self.client.get('/surveys/integration_multilang/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('language', response.url)

        # Step 2: Select Russian language
        response = self.client.post(
            '/surveys/integration_multilang/language/',
            {'language': 'ru'}
        )
        self.assertEqual(response.status_code, 302)

        # Step 3: View section - should show translated content
        response = self.client.get('/surveys/integration_multilang/main_section/')
        self.assertEqual(response.status_code, 200)

        # Verify translated section title is in context
        self.assertEqual(response.context['section_title'], "Русский заголовок секции")
        self.assertEqual(response.context['section_subheading'], "Русское описание секции")
        self.assertEqual(response.context['selected_language'], 'ru')

        # Verify session was created with correct language
        session = SurveySession.objects.get(survey=self.survey)
        self.assertEqual(session.language, 'ru')

    def test_export_import_multilingual_survey_roundtrip(self):
        """
        GIVEN a multilingual survey with translations and responses
        WHEN exported and imported to fresh database
        THEN all translations and language settings are preserved
        """
        # Create a session with language
        session = SurveySession.objects.create(
            survey=self.survey,
            language="ru"
        )
        Answer.objects.create(
            survey_session=session,
            question=self.text_question,
            text="Тестовый ответ"
        )

        # Export
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="full")
        output.seek(0)

        # Modify name for import
        with zipfile.ZipFile(output, 'r') as zf:
            survey_json = json.loads(zf.read("survey.json"))
            responses_json = json.loads(zf.read("responses.json"))

        survey_json["survey"]["name"] = "imported_integration_multilang"
        responses_json["survey_name"] = "imported_integration_multilang"

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_json))
            zf.writestr("responses.json", json.dumps(responses_json))
        import_buffer.seek(0)

        # Import
        imported_survey, _ = import_survey_from_zip(import_buffer)

        # Verify survey structure
        self.assertEqual(imported_survey.available_languages, ["en", "ru"])

        # Verify section translations
        imported_section = SurveySection.objects.get(survey_header=imported_survey)
        self.assertEqual(
            imported_section.get_translated_title("ru"),
            "Русский заголовок секции"
        )

        # Verify question translations
        imported_text_q = Question.objects.get(
            survey_section=imported_section,
            name="What is your name?"
        )
        self.assertEqual(
            imported_text_q.get_translated_name("ru"),
            "Как вас зовут?"
        )

        # Verify session language preserved
        imported_session = SurveySession.objects.get(survey=imported_survey)
        self.assertEqual(imported_session.language, "ru")

    def test_single_language_survey_backwards_compatibility(self):
        """
        GIVEN a survey without available_languages (single-language)
        WHEN user accesses the survey
        THEN no language selection screen is shown, direct access to section
        """
        # Create single-language survey
        single_survey = SurveyHeader.objects.create(
            name="single_lang_compat",
            organization=self.org,
            available_languages=[],
            status='published',
        )
        single_section = SurveySection.objects.create(
            survey_header=single_survey,
            name="single_section",
            title="Single Lang Title",
            code="SLC1",
            is_head=True
        )
        Question.objects.create(
            survey_section=single_section,
            code="Q_SINGLE",
            name="Single language question",
            input_type="text"
        )

        # Access survey - should redirect directly to section
        response = self.client.get('/surveys/single_lang_compat/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('single_section', response.url)
        self.assertNotIn('language', response.url)

        # Access section directly - should work without language selection
        response = self.client.get('/surveys/single_lang_compat/single_section/')
        self.assertEqual(response.status_code, 200)

        # Verify original content is shown (no translations)
        self.assertEqual(response.context['section_title'], "Single Lang Title")
        self.assertIsNone(response.context['selected_language'])

        # Submit answer
        response = self.client.post('/surveys/single_lang_compat/single_section/', {
            'Q_SINGLE': 'Test answer',
        })

        # Verify session created without language
        session = SurveySession.objects.get(survey=single_survey)
        self.assertIsNone(session.language)

    def test_missing_translation_fallback_in_section_title(self):
        """
        GIVEN a multilingual survey where section lacks translation for a language
        WHEN user selects that language
        THEN original section title is displayed as fallback
        """
        # Create a new section without Russian translation
        untranslated_section = SurveySection.objects.create(
            survey_header=self.survey,
            name="untranslated_section",
            title="Untranslated Section Title",
            subheading="Untranslated subheading",
            code="UNT1",
            is_head=False
        )
        # Link from main section
        self.section.next_section = untranslated_section
        self.section.save()

        # Select Russian
        self.client.post('/surveys/integration_multilang/language/', {'language': 'ru'})

        # Access untranslated section
        response = self.client.get('/surveys/integration_multilang/untranslated_section/')
        self.assertEqual(response.status_code, 200)

        # Verify original title is shown as fallback
        self.assertEqual(response.context['section_title'], "Untranslated Section Title")
        self.assertEqual(response.context['section_subheading'], "Untranslated subheading")


class PrimaryLanguageBaseFieldsTest(TestCase):
    """The primary language lives in base fields; translation rows are for
    non-primary languages only (change: fix-primary-language-duplicate-fields)."""

    def setUp(self):
        self.org = _make_org('PrimaryLangOrg')
        self.user = User.objects.create_user(username='primlang', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='primlang', password='pass')

    def _survey(self, languages):
        survey = SurveyHeader.objects.create(
            name='primlang_survey', visibility='private', organization=self.org,
            available_languages=languages,
        )
        section = SurveySection.objects.create(
            survey_header=survey, name='sec1', title='Base title', code='S1', is_head=True,
        )
        return survey, section

    def test_single_language_save_creates_no_translation_rows(self):
        """
        GIVEN a single-language ["es"] survey
        WHEN the section form is saved with a stale translation_es_title value
        THEN no SurveySectionTranslation row is created — the primary language
             lives in the base field only
        """
        survey, section = self._survey(['es'])
        response = self.client.post(
            f'/editor/surveys/{survey.uuid}/sections/{section.id}/',
            {'title': 'Título real', 'subheading': '', 'code': 'S1',
             'translation_es_title': 'Fantasma', 'translation_es_subheading': ''},
        )
        self.assertIn(response.status_code, (200, 204, 302))
        section.refresh_from_db()
        self.assertEqual(section.title, 'Título real')
        self.assertFalse(SurveySectionTranslation.objects.filter(section=section).exists())

    def test_stale_primary_translation_post_is_ignored_multilingual(self):
        """
        GIVEN a ["pt", "es"] survey
        WHEN the section form posts translation values for both pt and es
        THEN no row is created: the pt key names the primary language and the es
             one is ignored too, because the modal stopped writing translations
             (change translation-table — the Translations tab writes them)
        """
        survey, section = self._survey(['pt', 'es'])
        response = self.client.post(
            f'/editor/surveys/{survey.uuid}/sections/{section.id}/',
            {'title': 'Título base', 'subheading': '', 'code': 'S1',
             'translation_pt_title': 'Fantasma pt',
             'translation_es_title': 'Título es'},
        )
        self.assertIn(response.status_code, (200, 204, 302))
        self.assertFalse(SurveySectionTranslation.objects.filter(section=section).exists())

    def test_question_save_skips_primary_language_row(self):
        """
        GIVEN a ["pt", "es"] survey
        WHEN a question is created with pt and es translation values posted
        THEN no QuestionTranslation row exists — the modal is a read-only mirror
             of the Translations tab (change translation-table)
        """
        survey, section = self._survey(['pt', 'es'])
        response = self.client.post(
            f'/editor/surveys/{survey.uuid}/sections/{section.id}/questions/new/',
            {'name': 'Pergunta base', 'input_type': 'text', 'color': '#000000',
             'translation_pt_name': 'Fantasma', 'translation_es_name': 'Pregunta es'},
        )
        self.assertEqual(response.status_code, 200)
        question = Question.objects.get(survey_section=section, name='Pergunta base')
        self.assertFalse(QuestionTranslation.objects.filter(question=question).exists())

    def test_editor_templates_render_translation_inputs_for_non_primary_only(self):
        """
        GIVEN a ["pt", "es"] survey
        WHEN the section detail partial is rendered
        THEN the es translation mirror is present, a pt one is not, and the base
             label names the primary language
        """
        survey, section = self._survey(['pt', 'es'])
        response = self.client.get(
            f'/editor/surveys/{survey.uuid}/sections/{section.id}/',
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="translations-es"', html)
        self.assertIn('?to=es#row-section:S1:title', html)
        self.assertNotIn('translations-pt', html)
        self.assertNotIn('translation_es_title', html)
        self.assertIn('(Portuguese)', html)

    def test_single_language_survey_renders_no_translation_inputs(self):
        """
        GIVEN a single-language ["es"] survey
        WHEN the section detail partial is rendered
        THEN no translation inputs and no language suffix on base labels appear
        """
        survey, section = self._survey(['es'])
        response = self.client.get(
            f'/editor/surveys/{survey.uuid}/sections/{section.id}/',
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn('translation_es_title', html)
        self.assertNotIn('(Spanish)', html)


class FoldPrimaryTranslationsMigrationTest(TestCase):
    """The 0052 data migration logic: fold primary rows into base, normalize
    choice shapes, preserve exactly what respondents currently see."""

    def setUp(self):
        self.org = _make_org('FoldMigrationOrg')

    def _run_migration(self):
        from importlib import import_module
        migration = import_module(
            'survey.migrations.0052_fold_primary_language_translations',
        )
        from django.apps import apps as live_apps
        migration.fold_primary_translations(live_apps, None)

    def test_divergent_primary_row_wins_over_base(self):
        """
        GIVEN a single-language survey whose section has a non-empty primary
              translation row diverging from the base field (the survey-465 shape)
        WHEN the migration runs
        THEN the base field takes the translation's value (what respondents saw
             via the fallback) and the row is gone
        """
        survey = SurveyHeader.objects.create(
            name='fold_465', organization=self.org, available_languages=['es'],
        )
        section = SurveySection.objects.create(
            survey_header=survey, name='sec1', title='AI text', subheading='AI sub',
            code='S1', is_head=True,
        )
        SurveySectionTranslation.objects.create(
            section=section, language='es', title='Author text', subheading='',
        )

        self._run_migration()

        section.refresh_from_db()
        # Non-empty translation wins; empty subheading means base was showing.
        self.assertEqual(section.title, 'Author text')
        self.assertEqual(section.subheading, 'AI sub')
        self.assertFalse(SurveySectionTranslation.objects.filter(section=section).exists())

    def test_identical_primary_rows_folded_on_multilingual_survey(self):
        """
        GIVEN a ["pt", "es"] survey with a pt question row identical to base
              (the survey-467 shape)
        WHEN the migration runs
        THEN the pt row is deleted, the es row survives, base text is unchanged
        """
        survey = SurveyHeader.objects.create(
            name='fold_467', organization=self.org, available_languages=['pt', 'es'],
        )
        section = SurveySection.objects.create(
            survey_header=survey, name='sec1', title='Base', code='S1', is_head=True,
        )
        question = Question.objects.create(
            survey_section=section, name='Pergunta', input_type='text',
        )
        QuestionTranslation.objects.create(question=question, language='pt', name='Pergunta')
        QuestionTranslation.objects.create(question=question, language='es', name='Pregunta')

        self._run_migration()

        question.refresh_from_db()
        self.assertEqual(question.name, 'Pergunta')
        languages = set(
            QuestionTranslation.objects.filter(question=question)
            .values_list('language', flat=True)
        )
        self.assertEqual(languages, {'es'})

    def test_choice_shapes_are_normalized(self):
        """
        GIVEN a single-language survey with dict choice names and a
              multilingual survey whose dict lacks the primary key
        WHEN the migration runs
        THEN the first flattens to strings and the second gains the primary key
             with the value the resolver currently falls back to
        """
        single = SurveyHeader.objects.create(
            name='fold_single', organization=self.org, available_languages=['es'],
        )
        s_section = SurveySection.objects.create(
            survey_header=single, name='sec1', title='S', code='S1', is_head=True,
        )
        s_q = Question.objects.create(
            survey_section=s_section, name='Q', input_type='choice',
            choices=[{'code': 1, 'name': {'es': 'Sí'}}, {'code': 2, 'name': 'No'}],
        )
        multi = SurveyHeader.objects.create(
            name='fold_multi', organization=self.org, available_languages=['pt', 'en'],
        )
        m_section = SurveySection.objects.create(
            survey_header=multi, name='sec1', title='S', code='S1', is_head=True,
        )
        m_q = Question.objects.create(
            survey_section=m_section, name='Q', input_type='choice',
            choices=[{'code': 1, 'name': {'en': 'Yes'}}],
        )

        self._run_migration()

        s_q.refresh_from_db()
        self.assertEqual(s_q.choices, [{'code': 1, 'name': 'Sí'}, {'code': 2, 'name': 'No'}])
        m_q.refresh_from_db()
        # Missing pt key gains what get_choice_name resolves today ('en' fallback).
        self.assertEqual(m_q.choices[0]['name'], {'pt': 'Yes', 'en': 'Yes'})

    def test_migration_is_idempotent(self):
        """
        GIVEN a survey already folded once
        WHEN the migration runs again
        THEN nothing changes
        """
        survey = SurveyHeader.objects.create(
            name='fold_idem', organization=self.org, available_languages=['es'],
        )
        section = SurveySection.objects.create(
            survey_header=survey, name='sec1', title='T', code='S1', is_head=True,
        )
        SurveySectionTranslation.objects.create(section=section, language='es', title='T2')

        self._run_migration()
        section.refresh_from_db()
        first_title = section.title
        self._run_migration()
        section.refresh_from_db()

        self.assertEqual(section.title, first_title)
        self.assertEqual(first_title, 'T2')
