"""Tests for the `changelog-hero-banner` capability (openspec/specs/changelog-hero-banner/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from unittest import mock
from unittest.mock import patch
import uuid
from survey.models import SurveyHeader, Membership, CreatorPreferences
from django.test import RequestFactory
import os
from survey.tests.helpers import _ChangelogDirMixin, _ENTRY_A, _HERO, _dated, _make_org


class ChangelogHeroTest(_ChangelogDirMixin, TestCase):
    """The hero tier on the dashboard (change changelog-hero, #423): one banner,
    no queue, closing covers everything."""

    def setUp(self):
        self.org = _make_org('HeroOrg')
        self.user = User.objects.create_user('hero_creator', password='pw')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.force_login(self.user)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.park = SurveyHeader.objects.create(name='Park <b>x</b>', organization=self.org,
                                                created_by=self.user, status='published')
        self.hero_id = '%s-assistant' % _dated(3)
        self.old_card_id = '%s-export' % _dated(5)
        self.use_entries({self.hero_id + '.html': _HERO, self.old_card_id + '.html': _ENTRY_A})

    def _dashboard(self):
        return self.client.get(reverse('editor')).content.decode()

    def _mcp_token(self, revoked=False):
        import datetime as dt
        from oauth2_provider.models import AccessToken, Application
        from api.models import KIND_OAUTH, TokenProfile
        app = Application.objects.create(
            name='Claude', client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris='https://claude.ai/api/mcp/auth_callback')
        token = AccessToken.objects.create(user=self.user, application=app, scope='surveys:read',
                                           token='msa_hero_%s' % uuid.uuid4().hex,
                                           expires=timezone.now() + dt.timedelta(hours=1))
        return TokenProfile.objects.create(token=token, kind=KIND_OAUTH, audiences=['mcp'],
                                           revoked_at=timezone.now() if revoked else None)

    def test_dashboard_renders_the_hero_and_no_card(self):
        """
        GIVEN a creator with a published survey, no MCP connection, a pending
              hero and an older unseen card entry
        WHEN the dashboard renders
        THEN the sidebar block carries the hero (title, call to action to the agent
             page with ?from=dashboard), there is no banner above the survey list,
             and the older card entry is not shown
        """
        html = self._dashboard()
        self.assertIn('id="whatsNewSide"', html)
        self.assertIn('data-tier="hero"', html)
        self.assertIn('data-entry-id="%s"' % self.hero_id, html)
        self.assertIn('Edit these surveys from your assistant', html)
        self.assertIn('href="%s?from=dashboard"' % reverse('editor_survey_start_agent'), html)
        self.assertNotIn('wn-hero', html)
        self.assertNotIn('Export as Excel', html)

    def test_editor_page_shows_the_hero_in_the_sidebar(self):
        """
        GIVEN the same creator
        WHEN another creator page renders
        THEN its sidebar carries the same hero, and no page carries a banner or a corner card
        """
        html = self.client.get(reverse('editor_survey_create')).content.decode()
        self.assertIn('data-tier="hero"', html)
        self.assertNotIn('id="whatsNewHero"', html)
        self.assertNotIn('id="whatsNewCard"', html)

    def test_connected_creator_gets_the_card_not_the_hero(self):
        """
        GIVEN the creator holds a live MCP grant (audience fails), then only a
              revoked one (audience holds again)
        WHEN the dashboard renders each time
        THEN first the small card for the newer... older card entry shows and
             no hero; after revocation the hero is back
        """
        profile = self._mcp_token()
        html = self._dashboard()
        self.assertNotIn('data-tier="hero"', html)
        self.assertIn('data-tier="card"', html)
        self.assertIn('data-entry-id="%s"' % self.old_card_id, html)
        profile.revoked_at = timezone.now()
        profile.save(update_fields=['revoked_at'])
        self.assertIn('data-tier="hero"', self._dashboard())

    def test_expired_hero_shows_nothing_of_itself(self):
        """
        GIVEN the hero is 31 days old and the only unseen entry
        WHEN the dashboard and the context resolve
        THEN no hero, no small card, and no audience query ran (one query: the
             preferences row)
        """
        from django.test import RequestFactory
        from survey.context_processors import whats_new
        expired = '%s-assistant' % _dated(31)
        self.use_entries({expired + '.html': _HERO})
        html = self._dashboard()
        self.assertNotIn('data-tier="hero"', html)
        self.assertNotIn('data-tier="card"', html)
        request = RequestFactory().get('/editor/')
        request.user = self.user
        request.active_org = self.org
        with self.assertNumQueries(1):
            value = dict(whats_new(request)['whats_new'])
        self.assertIsNone(value['hero'])
        self.assertFalse(value['show_card'])
        self.assertEqual(value['unseen_count'], 1)

    def test_empty_workspace_has_no_hero(self):
        """
        GIVEN the creator's workspace has its only survey in the trash
        WHEN the dashboard (?dashboard=1) renders
        THEN has_surveys fails and no hero shows; the older card shows instead
        """
        self.park.deleted_at = timezone.now()
        self.park.save(update_fields=['deleted_at'])
        html = self.client.get(reverse('editor') + '?dashboard=1').content.decode()
        self.assertNotIn('data-tier="hero"', html)
        self.assertIn('data-tier="card"', html)

    def test_cta_closes_everything_and_emits_both_events(self):
        """
        GIVEN the pending hero
        WHEN the creator posts how=cta with the hero's entry_id
        THEN the watermark is the newest id, clicked and dismissed carry
             tier=hero, and the next dashboard has neither hero nor card
        """
        with patch('survey.editor_views.pe.emit') as emit:
            response = self.client.post(reverse('whats_new_seen'),
                                        {'how': 'cta', 'entry_id': self.hero_id})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(CreatorPreferences.objects.get(user=self.user).changelog_seen, self.hero_id)
        self.assertEqual(emit.call_args_list, [
            mock.call('changelog_card_clicked', self.user.pk,
                      {'entry_id': self.hero_id, 'tier': 'hero', 'target': 'cta'}),
            mock.call('changelog_card_dismissed', self.user.pk,
                      {'entry_id': self.hero_id, 'how': 'cta', 'tier': 'hero'}),
        ])
        html = self._dashboard()
        self.assertNotIn('data-tier="hero"', html)
        self.assertNotIn('data-tier="card"', html)

    def test_small_card_dismissal_carries_its_tier(self):
        """
        GIVEN a creator who is connected (so the small card shows)
        WHEN they post how=close with the card's entry_id
        THEN the dismissed event says tier=card for that entry
        """
        self._mcp_token()
        with patch('survey.editor_views.pe.emit') as emit:
            self.client.post(reverse('whats_new_seen'), {'how': 'close', 'entry_id': self.old_card_id})
        emit.assert_called_once_with('changelog_card_dismissed', self.user.pk,
                                     {'entry_id': self.old_card_id, 'how': 'close', 'tier': 'card'})

    def test_partials_remember_the_closed_entry(self):
        """
        GIVEN the sidebar partial
        WHEN its script is read
        THEN it remembers the closed id under one localStorage key and hides a
             matching entry on render -- the close that failed to persist stays closed;
             the old banner and card partials are gone
        """
        import os
        from django.conf import settings as dj
        base = os.path.join(dj.BASE_DIR, 'survey', 'templates')
        with open(os.path.join(base, 'partials', '_sidebar_whats_new.html')) as fh:
            src = fh.read()
        self.assertIn("'msWhatsNewClosed'", src)
        self.assertIn("remembered() === entryId", src)
        self.assertIn("classList.add('wn-hidden')", src)
        for name in ('_whats_new_card.html', '_whats_new_hero.html'):
            self.assertFalse(os.path.exists(os.path.join(base, 'editor', 'partials', name)), name)
