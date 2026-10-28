"""Tests for the `for-educators-page` capability (openspec/specs/for-educators-page/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client


class ForEducatorsLandingTest(TestCase):
    """"Mapsurvey for classrooms" SEO landing page (coursework channel H1)."""

    def test_page_renders_with_seo_and_utm_cta(self):
        """
        GIVEN the for-educators landing page
        WHEN it is requested
        THEN it renders with education SEO (title/canonical) and a UTM-tagged register CTA
        """
        resp = Client().get("/for-educators/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Mapsurvey for classrooms")
        self.assertContains(resp, "for-educators/")            # canonical / og url
        self.assertContains(resp, "utm_source=edu")            # attribution tag on the CTA

    def test_listed_in_sitemap_and_allowed_in_robots(self):
        """
        GIVEN the page should be discoverable by search engines
        WHEN sitemap.xml and robots.txt are fetched
        THEN the page URL is in the sitemap and allowed in robots
        """
        c = Client()
        self.assertContains(c.get("/sitemap.xml"), "/for-educators/")
        self.assertContains(c.get("/robots.txt"), "/for-educators/")
