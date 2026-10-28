"""Tests for the `section-form-layout` capability (openspec/specs/section-form-layout/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from io import BytesIO
import json
import zipfile
from survey.models import Organization, SurveyHeader, SurveySection, Question, Membership
from survey.serialization import export_survey_to_zip, import_survey_from_zip
from survey.models import SurveySectionTranslation


class MaplessSectionRenderingTest(TestCase):
    """Respondent rendering of form-layout sections."""

    def setUp(self):
        self.client = Client()
        self.org = Organization.objects.create(name="Mapless Org")
        self.survey = SurveyHeader.objects.create(
            name="mapless_survey",
            organization=self.org,
            redirect_url="/thanks/",
            status='published',
        )
        self.welcome = SurveySection.objects.create(
            survey_header=self.survey, name="welcome", title="Welcome",
            code="W1", is_head=True, layout='form',
        )
        self.map_section = SurveySection.objects.create(
            survey_header=self.survey, name="mapping", title="Mapping",
            code="M1", layout='map',
        )
        self.welcome.next_section = self.map_section
        self.welcome.save()
        self.map_section.prev_section = self.welcome
        self.map_section.save()
        Question.objects.create(
            survey_section=self.welcome, code="MLQ001", name="Your district",
            input_type="choice", choices=[{"code": 1, "name": "North"}],
            order_number=1,
        )
        Question.objects.create(
            survey_section=self.map_section, code="MLQ002", name="Mark a spot",
            input_type="point", order_number=1,
        )

    def test_form_section_renders_with_form_layout_mode(self):
        """
        GIVEN a section with layout 'form'
        WHEN a respondent loads it directly
        THEN the initial HTML already carries the form-layout body class and the
             section data element declares data-layout "form"
        """
        response = self.client.get('/surveys/mapless_survey/welcome/')

        self.assertContains(response, 'class="survey-form-layout"')
        self.assertContains(response, 'data-layout="form"')

    def test_default_forward_label_is_next(self):
        """
        GIVEN a section without a custom button label
        WHEN it is rendered
        THEN the forward button keeps the default Next label
        """
        response = self.client.get('/surveys/mapless_survey/welcome/')

        self.assertContains(response, 'value="Next"')

    def test_creator_label_overrides_next(self):
        """
        GIVEN a section whose creator set the button label to Start
        WHEN it is rendered
        THEN the forward button reads Start instead of Next
        """
        self.welcome.next_label = 'Start'
        self.welcome.save()

        response = self.client.get('/surveys/mapless_survey/welcome/')

        self.assertContains(response, 'value="Start"')
        self.assertNotContains(response, 'value="Next"')

    def test_creator_label_is_translated(self):
        """
        GIVEN a custom button label with a German translation
        WHEN the section renders in German
        THEN the translated label is used
        """
        self.welcome.next_label = 'Start'
        self.welcome.save()
        SurveySectionTranslation.objects.create(
            section=self.welcome, language='de', next_label='Los geht’s',
        )
        self.survey.available_languages = ['en', 'de']
        self.survey.save()

        session = self.client.session
        session['survey_language'] = 'de'
        session.save()
        response = self.client.get('/surveys/mapless_survey/welcome/')

        self.assertContains(response, 'Los geht’s')

    def test_accent_color_styles_survey_page(self):
        """
        GIVEN a survey with a validated accent color in style_settings
        WHEN a section is rendered
        THEN the accent is interpolated into the page's style block
        """
        self.survey.style_settings = {'accent_color': '#7a1f2b'}
        self.survey.save()

        response = self.client.get('/surveys/mapless_survey/welcome/')

        self.assertContains(response, 'background-color: #7a1f2b')

    def test_invalid_accent_color_is_ignored(self):
        """
        GIVEN style_settings carrying a non-hex accent (e.g. from a crafted ZIP)
        WHEN a section is rendered
        THEN no accent style block is emitted
        """
        self.survey.style_settings = {'accent_color': 'red;} body{display:none'}
        self.survey.save()

        response = self.client.get('/surveys/mapless_survey/welcome/')

        self.assertNotContains(response, 'body{display:none')
        self.assertNotContains(response, 'background-color: red')

    def test_map_section_is_unchanged(self):
        """
        GIVEN a section with layout 'map'
        WHEN a respondent loads it directly
        THEN no form-layout mode is present and the submit label is the normal one
        """
        response = self.client.get('/surveys/mapless_survey/mapping/')

        self.assertNotContains(response, 'class="survey-form-layout"')
        self.assertContains(response, 'data-layout="map"')


class MaplessSectionSerializationTest(TestCase):
    """Section layout in export/import."""

    def setUp(self):
        self.org = Organization.objects.create(name="MaplessSer Org")
        self.survey = SurveyHeader.objects.create(
            name="mapless_ser_survey", organization=self.org, redirect_url="/thanks/",
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1",
            is_head=True, layout='form',
        )
        Question.objects.create(
            survey_section=self.section, code="MLS001", name="Q",
            input_type="text", order_number=1,
        )

    def _roundtrip(self, mutate=None):
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")
        output.seek(0)
        with zipfile.ZipFile(output, 'r') as zf:
            survey_json = json.loads(zf.read("survey.json"))

        survey_json["survey"]["name"] = "mapless_ser_imported"
        if mutate:
            mutate(survey_json["survey"]["sections"][0])

        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_json))
        buf.seek(0)
        imported, _ = import_survey_from_zip(buf)
        return SurveySection.objects.get(survey_header=imported)

    def test_layout_round_trips(self):
        """
        GIVEN a section with layout 'form'
        WHEN the survey is exported and re-imported
        THEN the imported section keeps layout 'form'
        """
        imported = self._roundtrip()

        self.assertEqual(imported.layout, 'form')

    def test_legacy_archive_defaults_to_map(self):
        """
        GIVEN a survey.json without the layout key (pre-change archive)
        WHEN the archive is imported
        THEN the imported section gets layout 'map'
        """
        def mutate(section):
            section.pop("layout", None)

        imported = self._roundtrip(mutate)

        self.assertEqual(imported.layout, 'map')


class MaplessSectionEditorTest(TestCase):
    """Editor gating: geo questions and form layout exclude each other."""

    def setUp(self):
        self.org = Organization.objects.create(name="MaplessEditorOrg")
        self.user = User.objects.create_user(username='mapless_editor', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='mapless_editor', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='mapless_editor_survey', visibility='private', organization=self.org,
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section 1', code='S1',
            is_head=True,
        )

    def test_layout_switch_refused_while_geo_questions_exist(self):
        """
        GIVEN a map section containing a point question
        WHEN the section form is submitted with layout 'form'
        THEN validation fails naming the question and the section stays 'map'
        """
        Question.objects.create(
            survey_section=self.section, code="MLE001", name="Mark home",
            input_type="point", order_number=1,
        )
        from survey.editor_forms import SurveySectionForm
        form = SurveySectionForm(
            {'title': 'Section 1', 'subheading': '', 'code': 'S1', 'layout': 'form'},
            instance=self.section,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('Mark home', str(form.errors['layout']))
        self.section.refresh_from_db()
        self.assertEqual(self.section.layout, 'map')

    def test_layout_switch_succeeds_without_geo_questions(self):
        """
        GIVEN a map section with only non-geo questions
        WHEN the section form is submitted with layout 'form'
        THEN the section persists layout 'form'
        """
        from survey.editor_forms import SurveySectionForm
        form = SurveySectionForm(
            {'title': 'Section 1', 'subheading': '', 'code': 'S1', 'layout': 'form'},
            instance=self.section,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.section.refresh_from_db()
        self.assertEqual(self.section.layout, 'form')

    def test_geo_question_rejected_in_form_section(self):
        """
        GIVEN a section with layout 'form'
        WHEN a point question is posted to the create endpoint
        THEN the save is refused and no question is created
        """
        self.section.layout = 'form'
        self.section.save()

        self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/',
            {'name': 'Mark a spot', 'input_type': 'point', 'color': '#000000'},
        )

        self.assertFalse(
            Question.objects.filter(survey_section=self.section, name='Mark a spot').exists()
        )

    def test_type_picker_choices_lack_geo_in_form_section(self):
        """
        GIVEN a question form bound to a form-layout section
        WHEN its input_type choices are inspected
        THEN no geo type is offered (which also removes the picker's geo group)
        """
        self.section.layout = 'form'
        self.section.save()
        from survey.editor_forms import QuestionForm
        form = QuestionForm(section=self.section)

        values = {v for v, _ in form.fields['input_type'].choices}

        self.assertFalse({'point', 'line', 'polygon'} & values)
        self.assertIn('choice', values)


class SectionNextLabelSerializationTest(TestCase):
    """next_label in export/import."""

    def setUp(self):
        self.org = Organization.objects.create(name="NextLabelSer Org")
        self.survey = SurveyHeader.objects.create(
            name="nextlabel_ser_survey", organization=self.org, redirect_url="/thanks/",
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1",
            is_head=True, next_label='Start',
        )
        SurveySectionTranslation.objects.create(
            section=self.section, language='de', next_label='Los',
        )
        Question.objects.create(
            survey_section=self.section, code="NLS001", name="Q",
            input_type="text", order_number=1,
        )

    def test_next_label_round_trips_with_translation(self):
        """
        GIVEN a section with a custom button label and its translation
        WHEN the survey is exported and re-imported
        THEN both the base label and the translated label survive
        """
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")
        output.seek(0)
        with zipfile.ZipFile(output, 'r') as zf:
            survey_json = json.loads(zf.read("survey.json"))
        survey_json["survey"]["name"] = "nextlabel_imported"
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_json))
        buf.seek(0)

        imported, _ = import_survey_from_zip(buf)

        section = SurveySection.objects.get(survey_header=imported)
        self.assertEqual(section.next_label, 'Start')
        self.assertEqual(section.translations.get(language='de').next_label, 'Los')
