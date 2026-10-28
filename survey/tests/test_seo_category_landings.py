"""Tests for the `seo-category-landings` capability (openspec/specs/seo-category-landings/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.conf import settings
import os


class SeoCategoryLandingContractTest(TestCase):
    """Change seo-landings-rewrite (#251): the four category landings carry the content a page
    needs to rank for its own term — definition, screenshots, a dated comparison against two
    incumbents, the shared pricing block, sibling links, 1,500+ words — and no hosting claim
    the trust page contradicts."""

    import re as _re
    _DROP_RE = _re.compile(r"<(script|style|nav|footer)\b.*?</\1>", _re.S | _re.I)
    _TAG_RE = _re.compile(r"<[^>]+>")

    PAGES = {
        "/community-engagement-platform/": ("Community Engagement Platform", ("Social Pinpoint", "EngagementHQ"), "/for-government/"),
        "/public-consultation-software/": ("Public Consultation Software", ("Citizen Space", "Commonplace"), "/for-government/"),
        "/civic-engagement/": ("Civic engagement", ("Go Vocal", "Consul"), "/for-planners/"),
        "/participatory-budgeting/": ("Participatory budgeting", ("Decidim", "Balancing Act"), "/for-government/"),
        # Change citizen-engagement-landing (#252): the fifth page under the same contract.
        "/citizen-engagement-platform/": ("Citizen Engagement Platform", ("Go Vocal", "Citizen Space"), "/for-government/"),
    }
    SIBLINGS = ("/community-engagement-platform/", "/public-consultation-software/",
                "/civic-engagement/", "/participatory-budgeting/", "/citizen-engagement-platform/")

    def _in(self, needle, hay, msg=""):
        self.assertTrue(needle in hay, f"{msg}: {needle!r} missing")

    def _not_in(self, needle, hay, msg=""):
        self.assertFalse(needle in hay, f"{msg}: {needle!r} present")

    def _visible_words(self, html):
        import html as html_mod
        body = self._DROP_RE.sub(" ", html)
        text = html_mod.unescape(self._TAG_RE.sub(" ", body))
        return [w for w in text.split() if any(c.isalpha() for c in w)]

    def test_every_category_page_carries_the_contract(self):
        """
        GIVEN the four category landing pages
        WHEN each is rendered
        THEN it has the head-term H1, a dated comparison table naming its two incumbents,
             the four demo screenshots, the pricing block with a /pro/ link,
             the three sibling links plus its audience page, and 1,500+ visible words
        """
        c = Client()
        for path, (h1, incumbents, audience) in self.PAGES.items():
            resp = c.get(path)
            self.assertEqual(resp.status_code, 200, path)
            html = resp.content.decode()
            self.assertRegex(html, r"<h1[^>]*>[^<]*%s" % h1.split()[0], path)
            self._in(h1, html, path)
            for name in incumbents:
                self._in(name, html, f"{path}: comparison table must name {name}")
            self._in('class="cmp"', html, path)
            self._in("as of October 2026", html, f"{path}: comparison note must be dated")
            for shot in ("build", "collect", "analyze", "share"):
                self.assertRegex(html, rf"img/landing/{shot}\.(?:[0-9a-f]+\.)?webp", f"{path}: screenshot {shot}")
            self._in('id="pricing"', html, path)
            self._in("$49", html, path)
            self._in("$490", html, path)
            self._in('href="/pro/"', html, path)
            self._in('id="related"', html, path)
            for sib in self.SIBLINGS:
                if sib != path:
                    self._in(f'href="{sib}"', html, f"{path}: sibling link {sib}")
            self._in(f'href="{audience}"', html, path)
            words = self._visible_words(html)
            self.assertGreaterEqual(len(words), 1500, f"{path}: {len(words)} visible words")

    def test_sibling_block_never_links_to_itself(self):
        """
        GIVEN the shared sibling-links partial
        WHEN /civic-engagement/ is rendered
        THEN the block between id="related" and the next section links to the other three
             category pages and not to /civic-engagement/
        """
        html = Client().get("/civic-engagement/").content.decode()
        start = html.index('id="related"')
        end = html.index("</section>", start)
        block = html[start:end]
        self._not_in('href="/civic-engagement/"', block, "")
        for sib in ("/community-engagement-platform/", "/public-consultation-software/",
                    "/participatory-budgeting/", "/citizen-engagement-platform/", "/for-planners/"):
            self._in(f'href="{sib}"', block, "")

    def test_price_lives_in_the_partial_only(self):
        """
        GIVEN the Pro price must be editable in one place (change pricing-page moved it to the
              shared plan cards)
        WHEN every template of the survey and billing apps is read from disk
        THEN only partials/_plan_cards.html contains the figure
        """
        import os
        from django.conf import settings
        holder = os.path.join(settings.BASE_DIR, "survey", "templates", "partials", "_plan_cards.html")
        for app in ("survey", "billing"):
            for root, _dirs, files in os.walk(os.path.join(settings.BASE_DIR, app, "templates")):
                for name in files:
                    path = os.path.join(root, name)
                    if path == holder or not name.endswith((".html", ".txt")):
                        continue
                    with open(path) as fh:
                        self.assertFalse("$49" in fh.read(), f"{path}: the Pro figure belongs in _plan_cards.html only")
        with open(holder) as fh:
            self.assertIn("$49", fh.read())

    def test_no_eu_hosting_claims_on_category_pages(self):
        """
        GIVEN production runs in Render's Oregon region
        WHEN the four category pages are rendered
        THEN none claims EU hosting or Frankfurt,
             and the community-engagement page states the United States location
        """
        c = Client()
        for path in self.PAGES:
            html = c.get(path).content.decode()
            for claim in ("EU-hosted", "Frankfurt", "hosted in the EU", "Data stays in the EU", "EU, Frankfurt"):
                self._not_in(claim, html, f"{path}: {claim!r}")
        self.assertIn("United States", c.get("/community-engagement-platform/").content.decode())

    def test_pb_page_states_its_scope(self):
        """
        GIVEN participatory budgeting has a vote-and-allocate step Mapsurvey does not do
        WHEN /participatory-budgeting/ is rendered
        THEN it says so in plain words
        """
        html = Client().get("/participatory-budgeting/").content.decode()
        self._in("not a budget-allocation", html, "")

    def test_titles_and_descriptions_for_click_through(self):
        """
        GIVEN the five pages whose titles were rewritten for CTR
        WHEN each is rendered
        THEN the title starts with the head term, the description is at most 160 characters,
             and the Social Pinpoint page names drawing, point markers and quote-only pricing
        """
        import html as html_mod
        c = Client()
        starts = {
            "/community-engagement-platform/": "Community Engagement Platform",
            "/public-consultation-software/": "Public Consultation Software",
            "/civic-engagement/": "Civic Engagement",
            "/participatory-budgeting/": "Participatory Budgeting",
            "/alternatives/social-pinpoint/": "Social Pinpoint Alternative",
            "/citizen-engagement-platform/": "Citizen Engagement Platform",
        }
        for path, start in starts.items():
            html = c.get(path).content.decode()
            title = self._re.search(r"<title>(.*?)</title>", html, self._re.S).group(1).strip()
            self.assertTrue(title.startswith(start), f"{path}: {title!r}")
            desc = self._re.search(r'<meta name="description" content="(.*?)"', html, self._re.S).group(1)
            self.assertLessEqual(len(html_mod.unescape(desc)), 160, f"{path}: {len(desc)} chars")
        sp = c.get("/alternatives/social-pinpoint/").content.decode()
        title = self._re.search(r"<title>(.*?)</title>", sp, self._re.S).group(1)
        self.assertRegex(title, r"[Ll]ines|[Aa]reas|[Dd]raw")
        desc = self._re.search(r'<meta name="description" content="(.*?)"', sp, self._re.S).group(1)
        self.assertIn("point markers", desc)
        self.assertIn("quote", desc)

    def test_sitemap_lastmod_bumped_for_rewritten_pages(self):
        """
        GIVEN the five rewritten entries carry the ship date
        WHEN sitemap.xml is fetched
        THEN each of them is listed with lastmod 2026-10-06
        """
        body = Client().get("/sitemap.xml").content.decode()
        for path in ("/community-engagement-platform/", "/public-consultation-software/",
                     "/civic-engagement/", "/participatory-budgeting/", "/alternatives/social-pinpoint/",
                     "/citizen-engagement-platform/"):
            self._in(f"<loc>http://testserver{path}</loc><lastmod>2026-10-06</lastmod>", body, path)

    def test_faq_answers_variant_queries(self):
        """
        GIVEN Search Console shows cost and council variants for the category terms
        WHEN the registry FAQs are read
        THEN the community page asks about cost and answers with the Pro price,
             and the consultation page names council consultation software
        """
        from survey.seo_landings import get_landing
        cep = get_landing("community_engagement_platform").faq
        cost = next(qa for qa in cep if "cost" in qa.q.lower())
        self.assertIn("$49", cost.a)
        pcs = get_landing("public_consultation_software").faq
        self.assertTrue(any("council consultation software" in qa.q.lower() for qa in pcs))
