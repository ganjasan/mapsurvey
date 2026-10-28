"""Tests for the `rating-display-style` capability (openspec/specs/rating-display-style/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from io import BytesIO
import json
import zipfile
from survey.models import Organization, SurveyHeader, SurveySection, Question, Answer, Membership
from survey.serialization import serialize_questions, export_survey_to_zip, import_survey_from_zip
from survey.cloning import clone_question
from survey.editor_forms import SurveyHeaderForm
from survey.tests.helpers import _make_org


class RatingDisplayStyleTest(TestCase):
    """Tests for rating question display styles (scale_strip / list_pips)."""

    LIKERT = [
        {"code": 1, "name": "very unsure"},
        {"code": 2, "name": "rather unsure"},
        {"code": 3, "name": "undecided"},
        {"code": 4, "name": "rather confident"},
        {"code": 5, "name": "very confident"},
    ]

    def setUp(self):
        self.client = Client()
        self.org = Organization.objects.create(name="Rating Org")
        self.survey = SurveyHeader.objects.create(
            name="rating_style_survey",
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
        self.rating_q = Question.objects.create(
            survey_section=self.section,
            name="How confident are you?",
            input_type="rating",
            choices=self.LIKERT,
            order_number=1,
        )

    def _visit(self):
        return self.client.get('/surveys/rating_style_survey/section1/')

    def test_default_display_style_inherits_survey_default(self):
        """
        GIVEN a rating question created without an explicit display_style
        WHEN the model instance is inspected and the section rendered
        THEN display_style is 'default' and the question renders as a scale strip
        """
        self.assertEqual(self.rating_q.display_style, 'default')

        response = self._visit()

        self.assertContains(response, 'rating-scale-strip__cells')

    def test_survey_default_applies_to_inheriting_question(self):
        """
        GIVEN a survey whose style_settings default rating style is list_pips
        WHEN a rating question with display_style 'default' is rendered
        THEN it renders as a labeled list
        """
        self.survey.style_settings = {'rating_display_style': 'list_pips'}
        self.survey.save()

        response = self._visit()

        self.assertContains(response, 'class="rating-list-pips"')
        self.assertNotContains(response, 'rating-scale-strip__cells')

    def test_question_override_wins_over_survey_default(self):
        """
        GIVEN a survey default of list_pips and a question explicitly set to scale_strip
        WHEN the section is rendered
        THEN the question renders as a scale strip
        """
        self.survey.style_settings = {'rating_display_style': 'list_pips'}
        self.survey.save()
        self.rating_q.display_style = 'scale_strip'
        self.rating_q.save()

        response = self._visit()

        self.assertContains(response, 'rating-scale-strip__cells')
        self.assertNotContains(response, 'class="rating-list-pips"')

    def test_mixed_styles_render_independently(self):
        """
        GIVEN two rating questions in one section, one scale_strip and one list_pips
        WHEN the section is rendered
        THEN each question renders in its own style on the same page
        """
        self.rating_q.display_style = 'scale_strip'
        self.rating_q.save()
        Question.objects.create(
            survey_section=self.section,
            name="Second rating",
            input_type="rating",
            choices=self.LIKERT,
            display_style='list_pips',
            order_number=2,
        )

        response = self._visit()

        self.assertContains(response, 'rating-scale-strip__cells', count=1)
        self.assertContains(response, 'class="rating-list-pips"', count=1)

    def test_scale_strip_markup(self):
        """
        GIVEN a rating question with 5 worded choices and default display_style
        WHEN the section is rendered
        THEN it shows one grid row of 5 numbered cells with first/last anchors and a chip
        """
        response = self._visit()

        self.assertContains(response, 'class="rating-scale-strip__cell"', count=5)
        self.assertContains(response, 'repeat(5, 1fr)')
        self.assertContains(response, 'very unsure')
        self.assertContains(response, 'very confident')
        self.assertContains(response, 'rating-scale-strip__chip')
        self.assertContains(response, 'data-label="rather confident"')

    def test_scale_strip_seven_points_single_row(self):
        """
        GIVEN a rating question with 7 choices
        WHEN the section is rendered as scale_strip
        THEN all 7 cells share one grid row
        """
        self.rating_q.choices = [
            {"code": i, "name": f"level {i}"} for i in range(1, 8)
        ]
        self.rating_q.save()

        response = self._visit()

        self.assertContains(response, 'class="rating-scale-strip__cell"', count=7)
        self.assertContains(response, 'repeat(7, 1fr)')

    def test_list_pips_markup(self):
        """
        GIVEN a rating question with display_style list_pips
        WHEN the section is rendered
        THEN it shows 5 labeled rows with intensity pips (1+2+3+4+5 filled dots)
        """
        self.rating_q.display_style = 'list_pips'
        self.rating_q.save()

        response = self._visit()

        self.assertContains(response, 'class="rating-list-pips__row"', count=5)
        self.assertContains(response, 'class="rating-list-pips__pips"', count=5)
        self.assertContains(response, ' class="on"', count=15)
        self.assertContains(response, 'rather confident')
        self.assertNotContains(response, 'rating-scale-strip__cell')

    def test_prepopulation_restores_checked_state(self):
        """
        GIVEN a submitted rating answer
        WHEN the respondent revisits the section
        THEN the previously selected radio renders checked
        """
        self._visit()
        self.client.post('/surveys/rating_style_survey/section1/', {
            self.rating_q.code: '4',
        })

        response = self._visit()

        self.assertContains(response, 'checked')

    def test_submission_stores_choice_code(self):
        """
        GIVEN a rating question rendered in either display style
        WHEN the respondent submits option code 4
        THEN the Answer stores selected_choices [4] exactly as before this change
        """
        self._visit()
        self.client.post('/surveys/rating_style_survey/section1/', {
            self.rating_q.code: '4',
        })

        session_id = self.client.session['survey_session_id']
        answer = Answer.objects.get(
            survey_session_id=session_id, question=self.rating_q,
        )
        self.assertEqual(answer.selected_choices, [4])

    def test_non_rating_question_ignores_display_style(self):
        """
        GIVEN a choice question with display_style set to list_pips
        WHEN the section is rendered
        THEN no rating-specific markup is emitted for it
        """
        self.rating_q.delete()
        Question.objects.create(
            survey_section=self.section,
            name="Agree?",
            input_type="choice",
            choices=[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}],
            display_style='list_pips',
            order_number=1,
        )

        response = self._visit()

        self.assertNotContains(response, 'rating-list-pips__row')
        self.assertNotContains(response, 'rating-scale-strip__cell')


class RatingDisplayStyleSerializationTest(TestCase):
    """Tests for display_style in export/import and cloning."""

    def setUp(self):
        self.org = Organization.objects.create(name="RatingSer Org")
        self.survey = SurveyHeader.objects.create(
            name="rating_ser_survey",
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
            code="RQ001",
            name="Rate it",
            input_type="rating",
            choices=[{"code": 1, "name": "bad"}, {"code": 2, "name": "good"}],
            display_style='list_pips',
            order_number=1,
        )

    def _export_mutate_import(self, mutate):
        """Export the survey, apply `mutate(question_dict)`, import under a new name."""
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")
        output.seek(0)
        with zipfile.ZipFile(output, 'r') as zf:
            survey_json = json.loads(zf.read("survey.json"))

        survey_json["survey"]["name"] = "rating_ser_imported"
        mutate(survey_json["survey"]["sections"][0]["questions"][0])

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_json))
        import_buffer.seek(0)

        imported_survey, _ = import_survey_from_zip(import_buffer)
        return Question.objects.get(
            survey_section__survey_header=imported_survey, name="Rate it",
        )

    def test_export_includes_display_style(self):
        """
        GIVEN a rating question with display_style list_pips
        WHEN the section's questions are serialized
        THEN the question dict contains display_style 'list_pips'
        """
        data = serialize_questions(self.section)

        self.assertEqual(data[0]["display_style"], "list_pips")

    def test_import_legacy_archive_defaults_display_style(self):
        """
        GIVEN a survey.json without the display_style key (pre-change archive)
        WHEN the archive is imported
        THEN the rating question gets display_style 'default'
        """
        imported_q = self._export_mutate_import(
            lambda q: q.pop("display_style", None)
        )

        self.assertEqual(imported_q.display_style, 'default')

    def test_import_garbage_display_style_falls_back(self):
        """
        GIVEN a hand-edited survey.json with an unknown display_style value
        WHEN the archive is imported
        THEN the question imports with display_style 'default'
        """
        def set_garbage(q):
            q["display_style"] = "fancy"

        imported_q = self._export_mutate_import(set_garbage)

        self.assertEqual(imported_q.display_style, 'default')

    def test_style_settings_roundtrip(self):
        """
        GIVEN a survey with style_settings rating_display_style list_pips
        WHEN the survey is exported and re-imported
        THEN the imported survey keeps the style_settings value
        """
        self.survey.style_settings = {'rating_display_style': 'list_pips'}
        self.survey.save()

        imported_q = self._export_mutate_import(lambda q: None)

        imported_survey = imported_q.survey_section.survey_header
        self.assertEqual(
            imported_survey.style_settings, {'rating_display_style': 'list_pips'}
        )

    def test_import_garbage_style_settings_dropped(self):
        """
        GIVEN a survey.json whose style_settings holds unknown keys and values
        WHEN the archive is imported
        THEN only valid style keys survive
        """
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")
        output.seek(0)
        with zipfile.ZipFile(output, 'r') as zf:
            survey_json = json.loads(zf.read("survey.json"))

        survey_json["survey"]["name"] = "rating_ser_garbage"
        survey_json["survey"]["style_settings"] = {
            "rating_display_style": "fancy", "font_size": "42px",
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_json))
        import_buffer.seek(0)

        imported_survey, _ = import_survey_from_zip(import_buffer)

        self.assertEqual(imported_survey.style_settings, {})

    def test_roundtrip_preserves_display_style(self):
        """
        GIVEN a rating question with display_style list_pips
        WHEN the survey is exported and re-imported unchanged
        THEN the imported question keeps display_style 'list_pips'
        """
        imported_q = self._export_mutate_import(lambda q: None)

        self.assertEqual(imported_q.display_style, 'list_pips')

    def test_clone_question_preserves_display_style(self):
        """
        GIVEN a rating question with display_style list_pips
        WHEN clone_question is called
        THEN the clone keeps display_style 'list_pips'
        """
        clone = clone_question(
            self.question, target_section=self.section, regenerate_code=True,
        )

        self.assertEqual(clone.display_style, 'list_pips')


class RatingDisplayStyleEditorTest(TestCase):
    """Tests for the display_style picker in the editor question modal."""

    def setUp(self):
        self.org = _make_org('RatingEditorOrg')
        self.user = User.objects.create_user(username='rating_editor', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='rating_editor', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='rating_editor_survey', visibility='private', organization=self.org,
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section 1', code='S1', is_head=True,
        )

    def test_create_rating_question_with_display_style(self):
        """
        GIVEN the question create endpoint
        WHEN a rating question is posted with display_style list_pips
        THEN the saved question has display_style 'list_pips'
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/',
            {
                'name': 'Confidence',
                'input_type': 'rating',
                'color': '#000000',
                'display_style': 'list_pips',
                'choices_json': json.dumps([{"code": 1, "name": "low"}, {"code": 2, "name": "high"}]),
            },
        )
        self.assertEqual(response.status_code, 200)
        q = Question.objects.get(survey_section=self.section, name='Confidence')
        self.assertEqual(q.display_style, 'list_pips')

    def test_post_without_display_style_defaults(self):
        """
        GIVEN the question create endpoint
        WHEN a rating question is posted without display_style (legacy client)
        THEN the saved question defaults to 'default' (inherit survey style)
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/',
            {
                'name': 'Confidence',
                'input_type': 'rating',
                'color': '#000000',
                'choices_json': json.dumps([{"code": 1, "name": "low"}, {"code": 2, "name": "high"}]),
            },
        )
        self.assertEqual(response.status_code, 200)
        q = Question.objects.get(survey_section=self.section, name='Confidence')
        self.assertEqual(q.display_style, 'default')

    def test_editing_one_question_leaves_siblings_untouched(self):
        """
        GIVEN two rating questions in one section
        WHEN one question's display_style is changed via the edit endpoint
        THEN the other question's display_style is unchanged
        """
        choices = [{"code": 1, "name": "low"}, {"code": 2, "name": "high"}]
        q1 = Question.objects.create(
            survey_section=self.section, name='First', input_type='rating',
            choices=choices, display_style='scale_strip', order_number=1,
        )
        q2 = Question.objects.create(
            survey_section=self.section, name='Second', input_type='rating',
            choices=choices, display_style='scale_strip', order_number=2,
        )

        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/{q1.id}/edit/',
            {
                'name': 'First',
                'input_type': 'rating',
                'color': '#000000',
                'display_style': 'list_pips',
                'choices_json': json.dumps(choices),
            },
        )
        self.assertEqual(response.status_code, 200)

        q1.refresh_from_db()
        q2.refresh_from_db()
        self.assertEqual(q1.display_style, 'list_pips')
        self.assertEqual(q2.display_style, 'scale_strip')

    def test_settings_form_saves_default_rating_style(self):
        """
        GIVEN the survey settings form
        WHEN it is saved with default_rating_display_style list_pips
        THEN the survey's style_settings holds the value
        """
        form = SurveyHeaderForm(
            data={
                'name': 'rating_editor_survey',
                'redirect_url': '#',
                'visibility': 'private',
                'available_languages': '[]',
                'thanks_html': '{}',
                'basemaps': '["streets"]',
                'default_basemap': 'streets',
                'default_rating_display_style': 'list_pips',
            },
            instance=self.survey,
        )
        self.assertTrue(form.is_valid(), form.errors)
        survey = form.save()

        self.assertEqual(
            survey.style_settings.get('rating_display_style'), 'list_pips'
        )
        self.assertEqual(survey.get_default_rating_display_style(), 'list_pips')

    def test_preview_frame_uses_new_renderers_and_override(self):
        """
        GIVEN a rating question and the modal preview endpoint
        WHEN the preview is fetched with and without a display_style override
        THEN it renders the resolved style, and the override wins without saving
        """
        q = Question.objects.create(
            survey_section=self.section, name='Conf', input_type='rating',
            choices=[{"code": 1, "name": "low"}, {"code": 2, "name": "high"}],
            display_style='scale_strip', order_number=1,
        )
        base_url = f'/editor/surveys/{self.survey.uuid}/questions/{q.id}/preview/'

        response = self.client.get(base_url)
        self.assertContains(response, 'rating-scale-strip__cells')

        response = self.client.get(base_url + '?display_style=list_pips')
        self.assertContains(response, 'class="rating-list-pips"')
        self.assertNotContains(response, 'rating-scale-strip__cells')
        q.refresh_from_db()
        self.assertEqual(q.display_style, 'scale_strip')

    def test_modal_contains_display_style_picker(self):
        """
        GIVEN the new-question modal
        WHEN it is fetched
        THEN it contains the Display-as picker block with both style options
        """
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/',
        )

        self.assertContains(response, 'display-style-fields')
        self.assertContains(response, 'Display as')
        self.assertContains(response, 'scale_strip')
        self.assertContains(response, 'list_pips')
