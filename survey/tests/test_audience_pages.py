"""Tests for the `audience-pages` capability (openspec/specs/audience-pages/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client


class AudienceLandingPagesTest(TestCase):
    """Audience "for …" pages: planners and researchers (SEO + UTM + discoverability)."""

    def test_planners_page(self):
        """
        GIVEN the urban-planners page
        WHEN requested
        THEN it renders with planner SEO and a planners-UTM CTA
        """
        resp = Client().get("/for-planners/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Mapsurvey for urban planners")
        self.assertContains(resp, "for-planners/")
        self.assertContains(resp, "utm_source=planners")

    def test_researchers_page(self):
        """
        GIVEN the researchers page
        WHEN requested
        THEN it renders with researcher SEO and a researchers-UTM CTA
        """
        resp = Client().get("/for-researchers/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Mapsurvey for researchers")
        self.assertContains(resp, "for-researchers/")
        self.assertContains(resp, "utm_source=researchers")

    def test_both_in_sitemap_and_robots(self):
        """
        GIVEN the pages should be indexable
        WHEN sitemap.xml and robots.txt are fetched
        THEN both audience pages are listed / allowed
        """
        c = Client()
        sm = c.get("/sitemap.xml")
        self.assertContains(sm, "/for-planners/")
        self.assertContains(sm, "/for-researchers/")
        rb = c.get("/robots.txt")
        self.assertContains(rb, "/for-planners/")
        self.assertContains(rb, "/for-researchers/")


class ForGovernmentLandingTest(TestCase):
    """Local-government page positioned as the open-source community engagement platform."""

    def test_page_renders_with_engagement_positioning_and_utm(self):
        """
        GIVEN the for-government page
        WHEN requested
        THEN it renders with the community-engagement-platform positioning and a government-UTM CTA
        """
        resp = Client().get("/for-government/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "community engagement platform")
        self.assertContains(resp, "for-government/")
        self.assertContains(resp, "utm_source=government")

    def test_in_sitemap_and_robots(self):
        c = Client()
        self.assertContains(c.get("/sitemap.xml"), "/for-government/")
        self.assertContains(c.get("/robots.txt"), "/for-government/")
