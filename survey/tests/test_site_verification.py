"""Tests for the `site-verification` capability (openspec/specs/site-verification/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client


class GoogleSiteVerificationTest(TestCase):
    """GSC meta-tag verification: rendered only when the token is configured."""

    def test_tag_absent_by_default(self):
        """
        GIVEN no GOOGLE_SITE_VERIFICATION configured (default '')
        WHEN the landing page renders
        THEN no google-site-verification meta tag is emitted
        """
        resp = Client().get("/")
        self.assertNotContains(resp, "google-site-verification")

    def test_tag_rendered_when_configured(self):
        """
        GIVEN GOOGLE_SITE_VERIFICATION is set to a token
        WHEN the landing page renders
        THEN the meta tag with that token is emitted
        """
        with self.settings(GOOGLE_SITE_VERIFICATION="tok123abc"):
            resp = Client().get("/")
            self.assertContains(resp, '<meta name="google-site-verification" content="tok123abc">')
