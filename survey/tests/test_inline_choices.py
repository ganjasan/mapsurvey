"""Tests for the `inline-choices` capability (openspec/specs/inline-choices/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from survey.models import Organization, SurveyHeader, SurveySection, Question, SurveySession, Answer, ChoicesValidator


class InlineChoicesTest(TestCase):
    """Tests for inline choices functionality on Question and Answer models."""

    def setUp(self):
        """Set up test data with inline choices."""
        self.org = Organization.objects.create(name="Inline Choices Test Org")
        self.survey = SurveyHeader.objects.create(
            name="inline_choices_test",
            organization=self.org
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="section1",
            code="IC1",
            is_head=True
        )
        self.multilingual_choices = [
            {"code": 1, "name": {"en": "Yes", "ru": "Да", "de": "Ja"}},
            {"code": 2, "name": {"en": "No", "ru": "Нет", "de": "Nein"}},
        ]
        self.question = Question.objects.create(
            survey_section=self.section,
            code="Q_IC",
            order_number=1,
            name="Choice Question",
            input_type="choice",
            choices=self.multilingual_choices
        )
        self.session = SurveySession.objects.create(survey=self.survey)

    def test_get_choice_name_returns_requested_language(self):
        """
        GIVEN a question with multilingual choices
        WHEN get_choice_name is called with a specific language
        THEN the name in that language is returned
        """
        self.assertEqual(self.question.get_choice_name(1, "en"), "Yes")
        self.assertEqual(self.question.get_choice_name(1, "ru"), "Да")
        self.assertEqual(self.question.get_choice_name(2, "de"), "Nein")

    def test_get_choice_name_falls_back_to_english(self):
        """
        GIVEN a question with multilingual choices
        WHEN get_choice_name is called with a language that has no translation
        THEN the English name is returned as fallback
        """
        self.assertEqual(self.question.get_choice_name(1, "fr"), "Yes")
        self.assertEqual(self.question.get_choice_name(2, "ja"), "No")

    def test_get_choice_name_falls_back_to_first_available(self):
        """
        GIVEN a question with choices that have no English translation
        WHEN get_choice_name is called with an unavailable language
        THEN the first available translation is returned
        """
        no_en_choices = [
            {"code": 1, "name": {"ru": "Да", "de": "Ja"}},
        ]
        question = Question.objects.create(
            survey_section=self.section,
            code="Q_NOEN",
            order_number=2,
            name="No English",
            input_type="choice",
            choices=no_en_choices
        )
        result = question.get_choice_name(1, "fr")
        self.assertIn(result, ["Да", "Ja"])

    def test_get_choice_name_returns_code_for_missing_choice(self):
        """
        GIVEN a question with choices
        WHEN get_choice_name is called with a non-existent code
        THEN the string representation of the code is returned
        """
        self.assertEqual(self.question.get_choice_name(99, "en"), "99")

    def test_get_choice_name_with_string_name(self):
        """
        GIVEN a question with choices where name is a plain string
        WHEN get_choice_name is called
        THEN the string name is returned regardless of language
        """
        simple_choices = [
            {"code": 1, "name": "Simple Choice"},
        ]
        question = Question.objects.create(
            survey_section=self.section,
            code="Q_SIMPLE",
            order_number=3,
            name="Simple",
            input_type="choice",
            choices=simple_choices
        )
        self.assertEqual(question.get_choice_name(1, "en"), "Simple Choice")
        self.assertEqual(question.get_choice_name(1, "ru"), "Simple Choice")

    def test_get_choice_name_with_none_language(self):
        """
        GIVEN a question with multilingual choices
        WHEN get_choice_name is called with lang=None
        THEN the English name is returned as fallback
        """
        self.assertEqual(self.question.get_choice_name(1, None), "Yes")
        self.assertEqual(self.question.get_choice_name(2), "No")

    def test_choices_validator_accepts_valid_choices(self):
        """
        GIVEN valid choices structure
        WHEN ChoicesValidator is called
        THEN no error is raised
        """
        validator = ChoicesValidator()
        validator([
            {"code": 1, "name": "Choice A"},
            {"code": 2, "name": {"en": "Choice B", "ru": "Выбор Б"}},
        ])

    def test_choices_validator_rejects_non_list(self):
        """
        GIVEN a non-list value
        WHEN ChoicesValidator is called
        THEN ValidationError is raised
        """
        from django.core.exceptions import ValidationError
        validator = ChoicesValidator()
        with self.assertRaises(ValidationError):
            validator("not a list")

    def test_choices_validator_rejects_missing_code(self):
        """
        GIVEN a choice dict without 'code' key
        WHEN ChoicesValidator is called
        THEN ValidationError is raised
        """
        from django.core.exceptions import ValidationError
        validator = ChoicesValidator()
        with self.assertRaises(ValidationError):
            validator([{"name": "No code"}])

    def test_choices_validator_rejects_missing_name(self):
        """
        GIVEN a choice dict without 'name' key
        WHEN ChoicesValidator is called
        THEN ValidationError is raised
        """
        from django.core.exceptions import ValidationError
        validator = ChoicesValidator()
        with self.assertRaises(ValidationError):
            validator([{"code": 1}])

    def test_choices_validator_rejects_non_dict_items(self):
        """
        GIVEN a list containing non-dict items
        WHEN ChoicesValidator is called
        THEN ValidationError is raised
        """
        from django.core.exceptions import ValidationError
        validator = ChoicesValidator()
        with self.assertRaises(ValidationError):
            validator(["not a dict"])

    def test_selected_choices_saved_and_retrieved(self):
        """
        GIVEN an answer with selected_choices
        WHEN saved and retrieved from database
        THEN selected_choices are preserved
        """
        answer = Answer.objects.create(
            survey_session=self.session,
            question=self.question,
            selected_choices=[1, 2]
        )
        answer.refresh_from_db()
        self.assertEqual(answer.selected_choices, [1, 2])

    def test_get_selected_choice_names_returns_names(self):
        """
        GIVEN an answer with selected_choices
        WHEN get_selected_choice_names is called
        THEN choice names are returned in the requested language
        """
        answer = Answer.objects.create(
            survey_session=self.session,
            question=self.question,
            selected_choices=[1, 2]
        )
        self.assertEqual(answer.get_selected_choice_names("en"), ["Yes", "No"])
        self.assertEqual(answer.get_selected_choice_names("ru"), ["Да", "Нет"])

    def test_get_selected_choice_names_empty_for_no_choices(self):
        """
        GIVEN an answer with no selected_choices
        WHEN get_selected_choice_names is called
        THEN an empty list is returned
        """
        answer = Answer.objects.create(
            survey_session=self.session,
            question=self.question
        )
        self.assertEqual(answer.get_selected_choice_names("en"), [])
