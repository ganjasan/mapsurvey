"""Tests for the `vendor-fact-registry` capability (openspec/specs/vendor-fact-registry/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase


class VendorRegistryTest(TestCase):
    """Change market-guide-landscape-hub (#259): survey/vendors.py is the one source of every
    claim about another vendor — sourced, dated, complete, and free of price figures."""

    def test_every_fact_is_sourced_dated_and_complete(self):
        """
        GIVEN the vendor registry
        WHEN every vendor's facts and extras are inspected
        THEN each criterion has a fact, every source is an https URL, every verified date is an
             ISO date not after today, and every category key exists
        """
        from datetime import date
        from survey.vendors import CATEGORIES, CRITERIA, VENDORS
        categories = {c.key for c in CATEGORIES}
        today = date.today().isoformat()
        for vendor in VENDORS:
            with self.subTest(vendor=vendor.key):
                self.assertIn(vendor.category, categories)
                self.assertEqual(set(vendor.facts), {c.key for c in CRITERIA})
                for fact in list(vendor.facts.values()) + [e.theirs for e in vendor.extras]:
                    self.assertTrue(fact.source.startswith("https://"), fact)
                    self.assertEqual(date.fromisoformat(fact.verified).isoformat(), fact.verified)
                    self.assertLessEqual(fact.verified, today)
                self.assertTrue(vendor.summary and vendor.maker and vendor.url.startswith("https://"))

    def test_not_published_facts_still_carry_a_source(self):
        """
        GIVEN facts whose text is "Not published"
        WHEN they are read
        THEN each still names the page that was read and the date, and at least one exists
        """
        from survey.vendors import VENDORS
        unpublished = [f for v in VENDORS for f in v.facts.values() if f.text == "Not published"]
        self.assertTrue(unpublished)
        for fact in unpublished:
            self.assertTrue(fact.source.startswith("https://"))
            self.assertRegex(fact.verified, r"^\d{4}-\d{2}-\d{2}$")

    def test_every_alternatives_landing_has_a_vendor(self):
        """
        GIVEN the /alternatives/ landings in the seo_landings registry
        WHEN each is looked up in the vendor registry
        THEN a vendor with that landing_key exists, and every landing_key resolves back
        """
        from survey.seo_landings import SEO_LANDINGS, get_landing
        from survey.vendors import VENDORS, vendor_for_landing
        alternatives = [l for l in SEO_LANDINGS if l.path.startswith("/alternatives/")]
        self.assertEqual(len(alternatives), 3)
        for landing in alternatives:
            self.assertIsNotNone(vendor_for_landing(landing.key), landing.key)
        for vendor in VENDORS:
            if vendor.landing_key:
                self.assertEqual(get_landing(vendor.landing_key).template, f"{vendor.landing_key}.html")

    def test_helpers(self):
        """
        GIVEN a vendor with several facts on one page and extras
        WHEN verified_on, sources and compare_rows are read
        THEN the earliest date is reported, sources are distinct URLs in first-seen order with
             hosts stripped of www, and the rows list the criteria before the extras
        """
        from survey.vendors import CRITERIA, compare_rows, get_vendor
        mq = get_vendor("metroquest")
        self.assertEqual(mq.verified_on, min(f.verified for f in mq.facts.values()))
        urls = [s["url"] for s in mq.sources]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertIn("socialpinpoint.com", [s["host"] for s in mq.sources])
        rows = compare_rows(mq)
        self.assertEqual([r["label"] for r in rows[:len(CRITERIA)]], [c.label for c in CRITERIA])
        self.assertEqual(rows[-1]["label"], mq.extras[-1].label)
        self.assertEqual(rows[0]["ours"], get_vendor("mapsurvey").facts["geometry"].text)
