"""Tests for the `comparison-pages` capability (openspec/specs/comparison-pages/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client


class MaptionnaireAlternativeTest(TestCase):
    """SEO comparison page targeting the validated "Maptionnaire alternative" query."""

    def test_page_renders_with_seo_and_utm(self):
        """
        GIVEN the Maptionnaire alternative page
        WHEN requested
        THEN it renders with comparison content, education/alternative SEO, and a comparison-UTM CTA
        """
        resp = Client().get("/alternatives/maptionnaire/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Maptionnaire alternative")
        self.assertContains(resp, "alternatives/maptionnaire/")     # canonical
        self.assertContains(resp, "utm_source=comparison")

    def test_discoverable_in_sitemap_and_robots(self):
        """
        GIVEN the page should be indexable
        WHEN sitemap.xml and robots.txt are fetched
        THEN both reference the page / its prefix
        """
        c = Client()
        self.assertContains(c.get("/sitemap.xml"), "/alternatives/maptionnaire/")
        self.assertContains(c.get("/robots.txt"), "/alternatives/")
