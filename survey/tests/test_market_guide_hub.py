"""Tests for the `market-guide-hub` capability (openspec/specs/market-guide-hub/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from unittest.mock import patch
import json
import re


class MarketGuideHubTest(TestCase):
    """Change market-guide-landscape-hub (#259): /participatory-mapping-tools/ is the buyer's
    guide above the /alternatives/ pages, and those pages render their tables from the registry."""

    import re as _re
    PATH = "/participatory-mapping-tools/"
    _LD_RE = _re.compile(r'<script type="application/ld\+json">(.*?)</script>', _re.S)

    @staticmethod
    def _visible_words(body):
        import re
        text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", body, flags=re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        return [w for w in text.split() if any(ch.isalpha() for ch in w)]

    def test_page_renders_the_contract(self):
        """
        GIVEN the hub landing
        WHEN rendered
        THEN it carries the H1, every vendor and category from the registry, the gaps block,
             the sources list, links to every alternatives page, the pricing and sibling
             sections, a FAQPage block and at least 1,500 visible words
        """
        import json
        from survey.vendors import CATEGORIES, VENDORS
        resp = Client().get(self.PATH)
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertRegex(body, r"<h1[^>]*>[^<]*Participatory mapping tools")
        table = body[body.index('<table class="cmp guide-table">'):body.index("</table>")]
        for vendor in VENDORS:
            self.assertIn(vendor.name, table)
            self.assertIn(f'id="row-{vendor.key}"', table)
        for category in CATEGORIES:
            self.assertIn(category.title, body)
        gaps = body[body.index('id="gaps"'):body.index('id="sources"')]
        for word in ("participatory budgeting", "SSO", "United States", "falls short"):
            self.assertIn(word, gaps)
        self.assertNotIn("EU-hosted", body)
        self.assertNotIn("Frankfurt", body)
        for href in ('href="/alternatives/maptionnaire/"', 'href="/alternatives/social-pinpoint/"',
                     'href="/alternatives/metroquest/"', 'href="/pro/"'):
            self.assertIn(href, body)
        for anchor in ('id="pricing"', 'id="related"', 'id="table"', 'id="criteria"', 'id="categories"'):
            self.assertIn(anchor, body)
        self.assertIn("$49", body)
        self.assertIn("$490", body)
        blocks = [json.loads(m) for m in self._LD_RE.findall(body)]
        self.assertEqual(sum(1 for b in blocks if b.get("@type") == "FAQPage"), 1)
        self.assertGreaterEqual(len(self._visible_words(body)), 1500)

    def test_sources_and_verified_dates_are_rendered(self):
        """
        GIVEN every vendor's facts carry a source URL and a date
        WHEN the hub is rendered
        THEN every distinct source URL is a link inside the sources section and the vendor's
             earliest verified date sits in its table row, and every cell carries its source host
        """
        from survey.vendors import VENDORS
        body = Client().get(self.PATH).content.decode()
        sources = body[body.index('id="sources"'):body.index('id="compare"')]
        table = body[body.index('<table class="cmp guide-table">'):body.index("</table>")]
        for vendor in VENDORS:
            with self.subTest(vendor=vendor.key):
                self.assertIn(f'id="src-{vendor.key}"', sources)
                for s in vendor.sources:
                    self.assertIn(f'href="{s["url"]}"', sources)
                row = table[table.index(f'id="row-{vendor.key}"'):]
                row = row[:row.index("</tr>")]
                self.assertIn(f'href="#src-{vendor.key}">{vendor.verified_on}</a>', row)
                for fact in vendor.facts.values():
                    self.assertIn(f"Source: {fact.host}, read {fact.verified}", row)

    def test_registry_drives_sitemap_robots_and_hreflang(self):
        """
        GIVEN the hub is a registry landing with lastmod 2026-10-06
        WHEN sitemap.xml, robots.txt and the page are fetched
        THEN the sitemap lists it with that lastmod, robots allows it, and x-default equals the canonical
        """
        c = Client()
        self.assertIn(f"<loc>http://testserver{self.PATH}</loc><lastmod>2026-10-06</lastmod>",
                      c.get("/sitemap.xml").content.decode())
        self.assertIn(f"Allow: {self.PATH}", c.get("/robots.txt").content.decode())
        body = c.get(self.PATH).content.decode()
        self.assertIn('<link rel="canonical" href="https://mapsurvey.org/participatory-mapping-tools/">', body)
        self.assertIn('hreflang="x-default" href="https://mapsurvey.org/participatory-mapping-tools/"', body)

    def test_alternatives_index_redirects_to_the_hub(self):
        """
        GIVEN /alternatives/ was a breadcrumb parent with no page behind it
        WHEN it is requested
        THEN it is a permanent redirect to the hub
        """
        resp = Client().get("/alternatives/")
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp["Location"], self.PATH)

    def test_alternatives_pages_link_up_and_render_from_the_registry(self):
        """
        GIVEN the three /alternatives/ pages
        WHEN each is rendered
        THEN its body links to the hub, its table carries the vendor's registry cells with their
             source hosts, its note links the vendor's source pages, and the BreadcrumbList names
             the hub as the parent
        """
        import json
        from django.utils.html import escape
        from survey.seo_landings import SEO_LANDINGS
        from survey.vendors import CRITERIA, vendor_for_landing
        for landing in [l for l in SEO_LANDINGS if l.path.startswith("/alternatives/")]:
            with self.subTest(path=landing.path):
                vendor = vendor_for_landing(landing.key)
                body = Client().get(landing.path).content.decode()
                self.assertIn('href="/participatory-mapping-tools/"', body)
                for c in CRITERIA:
                    fact = vendor.facts[c.key]
                    self.assertIn(escape(fact.text), body)
                    self.assertIn(f"Source: {fact.host}, read {fact.verified}", body)
                for s in vendor.sources:
                    self.assertIn(f'href="{s["url"]}"', body)
                self.assertIn(f"read on {vendor.verified_on}", body)
                blocks = [json.loads(m) for m in self._LD_RE.findall(body)]
                crumbs = next(b for b in blocks if b.get("@type") == "BreadcrumbList")
                self.assertEqual(crumbs["itemListElement"][1]["item"],
                                 "https://mapsurvey.org/participatory-mapping-tools/")

    def test_maptionnaire_page_no_longer_claims_eu_hosting(self):
        """
        GIVEN the Maptionnaire page carried "EU-hosted" and "Frankfurt" fourteen months after
              production moved to Oregon
        WHEN it is rendered from the registry
        THEN the hosting cell says AWS in the US and Ireland for Maptionnaire, our own cell names
             the United States, and neither false claim remains
        """
        body = Client().get("/alternatives/maptionnaire/").content.decode()
        self.assertNotIn("Frankfurt", body)
        self.assertNotIn("EU-hosted", body)
        self.assertIn("AWS, US and Ireland", body)
        self.assertIn("United States", body)
        self.assertNotIn("prices listed on the vendor", body)

    def test_social_pinpoint_page_agrees_with_itself_on_export(self):
        """
        GIVEN the Social Pinpoint page said "no GeoJSON export" in a card and listed GeoJSON in
              its table
        WHEN it is rendered from the registry
        THEN GeoJSON appears in the export cell and the contradiction is gone
        """
        body = Client().get("/alternatives/social-pinpoint/").content.decode()
        self.assertIn("XLS, CSV, PDF or GeoJSON", body)
        self.assertNotIn("no GeoJSON export", body)
        self.assertNotIn("there's no GeoJSON", body)

    def test_a_registry_edit_reaches_both_pages(self):
        """
        GIVEN one Fact in the registry
        WHEN its text is patched
        THEN the hub and the alternatives page both render the new text
        """
        from unittest.mock import patch
        from survey import vendors
        from survey.vendors import Fact
        mt = vendors.get_vendor("maptionnaire")
        patched = dict(mt.facts)
        patched["export"] = Fact("PATCHED EXPORT TEXT", mt.facts["export"].source, mt.facts["export"].verified)
        with patch.dict(mt.facts, patched):
            self.assertIn("PATCHED EXPORT TEXT", Client().get(self.PATH).content.decode())
            self.assertIn("PATCHED EXPORT TEXT", Client().get("/alternatives/maptionnaire/").content.decode())

    def test_category_pages_and_footer_link_down(self):
        """
        GIVEN the sibling partial and the landing footer
        WHEN a category page is rendered
        THEN its related block and its footer both link to the hub, and the hub's own related
             block does not link to itself
        """
        body = Client().get("/community-engagement-platform/").content.decode()
        related = body[body.index('id="related"'):]
        related = related[:related.index("</section>")]
        self.assertIn('href="/participatory-mapping-tools/"', related)
        footer = body[body.index("landing-footer"):]
        self.assertIn('href="/participatory-mapping-tools/"', footer)
        nav = body[body.index('class="landing-nav__dd-menu"'):body.index("</ul>", body.index('class="landing-nav__dd-menu"'))]
        self.assertIn('href="/participatory-mapping-tools/"', nav)  # Solutions dropdown, on every page
        home = Client().get("/").content.decode()
        self.assertIn('href="/participatory-mapping-tools/"', home[home.index('class="landing-nav__dd-menu"'):])
        hub = Client().get(self.PATH).content.decode()
        hub_related = hub[hub.index('id="related"'):]
        hub_related = hub_related[:hub_related.index("</section>")]
        self.assertNotIn('href="/participatory-mapping-tools/"', hub_related)
        self.assertIn('href="/community-engagement-platform/"', hub_related)
