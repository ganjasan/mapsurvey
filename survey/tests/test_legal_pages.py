"""Tests for the `legal-pages` capability (openspec/specs/legal-pages/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client


# --- change dpga-readiness ----------------------------------------------------

class TermsAndPrivacyPagesTest(TestCase):
    """/terms/, /privacy/ redirect, /trust/ ownership block, landing footer, sitemap."""

    def test_terms_page_renders_all_policy_anchors(self):
        """
        GIVEN an anonymous visitor
        WHEN they open /terms/
        THEN the page answers 200 and carries every anchor the DPGA application links to
        """
        response = Client().get('/terms/')
        self.assertEqual(response.status_code, 200)
        for anchor in ('terms', 'acceptable-use', 'prohibited', 'moderation', 'harassment', 'children', 'personal-data', 'contact'):
            self.assertContains(response, f'id="{anchor}"')

    def test_terms_names_csam_first_and_states_commitments(self):
        """
        GIVEN the Terms page
        WHEN its prohibited, moderation and children sections are read
        THEN child sexual abuse material is the first prohibited item, the 2-business-day and same-day times are stated, and accounts are 16+
        """
        html = Client().get('/terms/').content.decode()
        prohibited = html[html.index('id="prohibited"'):html.index('id="detection"')]
        first_item = prohibited[prohibited.index('<li>'):prohibited.index('</li>')]
        self.assertIn('Child sexual abuse material', first_item)
        moderation = html[html.index('id="moderation"'):html.index('id="harassment"')]
        self.assertIn('2 business days', moderation)
        self.assertIn('same day', moderation)
        children = html[html.index('id="children"'):html.index('id="personal-data"')]
        self.assertIn('16 and over', children)
        self.assertIn('konuchovartem@mapsurvey.org', html)

    def test_privacy_redirects_permanently_to_trust(self):
        """
        GIVEN any visitor
        WHEN they request /privacy/
        THEN the response is a 301 to /trust/
        """
        response = Client().get('/privacy/')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], '/trust/')

    def test_sitemap_lists_terms_but_not_privacy(self):
        """
        GIVEN the sitemap
        WHEN /sitemap.xml is requested
        THEN it lists /terms/ and does not list the /privacy/ redirect
        """
        body = Client().get('/sitemap.xml').content.decode()
        self.assertIn('/terms/</loc>', body)
        self.assertNotIn('/privacy/</loc>', body)

    def test_trust_page_has_ownership_block_with_owner_name(self):
        """
        GIVEN the Trust page
        WHEN it is rendered
        THEN it has an ownership block naming Artem Koniukhov, no longer says Konuchov, and links /terms/
        """
        response = Client().get('/trust/')
        self.assertContains(response, 'id="ownership"')
        self.assertContains(response, 'Artem Koniukhov')
        self.assertNotContains(response, 'Artem Konuchov')
        self.assertContains(response, 'href="/terms/"')

    def test_landing_footer_links_legal_pages_and_names_owner(self):
        """
        GIVEN a page built on base_landing.html
        WHEN it is rendered
        THEN the footer links Terms of use and Privacy & Trust and its copyright line names the owner
        """
        response = Client().get('/trust/')
        footer = response.content.decode().split('<footer', 1)[1]
        self.assertIn('href="/terms/"', footer)
        self.assertIn('Privacy & Trust', footer)
        self.assertIn('2021&ndash;', footer)
        self.assertIn('Artem Koniukhov', footer)
