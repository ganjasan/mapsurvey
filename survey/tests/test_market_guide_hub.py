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
        THEN it carries the H1, the verdict before the method, every vendor and category from
             the registry, the right-pick block then the better-fit block with the gaps, the
             sources list, links to every alternatives page, the pricing and sibling sections,
             a FAQPage block and at least 1,500 visible words
        """
        import json
        from django.utils.html import escape
        from survey.vendors import CATEGORIES, VENDORS
        resp = Client().get(self.PATH)
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertRegex(body, r"<h1[^>]*>[^<]*Participatory mapping tools")
        self.assertLess(body.index('id="verdict"'), body.index('id="how-to-read"'))
        table = body[body.index('<table class="cmp guide-table"'):body.index("</table>")]
        for vendor in VENDORS:
            self.assertIn(escape(vendor.name), table)
            self.assertIn(f'id="row-{vendor.key}"', table)
        for category in CATEGORIES:
            self.assertIn(category.title, body)
        self.assertLess(body.index('id="right-pick"'), body.index('id="better-fit"'))
        gaps = body[body.index('id="better-fit"'):body.index('id="sources"')]
        for word in ("participatory budgeting", "SSO", "United States"):
            self.assertIn(word, gaps)
        self.assertNotIn("EU-hosted", body)
        self.assertNotIn("Frankfurt", body)
        self.assertNotIn("not a sales page", body)
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
        table = body[body.index('<table class="cmp guide-table"'):body.index("</table>")]
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
        GIVEN the hub is a registry landing with a lastmod
        WHEN sitemap.xml, robots.txt and the page are fetched
        THEN the sitemap lists it with that lastmod, robots allows it, and x-default equals the canonical
        """
        from survey.seo_landings import SEO_LANDINGS
        lastmod = next(l.lastmod for l in SEO_LANDINGS if l.key == "participatory_mapping_tools")
        c = Client()
        self.assertIn(f"<loc>http://testserver{self.PATH}</loc><lastmod>{lastmod}</lastmod>",
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


class MarketGuideFiltersTest(TestCase):
    """Change market-guide-filters (#651): vendor links, who is behind each tool, the filter bar
    over a table that stays complete without JavaScript, and the ItemList structured data."""

    PATH = "/participatory-mapping-tools/"
    _LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)

    def _body(self):
        return Client().get(self.PATH).content.decode()

    @staticmethod
    def _row(body, key):
        row = body[body.index(f'id="row-{key}"'):]
        return row[:row.index("</tr>")]

    def test_every_tool_name_links_to_the_vendor_site(self):
        """
        GIVEN only three of 22 names used to be links, and those pointed at our own pages
        WHEN the hub is rendered
        THEN every table row and every category entry links the name to the vendor's own URL,
             and the "vs Mapsurvey" link stays only where an alternatives page exists
        """
        from django.utils.html import escape
        from survey.vendors import VENDORS
        body = self._body()
        cats = body[body.index('id="categories"'):body.index('id="criteria"')]
        for vendor in VENDORS:
            with self.subTest(vendor=vendor.key):
                link = f'href="{escape(vendor.url)}" rel="noopener" target="_blank">{escape(vendor.name)}</a>'
                self.assertIn(link, self._row(body, vendor.key))
                self.assertIn(link, cats)
                self.assertEqual("vs Mapsurvey in detail" in self._row(body, vendor.key),
                                 bool(vendor.landing_key))

    def test_rows_carry_the_filter_facets_and_the_backing_cell(self):
        """
        GIVEN each vendor's category, region, backing kind and flags in the registry
        WHEN the hub is rendered
        THEN its row carries them as data attributes, and the "Who is behind it" cell shows the
             backing fact with its source host and date
        """
        from django.utils.html import escape
        from survey.vendors import VENDORS
        body = self._body()
        self.assertIn('<th role="columnheader">Who is behind it</th>', body)
        for vendor in VENDORS:
            with self.subTest(vendor=vendor.key):
                row = self._row(body, vendor.key)
                for attr in (f'data-category="{vendor.category}"', f'data-region="{vendor.region}"',
                             f'data-backing="{vendor.backing_kind}"', f'data-has="{vendor.flag_keys}"'):
                    self.assertIn(attr, row)
                self.assertIn(escape(vendor.backing.text), row)
                # The phone layout labels every cell from data-label.
                self.assertEqual(row.count('role="cell" data-label="'), len(vendor.facts) + 2)
                self.assertIn(f"Source: {vendor.backing.host}, read {vendor.backing.verified}", row)

    def test_filter_bar_is_hidden_until_the_script_runs(self):
        """
        GIVEN crawlers and assistants read the page without running JavaScript
        WHEN the hub is rendered
        THEN every vendor row is in the HTML and none is hidden, the filter bar is rendered with
             the hidden attribute, every chip value is one some vendor has, and the script is loaded
        """
        from survey.vendors import VENDORS, hub_context
        body = self._body()
        self.assertIn('<div class="guide-filters" id="guide-filters" hidden>', body)
        self.assertIn("js/market_guide_filters", body)
        for vendor in VENDORS:
            self.assertNotIn(" hidden", self._row(body, vendor.key).split(">")[0])
        for group in hub_context()["filter_groups"]:
            self.assertIn(f'data-param="{group["param"]}"', body)
            for chip in group["chips"]:
                self.assertGreater(chip["count"], 0)
                self.assertIn(f'data-value="{chip["value"]}"', body)

    def test_verdict_names_public_and_non_profit_tools_from_the_registry(self):
        """
        GIVEN backing kinds in the registry
        WHEN the hub is rendered
        THEN the public-body scenario names every vendor whose backing is public, non-profit or
             academic, links each to its row, and no company's product
        """
        from survey.vendors import VENDORS
        body = self._body()
        block = body[body.index('id="verdict-public"'):body.index('id="verdict-selfhost"')]
        for vendor in VENDORS:
            with self.subTest(vendor=vendor.key):
                listed = f'href="#row-{vendor.key}"' in block
                self.assertEqual(listed, vendor.backing_kind != "commercial")
        self.assertIn('data-guide-filter="backing=public,nonprofit,academic"', block)

    def test_itemlist_names_every_tool(self):
        """
        GIVEN a crawler reads structured data before the table
        WHEN the hub is rendered
        THEN one ItemList block lists every vendor in registry order with its name and URL
        """
        from survey.vendors import VENDORS
        blocks = [json.loads(m) for m in self._LD_RE.findall(self._body())]
        lists = [b for b in blocks if b.get("@type") == "ItemList"]
        self.assertEqual(len(lists), 1)
        items = lists[0]["itemListElement"]
        self.assertEqual(lists[0]["numberOfItems"], len(VENDORS))
        self.assertEqual([(i["name"], i["url"]) for i in items], [(v.name, v.url) for v in VENDORS])

    def test_registry_refuses_a_vendor_without_backing_or_with_an_unknown_country(self):
        """
        GIVEN the import-time validator
        WHEN a vendor names a country outside COUNTRY_REGION or has no backing Fact
        THEN validation raises
        """
        import dataclasses
        from survey import vendors
        bad_country = dataclasses.replace(vendors.MAPSURVEY, key="x1", country="Atlantis")
        no_backing = dataclasses.replace(vendors.MAPSURVEY, key="x2", backing=None)
        for bad in (bad_country, no_backing):
            with self.subTest(vendor=bad.key):
                with patch.object(vendors, "VENDORS", vendors.VENDORS + (bad,)), \
                        patch.object(vendors, "_BY_KEY", {**vendors._BY_KEY, bad.key: bad}):
                    with self.assertRaises((ValueError, AttributeError)):
                        vendors._validate()
