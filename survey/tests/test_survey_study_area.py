"""Tests for the `survey-study-area` capability (spec in the unarchived change map-layers-study-area:
openspec/changes/map-layers-study-area/specs/survey-study-area/spec.md).

A survey has at most one study area; it is not a layer. The respondent map opens on it, a fog greys
the outside, and an optional rule refuses map answers outside it.
"""
import json
import math
import zipfile
from io import BytesIO

from django.contrib.auth.models import User
from django.test import TestCase

from survey.models import Organization, StudyArea, SurveyHeader, SurveySection
from survey.services import study_area as svc_area
from survey.services.context import Actor
from survey.services.errors import ValidationFailed

# A square of about 1.1 × 1.1 km in Midtown, Atlanta.
SQUARE = {'type': 'Polygon', 'coordinates': [[
    [-84.39, 33.78], [-84.38, 33.78], [-84.38, 33.79], [-84.39, 33.79], [-84.39, 33.78]]]}


def _circle(n, lng=-84.385, lat=33.785, r=0.01):
    ring = [[lng + r * math.cos(2 * math.pi * i / n), lat + r * math.sin(2 * math.pi * i / n)] for i in range(n)]
    return {'type': 'Polygon', 'coordinates': [ring + [ring[0]]]}


class _Fixture(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('area_owner', password='pw')
        self.actor = Actor(user=self.owner)
        self.org = Organization.objects.create(name='Area Org')
        self.survey = SurveyHeader.objects.create(name='area_survey', organization=self.org, redirect_url='#',
                                                  available_languages=['en', 'de'])
        self.section = SurveySection.objects.create(survey_header=self.survey, name='s1', title='Map', code='S1',
                                                    is_head=True, layout='map')


class StudyAreaServiceTest(_Fixture):
    """Spec survey-study-area / Requirement: A survey has at most one study area, and it is not a layer."""

    def test_set_and_replace(self):
        """
        GIVEN a survey without a study area
        WHEN a square is set, then a circle replaces it
        THEN there is exactly one study area, a MultiPolygon, with fog on and answers outside allowed
        """
        svc_area.set_area(self.actor, self.survey, SQUARE, source='draw')
        svc_area.set_area(self.actor, self.survey, _circle(40), source='draw')
        area = StudyArea.objects.get(survey=self.survey)
        self.assertEqual(area.geometry.geom_type, 'MultiPolygon')
        self.assertEqual((area.fog, area.refuse_outside), (True, False))
        self.assertEqual(StudyArea.objects.count(), 1)

    def test_not_a_polygon_is_refused(self):
        """
        GIVEN a client sends a LineString as the study area
        THEN the request is refused with a validation error and nothing changes
        """
        with self.assertRaises(ValidationFailed) as ctx:
            svc_area.set_area(self.actor, self.survey, {'type': 'LineString', 'coordinates': [[0, 0], [1, 1]]})
        self.assertIn('geometry', ctx.exception.fields)
        self.assertFalse(StudyArea.objects.exists())

    def test_projected_coordinates_are_refused(self):
        """
        GIVEN a polygon in State Plane feet (coordinates far outside longitude/latitude)
        THEN it is refused with a message about the coordinate system
        """
        big = {'type': 'Polygon', 'coordinates': [[[2200000, 1300000], [2201000, 1300000], [2201000, 1301000],
                                                   [2200000, 1300000]]]}
        with self.assertRaises(ValidationFailed) as ctx:
            svc_area.set_area(self.actor, self.survey, big)
        self.assertIn('WGS 84', ctx.exception.message)

    def test_a_bow_tie_is_made_valid(self):
        """
        GIVEN a self-intersecting polygon (a bow tie)
        WHEN it is set
        THEN the stored area is valid and keeps both halves
        """
        bow = {'type': 'Polygon', 'coordinates': [[[-84.39, 33.78], [-84.38, 33.79], [-84.38, 33.78],
                                                   [-84.39, 33.79], [-84.39, 33.78]]]}
        area = svc_area.set_area(self.actor, self.survey, bow)
        self.assertTrue(area.geometry.valid)
        self.assertEqual(len(area.geometry), 2)

    def test_a_large_boundary_is_simplified(self):
        """
        GIVEN an OpenStreetMap-like boundary of 6,000 vertices
        WHEN it is set
        THEN at most 2,000 vertices are stored and the shape keeps its size
        """
        area = svc_area.set_area(self.actor, self.survey, _circle(6000), source='place', place_name='Midtown')
        self.assertLessEqual(svc_area.vertex_count(area.geometry), svc_area.MAX_VERTICES)
        self.assertAlmostEqual(area.geometry.area, math.pi * 0.01 ** 2, delta=0.00001)

    def test_draft_copy_writes_the_canonical_area(self):
        """
        GIVEN a published survey with unpublished changes
        WHEN the study area is set through the draft copy
        THEN the canonical survey holds it and the draft copy reads it
        """
        from survey.versioning import clone_survey_for_draft
        self.survey.status = 'published'
        self.survey.save()
        draft = clone_survey_for_draft(self.survey)
        svc_area.set_area(self.actor, draft, SQUARE)
        self.assertTrue(StudyArea.objects.filter(survey=self.survey).exists())
        self.assertFalse(StudyArea.objects.filter(survey=draft).exists())
        self.assertIsNotNone(svc_area.get(draft))

    def test_message_is_plain_text_per_language(self):
        """
        GIVEN a refusal message with markup, set as a bare string
        THEN it is stored under the survey's primary language without tags
        """
        svc_area.set_area(self.actor, self.survey, SQUARE, refuse_outside=True,
                          message='<b>Only</b> inside Midtown, please.')
        area = svc_area.get(self.survey)
        self.assertEqual(area.message, {'en': 'Only inside Midtown, please.'})
        self.assertEqual(svc_area.message_for(area, 'de', ['en']), 'Only inside Midtown, please.')

    def test_describe_reports_size(self):
        """
        GIVEN the 0.01° square at Atlanta's latitude
        THEN describe() reports about 1.03 km² and the bounds
        """
        info = svc_area.describe(svc_area.set_area(self.actor, self.survey, SQUARE))
        self.assertAlmostEqual(info['area_km2'], 1.03, delta=0.05)
        self.assertEqual([round(v, 2) for v in info['bounds']], [-84.39, 33.78, -84.38, 33.79])

    def test_clear(self):
        """
        GIVEN a survey with a study area
        WHEN it is cleared
        THEN the survey has none
        """
        svc_area.set_area(self.actor, self.survey, SQUARE)
        self.assertTrue(svc_area.clear(self.actor, self.survey))
        self.assertIsNone(svc_area.get(self.survey))


class StudyAreaArchiveTest(_Fixture):
    """Spec survey-serialization / Requirement: The study area rides the archive."""

    def _export(self):
        from survey.serialization import export_survey_to_zip
        buf = BytesIO()
        export_survey_to_zip(self.survey, buf, 'structure')
        buf.seek(0)
        return buf

    def test_study_area_round_trips(self):
        """
        GIVEN a survey with a study area (fog on, refusal on, a German message)
        WHEN it is exported and re-imported
        THEN the imported survey has the same polygon, flags and both messages, and no refused count
        """
        from survey.serialization import import_survey_from_zip
        svc_area.set_area(self.actor, self.survey, SQUARE, refuse_outside=True,
                          message={'en': 'Inside only.', 'de': 'Nur innerhalb.'})
        StudyArea.objects.filter(survey=self.survey).update(refused_marks=7)
        buf = self._export()
        self.survey.name = 'area_survey_old'
        self.survey.save()
        imported, warnings = import_survey_from_zip(buf)
        area = StudyArea.objects.get(survey=imported)
        self.assertTrue(area.geometry.equals_exact(StudyArea.objects.get(survey=self.survey).geometry, 1e-9))
        self.assertEqual((area.fog, area.refuse_outside, area.refused_marks), (True, True, 0))
        self.assertEqual(area.message, {'en': 'Inside only.', 'de': 'Nur innerhalb.'})
        self.assertEqual(warnings, [])

    def test_broken_geometry_in_an_archive(self):
        """
        GIVEN an archive whose study_area.geometry is a LineString
        WHEN it is imported
        THEN the survey imports without a study area and the report says why
        """
        from survey.serialization import import_survey_from_zip
        svc_area.set_area(self.actor, self.survey, SQUARE)
        buf = self._export()
        out = BytesIO()
        with zipfile.ZipFile(buf) as src, zipfile.ZipFile(out, 'w') as dst:
            for item in src.namelist():
                if item == 'survey.json':
                    data = json.loads(src.read(item))
                    data['survey']['study_area']['geometry'] = {'type': 'LineString', 'coordinates': [[0, 0], [1, 1]]}
                    data['survey']['name'] = 'area_broken'
                    dst.writestr(item, json.dumps(data))
                else:
                    dst.writestr(item, src.read(item))
        out.seek(0)
        imported, warnings = import_survey_from_zip(out)
        self.assertFalse(StudyArea.objects.filter(survey=imported).exists())
        self.assertTrue(any('study area' in w for w in warnings))


def _feature(code, geometry):
    return json.dumps({'type': 'Feature', 'properties': {'question_id': code}, 'geometry': geometry})


class RefusalOutsideTest(_Fixture):
    """Spec survey-study-area / Requirement: Map answers outside the study area can be refused."""

    def setUp(self):
        super().setUp()
        from survey.models import Question
        self.survey.status = 'published'
        # One language: a multi-language survey opens on the language picker first.
        self.survey.available_languages = ['en']
        self.survey.save()
        self.point_q = Question.objects.create(survey_section=self.section, name='Where?', input_type='point',
                                               order_number=1)
        self.line_q = Question.objects.create(survey_section=self.section, name='Route', input_type='line',
                                              order_number=2)
        self.url = f'/surveys/{self.survey.name}/{self.section.name}/'

    def _post(self, data):
        from survey.models import Answer
        self.client.get(self.url)
        session_id = self.client.session['survey_session_id']
        response = self.client.post(self.url, data)
        return response, Answer.objects.filter(survey_session_id=session_id)

    def test_scripted_point_outside_is_refused_and_the_page_moves_on(self):
        """
        GIVEN refusal on and a section POST with one point inside and one 2 km outside
        WHEN it is submitted
        THEN the inside point is stored, the outside one is not, the response is the normal next
             step and the survey's refused counter is 1
        """
        svc_area.set_area(self.actor, self.survey, SQUARE, refuse_outside=True, message='Inside only.')
        payload = '|'.join([_feature(self.point_q.code, {'type': 'Point', 'coordinates': [-84.385, 33.785]}),
                            _feature(self.point_q.code, {'type': 'Point', 'coordinates': [-84.36, 33.785]})]) + '|'
        response, answers = self._post({self.point_q.code: payload})
        self.assertIn(response.status_code, (200, 302))
        self.assertEqual(answers.filter(question=self.point_q).count(), 1)
        self.assertEqual(StudyArea.objects.get(survey=self.survey).refused_marks, 1)

    def test_line_three_metres_outside_is_accepted(self):
        """
        GIVEN refusal on and a line whose end lies 3 m east of the area's edge
        WHEN it is submitted
        THEN it is stored (the 5 m snapping tolerance), and a line ending 200 m outside is not
        """
        svc_area.set_area(self.actor, self.survey, SQUARE, refuse_outside=True)
        three_m = 3 / (111320 * math.cos(math.radians(33.785)))
        close = {'type': 'LineString', 'coordinates': [[-84.385, 33.785], [-84.38 + three_m, 33.785]]}
        far = {'type': 'LineString', 'coordinates': [[-84.385, 33.786], [-84.378, 33.786]]}
        _response, answers = self._post({self.line_q.code: _feature(self.line_q.code, close) + '|'
                                         + _feature(self.line_q.code, far) + '|'})
        self.assertEqual(answers.filter(question=self.line_q).count(), 1)

    def test_rule_off_keeps_everything(self):
        """
        GIVEN a study area with the refusal rule off
        WHEN a point outside is submitted
        THEN it is stored and nothing is counted
        """
        svc_area.set_area(self.actor, self.survey, SQUARE, refuse_outside=False)
        _response, answers = self._post({self.point_q.code: _feature(
            self.point_q.code, {'type': 'Point', 'coordinates': [-84.30, 33.785]}) + '|'})
        self.assertEqual(answers.filter(question=self.point_q).count(), 1)
        self.assertEqual(StudyArea.objects.get(survey=self.survey).refused_marks, 0)

    def test_respondent_page_carries_fog_rule_and_translated_message(self):
        """
        GIVEN a study area with fog, refusal and an English and a German message
        WHEN the respondent page opens in German
        THEN the page carries the outline URL (not the geometry), fog, the rule and the German message,
             and the outline endpoint serves the area
        """
        svc_area.set_area(self.actor, self.survey, SQUARE, refuse_outside=True,
                          message={'en': 'Inside only.', 'de': 'Nur innerhalb.'})
        html = self.client.get(self.url).content.decode()
        self.assertIn('study-area-data', html)
        self.assertIn('study-area.geojson', html)
        self.assertNotIn('[-84.38, 33.78]', html)   # a ring corner: the outline is not inlined
        geo = self.client.get(f'/surveys/{self.survey.uuid}/study-area.geojson')
        self.assertEqual(geo.status_code, 200)
        self.assertEqual(geo.json()['features'][0]['geometry']['type'], 'MultiPolygon')
        from survey.views import study_area_meta
        from django.utils import translation
        self.survey.available_languages = ['en', 'de']
        self.survey.save()
        with translation.override('de'):
            meta = study_area_meta(self.survey)
        self.assertEqual((meta['fog'], meta['refuse_outside'], meta['message']), (True, True, 'Nur innerhalb.'))

    def test_editor_preview_shows_the_study_area(self):
        """
        GIVEN a survey with a study area and its owner signed in
        WHEN the editor's Live preview of a map section renders
        THEN it carries the same study area metadata as the respondent page (outline URL, fog,
             refusal) — the preview never shows a map the respondent will not see
        """
        from survey.models import Membership
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.client.force_login(self.owner)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        svc_area.set_area(self.actor, self.survey, SQUARE, refuse_outside=True)
        html = self.client.get(f'/editor/surveys/{self.survey.uuid}/preview/{self.section.name}/').content.decode()
        self.assertIn('study-area-data', html)
        self.assertIn('study-area.geojson', html)
        self.assertIn('"refuse_outside": true', html)

    def test_outline_of_a_draft_survey_is_hidden(self):
        """
        GIVEN a draft survey with a study area
        WHEN an anonymous visitor asks for the outline
        THEN the answer is 404, like a layer of a draft
        """
        self.survey.status = 'draft'
        self.survey.save()
        svc_area.set_area(self.actor, self.survey, SQUARE)
        self.assertEqual(self.client.get(f'/surveys/{self.survey.uuid}/study-area.geojson').status_code, 404)

    def test_message_is_in_the_translation_table(self):
        """
        GIVEN refusal on with an English message and German offered
        WHEN the translation table is listed and the German row is written
        THEN the occurrence `survey:study_area_message` exists and the area keeps both messages
        """
        from survey import translation_table as tt
        self.survey.available_languages = ['en', 'de']
        self.survey.save()
        svc_area.set_area(self.actor, self.survey, SQUARE, refuse_outside=True, message='Inside only.')
        keys = [o.key for o in tt.occurrences(self.survey, 'de')]
        self.assertIn('survey:study_area_message', keys)
        tt.apply(self.actor, self.survey, 'de', {'survey:study_area_message': 'Nur innerhalb.'})
        self.assertEqual(svc_area.get(self.survey).message, {'en': 'Inside only.', 'de': 'Nur innerhalb.'})


class OutlineElsewhereTest(_Fixture):
    """Spec survey-study-area / Requirement: The study area outline shows on Responses and Reports maps."""

    def setUp(self):
        super().setUp()
        from survey.models import Question
        from reports.models import Report, ReportBlock
        self.point_q = Question.objects.create(survey_section=self.section, name='Where?', input_type='point',
                                               order_number=1, code='SAQ1')
        self.report = Report.objects.create(survey=self.survey, slug='sa-report')
        self.block = ReportBlock.objects.create(report=self.report, block_type='map', question=self.point_q, order=0)

    def _payload(self):
        from reports.render import ReportService
        self.block.refresh_from_db()
        return ReportService(self.report)._map_payload(self.block)

    def test_responses_map_lists_the_outline(self):
        """
        GIVEN a survey with a study area
        WHEN the Responses map metadata is built
        THEN its first reference entry is "Study area", an outline with no fill, from the gated endpoint
        """
        from survey.analytics_views import _map_layers_with_object_stats
        self.assertEqual(_map_layers_with_object_stats(self.survey), [])
        svc_area.set_area(self.actor, self.survey, SQUARE)
        first = _map_layers_with_object_stats(self.survey)[0]
        self.assertEqual((first['id'], first['name'], first['style']['fill_opacity']), ('study_area', 'Study area', 0))
        self.assertIn('study-area.geojson', first['url'])

    def test_report_map_block_draws_the_outline_and_can_switch_it_off(self):
        """
        GIVEN a report map block whose question belongs to a survey with a study area
        WHEN the payload is built, then again after the author switches the outline off
        THEN the first payload carries the outline and the frame is untouched; the second has none
             and the config stores `study_area: false`
        """
        from reports import story
        self.assertNotIn('study_area', self._payload())
        svc_area.set_area(self.actor, self.survey, SQUARE)
        payload = self._payload()
        self.assertEqual(payload['study_area']['type'], 'MultiPolygon')
        self.assertNotIn('frame', payload)
        self.block.config = story.clean_config('map', {**(self.block.config or {}), 'study_area': False})
        self.block.save()
        self.assertNotIn('study_area', self._payload())
        self.assertIs(self.block.config['study_area'], False)
        self.assertNotIn('study_area', story.clean_config('map', {'study_area': True}))

    def test_pdf_image_paints_the_outline(self):
        """
        GIVEN a map payload with one mark and the study area outline
        WHEN the PDF image is drawn without a basemap
        THEN the image has the outline's indigo pixels
        """
        from reports.pdf import map_image
        svc_area.set_area(self.actor, self.survey, SQUARE)
        payload = {'data_type': 'marks', 'display': 'marks', 'color': '#e11d48', 'basemap': 'streets',
                   'frame': [-84.392, 33.778, -84.378, 33.792],
                   'marks': {'type': 'FeatureCollection', 'features': [
                       {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [-84.385, 33.785]}}]},
                   'study_area': json.loads(svc_area.get(self.survey).geometry.geojson)}
        from django.test import override_settings
        with override_settings(MAPBOX_ACCESS_TOKEN='', MAPBOX_SERVER_TOKEN=''):
            image = map_image(payload, self.survey).convert('RGB')
        colours = set(image.getdata())
        self.assertTrue(any(abs(r - 79) < 25 and abs(g - 70) < 25 and abs(b - 229) < 25 for r, g, b in colours))


class PlaceLookupTest(_Fixture):
    """Spec survey-study-area / Requirement: The study area is set from a place name and edited on the map."""

    def setUp(self):
        super().setUp()
        from django.core.cache import cache
        cache.clear()
        from survey.models import Membership
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.client.force_login(self.owner)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.base = f'/editor/surveys/{self.survey.uuid}/study-area/'

    def _nominatim(self, results, status=200):
        from unittest import mock
        response = mock.Mock(status_code=status)
        response.json.return_value = results
        return mock.patch('survey.study_area_lookup.requests.get', return_value=response)

    def test_neighbourhood_boundary(self):
        """
        GIVEN Nominatim answers "Midtown, Atlanta" with a polygon
        WHEN the creator searches, picks it and saves the outline
        THEN the candidate is a polygon and the study area has source `place` and the place name
        """
        raw = [{'osm_type': 'relation', 'osm_id': 123, 'display_name': 'Midtown, Atlanta', 'type': 'neighbourhood',
                'boundingbox': ['33.78', '33.79', '-84.39', '-84.38'], 'lat': '33.785', 'lon': '-84.385',
                'geojson': SQUARE}]
        with self._nominatim(raw):
            found = self.client.get(self.base + 'lookup/', {'q': 'Midtown, Atlanta'}).json()['candidates']
        self.assertEqual((found[0]['osm_ref'], found[0]['kind']), ('R123', 'polygon'))
        outline = self.client.get(self.base + 'candidate/', {'osm_ref': 'R123'}).json()
        saved = self.client.post(self.base + 'save/', {'geometry': json.dumps(outline['geometry']), 'source': 'place',
                                                       'place_name': 'Midtown, Atlanta', 'osm_ref': 'R123'})
        self.assertEqual(saved.status_code, 200, saved.content)
        area = svc_area.get(self.survey)
        self.assertEqual((area.source, area.place_name, area.osm_ref), ('place', 'Midtown, Atlanta', 'R123'))

    def test_street_becomes_a_corridor_and_its_width_changes(self):
        """
        GIVEN Nominatim answers a street as a LineString 1 km long
        WHEN the creator picks it at 100 m, then at 50 m
        THEN both are polygons, the 50 m corridor is about half as wide, and nothing is saved
        """
        line = {'type': 'LineString', 'coordinates': [[-84.39, 33.785], [-84.38, 33.785]]}
        raw = [{'osm_type': 'way', 'osm_id': 77, 'display_name': 'North Highland Avenue', 'type': 'secondary',
                'boundingbox': ['33.785', '33.785', '-84.39', '-84.38'], 'lat': '33.785', 'lon': '-84.385',
                'geojson': line}]
        with self._nominatim(raw):
            found = self.client.get(self.base + 'lookup/', {'q': 'North Highland Avenue'}).json()['candidates']
        self.assertEqual(found[0]['kind'], 'line')
        wide = self.client.get(self.base + 'candidate/', {'osm_ref': 'W77', 'width': 100}).json()['geometry']
        narrow = self.client.get(self.base + 'candidate/', {'osm_ref': 'W77', 'width': 50}).json()['geometry']
        self.assertEqual((wide['type'], narrow['type']), ('Polygon', 'Polygon'))
        height = lambda g: max(c[1] for c in g['coordinates'][0]) - min(c[1] for c in g['coordinates'][0])
        self.assertAlmostEqual(height(narrow) / height(wide), 0.5, delta=0.05)
        self.assertIsNone(svc_area.get(self.survey))

    def test_point_only_place_starts_as_a_rectangle(self):
        """
        GIVEN Nominatim knows "Elm Park estate" only as a point with a tiny bounding box
        WHEN the creator picks it
        THEN the candidate is a point and its outline a 500 × 500 m square around it
        """
        raw = [{'osm_type': 'node', 'osm_id': 5, 'display_name': 'Elm Park estate', 'type': 'place',
                'boundingbox': ['33.7850', '33.7851', '-84.3851', '-84.3850'], 'lat': '33.785', 'lon': '-84.385',
                'geojson': {'type': 'Point', 'coordinates': [-84.385, 33.785]}}]
        with self._nominatim(raw):
            found = self.client.get(self.base + 'lookup/', {'q': 'Elm Park estate'}).json()['candidates']
        self.assertEqual(found[0]['kind'], 'point')
        square = self.client.get(self.base + 'candidate/', {'osm_ref': 'N5'}).json()['geometry']
        lats = [c[1] for c in square['coordinates'][0]]
        self.assertAlmostEqual((max(lats) - min(lats)) * 111320, 500, delta=5)

    def test_service_down(self):
        """
        GIVEN Nominatim does not answer
        WHEN the creator searches
        THEN the answer is 503 saying OpenStreetMap could not be reached, and nothing is saved
        """
        import requests
        from unittest import mock
        with mock.patch('survey.study_area_lookup.requests.get', side_effect=requests.ConnectionError()):
            response = self.client.get(self.base + 'lookup/', {'q': 'Anywhere'})
        self.assertEqual(response.status_code, 503)
        self.assertIn('OpenStreetMap', response.json()['error'])
        self.assertIsNone(svc_area.get(self.survey))

    def test_upload_a_projected_boundary(self):
        """
        GIVEN a boundary GeoJSON in NAD83 / Georgia West (US feet)
        WHEN it is uploaded into the study area editor
        THEN the outline comes back in longitude/latitude around Atlanta
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        # EPSG:2240, about 33.78 N 84.39 W.
        x0, y0 = 2228000, 1376000
        gj = {'type': 'FeatureCollection', 'crs': {'type': 'name', 'properties': {'name': 'urn:ogc:def:crs:EPSG::2240'}},
              'features': [{'type': 'Feature', 'properties': {}, 'geometry': {'type': 'Polygon', 'coordinates': [[
                  [x0, y0], [x0 + 3000, y0], [x0 + 3000, y0 + 3000], [x0, y0 + 3000], [x0, y0]]]}}]}
        f = SimpleUploadedFile('boundary.geojson', json.dumps(gj).encode(), content_type='application/geo+json')
        response = self.client.post(self.base + 'upload/', {'file': f})
        self.assertEqual(response.status_code, 200, response.content)
        geometry = response.json()['geometry']
        ring = geometry['coordinates'][0][0] if geometry['type'] == 'MultiPolygon' else geometry['coordinates'][0]
        lng, lat = ring[0]
        self.assertAlmostEqual(lat, 33.78, delta=0.1)
        self.assertAlmostEqual(lng, -84.39, delta=0.1)
