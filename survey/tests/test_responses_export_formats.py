"""Tests for the `responses-export-formats` capability (openspec/specs/responses-export-formats/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point, Polygon
from io import BytesIO
from unittest.mock import patch
import json
import zipfile
import unittest
from survey import export as _export
from survey.models import Organization, SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership, SurveyCollaborator
from survey.serialization import export_survey_to_zip, import_survey_from_zip
from survey.analytics import SurveyAnalyticsService
import os
import tempfile
import datetime as _dt
from urllib.parse import urlencode
from survey.tests.helpers import _make_org, _objects_layer


class ExportFormatsTest(TestCase):
    """The format catalogue of /download, the flat observations table, Excel, CSV."""

    def setUp(self):
        self.org = _make_org('FormatsOrg')
        self.user = User.objects.create_user('fmtowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='squirrel_count', organization=self.org, created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='Count', code='S1', is_head=True,
        )
        self.q_weather = Question.objects.create(
            survey_section=self.section, name='Weather', code='WX', input_type='choice', order_number=1,
            choices=[{'code': 'sun', 'name': 'Sunny'}, {'code': 'rain', 'name': 'Rainy'}],
        )
        self.q_white = Question.objects.create(
            survey_section=self.section, name='White squirrel', code='WS', input_type='point', order_number=2,
        )
        self.q_white_qty = Question.objects.create(
            survey_section=self.section, name='Quantity', code='WS_Q', input_type='number',
            parent_question_id=self.q_white, order_number=1,
        )
        self.q_white_note = Question.objects.create(
            survey_section=self.section, name='Note', code='WS_N', input_type='text',
            parent_question_id=self.q_white, order_number=2,
        )
        self.q_fox = Question.objects.create(
            survey_section=self.section, name='Fox squirrel', code='FS', input_type='point', order_number=3,
        )
        self.q_fox_qty = Question.objects.create(
            survey_section=self.section, name='Quantity', code='FS_Q', input_type='number',
            parent_question_id=self.q_fox, order_number=1,
        )
        self.q_zone = Question.objects.create(
            survey_section=self.section, name='Zone', code='ZN', input_type='polygon', order_number=4,
        )
        self.client.login(username='fmtowner', password='pass')

    # -- fixtures -----------------------------------------------------------

    def _session(self, **kwargs):
        import datetime as _dt

        kwargs.setdefault('start_datetime', _dt.datetime(2026, 9, 22, 18, 59, 30, tzinfo=_dt.timezone.utc))
        return SurveySession.objects.create(survey=self.survey, **kwargs)

    def _observe(self, session, question, point, quantity=None, note=None):
        parent = Answer.objects.create(survey_session=session, question=question, point=point)
        subs = {q.code: q for q in question.subQuestions()}
        if quantity is not None:
            Answer.objects.create(survey_session=session, question=subs[question.code + '_Q'],
                                  parent_answer_id=parent, numeric=quantity)
        if note is not None:
            Answer.objects.create(survey_session=session, question=subs['WS_N'],
                                  parent_answer_id=parent, text=note)
        return parent

    def _download(self, **params):
        from urllib.parse import urlencode
        url = f'/surveys/{self.survey.uuid}/download'
        if params:
            url += '?' + urlencode(params)
        return self.client.get(url)

    @staticmethod
    def _body(response):
        if hasattr(response, 'streaming_content'):
            return b''.join(response.streaming_content)
        return response.content

    def _workbook(self, response):
        import openpyxl
        self.assertEqual(response.status_code, 200, getattr(response, 'content', b'')[:200])
        return openpyxl.load_workbook(BytesIO(self._body(response)))

    @staticmethod
    def _rows(ws):
        rows = list(ws.iter_rows(values_only=True))
        header = list(rows[0])
        return header, [dict(zip(header, r)) for r in rows[1:]]

    # -- URL contract -------------------------------------------------------

    def test_legacy_link_unchanged(self):
        """
        GIVEN a session with a point and a choice answer
        WHEN the download is requested with no format parameter
        THEN the response is the GeoJSON+CSV archive: one .geojson per geo question, a BOM-less
             per-session CSV, and nothing else
        """
        s = self._session()
        Answer.objects.create(survey_session=s, question=self.q_weather, selected_choices=['sun'])
        self._observe(s, self.q_white, Point(-88.0936, 38.7265), quantity=2)
        response = self._download()
        self.assertEqual(response['Content-Type'], 'application/zip')
        archive = zipfile.ZipFile(BytesIO(response.content))
        names = sorted(archive.namelist())
        self.assertEqual(names, ['Fox squirrel.geojson', 'White squirrel.geojson', 'Zone.geojson',
                                 'squirrel_count.csv'])
        csv_bytes = archive.read('squirrel_count.csv')
        self.assertFalse(csv_bytes.startswith('﻿'.encode('utf-8')))
        self.assertIn(b'Sunny', csv_bytes)

    def test_unknown_format_is_400_without_event(self):
        """
        GIVEN a signed-in owner
        WHEN the download names an unknown format
        THEN the response is 400 and no data_exported event is emitted
        """
        with patch('survey.views.pe.emit') as emit:
            response = self._download(format='pdf')
        self.assertEqual(response.status_code, 400)
        self.assertEqual([c for c in emit.call_args_list if c.args[0] == 'data_exported'], [])

    def test_gis_format_without_ogr_is_400(self):
        """
        GIVEN a host without ogr2ogr
        WHEN a GIS format is requested
        THEN the response is 400
        """
        with patch('survey.export.OGR_AVAILABLE', False):
            response = self._download(format='gpkg')
        self.assertEqual(response.status_code, 400)

    def test_viewer_role_required_for_every_format(self):
        """
        GIVEN a signed-in user without a role on the survey
        WHEN they request the Excel export
        THEN the response is 404, exactly as for the legacy archive
        """
        User.objects.create_user('stranger', password='pass')
        self.client.login(username='stranger', password='pass')
        self.assertEqual(self._download(format='xlsx').status_code, 404)

    def test_data_exported_carries_the_chosen_format(self):
        """
        GIVEN a signed-in owner
        WHEN they download the Excel export
        THEN one data_exported event with format xlsx is emitted
        """
        with patch('survey.views.pe.emit') as emit:
            response = self._download(format='xlsx')
        self.assertEqual(response.status_code, 200)
        calls = [c for c in emit.call_args_list if c.args[0] == 'data_exported']
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[2]['format'], 'xlsx')

    # -- Excel --------------------------------------------------------------

    def test_workbook_shape(self):
        """
        GIVEN a survey with geo and choice questions and no Objects-on-the-map question
        WHEN it is exported as xlsx
        THEN the workbook has sheets observations, responses, sessions in that order and no objects sheet
        """
        self._session()
        wb = self._workbook(self._download(format='xlsx'))
        self.assertEqual(wb.sheetnames, ['observations', 'responses', 'sessions'])
        self.assertEqual(self._download(format='xlsx')['Content-Disposition'],
                         'attachment; filename="squirrel_count.xlsx"')

    def test_types_survive_the_round_trip(self):
        """
        GIVEN a session started 2026-09-22 18:59 UTC that placed a point with Quantity 3
        WHEN the observations sheet is read back
        THEN session_start_utc is a datetime, Quantity is 3 as a number and lat is a float
        """
        s = self._session()
        self._observe(s, self.q_white, Point(-88.0936, 38.7265), quantity=3)
        wb = self._workbook(self._download(format='xlsx'))
        header, rows = self._rows(wb['observations'])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        from datetime import datetime as _dt
        self.assertIsInstance(row['session_start_utc'], _dt)
        self.assertEqual(row['session_start_utc'].strftime('%Y-%m-%d %H:%M'), '2026-09-22 18:59')
        self.assertEqual(row['Quantity'], 3)
        self.assertIsInstance(row['lat'], float)
        self.assertAlmostEqual(row['lat'], 38.7265)
        self.assertAlmostEqual(row['lon'], -88.0936)
        self.assertEqual(wb['observations'].freeze_panes, 'A2')
        self.assertTrue(wb['observations']['A1'].font.bold)

    def test_shared_subquestion_name_is_one_column(self):
        """
        GIVEN point questions "White squirrel" and "Fox squirrel", each with a number sub-question
              named "Quantity", and one session placing one point on each with quantities 2 and 1
        WHEN the observations sheet is read
        THEN there are two rows, one Quantity column, question disambiguates, lat/lon are each point's
        """
        s = self._session()
        self._observe(s, self.q_white, Point(-88.0936, 38.7265), quantity=2, note='by the feeder')
        self._observe(s, self.q_fox, Point(-88.0940, 38.7262), quantity=1)
        wb = self._workbook(self._download(format='xlsx'))
        header, rows = self._rows(wb['observations'])
        self.assertEqual(header.count('Quantity'), 1)
        self.assertEqual(header[:12], list(_export.OBSERVATION_FIXED_COLUMNS))
        self.assertEqual(header[12:], ['Quantity', 'Note'])
        by_q = {r['question']: r for r in rows}
        self.assertEqual(set(by_q), {'White squirrel', 'Fox squirrel'})
        self.assertEqual(by_q['White squirrel']['Quantity'], 2)
        self.assertEqual(by_q['White squirrel']['Note'], 'by the feeder')
        self.assertEqual(by_q['Fox squirrel']['Quantity'], 1)
        self.assertIsNone(by_q['Fox squirrel']['Note'])
        self.assertAlmostEqual(by_q['Fox squirrel']['lon'], -88.0940)
        self.assertEqual(by_q['White squirrel']['question_code'], 'WS')
        self.assertEqual(by_q['White squirrel']['section'], 'Count')
        self.assertEqual(by_q['White squirrel']['version'], self.survey.version_number)
        self.assertEqual(by_q['White squirrel']['geometry_type'], 'Point')
        self.assertTrue(by_q['White squirrel']['wkt'].startswith('POINT ('))

    def test_polygon_row_has_centroid_and_wkt(self):
        """
        GIVEN a respondent drew a polygon
        WHEN the observations sheet is read
        THEN geometry_type is Polygon, lat/lon are the centroid and wkt starts with POLYGON ((
        """
        s = self._session()
        square = Polygon(((0, 0), (0, 2), (2, 2), (2, 0), (0, 0)))
        Answer.objects.create(survey_session=s, question=self.q_zone, polygon=square)
        wb = self._workbook(self._download(format='xlsx'))
        _, rows = self._rows(wb['observations'])
        self.assertEqual(rows[0]['geometry_type'], 'Polygon')
        self.assertAlmostEqual(rows[0]['lat'], 1.0)
        self.assertAlmostEqual(rows[0]['lon'], 1.0)
        self.assertTrue(rows[0]['wkt'].startswith('POLYGON (('))

    def test_blank_subquestion_stays_blank(self):
        """
        GIVEN a point whose Quantity sub-question has no answer row and whose Note is answered
        WHEN the observations sheet is read
        THEN the Quantity cell is empty and Note holds its own value
        """
        s = self._session()
        self._observe(s, self.q_white, Point(1, 1), note='only a note')
        wb = self._workbook(self._download(format='xlsx'))
        _, rows = self._rows(wb['observations'])
        self.assertIsNone(rows[0]['Quantity'])
        self.assertEqual(rows[0]['Note'], 'only a note')

    def test_excluded_sessions_absent_from_observations(self):
        """
        GIVEN a clean session, a trashed one and a not_approved one, each with a point
        WHEN the export runs without include_all
        THEN only the clean session's feature is in observations and sessions
        """
        good = self._session()
        self._observe(good, self.q_white, Point(1, 1), quantity=1)
        self._observe(self._session(is_deleted=True), self.q_white, Point(2, 2), quantity=1)
        self._observe(self._session(validation_status='not_approved'), self.q_white, Point(3, 3), quantity=1)
        wb = self._workbook(self._download(format='xlsx'))
        _, obs = self._rows(wb['observations'])
        _, sessions = self._rows(wb['sessions'])
        self.assertEqual([r['session_id'] for r in obs], [good.id])
        self.assertEqual([r['session_id'] for r in sessions], [good.id])
        wb_all = self._workbook(self._download(format='xlsx', include_all=1))
        self.assertEqual(len(self._rows(wb_all['observations'])[1]), 3)

    def test_responses_sheet_keeps_the_per_session_layout(self):
        """
        GIVEN a session with a choice answer
        WHEN the responses sheet is read
        THEN one row per session holds the choice NAME under the question, and session_start_utc
             replaces the legacy datetime column
        """
        s = self._session()
        Answer.objects.create(survey_session=s, question=self.q_weather, selected_choices=['rain'])
        wb = self._workbook(self._download(format='xlsx'))
        header, rows = self._rows(wb['responses'])
        self.assertIn('session_start_utc', header)
        self.assertNotIn('datetime', header)
        self.assertEqual(rows[0]['Weather'], 'Rainy')
        self.assertEqual(rows[0]['session_id'], s.id)

    def test_sessions_sheet_columns(self):
        """
        GIVEN a completed session with tags and a note
        WHEN the sessions sheet is read
        THEN it has the documented columns and the end time, tags and notes
        """
        s = self._session(tags=['field', 'verified'], notes='called back')
        Answer.objects.create(survey_session=s, question=self.q_weather, selected_choices=['sun'])
        s.mark_completed()
        wb = self._workbook(self._download(format='xlsx'))
        header, rows = self._rows(wb['sessions'])
        self.assertEqual(header, list(_export.SESSION_COLUMNS))
        self.assertIsNotNone(rows[0]['session_end_utc'])
        self.assertEqual(rows[0]['tags'], 'field; verified')
        self.assertEqual(rows[0]['notes'], 'called back')
        self.assertEqual(rows[0]['opened_by_kind'], 'external')

    def test_temp_directory_removed_when_response_closes(self):
        """
        GIVEN an xlsx export
        WHEN the response is fully consumed and closed
        THEN the temporary directory it was written to no longer exists
        """
        import os, tempfile as _tf
        self._session()
        made = []
        real = _tf.TemporaryDirectory   # the patch below replaces the module attribute itself

        def make(*args, **kwargs):
            d = real(*args, **kwargs)
            made.append(d.name)
            return d

        with patch('survey.views.tempfile.TemporaryDirectory', side_effect=make):
            response = self._download(format='xlsx')
            self.assertEqual(len(made), 1)
            self.assertTrue(os.path.isdir(made[0]))
            b''.join(response.streaming_content)
            # Closing the test client's response fires request_finished, which
            # would close the test transaction's connection; the client itself
            # detaches close_old_connections around that signal, so do the same.
            from django.core.signals import request_finished
            from django.db import close_old_connections
            request_finished.disconnect(close_old_connections)
            try:
                response.close()
            finally:
                request_finished.connect(close_old_connections)
        self.assertFalse(os.path.exists(made[0]))

    # -- completed_only -----------------------------------------------------

    def test_completed_only_matches_the_overview(self):
        """
        GIVEN two sections and 5 clean sessions of which 3 answered the last section
        WHEN the export runs with completed_only=1
        THEN the sessions sheet has 3 rows and the Responses overview counts 3 completed
        """
        last = SurveySection.objects.create(survey_header=self.survey, name='Wrap', code='S2')
        self.section.next_section = last
        self.section.save()
        q_last = Question.objects.create(survey_section=last, name='Anything else', code='AE',
                                         input_type='text', order_number=1)
        sessions = [self._session() for _ in range(5)]
        for s in sessions:
            Answer.objects.create(survey_session=s, question=self.q_weather, selected_choices=['sun'])
        for s in sessions[:3]:
            Answer.objects.create(survey_session=s, question=q_last, text='no')
        trashed = self._session(is_deleted=True)
        Answer.objects.create(survey_session=trashed, question=q_last, text='trashed but complete')

        wb = self._workbook(self._download(format='xlsx', completed_only=1))
        _, rows = self._rows(wb['sessions'])
        self.assertEqual(sorted(r['session_id'] for r in rows), sorted(s.id for s in sessions[:3]))
        overview = SurveyAnalyticsService(self.survey).get_overview()
        self.assertEqual(overview['completed_count'], 3)

        legacy = self._download(completed_only=1)
        archive = zipfile.ZipFile(BytesIO(legacy.content))
        csv_text = archive.read('squirrel_count.csv').decode()
        self.assertEqual(csv_text.count('\n') - 1, 3)

    # -- CSV ----------------------------------------------------------------

    def test_csv_archive_has_bom_flat_tables(self):
        """
        GIVEN a session with a point and a choice answer
        WHEN the export runs as csv
        THEN the archive holds observations.csv, responses.csv and sessions.csv, each starting with a
             BOM, and observations.csv has one row with lat/lon
        """
        s = self._session()
        Answer.objects.create(survey_session=s, question=self.q_weather, selected_choices=['sun'])
        self._observe(s, self.q_white, Point(-88.0936, 38.7265), quantity=2)
        response = self._download(format='csv')
        self.assertEqual(response.status_code, 200)
        archive = zipfile.ZipFile(BytesIO(self._body(response)))
        self.assertEqual(sorted(archive.namelist()), ['observations.csv', 'responses.csv', 'sessions.csv'])
        import csv as _csv, io as _io
        for name in archive.namelist():
            raw = archive.read(name)
            self.assertTrue(raw.startswith('﻿'.encode('utf-8')), name)
        obs = list(_csv.DictReader(_io.StringIO(archive.read('observations.csv').decode('utf-8-sig'))))
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]['question'], 'White squirrel')
        self.assertEqual(obs[0]['lat'], '38.7265')
        self.assertEqual(obs[0]['Quantity'], '2.0')
        self.assertEqual(obs[0]['session_start_utc'], '2026-09-22T18:59:30')


class ExportObjectsSheetTest(TestCase):
    """Answers about layer objects get their own sheet in the workbook."""

    def setUp(self):
        self.org = _make_org('ObjSheetOrg')
        self.owner = User.objects.create_user('objsheet', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='obj_sheet', organization=self.org, created_by=self.owner, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.layer = _objects_layer(self.survey, name='Sites', key_field='zone_id', label_field='name')
        self.q = Question.objects.create(
            survey_section=self.section, code='OB1', name='Objects', input_type='layer_objects',
            layer=self.layer, order_number=1,
        )
        self.thumbs = Question.objects.create(
            survey_section=self.section, code='OB2', name='Build?', input_type='thumbs',
            parent_question_id=self.q, order_number=1,
        )
        self.thumbs.choices = self.thumbs.thumbs_choices()
        self.thumbs.save()
        self.client.login(username='objsheet', password='pass')

    def test_objects_sheet_present(self):
        """
        GIVEN a layer_objects question with a thumbs sub-question and one vote on object 1
        WHEN the survey is exported as xlsx
        THEN a sheet objects_OB1 holds one row with the object key, title, category and the vote
        """
        import openpyxl
        obj = self.layer.items.get(key='1')
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=session, question=self.thumbs, layer_object=obj, selected_choices=[1])
        response = self.client.get(f'/surveys/{self.survey.uuid}/download?format=xlsx')
        wb = openpyxl.load_workbook(BytesIO(b''.join(response.streaming_content)))
        self.assertEqual(wb.sheetnames, ['observations', 'responses', 'sessions', 'objects_OB1'])
        rows = list(wb['objects_OB1'].iter_rows(values_only=True))
        header = list(rows[0])
        row = dict(zip(header, rows[1]))
        self.assertEqual(row['object_key'], '1')
        self.assertEqual(row['object_title'], obj.title)
        self.assertEqual(row['object_category'], obj.category or None)
        self.assertEqual(row['Build?'], 'up')
        self.assertEqual(row['session_id'], session.id)
        self.assertIn('session_start_utc', header)


class ExportAttachedFilesTest(TestCase):
    """Uploads ride along only on request; without them Excel is a single file."""

    JPEG = b'\xff\xd8\xff\xe0' + b'0' * 16

    def setUp(self):
        self.user = User.objects.create_user(username='fexp', password='pass')
        org = Organization.objects.create(name="FExp Org")
        Membership.objects.create(user=self.user, organization=org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="fexp_survey", organization=org, created_by=self.user,
            redirect_url="#", status="published",
        )
        SurveyCollaborator.objects.create(user=self.user, survey=self.survey, role='owner')
        self.section = SurveySection.objects.create(survey_header=self.survey, name="sec1", code="S1")
        self.photo_q = Question.objects.create(
            survey_section=self.section, name="Photos", code="Q_PH", input_type="photo",
        )

    def _collect_one_photo(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        section_url = f'/surveys/{self.survey.uuid}/sec1/'
        self.client.get(section_url)
        response = self.client.post(f'/surveys/{self.survey.uuid}/upload/', {
            'question': 'Q_PH',
            'file': SimpleUploadedFile('shot.jpg', self.JPEG, content_type='image/jpeg'),
        })
        token = response.json()['token']
        self.client.post(section_url, {'Q_PH': [token]})
        self.client.login(username='fexp', password='pass')
        return SurveySession.objects.get(survey=self.survey)

    def test_excel_alone_is_a_single_file_naming_the_path(self):
        """
        GIVEN a survey with one photo answer
        WHEN it is exported as xlsx without files
        THEN the response is a single workbook whose Photos cell holds files/<sid>/Q_PH__shot.jpg
        """
        import openpyxl
        session = self._collect_one_photo()
        response = self.client.get(f'/surveys/{self.survey.uuid}/download?format=xlsx')
        self.assertEqual(response['Content-Type'], _export.CONTENT_TYPES['xlsx'])
        wb = openpyxl.load_workbook(BytesIO(b''.join(response.streaming_content)))
        rows = list(wb['responses'].iter_rows(values_only=True))
        row = dict(zip(rows[0], rows[1]))
        self.assertEqual(row['Photos'], f'files/{session.id}/Q_PH__shot.jpg')

    def test_excel_with_files_is_a_zip(self):
        """
        GIVEN the same survey
        WHEN it is exported as xlsx with files=1
        THEN the response is a ZIP with fexp_survey.xlsx at the root and the photo under files/
        """
        session = self._collect_one_photo()
        response = self.client.get(f'/surveys/{self.survey.uuid}/download?format=xlsx&files=1')
        self.assertEqual(response['Content-Type'], 'application/zip')
        archive = zipfile.ZipFile(BytesIO(b''.join(response.streaming_content)))
        names = archive.namelist()
        self.assertIn('fexp_survey.xlsx', names)
        self.assertIn(f'files/{session.id}/Q_PH__shot.jpg', names)
        self.assertEqual(archive.read(f'files/{session.id}/Q_PH__shot.jpg'), self.JPEG)

    def test_dialog_offers_files_switch_only_with_file_questions(self):
        """
        GIVEN a survey with a photo question and one without
        WHEN their Responses pages render
        THEN the export dialog's attached-files switch is present for the first and absent for the second
        """
        self.client.login(username='fexp', password='pass')
        with_files = self.client.get(f'/editor/surveys/{self.survey.uuid}/analytics/').content.decode()
        self.assertIn('data-has-files="1"', with_files)
        other = SurveyHeader.objects.create(
            name="plain", organization=self.survey.organization, created_by=self.user, status="published",
        )
        SurveyCollaborator.objects.create(user=self.user, survey=other, role='owner')
        SurveySection.objects.create(survey_header=other, name="s", code="S1", is_head=True)
        without = self.client.get(f'/editor/surveys/{other.uuid}/analytics/').content.decode()
        self.assertIn('data-has-files="0"', without)


@unittest.skipUnless(_export.OGR_AVAILABLE, 'ogr2ogr not installed on this host')
class ExportOgrFormatsTest(TestCase):
    """GeoPackage, Shapefile and KML through ogr2ogr."""

    def setUp(self):
        self.org = _make_org('OgrOrg')
        self.user = User.objects.create_user('ogrowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='ogr_survey', organization=self.org, created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.q_sight = Question.objects.create(
            survey_section=self.section, name='Sightings', code='SG', input_type='point', order_number=1,
        )
        self.q_qty = Question.objects.create(
            survey_section=self.section, name='Quantity', code='SG_Q', input_type='number',
            parent_question_id=self.q_sight, order_number=1,
        )
        self.q_zone = Question.objects.create(
            survey_section=self.section, name='Zones', code='ZN', input_type='polygon', order_number=2,
        )
        for i in range(3):
            s = SurveySession.objects.create(survey=self.survey)
            parent = Answer.objects.create(survey_session=s, question=self.q_sight, point=Point(-88.09 + i * 0.001, 38.72))
            Answer.objects.create(survey_session=s, question=self.q_qty, parent_answer_id=parent, numeric=i + 1)
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.q_zone,
                              polygon=Polygon(((0, 0), (0, 1), (1, 1), (1, 0), (0, 0))))
        self.client.login(username='ogrowner', password='pass')

    def _download(self, fmt, **params):
        from urllib.parse import urlencode
        params['format'] = fmt
        response = self.client.get(f'/surveys/{self.survey.uuid}/download?' + urlencode(params))
        self.assertEqual(response.status_code, 200)
        return response, b''.join(response.streaming_content)

    def test_geopackage_has_one_layer_per_question(self):
        """
        GIVEN a point question with 3 features and a polygon question with 1
        WHEN the survey is exported as gpkg
        THEN the file has layers Sightings and Zones with those feature counts and the Quantity attribute
        """
        import sqlite3, tempfile, os
        response, body = self._download('gpkg')
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="ogr_survey.gpkg"')
        with tempfile.NamedTemporaryFile(suffix='.gpkg', delete=False) as fh:
            fh.write(body)
        try:
            con = sqlite3.connect(fh.name)
            tables = sorted(r[0] for r in con.execute("SELECT table_name FROM gpkg_contents"))
            self.assertEqual(tables, ['Sightings', 'Zones'])
            self.assertEqual(con.execute('SELECT count(*) FROM "Sightings"').fetchone()[0], 3)
            self.assertEqual(con.execute('SELECT count(*) FROM "Zones"').fetchone()[0], 1)
            quantities = sorted(r[0] for r in con.execute('SELECT "Quantity" FROM "Sightings"'))
            self.assertEqual(quantities, [1, 2, 3])
            con.close()
        finally:
            os.unlink(fh.name)

    def test_shapefile_zip_has_five_files_per_question(self):
        """
        GIVEN the same survey
        WHEN it is exported as shp
        THEN the ZIP holds exactly .shp/.shx/.dbf/.prj/.cpg per question and the .prj names WGS 84
        """
        response, body = self._download('shp')
        self.assertEqual(response['Content-Type'], 'application/zip')
        archive = zipfile.ZipFile(BytesIO(body))
        names = sorted(archive.namelist())
        expected = sorted(f'{q}.{ext}' for q in ('Sightings', 'Zones') for ext in ('shp', 'shx', 'dbf', 'prj', 'cpg'))
        self.assertEqual(names, expected)
        self.assertIn('WGS', archive.read('Sightings.prj').decode())
        self.assertEqual(archive.read('Sightings.cpg').decode().strip(), 'UTF-8')

    def test_kml_has_a_container_per_question(self):
        """
        GIVEN the same survey
        WHEN it is exported as kml
        THEN the file parses as XML and holds a named Document or Folder per question inside a root
             named after the survey
        """
        import xml.etree.ElementTree as ET
        response, body = self._download('kml')
        root = ET.fromstring(body)
        ns = {'k': 'http://www.opengis.net/kml/2.2'}
        names = [n.text for n in root.iter('{http://www.opengis.net/kml/2.2}name')]
        self.assertIn('ogr_survey', names)
        containers = [el for el in root.iter() if el.tag.split('}')[-1] in ('Document', 'Folder')]
        container_names = {el.find('k:name', ns).text for el in containers if el.find('k:name', ns) is not None}
        self.assertTrue({'Sightings', 'Zones'} <= container_names, container_names)
        self.assertEqual(len(list(root.iter('{http://www.opengis.net/kml/2.2}Placemark'))), 4)

    def _add_bow_tie_zone(self):
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.q_zone,
                              polygon=Polygon(((2, 2), (3, 3), (3, 2), (2, 3), (2, 2))))

    def test_kml_repairs_a_self_intersecting_polygon(self):
        """
        GIVEN the polygon question has a valid square and a self-intersecting "bow tie" answer (#277)
        WHEN the survey is exported as kml
        THEN the export succeeds and every Zones placemark carries geometry
        """
        import xml.etree.ElementTree as ET
        self._add_bow_tie_zone()
        _response, body = self._download('kml')
        kml = '{http://www.opengis.net/kml/2.2}'
        root = ET.fromstring(body)
        zones = next(el for el in root.iter() if el.tag in (kml + 'Document', kml + 'Folder')
                     and el.findtext(kml + 'name') == 'Zones')
        placemarks = list(zones.iter(kml + 'Placemark'))
        self.assertEqual(len(placemarks), 2)
        for placemark in placemarks:
            self.assertTrue(any(el.tag in (kml + 'Polygon', kml + 'MultiGeometry') for el in placemark.iter()),
                            ET.tostring(placemark))

    def test_geopackage_keeps_a_self_intersecting_polygon_as_drawn(self):
        """
        GIVEN the same bow-tie answer
        WHEN the survey is exported as gpkg
        THEN the Zones layer holds it unchanged, as one invalid Polygon (only KML repairs geometry)
        """
        import tempfile, os
        from django.contrib.gis.gdal import DataSource
        self._add_bow_tie_zone()
        _response, body = self._download('gpkg')
        with tempfile.NamedTemporaryFile(suffix='.gpkg', delete=False) as fh:
            fh.write(body)
        try:
            geoms = [f.geom.geos for f in DataSource(fh.name)['Zones']]
            self.assertEqual([g.geom_type for g in geoms], ['Polygon', 'Polygon'])
            self.assertEqual(sorted(g.valid for g in geoms), [False, True])
        finally:
            os.unlink(fh.name)

    def test_ogr_failure_is_loud(self):
        """
        GIVEN ogr2ogr exits non-zero
        WHEN a GeoPackage export is requested
        THEN the request fails with ExportFailed carrying the tool's stderr, and no file is returned
        """
        import subprocess as _sp
        fake = _sp.CompletedProcess(args=['ogr2ogr'], returncode=1, stdout='', stderr='ERROR 1: boom')
        with patch('survey.export.subprocess.run', return_value=fake):
            with self.assertRaises(_export.ExportFailed) as ctx:
                self.client.get(f'/surveys/{self.survey.uuid}/download?format=gpkg')
        self.assertIn('ERROR 1: boom', str(ctx.exception))

    def test_kml_with_files_is_a_zip_with_the_kml_at_root(self):
        """
        GIVEN the same survey
        WHEN it is exported as kml with files=1
        THEN the response is a ZIP with ogr_survey.kml at the root
        """
        response, body = self._download('kml', files=1)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertIn('ogr_survey.kml', zipfile.ZipFile(BytesIO(body)).namelist())


class SpraycanReadSurfacesTest(TestCase):
    """Specs spraycan-density-views / responses-export-formats / survey-serialization."""

    def setUp(self):
        self.org = _make_org('Spray Read Org')
        self.user = User.objects.create_user('sprayreader', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='spray_reads', organization=self.org, created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='Heat', code='S1', is_head=True,
        )
        self.spray = Question.objects.create(
            survey_section=self.section, name='Too hot', code='HT', input_type='spraycan',
            order_number=1, color='#d6336c', spray_brush='large',
        )
        self.sub = Question.objects.create(
            survey_section=self.section, name='Why', code='HT_W', input_type='text_line',
            parent_question_id=self.spray, order_number=1,
        )
        self.client.login(username='sprayreader', password='pass')

    def _cloud(self, n, x0=13.3, y0=52.5, session=None, why=None):
        from django.contrib.gis.geos import MultiPoint
        session = session or SurveySession.objects.create(survey=self.survey)
        geom = MultiPoint(*[Point(x0 + i * 0.0001, y0 + (i % 5) * 0.0001) for i in range(n)], srid=4326)
        answer = Answer.objects.create(survey_session=session, question=self.spray, multipoint=geom)
        if why:
            Answer.objects.create(survey_session=session, question=self.sub, parent_answer_id=answer, text=why)
        return answer

    @staticmethod
    def _body(response):
        if hasattr(response, 'streaming_content'):
            return b''.join(response.streaming_content)
        return response.content

    def test_legacy_geojson_has_one_multipoint_feature_per_cloud_with_dot_count(self):
        """
        GIVEN two sessions that sprayed clouds
        WHEN the legacy ZIP is downloaded
        THEN the question's GeoJSON holds two MultiPoint features with dot_count and the sub-answer
        """
        self._cloud(40, why='no shade')
        self._cloud(7)
        response = self.client.get(f'/surveys/{self.survey.uuid}/download')
        self.assertEqual(response.status_code, 200)
        archive = zipfile.ZipFile(BytesIO(self._body(response)))
        name = next(n for n in archive.namelist() if n.endswith('.geojson'))
        fc = json.loads(archive.read(name))
        self.assertEqual([f['geometry']['type'] for f in fc['features']], ['MultiPoint', 'MultiPoint'])
        self.assertEqual(sorted(f['properties']['dot_count'] for f in fc['features']), [7, 40])
        self.assertEqual(sorted(f['properties']['Why'] for f in fc['features']), ['', 'no shade'])

    def test_observations_row_has_centroid_wkt_and_trailing_dot_count(self):
        """
        GIVEN a 40-dot cloud
        WHEN the xlsx export is read
        THEN its observations row has geometry_type MultiPoint, centroid lat/lon,
             a MULTIPOINT wkt, and dot_count 40 + area_m2 as the LAST two columns
        """
        import openpyxl
        self._cloud(40)
        response = self.client.get(f'/surveys/{self.survey.uuid}/download?format=xlsx')
        wb = openpyxl.load_workbook(BytesIO(self._body(response)))
        rows = list(wb['observations'].iter_rows(values_only=True))
        header = list(rows[0])
        row = dict(zip(header, rows[1]))
        self.assertEqual(header[-2:], ['dot_count', 'area_m2'])
        self.assertEqual(row['geometry_type'], 'MultiPoint')
        self.assertEqual(row['dot_count'], 40)
        self.assertGreater(row['area_m2'], 0)
        self.assertTrue(row['wkt'].startswith('MULTIPOINT ('))
        self.assertAlmostEqual(row['lon'], 13.3 + 0.0001 * 19.5, places=5)

    def test_no_dot_count_column_without_a_spraycan_question(self):
        """
        GIVEN a survey whose only geo question is a point question
        WHEN the observations columns are built
        THEN no dot_count column is present
        """
        from survey import export
        self.spray.input_type = 'point'
        self.spray.save(update_fields=['input_type'])
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=session, question=self.spray, point=Point(13.3, 52.5))
        bundle = export.collect(self.survey, [(self.survey, '')])
        self.assertNotIn('dot_count', export.observation_columns(bundle))

    def test_ogr_layer_type_is_multipoint(self):
        """
        GIVEN a cloud
        WHEN the OGR layer list is built
        THEN the spraycan layer is declared wkbMultiPoint
        """
        from survey import export
        self._cloud(5)
        bundle = export.collect(self.survey, [(self.survey, '')])
        types = {name: t for name, _, t in export._unique_layer_names(bundle)}
        self.assertEqual(list(types.values()), ['wkbMultiPoint'])

    def test_responses_feature_collection_carries_dots(self):
        """
        GIVEN two clouds of different size
        WHEN the Responses geo feature collection is built
        THEN each is a MultiPoint feature with properties.dots = its dot count
        """
        self._cloud(30)
        self._cloud(3)
        fc = SurveyAnalyticsService(self.survey).get_geo_feature_collection()
        self.assertEqual(sorted(f['properties']['dots'] for f in fc['features']), [3, 30])
        self.assertTrue(all(f['geometry']['type'] == 'MultiPoint' for f in fc['features']))
        self.assertTrue(all(f['properties']['color'] == '#d6336c' for f in fc['features']))

    def test_cell_formats_as_dot_count_and_area(self):
        """
        GIVEN a 12-dot cloud spread over a few hundred square metres
        WHEN the attribute-table cell is formatted
        THEN it reads "12 dots · <area> m²"
        """
        answer = self._cloud(12)
        cell = SurveyAnalyticsService._format_cell(answer)
        self.assertRegex(cell, r'^12 dots · \d+ m²$')

    def test_two_dot_cloud_has_no_area(self):
        """
        GIVEN a two-dot cloud (no hull)
        WHEN the cell is formatted
        THEN it reads "2 dots" with no area
        """
        answer = self._cloud(2)
        self.assertEqual(SurveyAnalyticsService._format_cell(answer), '2 dots')

    def test_serialization_round_trips_brush_and_cloud(self):
        """
        GIVEN a survey with a spraycan question (brush large) and a 9-dot cloud
        WHEN it is exported to ZIP in full mode and imported back
        THEN the question is spraycan with brush large and the answer holds 9 dots as MULTIPOINT
        """
        from survey.serialization import export_survey_to_zip, import_survey_from_zip
        self._cloud(9)
        buf = BytesIO()
        export_survey_to_zip(self.survey, buf, mode='full')
        buf.seek(0)
        with zipfile.ZipFile(buf) as z:
            data = json.loads(z.read('survey.json'))
        q = data['survey']['sections'][0]['questions'][0]
        self.assertEqual(q['input_type'], 'spraycan')
        self.assertEqual(q['spray_brush'], 'large')
        buf.seek(0)
        imported, warnings = import_survey_from_zip(buf, organization=self.org)
        new_q = Question.objects.get(survey_section__survey_header=imported, input_type='spraycan')
        self.assertEqual(new_q.spray_brush, 'large')
        new_a = Answer.objects.get(question=new_q)
        self.assertEqual(len(new_a.multipoint), 9)

    def test_import_defaults_unknown_brush_with_a_report_line(self):
        """
        GIVEN an archive whose spraycan question carries spray_brush "huge"
        WHEN it is imported
        THEN the question gets medium and the report names it
        """
        from survey.serialization import export_survey_to_zip, import_survey_from_zip
        buf = BytesIO()
        export_survey_to_zip(self.survey, buf, mode='structure')
        buf.seek(0)
        with zipfile.ZipFile(buf) as z:
            data = json.loads(z.read('survey.json'))
            others = {n: z.read(n) for n in z.namelist() if n != 'survey.json'}
        data['survey']['sections'][0]['questions'][0]['spray_brush'] = 'huge'
        out = BytesIO()
        with zipfile.ZipFile(out, 'w') as z:
            z.writestr('survey.json', json.dumps(data))
            for n, b in others.items():
                z.writestr(n, b)
        out.seek(0)
        imported, warnings = import_survey_from_zip(out, organization=self.org)
        new_q = Question.objects.get(survey_section__survey_header=imported, input_type='spraycan')
        self.assertEqual(new_q.spray_brush, 'medium')
        self.assertTrue(any('spray_brush' in w for w in warnings), warnings)
