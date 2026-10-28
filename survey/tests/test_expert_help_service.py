"""Tests for the `expert-help-service` capability (openspec/specs/expert-help-service/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client


class ServicesPageTest(TestCase):
    """Expert-help service page: optional paid help on top of the free platform."""

    def test_page_renders_with_help_offer_and_free_reassurance(self):
        """
        GIVEN the services page
        WHEN an anonymous visitor requests it
        THEN it renders with the two help tiers, the "stays free" reassurance,
             and both call-to-action buttons pointing at /demo/?src=services
        """
        resp = Client().get("/services/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Launch help")
        self.assertContains(resp, "Done-with-you engagement")
        self.assertContains(resp, "free and open source")
        self.assertContains(resp, 'href="/demo/?src=services" class="btn-primary-landing">Request a demo', count=2)
        self.assertNotContains(resp, "mailto:konuchovartem@mapsurvey.org?subject=")

    def test_in_sitemap_and_robots(self):
        """
        GIVEN the services page
        WHEN sitemap.xml and robots.txt are fetched
        THEN both list /services/
        """
        c = Client()
        self.assertContains(c.get("/sitemap.xml"), "/services/")
        self.assertContains(c.get("/robots.txt"), "/services/")
