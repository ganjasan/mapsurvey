"""Tests for the `layer-objects-question` capability (openspec/specs/layer-objects-question/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.urls import reverse
from io import BytesIO
from survey.models import Organization, SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
from survey.serialization import export_survey_to_zip, import_survey_from_zip
from survey.versioning import clone_survey_for_draft
from survey.cloning import clone_question
from survey.tests.helpers import _objects_layer, _shared_map_survey, _validated_geojson_text, _zones_geojson


class LayersByQuestionMigrationTest(TestCase):
    """The hidden_layers → Objects-question conversion (migration 0074 and the
    live `ensure_layer_questions` copy the ZIP import uses)."""

    def setUp(self):
        from survey.models import SurveyMapLayer
        from survey.layers import validate_layer_upload
        self.org = Organization.objects.create(name="LBQ Org")
        self.survey = SurveyHeader.objects.create(
            name="lbq_survey", organization=self.org, redirect_url="/thanks/", status='published',
        )
        self.map_section = SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="Map", code="S1", is_head=True, layout='map',
        )
        self.form_section = SurveySection.objects.create(
            survey_header=self.survey, name="s2", title="Form", code="S2", layout='form',
        )
        geojson, count, _ = _validated_geojson_text(_zones_geojson().encode())
        self.a = SurveyMapLayer.objects.create(
            survey=self.survey, name="A", color="#111111", geojson=geojson, feature_count=count,
            size_bytes=len(geojson), position=0,
        )
        self.b = SurveyMapLayer.objects.create(
            survey=self.survey, name="B", color="#222222", geojson=geojson, feature_count=count,
            size_bytes=len(geojson), position=1,
        )

    def test_default_question_names_and_the_follow_up_migration(self):
        """
        GIVEN an uploaded layer "existing-dog-bins" and a marks layer, Objects questions still
              carrying the raw layer names (as migration 0074 wrote them), one renamed by the
              creator, and the marks layer never materialised although its source has answers
        WHEN the 0077 follow-up runs
        THEN the untouched questions read "Existing dog bins" / "Other respondents' marks", the
             renamed one is left alone, the marks layer holds an object per answer, and a fresh
             conversion names new questions the same way
        """
        import importlib
        from survey.layers import default_question_name, ensure_layer_questions
        from survey.models import SurveyMapLayer
        self.assertEqual(default_question_name(self.a), 'A')
        self.a.name = 'existing-dog-bins'
        self.a.save()
        self.assertEqual(default_question_name(self.a), 'Existing dog bins')
        q1 = Question.objects.create(survey_section=self.map_section, code="LBQ_Q1", name="Where?", input_type="point", order_number=1)
        marks = SurveyMapLayer.objects.create(survey=self.survey, name="Marks: Where?", source='question', source_question_code='LBQ_Q1',
                                              geojson='{"type":"FeatureCollection","features":[]}')
        self.assertEqual(default_question_name(marks), "Other respondents' marks")
        raw_a = Question.objects.create(survey_section=self.map_section, code="LBQ_A", name="existing-dog-bins", input_type="layer_objects", layer=self.a, order_number=2)
        raw_m = Question.objects.create(survey_section=self.map_section, code="LBQ_M", name="Marks: Where?", input_type="layer_objects", layer=marks, order_number=3)
        renamed = Question.objects.create(survey_section=self.map_section, code="LBQ_B", name="Bins nearby", input_type="layer_objects", layer=self.b, order_number=4)
        sess = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=sess, question=q1, point=Point(13.4, 52.5))
        mig = importlib.import_module('survey.migrations.0077_backfill_marks_and_legend_names')
        mig.forwards(None, None)
        for q in (raw_a, raw_m, renamed):
            q.refresh_from_db()
        self.assertEqual((raw_a.name, raw_m.name, renamed.name), ('Existing dog bins', "Other respondents' marks", 'Bins nearby'))
        self.assertEqual(marks.items.count(), 1)
        created = ensure_layer_questions(self.form_section, [])
        self.assertEqual(created, [])
        section3 = SurveySection.objects.create(survey_header=self.survey, name="s3", title="Map 2", code="S3", layout='map')
        names = sorted(q.name for q in ensure_layer_questions(section3, []))
        self.assertEqual(names, ['B', 'Existing dog bins', "Other respondents' marks"])

    def test_conversion_creates_legend_questions_for_visible_unbound_layers(self):
        """
        GIVEN a map section that hid layer B and already binds nothing, and a form section
        WHEN the conversion runs
        THEN the map section gets one legend-mode Objects question for A only, the form section
             gets none, and a second run creates nothing more (idempotent)
        """
        from survey.layers import ensure_layer_questions, section_layer_ids
        created = ensure_layer_questions(self.map_section, [self.b.pk])
        self.assertEqual([(q.layer_id, q.panel_mode, q.min_objects, q.name) for q in created],
                         [(self.a.pk, 'legend', 0, 'A')])
        self.assertEqual(ensure_layer_questions(self.form_section, []), [])
        self.assertEqual(ensure_layer_questions(self.map_section, [self.b.pk]), [])
        self.assertEqual(section_layer_ids(self.map_section), [self.a.pk])

    def test_conversion_skips_layers_a_question_already_binds(self):
        """
        GIVEN a map section whose Objects question already binds layer A
        WHEN the conversion runs with nothing hidden
        THEN only B gets a new question, appended after the existing one
        """
        from survey.layers import ensure_layer_questions, section_layer_ids
        existing = Question.objects.create(
            survey_section=self.map_section, code="LBQ1", name="Ask about A", input_type="layer_objects",
            layer=self.a, order_number=3,
        )
        created = ensure_layer_questions(self.map_section, [])
        self.assertEqual([(q.layer_id, q.order_number) for q in created], [(self.b.pk, 4)])
        self.assertEqual(section_layer_ids(self.map_section), [self.a.pk, self.b.pk])
        self.assertEqual(Question.objects.get(pk=existing.pk).panel_mode, 'list')

    def test_draft_copy_sections_convert_against_the_canonical_layers(self):
        """
        GIVEN a draft copy of the survey (which borrows the canonical's layers)
        WHEN its map section is converted
        THEN it gets Objects questions bound to the canonical's layers
        """
        from survey.layers import ensure_layer_questions
        draft = clone_survey_for_draft(self.survey)
        section = SurveySection.objects.get(survey_header=draft, name='s1')
        created = ensure_layer_questions(section, [])
        self.assertEqual(sorted(q.layer_id for q in created), sorted([self.a.pk, self.b.pk]))


class ShareFlagSeedingTest(TestCase):
    """Legacy layer flags → sub-question sharing (migration 0076 and the ZIP import seed)."""

    def test_seed_from_layer_flags(self):
        """
        GIVEN a marks layer with show_tallies on and show_comments off, bound by an Objects
              question with a 👍/👎 and a text sub-question
        WHEN the seed runs
        THEN the 👍/👎 sub-question shares and the text one does not
        """
        from survey.serialization import seed_share_flags_from_layers
        f = _shared_map_survey("seed_survey")
        f['layer'].show_tallies = True
        f['layer'].show_comments = False
        f['layer'].save()
        seed_share_flags_from_layers(f['survey'])
        f['vote'].refresh_from_db(); f['cmt'].refresh_from_db()
        self.assertTrue(f['vote'].share_with_respondents)
        self.assertFalse(f['cmt'].share_with_respondents)


class LayerObjectsQuestionEditorTest(TestCase):
    """The `layer_objects` type in the editor: picker, form, sub-questions (specs
    survey-editor, question-type-picker)."""

    def setUp(self):
        self.org = Organization.objects.create(name="LOQ Org")
        self.owner = User.objects.create_user(username='loqowner', password='pw12345678')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="loq_survey", organization=self.org, redirect_url="/thanks/", created_by=self.owner,
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True,
        )
        self.form_section = SurveySection.objects.create(
            survey_header=self.survey, name="s2", title="S2", code="S2", layout='form',
        )
        self.layer = _objects_layer(self.survey, name="Sites", key_field='zone_id', label_field='name')
        self.client.login(username='loqowner', password='pw12345678')

    def _create_url(self, section=None):
        return reverse('editor_question_create', kwargs={'survey_uuid': self.survey.uuid, 'section_id': (section or self.section).pk})

    def _post(self, data, section=None):
        base = {'subtext': '', 'display_style': 'default', 'color': '#000000'}
        base.update(data)
        return self.client.post(self._create_url(section), base)

    def test_picker_offers_objects_on_the_map_with_a_layer(self):
        """
        GIVEN a survey with a reference layer and a map-layout section
        WHEN the new-question modal is opened
        THEN the picker lists "Objects on the map" in the Map questions group
        """
        html = self.client.get(self._create_url()).content.decode()
        self.assertIn('data-qtp-value="layer_objects"', html)
        self.assertIn('Objects on the map', html)

    def test_picker_hides_the_type_without_layers_and_on_form_sections(self):
        """
        GIVEN a survey with no layers, or a form-layout section
        WHEN the new-question modal is opened
        THEN the picker does not offer layer_objects
        """
        html = self.client.get(self._create_url(self.form_section)).content.decode()
        self.assertNotIn('data-qtp-value="layer_objects"', html)
        self.layer.delete()
        html = self.client.get(self._create_url()).content.decode()
        self.assertNotIn('data-qtp-value="layer_objects"', html)

    def test_form_section_shows_map_types_disabled_with_reason(self):
        """
        GIVEN a form-layout section in a survey with a layer
        WHEN the new-question modal is opened there, then in a map section
        THEN the form section lists every map type as an inert tile with the reason,
             none of them pickable; the map section shows them pickable and no reason
        """
        html = self.client.get(self._create_url(self.form_section)).content.decode()
        for value in ('point', 'line', 'polygon', 'spraycan', 'layer_objects'):
            self.assertIn(f'data-qtp-unavailable="{value}"', html)
            self.assertNotIn(f'data-qtp-value="{value}"', html)
        self.assertIn('Switch its Layout to Map', html)
        self.assertIn('data-qtp-value="choice"', html)

        html = self.client.get(self._create_url()).content.decode()
        self.assertIn('data-qtp-value="point"', html)
        self.assertNotIn('data-qtp-unavailable', html)
        self.assertNotIn('Switch its Layout to Map', html)

    def test_create_requires_a_layer_and_ignores_required(self):
        """
        GIVEN a POST for an Objects-on-the-map question without a layer, then with one and required=on
        WHEN the create endpoint validates
        THEN the first is refused on the layer field and the second is stored with required=False and min_objects;
             the "min" badge waits for a sub-question, since without one the question collects nothing
        """
        response = self._post({'name': 'Objects', 'input_type': 'layer_objects'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('Pick the reference layer', response.content.decode())
        self.assertFalse(Question.objects.filter(name='Objects').exists())
        response = self._post({'name': 'Objects', 'input_type': 'layer_objects', 'layer': self.layer.pk,
                               'required': 'on', 'min_objects': '2', 'objects_search': 'on'})
        self.assertEqual(response.status_code, 200)
        q = Question.objects.get(name='Objects')
        self.assertEqual((q.layer_id, q.required, q.min_objects, q.objects_search), (self.layer.pk, False, 2, 'on'))
        html = response.content.decode()
        self.assertIn('Sites', html)
        self.assertNotIn('min 2', html)
        self.assertIn('Add Sub-question', html)
        self.assertFalse(q.collects_objects)

    def test_switching_type_drops_the_layer_binding(self):
        """
        GIVEN a layer_objects question
        WHEN it is edited into a text question
        THEN the layer binding is cleared so the layer stays deletable
        """
        q = Question.objects.create(survey_section=self.section, code="LO001", name="Objects",
                                    input_type="layer_objects", layer=self.layer, order_number=1)
        self.client.post(reverse('editor_question_edit', kwargs={'survey_uuid': self.survey.uuid, 'question_id': q.pk}),
                         {'name': 'Objects', 'input_type': 'text', 'subtext': '', 'display_style': 'default', 'color': '#000000'})
        q.refresh_from_db()
        self.assertEqual((q.input_type, q.layer_id), ('text', None))

    def test_subquestion_form_excludes_parent_types(self):
        """
        GIVEN the New Sub-question modal for a layer_objects question
        WHEN it renders and when a POST tries a parent type
        THEN the picker offers neither geo types nor layer_objects, and the POST is rejected
        """
        q = Question.objects.create(survey_section=self.section, code="LO002", name="Objects",
                                    input_type="layer_objects", layer=self.layer, order_number=1)
        url = reverse('editor_subquestion_create', kwargs={'survey_uuid': self.survey.uuid, 'parent_id': q.pk})
        html = self.client.get(url).content.decode()
        for value in ('point', 'line', 'polygon', 'layer_objects'):
            self.assertNotIn(f'data-qtp-value="{value}"', html)
        self.assertIn('data-qtp-value="thumbs"', html)
        self.client.post(url, {'name': 'Nested', 'input_type': 'layer_objects', 'layer': self.layer.pk,
                               'subtext': '', 'display_style': 'default', 'color': '#000000'})
        self.assertFalse(Question.objects.filter(name='Nested').exists())
        self.client.post(url, {'name': 'Rate', 'input_type': 'rating', 'subtext': '', 'display_style': 'default',
                               'color': '#000000', 'choices_json': '[]'})
        sub = Question.objects.get(name='Rate')
        self.assertEqual(sub.parent_question_id_id, q.pk)

    def test_modal_subquestions_block_and_picker_only_create(self):
        """
        GIVEN a polygon question with one sub-question, and the section's New question modal
        WHEN the edit modal and the create modal render
        THEN the edit modal carries the Sub-questions block listing the child with an in-modal add link,
             the sub-question's own modal has none, and the create modal is the same shell with the
             picker in create mode (data-create-picker) — Name, Subtext and the preview column present
        """
        poly = Question.objects.create(survey_section=self.section, code="LO003", name="Area", input_type="polygon", order_number=1)
        sub = Question.objects.create(survey_section=self.section, code="LO004", name="Why?", input_type="text",
                                      parent_question_id=poly, order_number=1)
        html = self.client.get(reverse('editor_question_edit', kwargs={'survey_uuid': self.survey.uuid, 'question_id': poly.pk})).content.decode()
        self.assertIn('id="fg-subquestions"', html)
        self.assertIn('Why?', html)
        self.assertIn(reverse('editor_subquestion_create', kwargs={'survey_uuid': self.survey.uuid, 'parent_id': poly.pk}) + '?return=modal', html)
        html = self.client.get(reverse('editor_question_edit', kwargs={'survey_uuid': self.survey.uuid, 'question_id': sub.pk})).content.decode()
        self.assertNotIn('id="fg-subquestions"', html)
        html = self.client.get(reverse('editor_question_create', kwargs={'survey_uuid': self.survey.uuid, 'section_id': self.section.pk})).content.decode()
        self.assertIn('data-create-picker', html)
        self.assertNotIn('pick a type', html)
        for marker in ('id="fg-name"', 'id="fg-subtext"', 'question-preview-panel qtp-preview-col'):
            self.assertIn(marker, html)

    def test_polygon_without_subquestions_saves(self):
        """
        GIVEN a polygon question created with no sub-questions
        WHEN it is saved
        THEN it exists — no minimum, no block (D4)
        """
        response = self._post({'name': 'Area', 'input_type': 'polygon'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Question.objects.filter(name='Area', input_type='polygon').exists())

    def test_live_preview_renders_the_block(self):
        """
        GIVEN a draft Objects-on-the-map question in the modal
        WHEN the live preview endpoint renders it with the picked layer
        THEN the block shell renders with the layer's object count and code attributes; the minimum
             is 0 because a draft with no sub-questions collects nothing
        """
        response = self.client.post(
            reverse('editor_question_preview_live', kwargs={'survey_uuid': self.survey.uuid, 'section_id': self.section.pk}),
            {'input_type': 'layer_objects', 'name': 'Objects', 'layer': self.layer.pk, 'min_objects': '1', 'objects_search': 'auto'})
        html = response.content.decode()
        self.assertIn('data-layer-objects', html)
        self.assertIn(f'data-layer-id="{self.layer.pk}"', html)
        self.assertIn('data-min-objects="0"', html)
        self.assertIn('data-collects="0"', html)

    def test_live_preview_renders_the_layers_objects_as_a_static_panel(self):
        """
        GIVEN the Sites layer with three objects, one categorised
        WHEN the live preview renders a list-mode draft bound to it
        THEN the pane shows the objects' titles as rows and the category as a chip — a picture of
             the respondent's panel, not the empty shell the map would fill (direction B)
        """
        first = self.layer.items.order_by('key').first()
        first.category = 'Parks'
        first.save()
        html = self.client.post(
            reverse('editor_question_preview_live', kwargs={'survey_uuid': self.survey.uuid, 'section_id': self.section.pk}),
            {'input_type': 'layer_objects', 'name': 'Objects', 'layer': self.layer.pk, 'panel_mode': 'list', 'objects_search': 'on'}).content.decode()
        self.assertIn('class="lo-row"', html)
        self.assertIn(first.title, html)
        self.assertIn('Parks · 1', html)
        # The respondent page itself still gets the empty shell the map fills.
        self.assertNotIn('data-lo-list', html.split('class="layer-objects__list"')[0][-60:])

    def test_clone_keeps_layer_within_the_survey_and_drops_it_elsewhere(self):
        """
        GIVEN a layer_objects question
        WHEN it is cloned into the same survey and into another survey
        THEN the same-survey clone keeps the layer and the cross-survey clone is unbound
        """
        from survey.cloning import clone_question
        q = Question.objects.create(survey_section=self.section, code="LO005", name="Objects",
                                    input_type="layer_objects", layer=self.layer, min_objects=1, order_number=1)
        same = clone_question(q, target_section=self.section)
        self.assertEqual((same.layer_id, same.min_objects), (self.layer.pk, 1))
        other = SurveyHeader.objects.create(name="other_survey", organization=self.org, redirect_url="/thanks/")
        other_section = SurveySection.objects.create(survey_header=other, name="s1", title="S1", code="S1", is_head=True)
        cross = clone_question(q, target_section=other_section)
        self.assertIsNone(cross.layer_id)

    def test_bound_layer_cannot_be_deleted(self):
        """
        GIVEN a layer bound to a layer_objects question
        WHEN the owner deletes the layer through the settings endpoint
        THEN the request is refused with a message naming the question and the layer remains
        """
        Question.objects.create(survey_section=self.section, code="LO006", name="Rate the sites",
                                input_type="layer_objects", layer=self.layer, order_number=1)
        response = self.client.post(reverse('editor_survey_layer_delete', kwargs={'survey_uuid': self.survey.uuid, 'layer_id': self.layer.pk}))
        self.assertEqual(response.status_code, 400)
        self.assertIn('Rate the sites', response.json()['error'])
        self.assertTrue(self.layer.__class__.objects.filter(pk=self.layer.pk).exists())

    def test_serialization_round_trips_the_binding(self):
        """
        GIVEN a layer_objects question bound to the survey's layer
        WHEN the survey is exported and re-imported
        THEN the imported question is bound to the imported layer by position, with its settings
        """
        Question.objects.create(survey_section=self.section, code="LO007", name="Objects",
                                input_type="layer_objects", layer=self.layer, min_objects=2, objects_search='off', order_number=1)
        buf = BytesIO()
        export_survey_to_zip(self.survey, buf, 'structure')
        buf.seek(0)
        self.survey.name = 'loq_survey_old'
        self.survey.save()
        imported, warnings = import_survey_from_zip(buf)
        q = Question.objects.get(survey_section__survey_header=imported, name='Objects')
        self.assertEqual(q.layer, imported.map_layers.get())
        self.assertEqual((q.min_objects, q.objects_search), (2, 'off'))
