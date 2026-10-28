"""Tests for the `creator-preferences-page` capability (openspec/specs/creator-preferences-page/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from survey.models import SurveyHeader, Membership, SurveyCollaborator, CreatorPreferences
from survey.tests.helpers import _make_org


class CreatorPreferencesPageTest(TestCase):
    """The personal Preferences page (change start-cards-one-click): where the default way to
    start a survey is set now that the start page acts on one click."""

    def setUp(self):
        self.org = _make_org('PrefsOrg')
        self.user = User.objects.create_user('prefsuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='prefsuser', password='pass')
        self.url = reverse('editor_account_preferences')

    def _stored(self):
        return CreatorPreferences.objects.get(user=self.user).survey_start_default

    def test_page_shows_the_current_default(self):
        """
        GIVEN survey_start_default = 'blank'
        WHEN the Preferences page opens
        THEN Start from scratch is the checked option
        """
        CreatorPreferences.objects.create(user=self.user, survey_start_default='blank')

        html = self.client.get(self.url).content.decode()

        self.assertIn('value="blank" checked', html)
        self.assertNotIn('value="" checked', html)
        self.assertIn('Survey wizard', html)
        self.assertNotIn('Draft with AI', html)

    def test_no_row_means_ask_and_writes_nothing(self):
        """
        GIVEN a creator without a CreatorPreferences row
        WHEN the page opens
        THEN Ask every time is checked and no row is created
        """
        CreatorPreferences.objects.filter(user=self.user).delete()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="" checked')
        self.assertFalse(CreatorPreferences.objects.filter(user=self.user).exists())

    def test_saving_a_default_routes_the_dashboard_button(self):
        """
        GIVEN the page
        WHEN the creator saves the Survey wizard
        THEN the value is stored, the page redirects to itself with a confirmation, and
             "+ New Survey" on the dashboard links to the create page
        """
        response = self.client.post(self.url, {'survey_start_default': 'ai'}, follow=True)

        self.assertRedirects(response, self.url)
        self.assertContains(response, 'Preferences saved.')
        self.assertEqual(self._stored(), 'ai')
        SurveyHeader.objects.create(name='existing', organization=self.org, created_by=self.user)
        dashboard = self.client.get(reverse('editor')).content.decode()
        self.assertIn('href="%s" class="btn btn-sm btn-primary btn-new-survey"' % reverse('editor_survey_create'),
                      dashboard)

    def test_back_to_asking(self):
        """
        GIVEN a stored default
        WHEN the creator saves Ask every time
        THEN the stored value is ''
        """
        CreatorPreferences.objects.create(user=self.user, survey_start_default='blank')

        self.client.post(self.url, {'survey_start_default': ''})

        self.assertEqual(self._stored(), '')

    def test_invalid_value_is_refused(self):
        """
        GIVEN a stored default
        WHEN a value outside the three is posted
        THEN 400 and the stored value is unchanged
        """
        CreatorPreferences.objects.create(user=self.user, survey_start_default='blank')

        response = self.client.post(self.url, {'survey_start_default': 'agent'})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._stored(), 'blank')

    def test_viewer_can_store_a_default(self):
        """
        GIVEN a creator whose role in the active workspace is viewer
        WHEN they open and submit the page
        THEN it renders and the value is stored -- the setting is personal
        """
        viewer = User.objects.create_user('prefsviewer', password='pass')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        self.client.login(username='prefsviewer', password='pass')

        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.client.post(self.url, {'survey_start_default': 'blank'})

        self.assertEqual(CreatorPreferences.objects.get(user=viewer).survey_start_default, 'blank')

    def test_anonymous_visitor_goes_to_login(self):
        """
        GIVEN a visitor who is not signed in
        WHEN they open the page
        THEN they are redirected to the login page
        """
        self.client.logout()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='', GEMINI_API_KEY='')
    def test_ai_option_without_a_provider(self):
        """
        GIVEN no LLM provider
        WHEN the page renders, first with no default and then with a stored 'ai'
        THEN the Survey wizard option is disabled with an explanation, except that a stored 'ai' stays
             checked and enabled so a save keeps it
        """
        html = self.client.get(self.url).content.decode()
        self.assertIn('value="ai" disabled', html)
        self.assertIn('Not available on this server', html)

        CreatorPreferences.objects.update_or_create(user=self.user, defaults={'survey_start_default': 'ai'})
        html = self.client.get(self.url).content.decode()
        self.assertIn('value="ai" checked>', html)

    def test_account_menus_link_to_preferences(self):
        """
        GIVEN a signed-in creator
        WHEN the dashboard (base.html) and a survey editor page (editor_base.html) render
        THEN each account menu carries a Preferences link
        """
        survey = SurveyHeader.objects.create(name='prefs_menu', organization=self.org, created_by=self.user)
        SurveyCollaborator.objects.create(survey=survey, user=self.user, role='owner')
        link = 'href="%s"' % self.url

        dashboard = self.client.get(reverse('editor')).content.decode()
        editor = self.client.get(reverse('editor_survey_detail', kwargs={'survey_uuid': survey.uuid})).content.decode()

        self.assertIn(link, dashboard)
        self.assertIn(link, editor)
