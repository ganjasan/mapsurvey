"""Tests for the `support-chat` capability (openspec/specs/support-chat/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
import json
import re
from survey.models import SurveyHeader, Membership
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from survey.tests.helpers import _make_org


class SupportChatTest(TestCase):
    """Chatwoot support widget (change chatwoot-support-chat, #291)."""

    WEBSITE_TOKEN = 'cwWebsiteToken123'
    HMAC_TOKEN = 'cwHmacSecret0123456789'

    def setUp(self):
        self.user = User.objects.create_user(
            username='chatuser', email='chat@example.com', password='pass',
            first_name='Chat', last_name='User',
        )
        org = _make_org('ChatOrg')
        Membership.objects.create(user=self.user, organization=org, role='owner')
        # An empty workspace is redirected to the create page on first visit.
        SurveyHeader.objects.create(name='chat_survey', organization=org)

    def _context_for(self, user=None):
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory

        from survey.context_processors import support_chat

        request = RequestFactory().get('/editor/')
        request.user = user or AnonymousUser()
        return support_chat(request)['SUPPORT_CHAT']

    def _config_on(self, response):
        match = re.search(
            r'<script id="support-chat-config" type="application/json">(.*?)</script>',
            response.content.decode(), re.S,
        )
        self.assertIsNotNone(match, 'config json_script missing')
        return json.loads(match.group(1))

    def _identity_on(self, response):
        return self._config_on(response)['identity']

    def test_unconfigured_widget_is_off(self):
        """
        GIVEN CHATWOOT_WEBSITE_TOKEN is empty
        WHEN the context is built and the landing page is rendered
        THEN there is no widget config, no SDK request, and openSupportChat is a no-op
        """
        with self.settings(CHATWOOT_WEBSITE_TOKEN=''):
            self.assertIsNone(self._context_for(self.user))
            response = self.client.get('/')
        self.assertNotContains(response, '/packs/js/sdk.js')
        self.assertContains(response, 'window.openSupportChat = function (e) { if (e) e.preventDefault(); };')

    def test_unconfigured_help_menu_falls_back_to_email(self):
        """
        GIVEN CHATWOOT_WEBSITE_TOKEN is empty
        WHEN a signed-in creator opens the editor dashboard
        THEN the "?" help menu offers email support instead of the chat
        """
        self.client.login(username='chatuser', password='pass')
        with self.settings(CHATWOOT_WEBSITE_TOKEN='', CONTACT_EMAIL='help@example.com'):
            response = self.client.get('/editor/')
        self.assertContains(response, 'help-nav-icon')
        self.assertContains(response, 'mailto:help@example.com')
        self.assertNotContains(response, 'onclick="openSupportChat(event)"')

    def test_signed_in_identity_is_signed_server_side(self):
        """
        GIVEN the website and HMAC tokens are configured
        WHEN the context is built for a signed-in creator
        THEN the identity carries the pk, email, full name and HMAC-SHA256(pk) under the HMAC token
        """
        import hashlib
        import hmac as hmac_mod

        with self.settings(CHATWOOT_WEBSITE_TOKEN=self.WEBSITE_TOKEN, CHATWOOT_HMAC_TOKEN=self.HMAC_TOKEN):
            identity = self._context_for(self.user)['identity']
        expected = hmac_mod.new(
            self.HMAC_TOKEN.encode(), str(self.user.pk).encode(), hashlib.sha256,
        ).hexdigest()
        self.assertEqual(identity, {
            'identifier': str(self.user.pk),
            'email': 'chat@example.com',
            'name': 'Chat User',
            'identifier_hash': expected,
        })

    def test_signed_in_identity_without_hmac_token_is_unsigned(self):
        """
        GIVEN only the website token is configured
        WHEN the context is built for a signed-in creator
        THEN the identity is passed without identifier_hash
        """
        with self.settings(CHATWOOT_WEBSITE_TOKEN=self.WEBSITE_TOKEN, CHATWOOT_HMAC_TOKEN=''):
            identity = self._context_for(self.user)['identity']
        self.assertEqual(identity['identifier'], str(self.user.pk))
        self.assertNotIn('identifier_hash', identity)

    def test_anonymous_visitor_has_no_identity(self):
        """
        GIVEN the widget is configured
        WHEN the landing page is rendered for an anonymous visitor
        THEN the SDK loads with the bubble shown and the identity is null
        """
        with self.settings(CHATWOOT_WEBSITE_TOKEN=self.WEBSITE_TOKEN, CHATWOOT_HMAC_TOKEN=self.HMAC_TOKEN):
            response = self.client.get('/')
        self.assertContains(response, "script.src = baseUrl + '/packs/js/sdk.js';")
        self.assertEqual(self._config_on(response)['website_token'], self.WEBSITE_TOKEN)
        self.assertContains(response, 'var hideBubble = false;')
        self.assertNotContains(response, 'help-nav-icon')
        self.assertIsNone(self._identity_on(response))

    def test_editor_page_identifies_creator_and_hides_bubble(self):
        """
        GIVEN the widget is configured and MOBILE_EDITOR_NAV is on
        WHEN a signed-in creator opens the editor dashboard
        THEN the page carries the signed identity, hides the bubble, and never the HMAC token
        """
        self.client.login(username='chatuser', password='pass')
        with self.settings(CHATWOOT_WEBSITE_TOKEN=self.WEBSITE_TOKEN,
                           CHATWOOT_HMAC_TOKEN=self.HMAC_TOKEN, MOBILE_EDITOR_NAV=True):
            response = self.client.get('/editor/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'var hideBubble = true;')
        config = self._config_on(response)
        self.assertEqual(config['identity']['identifier'], str(self.user.pk))
        self.assertEqual(len(config['identity']['identifier_hash']), 64)
        self.assertEqual(config['attributes'], {'workspace': 'chatorg', 'plan': 'free'})
        self.assertNotContains(response, self.HMAC_TOKEN)
        # The "?" help menu: chat entry with the unread dot, and the expectation line.
        self.assertContains(response, 'help-nav-icon')
        self.assertContains(response, 'onclick="openSupportChat(event)"')
        self.assertContains(response, 'support-unread')
        self.assertContains(response, 'We reply within a day')

    def test_bubble_shown_on_editor_without_mobile_nav(self):
        """
        GIVEN the widget is configured and MOBILE_EDITOR_NAV is off
        WHEN a signed-in creator opens the editor dashboard
        THEN the bubble is shown
        """
        self.client.login(username='chatuser', password='pass')
        with self.settings(CHATWOOT_WEBSITE_TOKEN=self.WEBSITE_TOKEN, MOBILE_EDITOR_NAV=False):
            response = self.client.get('/editor/')
        self.assertContains(response, 'var hideBubble = false;')

    def test_widget_locale_follows_page_language(self):
        """
        GIVEN the widget is configured
        WHEN the Russian homepage is rendered
        THEN the widget locale is ru
        """
        with self.settings(CHATWOOT_WEBSITE_TOKEN=self.WEBSITE_TOKEN):
            response = self.client.get('/ru/')
        self.assertContains(response, "locale: 'ru'")

    def test_tawk_is_gone(self):
        """
        GIVEN any configuration
        WHEN the landing, login and editor pages are rendered
        THEN none references tawk.to
        """
        for path in ('/', '/accounts/login/'):
            with self.subTest(path=path):
                self.assertNotContains(self.client.get(path), 'tawk.to')
        self.client.login(username='chatuser', password='pass')
        self.assertNotContains(self.client.get('/editor/'), 'tawk.to')
