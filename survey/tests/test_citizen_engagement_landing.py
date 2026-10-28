"""Tests for the `citizen-engagement-landing` capability (openspec/specs/citizen-engagement-landing/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.utils import timezone
from survey.models import Story
from django.conf import settings
import os


class CitizenEngagementLandingTest(TestCase):
    """Change citizen-engagement-landing (#252): the buyer's page answers the procurement
    questions Search Console shows, names no competitor price, and the three overlapping pages
    (community = product, civic = methods, citizen = buyer) link to each other in body copy."""

    import re as _re
    PATH = "/citizen-engagement-platform/"

    OWN_PRICES = {"$0", "$49", "$490"}

    def test_no_competitor_price_figure_on_any_landing(self):
        """
        GIVEN the owner rule (2026-10-06, issues #253/#259) that no other vendor's price
              figure is published: pricing model, free tier and "listed or on request" only
        WHEN every landing template in the registry and every registry FAQ answer is read
        THEN the only currency figures are Mapsurvey's own ($0, $49, $490)
        """
        import os
        from django.conf import settings
        from survey.seo_landings import SEO_LANDINGS
        figure = self._re.compile(r"[£$€]\s?\d(?:[\d,.]*\d)?")
        base = os.path.join(settings.BASE_DIR, "survey", "templates")
        for landing in SEO_LANDINGS:
            with open(os.path.join(base, landing.template)) as fh:
                found = set(figure.findall(fh.read()))
            self.assertFalse(found - self.OWN_PRICES, f"{landing.template}: {found}")
            for qa in landing.faq:
                found = set(figure.findall(qa.a))
                self.assertFalse(found - self.OWN_PRICES, f"{landing.key} FAQ {qa.q!r}: {found}")
        # Change market-guide-landscape-hub: the vendor registry and the hub it renders are under
        # the same rule, so a figure in a Fact.text fails here, not on a reader's screen.
        from survey.vendors import VENDORS
        for vendor in VENDORS:
            for fact in list(vendor.facts.values()) + [e.theirs for e in vendor.extras]:
                found = set(figure.findall(fact.text))
                self.assertFalse(found - self.OWN_PRICES, f"vendors.py {vendor.key}: {found}")
        body = Client().get("/participatory-mapping-tools/").content.decode()
        found = set(figure.findall(body))
        self.assertFalse(found - self.OWN_PRICES, f"hub page: {found}")

    def test_faq_answers_the_procurement_questions(self):
        """
        GIVEN Search Console shows free-trial, affordability, data-ownership and uptime questions
        WHEN the registry FAQ is read
        THEN one question each covers them, and the uptime answer quotes no percentage
        """
        from survey.seo_landings import get_landing
        faq = get_landing("citizen_engagement_platform").faq
        questions = [qa.q.lower() for qa in faq]
        for needle in ("free trial", "small jurisdiction", "owns the data", "uptime"):
            self.assertTrue(any(needle in q for q in questions), needle)
        uptime = next(qa for qa in faq if "uptime" in qa.q.lower())
        self.assertNotIn("%", uptime.a)
        self.assertNotIn("SLA of", uptime.a)

    def test_procurement_section_and_uptime_copy(self):
        """
        GIVEN the page has a procurement section
        WHEN it is rendered
        THEN the section is present with the free-plan, data-ownership and uptime headings,
             and the page quotes no uptime percentage
        """
        html = Client().get(self.PATH).content.decode()
        self.assertIn('id="procurement"', html)
        for heading in ("Free plan, not a trial", "Data ownership and export", "Uptime and support"):
            self.assertIn(heading, html)
        self.assertIsNone(self._re.search(r"9\d(\.\d+)?\s?%", html))

    def test_three_pages_cross_link_in_body_copy(self):
        """
        GIVEN community = product, civic = methods, citizen = buyer
        WHEN the three pages are rendered
        THEN the community and civic pages link to the citizen page before the sibling block,
             and the citizen page links to both in its definition section
        """
        c = Client()
        for path in ("/community-engagement-platform/", "/civic-engagement/"):
            html = c.get(path).content.decode()
            body = html[: html.index('id="related"')]
            self.assertIn('href="/citizen-engagement-platform/"', body, path)
        html = c.get(self.PATH).content.decode()
        definition = html[html.index('class="cat-def"'): html.index("How it works")]
        self.assertIn('href="/community-engagement-platform/"', definition)
        self.assertIn('href="/civic-engagement/"', definition)

    def test_sibling_block_excludes_itself(self):
        """
        GIVEN the shared sibling partial
        WHEN the citizen page is rendered
        THEN its related block links to the four other category pages and the government
             page, and not to itself
        """
        html = Client().get(self.PATH).content.decode()
        start = html.index('id="related"')
        block = html[start: html.index("</section>", start)]
        self.assertNotIn('href="/citizen-engagement-platform/"', block)
        for sib in ("/community-engagement-platform/", "/public-consultation-software/",
                    "/civic-engagement/", "/participatory-budgeting/", "/for-government/"):
            self.assertIn(f'href="{sib}"', block, sib)

    def test_tagged_story_renders_in_from_the_field(self):
        """
        GIVEN a published story tagged citizen-engagement
        WHEN the citizen page is rendered
        THEN the story title appears inside the From the field block
             and the story's chip links to the page
        """
        from django.utils import timezone
        from survey.topics import chips_for
        story = Story.objects.create(
            title="Parish Dog Bin Census", slug="parish-dog-bins", story_type="results",
            body="<p>Body.</p>", is_published=True, published_date=timezone.now(),
            topics=["citizen-engagement"],
        )
        html = Client().get(self.PATH).content.decode()
        start = html.index('id="from-the-field"')
        block = html[start: html.index("</section>", start)]
        self.assertIn("Parish Dog Bin Census", block)
        self.assertEqual(chips_for(story), [("Citizen engagement", self.PATH)])
