"""Tests for the `seo-structured-data` capability (openspec/specs/seo-structured-data/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.urls import reverse
import json


class LandingStructuredDataTest(TestCase):
    """Per-page structured data on the SEO landings: FAQ section + FAQPage /
    BreadcrumbList JSON-LD driven by the seo_landings registry."""

    import re as _re
    _LD_RE = _re.compile(r'<script type="application/ld\+json">(.*?)</script>', _re.S)

    def _ld_blocks(self, html):
        """GIVEN rendered HTML WHEN scanning ld+json THEN return parsed JSON objects."""
        return [json.loads(b) for b in self._LD_RE.findall(html)]

    def test_every_landing_has_valid_faqpage_matching_visible_faq(self):
        """
        GIVEN each SEO landing page
        WHEN rendered
        THEN it emits a valid FAQPage JSON-LD whose question names each appear
             in the visible FAQ section
        """
        from survey.seo_landings import SEO_LANDINGS
        c = Client()
        for landing in SEO_LANDINGS:
            resp = c.get(landing.path)
            self.assertEqual(resp.status_code, 200, landing.path)
            html = resp.content.decode()
            blocks = self._ld_blocks(html)  # all parse as valid JSON
            faqpages = [b for b in blocks if b.get("@type") == "FAQPage"]
            self.assertEqual(len(faqpages), 1, f"{landing.path}: expected one FAQPage")
            names = {q["name"] for q in faqpages[0]["mainEntity"]}
            self.assertEqual(names, {qa.q for qa in landing.faq}, landing.path)
            # each question is also visible on the page
            for qa in landing.faq:
                self.assertIn(qa.q, html, f"{landing.path}: visible FAQ missing {qa.q!r}")

    def test_breadcrumb_single_and_two_level(self):
        """
        GIVEN a single-level landing and a two-level alternatives landing
        WHEN rendered
        THEN BreadcrumbList JSON-LD has 2 vs 3 ordered items with absolute URLs
        """
        c = Client()
        one = self._ld_blocks(c.get("/for-planners/").content.decode())
        bc1 = next(b for b in one if b.get("@type") == "BreadcrumbList")
        items1 = bc1["itemListElement"]
        self.assertEqual([i["position"] for i in items1], [1, 2])
        self.assertEqual(items1[0]["name"], "Home")
        self.assertTrue(items1[-1]["item"].startswith("https://mapsurvey.org/for-planners/"))

        two = self._ld_blocks(c.get("/alternatives/maptionnaire/").content.decode())
        bc2 = next(b for b in two if b.get("@type") == "BreadcrumbList")
        items2 = bc2["itemListElement"]
        self.assertEqual([i["position"] for i in items2], [1, 2, 3])
        # Change market-guide-landscape-hub: the parent crumb is the market guide.
        self.assertEqual([i["name"] for i in items2], ["Home", "Participatory mapping tools", "Maptionnaire Alternative"])
        self.assertEqual(items2[1]["item"], "https://mapsurvey.org/participatory-mapping-tools/")

    def test_sitewide_schema_preserved_on_landing(self):
        """
        GIVEN a landing page with per-page structured data
        WHEN rendered
        THEN the site-wide SoftwareApplication + Organization JSON-LD are still present
        """
        blocks = self._ld_blocks(Client().get("/civic-engagement/").content.decode())
        types = {b.get("@type") for b in blocks}
        self.assertIn("SoftwareApplication", types)
        self.assertIn("Organization", types)
        self.assertIn("FAQPage", types)
        self.assertIn("BreadcrumbList", types)

    def test_faq_questions_are_page_specific(self):
        """
        GIVEN two different landing pages
        WHEN their FAQ question sets are compared
        THEN they are not identical (guards against thin duplicated FAQ markup)
        """
        from survey.seo_landings import get_landing
        a = {qa.q for qa in get_landing("participatory_budgeting").faq}
        b = {qa.q for qa in get_landing("maptionnaire_alternative").faq}
        self.assertNotEqual(a, b)

    def test_answer_with_apostrophe_is_json_safe(self):
        """
        GIVEN an FAQ answer containing an apostrophe
        WHEN the FAQPage JSON-LD is built
        THEN it still parses as valid JSON with the answer intact
        """
        from survey.seo_landings import build_faqpage_jsonld, QA
        raw = build_faqpage_jsonld((QA("Q?", "You don't need an account — it's free."),))
        data = json.loads(raw)  # must not raise
        self.assertEqual(
            data["mainEntity"][0]["acceptedAnswer"]["text"],
            "You don't need an account — it's free.",
        )


class SeoLandingRegistryTest(TestCase):
    """The seo_landings registry is the single source of truth for sitemap/robots."""

    def test_sitemap_lists_every_landing_with_crawl_hints(self):
        """
        GIVEN the SEO landing registry
        WHEN sitemap.xml is fetched
        THEN every registry path is present with lastmod/changefreq/priority
        """
        from survey.seo_landings import SEO_LANDINGS
        sm = Client().get("/sitemap.xml")
        body = sm.content.decode()
        for landing in SEO_LANDINGS:
            self.assertIn(f"<loc>http://testserver{landing.path}</loc>", body)
            self.assertIn(f"<lastmod>{landing.lastmod}</lastmod>", body)
        self.assertIn("<changefreq>", body)
        self.assertIn("<priority>", body)

    def test_robots_allows_every_landing(self):
        """
        GIVEN the SEO landing registry
        WHEN robots.txt is fetched
        THEN every registry path has an Allow rule
        """
        from survey.seo_landings import SEO_LANDINGS
        rb = Client().get("/robots.txt").content.decode()
        for landing in SEO_LANDINGS:
            self.assertIn(f"Allow: {landing.path}", rb)

    def test_registry_url_names_resolve_and_match_paths(self):
        """
        GIVEN the SEO landing registry
        WHEN each url_name is reversed
        THEN it resolves to the registry path (registry and routes stay in sync)
        """
        from django.urls import reverse
        from survey.seo_landings import SEO_LANDINGS
        for landing in SEO_LANDINGS:
            self.assertEqual(reverse(landing.url_name), landing.path)
