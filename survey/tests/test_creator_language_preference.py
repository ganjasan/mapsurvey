"""Tests that no capability owns yet: creator-language-preference.

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
import re
from survey.models import Organization, SurveyHeader, SurveySection, Membership, CreatorPreferences
from django.conf import settings as dj_settings


class CreatorLanguagePreferenceTest(TestCase):
    """Creator UI language (openspec: creator-ui-localization).

    The severe risk this guards is leakage: a creator's language must never
    re-language a respondent page, because that page belongs to the survey and
    is seen by the customer's audience, not by us.
    """

    def setUp(self):
        self.org = Organization.objects.create(name="Lang Org")
        self.user = User.objects.create_user('lang_owner', password='pw')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.force_login(self.user)

    def test_switching_stores_the_preference_and_the_cookie(self):
        """
        GIVEN a signed-in creator
        WHEN they choose Deutsch in the switcher
        THEN the preference is stored AND the language cookie is set, because
             LocaleMiddleware runs before request.user exists and can only read
             the cookie
        """
        response = self.client.post(
            reverse('set_creator_language'), {'language': 'de', 'next': '/editor/'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            CreatorPreferences.objects.get(user=self.user).ui_language, 'de')
        self.assertEqual(
            response.cookies[dj_settings.LANGUAGE_COOKIE_NAME].value, 'de')

    def test_unsupported_language_is_refused(self):
        """
        GIVEN a language outside the supported set
        WHEN it is submitted to the switcher
        THEN nothing is stored -- storing it would resolve to an interface with
             no catalog behind it
        """
        self.client.post(reverse('set_creator_language'), {'language': 'zz'})
        self.assertFalse(CreatorPreferences.objects.filter(user=self.user).exists())

    def test_next_cannot_leave_the_site(self):
        """
        GIVEN an absolute URL passed as `next`
        WHEN the language is switched
        THEN the redirect stays on this site, so the switcher is not an open
             redirect
        """
        response = self.client.post(
            reverse('set_creator_language'),
            {'language': 'de', 'next': '//evil.example.com/'})
        self.assertEqual(response.url, reverse('editor'))

    def test_switcher_lists_every_supported_language(self):
        """
        GIVEN the editor chrome
        WHEN it renders for a signed-in creator
        THEN every configured language is offered, each written in its own
             language
        """
        html = self.client.get('/editor/', follow=True).content.decode()
        for _, name in dj_settings.LANGUAGES:
            self.assertIn(name, html)

    def test_language_names_do_not_change_with_the_active_language(self):
        """
        GIVEN a creator whose interface is NOT the default language
        WHEN the switcher renders
        THEN each language still reads in its own language

        Django's {% get_available_languages %} runs every name through gettext,
        and Django ships translations for language names, so "English" rendered
        as "Anglais" for a French creator. The test above misses this because it
        renders under English, where that translation is a no-op. The switcher
        exists for the person who cannot read the current interface, so the one
        entry they came to find must not be relabelled.
        """
        self.client.post(reverse('set_creator_language'),
                         {'language': 'fr', 'next': '/editor/'})
        html = self.client.get('/editor/', follow=True).content.decode()
        for _, name in dj_settings.LANGUAGES:
            self.assertIn(name, html)
        self.assertNotIn('Anglais', html)

    def test_the_survey_editor_offers_the_language_switcher(self):
        """
        GIVEN a creator inside a survey, on a desktop-width screen
        WHEN the editor chrome renders
        THEN the switcher is on the page

        It was not. The editor included it only in the ⋯ overflow menu, which
        `editor-mobile.css` reveals below 768px, so the language could be
        changed on the survey LIST and nowhere else — reported by the owner.

        Asserting merely that the form is on the page would NOT have caught
        that: the overflow menu is in the HTML at every width and hidden in
        CSS. So this looks for the control that survives on a desktop — the
        one marked `nav-desktop`, which `editor-mobile.css` hides on phones.
        """
        survey = SurveyHeader.objects.create(
            name='lang-editor-survey', organization=self.org,
            created_by=self.user, status='draft')
        html = self.client.get(
            reverse('editor_survey_detail', args=[survey.uuid])).content.decode()
        self.assertIn(reverse('set_creator_language'), html)
        self.assertRegex(
            html,
            r'nav-desktop"[^>]*>\s*<a class="dropdown-toggle"[^>]*>\s*'
            r'<i class="fas fa-globe')
        for _code, name in dj_settings.LANGUAGES:
            self.assertIn(name, html)

    def test_the_header_names_the_current_language_without_opening_a_menu(self):
        """
        GIVEN a creator whose interface is Deutsch
        WHEN the chrome renders
        THEN «Deutsch» is on the control itself, not only inside its menu

        The control exists for someone who cannot read the interface around it,
        so which language they are in has to be legible without clicking.
        """
        self.client.post(reverse('set_creator_language'),
                         {'language': 'de', 'next': '/editor/'})
        html = self.client.get('/editor/', follow=True).content.decode()
        # The trigger, not a position in the document: the ⋯ overflow menu is
        # emitted earlier in the DOM, so "before the first menu" would be a
        # test of markup order rather than of what a creator can read.
        self.assertRegex(html, r'fa-globe[^>]*></i>\s*Deutsch')

    def test_the_active_language_row_is_not_styled_invisible(self):
        """
        GIVEN the switcher rendered for a creator
        WHEN the entry for their CURRENT language is inspected
        THEN it carries no inline background override

        Bootstrap's `.dropdown-item.active` is white text on blue. An inline
        `background:none` removed the blue and kept the white, so the current
        language rendered as a blank row — the one entry a creator looks for
        first (owner screenshot, 2026-08-29).
        """
        html = self.client.get('/editor/', follow=True).content.decode()
        active = re.search(
            r'<button[^>]*class="dropdown-item active"[^>]*>', html)
        self.assertIsNotNone(active, 'no active language entry rendered')
        self.assertNotIn('background', active.group(0))

    def test_login_required(self):
        """
        GIVEN an anonymous visitor
        WHEN they POST to the switcher
        THEN they are redirected to sign in rather than storing a preference
        """
        self.client.logout()
        response = self.client.post(reverse('set_creator_language'), {'language': 'de'})
        self.assertEqual(response.status_code, 302)
        self.assertIn(dj_settings.LOGIN_URL, response.url)
        self.assertFalse(CreatorPreferences.objects.filter(user=self.user).exists())


class RespondentLanguageIsolationTest(TestCase):
    """A creator's UI language must never reach a respondent page.

    `survey/views.py` activates the SURVEY's language inside the view, after all
    middleware, which is what makes this hold. Nothing stated it before; these
    tests do.
    """

    def setUp(self):
        self.org = Organization.objects.create(name="Iso Org")
        self.user = User.objects.create_user('iso_owner', password='pw')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='iso-survey', organization=self.org, created_by=self.user,
            status='published', visibility='public',
            available_languages=['de'],
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section one', is_head=True)

    def test_survey_language_wins_over_creator_preference(self):
        """
        GIVEN a creator whose interface language is Polish
        WHEN they open their own German survey as a respondent would
        THEN the respondent chrome renders in German, because the page belongs
             to the survey and its audience, not to the creator
        """
        CreatorPreferences.objects.create(user=self.user, ui_language='pl')
        self.client.force_login(self.user)
        self.client.cookies[dj_settings.LANGUAGE_COOKIE_NAME] = 'pl'

        response = self.client.get(f'/surveys/{self.survey.uuid}/', follow=True)
        self.assertEqual(response.status_code, 200)
        # "Next" is part of the respondent chrome, translated in every locale.
        self.assertNotContains(response, 'Dalej')      # the Polish rendering
        self.assertContains(response, 'Weiter')        # the German one

    def test_no_site_wide_language_session_key_is_written(self):
        """
        GIVEN a respondent choosing a language on a multilingual survey
        WHEN the choice is submitted
        THEN no site-wide Django language session key is written: Django 4.2
             never reads it, and leaving one invites a future reader to make the
             creator and respondent surfaces share a language
        """
        self.survey.available_languages = ['de', 'en']
        self.survey.save(update_fields=['available_languages'])
        # The picker lives on its own route; posting to the entry URL only
        # redirects here.
        self.client.post(
            f'/surveys/{self.survey.uuid}/language/', {'language': 'de'})
        self.assertNotIn('_language', self.client.session)
        self.assertEqual(self.client.session.get('survey_language'), 'de')
