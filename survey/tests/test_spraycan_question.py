"""Tests for the `spraycan-question` capability (openspec/specs/spraycan-question/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, SimpleTestCase
from django.contrib.auth.models import User
import json
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
from survey.cloning import clone_question
from survey.tests.helpers import _make_org


# ---------------------------------------------------------------------------
# Spray area question type (change spraycan-question-type)
# ---------------------------------------------------------------------------

class SpraycanTypeSetsTest(SimpleTestCase):
    """Spec spraycan-question: the fourth geo type is in every set the code consults."""

    def test_geo_sets_include_spraycan(self):
        """
        GIVEN the shared type sets in survey/question_types.py
        WHEN membership of `spraycan` is checked
        THEN it is a geo type, a parent type and a map-only type, maps to the
             `multipoint` column, and is NOT a multi-feature or shared-map source type
        """
        from survey.question_types import (
            GEO_TYPES, PARENT_TYPES, MAP_ONLY_TYPES, MULTI_FEATURE_TYPES,
            SHARED_MAP_SOURCE_TYPES, geo_column,
        )
        self.assertIn('spraycan', GEO_TYPES)
        self.assertIn('spraycan', PARENT_TYPES)
        self.assertIn('spraycan', MAP_ONLY_TYPES)
        self.assertNotIn('spraycan', MULTI_FEATURE_TYPES)
        self.assertNotIn('spraycan', SHARED_MAP_SOURCE_TYPES)
        self.assertEqual(geo_column('spraycan'), 'multipoint')
        self.assertEqual(geo_column('polygon'), 'polygon')
        self.assertIsNone(geo_column('text'))

    def test_every_derived_set_imports_the_shared_one(self):
        """
        GIVEN the modules that used to carry a literal ('point','line','polygon')
        WHEN their geo sets are compared with question_types.GEO_TYPES
        THEN they are the same object or an equal set, so the next type is one edit
        """
        from survey.question_types import GEO_TYPES, SHARED_MAP_SOURCE_TYPES
        from survey import export, public_results, layers
        from survey.ai import validator
        self.assertEqual(set(export.EXPORT_GEOMETRY_TYPES), set(GEO_TYPES))
        self.assertEqual(set(public_results.GEO_INPUT_TYPES), set(GEO_TYPES))
        self.assertEqual(set(validator.GEO_INPUT_TYPES), set(GEO_TYPES))
        self.assertEqual(set(layers.GEO_INPUT_TYPES), set(SHARED_MAP_SOURCE_TYPES))
        for t in GEO_TYPES:
            self.assertIn(t, export.GEOMETRY_TYPE_NAMES)
            self.assertIn(t, export.OGR_GEOMETRY_TYPES)


class SpraycanSectionPostTest(TestCase):
    """Spec spraycan-question: one MultiPoint per respondent, bounded and validated."""

    def setUp(self):
        self.org = _make_org('Spray Org')
        self.survey = SurveyHeader.objects.create(
            name='sprays', organization=self.org, status='published',
            available_languages=[], redirect_url='#',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='centre', title='Centre', code='S1', is_head=True,
        )
        self.spray = Question.objects.create(
            survey_section=self.section, code='SP', order_number=1, name='Where does the centre end?',
            input_type='spraycan', required=True, color='#d6336c',
        )
        self.sub = Question.objects.create(
            survey_section=self.section, code='SP_WHY', order_number=1, name='Why there?',
            input_type='text_line', parent_question_id=self.spray,
        )

    @staticmethod
    def _cloud(n, props=None):
        coords = [[13.3 + i * 0.0001, 52.5 + (i % 7) * 0.0001] for i in range(n)]
        feature = {'type': 'Feature', 'properties': props or {'question_id': 'SP'},
                   'geometry': {'type': 'MultiPoint', 'coordinates': coords}}
        return json.dumps(feature) + '|'

    def _post(self, value):
        self.client.get('/surveys/sprays/centre/')
        return self.client.post('/surveys/sprays/centre/', {'SP': value})

    def _answers(self):
        session = SurveySession.objects.get(pk=self.client.session['survey_session_id'])
        return Answer.objects.filter(survey_session=session, question=self.spray)

    def test_spray_is_stored_as_one_multipoint(self):
        """
        GIVEN a published survey with a spraycan question
        WHEN a respondent posts a 120-dot cloud
        THEN one Answer row holds a 120-point MultiPoint in `multipoint` and the
             other geometry columns are null
        """
        response = self._post(self._cloud(120))
        self.assertEqual(response.status_code, 302)
        answer = self._answers().get()
        self.assertEqual(answer.multipoint.geom_type, 'MultiPoint')
        self.assertEqual(len(answer.multipoint), 120)
        self.assertIsNone(answer.point)
        self.assertIsNone(answer.polygon)
        self.assertEqual(answer.geometry, answer.multipoint)

    def test_resubmit_replaces_the_cloud_and_keeps_subanswers_attached(self):
        """
        GIVEN a stored cloud with a sub-answer
        WHEN the respondent submits again with a smaller cloud and a new sub-answer
        THEN exactly one cloud row exists, holding the new dots, with the sub-answer under it
        """
        self._post(self._cloud(50, {'question_id': 'SP', 'SP_WHY': ['first']}))
        self._post(self._cloud(20, {'question_id': 'SP', 'SP_WHY': ['second']}))
        rows = self._answers()
        self.assertEqual(rows.count(), 1)
        cloud = rows.get()
        self.assertEqual(len(cloud.multipoint), 20)
        sub = Answer.objects.get(parent_answer_id=cloud, question=self.sub)
        self.assertEqual(sub.text, 'second')

    def test_only_one_cloud_per_respondent(self):
        """
        GIVEN a scripted POST with two cloud chunks
        WHEN the section is submitted
        THEN only the first cloud is stored
        """
        self._post(self._cloud(10) + self._cloud(30))
        self.assertEqual(self._answers().count(), 1)
        self.assertEqual(len(self._answers().get().multipoint), 10)

    def test_dots_snap_to_one_metre_and_dedupe(self):
        """
        GIVEN a posted cloud with 50 dots inside one square metre and 3 far apart
        WHEN the section is submitted
        THEN the stored cloud has 4 dots — paint saturates at one dot per metre,
             so the count reflects painted area, not the mouse's event rate
        """
        coords = [[13.3 + i * 1e-7, 52.5 + i * 1e-7] for i in range(50)]
        coords += [[13.31, 52.51], [13.32, 52.52], [13.33, 52.53]]
        feature = {'type': 'Feature', 'properties': {'question_id': 'SP'},
                   'geometry': {'type': 'MultiPoint', 'coordinates': coords}}
        self._post(json.dumps(feature) + '|')
        self.assertEqual(len(self._answers().get().multipoint), 4)

    def test_no_cap_by_default(self):
        """
        GIVEN a spraycan question with no max_dots setting
        WHEN a 5000-dot cloud is posted
        THEN all 5000 dots are stored and the widget carries no data-max-dots
        """
        self._post(self._cloud(5000))
        self.assertEqual(len(self._answers().get().multipoint), 5000)
        html = self.client.get('/surveys/sprays/centre/').content.decode()
        self.assertNotIn('data-max-dots="', html)

    def test_creator_cap_truncates_and_reaches_the_widget(self):
        """
        GIVEN a spraycan question with validation_settings max_dots = 100
        WHEN a 150-dot cloud is posted
        THEN the stored cloud holds the first 100 dots and the button carries data-max-dots="100"
        """
        self.spray.validation_settings = {'max_dots': 100}
        self.spray.save(update_fields=['validation_settings'])
        self._post(self._cloud(150))
        self.assertEqual(len(self._answers().get().multipoint), 100)
        html = self.client.get('/surveys/sprays/centre/').content.decode()
        self.assertIn('data-max-dots="100"', html)

    def test_malformed_coordinates_store_nothing(self):
        """
        GIVEN a cloud containing the coordinate [200, 95]
        WHEN it is posted
        THEN the response is the normal redirect, a warning is logged and no cloud is stored
        """
        feature = {'type': 'Feature', 'properties': {'question_id': 'SP'},
                   'geometry': {'type': 'MultiPoint', 'coordinates': [[13.3, 52.5], [200, 95]]}}
        with self.assertLogs('survey.views', level='WARNING') as logs:
            response = self._post(json.dumps(feature) + '|')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self._answers().count(), 0)
        self.assertIn('SP', logs.output[0])

    def test_section_get_restores_the_cloud(self):
        """
        GIVEN a stored cloud
        WHEN the section is opened again
        THEN the page's geo-answers data carries a MultiPoint feature for the question
        """
        self._post(self._cloud(12))
        response = self.client.get('/surveys/sprays/centre/')
        html = response.content.decode()
        self.assertIn('"type": "MultiPoint"', html)
        self.assertIn('data-brush-px="40"', html)
        self.assertIn('drawspray', html)

    def test_widget_carries_brush_size(self):
        """
        GIVEN a spraycan question with brush size `large`
        WHEN the section renders
        THEN the draw button carries the large brush radius and the dot cap
        """
        from survey.question_types import SPRAY_BRUSH_PX
        self.spray.spray_brush = 'large'
        self.spray.save(update_fields=['spray_brush'])
        html = self.client.get('/surveys/sprays/centre/').content.decode()
        self.assertIn('data-brush-px="%d"' % SPRAY_BRUSH_PX['large'], html)
        self.assertIn('data-brush-sizes=', html)
        self.assertRegex(html, r'js/spray_layer(\.[0-9a-f]+)?\.js')


class SpraycanEditorTest(TestCase):
    """Spec spraycan-question: the editor side — brush field, exclusions, cloning."""

    def setUp(self):
        self.org = _make_org('Spray Editor Org')
        self.user = User.objects.create_user(username='sprayed', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='spray_editor', organization=self.org, redirect_url='/thanks/', status='draft',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section One', code='S1', is_head=True,
        )
        self.client.login(username='sprayed', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def test_create_and_edit_save_brush_size(self):
        """
        GIVEN the question create endpoint
        WHEN a spraycan question is posted with Brush size `large`
        THEN it is stored with spray_brush=large and an edit to `small` sticks
        """
        self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/',
            {'name': 'Unsafe area', 'input_type': 'spraycan', 'color': '#d6336c', 'spray_brush': 'large'},
        )
        q = Question.objects.get(survey_section=self.section, name='Unsafe area')
        self.assertEqual(q.input_type, 'spraycan')
        self.assertEqual(q.spray_brush, 'large')
        self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/{q.id}/edit/',
            {'name': 'Unsafe area', 'input_type': 'spraycan', 'color': '#d6336c', 'spray_brush': 'small',
             'vs_min_features': '2', 'vs_max_features': '5', 'vs_max_dots': '500'},
        )
        q.refresh_from_db()
        self.assertEqual(q.spray_brush, 'small')
        self.assertEqual(q.validation_settings.get('max_dots'), 500)
        # One cloud per respondent: feature-count limits are not stored for this type
        self.assertNotIn('min_features', q.validation_settings)
        self.assertNotIn('max_features', q.validation_settings)

    def test_spraycan_refused_in_form_section(self):
        """
        GIVEN a section with layout 'form'
        WHEN a spraycan question is posted to the create endpoint
        THEN the save is refused and no question is created
        """
        self.section.layout = 'form'
        self.section.save()
        self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/',
            {'name': 'Fuzzy', 'input_type': 'spraycan', 'color': '#000000'},
        )
        self.assertFalse(Question.objects.filter(survey_section=self.section, name='Fuzzy').exists())

    def test_spraycan_not_offered_as_sub_question(self):
        """
        GIVEN the question form bound as a sub-question
        WHEN its input_type choices are inspected
        THEN spraycan is absent, like the other geo types
        """
        from survey.editor_forms import QuestionForm
        form = QuestionForm(is_subquestion=True, section=self.section)
        values = {v for v, _ in form.fields['input_type'].choices}
        self.assertNotIn('spraycan', values)
        self.assertNotIn('polygon', values)

    def test_spraycan_is_not_a_shared_map_source(self):
        """
        GIVEN a spraycan and a point question
        WHEN the shared-map source candidates are listed
        THEN only the point question is offered
        """
        from survey.editor_views import _geo_questions
        Question.objects.create(survey_section=self.section, name='Cloud', code='CL', input_type='spraycan')
        pt = Question.objects.create(survey_section=self.section, name='Spot', code='PT', input_type='point')
        self.assertEqual([q.id for q in _geo_questions(self.survey)], [pt.id])

    def test_clone_keeps_the_brush(self):
        """
        GIVEN a spraycan question with brush size `small`
        WHEN it is cloned into another section
        THEN the copy is a spraycan question with brush size `small`
        """
        from survey.cloning import clone_question
        q = Question.objects.create(survey_section=self.section, name='Cloud', code='CL',
                                    input_type='spraycan', spray_brush='small')
        other = SurveySection.objects.create(survey_header=self.survey, name='sec2', title='Two', code='S2')
        copy = clone_question(q, target_section=other)
        self.assertEqual(copy.input_type, 'spraycan')
        self.assertEqual(copy.spray_brush, 'small')

    def test_picker_lists_spray_area_with_the_map_questions(self):
        """
        GIVEN the model choices
        WHEN picker groups are built
        THEN "Spray area" sits in the Map questions group after the polygon type
        """
        from survey.question_types import picker_groups_for
        from survey.models import INPUT_TYPE_CHOICES
        groups = dict(picker_groups_for(INPUT_TYPE_CHOICES))
        values = [t['value'] for t in groups['Map questions']]
        self.assertEqual(values.index('spraycan'), values.index('polygon') + 1)
        entry = next(t for t in groups['Map questions'] if t['value'] == 'spraycan')
        self.assertEqual(entry['label'], 'Spray area')
