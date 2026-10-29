"""Tests for the `response-data-export` capability (openspec/specs/response-data-export/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point, LineString, Polygon
from io import BytesIO
import json
import zipfile
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
import csv
from survey.tests.helpers import _make_org


class CleanExportTest(TestCase):
    """Tests for clean export (respects validation status and trash)."""

    def setUp(self):
        self.org = _make_org('ExportOrg')
        self.user = User.objects.create_user('exportuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

        self.survey = SurveyHeader.objects.create(
            name='export_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.q_text = Question.objects.create(
            survey_section=self.section, name='Comment', code='q1',
            input_type='text', order_number=1,
        )
        self.q_point = Question.objects.create(
            survey_section=self.section, name='Location', code='q2',
            input_type='point', order_number=2,
        )
        self.client.login(username='exportuser', password='pass')

    def _create_session(self, text='hello', point=None, **kwargs):
        session = SurveySession.objects.create(survey=self.survey, **kwargs)
        Answer.objects.create(survey_session=session, question=self.q_text, text=text)
        if point:
            Answer.objects.create(survey_session=session, question=self.q_point, point=point)
        return session

    def _download(self, include_all=False):
        url = f'/surveys/{self.survey.uuid}/download'
        if include_all:
            url += '?include_all=1'
        return self.client.get(url)

    def _extract_csv(self, response):
        import csv
        import io
        zip_buffer = BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            csv_name = [n for n in zf.namelist() if n.endswith('.csv')][0]
            csv_text = zf.read(csv_name).decode('utf-8')
        reader = csv.DictReader(io.StringIO(csv_text))
        return list(reader)

    def _extract_geojson(self, response):
        zip_buffer = BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            geojson_name = [n for n in zf.namelist() if n.endswith('.geojson')][0]
            return json.loads(zf.read(geojson_name))

    def test_clean_export_excludes_trashed(self):
        """
        GIVEN 2 active sessions and 1 trashed session
        WHEN download_data is called without include_all
        THEN CSV contains only 2 rows
        """
        self._create_session(text='good1')
        self._create_session(text='good2')
        self._create_session(text='trashed', is_deleted=True)
        resp = self._download()
        self.assertEqual(resp.status_code, 200)
        rows = self._extract_csv(resp)
        self.assertEqual(len(rows), 2)

    def test_clean_export_excludes_not_approved(self):
        """
        GIVEN 1 active session and 1 not_approved session
        WHEN download_data is called without include_all
        THEN CSV contains only 1 row
        """
        self._create_session(text='good')
        self._create_session(text='bad', validation_status='not_approved')
        resp = self._download()
        rows = self._extract_csv(resp)
        self.assertEqual(len(rows), 1)

    def test_include_all_exports_everything(self):
        """
        GIVEN 1 active, 1 trashed, and 1 not_approved session
        WHEN download_data is called with include_all=1
        THEN CSV contains all 3 rows
        """
        self._create_session(text='good')
        self._create_session(text='trashed', is_deleted=True)
        self._create_session(text='rejected', validation_status='not_approved')
        resp = self._download(include_all=True)
        rows = self._extract_csv(resp)
        self.assertEqual(len(rows), 3)

    def test_csv_has_validation_status_column(self):
        """
        GIVEN a session with validation_status='approved'
        WHEN download_data is called
        THEN CSV rows contain a validation_status column
        """
        self._create_session(text='data', validation_status='approved')
        resp = self._download()
        rows = self._extract_csv(resp)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['validation_status'], 'approved')

    def test_geojson_has_validation_status_and_session_id(self):
        """
        GIVEN a session with a geo answer
        WHEN download_data is called
        THEN GeoJSON features have validation_status and session_id properties
        """
        s = self._create_session(text='geo', point=Point(13.4, 52.5), validation_status='approved')
        resp = self._download()
        geojson = self._extract_geojson(resp)
        self.assertEqual(len(geojson['features']), 1)
        props = geojson['features'][0]['properties']
        self.assertEqual(props['validation_status'], 'approved')
        self.assertEqual(props['session_id'], s.id)


class ExportValueCorrectnessTest(TestCase):
    """Value-level tests for the respondent-data download.

    The existing export tests assert how many rows come back and that the
    metadata columns are present. None of them assert that a given answer
    reaches a given column, and none exercise sub-question properties at all —
    which is why the defects in change `export-data-integrity` survived.

    Tests here are characterisation tests: they pin the behaviour that is
    already correct, so the refactor that fixes the defects cannot quietly
    change anything else.
    """

    CHOICES = [
        {"code": 1, "name": {"en": "Ruhig"}},
        {"code": 2, "name": {"en": "Laut"}},
    ]

    def setUp(self):
        self.org = _make_org('ValueExportOrg')
        self.user = User.objects.create_user('valueexportuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

        self.survey = SurveyHeader.objects.create(
            name='value_export_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )

        def q(name, code, input_type, order, choices=None, parent=None):
            return Question.objects.create(
                survey_section=self.section, name=name, code=code,
                input_type=input_type, order_number=order,
                choices=choices, parent_question_id=parent,
            )

        self.q_text = q('Comment', 'q_text', 'text', 1)
        self.q_text_line = q('Title', 'q_line', 'text_line', 2)
        self.q_number = q('District', 'q_num', 'number', 3)
        self.q_range = q('Loudness', 'q_range', 'range', 4, self.CHOICES)
        self.q_choice = q('Character', 'q_choice', 'choice', 5, self.CHOICES)
        self.q_rating = q('Quality', 'q_rating', 'rating', 6, self.CHOICES)
        self.q_multi = q('Sources', 'q_multi', 'multichoice', 7, self.CHOICES)
        self.q_html = q('Intro', 'q_html', 'html', 8)

        self.q_point = q('Location', 'q_point', 'point', 9)
        self.sub_text = q('SubComment', 'sq_text', 'text', 1, parent=self.q_point)
        self.sub_number = q('SubCount', 'sq_num', 'number', 2, parent=self.q_point)
        self.sub_choice = q('SubCharacter', 'sq_choice', 'choice', 3,
                            self.CHOICES, parent=self.q_point)

        self.client.login(username='valueexportuser', password='pass')

    def _session(self, **kwargs):
        return SurveySession.objects.create(survey=self.survey, **kwargs)

    def _answer(self, session, question, parent=None, **fields):
        return Answer.objects.create(
            survey_session=session, question=question,
            parent_answer_id=parent, **fields,
        )

    def _download(self):
        return self.client.get(f'/surveys/{self.survey.uuid}/download')

    def _csv_rows(self, response):
        import csv
        import io
        with zipfile.ZipFile(BytesIO(response.content), 'r') as zf:
            name = [n for n in zf.namelist() if n.endswith('.csv')][0]
            text = zf.read(name).decode('utf-8')
        return list(csv.DictReader(io.StringIO(text)))

    def _geojson(self, response, question_name='Location'):
        with zipfile.ZipFile(BytesIO(response.content), 'r') as zf:
            name = [n for n in zf.namelist()
                    if n.endswith('.geojson') and question_name in n][0]
            return json.loads(zf.read(name))

    def _answer_all_flat(self, session):
        """Answer every non-geo question of the survey."""
        self._answer(session, self.q_text, text='Ein Kommentar')
        self._answer(session, self.q_text_line, text='Ein Titel')
        self._answer(session, self.q_number, numeric=7)
        self._answer(session, self.q_range, numeric=5)
        self._answer(session, self.q_choice, selected_choices=[2])
        self._answer(session, self.q_rating, selected_choices=[1])
        self._answer(session, self.q_multi, selected_choices=[1, 2])

    # ── 1.1 CSV: every value-bearing type lands in its own column ──────────

    def test_csv_exports_each_value_type_in_its_own_column(self):
        """
        GIVEN one session answering every non-geo question type
        WHEN the data is downloaded
        THEN each answer appears in the column named after its own question
        """
        self._answer_all_flat(self._session())

        rows = self._csv_rows(self._download())

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['Comment'], 'Ein Kommentar')
        self.assertEqual(row['Title'], 'Ein Titel')
        self.assertEqual(row['District'], '7.0')
        self.assertEqual(row['Loudness'], '5.0')
        self.assertEqual(row['Character'], 'Laut')
        self.assertEqual(row['Quality'], 'Ruhig')
        self.assertEqual(row['Sources'], 'Ruhig; Laut')

    def test_csv_keeps_values_on_their_own_row(self):
        """
        GIVEN two sessions answering the same question differently
        WHEN the data is downloaded
        THEN each row carries its own session's answer
        """
        first = self._session()
        self._answer(first, self.q_text, text='erste')
        second = self._session()
        self._answer(second, self.q_text, text='zweite')

        rows = self._csv_rows(self._download())

        self.assertEqual(len(rows), 2)
        by_session = {int(r['session_id']): r['Comment'] for r in rows}
        self.assertEqual(by_session[first.id], 'erste')
        self.assertEqual(by_session[second.id], 'zweite')

    # ── 1.2 GeoJSON: sub-question properties ───────────────────────────────

    def test_geojson_exports_each_subquestion_property(self):
        """
        GIVEN a geo answer whose sub-questions are all answered
        WHEN the data is downloaded
        THEN each property holds its own sub-question's value
        """
        session = self._session()
        geo = self._answer(session, self.q_point, point=Point(13.4, 52.5))
        self._answer(session, self.sub_text, parent=geo, text='Lärm')
        self._answer(session, self.sub_number, parent=geo, numeric=7)
        self._answer(session, self.sub_choice, parent=geo, selected_choices=[2])

        geojson = self._geojson(self._download())

        self.assertEqual(len(geojson['features']), 1)
        props = geojson['features'][0]['properties']
        self.assertEqual(props['SubComment'], 'Lärm')
        self.assertEqual(props['SubCount'], 7)
        self.assertEqual(props['SubCharacter'], 'Laut')

    def test_geojson_geometry_matches_the_answer(self):
        """
        GIVEN a geo answer at a known coordinate
        WHEN the data is downloaded
        THEN the feature geometry carries that coordinate
        """
        session = self._session()
        self._answer(session, self.q_point, point=Point(13.4, 52.5))

        geojson = self._geojson(self._download())

        geometry = geojson['features'][0]['geometry']
        self.assertEqual(geometry['type'], 'Point')
        self.assertAlmostEqual(geometry['coordinates'][0], 13.4)
        self.assertAlmostEqual(geometry['coordinates'][1], 52.5)

    # ── 1.3 Which questions produce a CSV column at all ────────────────────

    def test_geo_question_produces_a_layer_and_no_csv_column(self):
        """
        GIVEN a survey with a geo question that has been answered
        WHEN the data is downloaded
        THEN the geometry is exported as a GeoJSON layer, not a CSV column
        """
        session = self._session()
        self._answer_all_flat(session)
        self._answer(session, self.q_point, point=Point(13.4, 52.5))

        response = self._download()

        with zipfile.ZipFile(BytesIO(response.content), 'r') as zf:
            names = zf.namelist()
        self.assertTrue(any(n.endswith('.geojson') and 'Location' in n for n in names))
        self.assertNotIn('Location', self._csv_rows(response)[0])

    def test_display_only_question_produces_no_csv_column(self):
        """
        GIVEN a survey containing an html question, which collects nothing
        WHEN the data is downloaded
        THEN no column is named after it
        """
        self._answer_all_flat(self._session())

        rows = self._csv_rows(self._download())

        self.assertNotIn('Intro', rows[0])

    # ── 2.1-2.2 A blank sub-question must not inherit its neighbour ────────

    def test_blank_subquestion_exports_empty_not_the_neighbours_value(self):
        """
        GIVEN a geo answer whose first sub-question is answered and whose
              second has no Answer row at all
        WHEN the data is downloaded
        THEN the second sub-question's property is empty
        """
        session = self._session()
        geo = self._answer(session, self.q_point, point=Point(13.4, 52.5))
        self._answer(session, self.sub_text, parent=geo, text='Lärm')

        props = self._geojson(self._download())['features'][0]['properties']

        self.assertEqual(props['SubComment'], 'Lärm')
        self.assertEqual(props['SubCount'], '')

    def test_consecutive_blank_subquestions_all_export_empty(self):
        """
        GIVEN a geo answer with one answered sub-question followed by three
              with no Answer rows
        WHEN the data is downloaded
        THEN none of the three carries the answered sub-question's value
        """
        extra = Question.objects.create(
            survey_section=self.section, name='SubExtra', code='sq_extra',
            input_type='text_line', order_number=4, parent_question_id=self.q_point,
        )
        session = self._session()
        geo = self._answer(session, self.q_point, point=Point(13.4, 52.5))
        self._answer(session, self.sub_text, parent=geo, text='Lärm')

        props = self._geojson(self._download())['features'][0]['properties']

        self.assertEqual(props['SubCount'], '')
        self.assertEqual(props['SubCharacter'], '')
        self.assertEqual(props[extra.name], '')

    def test_display_only_subquestion_does_not_absorb_a_value(self):
        """
        GIVEN a geo answer with an answered text sub-question followed by an
              html sub-question, which can never hold input
        WHEN the data is downloaded
        THEN the html sub-question's property is empty
        """
        html_sub = Question.objects.create(
            survey_section=self.section, name='SubIntro', code='sq_html',
            input_type='html', order_number=4, parent_question_id=self.q_point,
        )
        session = self._session()
        geo = self._answer(session, self.q_point, point=Point(13.4, 52.5))
        self._answer(session, self.sub_text, parent=geo, text='Lärm')

        props = self._geojson(self._download())['features'][0]['properties']

        self.assertEqual(props[html_sub.name], '')

    # ── 2.3 datetime answers must reach the CSV ────────────────────────────

    def test_datetime_answer_appears_in_csv_as_iso_8601(self):
        """
        GIVEN a session answering a datetime question
        WHEN the data is downloaded
        THEN the CSV holds the answered moment as ISO 8601
        """
        Question.objects.create(
            survey_section=self.section, name='Observed', code='q_dt',
            input_type='datetime', order_number=10,
        )
        session = self._session()
        self._answer(session, Question.objects.get(code='q_dt'),
                     text='2026-08-04T19:21')

        rows = self._csv_rows(self._download())

        self.assertEqual(rows[0]['Observed'], '2026-08-04T19:21:00')

    def test_unparseable_datetime_passes_through_unchanged(self):
        """
        GIVEN a datetime answer holding a string that is not a datetime
        WHEN the data is downloaded
        THEN the raw string is exported rather than dropped
        """
        Question.objects.create(
            survey_section=self.section, name='Observed', code='q_dt',
            input_type='datetime', order_number=10,
        )
        session = self._session()
        self._answer(session, Question.objects.get(code='q_dt'), text='sometime')

        rows = self._csv_rows(self._download())

        self.assertEqual(rows[0]['Observed'], 'sometime')

    # ── 2.4 Backlog #23: number sub-question of a geo question ─────────────

    def test_number_subquestion_reaches_the_export(self):
        """
        GIVEN a number sub-question of a geo question, answered — the shape
              reported in backlog #23 as exporting blank
        WHEN the data is downloaded
        THEN the value appears in the feature's properties
        """
        session = self._session()
        geo = self._answer(session, self.q_point, point=Point(13.4, 52.5))
        self._answer(session, self.sub_number, parent=geo, numeric=12)

        props = self._geojson(self._download())['features'][0]['properties']

        self.assertEqual(props['SubCount'], 12)

    def test_top_level_number_question_reaches_the_csv(self):
        """
        GIVEN a top-level number question, answered
        WHEN the data is downloaded
        THEN the value appears in the CSV column named after it
        """
        session = self._session()
        self._answer(session, self.q_number, numeric=12)

        rows = self._csv_rows(self._download())

        self.assertEqual(rows[0]['District'], '12.0')

    # ── 2.5 Session metadata comes from the feature's own session ──────────

    def test_each_feature_reports_its_own_session(self):
        """
        GIVEN two sessions that each place a point with an answered
              sub-question
        WHEN the data is downloaded
        THEN each feature's session metadata is its own session's
        """
        first = self._session(validation_status='approved', language='de')
        geo_first = self._answer(first, self.q_point, point=Point(13.4, 52.5))
        self._answer(first, self.sub_text, parent=geo_first, text='erste')

        second = self._session(validation_status='not_checked', language='en')
        geo_second = self._answer(second, self.q_point, point=Point(13.5, 52.6))
        self._answer(second, self.sub_text, parent=geo_second, text='zweite')

        features = self._geojson(self._download())['features']

        by_session = {f['properties']['session_id']: f['properties'] for f in features}
        self.assertEqual(by_session[first.id]['SubComment'], 'erste')
        self.assertEqual(by_session[first.id]['validation_status'], 'approved')
        self.assertEqual(by_session[first.id]['language'], 'de')
        self.assertEqual(by_session[second.id]['SubComment'], 'zweite')
        self.assertEqual(by_session[second.id]['validation_status'], 'not_checked')
        self.assertEqual(by_session[second.id]['language'], 'en')

    # ── The layer has to be readable as a layer, not just as JSON ──────────

    def test_every_feature_carries_the_same_attribute_set(self):
        """
        GIVEN two geo answers, one with all sub-questions answered and one
              with none of them answered
        WHEN the data is downloaded
        THEN both features expose the same property keys

        A feature collection whose attribute set varies per feature loads in
        QGIS with columns missing for some rows, which is why blank
        sub-questions keep an empty property rather than being omitted.
        """
        complete = self._session()
        geo_complete = self._answer(complete, self.q_point, point=Point(13.4, 52.5))
        self._answer(complete, self.sub_text, parent=geo_complete, text='Lärm')
        self._answer(complete, self.sub_number, parent=geo_complete, numeric=7)
        self._answer(complete, self.sub_choice, parent=geo_complete, selected_choices=[2])

        empty = self._session()
        self._answer(empty, self.q_point, point=Point(13.5, 52.6))

        features = self._geojson(self._download())['features']

        self.assertEqual(len(features), 2)
        key_sets = [set(f['properties']) for f in features]
        self.assertEqual(key_sets[0], key_sets[1])
        self.assertIn('SubComment', key_sets[0])

    def test_exported_geometries_parse_as_geometries(self):
        """
        GIVEN answers of every geometry type
        WHEN the data is downloaded
        THEN each exported geometry is readable by a GIS reader
        """
        from django.contrib.gis.geos import GEOSGeometry

        q_line = Question.objects.create(
            survey_section=self.section, name='Route', code='q_line_geo',
            input_type='line', order_number=11,
        )
        q_polygon = Question.objects.create(
            survey_section=self.section, name='Area', code='q_poly_geo',
            input_type='polygon', order_number=12,
        )
        session = self._session()
        self._answer(session, self.q_point, point=Point(13.4, 52.5))
        self._answer(session, q_line, line=LineString((13.4, 52.5), (13.5, 52.6)))
        self._answer(session, q_polygon, polygon=Polygon(
            ((13.4, 52.5), (13.5, 52.5), (13.5, 52.6), (13.4, 52.5)),
        ))

        response = self._download()

        for name, expected in (('Location', 'Point'),
                               ('Route', 'LineString'),
                               ('Area', 'Polygon')):
            collection = self._geojson(response, question_name=name)
            geometry = collection['features'][0]['geometry']
            self.assertEqual(geometry['type'], expected)
            parsed = GEOSGeometry(json.dumps(geometry))
            self.assertTrue(parsed.valid, f'{name} exported an invalid geometry')


class SessionSourceInExportTest(TestCase):
    """Delta of change operator-entry: session tables carry `source` and `entered_by`."""

    def test_sessions_table_carries_the_source(self):
        """
        GIVEN one online session and one session entered from paper by operator `clerk`
        WHEN the sessions rows of the export are built
        THEN they read `online` / blank and `paper` / `clerk`
        """
        from survey import export
        org = _make_org('ExportSourceOrg')
        clerk = User.objects.create_user('clerk', password='x')
        survey = SurveyHeader.objects.create(name='export_source', organization=org, redirect_url='#')
        section = SurveySection.objects.create(survey_header=survey, name='s1', code='S1', is_head=True)
        q = Question.objects.create(survey_section=section, code='T', name='T', input_type='text')
        online = SurveySession.objects.create(survey=survey)
        paper = SurveySession.objects.create(survey=survey, source='paper', entered_by=clerk)
        for s in (online, paper):
            Answer.objects.create(survey_session=s, question=q, text='x')
        self.assertIn('source', export.SESSION_COLUMNS)
        self.assertIn('entered_by', export.SESSION_COLUMNS)
        rows = {r['session_id']: r for r in export.sessions_rows(export.collect(survey, [(survey, '')]))}
        self.assertEqual((rows[online.pk]['source'], rows[online.pk]['entered_by']), ('online', ''))
        self.assertEqual((rows[paper.pk]['source'], rows[paper.pk]['entered_by']), ('paper', 'clerk'))
