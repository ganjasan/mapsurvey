"""Tests for the `editor-mobile-navigation` capability (openspec/specs/editor-mobile-navigation/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.utils import timezone
import re
from survey.models import Organization, SurveyHeader, SurveySection, Question, Membership, SurveyCollaborator, PublicResultsPage, PublicResultsBlock


class MobileEditorNavTest(TestCase):
    """Mobile editor chrome behind the MOBILE_EDITOR_NAV kill switch.

    Markup-level assertions only: layout properties (no horizontal overflow,
    one-row toolbar) need a rendering engine and are covered by the device
    pass on a PR preview, not by the test client.
    """

    def setUp(self):
        self.org = Organization.objects.create(name="Mobile Org")
        self.user = User.objects.create_user('mobile_owner', password='pw')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(name="mobile_nav_survey", organization=self.org)
        self.client.force_login(self.user)

    @override_settings(MOBILE_EDITOR_NAV=True)
    def test_flag_on_renders_mobile_chrome(self):
        """
        GIVEN the MOBILE_EDITOR_NAV flag is on
        WHEN the survey editor page renders
        THEN the mobile chrome (body class, contextual bottom tab bar with the
             Structure/Edit/Preview panes, overflow menu, mobile stylesheet) is present
        """
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('mobile-nav-enabled', html)
        self.assertIn('mobile-tabbar', html)
        self.assertIn('data-pane="structure"', html)
        self.assertIn('data-pane="edit"', html)
        self.assertIn('data-pane="preview"', html)
        self.assertIn('navbar-overflow', html)
        self.assertIn('editor-mobile', html)
        self.assertIn('data-active-pane="structure"', html)

    @override_settings(MOBILE_EDITOR_NAV=False)
    def test_flag_off_serves_legacy_layout(self):
        """
        GIVEN the MOBILE_EDITOR_NAV flag is off (default)
        WHEN the survey editor page renders
        THEN no mobile chrome markup is emitted on any viewport
        """
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn('mobile-nav-enabled', html)
        self.assertNotIn('mobile-tabbar', html)
        self.assertNotIn('editor-mobile', html)

    def test_type_picker_has_no_geo_highlight(self):
        """
        GIVEN the grouped question type picker
        WHEN the picker partial renders
        THEN the map-questions group is NOT specially highlighted — the purple
             wash was removed (it read as a selected state)
        """
        from django.template.loader import render_to_string
        from survey.question_types import picker_groups_for
        from survey.models import INPUT_TYPE_CHOICES
        groups = picker_groups_for(INPUT_TYPE_CHOICES)
        html = render_to_string(
            'editor/partials/question_type_picker.html',
            {'groups': groups, 'current': 'text'},
        )
        self.assertNotIn('qtp-grid-geo', html)
        self.assertNotIn('qtp-group-geo', html)


class MobileContextualPaneBarTest(TestCase):
    """The bottom tab bar is contextual to the active level-1 page tab."""

    def setUp(self):
        self.org = Organization.objects.create(name="Ctx Org")
        self.user = User.objects.create_user('ctx_owner', password='pw')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(name="ctx_survey", organization=self.org)
        self.client.force_login(self.user)

    @override_settings(MOBILE_EDITOR_NAV=True, RESPONSES_V2=False)
    def test_responses_bar_has_its_own_panes(self):
        """
        GIVEN the mobile nav flag on and Responses v2 off
        WHEN the Responses (analytics) page renders
        THEN the bottom bar carries Table/Map/Charts/Performance, with Charts
             as the mobile default

        Pinned to RESPONSES_V2=False: this is the v1 pane vocabulary, which
        still ships behind that switch. v2 replaced it with
        Overview/Map/Responses/Perf and has its own coverage in
        ResponsesV2MobileTest.test_v2_bottom_bar_vocabulary.
        """
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/analytics/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('data-pane="table"', html)
        self.assertIn('data-pane="map"', html)
        self.assertIn('data-pane="charts"', html)
        self.assertIn('data-pane="performance"', html)
        self.assertIn("mobileAnalyticsPane('charts')", html)
        self.assertNotIn('data-pane="structure"', html)

    @override_settings(MOBILE_EDITOR_NAV=True)
    def test_public_results_bar_shares_pane_vocabulary(self):
        """
        GIVEN the mobile nav flag on
        WHEN the Public results config page renders
        THEN the bottom bar carries Structure/Edit/Preview and the pane
             container starts on Structure when no block is selected
        """
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/public-results/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('data-pane="structure"', html)
        self.assertIn('data-pane="edit"', html)
        self.assertIn('data-pane="preview"', html)
        self.assertIn('data-active-pane="structure"', html)
        self.assertNotIn('data-pane="charts"', html)

    @override_settings(MOBILE_EDITOR_NAV=False)
    def test_flag_off_no_bars_anywhere(self):
        """
        GIVEN the mobile nav flag off
        WHEN Responses and Public results pages render
        THEN neither carries a mobile tab bar
        """
        for path in (f'/editor/surveys/{self.survey.uuid}/analytics/',
                     f'/editor/surveys/{self.survey.uuid}/public-results/'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            # The rendered element, not the bare class name: the v2 dashboard's
            # JavaScript holds `.mobile-tabbar` as a selector, so searching for
            # the string alone reported a bar that is not there.
            self.assertNotIn('<nav class="mobile-tabbar"', response.content.decode())


class DashboardVariantATest(TestCase):
    """Dashboard adaptive top block (variant A) behind MOBILE_EDITOR_NAV."""

    def setUp(self):
        self.org = Organization.objects.create(name="Dash Org")
        self.user = User.objects.create_user('dash_owner', password='pw')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        SurveyHeader.objects.create(name="dash_survey", organization=self.org)
        self.client.force_login(self.user)

    @override_settings(MOBILE_EDITOR_NAV=True)
    def test_flag_on_renders_adaptive_header(self):
        """
        GIVEN the MOBILE_EDITOR_NAV flag on
        WHEN the dashboard renders
        THEN the collapsed-search button, the overflow menu (Import, Show
             Archived, view toggle) and the count label are present
        """
        html = self.client.get('/editor/', follow=True).content.decode()
        self.assertIn('mobile-nav-enabled', html)
        self.assertIn('dash-search-btn', html)
        self.assertIn('dash-overflow', html)
        self.assertIn('My Surveys · 1', html)
        self.assertIn('List view', html)
        self.assertIn('Show Archived', html)

    @override_settings(MOBILE_EDITOR_NAV=False)
    def test_flag_off_serves_legacy_header(self):
        """
        GIVEN the flag explicitly off
        WHEN the dashboard renders
        THEN none of the variant-A chrome is emitted
        """
        html = self.client.get('/editor/', follow=True).content.decode()
        # CSS selectors naming these classes are always in the <style> block;
        # what must be absent with the flag off is the MARKUP and JS.
        self.assertNotIn('<body class="mobile-nav-enabled"', html)
        self.assertNotIn('dashSearchToggle', html)
        self.assertNotIn('class="dropdown dash-overflow"', html)
        self.assertNotIn('dash-count', html.split('</style>')[-1])


class CreateSurveyWizardTest(TestCase):
    """Create-survey wizard (variant A) behind MOBILE_EDITOR_NAV."""

    def setUp(self):
        self.org = Organization.objects.create(name="Wizard Org")
        self.user = User.objects.create_user('wizard_owner', password='pw')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.force_login(self.user)

    # The empty-path button only renders when an AI provider is configured
    # (it sits inside `{% if ai_available %}`); without a key the page shows
    # the plain "Create Survey" button instead.
    @override_settings(MOBILE_EDITOR_NAV=True, AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test')
    def test_flag_on_renders_wizard_chrome(self):
        """
        GIVEN the MOBILE_EDITOR_NAV flag on
        WHEN the create page renders
        THEN the wizard chrome is present (map topbar, step footers, novalidate),
             the path buttons carry the approved copy, and the legacy name and
             language fields are wrapped for hiding
        """
        html = self.client.get('/editor/surveys/new/').content.decode()
        self.assertIn('wizard-map-topbar', html)
        self.assertIn('wizard-goal-footer', html)
        self.assertIn('wizard-create-btn', html)
        self.assertIn('novalidate', html)
        self.assertIn('create-legacy-fields', html)
        self.assertIn('Skip and start from scratch', html)
        self.assertNotIn('>Create empty</button>', html)

    @override_settings(MOBILE_EDITOR_NAV=False, AI_PROVIDER='anthropic', ANTHROPIC_API_KEY='sk-test')
    def test_flag_off_serves_legacy_page(self):
        """
        GIVEN the flag explicitly off
        WHEN the create page renders
        THEN no wizard chrome or copy is emitted and the legacy buttons remain
        """
        html = self.client.get('/editor/surveys/new/').content.decode()
        self.assertNotIn('wizard-map-topbar', html)
        self.assertNotIn('novalidate', html)
        self.assertIn('>Create empty</button>', html)
        self.assertNotIn('Skip and start from scratch', html)

    @override_settings(MOBILE_EDITOR_NAV=True)
    def test_empty_path_creates_untitled_survey(self):
        """
        GIVEN the wizard's empty path (JS fills the hidden name with the default)
        WHEN the form posts the wizard-produced payload
        THEN the survey is created with the placeholder name and a head section
        """
        response = self.client.post('/editor/surveys/new/', {
            'name': 'Untitled survey',
            'available_languages': '[]',
            'action': 'empty',
            'map_lat': '52.52', 'map_lng': '13.405', 'map_zoom': '12',
        })
        self.assertEqual(response.status_code, 302)
        survey = SurveyHeader.objects.get(name='Untitled survey', organization=self.org)
        self.assertTrue(survey.surveysection_set.filter(is_head=True).exists())
    @override_settings(MOBILE_EDITOR_NAV=True)
    def test_cyrillic_name_accepted(self):
        """
        GIVEN a creator briefing in Russian (any language is supported)
        WHEN the wizard posts a Cyrillic-derived survey name
        THEN validate_url_name (now Unicode) accepts it and the survey is created
        """
        response = self.client.post('/editor/surveys/new/', {
            'name': 'Лучшие места в Бишкеке',
            'available_languages': '["ru"]',
            'action': 'empty',
            'map_lat': '42.87', 'map_lng': '74.59', 'map_zoom': '12',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SurveyHeader.objects.filter(name='Лучшие места в Бишкеке').exists())

    @override_settings(MOBILE_EDITOR_NAV=True)
    def test_languages_stay_on_step_one(self):
        """
        GIVEN the wizard flag on
        WHEN the create page renders
        THEN the language picker is NOT wrapped in the hidden legacy block —
             languages are chosen up front so drafts generate translations
        """
        html = self.client.get('/editor/surveys/new/').content.decode()
        wrapper = re.search(r'class="create-legacy-fields".*?</div>\s*</div>', html, re.S)
        self.assertIsNotNone(wrapper)
        self.assertIn('name="name"', wrapper.group(0))
        self.assertNotIn('available_languages', wrapper.group(0))
        self.assertIn('Available languages', html)



class SurveyStatusLineTest(TestCase):
    """Variant C status line, sheets and menus behind MOBILE_EDITOR_NAV."""

    def setUp(self):
        self.org = Organization.objects.create(name="Status Org")
        self.user = User.objects.create_user('status_owner', password='pw')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(name="status_survey", organization=self.org)
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', title='S1', is_head=True,
        )
        Question.objects.create(survey_section=self.section, name='Q1', input_type='text')
        SurveyCollaborator.objects.create(user=self.user, survey=self.survey, role='owner')
        self.client.force_login(self.user)

    def _page(self):
        return self.client.get(f'/editor/surveys/{self.survey.uuid}/').content.decode()

    @override_settings(MOBILE_EDITOR_NAV=True)
    def test_draft_status_line(self):
        """
        GIVEN a draft survey and the flag on
        WHEN the editor renders
        THEN the status line carries the grey Draft chip (lifecycle menu) and
             offers Publish; the navbar chip is gone
        """
        html = self._page()
        self.assertIn('mobile-statusbar', html)
        self.assertIn("doTransition('published')", html)
        # Chip in the status line, colored by status (draft = grey/secondary)
        self.assertIn('pub-chip badge-secondary', html)
        statusbar = html.split('mobile-statusbar', 1)[1]
        self.assertIn('publishing-widget', statusbar)
        # Tab dots replace the navbar chip
        self.assertIn('tabdot td-draft', html)

    @override_settings(MOBILE_EDITOR_NAV=True)
    def test_testing_status_has_share_link_sheet(self):
        """
        GIVEN a testing survey
        WHEN the editor renders
        THEN the status line offers the test link and the sheet carries the
             tokenized URL, the password form and the Publish exit
        """
        self.survey.status = 'testing'
        self.survey.save(update_fields=['status'])
        html = self._page()
        self.assertIn('pub-chip badge-warning', html)
        self.assertIn('Share test link', html)
        self.assertIn(f'token={self.survey.test_token}', html)
        self.assertIn('editor_survey_password'.replace('editor_survey_password', f'/editor/surveys/{self.survey.uuid}/password/'), html)
        self.assertIn('Publish — open for everyone', html)

    @override_settings(MOBILE_EDITOR_NAV=True, LIVE_SURVEY_EDITING=False)
    def test_published_status_edit_and_share(self):
        """
        GIVEN a published survey, live editing switched off
        WHEN the editor renders
        THEN the status line shows the live count with Edit + Share, the edit
             intercept sheet exists, and the ctx-bar Preview duplicate stays out
        """
        self.survey.status = 'published'
        self.survey.save(update_fields=['status'])
        html = self._page()
        self.assertIn('pub-chip badge-success', html)
        self.assertIn('✎ Edit', html)
        self.assertIn('editIntercept', html)
        self.assertIn(f'/editor/surveys/{self.survey.uuid}/share/', html)

    @override_settings(MOBILE_EDITOR_NAV=True)
    def test_overflow_menu_has_share_and_sections_have_counts(self):
        """
        GIVEN the flag on
        WHEN the editor renders
        THEN the overflow menu offers Share…, the HEAD badge is gone and the
             section rows carry question counts
        """
        html = self._page()
        self.assertIn('Share…', html)
        self.assertNotIn('>HEAD<', html)
        self.assertIn('section-qcount', html)

    @override_settings(MOBILE_EDITOR_NAV=False)
    def test_flag_off_keeps_ctx_bar_only(self):
        """
        GIVEN the flag explicitly off
        WHEN the editor renders
        THEN no status line or sheets are emitted and the legacy ctx-bar remains
        """
        html = self._page()
        self.assertNotIn('mobile-statusbar', html)
        self.assertNotIn('testSheet', html)
        self.assertIn('build-ctxbar', html)


class PublicResultsStatusLineTest(TestCase):
    """Survey↔Public-results parity: the PR tab gets the same status-line
    anatomy (colored chip with lifecycle menu + primary action per state)."""

    def setUp(self):
        self.org = Organization.objects.create(name="PR Status Org")
        self.user = User.objects.create_user('pr_status_owner', password='pw')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="pr_status_survey", organization=self.org, status='published',
        )
        self.page = PublicResultsPage.objects.create(survey=self.survey, slug='pr-status')
        SurveyCollaborator.objects.create(user=self.user, survey=self.survey, role='owner')
        self.client.force_login(self.user)

    def _page(self):
        return self.client.get(f'/editor/surveys/{self.survey.uuid}/public-results/').content.decode()

    @override_settings(MOBILE_EDITOR_NAV=True)
    def test_not_published_state(self):
        """
        GIVEN an unpublished results page and the flag on
        WHEN the PR tab renders
        THEN the status line shows the grey Not published chip and the green
             Publish page primary, and the legacy ctx-bar buttons stay out
        """
        html = self._page()
        self.assertIn('mobile-statusbar', html)
        self.assertIn('Not published', html)
        self.assertIn('pub-chip badge-secondary', html)
        self.assertIn('Publish page', html)
        self.assertNotIn('Copy public link', html)

    @override_settings(MOBILE_EDITOR_NAV=True)
    def test_live_state_share_freeze_visitor(self):
        """
        GIVEN a live results page
        WHEN the PR tab renders
        THEN the chip is green Live and the line offers Share (copies /r/),
             Freeze snapshot and Open as visitor on the real public URL
        """
        self.page.is_published = True
        self.page.save(update_fields=['is_published'])
        html = self._page()
        self.assertIn('pub-chip badge-success', html)
        self.assertIn('Live', html)
        self.assertIn('prCopyPublicLink(this)', html)
        self.assertIn('Freeze snapshot', html)
        self.assertIn('Open as visitor', html)
        self.assertIn('/r/pr-status/', html)
        self.assertIn('Unpublish', html)

    @override_settings(MOBILE_EDITOR_NAV=True)
    def test_frozen_state_update_snapshot(self):
        """
        GIVEN a live page in frozen mode
        WHEN the PR tab renders
        THEN the chip is the sky Frozen one with its date and the primary
             action becomes Update snapshot
        """
        from django.utils import timezone
        self.page.is_published = True
        self.page.mode = 'frozen'
        self.page.frozen_at = timezone.now()
        self.page.save(update_fields=['is_published', 'mode', 'frozen_at'])
        html = self._page()
        self.assertIn('pub-chip badge-info', html)
        self.assertIn('Frozen ·', html)
        self.assertIn('Update snapshot', html)
        self.assertIn('Back to live data', html)

    @override_settings(MOBILE_EDITOR_NAV=True)
    def test_tab_dots_and_block_type_badges(self):
        """
        GIVEN the flag on
        WHEN the PR tab renders with a block
        THEN the navbar tabs carry status dots instead of the survey chip and
             block rows show their type badge
        """
        PublicResultsBlock.objects.create(page=self.page, block_type='text', order=1)
        html = self._page()
        self.assertIn('tabdot td-published', html)
        self.assertIn('tabdot td-off', html)
        self.assertIn('section-qcount', html)

    @override_settings(MOBILE_EDITOR_NAV=False)
    def test_flag_off_keeps_legacy_ctxbar(self):
        """
        GIVEN the flag explicitly off
        WHEN the PR tab renders
        THEN no status line is emitted and the scattered ctx-bar controls stay
        """
        html = self._page()
        self.assertNotIn('mobile-statusbar', html)
        self.assertIn('Publish page', html)
