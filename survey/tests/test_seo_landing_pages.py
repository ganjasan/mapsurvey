"""Tests for the `seo-landing-pages` capability (openspec/specs/seo-landing-pages/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client


class SeoProductLandingPagesTest(TestCase):
    """Bottom-funnel product pages: community engagement platform & public consultation software."""

    def test_community_engagement_platform_page(self):
        """
        GIVEN the community-engagement-platform product page
        WHEN requested
        THEN it renders with the head-term H1, a self-canonical, a platform-UTM CTA,
             and cross-links to audience pages
        """
        resp = Client().get("/community-engagement-platform/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Community Engagement Platform")
        self.assertContains(resp, "https://mapsurvey.org/community-engagement-platform/")
        self.assertContains(resp, "utm_source=engagement_platform")
        self.assertContains(resp, "/for-government/")  # cross-link to an audience segment

    def test_public_consultation_software_page(self):
        """
        GIVEN the public-consultation-software product page
        WHEN requested
        THEN it renders with the term H1, a self-canonical, and a consultation-UTM CTA
        """
        resp = Client().get("/public-consultation-software/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Public Consultation Software")
        self.assertContains(resp, "https://mapsurvey.org/public-consultation-software/")
        self.assertContains(resp, "utm_source=consultation_software")

    def test_both_in_sitemap_and_robots(self):
        """
        GIVEN the product pages should be indexable
        WHEN sitemap.xml and robots.txt are fetched
        THEN both are listed / allowed
        """
        c = Client()
        sm = c.get("/sitemap.xml")
        self.assertContains(sm, "/community-engagement-platform/")
        self.assertContains(sm, "/public-consultation-software/")
        rb = c.get("/robots.txt")
        self.assertContains(rb, "/community-engagement-platform/")
        self.assertContains(rb, "/public-consultation-software/")

    def test_shared_footer_links_to_both(self):
        """
        GIVEN the shared landing footer provides site-wide internal links
        WHEN any landing page is rendered
        THEN its footer links to both product pages
        """
        resp = Client().get("/for-planners/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'href="/community-engagement-platform/"')
        self.assertContains(resp, 'href="/public-consultation-software/"')


class SeoWave2LandingPagesTest(TestCase):
    """Wave-2 SEO pages: civic-engagement category, PB use-case, consultants audience,
    and the Social Pinpoint / MetroQuest comparison pages."""

    def test_civic_engagement_page(self):
        """
        GIVEN the civic-engagement category page
        WHEN requested
        THEN it renders with the head term, a self-canonical, its UTM CTA,
             and funnel links to a product page
        """
        resp = Client().get("/civic-engagement/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Civic engagement")
        self.assertContains(resp, "https://mapsurvey.org/civic-engagement/")
        self.assertContains(resp, "utm_source=civic_engagement")
        self.assertContains(resp, "/community-engagement-platform/")  # funnel link down

    def test_participatory_budgeting_page(self):
        """
        GIVEN the participatory-budgeting use-case page
        WHEN requested
        THEN it renders with the term, a self-canonical, and its UTM CTA
        """
        resp = Client().get("/participatory-budgeting/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Participatory budgeting")
        self.assertContains(resp, "https://mapsurvey.org/participatory-budgeting/")
        self.assertContains(resp, "utm_source=participatory_budgeting")

    def test_for_consultants_page(self):
        """
        GIVEN the consultants audience page
        WHEN requested
        THEN it renders with consultant positioning, a self-canonical, and its UTM CTA
        """
        resp = Client().get("/for-consultants/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "consultants")
        self.assertContains(resp, "https://mapsurvey.org/for-consultants/")
        self.assertContains(resp, "utm_source=consultants")

    def test_social_pinpoint_alternative_page(self):
        """
        GIVEN the Social Pinpoint comparison page
        WHEN requested
        THEN it renders with comparison positioning, a self-canonical, a fair section,
             and the comparison UTM
        """
        resp = Client().get("/alternatives/social-pinpoint/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Social Pinpoint alternative")
        self.assertContains(resp, "https://mapsurvey.org/alternatives/social-pinpoint/")
        self.assertContains(resp, "utm_medium=social_pinpoint_alt")
        self.assertContains(resp, "may be the better fit")  # "being fair" section

    def test_metroquest_alternative_page(self):
        """
        GIVEN the MetroQuest comparison page
        WHEN requested
        THEN it renders with migration positioning, a self-canonical, and the comparison UTM
        """
        resp = Client().get("/alternatives/metroquest/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "MetroQuest alternative")
        self.assertContains(resp, "https://mapsurvey.org/alternatives/metroquest/")
        self.assertContains(resp, "utm_medium=metroquest_alt")

    def test_all_in_sitemap_and_robots(self):
        """
        GIVEN the wave-2 pages should be indexable
        WHEN sitemap.xml and robots.txt are fetched
        THEN all five are listed in the sitemap and allowed by robots
        """
        c = Client()
        sm = c.get("/sitemap.xml")
        for path in ("/civic-engagement/", "/participatory-budgeting/", "/for-consultants/",
                     "/alternatives/social-pinpoint/", "/alternatives/metroquest/"):
            self.assertContains(sm, path)
        rb = c.get("/robots.txt")
        for path in ("/civic-engagement/", "/participatory-budgeting/", "/for-consultants/",
                     "/alternatives/"):
            self.assertContains(rb, path)

    def test_footer_and_nav_link_wave2_pages(self):
        """
        GIVEN the shared landing chrome provides site-wide internal links
        WHEN any landing page is rendered
        THEN the footer links all wave-2 pages and the Solutions dropdown links consultants
        """
        resp = Client().get("/for-planners/")
        self.assertEqual(resp.status_code, 200)
        for href in ('href="/civic-engagement/"', 'href="/participatory-budgeting/"',
                     'href="/for-consultants/"', 'href="/alternatives/social-pinpoint/"',
                     'href="/alternatives/metroquest/"'):
            self.assertContains(resp, href)
