"""Tests for the `map-layer-placement` capability (spec in the unarchived change
map-layers-study-area: openspec/changes/map-layers-study-area/specs/map-layer-placement/spec.md).

A reference layer shows on a section's map because a placement covers the section — never because a
question binds it. Placements belong to the canonical survey and name sections by reference.
"""
import importlib

from django.apps import apps
from django.contrib.auth.models import User
from django.test import TestCase

from survey.layers import layers_for, placements_for, section_layer_ids
from survey.models import (LayerPlacement, Organization, Question, SurveyHeader, SurveyMapLayer,
                           SurveySection)
from survey.section_refs import section_ref
from survey.services import placements as svc_placements
from survey.services.context import Actor
from survey.services.errors import ValidationFailed
from survey.tests.helpers import _objects_layer


def _migration(name):
    return importlib.import_module(f'survey.migrations.{name}')


class _Fixture(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('placement_owner', password='pw')
        self.actor = Actor(user=self.owner)
        self.org = Organization.objects.create(name='Placement Org')
        self.survey = SurveyHeader.objects.create(name='placement_survey', organization=self.org,
                                                  redirect_url='#', status='draft')
        self.s1 = SurveySection.objects.create(survey_header=self.survey, name='s1', title='Map 1', code='S1',
                                               is_head=True, layout='map')
        self.s2 = SurveySection.objects.create(survey_header=self.survey, name='s2', title='Map 2', code='S2',
                                               layout='map')
        self.form = SurveySection.objects.create(survey_header=self.survey, name='s3', title='Form', code='S3',
                                                 layout='form')
        self.s1.next_section, self.s2.next_section = self.s2, self.form
        self.s1.save()
        self.s2.save()
        self.layer = _objects_layer(self.survey, name='Study area')

    def legend(self, section, layer, order=10, code=None):
        return Question.objects.create(survey_section=section, code=code or f'LG{section.pk}{layer.pk}',
                                       name=layer.name, input_type='layer_objects', layer=layer,
                                       panel_mode='legend', order_number=order)


class LegendQuestionsBecomePlacementsTest(_Fixture):
    """Spec map-layer-placement / Requirement: Legend-only questions become placements (migration 0135)."""

    def run_migration(self):
        _migration('0135_legend_questions_to_placements').questions_to_placements(apps, None)

    def test_boundary_on_every_section_becomes_one_all_placement(self):
        """
        GIVEN a legend-only question bound to "Study area" in each of the survey's two map sections
        WHEN the migration runs, twice
        THEN the survey has one placement of the layer with scope `all`, both maps show it, and the
             second run adds nothing
        """
        self.legend(self.s1, self.layer)
        self.legend(self.s2, self.layer)
        self.run_migration()
        self.run_migration()
        placement = LayerPlacement.objects.get(survey=self.survey)
        self.assertEqual((placement.layer_id, placement.scope, placement.sections), (self.layer.pk, 'all', []))
        self.assertEqual(section_layer_ids(self.s1), [self.layer.pk])
        self.assertEqual(section_layer_ids(self.s2), [self.layer.pk])

    def test_one_of_two_sections_becomes_a_sections_placement(self):
        """
        GIVEN a legend question for the layer on section 2 only
        WHEN the migration runs
        THEN the placement names S2 and section 1's map stays without the layer
        """
        self.legend(self.s2, self.layer)
        self.run_migration()
        placement = LayerPlacement.objects.get(survey=self.survey)
        self.assertEqual((placement.scope, placement.sections), ('sections', ['S2']))
        self.assertEqual(section_layer_ids(self.s1), [])
        self.assertEqual(section_layer_ids(self.s2), [self.layer.pk])

    def test_a_question_that_asks_keeps_working(self):
        """
        GIVEN an Objects question with a sub-question bound to the layer in section 2
        WHEN the migration runs
        THEN section 2 has a placement of the layer and the question still asks about each object
        """
        asking = Question.objects.create(survey_section=self.s2, code='ASK1', name='Rate', input_type='layer_objects',
                                         layer=self.layer, order_number=1)
        Question.objects.create(survey_section=self.s2, code='ASK1R', name='Like it?', input_type='thumbs',
                                parent_question_id=asking, order_number=1)
        self.run_migration()
        self.assertEqual(section_layer_ids(self.s2), [self.layer.pk])
        self.assertTrue(Question.objects.get(pk=asking.pk).collects_objects)
        self.assertIn(asking.pk, [q.pk for q in self.s2.questions()])

    def test_draft_copy_legend_questions_count(self):
        """
        GIVEN a published survey whose unpublished changes added a legend question the live survey lacks
        WHEN the migration runs
        THEN the canonical survey gets the placement, so publishing the changes keeps the layer on the map
        """
        from survey.versioning import clone_survey_for_draft
        self.survey.status = 'published'
        self.survey.save()
        draft = clone_survey_for_draft(self.survey)
        self.legend(SurveySection.objects.get(survey_header=draft, code='S1'), self.layer)
        self.run_migration()
        self.assertEqual(LayerPlacement.objects.filter(survey=self.survey).count(), 1)
        self.assertFalse(LayerPlacement.objects.filter(survey=draft).exists())

    def test_legend_only_questions_are_hidden_everywhere(self):
        """
        GIVEN a legend-only question and a new Objects question without sub-questions yet
        WHEN the section's questions are listed
        THEN the legend-only one is left out and the new one stays (it is a question being written)
        """
        legend = self.legend(self.s1, self.layer)
        fresh = Question.objects.create(survey_section=self.s1, code='NEW1', name='Objects', input_type='layer_objects',
                                        layer=self.layer, order_number=2)
        ids = [q.pk for q in self.s1.questions()]
        self.assertNotIn(legend.pk, ids)
        self.assertIn(fresh.pk, ids)


class UploadLayersMoveToDataTest(_Fixture):
    """Spec data-links / Requirement: A dataset is linked into surveys and sites, not copied (migration 0136)."""

    def test_upload_layer_becomes_a_linked_public_dataset(self):
        """
        GIVEN a survey-owned upload layer whose Data row was made private, and a shared-map layer
        WHEN the migration runs
        THEN the upload layer has no survey, keeps its workspace, its dataset is public and linked to
             the survey, the shared-map layer stays the survey's, and `layers_for` returns both
        """
        from data.models import Dataset, DatasetLink
        Dataset.objects.create(organization=self.org, kind='layer', layer=self.layer, name='Study area',
                               privacy_class='private')
        marks = SurveyMapLayer.objects.create(survey=self.survey, name='Marks', source='question',
                                              source_question_code='Q1', geojson='')
        before = set(layers_for(self.survey).values_list('pk', flat=True))
        _migration('0136_upload_layers_live_in_data').layers_to_data(apps, None)
        self.layer.refresh_from_db()
        marks.refresh_from_db()
        self.assertEqual((self.layer.survey_id, self.layer.organization_id), (None, self.org.pk))
        self.assertEqual(marks.survey_id, self.survey.pk)
        dataset = Dataset.objects.get(layer=self.layer)
        self.assertEqual(dataset.privacy_class, 'public')
        self.assertTrue(DatasetLink.objects.filter(dataset=dataset, survey=self.survey).exists())
        self.assertEqual(set(layers_for(self.survey).values_list('pk', flat=True)), before)

    def test_survey_delete_keeps_the_dataset(self):
        """
        GIVEN a migrated upload layer
        WHEN the survey is deleted
        THEN the dataset is still in Data with nothing using it
        """
        from data.models import Dataset
        _migration('0136_upload_layers_live_in_data').layers_to_data(apps, None)
        self.survey.delete()
        dataset = Dataset.objects.get(layer=self.layer)
        self.assertFalse(dataset.links.exists())


class PlacementTest(_Fixture):
    """Spec map-layer-placement / Requirement: A layer is shown by its placement on the map."""

    def test_every_section_now_and_later(self):
        """
        GIVEN a layer placed with scope `all` on a survey with two map sections and a form section
        WHEN the creator adds a third map section
        THEN the layer renders on all three maps and the form section has none
        """
        svc_placements.place(self.actor, self.survey, self.layer.pk)
        s4 = SurveySection.objects.create(survey_header=self.survey, name='s4', title='Map 3', code='S4', layout='map')
        for section in (self.s1, self.s2, s4):
            self.assertEqual(section_layer_ids(section), [self.layer.pk])
        self.assertEqual(section_layer_ids(self.form), [])

    def test_only_picked_sections(self):
        """
        GIVEN a layer placed with scope `sections` naming section 2
        THEN it renders on section 2 and not on section 1
        """
        svc_placements.place(self.actor, self.survey, self.layer.pk, 'sections', ['S2'])
        self.assertEqual(section_layer_ids(self.s1), [])
        self.assertEqual(section_layer_ids(self.s2), [self.layer.pk])

    def test_repeated_section_codes(self):
        """
        GIVEN two sections sharing the code `S1` and a placement naming `S1#1`
        THEN the layer renders only on the second of them
        """
        twin = SurveySection.objects.create(survey_header=self.survey, name='s1_2', title='Map 1 copy', code='S1',
                                            layout='map')
        self.assertEqual((section_ref(self.s1), section_ref(twin)), ('S1#0', 'S1#1'))
        svc_placements.place(self.actor, self.survey, self.layer.pk, 'sections', ['S1#1'])
        self.assertEqual(section_layer_ids(self.s1), [])
        self.assertEqual(section_layer_ids(twin), [self.layer.pk])

    def test_a_ref_written_before_a_duplicate_keeps_its_section(self):
        """
        GIVEN a placement naming `S1` while the code was unique
        WHEN the section is duplicated (the copy keeps the code)
        THEN the layer stays on the first section and not on the copy
        """
        svc_placements.place(self.actor, self.survey, self.layer.pk, 'sections', ['S1'])
        twin = SurveySection.objects.create(survey_header=self.survey, name='s1_2', title='Map 1 copy', code='S1',
                                            layout='map')
        self.assertEqual(section_layer_ids(self.s1), [self.layer.pk])
        self.assertEqual(section_layer_ids(twin), [])

    def test_draft_copy_reads_the_canonical_placements(self):
        """
        GIVEN a published survey with a layer on section 2 and unpublished changes
        WHEN the draft copy's section 2 is read, and a placement is added while the draft exists
        THEN the draft shows the canonical placement, the new one is written on the canonical survey
             in place, and the draft gets no rows of its own
        """
        from survey.versioning import clone_survey_for_draft
        self.survey.status = 'published'
        self.survey.save()
        svc_placements.place(self.actor, self.survey, self.layer.pk, 'sections', ['S2'])
        draft = clone_survey_for_draft(self.survey)
        draft_s2 = SurveySection.objects.get(survey_header=draft, code='S2')
        self.assertEqual(section_layer_ids(draft_s2), [self.layer.pk])
        other = _objects_layer(self.survey, name='Bike lanes')
        svc_placements.place(self.actor, draft, other.pk)
        self.assertEqual(LayerPlacement.objects.filter(survey=self.survey).count(), 2)
        self.assertFalse(LayerPlacement.objects.filter(survey=draft).exists())
        self.assertEqual(SurveyHeader.objects.get(pk=self.survey.pk).status, 'published')

    def test_untick_one_section_of_an_all_placement(self):
        """
        GIVEN a layer on every map section
        WHEN the Map card unticks it for section 1, then unticks section 2
        THEN it first stays on section 2 only, then is on no map
        """
        svc_placements.place(self.actor, self.survey, self.layer.pk)
        svc_placements.set_on_section(self.actor, self.survey, self.layer.pk, self.s1, False)
        self.assertEqual((section_layer_ids(self.s1), section_layer_ids(self.s2)), ([], [self.layer.pk]))
        svc_placements.set_on_section(self.actor, self.survey, self.layer.pk, self.s2, False)
        self.assertFalse(LayerPlacement.objects.filter(survey=self.survey).exists())

    def test_place_a_layer_that_is_not_linked(self):
        """
        GIVEN a workspace dataset the survey does not link
        WHEN it is placed
        THEN the service refuses with a validation error naming the layer
        """
        loose = SurveyMapLayer.objects.create(survey=None, organization=self.org, name='Loose', geojson='')
        with self.assertRaises(ValidationFailed) as ctx:
            svc_placements.place(self.actor, self.survey, loose.pk)
        self.assertIn(str(loose.pk), ctx.exception.fields['layer'][0])

    def test_unknown_section_is_refused(self):
        """
        GIVEN a placement naming a section code that does not exist, and one naming the form section
        THEN both are refused
        """
        for refs in (['NOPE'], ['S3']):
            with self.assertRaises(ValidationFailed):
                svc_placements.place(self.actor, self.survey, self.layer.pk, 'sections', refs)

    def test_layers_stack_in_placement_order(self):
        """
        GIVEN two layers placed on every section, the second placed first
        THEN the section lists them in placement order, and reorder changes it
        """
        other = _objects_layer(self.survey, name='Bike lanes')
        svc_placements.place(self.actor, self.survey, other.pk)
        svc_placements.place(self.actor, self.survey, self.layer.pk)
        self.assertEqual(section_layer_ids(self.s1), [other.pk, self.layer.pk])
        svc_placements.reorder(self.actor, self.survey, [self.layer.pk, other.pk])
        self.assertEqual(section_layer_ids(self.s1), [self.layer.pk, other.pk])
        self.assertEqual([p.layer_id for p in placements_for(self.survey)], [self.layer.pk, other.pk])


class MapCardTest(_Fixture):
    """Spec map-layer-placement / Requirement: The Map card places layers from Build."""

    def setUp(self):
        super().setUp()
        from survey.models import Membership
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.login(self.owner)

    def login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def test_section_panel_has_a_map_card_and_a_form_section_none(self):
        """
        GIVEN a layer placed on section 2 only
        WHEN the panels of section 1, section 2 and the form section are opened
        THEN map sections show the Map card with the layer (ticked on 2, not on 1) and the form none
        """
        svc_placements.place(self.actor, self.survey, self.layer.pk, 'sections', ['S2'])
        url = lambda s: f'/editor/surveys/{self.survey.uuid}/sections/{s.pk}/'
        one, two, form = (self.client.get(url(s)).content.decode() for s in (self.s1, self.s2, self.form))
        self.assertIn('id="map-card"', one)
        self.assertIn('Study area', two)
        self.assertRegex(two, r'data-layer-id="%d">\s*<input type="checkbox" class="map-card-tick" checked' % self.layer.pk)
        self.assertNotRegex(one, r'data-layer-id="%d">\s*<input type="checkbox" class="map-card-tick" checked' % self.layer.pk)
        self.assertNotIn('id="map-card"', form)

    def test_tick_on_a_live_survey_applies_in_place(self):
        """
        GIVEN a published survey
        WHEN an editor ticks the layer for section 1 in the Map card
        THEN the placement covers section 1 and no unpublished changes exist
        """
        from survey.models import Membership, SurveyCollaborator
        self.survey.status = 'published'
        self.survey.save()
        editor = User.objects.create_user('placement_editor', password='pw')
        Membership.objects.create(user=editor, organization=self.org, role='editor')
        SurveyCollaborator.objects.create(user=editor, survey=self.survey, role='editor')
        self.login(editor)
        response = self.client.post(f'/editor/surveys/{self.survey.uuid}/layers/{self.layer.pk}/place/section/',
                                    {'section': self.s1.pk, 'on': '1'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(section_layer_ids(self.s1), [self.layer.pk])
        self.assertFalse(SurveyHeader.objects.filter(published_version=self.survey).exists())

    def test_viewer_cannot_place(self):
        """
        GIVEN a collaborator with the viewer role
        WHEN they post a placement
        THEN the request is refused and nothing is placed
        """
        from survey.models import SurveyCollaborator
        viewer = User.objects.create_user('placement_viewer', password='pw')
        SurveyCollaborator.objects.create(user=viewer, survey=self.survey, role='viewer')
        self.login(viewer)
        response = self.client.post(f'/editor/surveys/{self.survey.uuid}/layers/{self.layer.pk}/place/',
                                    {'scope': 'all'})
        self.assertIn(response.status_code, (302, 403, 404))
        self.assertFalse(LayerPlacement.objects.exists())

    def test_settings_scope_control(self):
        """
        GIVEN a layer on every section
        WHEN Survey settings switches it to section 2 only, then to no map
        THEN the placement follows and Survey settings shows the on-no-map note
        """
        base = f'/editor/surveys/{self.survey.uuid}/layers/{self.layer.pk}/place/'
        svc_placements.place(self.actor, self.survey, self.layer.pk)
        self.assertEqual(self.client.post(base, {'scope': 'sections', 'sections': ['S2']}).json()['scope'], 'sections')
        self.assertEqual(section_layer_ids(self.s1), [])
        self.assertEqual(self.client.post(base, {'scope': 'off'}).json()['scope'], 'off')
        self.assertFalse(LayerPlacement.objects.exists())

    def test_respondent_legend_comes_from_placements(self):
        """
        GIVEN a published survey whose layer is placed on every section and no Objects question
        WHEN a respondent opens section 1
        THEN the panel shows "On this map" with the layer switched on
        """
        self.survey.status = 'published'
        self.survey.save()
        svc_placements.place(self.actor, self.survey, self.layer.pk)
        html = self.client.get(f'/surveys/{self.survey.name}/{self.s1.name}/').content.decode()
        self.assertIn('data-on-this-map', html)
        self.assertIn('data-otm-toggle="%d"' % self.layer.pk, html)
        self.assertIn('checked data-otm-toggle', html)


class QuestionPlacesItsLayerTest(_Fixture):
    """Spec layer-objects-question / Requirement: The `layer_objects` question type — picking a layer places it."""

    def test_objects_question_save_places_its_layer_on_the_section(self):
        """
        GIVEN a layer on no map
        WHEN an Objects-on-the-map question bound to it is created in section 2 through the service
        THEN section 2's map shows the layer and section 1's does not
        """
        from survey.services import questions as svc_questions
        svc_questions.create(self.actor, self.s2, {'name': 'Rate the sites', 'input_type': 'layer_objects',
                                                   'layer': str(self.layer.pk), 'objects_search': 'on',
                                                   'subtext': '', 'display_style': 'default', 'color': '#000000',
                                                   'min_objects': '0'})
        self.assertEqual(section_layer_ids(self.s2), [self.layer.pk])
        self.assertEqual(section_layer_ids(self.s1), [])

    def test_deleting_the_question_keeps_the_layer_on_the_map(self):
        """
        GIVEN a placed layer and the only Objects question asking about it
        WHEN the question is deleted
        THEN the layer stays on the section's map
        """
        svc_placements.place(self.actor, self.survey, self.layer.pk)
        q = Question.objects.create(survey_section=self.s1, code='ASK2', name='Rate', input_type='layer_objects',
                                    layer=self.layer, order_number=1)
        q.delete()
        self.assertEqual(section_layer_ids(self.s1), [self.layer.pk])
