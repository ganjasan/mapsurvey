"""Tests for the `marker-draw-lifecycle` capability (openspec/specs/marker-draw-lifecycle/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.gis.geos import Point
from survey.models import SurveyHeader, SurveySection, Question
from survey.tests.helpers import _make_org


class ZeroSizeMapGuardTest(TestCase):
    """Leaflet must not be driven while its container has no size.

    Everything Leaflet computes comes from `map.getSize()`; on a hidden
    container that is 0x0, and the projections built on it degenerate. Two
    PostHog issues, one root cause:

    * respondent/preview — the geolocation callback called `map.flyTo` from up
      to ten seconds later, by which point the respondent could be on a `form`
      section where `survey-form-layout` hides `#map`. `flyTo` is animated, so
      it threw once per frame: 3 sessions produced 64 events (01a03018).
    * editor analytics — `invalidateSize()` on a hidden pane re-fires the heat
      layer's redraw against a 0x0 canvas and `getImageData` throws (01a04e54).

    These assert on rendered markup. The Django test client runs no JavaScript
    and has no layout, so it cannot execute the geometry that fails; the real
    check is a browser pass, recorded in the change's verification tasks. What
    the markup CAN pin is that no unguarded call path exists — which is the
    part a future edit would break.
    """

    def setUp(self):
        self.org = _make_org('MapGuardOrg')
        self.survey = SurveyHeader.objects.create(
            name='mapguard', organization=self.org, status='published',
            available_languages=[], redirect_url='#',
            start_map_postion=Point(13.405, 52.52), start_map_zoom=12,
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='pick', title='Pick', code='S1',
            is_head=True, start_map_postion=Point(13.377, 52.516),
        )
        Question.objects.create(
            survey_section=self.section, code='Q1', name='Where?',
            input_type='point', order_number=1)

    def _respondent_html(self):
        response = self.client.get('/surveys/mapguard/pick/')
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_respondent_page_defines_the_size_guard(self):
        """
        GIVEN the respondent survey page
        WHEN it renders
        THEN the size guard and the move helper are defined on the page
        """
        html = self._respondent_html()
        self.assertIn('function mapHasSize()', html)
        self.assertIn('function moveMapTo(', html)

    def test_every_respondent_fly_goes_through_the_helper(self):
        """
        GIVEN the respondent page's map code
        WHEN counting raw Leaflet fly calls
        THEN exactly one exists, the one inside moveMapTo

        This is the assertion that survives future edits: a new `map.flyTo(`
        added anywhere else on this page fails here, which is precisely how
        the geolocation call slipped through in the first place.
        """
        html = self._respondent_html()
        self.assertEqual(html.count('map.flyTo('), 1, 'an unguarded map.flyTo was added')

    def test_geolocation_callback_defers_instead_of_flying(self):
        """
        GIVEN the locate-me handler
        WHEN it succeeds
        THEN it routes through moveMapTo and abandons the callback if the move
             could not happen
        """
        html = self._respondent_html()
        self.assertIn('if (!moveMapTo(lat, lng, 13)) return;', html)

    def test_pending_target_is_replayed_after_invalidate_size(self):
        """
        GIVEN a move deferred while the map was hidden
        WHEN the map section returns and the container is measured again
        THEN the deferred target is replayed
        """
        html = self._respondent_html()
        self.assertIn('_pendingMapTarget', html)
        invalidate = html.index('map.invalidateSize();')
        replay = html.index('moveMapTo(t.lat, t.lng, t.zoom);')
        self.assertLess(invalidate, replay,
                        'the deferred move must be replayed after the resize, not before')

    def test_map_section_still_carries_its_coordinates(self):
        """
        GIVEN a section with its own map position
        WHEN the respondent page renders
        THEN the coordinates still reach the page

        Guards against a "fix" that simply stops moving the map.
        """
        html = self._respondent_html()
        self.assertIn('data-map-lat="52.516', html)
        self.assertIn('data-map-lng="13.377', html)
