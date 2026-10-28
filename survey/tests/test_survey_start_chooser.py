"""Tests for the `survey-start-chooser` capability (openspec/specs/survey-start-chooser/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.urls import reverse
from django.utils import timezone, translation
from unittest.mock import patch
from survey.models import SurveyHeader, SurveySection, Membership, SurveyCollaborator, CreatorPreferences
from django.conf import settings as dj_settings
from survey.tests.helpers import _make_org


class EditorZeroSurveyRedirectTest(TestCase):
    """New creators land on the create page, not an empty dashboard."""

    def setUp(self):
        self.org = _make_org('ZeroSurveyOrg')
        self.user = User.objects.create_user('zerouser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='zerouser', password='pass')

    def test_empty_org_is_redirected_to_the_start_page(self):
        """
        GIVEN an organization with no surveys
        WHEN an owner opens the dashboard
        THEN they are redirected to the start page (the three ways to begin,
             change first-survey-onboarding) with the welcome flag
        """
        response = self.client.get(reverse('editor'))

        self.assertRedirects(
            response, reverse('editor_survey_start') + '?welcome=1',
        )

    def test_dashboard_flag_defeats_the_redirect(self):
        """
        GIVEN an organization with no surveys
        WHEN the dashboard is opened with ?dashboard=1
        THEN it renders instead of redirecting, so the escape link cannot loop
        """
        response = self.client.get(reverse('editor') + '?dashboard=1')

        self.assertEqual(response.status_code, 200)

    def test_navbar_dashboard_link_carries_the_escape_flag(self):
        """
        GIVEN an organization with no surveys, landed on the create page
        WHEN the page renders the editor navbar
        THEN its "Dashboard" link carries ?dashboard=1, so clicking it does not
             bounce the creator straight back to the create page
        """
        response = self.client.get(reverse('editor_survey_create') + '?welcome=1')

        self.assertContains(
            response, 'href="%s?dashboard=1"><i class="fas fa-arrow-left">' % reverse('editor'),
        )

    def test_org_with_a_survey_is_not_redirected(self):
        """
        GIVEN an organization that already has a survey
        WHEN the dashboard is opened
        THEN it renders as before
        """
        SurveyHeader.objects.create(
            name='existing', organization=self.org, created_by=self.user,
        )

        response = self.client.get(reverse('editor'))

        self.assertEqual(response.status_code, 200)

    def test_trashed_survey_does_not_count_as_content(self):
        """
        GIVEN an organization whose only survey is in the trash
        WHEN the dashboard is opened
        THEN the creator is still sent to the create page
        """
        SurveyHeader.objects.create(
            name='trashed', organization=self.org, created_by=self.user,
            deleted_at=timezone.now(),
        )

        response = self.client.get(reverse('editor'))

        self.assertEqual(response.status_code, 302)

    def test_viewer_is_not_redirected(self):
        """
        GIVEN a viewer in an empty organization
        WHEN they open the dashboard
        THEN they stay there — they cannot create, so the create page is a dead end
        """
        viewer = User.objects.create_user('zeroviewer', password='pass')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        self.client.login(username='zeroviewer', password='pass')

        response = self.client.get(reverse('editor'))

        self.assertEqual(response.status_code, 200)


class SurveyStartTest(TestCase):
    """The start page, the one-click blank survey and the remembered default."""

    def setUp(self):
        self.org = _make_org('StartOrg')
        self.user = User.objects.create_user('startuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='startuser', password='pass')

    @staticmethod
    def _created_props(emit):
        from survey import product_events as pe
        calls = [c for c in emit.call_args_list if c.args and c.args[0] == pe.SURVEY_CREATED]
        return calls[0].args[2] if calls else None

    # ── start page ──

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test')
    def test_start_page_shows_three_cards(self):
        """
        GIVEN an editor-or-higher creator and a configured provider
        WHEN the start page is opened
        THEN the three cards render: the blank card is the submit button of the blank form,
             the wizard (AI draft) card is a link to the brief, the agent card is a link to
             the agent page (change agent-onboarding)
        """
        response = self.client.get(reverse('editor_survey_start'))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Start from scratch', html)
        form = html[html.index('data-survey-start="blank"') - 200:html.index('</form>', html.index('data-survey-start="blank"'))]
        self.assertIn('action="%s"' % reverse('editor_survey_create_blank'), form)
        self.assertIn('<button type="submit" class="start-card" data-path="blank"', form)
        self.assertIn('Start from scratch', form)
        self.assertIn('Survey wizard', html)
        self.assertNotIn('Draft with AI', html)
        self.assertIn('<a class="start-card start-primary" data-path="ai" href="%s?from=start">'
                      % reverse('editor_survey_create'), html)
        self.assertIn('<a class="start-card" data-path="agent" href="%s">'
                      % reverse('editor_survey_start_agent'), html)
        card = html[html.index('data-path="agent"'):html.index('</a>', html.index('data-path="agent"'))]
        self.assertIn('Use your AI assistant', card)
        self.assertIn('New', card)
        for word in ('Claude', 'ChatGPT'):
            self.assertIn(word, card)
        for gone in ('aria-disabled', 'Coming soon', 'MCP', 'token'):
            self.assertNotIn(gone, card)
        self.assertNotIn('Skip to dashboard', html)

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='', GEMINI_API_KEY='')
    def test_ai_card_disabled_without_a_provider(self):
        """
        GIVEN no LLM provider
        WHEN the start page is opened
        THEN the AI card says it is not available and is no link, while the blank card works
        """
        response = self.client.get(reverse('editor_survey_start'))

        html = response.content.decode()
        self.assertIn('Not available on this server', html)
        self.assertIn('<div class="start-card disabled" data-path="ai" aria-disabled="true">', html)
        self.assertNotIn('?from=start', html)
        self.assertNotIn('Best to start', html)
        self.assertNotIn('class="start-card start-primary"', html)
        self.assertIn('data-survey-start="blank"', html)

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test')
    def test_wizard_card_is_the_first_card_and_best_to_start(self):
        """
        GIVEN a configured provider (AI drafts reach publication about 2.5x as often)
        WHEN the start page renders
        THEN the wizard card comes before the blank card in the markup, is the primary card,
             is badged "Best to start" and does not lead with the word AI
        """
        html = self.client.get(reverse('editor_survey_start')).content.decode()

        self.assertLess(html.index('data-path="ai"'), html.index('data-path="blank"'))
        ai_card = html[html.index('data-path="ai"') - 60:html.index('data-path="blank"')]
        self.assertIn('start-primary', ai_card)
        self.assertIn('Best to start', ai_card)
        self.assertIn('Wizard', ai_card)
        self.assertNotIn('With AI', ai_card)

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test')
    def test_cards_act_on_one_click(self):
        """
        GIVEN the start page (#335: a click on a card used to only select it)
        WHEN it renders
        THEN there is no detail block, no selected state, no "Always start this way" and no
             selection script -- the cards themselves are the controls
        """
        html = self.client.get(reverse('editor_survey_start')).content.decode()

        for gone in ('start-detail', 'start-lore', 'Always start this way', 'name="remember"',
                     'aria-pressed', 'Create empty survey'):
            self.assertNotIn(gone, html)

    def test_start_page_refuses_post(self):
        """
        GIVEN a stale tab of the old start page
        WHEN it posts action=clear or action=ai
        THEN 405 and the stored default is untouched
        """
        CreatorPreferences.objects.create(user=self.user, survey_start_default='ai')

        self.assertEqual(self.client.post(reverse('editor_survey_start'), {'action': 'clear'}).status_code, 405)
        self.assertEqual(self.client.post(reverse('editor_survey_start'), {'action': 'ai', 'remember': '1'}).status_code, 405)
        self.assertEqual(CreatorPreferences.objects.get(user=self.user).survey_start_default, 'ai')

    def test_welcome_escape_link(self):
        """
        GIVEN the empty-organization redirect landed here
        WHEN the page renders with ?welcome=1
        THEN a "Skip to dashboard" link carrying ?dashboard=1 is shown
        """
        response = self.client.get(reverse('editor_survey_start') + '?welcome=1')

        self.assertContains(response, 'href="%s?dashboard=1"' % reverse('editor'))
        self.assertContains(response, 'Skip to dashboard')

    def test_viewer_cannot_open_the_start_page(self):
        """
        GIVEN a viewer-role creator
        WHEN they open the start page or post to the blank endpoint
        THEN both are refused and nothing is created
        """
        viewer = User.objects.create_user('startviewer', password='pass')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        self.client.login(username='startviewer', password='pass')

        self.assertEqual(self.client.get(reverse('editor_survey_start')).status_code, 403)
        self.assertEqual(self.client.post(reverse('editor_survey_create_blank')).status_code, 403)
        self.assertEqual(SurveyHeader.objects.count(), 0)

    # ── blank survey in one request ──

    def test_blank_post_creates_a_survey_and_opens_the_editor(self):
        """
        GIVEN an editor with no body to send
        WHEN they post to the blank endpoint
        THEN an "Untitled survey" with one head section, the owner collaborator and a
             start position exists, survey_created says start_blank/world, and the editor opens
        """
        with patch('survey.product_events.emit') as emit:
            response = self.client.post(reverse('editor_survey_create_blank'))

        survey = SurveyHeader.objects.get()
        self.assertRedirects(response, reverse('editor_survey_detail', kwargs={'survey_uuid': survey.uuid}),
                             fetch_redirect_response=False)
        self.assertEqual(survey.name, 'Untitled survey')
        self.assertEqual(survey.available_languages, ['en'])
        self.assertEqual(survey.organization, self.org)
        self.assertEqual(survey.created_by, self.user)
        self.assertIsNotNone(survey.start_map_postion)
        self.assertEqual(survey.start_map_zoom, 2)
        section = SurveySection.objects.get(survey_header=survey)
        self.assertTrue(section.is_head)
        self.assertEqual(section.code, 'S1')
        self.assertTrue(SurveyCollaborator.objects.filter(survey=survey, user=self.user, role='owner').exists())
        props = self._created_props(emit)
        self.assertEqual(props['creation_method'], 'manual')
        self.assertEqual(props['surface'], 'start_blank')
        self.assertEqual(props['map_source'], 'world')
        self.assertEqual(set(props), {'survey_id', 'creation_method', 'surface', 'map_source'})

    def test_blank_survey_speaks_the_creators_language(self):
        """
        GIVEN a creator whose interface language is German
        WHEN they post to the blank endpoint
        THEN the survey's language is German and its name is the German "Untitled survey"
        """
        # The preference reaches a request through the language cookie the
        # middleware writes on the previous response; a fresh client carries it.
        from django.conf import settings as dj_settings
        CreatorPreferences.objects.create(user=self.user, ui_language='de')
        self.client.cookies[dj_settings.LANGUAGE_COOKIE_NAME] = 'de'
        with translation.override('de'):
            expected_name = translation.gettext('Untitled survey')

        self.client.post(reverse('editor_survey_create_blank'))

        survey = SurveyHeader.objects.get()
        self.assertEqual(survey.available_languages, ['de'])
        self.assertEqual(survey.name, expected_name)

    def test_unsupported_interface_language_falls_back_to_english(self):
        """
        GIVEN an active language the product cannot run a survey in
        WHEN the blank survey's language is chosen
        THEN it is English
        """
        from survey.editor_views import _creator_survey_language
        with translation.override('ja'):
            self.assertEqual(_creator_survey_language(), 'en')
        with translation.override('pl'):
            self.assertEqual(_creator_survey_language(), 'pl')

    def test_untitled_survey_is_a_valid_name_in_every_catalog(self):
        """
        GIVEN SurveyHeader.name's validator and 45-character limit
        WHEN "Untitled survey" is translated into every creator language
        THEN every translation passes
        """
        from survey.models import validate_url_name
        from django.conf import settings as dj_settings
        for code, _label in dj_settings.LANGUAGES:
            with translation.override(code):
                name = translation.gettext('Untitled survey')
            self.assertLessEqual(len(name), 45, code)
            validate_url_name(name)  # raises ValidationError on failure

    def test_browser_position_becomes_the_start(self):
        """
        GIVEN the browser handed the start form its coordinates
        WHEN the blank endpoint receives them
        THEN the survey opens there and survey_created says map_source='browser'
        """
        with patch('survey.product_events.emit') as emit:
            self.client.post(reverse('editor_survey_create_blank'),
                             {'map_lat': '42.87', 'map_lng': '74.59', 'map_zoom': '14'})

        survey = SurveyHeader.objects.get()
        self.assertAlmostEqual(survey.start_map_postion.y, 42.87)
        self.assertAlmostEqual(survey.start_map_postion.x, 74.59)
        self.assertEqual(survey.start_map_zoom, 14)
        self.assertEqual(self._created_props(emit)['map_source'], 'browser')

    def test_blank_get_creates_nothing(self):
        """
        GIVEN a link a browser might prefetch
        WHEN the blank endpoint receives a GET
        THEN it is refused and no survey exists
        """
        response = self.client.get(reverse('editor_survey_create_blank'))

        self.assertEqual(response.status_code, 405)
        self.assertEqual(SurveyHeader.objects.count(), 0)

    # ── remembered default ──

    def test_blank_endpoint_ignores_remember(self):
        """
        GIVEN a remember=1 from a tab opened before the checkbox moved to Preferences
        WHEN the blank endpoint runs
        THEN the survey is created and no default is stored
        """
        self.client.post(reverse('editor_survey_create_blank'), {'remember': '1'})

        self.assertEqual(SurveyHeader.objects.count(), 1)
        self.assertFalse(CreatorPreferences.objects.filter(user=self.user).exclude(survey_start_default='').exists())

    def test_start_page_shows_the_current_default(self):
        """
        GIVEN a stored default
        WHEN the start page renders
        THEN it names the default and links to Preferences instead of a Clear button
        """
        CreatorPreferences.objects.create(user=self.user, survey_start_default='ai')

        response = self.client.get(reverse('editor_survey_start'))

        self.assertContains(response, 'Your default:')
        self.assertContains(response, 'href="%s"' % reverse('editor_account_preferences'))
        self.assertNotContains(response, 'name="action" value="clear"')

    # ── dashboard ──

    def _dashboard(self):
        SurveyHeader.objects.create(name='existing', organization=self.org, created_by=self.user)
        return self.client.get(reverse('editor')).content.decode()

    def test_new_survey_button_leads_to_the_start_page_by_default(self):
        """
        GIVEN no remembered default
        WHEN the dashboard renders
        THEN "+ New Survey" links to the start page and the ⋯ menu offers "Start another way…"
        """
        html = self._dashboard()

        self.assertIn('href="%s" class="btn btn-sm btn-primary btn-new-survey"' % reverse('editor_survey_start'), html)
        self.assertIn('Start another way', html)
        self.assertNotIn('data-survey-start="blank"', html)

    def test_new_survey_button_honours_the_ai_default(self):
        """
        GIVEN survey_start_default = 'ai'
        WHEN the dashboard renders
        THEN "+ New Survey" links to the create page
        """
        CreatorPreferences.objects.create(user=self.user, survey_start_default='ai')

        html = self._dashboard()

        self.assertIn('href="%s" class="btn btn-sm btn-primary btn-new-survey"' % reverse('editor_survey_create'), html)

    def test_new_survey_button_honours_the_blank_default(self):
        """
        GIVEN survey_start_default = 'blank'
        WHEN the dashboard renders
        THEN "+ New Survey" is a POST form to the blank endpoint with the geolocation hook
        """
        CreatorPreferences.objects.create(user=self.user, survey_start_default='blank')

        html = self._dashboard()

        self.assertIn('action="%s" class="btn-new-survey-form" data-survey-start="blank"'
                      % reverse('editor_survey_create_blank'), html)
        self.assertRegex(html, r'js/survey_start\.[0-9a-f]+\.js')

    # ── create page ──

    @override_settings(AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test', MOBILE_EDITOR_NAV=False)
    def test_create_page_from_the_start_page_offers_the_way_back(self):
        """
        GIVEN the creator chose Draft with AI on the start page
        WHEN the create page opens with ?from=start
        THEN "Create empty" is gone and a link back to the start page is there; without the
             parameter the page is as before
        """
        from_start = self.client.get(reverse('editor_survey_create') + '?from=start').content.decode()
        plain = self.client.get(reverse('editor_survey_create')).content.decode()

        self.assertIn('id="start-another-way"', from_start)
        self.assertIn('href="%s"' % reverse('editor_survey_start'), from_start)
        self.assertNotIn('id="empty-btn"', from_start)
        self.assertIn('id="empty-btn"', plain)
        self.assertNotIn('id="start-another-way"', plain)

    def test_create_page_opens_on_the_suggested_centre(self):
        """
        GIVEN the organization's last survey is positioned on Bishkek
        WHEN the create page renders
        THEN the picker's first setView is that position, the hidden map_source says org_survey,
             the Berlin default is gone and the "Use my location" hint is absent
        """
        SurveyHeader.objects.create(name='bishkek', organization=self.org, created_by=self.user,
                                    start_map_postion=Point(74.59, 42.87), start_map_zoom=11)

        html = self.client.get(reverse('editor_survey_create')).content.decode()

        self.assertIn('[42.87, 74.59], 11', html)
        self.assertIn('name="map_source" id="create-map-source" value="org_survey"', html)
        self.assertNotIn('52.52, 13.405', html)
        self.assertNotIn('id="create-geo-hint"', html)

    def test_create_page_hints_at_geolocation_when_only_the_world_is_known(self):
        """
        GIVEN nothing but the world fallback
        WHEN the create page renders
        THEN the map starts on the world view, no on-load permission request is in the page,
             and the "Use my location" hint is shown
        """
        html = self.client.get(reverse('editor_survey_create')).content.decode()

        self.assertIn('[20.0, 0.0], 2', html)
        self.assertIn('value="world"', html)
        self.assertIn('id="create-geo-hint"', html)
        self.assertIn("permissions.query({ name: 'geolocation' })", html)

    @override_settings(USE_L10N=True, LANGUAGE_CODE='de')
    def test_create_page_centre_survives_a_decimal_comma_locale(self):
        """
        GIVEN a creator language that writes 42,87
        WHEN the create page renders the initial centre into JavaScript
        THEN the numbers keep their dots
        """
        from django.conf import settings as dj_settings
        SurveyHeader.objects.create(name='bishkek', organization=self.org, created_by=self.user,
                                    start_map_postion=Point(74.59, 42.87), start_map_zoom=11)
        self.client.cookies[dj_settings.LANGUAGE_COOKIE_NAME] = 'de'

        html = self.client.get(reverse('editor_survey_create')).content.decode()

        self.assertIn('[42.87, 74.59], 11', html)
        self.assertNotIn('[42,87', html)

    def test_manual_create_records_surface_and_map_source(self):
        """
        GIVEN the create page's manual action with a map the creator framed
        WHEN the survey is created
        THEN survey_created carries surface='create_page' and map_source='creator'
        """
        with patch('survey.product_events.emit') as emit:
            self.client.post(reverse('editor_survey_create'), {
                'name': 'framed', 'map_lat': '42.87', 'map_lng': '74.59', 'map_zoom': '12',
                'map_touched': '1', 'map_source': 'world',
            })

        props = self._created_props(emit)
        self.assertEqual(props['surface'], 'create_page')
        self.assertEqual(props['map_source'], 'creator')
        survey = SurveyHeader.objects.get(name='framed')
        self.assertAlmostEqual(survey.start_map_postion.y, 42.87)

    def test_manual_create_without_map_fields_uses_the_chain(self):
        """
        GIVEN a legacy POST that sends only a name
        WHEN the survey is created
        THEN it still gets a start position, from the chain, and map_source names the rung
        """
        with patch('survey.product_events.emit') as emit:
            self.client.post(reverse('editor_survey_create'), {'name': 'legacy'})

        survey = SurveyHeader.objects.get(name='legacy')
        self.assertIsNotNone(survey.start_map_postion)
        self.assertEqual(self._created_props(emit)['map_source'], 'world')
