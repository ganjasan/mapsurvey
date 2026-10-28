"""Tests for the `brand-structured-data` capability (openspec/specs/brand-structured-data/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from unittest import mock
import json
import re
from django.conf import settings


class OrganizationSchemaTest(TestCase):
    """Brand-entity Organization JSON-LD with sameAs on the landing pages."""

    def test_homepage_has_organization_schema_with_sameas(self):
        """
        GIVEN the landing page
        WHEN rendered
        THEN it includes an Organization JSON-LD block with sameAs linking our profiles
        """
        import json, re
        html = Client().get("/").content.decode()
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        types = []
        org = None
        for b in blocks:
            d = json.loads(b)   # must be valid JSON
            types.append(d.get("@type"))
            if d.get("@type") == "Organization":
                org = d
        self.assertIn("Organization", types)
        self.assertIn("SoftwareApplication", types)
        self.assertEqual(org["name"], "Mapsurvey")
        self.assertTrue(any("github.com" in s for s in org["sameAs"]))
        self.assertTrue(any("participedia.net" in s for s in org["sameAs"]))


class BrandEntityStructuredDataTest(TestCase):
    """Change brand-entity (#443): Organization, SoftwareApplication and WebSite JSON-LD as one
    linked entity, built in survey/brand.py, with the sameAs profiles from one registry."""

    import re as _re
    _LD_RE = _re.compile(r'<script type="application/ld\+json">(.*?)</script>', _re.S)
    ORG = {"@id": "https://mapsurvey.org/#organization"}

    def _nodes(self, path):
        resp = Client().get(path)
        self.assertEqual(resp.status_code, 200, path)
        return [json.loads(b) for b in self._LD_RE.findall(resp.content.decode())]

    def _one(self, nodes, type_):
        found = [n for n in nodes if n.get("@type") == type_]
        self.assertEqual(len(found), 1, f"expected one {type_}, got {len(found)}")
        return found[0]

    def test_marketing_page_links_software_to_organization(self):
        """
        GIVEN a marketing landing page
        WHEN an anonymous visitor opens it
        THEN it carries one Organization with the canonical @id and one SoftwareApplication
             published and authored by that organisation, described as a hosted business app
        """
        nodes = self._nodes("/for-planners/")
        org = self._one(nodes, "Organization")
        app = self._one(nodes, "SoftwareApplication")
        self.assertEqual(org["@id"], self.ORG["@id"])
        self.assertEqual(org["url"], "https://mapsurvey.org/")
        self.assertEqual(app["@id"], "https://mapsurvey.org/#software")
        self.assertEqual(app["publisher"], self.ORG)
        self.assertEqual(app["author"], self.ORG)
        self.assertEqual(app["applicationCategory"], "BusinessApplication")
        self.assertNotIn("Linux", app["operatingSystem"])
        self.assertNotIn("Docker", app["operatingSystem"])

    def test_homepage_pair_names_the_site(self):
        """
        GIVEN the English and the Russian homepage
        WHEN an anonymous visitor opens each
        THEN each carries one WebSite node named Mapsurvey, alternate name mapsurvey.org,
             on the canonical URL and published by the organisation
        """
        for path in ("/", "/ru/"):
            site = self._one(self._nodes(path), "WebSite")
            self.assertEqual(site["name"], "Mapsurvey", path)
            self.assertIn("mapsurvey.org", site["alternateName"], path)
            self.assertEqual(site["url"], "https://mapsurvey.org/", path)
            self.assertEqual(site["publisher"], self.ORG, path)

    def test_landing_pages_do_not_repeat_the_site_node(self):
        """
        GIVEN a landing page other than the homepage pair
        WHEN it is rendered
        THEN it carries no WebSite node
        """
        self.assertFalse([n for n in self._nodes("/for-planners/") if n.get("@type") == "WebSite"])

    def test_registry_profiles_reach_sameas(self):
        """
        GIVEN a profile added to the brand registry
        WHEN a marketing page is rendered
        THEN Organization.sameAs lists it after the public repository
        """
        from unittest import mock
        from survey import brand
        extra = "https://www.wikidata.org/wiki/Q0"
        with mock.patch.object(brand, "PROFILES", brand.PROFILES + [extra]):
            org = self._one(self._nodes("/for-planners/"), "Organization")
        self.assertIn(extra, org["sameAs"])
        self.assertEqual(org["sameAs"][0], settings.GITHUB_REPO_URL)

    def test_registry_entries_are_well_formed(self):
        """
        GIVEN the brand profile registry
        WHEN its entries are checked
        THEN each is an absolute https URL off mapsurvey.org and none repeats
        """
        from urllib.parse import urlparse
        from survey import brand
        self.assertEqual(len(brand.PROFILES), len(set(brand.PROFILES)))
        for url in brand.PROFILES:
            parts = urlparse(url)
            self.assertEqual(parts.scheme, "https", url)
            self.assertTrue(parts.netloc, url)
            self.assertFalse(parts.netloc.endswith("mapsurvey.org"), url)

    def test_script_cannot_be_closed_by_a_value(self):
        """
        GIVEN a node whose text contains a closing script tag
        WHEN the brand tag serialises it
        THEN the output has a single closing tag and the value survives a JSON round trip
        """
        from survey.templatetags.brand_tags import _script
        html = _script({"@type": "Thing", "name": "a </script><b> & c"})
        self.assertEqual(html.count("</script>"), 1)
        payload = self._LD_RE.findall(html)[0]
        self.assertEqual(json.loads(payload)["name"], "a </script><b> & c")
