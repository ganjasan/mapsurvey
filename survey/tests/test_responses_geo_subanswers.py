"""Tests for the `responses-geo-subanswers` capability (openspec/specs/responses-geo-subanswers/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point, Polygon
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
from survey.analytics import SurveyAnalyticsService
from survey.tests.helpers import _make_org


class GeoSubanswerVisibilityTest(TestCase):
    """Sub-answers (mapped-object attributes) in the editor Responses screen."""

    def setUp(self):
        from survey.analytics import SurveyAnalyticsService
        self.SurveyAnalyticsService = SurveyAnalyticsService

        self.org = _make_org('GeoSubOrg')
        self.user = User.objects.create_user('geosubowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='geosubowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

        self.survey = SurveyHeader.objects.create(
            name='geosub_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.q_point = Question.objects.create(
            survey_section=self.section, name='Tree', code='q1',
            input_type='point', order_number=1,
        )
        self.sub_species = Question.objects.create(
            survey_section=self.section, name='Species', code='q1a',
            input_type='choice', order_number=1, parent_question_id=self.q_point,
            choices=[{'code': 1, 'name': 'Oak'}, {'code': 2, 'name': 'Pine'}],
        )
        self.sub_height = Question.objects.create(
            survey_section=self.section, name='Height', code='q1b',
            input_type='number', order_number=2, parent_question_id=self.q_point,
        )
        self.sub_notes = Question.objects.create(
            survey_section=self.section, name='Notes', code='q1c',
            input_type='text', order_number=3, parent_question_id=self.q_point,
        )

    def _add_object(self, session, point, species=None, height=None, notes=None):
        """Helper: create one geo answer with optional sub-answers."""
        geo = Answer.objects.create(
            survey_session=session, question=self.q_point, point=point,
        )
        if species is not None:
            Answer.objects.create(
                survey_session=session, question=self.sub_species,
                parent_answer_id=geo, selected_choices=[species],
            )
        if height is not None:
            Answer.objects.create(
                survey_session=session, question=self.sub_height,
                parent_answer_id=geo, numeric=height,
            )
        if notes is not None:
            Answer.objects.create(
                survey_session=session, question=self.sub_notes,
                parent_answer_id=geo, text=notes,
            )
        return geo

    def test_feature_collection_includes_ordered_attributes(self):
        """
        GIVEN a point answer with choice, number and text sub-answers
        WHEN get_geo_feature_collection is called
        THEN the feature carries attributes in sub-question order with
             type-appropriate display values
        """
        session = SurveySession.objects.create(survey=self.survey)
        self._add_object(session, Point(30.5, 60.0), species=1, height=12, notes='old tree')

        fc = self.SurveyAnalyticsService(self.survey).get_geo_feature_collection()

        self.assertEqual(len(fc['features']), 1)
        self.assertEqual(fc['features'][0]['properties']['attributes'], [
            {'name': 'Species', 'value': 'Oak'},
            {'name': 'Height', 'value': '12.0'},
            {'name': 'Notes', 'value': 'old tree'},
        ])

    def test_feature_without_subanswers_has_empty_attributes(self):
        """
        GIVEN a point answer with no child answers
        WHEN get_geo_feature_collection is called
        THEN its feature has an empty attributes list and keeps existing keys
        """
        session = SurveySession.objects.create(survey=self.survey)
        self._add_object(session, Point(30.5, 60.0))

        fc = self.SurveyAnalyticsService(self.survey).get_geo_feature_collection()

        props = fc['features'][0]['properties']
        self.assertEqual(props['attributes'], [])
        self.assertEqual(props['question'], 'Tree')
        self.assertEqual(props['type'], 'point')
        self.assertEqual(props['session_id'], session.id)

    def test_feature_collection_query_count_is_bounded(self):
        """
        GIVEN many geo objects with sub-answers
        WHEN get_geo_feature_collection is called
        THEN the number of queries does not grow with the number of objects
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        session = SurveySession.objects.create(survey=self.survey)
        self._add_object(session, Point(30.5, 60.0), species=1, height=1)
        with CaptureQueriesContext(connection) as small:
            self.SurveyAnalyticsService(self.survey).get_geo_feature_collection()

        for i in range(5):
            self._add_object(session, Point(30.5 + i, 60.0), species=2, height=i)
        with CaptureQueriesContext(connection) as large:
            self.SurveyAnalyticsService(self.survey).get_geo_feature_collection()

        self.assertEqual(len(small), len(large))

    def test_session_answers_number_multiple_objects(self):
        """
        GIVEN a session with two points for one geo question
        WHEN format_session_answers is called
        THEN each object carries a numbered label and its own attributes
        """
        session = SurveySession.objects.create(survey=self.survey)
        self._add_object(session, Point(30.5, 60.0), species=1)
        self._add_object(session, Point(31.5, 61.0), species=2)

        rows, features = self.SurveyAnalyticsService(self.survey).format_session_answers(session)

        geo_rows = [r for r in rows if r['input_type'] == 'point']
        # The numbering moved off the row's value and onto the label, which the
        # map titles objects with; the value now reads like the table's cell.
        self.assertEqual([r['geo_label'] for r in geo_rows], ['point feature 1', 'point feature 2'])
        self.assertEqual([r['value'] for r in geo_rows], ['60.00, 30.50', '61.00, 31.50'])
        self.assertEqual(geo_rows[0]['attributes'], [{'name': 'Species', 'value': 'Oak'}])
        self.assertEqual(geo_rows[1]['attributes'], [{'name': 'Species', 'value': 'Pine'}])
        self.assertEqual(features[0]['properties']['attributes'], geo_rows[0]['attributes'])
        self.assertEqual(features[1]['properties']['attributes'], geo_rows[1]['attributes'])

    def test_session_answers_single_object_keeps_plain_value(self):
        """
        GIVEN a session with one geo object and no sub-answers
        WHEN format_session_answers is called
        THEN the label stays un-numbered and attributes are empty
        """
        session = SurveySession.objects.create(survey=self.survey)
        self._add_object(session, Point(30.5, 60.0))

        rows, _ = self.SurveyAnalyticsService(self.survey).format_session_answers(session)

        geo_row = next(r for r in rows if r['input_type'] == 'point')
        self.assertEqual(geo_row['geo_label'], 'point feature')
        self.assertEqual(geo_row['value'], '60.00, 30.50')
        self.assertEqual(geo_row['attributes'], [])

    def test_session_answers_carry_object_id_and_label(self):
        """
        GIVEN a session with two objects for one geo question
        WHEN format_session_answers is called
        THEN every feature carries the geo answer's pk and its own label,
             and the previously specified properties are untouched
        """
        session = SurveySession.objects.create(survey=self.survey)
        self._add_object(session, Point(30.5, 60.0), species=1)
        self._add_object(session, Point(31.5, 61.0), species=2)

        rows, features = self.SurveyAnalyticsService(self.survey).format_session_answers(session)

        object_ids = [f['properties']['object_id'] for f in features]
        self.assertEqual(len(set(object_ids)), len(object_ids))
        self.assertEqual(
            sorted(object_ids),
            sorted(Answer.objects.filter(
                survey_session=session, point__isnull=False,
                parent_answer_id__isnull=True,
            ).values_list('id', flat=True)),
        )
        self.assertEqual(
            [f['properties']['label'] for f in features],
            ['point feature 1', 'point feature 2'],
        )
        # Rows point at the same objects, which is what makes "show this one
        # on the map" resolvable.
        self.assertEqual(
            [r['geo_object_id'] for r in rows if r['input_type'] == 'point'],
            object_ids,
        )
        for f in features:
            self.assertIn('question', f['properties'])
            self.assertIn('type', f['properties'])
            self.assertIn('attributes', f['properties'])

    def test_polygon_cell_reports_vertex_count(self):
        """
        GIVEN a polygon answer
        WHEN its display value is formatted
        THEN the vertex count is shown, not the bare type name

        Regression: the formatter read `.exterior`, which GEOS polygons do not
        have, and a blanket except turned every polygon into "polygon".
        """
        session = SurveySession.objects.create(survey=self.survey)
        polygon_q = Question.objects.create(
            survey_section=self.section, name='Area', input_type='polygon', order_number=90,
        )
        Answer.objects.create(
            survey_session=session, question=polygon_q,
            polygon=Polygon(((0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0))),
        )

        rows, _ = self.SurveyAnalyticsService(self.survey).format_session_answers(session)

        geo_row = next(r for r in rows if r['input_type'] == 'polygon')
        self.assertEqual(geo_row['value'], '4 vertices')

    def test_session_detail_markup_shows_and_escapes_subanswers(self):
        """
        GIVEN a geo object whose text sub-answer contains markup
        WHEN the session detail modal is rendered
        THEN the attribute name and value appear and the markup is escaped
        """
        session = SurveySession.objects.create(survey=self.survey)
        self._add_object(
            session, Point(30.5, 60.0), species=1,
            notes='<script>alert(1)</script>',
        )

        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{session.id}/'
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Species')
        self.assertContains(response, 'Oak')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_detail_partial_renders_geo_preview_and_map_entry_points(self):
        """
        GIVEN a session holding a geo object
        WHEN the detail partial is rendered
        THEN it carries the preview container, the geo payload and a control
             for opening the object on the full-size map
        """
        session = SurveySession.objects.create(survey=self.survey)
        self._add_object(session, Point(30.5, 60.0), species=1)

        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{session.id}/'
        )

        self.assertContains(response, 'id="session-mini-map"')
        self.assertContains(response, 'id="session-geo-data"')
        self.assertContains(response, 'session-geo-open')
        self.assertContains(response, 'data-geo-object-id=')

    def test_detail_partial_without_geo_has_no_preview(self):
        """
        GIVEN a session with no geo answers
        WHEN the detail partial is rendered
        THEN no preview container and no map entry point are emitted
        """
        session = SurveySession.objects.create(survey=self.survey)

        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{session.id}/'
        )

        self.assertNotContains(response, 'id="session-mini-map"')
        self.assertNotContains(response, 'session-geo-open')

    def test_dashboard_provides_the_container_the_partial_binds_to(self):
        """
        GIVEN the dashboard template rendered for the active RESPONSES_V2 state
        WHEN the session detail partial's geo wiring is considered
        THEN the containers it targets exist in the dashboard

        Regression guard: the v1→v2 move carried the mini-map markup over but
        left its initialiser bound to `#sessionDetailModal`, a node v2 does not
        render. The handler could never fire, so the preview stayed an empty
        box — and no Django test noticed, because the break was pure client
        wiring. This asserts the contract between the two templates instead.
        """
        from django.conf import settings as django_settings

        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/analytics/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()

        if getattr(django_settings, 'RESPONSES_V2', False):
            # The partial is swapped into the drawer body and initialises
            # itself there; the map modal it opens must exist in the host page.
            self.assertIn('id="rv2-drawer-body"', html)
            self.assertIn('id="sessionGeoMapModal"', html)
            self.assertIn('id="session-geo-modal-map"', html)
            self.assertNotIn('id="sessionDetailModal"', html)
        else:
            self.assertIn('id="sessionDetailModal"', html)
