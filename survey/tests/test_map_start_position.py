"""Tests for the `map-start-position` capability (openspec/specs/map-start-position/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, override_settings
from django.contrib.gis.geos import Point
from django.utils import timezone
from survey.models import SurveyHeader
from django.test import RequestFactory
from survey.tests.helpers import _make_org


# ── Ways to start (change first-survey-onboarding) ──────────────────────────

class MapStartTest(TestCase):
    """`survey/map_start.py`: the ordered chain behind every new survey's map."""

    def setUp(self):
        from django.test import RequestFactory
        self.factory = RequestFactory()
        self.org = _make_org('MapStartOrg')

    def _request(self, **headers):
        request = self.factory.get('/editor/surveys/start/', **headers)
        request.active_org = self.org
        return request

    def test_browser_position_wins(self):
        """
        GIVEN posted browser coordinates and a positioned survey in the organization
        WHEN the chain runs
        THEN the browser coordinates come back with source 'browser'
        """
        from survey import map_start
        SurveyHeader.objects.create(name='bishkek', organization=self.org,
                                    start_map_postion=Point(74.59, 42.87), start_map_zoom=11)

        start = map_start.suggest_start_position(self._request(), browser=(10.0, 20.0, 9))

        self.assertEqual((start.lat, start.lng, start.zoom, start.source), (10.0, 20.0, 9, 'browser'))

    def test_newest_organization_survey(self):
        """
        GIVEN two positioned surveys in the organization and no browser position
        WHEN the chain runs
        THEN the newer survey's position and zoom come back with source 'org_survey'
        """
        from survey import map_start
        SurveyHeader.objects.create(name='older', organization=self.org,
                                    start_map_postion=Point(13.405, 52.52), start_map_zoom=12)
        SurveyHeader.objects.create(name='newer', organization=self.org,
                                    start_map_postion=Point(74.59, 42.87), start_map_zoom=11)
        # A trashed survey and a draft copy are not the workspace's map.
        SurveyHeader.objects.create(name='trashed', organization=self.org, deleted_at=timezone.now(),
                                    start_map_postion=Point(0.0, 0.0), start_map_zoom=3)

        start = map_start.suggest_start_position(self._request())

        self.assertEqual(start.source, 'org_survey')
        self.assertAlmostEqual(start.lat, 42.87)
        self.assertAlmostEqual(start.lng, 74.59)
        self.assertEqual(start.zoom, 11)

    @override_settings(CLOUDFLARE_TRUSTED=True)
    def test_country_from_the_edge_header(self):
        """
        GIVEN no browser position, no positioned survey, and CF-IPCountry = KG behind a trusted edge
        WHEN the chain runs
        THEN Kyrgyzstan's centre at zoom 5 comes back with source 'country'
        """
        from survey import map_start
        from survey.country_centroids import CENTROIDS

        start = map_start.suggest_start_position(self._request(HTTP_CF_IPCOUNTRY='KG'))

        self.assertEqual(start.source, 'country')
        self.assertEqual((start.lat, start.lng), CENTROIDS['KG'])
        self.assertEqual(start.zoom, 5)

    @override_settings(CLOUDFLARE_TRUSTED=False)
    def test_edge_header_ignored_when_untrusted(self):
        """
        GIVEN CF-IPCountry = KG but no trusted edge, and Accept-Language de-AT
        WHEN the chain runs
        THEN Austria's centre comes back, not Kyrgyzstan's
        """
        from survey import map_start
        from survey.country_centroids import CENTROIDS

        start = map_start.suggest_start_position(
            self._request(HTTP_CF_IPCOUNTRY='KG', HTTP_ACCEPT_LANGUAGE='de-AT,de;q=0.9'),
        )

        self.assertEqual(start.source, 'country')
        self.assertEqual((start.lat, start.lng), CENTROIDS['AT'])

    @override_settings(CLOUDFLARE_TRUSTED=True)
    def test_unknown_country_falls_through_to_the_world(self):
        """
        GIVEN Cloudflare's XX (unknown) and an Accept-Language without a region
        WHEN the chain runs
        THEN the world view comes back
        """
        from survey import map_start

        start = map_start.suggest_start_position(
            self._request(HTTP_CF_IPCOUNTRY='XX', HTTP_ACCEPT_LANGUAGE='en,fr;q=0.8'),
        )

        self.assertEqual(start, map_start.WORLD)
        self.assertEqual((start.lat, start.lng, start.zoom, start.source), (20.0, 0.0, 2, 'world'))

    def test_stock_browser_locale_is_not_a_location(self):
        """
        GIVEN a creator in Bishkek whose stock Chrome sends en-US and no trusted edge header
        WHEN the chain runs
        THEN the world view comes back, not Kansas: `en-US` is the browser default, not a place
        """
        from survey import map_start

        start = map_start.suggest_start_position(self._request(HTTP_ACCEPT_LANGUAGE='en-US,en;q=0.9'))

        self.assertEqual(start.source, 'world')
        self.assertEqual(map_start._accept_language_region('pt-BR,pt;q=0.9'), 'BR')

    def test_no_request_context_is_the_world(self):
        """
        GIVEN a request without an organization or any header
        WHEN the chain runs
        THEN the world view comes back and nothing raises
        """
        from survey import map_start
        request = self.factory.get('/')
        request.active_org = None

        self.assertEqual(map_start.suggest_start_position(request).source, 'world')

    def test_browser_position_parsing(self):
        """
        GIVEN posted map fields in several shapes
        WHEN they are parsed
        THEN a valid pair becomes a tuple, a missing zoom defaults, and garbage is None
        """
        from survey import map_start

        self.assertEqual(map_start.browser_position({'map_lat': '42.87', 'map_lng': '74.59', 'map_zoom': '11'}),
                         (42.87, 74.59, 11))
        self.assertEqual(map_start.browser_position({'map_lat': '42.87', 'map_lng': '74.59'}),
                         (42.87, 74.59, map_start.ZOOM_BROWSER))
        self.assertIsNone(map_start.browser_position({'map_lat': '', 'map_lng': ''}))
        self.assertIsNone(map_start.browser_position({'map_lat': '999', 'map_lng': '0'}))
        self.assertIsNone(map_start.browser_position({'map_lat': 'abc', 'map_lng': '1'}))
        self.assertIsNone(map_start.browser_position({}))

    def test_every_centroid_is_a_point_on_earth(self):
        """
        GIVEN the hand-maintained centroid table
        WHEN every entry is checked
        THEN each is an alpha-2 code with coordinates inside the WGS84 box
        """
        from survey.country_centroids import CENTROIDS

        self.assertGreater(len(CENTROIDS), 240)
        for code, (lat, lng) in CENTROIDS.items():
            self.assertRegex(code, r'^[A-Z]{2}$')
            self.assertTrue(-90 <= lat <= 90 and -180 <= lng <= 180, code)
