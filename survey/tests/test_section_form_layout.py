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


# ─── Section layout controls (change section-layout-controls, #473) ──────────

import base64
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

# A 1x1 PNG: enough for ImageField validation.
PNG_BYTES = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='
)


def _png(name='stage.png'):
    return SimpleUploadedFile(name, PNG_BYTES, content_type='image/png')


class SectionLayoutControlsRenderingTest(TestCase):
    """Respondent rendering of stage, panel side and panel width."""

    def setUp(self):
        self.org = Organization.objects.create(name="Layout Org")
        self.survey = SurveyHeader.objects.create(
            name="layout_survey", organization=self.org, redirect_url="#", status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="welcome", title="Welcome", code="W1",
            is_head=True, layout='image', panel_side='right', panel_width='half', next_label='Start',
        )

    def _get(self):
        return self.client.get('/surveys/layout_survey/welcome/')

    def test_image_section_carries_its_classes_in_the_first_html(self):
        """
        GIVEN an image section with the panel on the right at half width
        WHEN a respondent loads it directly
        THEN the body carries the stage, side and width classes and #section-data declares all three
        """
        response = self._get()

        self.assertContains(response, '<body class="survey-image-layout panel-right panel-w-half"')
        self.assertContains(response, 'data-layout="image"')
        self.assertContains(response, 'data-panel-side="right"')
        self.assertContains(response, 'data-panel-width="half"')
        self.assertContains(response, 'Start')

    def test_section_picture_wins_over_the_cover(self):
        """
        GIVEN an image section with its own picture in a survey with a cover
        WHEN the section is rendered
        THEN the stage shows the section's picture, not the cover
        """
        self.section.stage_image.name = 'sections/own.png'
        self.section.save()
        self.survey.cover_image.name = 'covers/cover.png'
        self.survey.save()

        response = self._get()

        self.assertContains(response, 'sections/own.png')
        self.assertNotContains(response, 'covers/cover.png')

    def test_cover_is_the_fallback(self):
        """
        GIVEN an image section without a picture in a survey with a cover
        WHEN the section is rendered
        THEN the stage shows the survey cover
        """
        self.survey.cover_image.name = 'covers/cover.png'
        self.survey.save()

        response = self._get()

        self.assertContains(response, 'id="stage-image" aria-hidden="true" style="background-image:')
        self.assertContains(response, 'covers/cover.png')

    def test_no_picture_renders_a_plain_stage(self):
        """
        GIVEN an image section without a picture in a survey without a cover
        WHEN the section is rendered
        THEN the stage has no background image and the page has no empty image source
        """
        response = self._get()

        self.assertContains(response, '<div id="stage-image" aria-hidden="true"></div>')
        self.assertContains(response, 'data-stage-image=""')
        self.assertNotContains(response, 'src=""')

    def test_form_section_ignores_side_and_width(self):
        """
        GIVEN a form section whose side and width are right / half
        WHEN it is rendered
        THEN the body carries only the form-layout class
        """
        self.section.layout = 'form'
        self.section.save()

        response = self._get()

        self.assertContains(response, '<body class="survey-form-layout"')

    def test_default_map_section_sets_no_class(self):
        """
        GIVEN a map section with the default side and width
        WHEN it is rendered
        THEN the body has no layout class at all, as before the change
        """
        self.section.layout, self.section.panel_side, self.section.panel_width = 'map', 'left', 'default'
        self.section.save()

        response = self._get()

        self.assertContains(response, '<body data-icon-sprites=')

    def test_unknown_width_renders_as_default(self):
        """
        GIVEN a map section whose stored panel_width is not a preset
        WHEN it is rendered
        THEN no width class is set
        """
        SurveySection.objects.filter(pk=self.section.pk).update(layout='map', panel_width='wide')

        response = self._get()

        self.assertContains(response, '<body class="panel-right"')


class SectionLayoutControlsEditorTest(TestCase):
    """Editor: geo exclusion for image sections, live edits, the picture upload."""

    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        self.org = Organization.objects.create(name="LayoutEditorOrg")
        self.user = User.objects.create_user(username='layout_editor', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='layout_editor', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='layout_editor_survey', organization=self.org, redirect_url='#',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section 1', code='S1', is_head=True,
        )
        self.url = f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/'

    def _post(self, **extra):
        data = {'title': 'Section 1', 'subheading': '', 'code': 'S1', 'layout': 'map',
                'panel_side': 'left', 'panel_width': 'default', 'next_label': ''}
        data.update(extra)
        with override_settings(MEDIA_ROOT=self.media):
            return self.client.post(self.url, data, HTTP_HX_REQUEST='true')

    def test_layout_switch_to_image_refused_while_geo_questions_exist(self):
        """
        GIVEN a map section containing a polygon question
        WHEN the section form is submitted with layout 'image'
        THEN validation fails naming the question
        """
        Question.objects.create(survey_section=self.section, code='LE1', name='Draw the park',
                                input_type='polygon', order_number=1)
        from survey.editor_forms import SurveySectionForm
        form = SurveySectionForm({'title': 'S', 'code': 'S1', 'layout': 'image'}, instance=self.section)

        self.assertFalse(form.is_valid())
        self.assertIn('Draw the park', str(form.errors['layout']))

    def test_type_picker_lacks_geo_in_image_section(self):
        """
        GIVEN a question form bound to an image section
        WHEN its input_type choices are inspected
        THEN no geo type is offered
        """
        self.section.layout = 'image'
        self.section.save()
        from survey.editor_forms import QuestionForm

        values = {v for v, _ in QuestionForm(section=self.section).fields['input_type'].choices}

        self.assertFalse({'point', 'line', 'polygon', 'spraycan'} & values)
        self.assertIn('choice', values)

    def test_modal_saves_side_width_and_picture(self):
        """
        GIVEN a draft survey's section
        WHEN the section modal posts image / right / third with a picture
        THEN the section stores all four
        """
        response = self._post(layout='image', panel_side='right', panel_width='third', stage_image=_png())

        self.assertEqual(response.status_code, 204, response.content[:400])
        self.section.refresh_from_db()
        self.assertEqual((self.section.layout, self.section.panel_side, self.section.panel_width),
                         ('image', 'right', 'third'))
        self.assertTrue(self.section.stage_image.name.startswith('sections/'))

    def test_post_without_layout_controls_keeps_them(self):
        """
        GIVEN a section stored as right / half
        WHEN an older modal posts without the two fields
        THEN the stored values are kept
        """
        SurveySection.objects.filter(pk=self.section.pk).update(panel_side='right', panel_width='half')
        data = {'title': 'Renamed', 'subheading': '', 'code': 'S1', 'layout': 'map', 'next_label': ''}

        self.client.post(self.url, data, HTTP_HX_REQUEST='true')

        self.section.refresh_from_db()
        self.assertEqual((self.section.title, self.section.panel_side, self.section.panel_width),
                         ('Renamed', 'right', 'half'))

    def test_live_survey_takes_layout_in_place(self):
        """
        GIVEN a published survey
        WHEN its section's side and width change in the modal
        THEN the save succeeds in place, without unpublished changes
        """
        self.survey.status = 'published'
        self.survey.save()

        response = self._post(panel_side='right', panel_width='half')

        self.assertEqual(response.status_code, 204, response.content[:400])
        self.section.refresh_from_db()
        self.assertEqual((self.section.panel_side, self.section.panel_width), ('right', 'half'))
        self.assertFalse(SurveyHeader.objects.filter(canonical_survey=self.survey, is_canonical=False).exists())

    def test_modal_renders_the_layout_block(self):
        """
        GIVEN a section
        WHEN the section modal is opened
        THEN it is a multipart form with the Layout block and the four controls
        """
        response = self.client.get(self.url)

        self.assertContains(response, 'hx-encoding="multipart/form-data"')
        self.assertContains(response, 'class="section-layout-block"')
        for name in ('layout', 'panel_side', 'panel_width', 'stage_image'):
            self.assertContains(response, f'data-layout-control="{name}"')


class SectionLayoutControlsTravelTest(TestCase):
    """Draft copy, duplicate and ZIP carry the controls and the picture."""

    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        settings_cm = override_settings(MEDIA_ROOT=self.media)
        settings_cm.enable()
        self.addCleanup(settings_cm.disable)
        self.org = Organization.objects.create(name="LayoutTravelOrg")
        self.survey = SurveyHeader.objects.create(
            name='layout_travel', organization=self.org, redirect_url='#',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='welcome', title='Welcome', code='W1', is_head=True,
            layout='image', panel_side='right', panel_width='half',
        )
        self.section.stage_image.save('stage.png', _png(), save=True)

    def test_draft_copy_keeps_layout_and_shares_picture(self):
        """
        GIVEN a published survey whose head section is image / right / half with a picture
        WHEN unpublished changes are started
        THEN the draft's section carries the same values and shares the picture file
        """
        from survey.versioning import clone_survey_for_draft
        self.survey.status = 'published'
        self.survey.save()

        draft = clone_survey_for_draft(self.survey)

        copy = SurveySection.objects.get(survey_header=draft)
        self.assertEqual((copy.layout, copy.panel_side, copy.panel_width), ('image', 'right', 'half'))
        self.assertEqual(copy.stage_image.name, self.section.stage_image.name)

    def test_duplicate_owns_a_new_picture_file(self):
        """
        GIVEN the same survey
        WHEN it is duplicated into a new survey
        THEN the copy's section has the values and its own copy of the picture
        """
        from survey.cloning import clone_survey

        copy_survey = clone_survey(self.survey, created_by=None)

        copy = SurveySection.objects.get(survey_header=copy_survey)
        self.assertEqual((copy.layout, copy.panel_side, copy.panel_width), ('image', 'right', 'half'))
        self.assertTrue(copy.stage_image)
        self.assertNotEqual(copy.stage_image.name, self.section.stage_image.name)

    def _roundtrip(self, mutate=None, drop_files=False):
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")
        output.seek(0)
        buf = BytesIO()
        with zipfile.ZipFile(output, 'r') as src, zipfile.ZipFile(buf, 'w') as dst:
            survey_json = json.loads(src.read("survey.json"))
            survey_json["survey"]["name"] = "layout_travel_imported"
            if mutate:
                mutate(survey_json["survey"]["sections"][0])
            dst.writestr("survey.json", json.dumps(survey_json))
            for name in src.namelist():
                if name != "survey.json" and not drop_files:
                    dst.writestr(name, src.read(name))
        buf.seek(0)
        imported, warnings = import_survey_from_zip(buf)
        return SurveySection.objects.get(survey_header=imported), warnings

    def test_zip_round_trip(self):
        """
        GIVEN the image / right / half section with a picture
        WHEN the survey is exported and imported
        THEN the imported section carries the three values and the same picture bytes
        """
        imported, _ = self._roundtrip()

        self.assertEqual((imported.layout, imported.panel_side, imported.panel_width), ('image', 'right', 'half'))
        with imported.stage_image.open('rb') as fh:
            self.assertEqual(fh.read(), PNG_BYTES)

    def test_legacy_archive_imports_defaults(self):
        """
        GIVEN an archive without the new keys
        WHEN it is imported
        THEN the section gets left / default and no picture
        """
        def mutate(section):
            for key in ('panel_side', 'panel_width', 'stage_image'):
                section.pop(key, None)

        imported, _ = self._roundtrip(mutate)

        self.assertEqual((imported.panel_side, imported.panel_width), ('left', 'default'))
        self.assertFalse(imported.stage_image)

    def test_unknown_values_import_as_defaults(self):
        """
        GIVEN an archive with a foreign panel_width and layout
        WHEN it is imported
        THEN those fields fall back to their defaults
        """
        def mutate(section):
            section['panel_width'] = 'wide'
            section['layout'] = 'carousel'

        imported, _ = self._roundtrip(mutate)

        self.assertEqual((imported.layout, imported.panel_width), ('map', 'default'))

    def test_missing_picture_is_a_warning(self):
        """
        GIVEN an archive naming a section picture that is not in it
        WHEN it is imported
        THEN the import succeeds with a warning and no picture
        """
        imported, warnings = self._roundtrip(drop_files=True)

        self.assertFalse(imported.stage_image)
        self.assertTrue(any('Picture for section' in w for w in warnings), warnings)


# ─── Content alignment inside the panel (change panel-content-align, #476) ───

class PanelContentAlignTest(TestCase):
    """Rendering, editor and travel of content_width / content_valign."""

    def setUp(self):
        self.org = Organization.objects.create(name="Align Org")
        self.user = User.objects.create_user(username='align_editor', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="align_survey", organization=self.org, redirect_url="#", status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="mapping", title="Mapping", code="A1", is_head=True,
            panel_side='right', panel_width='half', content_width='column', content_valign='middle',
        )

    def _get(self):
        return self.client.get('/surveys/align_survey/mapping/')

    def test_both_settings_add_their_classes(self):
        """
        GIVEN a map section, panel right / half, content column / middle
        WHEN a respondent loads it directly
        THEN the body carries all four classes and #section-data declares the content settings
        """
        response = self._get()

        self.assertContains(response, '<body class="panel-right panel-w-half content-column content-middle"')
        self.assertContains(response, 'data-content-width="column"')
        self.assertContains(response, 'data-content-valign="middle"')

    def test_column_alone(self):
        """
        GIVEN a section with a centred column at the top
        WHEN it is rendered
        THEN only the column class is added
        """
        SurveySection.objects.filter(pk=self.section.pk).update(panel_side='left', panel_width='default',
                                                                 content_valign='top')

        self.assertContains(self._get(), '<body class="content-column"')

    def test_defaults_add_nothing(self):
        """
        GIVEN a map section with every layout setting at its default
        WHEN it is rendered
        THEN the body has no class, as before these settings existed
        """
        SurveySection.objects.filter(pk=self.section.pk).update(
            panel_side='left', panel_width='default', content_width='full', content_valign='top')

        self.assertContains(self._get(), '<body data-icon-sprites=')

    def test_form_section_and_unknown_values_ignore_them(self):
        """
        GIVEN a form section with column / middle, and a map section with unknown stored values
        WHEN each is rendered
        THEN neither carries a content class
        """
        SurveySection.objects.filter(pk=self.section.pk).update(layout='form')
        self.assertContains(self._get(), '<body class="survey-form-layout"')

        SurveySection.objects.filter(pk=self.section.pk).update(
            layout='map', panel_side='left', panel_width='default', content_width='wide', content_valign='bottom')
        self.assertContains(self._get(), '<body data-icon-sprites=')

    def test_editor_saves_and_keeps_them(self):
        """
        GIVEN a section with column / middle
        WHEN the modal posts full / top, and then an older modal posts without the two fields
        THEN the first post stores them, the second keeps what is stored
        """
        self.client.login(username='align_editor', password='pass')
        url = f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/'
        base = {'title': 'Mapping', 'subheading': '', 'code': 'A1', 'layout': 'map', 'next_label': ''}

        response = self.client.post(url, {**base, 'content_width': 'full', 'content_valign': 'top'},
                                    HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 204, response.content[:300])
        self.section.refresh_from_db()
        self.assertEqual((self.section.content_width, self.section.content_valign), ('full', 'top'))

        SurveySection.objects.filter(pk=self.section.pk).update(content_width='column', content_valign='middle')
        self.client.post(url, base, HTTP_HX_REQUEST='true')
        self.section.refresh_from_db()
        self.assertEqual((self.section.content_width, self.section.content_valign), ('column', 'middle'))
        self.assertFalse(SurveyHeader.objects.filter(canonical_survey=self.survey, is_canonical=False).exists())

    def test_draft_copy_and_zip_carry_them(self):
        """
        GIVEN the column / middle section
        WHEN unpublished changes are started, and the survey is exported and imported
        THEN both copies carry the two values; a legacy or foreign archive gets the defaults
        """
        from survey.versioning import clone_survey_for_draft
        draft = clone_survey_for_draft(self.survey)
        copy = SurveySection.objects.get(survey_header=draft)
        self.assertEqual((copy.content_width, copy.content_valign), ('column', 'middle'))

        def roundtrip(name, mutate=None):
            output = BytesIO()
            export_survey_to_zip(self.survey, output, mode="structure")
            output.seek(0)
            with zipfile.ZipFile(output) as zf:
                data = json.loads(zf.read("survey.json"))
            data["survey"]["name"] = name
            if mutate:
                mutate(data["survey"]["sections"][0])
            buf = BytesIO()
            with zipfile.ZipFile(buf, 'w') as zf:
                zf.writestr("survey.json", json.dumps(data))
            buf.seek(0)
            imported, _ = import_survey_from_zip(buf)
            return SurveySection.objects.get(survey_header=imported)

        imported = roundtrip("align_imported")
        self.assertEqual((imported.content_width, imported.content_valign), ('column', 'middle'))

        def legacy(section):
            section.pop("content_width")
            section["content_valign"] = "bottom"
        imported = roundtrip("align_legacy", legacy)
        self.assertEqual((imported.content_width, imported.content_valign), ('full', 'top'))
