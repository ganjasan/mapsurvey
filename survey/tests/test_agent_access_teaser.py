"""Tests for the `agent-access-teaser` capability (openspec/specs/agent-access-teaser/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from survey.models import Membership
from survey.tests.helpers import _make_org


class AgentAccessTeaserTest(TestCase):
    """`/editor/account/mcp/` is a redirect since change auth-core (#379); the
    page body, the interest button and the menu entrances are tested in
    `api/tests/test_connections.py` (TeaserDeltaTest)."""

    def setUp(self):
        self.org = _make_org('AgentOrg')
        self.user = User.objects.create_user('agentuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='agentuser', password='pass')

    def test_old_url_redirects_to_connections(self):
        """
        GIVEN a signed-in creator
        WHEN they open the old agent page URL
        THEN they are redirected to the connections page, URL name intact
        """
        response = self.client.get(reverse('editor_account_mcp'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('editor_account_connections'))

    def test_anonymous_is_sent_to_login(self):
        """
        GIVEN a signed-out visitor
        WHEN they open the old URL
        THEN they are redirected to sign in
        """
        self.client.logout()

        response = self.client.get(reverse('editor_account_mcp'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])
