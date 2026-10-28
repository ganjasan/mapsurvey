"""Tests for the `spraycan-density-views` capability (openspec/specs/spraycan-density-views/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.gis.geos import Point
import json
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, PublicResultsPage, PublicResultsBlock
from survey.tests.helpers import _make_org


class SpraycanPublicGridTest(TestCase):
    """Spec spraycan-density-views: the public page publishes a density grid, never dots."""

    def setUp(self):
        self.org = _make_org('Spray Public Org')
        self.survey = SurveyHeader.objects.create(name='spray_pub', organization=self.org, status='published')
        self.section = SurveySection.objects.create(survey_header=self.survey, name='sec', code='S1', is_head=True)
        self.spray = Question.objects.create(
            survey_section=self.section, code='SP', name='Unsafe', input_type='spraycan', color='#d6336c',
        )
        self.page = PublicResultsPage.objects.create(survey=self.survey, slug='spraypub', is_published=True)
        self.block = PublicResultsBlock.objects.create(page=self.page, block_type='map', question=self.spray, order=0)

    def _cloud(self, coords, status=''):
        from django.contrib.gis.geos import MultiPoint
        session = SurveySession.objects.create(survey=self.survey, validation_status=status)
        geom = MultiPoint(*[Point(x, y) for x, y in coords], srid=4326)
        return Answer.objects.create(survey_session=session, question=self.spray, multipoint=geom)

    def _payload(self, k=3):
        from survey.public_results import PublicResultsService
        self.page.k_anonymity_threshold = k
        self.page.save()
        blocks = PublicResultsService(self.page).build_blocks()
        return blocks[0]

    def test_grid_counts_respondents_and_omits_cells_below_k(self):
        """
        GIVEN one respondent with 400 dots in one spot, three others with 5 dots each
             there, and two respondents who sprayed a far corner
        WHEN the block payload is built with k=3
        THEN the busy cell counts 4 respondents, the far corner's cells are absent,
             and the payload holds cells only — no MultiPoint, no session ids
        """
        here = [(13.300 + i * 1e-6, 52.500 + i * 1e-6) for i in range(400)]
        self._cloud(here)
        for _ in range(3):
            self._cloud(here[:5])
        far = [(13.330, 52.520), (13.3301, 52.5201)]
        self._cloud(far)
        self._cloud(far)
        payload = self._payload(k=3)
        self.assertEqual(payload['data_type'], 'grid')
        self.assertEqual(payload['max'], 4)
        self.assertEqual(payload['color'], '#d6336c')
        self.assertEqual(payload['respondents_total'], 6)
        counts = [f['properties']['respondents'] for f in payload['cells']['features']]
        self.assertTrue(all(c >= 3 for c in counts), counts)
        self.assertNotIn('feature_collection', payload)
        dumped = json.dumps(payload)
        self.assertNotIn('MultiPoint', dumped)
        self.assertNotIn('session', dumped)
        # Far corner (two respondents) is not in any published cell
        for f in payload['cells']['features']:
            xs = [c[0] for c in f['geometry']['coordinates'][0]]
            self.assertLess(max(xs), 13.32)

    def test_threshold_one_keeps_every_cell(self):
        """
        GIVEN two respondents in different places
        WHEN the payload is built with k=1
        THEN both places have a cell with count 1
        """
        self._cloud([(13.300, 52.500)])
        self._cloud([(13.330, 52.520)])
        payload = self._payload(k=1)
        counts = sorted(f['properties']['respondents'] for f in payload['cells']['features'])
        self.assertEqual(counts, [1, 1])

    def test_excluded_sessions_leave_the_grid(self):
        """
        GIVEN a clean respondent and a not_approved one at the same spot
        WHEN the payload is built with k=1
        THEN the cell counts one respondent
        """
        self._cloud([(13.300, 52.500)])
        self._cloud([(13.300, 52.500)], status='not_approved')
        payload = self._payload(k=1)
        self.assertEqual(payload['max'], 1)
        self.assertEqual(payload['respondents_total'], 1)

    def test_stale_snapshot_asks_for_a_refreeze(self):
        """
        GIVEN a frozen page snapshotted under the previous format version
        WHEN the page data is rendered
        THEN it is flagged stale instead of rendering the old payload
        """
        from survey.public_results import freeze_page, render_page_data
        self._cloud([(13.300, 52.500)])
        freeze_page(self.page)
        self.page.snapshot['snapshot_version'] = 1
        self.page.save(update_fields=['snapshot'])
        data = render_page_data(self.page)
        self.assertTrue(data.get('stale'))

    def test_block_type_for_spraycan_is_map(self):
        """
        GIVEN a spraycan question
        WHEN its public block type is resolved
        THEN it is a map block
        """
        from survey.public_results import block_type_for_question
        self.assertEqual(block_type_for_question(self.spray), 'map')
