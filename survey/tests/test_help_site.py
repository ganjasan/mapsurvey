"""Tests for the `help-site` capability (openspec/specs/help-site/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
import json
import re
from survey.models import SurveyHeader, Membership
from django.conf import settings
import os
from survey.tests.helpers import _make_org


class HelpSiteLinksTest(TestCase):
    """Product → help centre links (change help-site, #298)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='helpuser', email='help-user@example.com', password='pass',
        )
        org = _make_org('HelpOrg')
        Membership.objects.create(user=self.user, organization=org, role='owner')
        self.survey = SurveyHeader.objects.create(name='help_survey', organization=org)
        self.client.login(username='helpuser', password='pass')

    def test_every_registry_path_is_a_page(self):
        """
        GIVEN the help-link registry
        WHEN each path is looked up under help/src/content/docs/
        THEN a page file exists for it (so a renamed page fails here, not as a dead link)
        """
        import os

        from survey.help_links import HELP_LINKS

        docs = os.path.join(settings.BASE_DIR, 'help', 'src', 'content', 'docs')
        self.assertTrue(os.path.isdir(docs), docs)
        for key, path in HELP_LINKS.items():
            self.assertTrue(path == '' or path.endswith('/'), f'{key}: {path!r} must end with /')
            stem = os.path.join(docs, path.rstrip('/')) if path else docs
            candidates = [stem + '.md', stem + '.mdx', os.path.join(stem, 'index.md'), os.path.join(stem, 'index.mdx')]
            self.assertTrue(any(os.path.isfile(c) for c in candidates), f'{key}: no page for {path!r}')

    def test_help_pages_are_tracked_by_git(self):
        """
        GIVEN a git checkout (skipped elsewhere)
        WHEN the help content directory is listed through git
        THEN its pages are tracked -- the root .gitignore's `docs/` rule once swallowed all of them (#307)
        """
        import os
        import subprocess

        if not os.path.isdir(os.path.join(settings.BASE_DIR, '.git')) and not os.path.isfile(os.path.join(settings.BASE_DIR, '.git')):
            self.skipTest('not a git checkout')
        out = subprocess.run(
            ['git', 'ls-files', '--', 'help/src/content/docs'],
            cwd=settings.BASE_DIR, capture_output=True, text=True, check=True,
        ).stdout.split()
        self.assertGreater(len(out), 30, 'help/src/content/docs pages are not tracked by git')
        ignored = subprocess.run(
            ['git', 'check-ignore', 'help/src/content/docs/faq.md'],
            cwd=settings.BASE_DIR, capture_output=True, text=True,
        )
        self.assertNotEqual(ignored.returncode, 0, 'help/src/content/docs is matched by .gitignore')

    def test_help_menu_links_to_the_help_centre(self):
        """
        GIVEN HELP_SITE_URL is set
        WHEN a signed-in creator opens the editor dashboard
        THEN the "?" menu carries "Help centre" opening the site in a new tab and no #faq link
        """
        with self.settings(HELP_SITE_URL='https://help.example.org'):
            response = self.client.get('/editor/')
        self.assertContains(response, 'href="https://help.example.org/" target="_blank" rel="noopener"')
        self.assertContains(response, 'Help centre')
        self.assertNotContains(response, '#faq')

    def test_help_menu_omits_the_item_when_the_site_is_off(self):
        """
        GIVEN HELP_SITE_URL is empty
        WHEN a signed-in creator opens the editor dashboard
        THEN the "?" menu has no "Help centre" item and no help-site link anywhere
        """
        with self.settings(HELP_SITE_URL=''):
            response = self.client.get('/editor/')
        self.assertContains(response, 'help-nav-icon')
        self.assertNotContains(response, 'Help centre')
        self.assertNotContains(response, 'class="ms-learn-more"')

    def test_learn_more_links_on_the_editor_surfaces(self):
        """
        GIVEN HELP_SITE_URL is set
        WHEN the settings panel, the Share page and the billing page are rendered
        THEN each carries a "Learn more" link to its registry page, opening in a new tab
        """
        from survey.help_links import HELP_LINKS

        base = 'https://help.example.org'
        # The Share page shows the embed section for a published survey only.
        self.survey.status = 'published'
        self.survey.save(update_fields=['status'])
        from billing.tests.helpers import PPG_SETTINGS  # the Pro card needs products on sale

        with self.settings(HELP_SITE_URL=base, **PPG_SETTINGS):
            detail = self.client.get(reverse('editor_survey_settings_panel', args=[self.survey.uuid]))
            share = self.client.get(reverse('editor_survey_share', args=[self.survey.uuid]))
            billing = self.client.get(reverse('org_billing', kwargs={'slug': self.survey.organization.slug}))
        for response, key in ((detail, 'reference_layers'), (share, 'embedding'), (billing, 'pro')):
            self.assertEqual(response.status_code, 200, key)
            self.assertContains(response, f'href="{base}/{HELP_LINKS[key]}" target="_blank" rel="noopener"', msg_prefix=key)

    def test_support_flag_opens_the_chat_for_a_signed_in_creator_only(self):
        """
        GIVEN the chat is configured
        WHEN /?support=1 is requested signed in, signed out, and signed in without the flag
        THEN only the first config carries open_on_load = true
        """
        with self.settings(CHATWOOT_WEBSITE_TOKEN='cwWebsiteToken123'):
            signed_in = self.client.get('/?support=1')
            plain = self.client.get('/')
            self.client.logout()
            anonymous = self.client.get('/?support=1')
        config = lambda r: json.loads(re.search(  # noqa: E731
            r'<script id="support-chat-config" type="application/json">(.*?)</script>', r.content.decode(), re.S,
        ).group(1))
        self.assertTrue(config(signed_in)['open_on_load'])
        self.assertFalse(config(plain)['open_on_load'])
        self.assertFalse(config(anonymous)['open_on_load'])
