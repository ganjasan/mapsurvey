"""Tests for the `error-tracking` capability (openspec/specs/error-tracking/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from unittest import mock
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser


class PostHogErrorTrackingTest(TestCase):
    """Server-side exception capture: middleware wiring, scrubbing, Celery hook.

    The SDK pin matters here: posthog-python 6.7.5-6.7.13 shipped with the
    Django middleware silently NOT capturing exceptions (upstream #286, then
    regression #329), and 7.x needs Python >=3.10. The canary tests exist so a
    quiet up- or downgrade fails the suite instead of silently blinding us.
    """

    def test_installed_sdk_is_the_pinned_series(self):
        """
        GIVEN the Pipfile pins posthog to the 6.9 series
        WHEN the installed package version is read
        THEN it is a 6.9.x release
        """
        import posthog.version
        self.assertTrue(
            posthog.version.VERSION.startswith('6.9'),
            f'installed posthog {posthog.version.VERSION}, expected 6.9.x — '
            'read openspec/changes/posthog-error-tracking/design.md before changing the pin',
        )

    def test_middleware_exception_hook_exists(self):
        """
        GIVEN two upstream releases shipped without working exception capture
        WHEN the middleware class is inspected
        THEN process_exception exists — the canary for that regression class
        """
        from posthog.integrations.django import PosthogContextMiddleware
        self.assertTrue(callable(getattr(PosthogContextMiddleware, 'process_exception', None)))

    def test_middleware_is_installed_after_auth(self):
        """
        GIVEN exceptions should carry the signed-in creator's pk as distinct id
        WHEN the middleware order is read
        THEN PosthogContextMiddleware sits after AuthenticationMiddleware
        """
        from django.conf import settings as s
        mw = list(s.MIDDLEWARE)
        self.assertIn('posthog.integrations.django.PosthogContextMiddleware', mw)
        self.assertLess(
            mw.index('django.contrib.auth.middleware.AuthenticationMiddleware'),
            mw.index('posthog.integrations.django.PosthogContextMiddleware'),
        )

    def test_unset_key_disables_the_client(self):
        """
        GIVEN POSTHOG_PROJECT_KEY is empty
        WHEN the app config hook runs
        THEN the module-level client is explicitly disabled
        """
        import posthog

        from survey.apps import SurveyConfig
        with self.settings(POSTHOG_PROJECT_KEY=''):
            SurveyConfig._configure_posthog()
        try:
            self.assertTrue(posthog.disabled)
        finally:
            SurveyConfig._configure_posthog()

    def test_set_key_configures_the_client(self):
        """
        GIVEN POSTHOG_PROJECT_KEY is set
        WHEN the app config hook runs
        THEN api_key and host reach the module-level client and it is enabled
        """
        import posthog

        from survey.apps import SurveyConfig
        with self.settings(POSTHOG_PROJECT_KEY='phc_errtest', POSTHOG_API_HOST=''):
            SurveyConfig._configure_posthog()
        try:
            self.assertFalse(posthog.disabled)
            self.assertEqual(posthog.api_key, 'phc_errtest')
            # Empty host falls back to Cloud EU, same guarantee as the snippet.
            self.assertEqual(posthog.host, 'https://eu.i.posthog.com')
        finally:
            posthog.api_key = None
            SurveyConfig._configure_posthog()

    def test_server_client_ignores_the_browser_proxy_host(self):
        """
        GIVEN a first-party proxy host is configured for the browser
        WHEN the app config hook runs
        THEN the server-side client still talks to POSTHOG_API_HOST directly

        The proxy exists to defeat ad blockers, which do not run inside our
        containers. Routing error capture through it would make the subsystem
        that has to survive an outage depend on a DNS record and a CDN edge.
        """
        import posthog

        from survey.apps import SurveyConfig
        with self.settings(
            POSTHOG_PROJECT_KEY='phc_errtest',
            POSTHOG_API_HOST='https://eu.i.posthog.com',
            POSTHOG_CLIENT_HOST='https://e.example.org',
        ):
            SurveyConfig._configure_posthog()
        try:
            self.assertEqual(posthog.host, 'https://eu.i.posthog.com')
        finally:
            posthog.api_key = None
            SurveyConfig._configure_posthog()

    @staticmethod
    def _sdk_tags_for(path):
        """Tags the real SDK middleware produces for a request, scrubber applied.

        Goes through the middleware's own extract_tags rather than hand-written
        dicts. Hand-written dicts are how the first version of this test passed
        while the scrubber popped `$ip` — a key the SDK never emits — leaving
        the respondent's real IP (`$ip_address`) in the payload.
        """
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory

        from posthog.integrations.django import PosthogContextMiddleware
        request = RequestFactory().get(
            path,
            HTTP_X_FORWARDED_FOR='203.0.113.7',
            HTTP_USER_AGENT='Mozilla/5.0 (probe)',
        )
        request.user = AnonymousUser()
        return PosthogContextMiddleware(lambda r: None).extract_tags(request)

    def test_sdk_tag_names_are_what_we_scrub(self):
        """
        GIVEN the scrubber can only remove tag names that actually exist
        WHEN the SDK middleware builds tags for a request with IP and UA headers
        THEN every name in POSTHOG_RESPONDENT_IDENTIFYING_TAGS is present

        This is the canary. If the SDK renames a tag, this fails loudly instead
        of the scrubber quietly popping nothing and shipping respondent data.
        """
        from django.conf import settings as s
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory

        from posthog.integrations.django import PosthogContextMiddleware
        request = RequestFactory().get(
            '/editor/',
            HTTP_X_FORWARDED_FOR='203.0.113.7',
            HTTP_USER_AGENT='Mozilla/5.0 (probe)',
        )
        request.user = AnonymousUser()
        # Bypass the configured tag map to see the SDK's raw output.
        mw = PosthogContextMiddleware(lambda r: None)
        mw.tag_map = None
        raw = mw.extract_tags(request)
        for tag_name in s.POSTHOG_RESPONDENT_IDENTIFYING_TAGS:
            self.assertIn(
                tag_name, raw,
                f'{tag_name} is not emitted by the installed SDK — the scrubber '
                'would silently remove nothing',
            )

    def test_respondent_path_tags_are_scrubbed(self):
        """
        GIVEN an exception on a respondent survey page is ours to see
        WHEN the real middleware builds tags for a /surveys/ request
        THEN the respondent's IP and user-agent are gone and the URL is
             truncated, so no survey slug or device fingerprint leaves the server
        """
        tags = self._sdk_tags_for('/surveys/abc-123/section1/')
        self.assertNotIn('$ip_address', tags)
        self.assertNotIn('$user_agent', tags)
        self.assertEqual(tags['$request_path'], '/surveys/')
        self.assertEqual(tags['$current_url'], '/surveys/')
        self.assertNotIn('abc-123', str(tags))

    def test_public_results_path_is_scrubbed_too(self):
        """
        GIVEN /r/ pages are read by a customer's audience
        WHEN the middleware builds tags for one
        THEN the same scrubbing applies
        """
        tags = self._sdk_tags_for('/r/some-slug/')
        self.assertNotIn('$ip_address', tags)
        self.assertNotIn('$user_agent', tags)
        self.assertEqual(tags['$request_path'], '/r/')
        self.assertNotIn('some-slug', str(tags))

    def test_creator_path_tags_are_untouched(self):
        """
        GIVEN creator-facing pages are ours to measure fully
        WHEN the middleware builds tags for an /editor/ path
        THEN the IP, user-agent and full URL all survive
        """
        tags = self._sdk_tags_for('/editor/')
        self.assertEqual(tags['$ip_address'], '203.0.113.7')
        self.assertEqual(tags['$user_agent'], 'Mozilla/5.0 (probe)')
        self.assertEqual(tags['$request_path'], '/editor/')

    def test_reporter_is_inert_when_unconfigured(self):
        """
        GIVEN no POSTHOG_PROJECT_KEY, as in tests and local development
        WHEN a view raises
        THEN the reporter stays out of the way instead of raising a second error

        posthog's lazy setup() raises ValueError("API key is required") before it
        ever checks the `disabled` flag, so `disabled = True` alone is not enough.
        Seventeen existing tests that raise on purpose died *inside the reporter*
        before POSTHOG_MW_CAPTURE_EXCEPTIONS was gated on the key — the error
        reporter breaking the error handling it exists to observe.
        """
        from django.conf import settings as s
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory

        from posthog.integrations.django import PosthogContextMiddleware
        self.assertFalse(s.POSTHOG_MW_CAPTURE_EXCEPTIONS)
        self.assertFalse(s.POSTHOG_MW_REQUEST_FILTER(RequestFactory().get('/editor/')))
        mw = PosthogContextMiddleware(lambda r: None)
        request = RequestFactory().get('/editor/')
        request.user = AnonymousUser()
        self.assertIsNone(mw.process_exception(request, RuntimeError('boom')))

    # A believable desktop-browser user-agent. RequestFactory sends none by
    # default, and an absent UA now reads as a bot, so every "this IS tracked"
    # assertion has to say who is asking.
    BROWSER_UA = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36'
    )

    def test_request_filter_skips_admin_but_not_respondents(self):
        """
        GIVEN admin tracebacks embed object reprs and respondent errors are ours
        WHEN the request filter runs
        THEN /admin/ and /__debug__/ are skipped while /surveys/ is captured
        """
        from django.test import RequestFactory

        from mapsurvey.settings import _posthog_skip_request
        rf = RequestFactory(HTTP_USER_AGENT=self.BROWSER_UA)
        # Configured, or the filter short-circuits to False for everything and
        # the admin/respondent distinction below would never be exercised.
        with self.settings(POSTHOG_PROJECT_KEY='phc_filtertest'):
            self.assertFalse(_posthog_skip_request(rf.get('/admin/survey/surveyheader/')))
            self.assertFalse(_posthog_skip_request(rf.get('/__debug__/render_panel/')))
            self.assertTrue(_posthog_skip_request(rf.get('/surveys/abc/section1/')))
            self.assertTrue(_posthog_skip_request(rf.get('/editor/')))

    def test_request_filter_skips_bots(self):
        """
        GIVEN crawlers re-walking dead draft URLs read as "affected users"
        WHEN the request filter sees a bot user-agent or none at all
        THEN the request is excluded from capture entirely
        """
        from django.test import RequestFactory

        from mapsurvey.settings import _posthog_skip_request
        rf = RequestFactory()
        crawler = ('Mozilla/5.0 (compatible; Googlebot/2.1; '
                   '+http://www.google.com/bot.html)')
        with self.settings(POSTHOG_PROJECT_KEY='phc_filtertest'):
            self.assertFalse(_posthog_skip_request(
                rf.get('/surveys/abc/', HTTP_USER_AGENT=crawler)))
            self.assertFalse(_posthog_skip_request(
                rf.get('/surveys/abc/', HTTP_USER_AGENT='python-requests/2.32')))
            # RequestFactory sends no User-Agent unless told to: the absent-UA case.
            self.assertFalse(_posthog_skip_request(rf.get('/surveys/abc/')))
            # And the browser control, or this test passes for the wrong reason.
            self.assertTrue(_posthog_skip_request(
                rf.get('/surveys/abc/', HTTP_USER_AGENT=self.BROWSER_UA)))

    def test_celery_failure_is_reported_with_task_name(self):
        """
        GIVEN the Django middleware never sees the worker
        WHEN a task failure signal fires with the client enabled
        THEN the exception is captured
        """
        import posthog

        from mapsurvey.celery import report_task_failure_to_posthog
        boom = ValueError('task went boom')
        sender = mock.Mock()
        sender.name = 'survey.tasks.generate_survey'
        with mock.patch.object(posthog, 'disabled', False), \
                mock.patch('posthog.capture_exception') as capture:
            report_task_failure_to_posthog(sender=sender, task_id='tid-1', exception=boom)
        capture.assert_called_once_with(boom)

    def test_celery_reporter_never_raises(self):
        """
        GIVEN an error reporter that can break failure handling is worse than none
        WHEN capture itself raises
        THEN the receiver swallows it
        """
        import posthog

        from mapsurvey.celery import report_task_failure_to_posthog
        with mock.patch.object(posthog, 'disabled', False), \
                mock.patch('posthog.capture_exception', side_effect=RuntimeError('down')):
            report_task_failure_to_posthog(
                sender=None, task_id='tid-2', exception=ValueError('x'),
            )  # must not raise

    def test_celery_reporter_noops_when_disabled(self):
        """
        GIVEN POSTHOG_PROJECT_KEY is unset and the client disabled
        WHEN a task failure signal fires
        THEN nothing is captured
        """
        import posthog

        from mapsurvey.celery import report_task_failure_to_posthog
        with mock.patch.object(posthog, 'disabled', True), \
                mock.patch('posthog.capture_exception') as capture:
            report_task_failure_to_posthog(
                sender=None, task_id='tid-3', exception=ValueError('x'),
            )
        capture.assert_not_called()
