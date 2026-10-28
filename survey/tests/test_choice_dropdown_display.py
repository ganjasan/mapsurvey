"""Tests for the `choice-dropdown-display` capability (openspec/specs/choice-dropdown-display/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from io import BytesIO
import json
import re
import zipfile
from survey.models import Organization, SurveyHeader, SurveySection, Question, SurveySession, Answer
from survey.serialization import export_survey_to_zip, import_survey_from_zip
from survey.forms import SurveySectionAnswerForm


class ChoiceDropdownDisplayTest(TestCase):
    """Respondent rendering of choice questions with display_style 'dropdown'."""

    AREAS = [{"code": i, "name": f"Area {i}"} for i in range(1, 6)]

    def setUp(self):
        self.client = Client()
        self.org = Organization.objects.create(name="Dropdown Org")
        self.survey = SurveyHeader.objects.create(
            name="choice_dropdown_survey",
            organization=self.org,
            redirect_url="/thanks/",
            status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="section1",
            title="Section One",
            code="S1",
            is_head=True,
        )
        self.choice_q = Question.objects.create(
            survey_section=self.section,
            code="CDQ001",
            name="Which counting area?",
            input_type="choice",
            choices=self.AREAS,
            order_number=1,
        )

    def _visit(self):
        return self.client.get('/surveys/choice_dropdown_survey/section1/')

    def test_default_choice_renders_radios_without_dropdown(self):
        """
        GIVEN a choice question with display_style 'default'
        WHEN the section is rendered
        THEN the radio list appears and no dropdown markup is emitted
        """
        response = self._visit()

        self.assertContains(response, 'type="radio" name="CDQ001"')
        self.assertNotContains(response, 'choice-dropdown')

    def test_dropdown_style_renders_search_widget(self):
        """
        GIVEN a choice question with display_style 'dropdown'
        WHEN the section is rendered
        THEN the searchable dropdown markup replaces the radio list
        """
        self.choice_q.display_style = 'dropdown'
        self.choice_q.save()

        response = self._visit()

        self.assertContains(response, 'data-choice-dropdown')
        self.assertContains(response, 'cd-search')
        self.assertContains(response, 'data-value="3"')
        self.assertNotContains(response, 'type="radio" name="CDQ001"')

    def test_dropdown_select_submits_under_question_code(self):
        """
        GIVEN a dropdown-styled choice question
        WHEN the section is rendered
        THEN the hidden select carries the question's field name, so the
             submitted value is identical to a radio submission
        """
        self.choice_q.display_style = 'dropdown'
        self.choice_q.save()

        response = self._visit()

        self.assertContains(response, 'name="CDQ001"')

    def test_dropdown_on_rating_question_is_ignored(self):
        """
        GIVEN a rating question wrongly carrying display_style 'dropdown'
        WHEN the display style is resolved
        THEN the survey-wide rating default applies
        """
        rating_q = Question.objects.create(
            survey_section=self.section,
            code="CDQ002",
            name="Rate it",
            input_type="rating",
            choices=[{"code": 1, "name": "bad"}, {"code": 2, "name": "good"}],
            display_style='dropdown',
            order_number=2,
        )

        resolved = SurveySectionAnswerForm.resolve_display_style(rating_q, 'scale_strip')

        self.assertEqual(resolved, 'scale_strip')

    def test_rating_style_on_choice_question_resolves_to_default(self):
        """
        GIVEN a choice question carrying a rating-only style value
        WHEN the display style is resolved
        THEN it falls back to the plain radio rendering
        """
        self.choice_q.display_style = 'list_pips'
        self.choice_q.save()

        resolved = SurveySectionAnswerForm.resolve_display_style(self.choice_q, 'scale_strip')

        self.assertEqual(resolved, 'default')

    def test_required_dropdown_rejects_empty_submission(self):
        """
        GIVEN a required dropdown-styled choice question
        WHEN the single-question form is bound without a value
        THEN validation fails exactly as it would for radios
        """
        self.choice_q.display_style = 'dropdown'
        self.choice_q.required = True
        self.choice_q.save()

        form = SurveySectionAnswerForm.single_question_form(self.choice_q)
        field = form.fields[self.choice_q.code]

        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            field.clean('')
        self.assertEqual(field.clean('3'), '3')


class ChoiceDropdownEmptyValueTest(TestCase):
    """An untouched dropdown must hold no value.

    A <select> with no blank entry is never empty — the browser selects the
    first option, so the widget used to arrive pre-answered: the required check
    saw a value and passed the card, and the POST stored choice 1 as if the
    respondent had picked it (three of four answers on the live Olney demo).
    """

    AREAS = [{"code": i, "name": f"Area {i}"} for i in range(1, 6)]

    def setUp(self):
        self.client = Client()
        self.org = Organization.objects.create(name="Dropdown Empty Org")
        self.survey = SurveyHeader.objects.create(
            name="dropdown_empty_survey", organization=self.org,
            redirect_url="/thanks/", status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="section1", title="S1", code="S1", is_head=True,
        )
        self.question = Question.objects.create(
            survey_section=self.section, code="CDE001", name="Which counting area?",
            input_type="choice", choices=self.AREAS, order_number=1,
            display_style='dropdown', required=True,
        )

    def _visit(self):
        return self.client.get('/surveys/dropdown_empty_survey/section1/')

    def test_unanswered_dropdown_selects_the_placeholder(self):
        """
        GIVEN a dropdown question with no stored answer
        WHEN the section is rendered
        THEN the hidden select carries a selected blank option, so the browser cannot fall back to the first real choice
        """
        html = self._visit().content.decode()

        self.assertIn('<option value="" selected>', html)
        self.assertNotIn('<option value="1" selected>', html)

    def test_placeholder_is_absent_from_the_visible_list(self):
        """
        GIVEN a dropdown question
        WHEN the section is rendered
        THEN the visible option list holds only real choices
        """
        html = self._visit().content.decode()

        options = re.findall(r'<li class="cd-option"[^>]*data-value="([^"]*)"', html)
        self.assertEqual(options, ['1', '2', '3', '4', '5'])

    def test_stored_answer_selects_its_own_option(self):
        """
        GIVEN a session that already answered the dropdown question
        WHEN the section is rendered again
        THEN that option is selected and the placeholder is not
        """
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(
            survey_session=session, question=self.question, selected_choices=[3],
        )
        s = self.client.session
        s['survey_session_id'] = session.id
        s.save()

        html = self._visit().content.decode()

        self.assertIn('<option value="3" selected>', html)
        self.assertNotIn('<option value="" selected>', html)

    def test_empty_submission_stores_no_answer(self):
        """
        GIVEN a section whose dropdown question was never touched
        WHEN it is submitted with the placeholder's empty value
        THEN no answer is stored for that question
        """
        self._visit()
        session_id = self.client.session['survey_session_id']

        self.client.post('/surveys/dropdown_empty_survey/section1/', {'CDE001': ''})

        self.assertFalse(
            Answer.objects.filter(survey_session_id=session_id, question=self.question).exists()
        )

    def test_chosen_option_still_stores_its_code(self):
        """
        GIVEN a respondent who picked an option
        WHEN the section is submitted
        THEN the answer stores that code, unchanged by the placeholder
        """
        self._visit()
        session_id = self.client.session['survey_session_id']

        self.client.post('/surveys/dropdown_empty_survey/section1/', {'CDE001': '3'})

        answer = Answer.objects.get(survey_session_id=session_id, question=self.question)
        self.assertEqual(answer.selected_choices, [3])


class ChoiceDropdownSerializationTest(TestCase):
    """display_style 'dropdown' in export/import round-trip."""

    def setUp(self):
        self.org = Organization.objects.create(name="DropdownSer Org")
        self.survey = SurveyHeader.objects.create(
            name="dropdown_ser_survey",
            organization=self.org,
            redirect_url="/thanks/",
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="s1",
            title="S1",
            code="S1",
            is_head=True,
        )
        self.question = Question.objects.create(
            survey_section=self.section,
            code="CDS001",
            name="Pick area",
            input_type="choice",
            choices=[{"code": 1, "name": "A"}, {"code": 2, "name": "B"}],
            display_style='dropdown',
            order_number=1,
        )

    def _roundtrip(self, mutate=None):
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")
        output.seek(0)
        with zipfile.ZipFile(output, 'r') as zf:
            survey_json = json.loads(zf.read("survey.json"))

        survey_json["survey"]["name"] = "dropdown_ser_imported"
        if mutate:
            mutate(survey_json["survey"]["sections"][0]["questions"][0])

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_json))
        import_buffer.seek(0)

        imported_survey, _ = import_survey_from_zip(import_buffer)
        return Question.objects.get(
            survey_section__survey_header=imported_survey, name="Pick area",
        )

    def test_dropdown_round_trips_on_choice_question(self):
        """
        GIVEN a choice question with display_style 'dropdown'
        WHEN the survey is exported and re-imported
        THEN the imported question keeps display_style 'dropdown'
        """
        imported = self._roundtrip()

        self.assertEqual(imported.display_style, 'dropdown')

    def test_dropdown_on_non_choice_question_falls_back(self):
        """
        GIVEN an archive whose text question carries display_style 'dropdown'
        WHEN the archive is imported
        THEN the question falls back to display_style 'default'
        """
        def mutate(q):
            q["input_type"] = "text"
            q["choices"] = None
            q["display_style"] = "dropdown"

        imported = self._roundtrip(mutate)

        self.assertEqual(imported.display_style, 'default')


class ChoiceDropdownEditorFormTest(TestCase):
    """QuestionForm accepts 'dropdown' for choice questions only."""

    def _form_data(self, **overrides):
        data = {
            'name': 'Pick one',
            'subtext': '',
            'input_type': 'choice',
            'color': '#000000',
            'icon_class': '',
            'display_style': 'dropdown',
        }
        data.update(overrides)
        return data

    def test_dropdown_persists_on_choice_question(self):
        """
        GIVEN a question form for a choice question with display_style 'dropdown'
        WHEN the form is validated
        THEN the cleaned display_style is 'dropdown'
        """
        from survey.editor_forms import QuestionForm
        form = QuestionForm(self._form_data())

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['display_style'], 'dropdown')

    def test_dropdown_on_text_question_normalizes_to_default(self):
        """
        GIVEN a question form for a text question submitted with 'dropdown'
        WHEN the form is validated
        THEN the cleaned display_style is normalized to 'default'
        """
        from survey.editor_forms import QuestionForm
        form = QuestionForm(self._form_data(input_type='text'))

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['display_style'], 'default')

    def test_rating_style_on_choice_question_normalizes_to_default(self):
        """
        GIVEN a question form for a choice question submitted with 'stars'
        WHEN the form is validated
        THEN the cleaned display_style is normalized to 'default'
        """
        from survey.editor_forms import QuestionForm
        form = QuestionForm(self._form_data(display_style='stars'))

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['display_style'], 'default')
