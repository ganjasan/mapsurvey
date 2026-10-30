"""Tests for the `printable-form` capability (openspec/specs/printable-form/spec.md).

Change printable-form (#489, epic #350 item 2): the paper form of a survey — the PDF, the
section map with layers and legend, the form code and alignment marks, the PrintedForm record.
Mapbox is never called: `requests.get` is mocked wherever a basemap is fetched.
"""
import io
import json
from unittest import mock

import requests as requests_lib
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.test import TestCase, override_settings
from PIL import Image

from django.contrib.auth.models import User
from django.urls import reverse

from survey.models import (
    Membership, Organization, PrintedForm, Question, QuestionGroup, SurveyHeader, SurveyMapLayer, SurveySection,
    TrackedLink,
)
from survey.print import static_map
from survey.print.static_map import FRAME_H, FRAME_W, SCALE, FrameSpec


def _png(width, height, color=(200, 220, 240)):
    buf = io.BytesIO()
    Image.new('RGB', (width, height), color).save(buf, format='PNG')
    return buf.getvalue()


def _response(status=200, content=b''):
    response = mock.Mock()
    response.status_code = status
    response.content = content
    return response


def _fc(*features):
    return json.dumps({'type': 'FeatureCollection', 'features': list(features)})


def _feature(geometry, **props):
    return {'type': 'Feature', 'geometry': geometry, 'properties': props}


class _MapFixture(TestCase):
    def setUp(self):
        cache.clear()
        org = Organization.objects.create(name='Print Org')
        self.survey = SurveyHeader.objects.create(name='print_survey', organization=org, redirect_url='#')
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='map', title='Map', code='S1', is_head=True)


class FrameResolutionTest(_MapFixture):

    def test_section_position_wins(self):
        """
        GIVEN a section with its own start position and zoom
        WHEN the frame is resolved
        THEN the frame is centred there at that zoom with the survey's basemap
        """
        self.survey.start_map_postion = Point(10.0, 50.0)
        self.survey.start_map_zoom = 10
        self.survey.default_basemap = 'topo'
        self.survey.save()
        self.section.start_map_postion = Point(13.4, 52.5)
        self.section.start_map_zoom = 14
        self.section.save()
        spec = static_map.resolve_frame(self.section, self.survey)
        self.assertEqual((spec.lat, spec.lng, spec.zoom, spec.basemap), (52.5, 13.4, 14, 'topo'))
        self.assertEqual(spec.note, '')

    def test_survey_position_then_layers_then_world(self):
        """
        GIVEN a section without a position
        WHEN the survey has one / only a reference layer / nothing
        THEN the frame falls back in that order and the world frame is noted
        """
        self.survey.start_map_postion = Point(10.0, 50.0)
        self.survey.save()
        self.assertEqual(static_map.resolve_frame(self.section, self.survey).lat, 50.0)
        self.survey.start_map_postion = None
        self.survey.save()
        SurveyMapLayer.objects.create(
            survey=self.survey, name='Parks',
            geojson=_fc(_feature({'type': 'Point', 'coordinates': [13.0, 52.0]}),
                        _feature({'type': 'Point', 'coordinates': [13.2, 52.2]})))
        spec = static_map.resolve_frame(self.section, self.survey)
        self.assertAlmostEqual(spec.lat, 52.1, places=3)
        self.assertEqual(spec.note, 'layers')
        SurveyMapLayer.objects.filter(survey=self.survey).delete()
        spec = static_map.resolve_frame(self.section, self.survey)
        self.assertEqual((spec.zoom, spec.note), (static_map.WORLD_ZOOM, 'world'))

    def test_section_basemap_override_names_the_outdoors_style(self):
        """
        GIVEN a section with override_basemap 'topo' and a token
        WHEN the basemap is fetched
        THEN the Static Images request names the outdoors style at one zoom lower
        """
        self.section.override_basemap = 'topo'
        self.section.start_map_postion = Point(13.4, 52.5)
        self.section.start_map_zoom = 13
        self.section.save()
        spec = static_map.resolve_frame(self.section, self.survey)
        with override_settings(MAPBOX_ACCESS_TOKEN='tok'), \
                mock.patch('survey.print.static_map.requests.get',
                           return_value=_response(200, _png(FRAME_W * SCALE, FRAME_H * SCALE))) as get:
            self.assertIsNotNone(static_map.fetch_basemap(spec))
        url = get.call_args.args[0]
        self.assertIn('mapbox/outdoors-v12/static/13.400000,52.500000,12/', url)
        self.assertEqual(get.call_args.kwargs['params']['attribution'], 'false')

    def test_bounds_round_trip(self):
        """
        GIVEN a frame centred on Berlin at zoom 13
        WHEN its bounds are computed and the corners projected back
        THEN the bounds span the frame's pixel size
        """
        spec = FrameSpec(52.5, 13.4, 13, 'streets')
        w, s, e, n = spec.bounds
        self.assertLess(w, 13.4)
        self.assertGreater(e, 13.4)
        self.assertLess(s, 52.5)
        self.assertGreater(n, 52.5)
        x0, y0 = static_map.project(w, n, 13)
        x1, y1 = static_map.project(e, s, 13)
        self.assertAlmostEqual(x1 - x0, FRAME_W, delta=1)
        self.assertAlmostEqual(y1 - y0, FRAME_H, delta=1)


class BasemapFetchTest(_MapFixture):

    def setUp(self):
        super().setUp()
        self.spec = FrameSpec(52.5, 13.4, 13, 'streets')

    def test_no_token_means_no_request(self):
        """
        GIVEN an empty Mapbox token
        WHEN the basemap is fetched
        THEN nothing is requested and None comes back
        """
        with override_settings(MAPBOX_ACCESS_TOKEN=''), \
                mock.patch('survey.print.static_map.requests.get') as get:
            self.assertIsNone(static_map.fetch_basemap(self.spec))
        get.assert_not_called()

    def test_http_error_and_timeout_mean_none(self):
        """
        GIVEN Mapbox answers 500, then times out
        WHEN the basemap is fetched twice
        THEN both calls return None and nothing is cached
        """
        with override_settings(MAPBOX_ACCESS_TOKEN='tok'):
            with mock.patch('survey.print.static_map.requests.get', return_value=_response(500, b'x')):
                self.assertIsNone(static_map.fetch_basemap(self.spec))
            with mock.patch('survey.print.static_map.requests.get', side_effect=requests_lib.Timeout()):
                self.assertIsNone(static_map.fetch_basemap(self.spec))

    def test_second_fetch_is_served_from_cache(self):
        """
        GIVEN a successful fetch
        WHEN the same frame is fetched again within a day
        THEN Mapbox is called once and both results are images
        """
        png = _png(FRAME_W * SCALE, FRAME_H * SCALE)
        with override_settings(MAPBOX_ACCESS_TOKEN='tok'), \
                mock.patch('survey.print.static_map.requests.get', return_value=_response(200, png)) as get:
            first = static_map.fetch_basemap(self.spec)
            second = static_map.fetch_basemap(self.spec)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(first.size, second.size)


class FrameRenderTest(_MapFixture):

    def setUp(self):
        super().setUp()
        self.section.start_map_postion = Point(13.4, 52.5)
        self.section.start_map_zoom = 13
        self.section.save()

    def test_unavailable_basemap_prints_a_grid_with_layers(self):
        """
        GIVEN no token and a point layer east of the frame's centre
        WHEN the frame is rendered
        THEN the basemap is flagged unavailable, the grid is drawn and the point still is
        """
        east = static_map.unproject(*[v + d for v, d in zip(static_map.project(13.4, 52.5, 13), (200, 0))], 13)
        SurveyMapLayer.objects.create(
            survey=self.survey, name='Spot', color='#ff0000',
            geojson=_fc(_feature({'type': 'Point', 'coordinates': [east[0], east[1]]})))
        with override_settings(MAPBOX_ACCESS_TOKEN=''):
            frame = static_map.render_frame(self.section, self.survey)
        self.assertFalse(frame.basemap_ok)
        self.assertEqual(frame.drawn_features, 1)
        image = frame.image
        cx, cy = image.width // 2 + 200 * SCALE, image.height // 2
        r, g, b = image.getpixel((cx, cy))
        self.assertGreater(r, 180)
        self.assertLess(g, 120)
        grid_px = [image.getpixel((x, 3)) for x in range(0, image.width, 1)]
        self.assertTrue(any(p != (255, 255, 255) and p[0] == p[1] == p[2] for p in grid_px))

    def test_polygon_and_point_layers_are_drawn_in_their_colour(self):
        """
        GIVEN a basemap image, a polygon layer around the centre and a point layer east of it
        WHEN the frame is rendered
        THEN both features are drawn, the polygon fill tints the centre and the point is red
        """
        SurveyMapLayer.objects.create(
            survey=self.survey, name='Zone', color='#0000ff', style={'fill_opacity': 0.5},
            geojson=_fc(_feature({'type': 'Polygon', 'coordinates': [[
                [13.39, 52.49], [13.41, 52.49], [13.41, 52.51], [13.39, 52.51], [13.39, 52.49]]]})))
        east = static_map.unproject(*[v + d for v, d in zip(static_map.project(13.4, 52.5, 13), (200, 0))], 13)
        SurveyMapLayer.objects.create(
            survey=self.survey, name='Spot', color='#ff0000',
            geojson=_fc(_feature({'type': 'Point', 'coordinates': [east[0], east[1]]})))
        png = _png(FRAME_W * SCALE, FRAME_H * SCALE, (255, 255, 255))
        with override_settings(MAPBOX_ACCESS_TOKEN='tok'), \
                mock.patch('survey.print.static_map.requests.get', return_value=_response(200, png)):
            frame = static_map.render_frame(self.section, self.survey)
        self.assertTrue(frame.basemap_ok)
        self.assertEqual(frame.drawn_features, 2)
        image = frame.image
        cx, cy = image.width // 2, image.height // 2
        r, g, b = image.getpixel((cx, cy - 40))
        self.assertGreater(b, r)
        pr, pg, pb = image.getpixel((cx + 200 * SCALE, cy))
        self.assertGreater(pr, 180)
        self.assertLess(pb, 120)

    def test_scale_bar_picks_a_round_number(self):
        """
        GIVEN Berlin at zoom 13 and a 180 px budget
        WHEN the scale bar is computed
        THEN it is a round metre value that fits
        """
        px, label = static_map.scale_bar(52.5, 13, max_px=180)
        self.assertLessEqual(px, 180)
        self.assertIn(label, ('1 km', '2 km', '500 m'))


# ── the PDF ────────────────────────────────────────────────────────────────

def _pdf_text(pdf_bytes):
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return reader, '\n'.join(page.extract_text() or '' for page in reader.pages)


class _FormFixture(TestCase):
    """A two-language survey: a map section with a point question (sub-questions,
    a reference layer), a conditional question, a group, a write-in choice, a
    file question and an operator-only section."""

    def setUp(self):
        cache.clear()
        self.org = Organization.objects.create(name='Form Org', slug='form-org')
        self.owner = User.objects.create_user('form_owner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='Park survey', organization=self.org, created_by=self.owner, status='published',
            redirect_url='#', available_languages=['en', 'de'], version_number=1)
        self.s1 = SurveySection.objects.create(
            survey_header=self.survey, name='about', title='About the park', code='S1', is_head=True,
            start_map_postion=Point(13.4, 52.5), start_map_zoom=13)
        self.s2 = SurveySection.objects.create(
            survey_header=self.survey, name='sheet', title='Sheet details', code='S2', audience='operators',
            prev_section=self.s1)
        self.s1.next_section = self.s2
        self.s1.save()
        self.alb = Question.objects.create(
            survey_section=self.s1, code='ALB', name='Albino?', input_type='choice', order_number=1, required=True,
            choices=[{'code': 1, 'name': {'en': 'Yes', 'de': 'Ja'}}, {'code': 0, 'name': {'en': 'No', 'de': 'Nein'}}])
        self.how = Question.objects.create(
            survey_section=self.s1, code='HOW', name='How many?', input_type='number', order_number=2,
            visibility_rule={'question_code': 'ALB', 'choice_codes': [1]})
        self.group = QuestionGroup.objects.create(survey_section=self.s1, order_number=3, title='Your visit')
        self.mood = Question.objects.create(
            survey_section=self.s1, code='MOOD', name='Mood', input_type='choice', order_number=4, group=self.group,
            choices=[{'code': 1, 'name': 'Good'}, {'code': 2, 'name': 'Other', 'other': True}])
        self.where = Question.objects.create(
            survey_section=self.s1, code='WHERE', name='Where do you sit?', input_type='point', order_number=5,
            validation_settings={'max_features': 2})
        Question.objects.create(survey_section=self.s1, code='WHY', name='Why there?', input_type='text',
                                parent_question_id=self.where, order_number=1)
        Question.objects.create(survey_section=self.s1, code='KIND', name='Kind', input_type='choice',
                                parent_question_id=self.where, order_number=2,
                                choices=[{'code': 1, 'name': 'Bench'}, {'code': 2, 'name': 'Grass'}])
        self.photo = Question.objects.create(
            survey_section=self.s1, code='PHOTO', name='A photo', input_type='photo', order_number=6)
        self.sheet = Question.objects.create(
            survey_section=self.s2, code='SHEET', name='Sheet number', input_type='text_line', order_number=1)
        SurveyMapLayer.objects.create(
            survey=self.survey, name='Parks', color='#00aa00',
            geojson=_fc(_feature({'type': 'Point', 'coordinates': [13.4, 52.5]}, name='Big park')))
        self.client.force_login(self.owner)
        s = self.client.session
        s['active_org_id'] = self.org.id
        s.save()
        self.url = reverse('editor_survey_print_form', args=[self.survey.uuid])

    def build(self, language='en', paper='a4', **kw):
        from survey.print.pdf import build_form
        with override_settings(MAPBOX_ACCESS_TOKEN=''):
            return build_form(self.survey, language, paper, user=self.owner, base_url='https://example.test', **kw)


class FormContentTest(_FormFixture):

    def test_order_translations_and_audience(self):
        """
        GIVEN the fixture survey
        WHEN the form is built in German
        THEN the PDF has the section, group and question wording in order, the German options,
             and nothing of the operator-only section
        """
        result = self.build('de')
        reader, text = _pdf_text(result.pdf)
        for needle in ('About the park', 'Albino?', 'Ja', 'Nein', 'Your visit', 'Mood', 'Where do you sit?'):
            self.assertIn(needle, text)
        self.assertLess(text.index('Albino?'), text.index('Mood'))
        self.assertNotIn('Sheet details', text)
        self.assertNotIn('Sheet number', text)

    def test_condition_line_write_in_and_file_note(self):
        """
        GIVEN HOW shown only when ALB = Yes, a write-in option and a photo question
        WHEN the form is built
        THEN the condition, the write-in line and "Online only" are on the form
        """
        _reader, text = _pdf_text(self.build().pdf)
        self.assertIn('Answer only if Albino? = Yes', text)
        self.assertIn('Other:', text)
        self.assertIn('Online only', text)
        self.assertIn('Choose one', text)

    def test_unknown_type_fails_open(self):
        """
        GIVEN a question whose type is not in QUESTION_SHAPES
        WHEN the form is built
        THEN its name is on the form and the build does not raise
        """
        Question.objects.create(survey_section=self.s1, code='ODD', name='Odd one', input_type='hologram',
                                order_number=7)
        _reader, text = _pdf_text(self.build().pdf)
        self.assertIn('Odd one', text)

    def test_map_frame_legend_and_tables(self):
        """
        GIVEN the map section with a point question (max 2) with two sub-questions
        WHEN the form is built
        THEN the legend names the question with letter A and "up to 2", the sub-question table has
             rows A1 and A2 with the sub-questions as columns, and the layout records the frame
        """
        result = self.build()
        _reader, text = _pdf_text(result.pdf)
        self.assertIn('Mark on the map', text)
        self.assertIn('Where do you sit?', text)
        self.assertIn('up to 2', text)
        for cell in ('A1', 'A2', 'Why there?', 'Kind', 'Bench'):
            self.assertIn(cell, text)
        self.assertNotIn('A3', text)
        self.assertEqual(result.map_pages, 1)
        frame = result.form.layout['1']['map']
        self.assertEqual(frame['section_code'], 'S1')
        self.assertEqual(frame['zoom'], 13)
        self.assertIsNone(frame['basemap'])
        self.assertEqual(len(frame['bbox']), 4)
        self.assertGreater(frame['w_mm'], 100)
        # The frame's own text is a raster (it is drawn into the image); the
        # attribution line is PDF text and absent without a basemap.
        self.assertNotIn('Mapbox', text)

    def test_form_section_prints_no_frame(self):
        """
        GIVEN the map section switched to the form layout
        WHEN the form is built
        THEN no frame is recorded (the page still lists its items) and the legend still names the question
        """
        self.s1.layout = 'form'
        self.s1.save()
        result = self.build()
        self.assertEqual(result.map_pages, 0)
        self.assertFalse(any('map' in rec for rec in result.form.layout.values()))
        self.assertIn('question:ALB', result.form.layout['1']['items'])
        _reader, text = _pdf_text(result.pdf)
        self.assertIn('Mark on the map', text)

    def test_marks_code_and_online_qr_on_pages(self):
        """
        GIVEN a form of at least one page
        WHEN the PDF is read back
        THEN every page carries the footer code with its page number, the page count, and
             page 1 the office-use box; the code names the PrintedForm, not the survey
        """
        result = self.build()
        reader, text = _pdf_text(result.pdf)
        code = result.form.code
        for n in range(1, len(reader.pages) + 1):
            page_text = reader.pages[n - 1].extract_text()
            self.assertIn(f'MS-{code}-{n}', page_text)
            self.assertIn(f'Page {n} of {len(reader.pages)}', page_text)
        self.assertIn('Office use', text)
        self.assertNotIn(str(self.survey.uuid), text)
        link = TrackedLink.objects.get(survey=self.survey, utm_source='paper')
        self.assertEqual(result.form.tracked_link, link)
        self.build()
        self.assertEqual(TrackedLink.objects.filter(survey=self.survey, utm_source='paper').count(), 1)

    def test_reprint_reuses_the_form_and_edits_make_a_new_one(self):
        """
        GIVEN the same survey printed twice, then a wording edit, then a new version
        WHEN forms are built
        THEN the first two share a PrintedForm, the edit makes a second, the version a third
        """
        first = self.build()
        second = self.build()
        self.assertEqual(first.form.pk, second.form.pk)
        self.assertEqual(PrintedForm.objects.count(), 1)
        self.alb.name = 'Is it albino?'
        self.alb.save()
        third = self.build()
        self.assertNotEqual(third.form.pk, first.form.pk)
        self.assertEqual(third.form.version_number, 1)
        self.survey.version_number = 2
        self.survey.save()
        fourth = self.build()
        self.assertEqual(fourth.form.version_number, 2)
        self.assertEqual(PrintedForm.objects.count(), 3)

    def test_watermark_on_draft_only(self):
        """
        GIVEN a draft survey, then a closed one
        WHEN forms are built
        THEN only the draft's pages carry the DRAFT text
        """
        self.survey.status = 'draft'
        self.survey.save()
        _r, draft_text = _pdf_text(self.build().pdf)
        self.assertIn('DRAFT', draft_text)
        self.survey.status = 'closed'
        self.survey.save()
        _r, closed_text = _pdf_text(self.build().pdf)
        self.assertNotIn('DRAFT', closed_text)

    def test_letter_paper(self):
        """
        GIVEN US Letter
        WHEN the form is built
        THEN the page is Letter-sized
        """
        reader, _text = _pdf_text(self.build(paper='letter').pdf)
        box = reader.pages[0].mediabox
        self.assertAlmostEqual(float(box.width), 612, delta=1)
        self.assertAlmostEqual(float(box.height), 792, delta=1)


class PrintViewTest(_FormFixture):

    def test_download_is_a_pdf_with_an_event(self):
        """
        GIVEN an owner of the survey
        WHEN they download the form in de on A4
        THEN the response is an attached PDF and form_printed carries the five properties
        """
        with override_settings(MAPBOX_ACCESS_TOKEN=''), mock.patch('survey.print.views.pe.emit') as emit:
            response = self.client.get(self.url, {'lang': 'de', 'paper': 'a4'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('park-survey-form-de-a4.pdf', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF'))
        event, _user, props = emit.call_args.args
        self.assertEqual(event, 'form_printed')
        self.assertEqual(set(props), {'survey_id', 'paper', 'language', 'pages', 'map_pages'})
        self.assertEqual((props['paper'], props['language']), ('a4', 'de'))

    def test_bad_language_and_paper(self):
        """
        GIVEN the download URL
        WHEN an unknown language or paper is asked for
        THEN the response is 400
        """
        self.assertEqual(self.client.get(self.url, {'lang': 'fr'}).status_code, 400)
        self.assertEqual(self.client.get(self.url, {'lang': 'en', 'paper': 'a3'}).status_code, 400)

    def test_viewer_cannot_print(self):
        """
        GIVEN a viewer of the workspace
        WHEN they request the download
        THEN the response is 403
        """
        viewer = User.objects.create_user('form_viewer', password='pass')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        self.client.force_login(viewer)
        s = self.client.session
        s['active_org_id'] = self.org.id
        s.save()
        self.assertEqual(self.client.get(self.url, {'lang': 'en'}).status_code, 403)

    def test_share_page_offers_the_form_in_every_status(self):
        """
        GIVEN a draft survey and a published one
        WHEN the Share page renders
        THEN both carry the Print section, the draft with the watermark hint
        """
        share = reverse('editor_survey_share', args=[self.survey.uuid])
        page = self.client.get(share)
        self.assertContains(page, 'id="print-form"')
        self.assertContains(page, 'name="lang"')
        self.assertNotContains(page, 'DRAFT watermark')
        self.survey.status = 'draft'
        self.survey.save()
        page = self.client.get(share)
        self.assertContains(page, 'id="print-form"')
        self.assertContains(page, 'DRAFT watermark')

    def test_letter_preselected_for_a_us_locale(self):
        """
        GIVEN a creator whose browser asks for en-US
        WHEN the Share page renders
        THEN US Letter is the preselected paper
        """
        share = reverse('editor_survey_share', args=[self.survey.uuid])
        page = self.client.get(share, HTTP_ACCEPT_LANGUAGE='en-US,en;q=0.9')
        self.assertContains(page, '<option value="letter" selected>')
        page = self.client.get(share, HTTP_ACCEPT_LANGUAGE='de-DE,de;q=0.9')
        self.assertContains(page, '<option value="a4" selected>')
