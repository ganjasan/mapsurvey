"""Spec: public-aggregates (change data-aggregate, Data epic #676, ADR-001 move 2 and §6.3).

Everything a public surface shows of answers goes through `data.aggregate`: one masking rule,
and maps as grids of cells counting distinct respondents, cells under K left out.
"""
from django.contrib.gis.geos import LineString, MultiPoint, Point, Polygon
from django.test import SimpleTestCase, TestCase

from data.aggregate import grid, mask
from survey.models import (
    Answer, Question, SurveyHeader, SurveySection, SurveySession,
)
from reports.models import ReportBlock, Report, SNAPSHOT_VERSION

from .helpers import _make_org


def _square(x, y, d=0.0005):
    return Polygon.from_bbox((x, y, x + d, y + d))


class MaskTest(SimpleTestCase):
    """Requirement: Public surfaces read answers through one aggregation path."""

    def test_small_bucket_has_no_value(self):
        """
        GIVEN K = 3
        WHEN counts 0, 2 and 5 are masked
        THEN 2 shows "<3" with no value, 0 and 5 are exact
        """
        self.assertEqual(mask(2, 3), {'value': None, 'display': '<3', 'masked': True})
        self.assertEqual(mask(0, 3)['value'], 0)
        self.assertEqual(mask(5, 3)['display'], '5')

    def test_threshold_one_disables_masking(self):
        """
        GIVEN K = 1
        WHEN a count of 1 is masked
        THEN it is exact
        """
        self.assertEqual(mask(1, 1)['display'], '1')


class GridTest(SimpleTestCase):
    """Requirement: A public map never carries an individual geometry."""

    def test_points_become_cells_and_a_lone_point_is_dropped(self):
        """
        GIVEN 5 respondents' points in one place and 1 respondent's point far away, K = 3
        WHEN the grid is built
        THEN one cell counts 5 respondents and nothing exists for the lone point
        """
        members = [(sid, sid, Point(30.0, 59.0, srid=4326)) for sid in range(5)]
        members.append((99, 99, Point(30.5, 59.5, srid=4326)))
        out = grid(members, k=3)
        self.assertEqual([c['respondents'] for c in out['cells']], [5])
        self.assertEqual(out['respondents_total'], 6)

    def test_a_polygon_counts_in_every_cell_it_touches_once_per_respondent(self):
        """
        GIVEN 3 respondents whose polygons cover the same area, one of them with two overlapping
              polygons, and a far point that fixes a coarse cell size
        WHEN the grid is built with K = 3
        THEN every published cell counts exactly 3 respondents
        """
        members = [(1, 'a', _square(30.0, 59.0)), (1, 'b', _square(30.0001, 59.0001)),
                   (2, 'c', _square(30.0, 59.0)), (3, 'd', _square(30.0, 59.0))]
        out = grid(members, k=3, cells_across=40)
        self.assertTrue(out['cells'])
        self.assertEqual({c['respondents'] for c in out['cells']}, {3})

    def test_a_line_counts_in_the_cells_it_crosses(self):
        """
        GIVEN 3 respondents drawing the same line
        WHEN the grid is built with K = 3
        THEN at least two cells are published, each counting 3
        """
        line = LineString((30.0, 59.0), (30.01, 59.0), srid=4326)
        out = grid([(i, i, line) for i in range(3)], k=3, cells_across=10)
        self.assertGreaterEqual(len(out['cells']), 2)
        self.assertEqual({c['respondents'] for c in out['cells']}, {3})

    def test_spray_cloud_counts_once_per_respondent_per_cell(self):
        """
        GIVEN one respondent with many dots in one cell and two others with one dot there
        WHEN the grid is built with K = 3
        THEN the cell counts 3 respondents, not the dots
        """
        cloud = MultiPoint([Point(30.0, 59.0), Point(30.00001, 59.00001)], srid=4326)
        members = [(1, 1, cloud), (2, 2, Point(30.0, 59.0, srid=4326)), (3, 3, Point(30.0, 59.0, srid=4326))]
        out = grid(members, k=3)
        self.assertEqual([c['respondents'] for c in out['cells']], [3])


class MarksTest(SimpleTestCase):
    """Requirement: The grid counts marks as well as respondents."""

    def test_two_points_from_one_respondent(self):
        """
        GIVEN 3 respondents with points in one cell, one of them two points, K = 3
        WHEN the grid is built
        THEN the cell reports 3 respondents and 4 marks
        """
        members = [(1, 'a', Point(30.0, 59.0, srid=4326)), (1, 'b', Point(30.00001, 59.0, srid=4326)),
                   (2, 'c', Point(30.0, 59.0, srid=4326)), (3, 'd', Point(30.0, 59.0, srid=4326))]
        out = grid(members, k=3)
        self.assertEqual([(c['respondents'], c['marks']) for c in out['cells']], [(3, 4)])

    def test_spray_dots_are_marks(self):
        """
        GIVEN a spray cloud of two dots and two single points in one cell
        WHEN the grid is built with K = 3
        THEN the cell reports 4 marks
        """
        cloud = MultiPoint([Point(30.0, 59.0), Point(30.00001, 59.00001)], srid=4326)
        members = [(1, 1, cloud), (2, 2, Point(30.0, 59.0, srid=4326)), (3, 3, Point(30.0, 59.0, srid=4326))]
        self.assertEqual([c['marks'] for c in grid(members, k=3)['cells']], [4])

    def test_marks_do_not_unlock_a_cell(self):
        """
        GIVEN 2 respondents with 10 points in one cell, K = 3
        WHEN the grid is built
        THEN the cell is omitted
        """
        members = [(sid, f'{sid}-{i}', Point(30.0 + i * 1e-6, 59.0, srid=4326)) for sid in (1, 2) for i in range(5)]
        self.assertEqual(grid(members, k=3)['cells'], [])


class AdaptiveGridTest(SimpleTestCase):
    """Requirement: A public map never carries an individual geometry — cell size (change
    data-grid-adaptive)."""

    # Four respondents within ~400 m of each other and two further out, over ~2 km.
    TOWN = [(30.000, 59.000), (30.002, 59.001), (30.003, 59.000), (30.001, 59.002),
            (30.030, 59.010), (30.034, 59.012)]

    def test_a_small_survey_gets_coarser_cells(self):
        """
        GIVEN 6 respondents' points a few hundred metres apart, K = 3
        WHEN the grid is built without a fixed size
        THEN a 40-across grid would show nobody, and the chosen coarser grid shows most of them
        """
        members = [(i, i, Point(x, y)) for i, (x, y) in enumerate(self.TOWN)]
        fixed = grid(members, k=3, cells_across=40)
        self.assertEqual(fixed['respondents_shown'], 0)
        out = grid(members, k=3)
        self.assertLess(out['cells_across'], 40)
        self.assertGreaterEqual(out['respondents_shown'], 4)
        self.assertTrue(all(c['respondents'] >= 3 for c in out['cells']))

    def test_a_busy_survey_keeps_the_fine_grid(self):
        """
        GIVEN 30 respondents' points in one small square and 2 elsewhere, K = 3
        WHEN the grid is built without a fixed size
        THEN the fine 40-across grid is kept
        """
        members = [(i, i, Point(30.0 + (i % 5) * 1e-5, 59.0)) for i in range(30)]
        members += [(30, 30, Point(30.02, 59.02)), (31, 31, Point(30.03, 59.0))]
        self.assertEqual(grid(members, k=3)['cells_across'], 40)

    def test_too_few_answers_show_no_cell(self):
        """
        GIVEN 2 respondents' points far apart, K = 3
        WHEN the grid is built
        THEN no cell is shown and both are counted as hidden
        """
        out = grid([(1, 1, Point(30.0, 59.0)), (2, 2, Point(31.0, 60.0))], k=3)
        self.assertEqual((out['cells'], out['respondents_hidden']), ([], 2))


class PublicSurfacesTest(TestCase):
    """Requirements: one path for every public surface; no individual geometry; stale snapshots."""

    def test_too_few_answers_replace_the_map_with_a_note(self):
        """
        GIVEN 2 respondents' points far apart, K = 3
        WHEN the public map block is built
        THEN it holds no cell and a note saying why, and no answer geometry
        """
        from reports.render import ReportService
        self._respondent(1, (30.0, 59.0))
        self._respondent(1, (31.0, 60.0))
        block = ReportBlock.objects.create(report=self.page, block_type='map', question=self.point, order=0)
        payload = ReportService(self.page)._build_block(block)
        self.assertEqual(payload['cells']['features'], [])
        self.assertIn('fewer than 3 people', payload['note'])
        self.assertEqual(payload['respondents_hidden'], 2)
        self.assertNotIn('"Point"', str(payload))

    def test_hidden_respondents_are_named_in_the_caption(self):
        """
        GIVEN 4 respondents in one place and 1 far away, K = 3
        WHEN the public map block is built
        THEN one cell of 4 shows and the note says 1 respondent is not shown
        """
        from reports.render import ReportService
        for _ in range(4):
            self._respondent(1, (30.0, 59.0))
        self._respondent(1, (31.0, 60.0))
        block = ReportBlock.objects.create(report=self.page, block_type='map', question=self.point, order=0)
        payload = ReportService(self.page)._build_block(block)
        self.assertEqual([f['properties']['respondents'] for f in payload['cells']['features']], [4])
        self.assertIn('1 respondent is in an area with fewer than 3 people', payload['note'])

    def setUp(self):
        org = _make_org('AggOrg')
        self.survey = SurveyHeader.objects.create(name='agg_survey', organization=org, status='published')
        section = SurveySection.objects.create(survey_header=self.survey, name='s', code='S1', is_head=True)
        self.choice = Question.objects.create(
            survey_section=section, code='AG_C', name='Pick', input_type='choice',
            choices=[{'code': 1, 'name': 'A'}, {'code': 2, 'name': 'B'}])
        self.point = Question.objects.create(survey_section=section, code='AG_P', name='Where', input_type='point')
        self.page = Report.objects.create(survey=self.survey, slug='agg', is_published=True)

    def _respondent(self, code, where=(30.0, 59.0)):
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.choice, selected_choices=[code])
        Answer.objects.create(survey_session=s, question=self.point, point=Point(*where))
        return s

    def test_results_page_and_site_block_mask_alike_and_the_api_stays_exact(self):
        """
        GIVEN option B picked by 2 respondents and A by 4, K = 3
        WHEN the public results block, the Site results block and the Responses/API statistics
             are computed
        THEN both public payloads show B as "<3" and the workspace statistics count 2
        """
        from types import SimpleNamespace
        from survey.analytics import SurveyAnalyticsService
        from reports.render import ReportService
        for code in (1, 1, 1, 1, 2, 2):
            self._respondent(code)
        block = ReportBlock.objects.create(report=self.page, block_type='chart', question=self.choice, order=0)
        page_payload = ReportService(self.page)._build_block(block)
        site_like = SimpleNamespace(id='r1', block_type='chart', viz='auto', custom_title={}, question=self.choice,
                                    question_id=self.choice.pk, geo_label_fields=[], basemap='streets',
                                    content={}, image=None, is_hidden=False)
        site_payload = ReportService.for_survey(self.survey, 3)._build_block(site_like)
        for payload in (page_payload, site_payload):
            b = next(i for i in payload['items'] if i['code'] == 2)
            self.assertEqual((b['display'], b['value']), ('<3', None))
        stats = SurveyAnalyticsService(self.survey).get_question_stats(self.choice)
        counts = dict(zip(stats['choice_codes'], stats['choice_counts']))
        self.assertEqual(counts[2], 2)

    def test_site_results_map_is_a_grid(self):
        """
        GIVEN 3 respondents' points in one place
        WHEN a Site results block shows the point question
        THEN its payload is a grid with one cell of 3 and no answer geometry
        """
        from types import SimpleNamespace
        from reports.render import ReportService
        for _ in range(3):
            self._respondent(1)
        site_like = SimpleNamespace(id='r2', block_type='map', viz='auto', custom_title={}, question=self.point,
                                    question_id=self.point.pk, geo_label_fields=[], basemap='streets',
                                    content={}, image=None, is_hidden=False)
        payload = ReportService.for_survey(self.survey, 3)._build_block(site_like)
        self.assertEqual(payload['data_type'], 'grid')
        self.assertEqual([f['properties']['respondents'] for f in payload['cells']['features']], [3])
        self.assertNotIn('"Point"', str(payload))

    def test_frozen_snapshot_of_an_earlier_format_is_stale(self):
        """
        GIVEN a page frozen with a version-2 snapshot that holds point features
        WHEN the page data is rendered
        THEN it is in the "refresh needed" state and carries no blocks
        """
        from reports.render import render_data
        self.page.mode = 'frozen'
        self.page.snapshot = {'snapshot_version': 2, 'response_count': 1, 'blocks': [
            {'block_type': 'map', 'feature_collection': {'features': [{'geometry': {'type': 'Point'}}]}}]}
        self.page.save()
        self.assertEqual(SNAPSHOT_VERSION, 3)
        data = render_data(self.page)
        self.assertTrue(data['stale'])
        self.assertEqual(data['blocks'], [])
