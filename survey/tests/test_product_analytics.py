"""Tests for the `product-analytics` capability (openspec/specs/product-analytics/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, SimpleTestCase
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.urls import reverse
from unittest import mock
import json
import re
from survey.models import SurveyHeader, SurveySection, Membership, PublicResultsPage, CreatorPreferences
from django.test import RequestFactory
from django.conf import settings
import os
from django.core.management import call_command
from django.contrib.auth.models import AnonymousUser
from survey.models import PublicResultsPage as _PRP
from survey.tests.helpers import _make_org


class PostHogSnippetTest(TestCase):
    """Tests for the internal product-analytics snippet.

    PostHog measures us, not our customers' respondents. The exclusion tests below
    are the load-bearing ones: they assert against genuinely routed respondent URLs,
    so moving a route breaks a test instead of quietly opting respondents in.
    """

    KEY = 'phc_testkey123'

    def setUp(self):
        self.org = _make_org('PostHogOrg')
        self.user = User.objects.create_user(
            'posthoguser', email='creator@example.com', password='pass',
        )
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='posthog_survey',
            organization=self.org,
            redirect_url='#',
            status='published',
        )
        self.section1 = SurveySection.objects.create(
            survey_header=self.survey,
            name='section1',
            start_map_postion=Point(0, 0),
            start_map_zoom=10,
        )
        self.results_page = PublicResultsPage.objects.create(
            survey=self.survey, slug='posthog-results', is_published=True,
        )

    def test_no_snippet_when_key_unset(self):
        """
        GIVEN POSTHOG_PROJECT_KEY is empty (the default)
        WHEN a creator-facing page is rendered
        THEN neither the loader nor the init call appears in the HTML
        """
        with self.settings(POSTHOG_PROJECT_KEY=''):
            response = self.client.get('/trust/')
            self.assertNotContains(response, 'posthog.init')
            self.assertNotContains(response, 'posthog-key')
            self.assertNotContains(response, 'i.posthog.com')

    def test_snippet_present_when_key_set(self):
        """
        GIVEN POSTHOG_PROJECT_KEY is configured
        WHEN a creator-facing page is rendered
        THEN the snippet carries that key and initialises against the configured host
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY):
            response = self.client.get('/trust/')
            self.assertContains(response, self.KEY)
            self.assertContains(response, 'posthog.init')
            self.assertContains(response, 'https://eu.i.posthog.com')

    def test_api_host_is_overridable(self):
        """
        GIVEN POSTHOG_API_HOST points somewhere other than Cloud EU
        WHEN a creator-facing page is rendered
        THEN the snippet initialises against that host and not the default
        """
        with self.settings(
            POSTHOG_PROJECT_KEY=self.KEY,
            POSTHOG_API_HOST='https://analytics.example.com',
        ):
            response = self.client.get('/trust/')
            self.assertContains(response, 'https://analytics.example.com')
            self.assertNotContains(response, 'https://eu.i.posthog.com')

    def test_empty_api_host_falls_back_to_cloud_eu(self):
        """
        GIVEN the deployment supplies POSTHOG_API_HOST as an empty string
        WHEN the snippet is rendered
        THEN it still initialises against Cloud EU rather than nothing

        render.yaml declares the variable as `sync: false`, so the Render
        dashboard can hand the process an empty value. An empty api_host is a
        silent no-op that looks identical to working analytics.
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY, POSTHOG_API_HOST=''):
            response = self.client.get('/trust/')
            self.assertContains(response, 'https://eu.i.posthog.com')

    def test_browser_uses_the_proxy_host_when_one_is_configured(self):
        """
        GIVEN POSTHOG_CLIENT_HOST names a first-party reverse proxy
        WHEN a creator-facing page is rendered
        THEN the snippet initialises against it and PostHog's own host is absent

        The absence matters as much as the presence: a hostname containing
        "posthog" anywhere in the page is a hostname the blocklists match, which
        is the entire reason the proxy exists.
        """
        with self.settings(
            POSTHOG_PROJECT_KEY=self.KEY,
            POSTHOG_CLIENT_HOST='https://e.example.org',
        ):
            response = self.client.get('/trust/')
            self.assertContains(response, 'https://e.example.org')
            self.assertNotContains(response, 'eu.i.posthog.com')

    def test_unset_proxy_host_falls_back_to_the_api_host(self):
        """
        GIVEN POSTHOG_CLIENT_HOST is empty (no proxy provisioned)
        WHEN a creator-facing page is rendered
        THEN the snippet initialises against POSTHOG_API_HOST, exactly as before
             the proxy existed
        """
        with self.settings(
            POSTHOG_PROJECT_KEY=self.KEY,
            POSTHOG_CLIENT_HOST='',
            POSTHOG_API_HOST='https://eu.i.posthog.com',
        ):
            response = self.client.get('/trust/')
            self.assertContains(response, 'https://eu.i.posthog.com')

    def test_ui_host_is_pinned_regardless_of_proxy(self):
        """
        GIVEN the snippet may be pointed at a domain of ours
        WHEN it is rendered, with and without a proxy configured
        THEN ui_host names the PostHog app, so toolbar links do not resolve
             against the proxy
        """
        for client_host in ('', 'https://e.example.org'):
            with self.subTest(client_host=client_host):
                with self.settings(
                    POSTHOG_PROJECT_KEY=self.KEY,
                    POSTHOG_CLIENT_HOST=client_host,
                ):
                    response = self.client.get('/trust/')
                    self.assertContains(response, "ui_host: 'https://eu.posthog.com'")

    def test_no_snippet_on_respondent_survey_page_even_with_proxy(self):
        """
        GIVEN both the key and a first-party proxy host are configured
        WHEN a respondent loads a survey section under /surveys/
        THEN neither the snippet nor the proxy hostname appears

        A first-party host is the one thing that could make PostHog on a
        respondent page look innocuous in review. It must not get there at all.
        """
        with self.settings(
            POSTHOG_PROJECT_KEY=self.KEY,
            POSTHOG_CLIENT_HOST='https://e.example.org',
        ):
            response = self.client.get(f'/surveys/{self.survey.uuid}/section1/')
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'posthog.init')
            self.assertNotContains(response, 'https://e.example.org')

    def test_no_snippet_without_a_key_even_with_proxy(self):
        """
        GIVEN a proxy host is configured but POSTHOG_PROJECT_KEY is empty
        WHEN a creator-facing page is rendered
        THEN nothing renders — the key remains the single on/off switch
        """
        with self.settings(
            POSTHOG_PROJECT_KEY='',
            POSTHOG_CLIENT_HOST='https://e.example.org',
        ):
            response = self.client.get('/trust/')
            self.assertNotContains(response, 'posthog.init')
            self.assertNotContains(response, 'https://e.example.org')

    def test_no_snippet_on_respondent_survey_page(self):
        """
        GIVEN POSTHOG_PROJECT_KEY is configured
        WHEN a respondent loads a survey section under /surveys/
        THEN no PostHog snippet is rendered
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY):
            response = self.client.get(f'/surveys/{self.survey.uuid}/section1/')
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'posthog.init')
            self.assertNotContains(response, self.KEY)

    def test_no_snippet_on_public_results_page(self):
        """
        GIVEN POSTHOG_PROJECT_KEY is configured
        WHEN a visitor loads a public results page under /r/
        THEN no PostHog snippet is rendered

        Belt and braces: `public_results.html` is a standalone template that
        includes no analytics partial at all today, so this would hold even
        without the exclusion. The exclusion is what keeps it holding if that
        template ever grows a shared head. The prefix rule itself is asserted
        directly in PostHogContextProcessorTest.
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY):
            response = self.client.get(f'/r/{self.results_page.slug}/')
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'posthog.init')
            self.assertNotContains(response, self.KEY)

    def test_snippet_on_editor_page(self):
        """
        GIVEN POSTHOG_PROJECT_KEY is configured AND a creator is signed in
        WHEN the editor dashboard is loaded
        THEN the snippet is rendered
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY):
            self.client.login(username='posthoguser', password='pass')
            response = self.client.get('/editor/')
            self.assertContains(response, 'posthog.init')
            self.assertContains(response, self.KEY)

    def test_no_snippet_on_editor_section_preview(self):
        """
        GIVEN POSTHOG_PROJECT_KEY is configured AND a creator is signed in
        WHEN the editor's Live preview iframe loads a section
        THEN no PostHog snippet is rendered

        The URL is reversed by name rather than written out: the exclusion is
        keyed on the view name, so a rename in urls.py that misses
        POSTHOG_EXCLUDED_VIEW_NAMES has to fail here instead of quietly putting
        a second recorder back into the creator's tab.
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY):
            self.client.login(username='posthoguser', password='pass')
            url = reverse(
                'editor_section_preview',
                args=[self.survey.uuid, self.section1.name],
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'posthog.init')
            self.assertNotContains(response, self.KEY)

    def test_no_snippet_on_editor_thanks_preview(self):
        """
        GIVEN POSTHOG_PROJECT_KEY is configured AND a creator is signed in
        WHEN the editor's Live preview iframe loads the thanks page
        THEN no PostHog snippet is rendered
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY):
            self.client.login(username='posthoguser', password='pass')
            url = reverse('editor_survey_thanks_preview', args=[self.survey.uuid])
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'posthog.init')
            self.assertNotContains(response, self.KEY)

    def test_editor_page_framing_the_preview_is_still_tracked(self):
        """
        GIVEN POSTHOG_PROJECT_KEY is configured AND a creator is signed in
        WHEN the editor page that hosts the preview pane is loaded
        THEN the snippet is rendered

        Guards the other direction: the view-name exclusion must not spread to
        the page whose usage we are trying to measure.
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY):
            self.client.login(username='posthoguser', password='pass')
            response = self.client.get(f'/editor/surveys/{self.survey.uuid}/')
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'posthog.init')
            self.assertContains(response, self.KEY)

    def test_snippet_does_not_initialise_in_a_frame(self):
        """
        GIVEN POSTHOG_PROJECT_KEY is configured
        WHEN a tracked page is rendered
        THEN the snippet refuses to initialise when the document is framed

        The client-side belt behind POSTHOG_EXCLUDED_VIEW_NAMES: it covers any
        framed surface added later without the view-name list being updated.
        Asserted on the rendered markup because a framed document is exactly
        what the Django test client cannot produce.
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY):
            self.client.login(username='posthoguser', password='pass')
            response = self.client.get('/editor/')
            self.assertContains(response, 'window.top !== window.self')

    def test_exclusion_list_is_configurable(self):
        """
        GIVEN /surveys/ is removed from POSTHOG_EXCLUDED_PREFIXES
        WHEN a respondent survey page is rendered
        THEN the snippet appears, proving the gate reads the setting rather
             than hardcoding the prefixes

        Uses /surveys/ deliberately: that template does include the shared
        analytics partial, so lifting the exclusion has an observable effect.
        """
        with self.settings(
            POSTHOG_PROJECT_KEY=self.KEY,
            POSTHOG_EXCLUDED_PREFIXES=('/r/',),
        ):
            response = self.client.get(f'/surveys/{self.survey.uuid}/section1/')
            self.assertContains(response, 'posthog.init')
            self.assertContains(response, self.KEY)

    def test_authenticated_creator_is_identified(self):
        """
        GIVEN POSTHOG_PROJECT_KEY is configured AND a creator is signed in
        WHEN a creator-facing page is rendered
        THEN the snippet identifies them by primary key with person properties attached
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY):
            self.client.login(username='posthoguser', password='pass')
            response = self.client.get('/editor/')
            # The id="..." form, not the bare string: the snippet's
            # getElementById('posthog-person') is present on every tracked
            # page, so a bare match would pass without any payload at all.
            self.assertContains(response, 'id="posthog-person"')
            self.assertContains(response, f'"distinct_id": "{self.user.pk}"')
            self.assertContains(response, 'creator@example.com')
            self.assertContains(response, 'posthoguser')

    def test_anonymous_visitor_is_not_identified(self):
        """
        GIVEN POSTHOG_PROJECT_KEY is configured AND nobody is signed in
        WHEN a marketing page is rendered
        THEN no identify payload and no email address reach the HTML
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY):
            response = self.client.get('/trust/')
            self.assertContains(response, 'posthog.init')
            self.assertNotContains(response, 'id="posthog-person"')
            self.assertNotContains(response, 'creator@example.com')

    def test_person_properties_are_escaped(self):
        """
        GIVEN a username containing characters that would close the script block
        WHEN the snippet is rendered for that user
        THEN the identify payload escapes them and still round-trips to the real value
        """
        import re

        hostile = User.objects.create_user(
            'bad</script>"user', email='hostile@example.com', password='pass',
        )
        Membership.objects.create(user=hostile, organization=self.org, role='owner')
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY):
            self.client.force_login(hostile)
            response = self.client.get('/editor/')

        match = re.search(
            r'<script id="posthog-person" type="application/json">(.*?)</script>',
            response.content.decode(),
            re.S,
        )
        self.assertIsNotNone(match, 'identify payload missing')
        payload = match.group(1)
        # Escaped in transport: a raw closing tag here would end the block early.
        self.assertNotIn('</script>', payload)
        self.assertIn('\\u003C', payload)
        # ...and still means the same thing once parsed.
        self.assertEqual(json.loads(payload)['username'], 'bad</script>"user')

    def test_session_recording_is_disabled_by_default(self):
        """
        GIVEN POSTHOG_PROJECT_KEY is configured and replay is not switched on
        WHEN the snippet is rendered
        THEN session recording is switched off in its initialisation

        The default is what local development, the test suite, PR previews, forks
        and self-hosted installs get. Recording is a deliberate act, everywhere.
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY, POSTHOG_SESSION_REPLAY=False):
            response = self.client.get('/trust/')
            self.assertContains(response, 'disable_session_recording: true')

    def test_session_recording_is_enabled_by_the_setting(self):
        """
        GIVEN replay is switched on
        WHEN the snippet is rendered
        THEN recording is not disabled in its initialisation
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY, POSTHOG_SESSION_REPLAY=True):
            response = self.client.get('/trust/')
            self.assertContains(response, 'disable_session_recording: false')
            self.assertNotContains(response, 'disable_session_recording: true')

    def test_inputs_are_masked_whenever_recording_is_possible(self):
        """
        GIVEN replay is switched on
        WHEN the snippet is rendered
        THEN every input is masked in the browser before anything is transmitted

        This assertion is the entire privacy claim on /trust/. An edit that removes
        the flag to make replays "more useful" starts recording keystrokes, and it
        must fail here rather than be discovered in a recording.
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY, POSTHOG_SESSION_REPLAY=True):
            response = self.client.get('/trust/')
            self.assertContains(response, 'maskAllInputs: true')

    def test_interface_text_is_not_masked(self):
        """
        GIVEN masking everything would make playback unreadable
        WHEN the snippet is rendered with replay on
        THEN the config does not mask all text

        The policy is: what the user typed is masked, what the product showed is
        not. Grey rectangles cannot answer which control someone hunted for.
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY, POSTHOG_SESSION_REPLAY=True):
            response = self.client.get('/trust/')
            self.assertNotContains(response, 'maskTextSelector')

    def test_recorded_request_urls_lose_their_query_string(self):
        """
        GIVEN the place search sends what the creator typed as ?q=...
        WHEN the snippet is rendered with replay on
        THEN recorded requests are rewritten to drop the query string

        Without this, a field masked in the replay reappears intact inside a
        recorded request URL — the one leak that input masking does not cover,
        and it is our own code that opens it (map_place_search.js).
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY, POSTHOG_SESSION_REPLAY=True):
            response = self.client.get('/trust/')
            self.assertContains(response, 'maskRequestFn')
            self.assertContains(response, "split('?')[0]")

    def test_request_bodies_are_not_recorded(self):
        """
        GIVEN request bodies and headers would carry exactly what masking removes
        WHEN the snippet is rendered with replay on
        THEN nothing in the config turns them on

        The SDK defaults them off (recordBody / recordHeaders in the recorder
        bundle). This test exists so that enabling them becomes a deliberate,
        visible act rather than a line added to a config nobody re-reads.
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY, POSTHOG_SESSION_REPLAY=True):
            response = self.client.get('/trust/')
            self.assertNotContains(response, 'recordBody')
            self.assertNotContains(response, 'recordHeaders')

    def test_no_recording_config_on_respondent_pages(self):
        """
        GIVEN replay is switched on and a key is configured
        WHEN a respondent loads a survey page
        THEN there is no snippet and therefore no recording configuration

        What protects respondents is the snippet's absence, not the URL trigger in
        the PostHog project — a dashboard setting could be changed by anyone with
        access, whereas this is enforced in the context processor.
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY, POSTHOG_SESSION_REPLAY=True):
            response = self.client.get(f'/surveys/{self.survey.uuid}/section1/')
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'posthog.init')
            self.assertNotContains(response, 'maskAllInputs')
            self.assertNotContains(response, 'disable_session_recording')

    def test_no_recording_config_on_public_results_page(self):
        """
        GIVEN replay is switched on and a key is configured
        WHEN a visitor loads a public results page
        THEN there is no snippet and no recording configuration
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY, POSTHOG_SESSION_REPLAY=True):
            response = self.client.get(f'/r/{self.results_page.slug}/')
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'posthog.init')
            self.assertNotContains(response, 'maskAllInputs')

    def test_replay_setting_without_a_key_renders_nothing(self):
        """
        GIVEN replay is switched on but POSTHOG_PROJECT_KEY is empty
        WHEN a creator-facing page is rendered
        THEN nothing renders — the key stays the single on/off switch
        """
        with self.settings(POSTHOG_PROJECT_KEY='', POSTHOG_SESSION_REPLAY=True):
            response = self.client.get('/trust/')
            self.assertNotContains(response, 'posthog.init')
            self.assertNotContains(response, 'maskAllInputs')

    def test_person_profiles_are_identified_only(self):
        """
        GIVEN POSTHOG_PROJECT_KEY is configured
        WHEN the snippet is rendered
        THEN profiles are created for identified users only, not anonymous visitors
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY):
            response = self.client.get('/trust/')
            self.assertContains(response, "person_profiles: 'identified_only'")

    def test_snippet_on_account_page(self):
        """
        GIVEN POSTHOG_PROJECT_KEY is configured
        WHEN a page built on the shared base template is rendered
        THEN the snippet is present

        Covers the third of the four heads that include the analytics partial:
        base_landing.html and editor_base.html are covered elsewhere, and
        base_survey_template.html is covered by the exclusion tests.
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY):
            response = self.client.get('/accounts/register/')
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'posthog.init')

    def test_trust_page_discloses_creator_analytics(self):
        """
        GIVEN the trust page is the answer we give IT security teams
        WHEN it is read
        THEN it discloses that product analytics runs on creator-facing pages
        AND states that it never loads where respondents answer surveys
        """
        response = self.client.get('/trust/')
        self.assertContains(response, 'Product analytics on creator-facing pages only')
        self.assertContains(response, 'never to load where respondents answer surveys')

    def test_trust_page_discloses_ai_drafting(self):
        """
        GIVEN AI draft generation sends the creator's brief to a US provider
        WHEN the trust page is read
        THEN it names that transfer, says the feature is optional
        AND repeats that survey responses never reach an AI provider

        The page's whole value is that it is checkable against the code. A
        capability that ships to production without appearing here is the same
        defect we spent 2026-08-15 correcting, only in the other direction.
        """
        response = self.client.get('/trust/')
        self.assertContains(response, "AI drafting sends the creator's brief to Google")
        self.assertContains(response, 'Survey responses are never sent to an AI provider')

    def test_trust_page_discloses_session_recording(self):
        """
        GIVEN we record what happens on screen while creators build surveys
        WHEN the trust page is read
        THEN it says recording happens, that typed content is masked, how long
             recordings are kept, and that respondents are never recorded

        Recording is the most invasive thing we point at a user, and the users are
        our own customers. A page describing analytics while omitting screen
        recording is worse than one that never mentioned analytics at all.
        """
        response = self.client.get('/trust/')
        self.assertContains(response, 'Editor sessions of signed-in creators may be recorded')
        self.assertContains(response, 'What creators type is masked in their browser')
        self.assertContains(response, 'kept for 30 days')
        self.assertContains(response, 'People answering surveys are never recorded')

    def test_trust_page_names_cloudflare_as_the_proxy(self):
        """
        GIVEN Cloudflare fronts every request to the hosted service, and browser
              analytics is deliberately routed through a first-party proxy
        WHEN the trust page is read
        THEN Cloudflare is named as CDN and reverse proxy, not only as Turnstile
        AND storage in the EU is distinguished from transit that is not
            contractually EU-only

        The disclosure predates the proxy — Render already fronts us with
        Cloudflare — but adding a second Cloudflare path while the page named it
        as an anti-abuse widget would repeat 2026-08-15 exactly.
        """
        response = self.client.get('/trust/')
        self.assertContains(response, 'Cloudflare fronts the hosted service')
        self.assertContains(response, 'including product-analytics traffic')
        self.assertContains(response, 'not contractually guaranteed to')

    def test_trust_page_states_hosting_region_truthfully(self):
        """
        GIVEN every Render service and the production database run in Oregon
        WHEN the trust page is read
        THEN it names the United States as the hosting region
        AND does not claim EU residency or Frankfurt hosting

        This test exists because the page previously claimed Frankfurt and
        "no cross-border transfers outside the EEA" while running in Oregon —
        on the page most likely to be read by an EU procurement officer.
        """
        response = self.client.get('/trust/')
        self.assertContains(response, 'Oregon, United States')
        self.assertContains(response, 'transferred outside the EEA')
        self.assertNotContains(response, 'Frankfurt')
        self.assertNotContains(response, 'Data stays in the EU')

    def test_trust_page_does_not_claim_unimplemented_controls(self):
        """
        GIVEN there is no Content Security Policy and no self-serve account deletion
        WHEN the trust page is read
        THEN it makes neither claim

        Both were asserted on the page while absent from the codebase. If either
        ships later, this test is the reminder to put the claim back.
        """
        response = self.client.get('/trust/')
        self.assertNotContains(response, 'Content Security Policy')
        self.assertNotContains(response, 'deleting your account removes')
        self.assertContains(response, 'Account deletion on request')

    def test_trust_page_does_not_distribute_the_dpa(self):
        """
        GIVEN the DPA template was withdrawn pending legal review
        WHEN the trust page is read
        THEN it offers to agree one on request instead of serving a signable PDF

        The file was moved out of survey/assets/ entirely, so unlinking it also
        stops it being served: leaving it collected would keep the old URL alive
        in every email that ever contained it.
        """
        response = self.client.get('/trust/')
        self.assertNotContains(response, 'mapsurvey-dpa.pdf')
        self.assertNotContains(response, 'Download DPA Template')
        self.assertContains(response, 'Request a DPA')

    def test_trust_page_discloses_respondent_metadata(self):
        """
        GIVEN survey sessions record the respondent's user-agent and referring page
        WHEN the trust page is read
        THEN that collection is disclosed rather than described as "no personal data"
        """
        response = self.client.get('/trust/')
        self.assertContains(response, 'Browser and referring page are recorded')
        self.assertNotContains(response, 'collects no personal data')


class PostHogContextProcessorTest(TestCase):
    """The gate itself, independent of which templates happen to exist today.

    The template-level tests above prove the four current heads behave. These
    prove the *mechanism*, which is what makes a base template added tomorrow
    inherit the exclusion instead of depending on which file its author copied.
    """

    KEY = 'phc_ctxkey'

    def _context_for(self, path, user=None):
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory

        from survey.context_processors import analytics

        request = RequestFactory().get(path)
        request.user = user or AnonymousUser()
        return analytics(request)

    def test_key_present_on_our_own_paths(self):
        """
        GIVEN POSTHOG_PROJECT_KEY is configured
        WHEN the context is built for a creator-facing path
        THEN the key is passed through to the template
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY):
            for path in ('/', '/trust/', '/editor/', '/accounts/register/'):
                with self.subTest(path=path):
                    self.assertEqual(
                        self._context_for(path)['POSTHOG_PROJECT_KEY'], self.KEY,
                    )

    def test_key_withheld_on_excluded_paths(self):
        """
        GIVEN POSTHOG_PROJECT_KEY is configured
        WHEN the context is built for a path belonging to somebody else's audience
        THEN the key is empty, so no snippet can render whatever the template does
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY):
            for path in ('/surveys/', '/surveys/abc/section1/', '/r/', '/r/slug/'):
                with self.subTest(path=path):
                    self.assertEqual(self._context_for(path)['POSTHOG_PROJECT_KEY'], '')

    def test_unset_key_stays_unset_everywhere(self):
        """
        GIVEN POSTHOG_PROJECT_KEY is empty
        WHEN the context is built for any path
        THEN the key is empty and no person data is computed
        """
        with self.settings(POSTHOG_PROJECT_KEY=''):
            context = self._context_for('/trust/')
            self.assertEqual(context['POSTHOG_PROJECT_KEY'], '')

    def test_person_is_none_for_anonymous(self):
        """
        GIVEN nobody is signed in
        WHEN the context is built
        THEN there is no identify payload
        """
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY):
            self.assertIsNone(self._context_for('/trust/')['POSTHOG_PERSON'])

    def test_person_uses_primary_key_not_natural_key(self):
        """
        GIVEN a signed-in creator whose email and username are both editable
        WHEN the context is built
        THEN the distinct id is their primary key, so renaming does not split
             one creator's history into two people
        """
        user = User.objects.create_user(
            'ctxuser', email='ctx@example.com', password='pass',
        )
        with self.settings(POSTHOG_PROJECT_KEY=self.KEY):
            person = self._context_for('/editor/', user=user)['POSTHOG_PERSON']
        self.assertEqual(person['distinct_id'], str(user.pk))
        self.assertEqual(person['email'], 'ctx@example.com')
        self.assertEqual(person['username'], 'ctxuser')
        self.assertTrue(person['date_joined'])

    def test_client_host_prefers_the_proxy(self):
        """
        GIVEN a first-party proxy host is configured
        WHEN the context is built
        THEN the browser is handed the proxy, not PostHog's host
        """
        with self.settings(
            POSTHOG_PROJECT_KEY=self.KEY,
            POSTHOG_CLIENT_HOST='https://e.example.org',
            POSTHOG_API_HOST='https://eu.i.posthog.com',
        ):
            context = self._context_for('/trust/')
        self.assertEqual(context['POSTHOG_CLIENT_HOST'], 'https://e.example.org')

    def test_client_host_falls_back_to_the_api_host(self):
        """
        GIVEN no proxy is configured
        WHEN the context is built
        THEN the browser is handed whatever POSTHOG_API_HOST currently is

        Resolved here rather than at settings import time so that overriding the
        API host — a preview pointed at a throwaway project, or this test — moves
        the browser with it instead of leaving it on the value frozen at startup.
        """
        with self.settings(
            POSTHOG_PROJECT_KEY=self.KEY,
            POSTHOG_CLIENT_HOST='',
            POSTHOG_API_HOST='https://analytics.example.com',
        ):
            context = self._context_for('/trust/')
        self.assertEqual(context['POSTHOG_CLIENT_HOST'], 'https://analytics.example.com')

    def test_both_hosts_empty_falls_back_to_cloud_eu(self):
        """
        GIVEN Render hands the process empty strings for both hosts
        WHEN the context is built
        THEN the browser still gets Cloud EU rather than an empty host

        An empty api_host initialises the SDK against nothing, which looks
        exactly like working analytics until someone notices no events arrive.
        """
        with self.settings(
            POSTHOG_PROJECT_KEY=self.KEY,
            POSTHOG_CLIENT_HOST='',
            POSTHOG_API_HOST='',
        ):
            context = self._context_for('/trust/')
        self.assertEqual(context['POSTHOG_CLIENT_HOST'], 'https://eu.i.posthog.com')


class ExternalScriptCorsTest(SimpleTestCase):
    """Every cross-origin <script src> must carry crossorigin="anonymous".

    Without the attribute a browser withholds the message, file and line of any
    exception thrown inside that script and reports the bare string
    "Script error." — 107 such events over 30 days from 18 people, and not one
    of them said what broke (PostHog 01a00c89).

    Plausible in `partials/_analytics.html` was the only external script in any
    base template missing it, and the opaque errors landed on exactly the pages
    that include that partial and on none of the respondent pages, which do not.

    This scans the templates rather than a rendered page because the point is to
    fail when someone ADDS a script tag, which no rendering test would cover:
    the new script would simply be as opaque as Plausible was.
    """

    TEMPLATE_DIR = os.path.join(settings.BASE_DIR, 'survey', 'templates')
    SCRIPT_TAG = re.compile(r'<script\b[^>]*\bsrc=(?P<q>["\'])(?P<src>.*?)(?P=q)[^>]*>', re.I | re.S)

    # A src that resolves against our own origin needs no CORS negotiation.
    LOCAL_SRC = re.compile(r'^(/|\{%\s*static|\{\{\s*STATIC)')

    def _external_script_tags(self):
        """Yield (relative path, tag) for every non-local script tag we ship."""
        for root, _dirs, files in os.walk(self.TEMPLATE_DIR):
            for filename in files:
                if not filename.endswith('.html'):
                    continue
                path = os.path.join(root, filename)
                with open(path, encoding='utf-8') as fh:
                    body = fh.read()
                for match in self.SCRIPT_TAG.finditer(body):
                    src = match.group('src').strip()
                    if not src or self.LOCAL_SRC.match(src):
                        continue
                    yield os.path.relpath(path, self.TEMPLATE_DIR), match.group(0)

    def test_every_external_script_declares_crossorigin(self):
        """
        GIVEN the templates we ship
        WHEN every external <script src> is inspected
        THEN each carries a crossorigin attribute

        A missing one does not break the page — it silently blinds error
        tracking for that script, which is why nothing else catches it.
        """
        missing = [
            f'{path}: {tag[:120]}'
            for path, tag in self._external_script_tags()
            if 'crossorigin' not in tag.lower()
        ]
        self.assertEqual(
            missing, [],
            'external script tags without crossorigin — exceptions inside them '
            'will be reported as the bare string "Script error.":\n' + '\n'.join(missing))

    def test_the_scan_actually_finds_our_script_tags(self):
        """
        GIVEN the same scan
        WHEN it runs
        THEN it sees the external scripts we know we ship

        Pins the scanner: a regex that matched nothing would make the assertion
        above pass forever.
        """
        tags = list(self._external_script_tags())
        self.assertGreater(len(tags), 5, 'the scan found almost nothing — the regex is wrong')
        srcs = ' '.join(tag for _path, tag in tags)
        self.assertIn('leaflet', srcs.lower())
        self.assertIn('unpkg.com', srcs)


class ResultsBadgeAndRespondentAnalyticsTest(TestCase):
    """The badge on /r/ and the absence of any third-party analytics on respondent pages."""

    def setUp(self):
        self.org = _make_org('BadgeOrg')
        self.survey = SurveyHeader.objects.create(
            name='badge_survey', organization=self.org, redirect_url='#', status='published',
        )
        SurveySection.objects.create(
            survey_header=self.survey, name='section1',
            start_map_postion=Point(0, 0), start_map_zoom=10,
        )
        self.results_page = _PRP.objects.create(
            survey=self.survey, slug='badge-results', is_published=True,
        )

    def test_results_page_badge_links_to_registration_with_utm_only(self):
        """
        GIVEN a published public results page
        WHEN a visitor opens it
        THEN the Made-with badge links to registration with utm_source=viral_loop and
             utm_medium=results, and the href carries no slug or survey id
        """
        response = self.client.get(f'/r/{self.results_page.slug}/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        href = '/accounts/register/?utm_source=viral_loop&amp;utm_medium=results'
        self.assertIn(href, html)
        start = html.index(href)
        self.assertNotIn(self.results_page.slug, html[start:start + len(href) + 40])
        self.assertNotIn(str(self.survey.uuid), html[start:start + len(href) + 40])

    def test_respondent_pages_load_no_third_party_analytics(self):
        """
        GIVEN PostHog configured
        WHEN a survey page, the thanks page and the results page render
        THEN none of them references plausible or initialises PostHog
        """
        with self.settings(POSTHOG_PROJECT_KEY='phc_testkey123'):
            for url in (f'/surveys/{self.survey.uuid}/section1/',
                        f'/surveys/{self.survey.uuid}/thanks/',
                        f'/r/{self.results_page.slug}/'):
                response = self.client.get(url, follow=True)
                html = response.content.decode().lower()
                self.assertNotIn('plausible', html, url)
                self.assertNotIn('posthog.init', html, url)

    def test_trust_page_states_the_new_boundary(self):
        """
        GIVEN the trust page
        WHEN it renders
        THEN it says respondent pages carry no analytics scripts, mentions the
             first-party attribution cookie, and never names Plausible
        """
        response = self.client.get('/trust/')
        html = response.content.decode()
        self.assertIn('No analytics scripts of any kind', html)
        self.assertIn('first-party cookie', html)
        self.assertNotIn('Plausible', html)


class UiLanguagePersonPropertyTest(TestCase):
    """The creator's interface language reaches PostHog as a person property."""

    def setUp(self):
        self.org = _make_org('LangOrg')
        self.user = User.objects.create_user('lang_user', password='x')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.force_login(self.user)

    def test_switch_sets_property_and_redirects(self):
        """
        GIVEN a signed-in creator
        WHEN they switch the interface language to German
        THEN ui_language='de' is set on their person and the switch still redirects
        """
        from unittest import mock
        from survey import product_events as pe
        with mock.patch('survey.editor_views.pe.set_person_properties') as setp:
            resp = self.client.post(reverse('set_creator_language'), {'language': 'de', 'next': '/editor/'})
        self.assertEqual(resp.status_code, 302)
        setp.assert_called_once_with(self.user.pk, {'ui_language': 'de'})
        self.assertEqual(CreatorPreferences.objects.get(user=self.user).ui_language, 'de')

    def test_set_person_properties_is_silent_when_disabled(self):
        """
        GIVEN PostHog is unconfigured (posthog.disabled)
        WHEN set_person_properties is called
        THEN nothing is sent and nothing raises
        """
        import posthog
        from unittest import mock
        from survey import product_events as pe
        with mock.patch.object(posthog, 'disabled', True), mock.patch('posthog.set') as pset:
            pe.set_person_properties(self.user.pk, {'ui_language': 'de'})
        pset.assert_not_called()

    def test_sync_includes_ui_language_for_everyone(self):
        """
        GIVEN one creator with a stored language and one without
        WHEN the person-properties sync runs (dry run)
        THEN the property dict of each carries ui_language, empty for the second
        """
        from survey.management.commands import sync_posthog_person_properties as cmd_mod
        CreatorPreferences.objects.create(user=self.user, ui_language='pl')
        other = User.objects.create_user('lang_other', password='x')
        # The command builds `rows` before deciding to send; capture them by
        # running with --limit high and inspecting through a patched posthog.set.
        import posthog
        from unittest import mock
        from django.core.management import call_command
        with self.settings(POSTHOG_PROJECT_KEY='phc_test'), \
                mock.patch.object(posthog, 'disabled', False), \
                mock.patch('posthog.set') as pset, mock.patch('posthog.set_once'), mock.patch('posthog.flush'):
            call_command('sync_posthog_person_properties')
        sent = {c.kwargs['distinct_id']: c.kwargs['properties'] for c in pset.call_args_list}
        self.assertEqual(sent[str(self.user.pk)]['ui_language'], 'pl')
        self.assertEqual(sent[str(other.pk)]['ui_language'], '')
