"""Tests for the `in-app-changelog` capability (openspec/specs/in-app-changelog/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, SimpleTestCase
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.urls import reverse
from unittest import mock
from unittest.mock import patch
from survey.models import Organization, SurveyHeader, SurveySection, Membership, CreatorPreferences
from django.test import RequestFactory
import os
import datetime
from django.contrib.auth.models import AnonymousUser
from survey.tests.helpers import _ChangelogDirMixin, _ENTRY_A, _ENTRY_B, _ENTRY_FIX, _HERO


class ChangelogEntriesTest(_ChangelogDirMixin, SimpleTestCase):
    """The repo-authored entry files and their loader."""

    def test_well_formed_entry_loads(self):
        """
        GIVEN an entry file with a valid header and body
        WHEN the loader reads the directory
        THEN the entry carries id, date, title, kind, link, image and body
        """
        from survey import changelog
        self.use_entries({'2026-10-06-empty-sessions.html': _ENTRY_B})
        [entry] = changelog.entries()
        self.assertEqual(entry.id, '2026-10-06-empty-sessions')
        self.assertEqual(entry.date, '2026-10-06')
        self.assertEqual(entry.title, 'Empty sessions are now hidden')
        self.assertEqual(entry.kind, 'new')
        self.assertEqual(entry.link, 'editor')
        self.assertEqual(entry.image, 'favicon-32x32.png')
        self.assertIn('<strong>Why.</strong>', entry.body)
        self.assertEqual(changelog.latest(), entry)

    def test_newest_first_and_unseen_watermark(self):
        """
        GIVEN two entries on different dates
        WHEN they are loaded
        THEN the newer comes first, is `latest()`, and `unseen()` compares ids
             against the watermark as strings
        """
        from survey import changelog
        self.use_entries({'2026-09-29-export-formats.html': _ENTRY_A,
                          '2026-10-06-empty-sessions.html': _ENTRY_B})
        ids = [e.id for e in changelog.entries()]
        self.assertEqual(ids, ['2026-10-06-empty-sessions', '2026-09-29-export-formats'])
        self.assertEqual(changelog.latest().id, '2026-10-06-empty-sessions')
        self.assertEqual(len(changelog.unseen('')), 2)
        self.assertEqual([e.id for e in changelog.unseen('2026-09-29-export-formats')],
                         ['2026-10-06-empty-sessions'])
        self.assertEqual(changelog.unseen('2026-10-06-empty-sessions'), ())

    def test_malformed_entries_are_rejected(self):
        """
        GIVEN entry files with a missing title, an unknown kind, a bad filename,
              an unclosed header, an unknown key or an empty body
        WHEN the loader reads them
        THEN each raises ChangelogError naming the file
        """
        from survey import changelog
        bad = {
            '2026-10-06-no-title.html': "---\nkind: new\n---\n<p>x</p>\n",
            '2026-10-06-bad-kind.html': "---\ntitle: T\nkind: shiny\n---\n<p>x</p>\n",
            'Empty_Sessions.html': _ENTRY_B,
            '2026-10-06-unclosed.html': "---\ntitle: T\nkind: new\n<p>x</p>\n",
            '2026-10-06-unknown-key.html': "---\ntitle: T\nkind: new\ncolour: red\n---\n<p>x</p>\n",
            '2026-10-06-no-body.html': "---\ntitle: T\nkind: new\n---\n\n",
        }
        for name, text in bad.items():
            with self.subTest(name=name):
                self.use_entries({name: text})
                with self.assertRaises(changelog.ChangelogError) as ctx:
                    changelog.entries()
                self.assertIn(name, str(ctx.exception))

    def test_no_entries(self):
        """
        GIVEN an entries directory with only the README
        WHEN the loader reads it
        THEN there are no entries and `latest()` is None
        """
        from survey import changelog
        self.use_entries({'README.md': '# nothing'})
        self.assertEqual(changelog.entries(), ())
        self.assertIsNone(changelog.latest())

    def test_shipped_entries_load(self):
        """
        GIVEN the real survey/changelog/ directory in this checkout
        WHEN the loader reads it
        THEN every file parses -- a malformed entry fails here, not on every
             editor page in production
        """
        from survey import changelog
        changelog.clear_cache()
        self.addCleanup(changelog.clear_cache)
        for entry in changelog.entries():
            self.assertTrue(entry.title)
            self.assertIn(entry.kind, changelog.KINDS)

    # ── the hero tier (change changelog-hero, #423) ──

    def test_hero_entry_loads(self):
        """
        GIVEN an entry declaring tier: hero with the hero keys
        WHEN the loader reads it
        THEN the entry carries tier, art, the call to action, chips, predicates
             and the note, and `day` is the date of the id
        """
        import datetime
        from survey import changelog
        self.use_entries({'2026-11-01-hero.html': _HERO})
        [entry] = changelog.entries()
        self.assertTrue(entry.is_hero)
        self.assertEqual(entry.art, 'agent')
        self.assertEqual(entry.link, 'editor_survey_start_agent')
        self.assertEqual(entry.link_query, 'from=dashboard')
        self.assertEqual(entry.cta_label, 'Connect your assistant')
        self.assertEqual(entry.help, 'mcp')
        self.assertEqual(entry.chips, ('Summarise {survey}', 'Add a question to {survey}', 'Plain chip'))
        self.assertEqual(entry.show_if, ('has_surveys', 'no_mcp_connection'))
        self.assertEqual((entry.note_if, entry.note), ('free_plan', 'Part of Pro'))
        self.assertEqual(entry.day, datetime.date(2026, 11, 1))
        self.assertEqual(changelog.heroes(), (entry,))

    def test_malformed_heroes_are_rejected(self):
        """
        GIVEN a hero without a cta_label, without a link, with an unknown
              predicate, an unknown art, kind: fixed, a note_if without a note,
              and a card entry carrying hero keys
        WHEN the loader reads each
        THEN each raises ChangelogError naming the file
        """
        from survey import changelog
        base = _HERO.replace('cta_label: Connect your assistant\n', '')
        bad = {
            '2026-11-01-no-cta.html': base,
            '2026-11-01-no-link.html': _HERO.replace('link: editor_survey_start_agent\n', ''),
            '2026-11-01-unicorns.html': _HERO.replace('no_mcp_connection', 'unicorns'),
            '2026-11-01-bad-art.html': _HERO.replace('art: agent', 'art: fireworks'),
            '2026-11-01-fixed-hero.html': _HERO.replace('kind: new', 'kind: fixed'),
            '2026-11-01-note-if-only.html': _HERO.replace('note: Part of Pro\n', ''),
            '2026-11-01-no-plate.html': _HERO.replace('art: agent\n', ''),
            '2026-11-01-card-with-chips.html': _ENTRY_A.replace('kind: new\n', 'kind: new\nchips: a|b\n'),
        }
        for name, text in bad.items():
            with self.subTest(name=name):
                self.use_entries({name: text})
                with self.assertRaises(changelog.ChangelogError) as ctx:
                    changelog.entries()
                self.assertIn(name, str(ctx.exception))
        self.use_entries({'2026-11-01-unicorns.html': _HERO.replace('no_mcp_connection', 'unicorns')})
        with self.assertRaises(changelog.ChangelogError) as ctx:
            changelog.entries()
        self.assertIn("'unicorns'", str(ctx.exception))

    def test_hero_budget(self):
        """
        GIVEN two heroes four days apart, and the real directory
        WHEN the spacing rule is checked
        THEN the pair is named, and the shipped directory keeps the 14-day rule
             with every hero's link resolving
        """
        from django.urls import reverse
        from survey import changelog
        self.use_entries({'2026-11-01-first.html': _HERO, '2026-11-05-second.html': _HERO,
                          '2026-11-20-third.html': _HERO})
        self.assertEqual(changelog.hero_spacing_violations(),
                         [('2026-11-01-first', '2026-11-05-second')])
        changelog.clear_cache()
        with mock.patch.object(changelog, 'ENTRIES_DIR',
                               os.path.join(os.path.dirname(changelog.__file__), 'changelog')):
            self.assertEqual(changelog.hero_spacing_violations(), [])
            for hero in changelog.heroes():
                reverse(hero.link)
                self.assertTrue(hero.cta_label, hero.id)
        changelog.clear_cache()

    def test_hero_for_window_and_audience(self):
        """
        GIVEN a hero 10 days old and one 40 days old
        WHEN the pending hero is asked for with an audience that holds, one that
             fails, and a watermark past both
        THEN the young one is pending for the holding audience only, the old one
             never, and the latest card skips heroes
        """
        import datetime
        from survey import changelog
        today = datetime.date(2026, 11, 20)
        self.use_entries({'2026-11-10-young.html': _HERO, '2026-10-11-old.html': _HERO,
                          '2026-11-12-card.html': _ENTRY_A})

        class Yes:
            def all(self, names): return True

        class No:
            def all(self, names): return False
        self.assertEqual(changelog.hero_for('', Yes(), today).id, '2026-11-10-young')
        self.assertIsNone(changelog.hero_for('', No(), today))
        self.assertIsNone(changelog.hero_for('2026-11-10-young', Yes(), today))
        self.assertEqual([e.id for e in changelog.hero_candidates('', today)], ['2026-11-10-young'])
        self.assertEqual(changelog.latest_card('').id, '2026-11-12-card')
        self.assertIsNone(changelog.latest_card('2026-11-12-card'))

    def test_render_chips(self):
        """
        GIVEN three chips, two with {survey}, and the names Park and Bikes / none
        WHEN the chips are rendered
        THEN names cycle one per chip, a plain chip stays, and without names the
             placeholder chips are dropped
        """
        from survey import changelog
        self.use_entries({'2026-11-01-hero.html': _HERO.replace(
            'chips: Summarise {survey}|Add a question to {survey}|Plain chip',
            'chips: Summarise {survey}|Add to {survey}|Plain chip|QR for {survey}')})
        [entry] = changelog.entries()
        self.assertEqual(changelog.render_chips(entry, ['Park', 'Bikes']),
                         ['Summarise Park', 'Add to Bikes', 'Plain chip', 'QR for Park'])
        self.assertEqual(changelog.render_chips(entry, []), ['Plain chip'])


class ChangelogContextTest(_ChangelogDirMixin, TestCase):
    """The lazy `whats_new` context processor behind the navbar and the card."""

    def setUp(self):
        self.org = Organization.objects.create(name="WN Org")
        self.user = User.objects.create_user('wn_creator', password='pw')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.use_entries({'2026-09-29-export-formats.html': _ENTRY_A,
                          '2026-10-06-empty-sessions.html': _ENTRY_B})

    def _resolve(self, user, path='/editor/'):
        from django.test import RequestFactory
        from survey.context_processors import whats_new
        request = RequestFactory().get(path)
        request.user = user
        value = whats_new(request)['whats_new']
        return dict(value)

    def test_respondent_surfaces_cost_no_query(self):
        """
        GIVEN a signed-in creator with unseen entries
        WHEN the value is resolved on a /surveys/ or /r/ path
        THEN it is the empty shape and no query ran -- a creator on their own
             survey's password gate or public results page gets no card
        """
        for path in ('/surveys/abc/', '/surveys/abc/password/', '/r/slug/'):
            with self.subTest(path=path), self.assertNumQueries(0):
                value = self._resolve(self.user, path)
            self.assertFalse(value['show_card'])
            self.assertEqual(value['unseen_count'], 0)

    def test_anonymous_costs_no_query(self):
        """
        GIVEN an anonymous request
        WHEN the lazy value is resolved
        THEN it is the empty shape and no query ran
        """
        from django.contrib.auth.models import AnonymousUser
        with self.assertNumQueries(0):
            value = self._resolve(AnonymousUser())
        self.assertFalse(value['show_card'])
        self.assertEqual(value['unseen_count'], 0)

    def test_creator_with_no_preferences_row_sees_everything_unseen(self):
        """
        GIVEN a creator who predates the changelog (no CreatorPreferences row)
        WHEN the value is resolved
        THEN both entries are unseen and the card shows the newest
        """
        value = self._resolve(self.user)
        self.assertTrue(value['show_card'])
        self.assertEqual(value['unseen_count'], 2)
        self.assertEqual(value['latest'].id, '2026-10-06-empty-sessions')

    def test_seen_watermark_hides_the_card(self):
        """
        GIVEN the watermark at the newest entry
        WHEN the value is resolved
        THEN nothing is unseen and no card shows
        """
        CreatorPreferences.objects.create(user=self.user, changelog_seen='2026-10-06-empty-sessions')
        value = self._resolve(self.user)
        self.assertFalse(value['show_card'])
        self.assertEqual(value['unseen_count'], 0)

    def test_cards_off_keeps_the_indicator(self):
        """
        GIVEN cards switched off and an unseen entry
        WHEN the value is resolved
        THEN no card, but the unseen count still feeds the badge and the dot
        """
        CreatorPreferences.objects.create(user=self.user, changelog_cards=False)
        value = self._resolve(self.user)
        self.assertFalse(value['show_card'])
        self.assertEqual(value['unseen_count'], 2)
        self.assertFalse(value['cards'])

    def test_no_entries_means_nothing(self):
        """
        GIVEN no entries shipped yet
        WHEN the value is resolved for a signed-in creator
        THEN the empty shape comes back without touching preferences
        """
        self.use_entries({})
        with self.assertNumQueries(0):
            value = self._resolve(self.user)
        self.assertFalse(value['show_card'])
        self.assertIsNone(value['latest'])


class WhatsNewViewsTest(_ChangelogDirMixin, TestCase):
    """The page, the two POST endpoints, registration seeding and the template guard."""

    def setUp(self):
        self.org = Organization.objects.create(name="WN Views Org")
        self.user = User.objects.create_user('wn_views', password='pw')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.force_login(self.user)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.use_entries({'2026-09-24-geo-edit.html': _ENTRY_FIX,
                          '2026-09-29-export-formats.html': _ENTRY_A,
                          '2026-10-06-empty-sessions.html': _ENTRY_B})

    def _seen(self):
        prefs = CreatorPreferences.objects.filter(user=self.user).first()
        return prefs.changelog_seen if prefs else ''

    def test_page_highlights_unseen_then_marks_seen(self):
        """
        GIVEN a creator whose watermark is at the oldest entry
        WHEN they open the page twice
        THEN the first render highlights the two newer entries, the "Earlier"
             divider sits before the old one, the watermark moves, the event
             fires once, and the second render highlights nothing
        """
        CreatorPreferences.objects.create(user=self.user, changelog_seen='2026-09-24-geo-edit')
        with patch('survey.editor_views.pe.emit') as emit:
            first = self.client.get(reverse('whats_new'))
        self.assertEqual(first.status_code, 200)
        html = first.content.decode()
        self.assertEqual(html.count('wn-entry wn-new'), 2)
        self.assertIn('Earlier', html)
        self.assertIn('Empty sessions are now hidden', html)
        self.assertIn('Geo answer edit no longer fails', html)
        self.assertIn('wn-tag wn-fixed', html)
        # `link: editor` resolves to an "Open" link; the other entries have none.
        self.assertEqual(html.count('class="wn-go"'), 1)
        self.assertIn('favicon-32x32', html)
        self.assertEqual(self._seen(), '2026-10-06-empty-sessions')
        emit.assert_called_once_with('changelog_page_viewed', self.user.pk,
                                     {'entry_id': '2026-10-06-empty-sessions'})

        with patch('survey.editor_views.pe.emit') as emit:
            second = self.client.get(reverse('whats_new'))
        self.assertEqual(second.content.decode().count('wn-entry wn-new'), 0)
        self.assertNotIn('Earlier', second.content.decode())
        emit.assert_not_called()

    def test_page_with_no_entries(self):
        """
        GIVEN no entries shipped
        WHEN the page is opened
        THEN it says so and writes nothing
        """
        self.use_entries({})
        response = self.client.get(reverse('whats_new'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('Nothing yet', response.content.decode())

    def test_got_it_marks_everything_seen(self):
        """
        GIVEN a creator with three unseen entries
        WHEN the card posts how=got_it
        THEN the watermark is the newest id, the event says how, and the next
             editor page carries no card
        """
        with patch('survey.editor_views.pe.emit') as emit:
            response = self.client.post(reverse('whats_new_seen'), {'how': 'got_it'})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self._seen(), '2026-10-06-empty-sessions')
        emit.assert_called_once_with('changelog_card_dismissed', self.user.pk,
                                     {'entry_id': '2026-10-06-empty-sessions', 'how': 'got_it',
                                      'tier': 'card'})
        page = self.client.get(reverse('editor') + '?dashboard=1')
        self.assertNotIn('id="whatsNewCard"', page.content.decode())

    def test_seen_rejects_unknown_how_and_anonymous(self):
        """
        GIVEN the seen endpoint
        WHEN it is posted with an unknown `how`, or by an anonymous client
        THEN it answers 400 / redirects to login and writes nothing
        """
        self.assertEqual(self.client.post(reverse('whats_new_seen'), {'how': 'later'}).status_code, 400)
        self.client.logout()
        response = self.client.post(reverse('whats_new_seen'), {'how': 'got_it'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login', response['Location'])
        self.assertEqual(self._seen(), '')

    def test_mute_from_the_card_marks_seen_too(self):
        """
        GIVEN a creator with unseen entries
        WHEN they post enabled=0 (Don't show these)
        THEN cards are off, the watermark moved, the event says muted, and the
             dashboard shows no card but still the unseen-free indicator
        """
        with patch('survey.editor_views.pe.emit') as emit:
            response = self.client.post(reverse('whats_new_cards'), {'enabled': '0'})
        self.assertEqual(response.status_code, 204)
        prefs = CreatorPreferences.objects.get(user=self.user)
        self.assertFalse(prefs.changelog_cards)
        self.assertEqual(prefs.changelog_seen, '2026-10-06-empty-sessions')
        emit.assert_called_once_with('changelog_card_dismissed', self.user.pk,
                                     {'entry_id': '2026-10-06-empty-sessions', 'how': 'muted',
                                      'tier': 'card'})

    def test_re_enable_does_not_resurface_seen_entries(self):
        """
        GIVEN cards muted and everything seen
        WHEN the creator posts enabled=1 from the page switch
        THEN cards are on and the dashboard still shows no card
        """
        CreatorPreferences.objects.create(user=self.user, changelog_cards=False,
                                          changelog_seen='2026-10-06-empty-sessions')
        with patch('survey.editor_views.pe.emit') as emit:
            self.assertEqual(self.client.post(reverse('whats_new_cards'), {'enabled': '1'}).status_code, 204)
        emit.assert_not_called()
        self.assertTrue(CreatorPreferences.objects.get(user=self.user).changelog_cards)
        page = self.client.get(reverse('editor') + '?dashboard=1')
        self.assertNotIn('id="whatsNewCard"', page.content.decode())
        self.assertEqual(self.client.post(reverse('whats_new_cards'), {'enabled': 'maybe'}).status_code, 400)

    def test_dashboard_carries_card_and_indicator_for_unseen(self):
        """
        GIVEN a creator who has seen nothing and has three unseen entries
        WHEN they open the dashboard
        THEN the card with the newest entry renders, the navbar dot and the
             menu badge "3" are there
        """
        page = self.client.get(reverse('editor') + '?dashboard=1')
        html = page.content.decode()
        self.assertIn('id="whatsNewCard"', html)
        self.assertIn('data-entry-id="2026-10-06-empty-sessions"', html)
        self.assertIn('Empty sessions are now hidden', html)
        self.assertIn('class="wn-dot"', html)
        self.assertIn('<span class="wn-badge">3</span>', html)

    def test_respondent_page_never_carries_the_card(self):
        """
        GIVEN the same creator with unseen entries
        WHEN they open their own survey as a respondent
        THEN the page carries no card markup and no changelog chrome
        """
        survey = SurveyHeader.objects.create(name='wn_survey', organization=self.org, status='published')
        SurveySection.objects.create(
            survey_header=survey, name='s1', title='S1', code='S1', is_head=True,
            start_map_postion=Point(30.5, 60.0), start_map_zoom=14,
        )
        response = self.client.get(reverse('survey', kwargs={'survey_slug': survey.uuid}), follow=True)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn('whatsNewCard', html)
        self.assertNotIn('wn-nav-icon', html)

    def test_registration_seeds_the_watermark(self):
        """
        GIVEN entries exist
        WHEN a new account registers
        THEN its preferences start at the newest id, so the first editor page
             shows no card
        """
        from django_registration.signals import user_registered
        newcomer = User.objects.create_user('wn_newcomer', password='pw')
        user_registered.send(sender=self.__class__, user=newcomer, request=None)
        prefs = CreatorPreferences.objects.get(user=newcomer)
        self.assertEqual(prefs.changelog_seen, '2026-10-06-empty-sessions')
        self.assertTrue(prefs.changelog_cards)

    def test_registration_with_no_entries_seeds_empty(self):
        """
        GIVEN no entries shipped
        WHEN a new account registers
        THEN the watermark is empty and nothing raised
        """
        from django_registration.signals import user_registered
        self.use_entries({})
        newcomer = User.objects.create_user('wn_newcomer2', password='pw')
        user_registered.send(sender=self.__class__, user=newcomer, request=None)
        self.assertEqual(CreatorPreferences.objects.get(user=newcomer).changelog_seen, '')
