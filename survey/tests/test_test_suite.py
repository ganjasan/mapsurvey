"""Change test-suite-speed (#272): the project test runner.

Spec: `test-suite` (test-only speed settings, media outside the checkout,
a Redis database per parallel worker, worker cap).
"""
import os

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import translation

from mapsurvey import test_runner


class TestRunnerSettingsTest(TestCase):

    def test_password_hasher_is_the_fast_one(self):
        """
        GIVEN a test run started through the project runner
        WHEN a user is created with a password
        THEN the hash is MD5 and logging in with the password still works
        """
        user = User.objects.create_user('runner', password='secret-pass')
        self.assertTrue(user.password.startswith('md5$'))
        self.assertTrue(self.client.login(username='runner', password='secret-pass'))

    def test_media_root_is_outside_the_checkout(self):
        """
        GIVEN a test run started through the project runner
        WHEN a file is saved through the default storage
        THEN it lands in the run's temporary directory, not in the checkout's mediafiles/
        """
        name = default_storage.save('runner-check.txt', ContentFile(b'x'))
        path = os.path.realpath(default_storage.path(name))
        self.assertIn('mapsurvey-test-media-', settings.MEDIA_ROOT)
        self.assertTrue(path.startswith(os.path.realpath(settings.MEDIA_ROOT)))
        self.assertFalse(path.startswith(os.path.realpath(settings.BASE_DIR)))


class WorkerCacheSettingsTest(SimpleTestCase):
    CACHES = {'default': {'BACKEND': 'django_redis.cache.RedisCache',
                          'LOCATION': 'redis://localhost:7389/1', 'OPTIONS': {'x': 1}}}

    def test_each_worker_gets_its_own_database(self):
        """
        GIVEN the run's cache on Redis database 1
        WHEN workers 1 and 2 derive their cache settings
        THEN they use databases 2 and 3, and the original settings are untouched
        """
        one = test_runner.worker_cache_settings(self.CACHES, 1)
        two = test_runner.worker_cache_settings(self.CACHES, 2)
        self.assertEqual(one['default']['LOCATION'], 'redis://localhost:7389/2')
        self.assertEqual(two['default']['LOCATION'], 'redis://localhost:7389/3')
        self.assertEqual(one['default']['OPTIONS'], {'x': 1})
        self.assertEqual(self.CACHES['default']['LOCATION'], 'redis://localhost:7389/1')

    def test_url_without_database(self):
        """
        GIVEN a Redis URL with no database part (database 0)
        WHEN worker 3 derives its cache settings
        THEN it uses database 3
        """
        caches = {'default': {'LOCATION': 'redis://localhost:6379'}}
        self.assertEqual(
            test_runner.worker_cache_settings(caches, 3)['default']['LOCATION'],
            'redis://localhost:6379/3',
        )

    def test_worker_cap(self):
        """
        GIVEN the run's cache on database 1 of 16
        WHEN the runner is asked for 20 workers
        THEN it runs 14, one per remaining database
        """
        self.assertEqual(test_runner.max_workers(self.CACHES), 14)
        with override_settings(CACHES=self.CACHES):
            runner = test_runner.MapsurveyTestRunner(parallel=20)
        self.assertEqual(runner.parallel, 14)


class DefaultLanguagePerTestTest(SimpleTestCase):
    """unittest runs a class's methods in name order, so test_1 always precedes test_2."""

    def test_1_leaves_another_language_active(self):
        """
        GIVEN a test that activates Portuguese
        WHEN it ends without resetting it
        THEN Portuguese is active at its end (the leak the next test must not see)
        """
        translation.activate('pt')
        self.assertEqual(translation.get_language(), 'pt')

    def test_2_starts_in_the_default_language(self):
        """
        GIVEN the previous test in this process left Portuguese active
        WHEN this test starts
        THEN the default language is active and gettext output is in it
        """
        self.assertEqual(translation.get_language(), settings.LANGUAGE_CODE)
        self.assertEqual(translation.gettext('Page title'), 'Page title')


class WorkerCacheIsolationTest(SimpleTestCase):

    def test_clear_in_one_database_keeps_another(self):
        """
        GIVEN a rate-limit counter in one worker's cache database
        WHEN a different worker's database is cleared
        THEN the counter is still there
        """
        mine = test_runner.worker_cache_settings(settings.CACHES, 9)
        theirs = test_runner.worker_cache_settings(settings.CACHES, 10)
        with override_settings(CACHES=mine):
            cache.set('rl:counter', 3)
        with override_settings(CACHES=theirs):
            cache.clear()
        with override_settings(CACHES=mine):
            self.assertEqual(cache.get('rl:counter'), 3)
            cache.clear()


# ── Spec ↔ test-module lineage (change split-survey-tests, #273) ──

# Modules that no capability in openspec/specs/ owns yet. Each is either a
# missing spec or a set of classes to fold into one; this list should shrink.
UNMAPPED_MODULES = {
    'smoke': 'infrastructure smoke test',
    'structure': 'service-layer structure tests (api-v2-structure) spanning survey-editor and question-groups',
    'org-access-control': 'organisations, membership, invitations, role resolution — no spec written yet',
    'survey-versioning': 'versioning model, clone and publish core — predates OpenSpec',
    'survey-lifecycle-states': 'draft/testing/published/closed transitions — predates OpenSpec',
    'survey-password-protection': 'password gate — predates OpenSpec',
    'survey-analytics-basic': 'pre-v2 SurveyAnalyticsService and view',
    'response-validation-management': 'session validation, linting, tags and notes (Data Management epic)',
    'htmx-section-navigation': 'HTMX section navigation of the respondent page',
    'form-required-validation': 'required-field summary on the respondent form',
    'respondent-touch-copy': 'tap-phrased respondent copy; its change (respondent bottom sheet) was removed',
    'creator-language-preference': 'spec lives in the unarchived change creator-ui-localization',
    'repo-hygiene': 'spec lives in the unarchived change ops-repo-separation',
    'question-audience': 'spec lives in the unarchived change operator-entry',
    'operator-entry': 'spec lives in the unarchived change operator-entry',
}

# Capabilities with no module here: tested in another app, or not by any
# automated test yet (the last group is the "capabilities without tests" list).
SPECS_WITHOUT_SURVEY_TESTS = {
    **dict.fromkeys(['api-access-rights', 'api-authentication', 'api-pro-gate', 'api-rate-limits',
                     'connected-apps', 'oauth-authorization-server', 'oauth-client-registration',
                     'personal-access-tokens', 'rest-api-v1'], 'api/tests'),
    'mcp-server': 'mcp/tests',
    **dict.fromkeys(['billing-checkout', 'billing-webhooks', 'made-with-badge', 'plan-entitlements',
                     'pricing', 'pro-help-channel', 'pro-trial-allowances', 'subscription-management'],
                    'billing/tests'),
    **dict.fromkeys(['abuse-event-log', 'analytics-transport', 'crosshair-marker-edit', 'deploy-startup',
                     'geo-field-validation', 'map-place-search', 'marker-popup-isolation',
                     'mobile-point-crosshair', 'project-governance-docs', 'responses-coverage-contrast',
                     'session-geo-map', 'session-replay'], 'no module yet'),
}


def _module_capabilities(module_files):
    return {f[len('test_'):-len('.py')].replace('_', '-') for f in module_files
            if f.startswith('test_') and f.endswith('.py')}


def lineage_problems(module_files, spec_dirs, unmapped=UNMAPPED_MODULES, untested=SPECS_WITHOUT_SURVEY_TESTS):
    """Return (modules naming nothing, specs without a module); both should be empty."""
    modules = _module_capabilities(module_files)
    specs = set(spec_dirs)
    stray = sorted(modules - specs - set(unmapped))
    missing = sorted(specs - modules - set(untested))
    return stray, missing


class SpecTestLineageTest(SimpleTestCase):
    """Spec: test-suite / Requirement: A guard keeps specs and test modules in step."""

    def _actual(self):
        tests_dir = os.path.dirname(os.path.abspath(__file__))
        specs_dir = os.path.join(os.path.dirname(os.path.dirname(tests_dir)), 'openspec', 'specs')
        return os.listdir(tests_dir), [d for d in os.listdir(specs_dir)
                                       if os.path.isdir(os.path.join(specs_dir, d))]

    def test_every_module_names_a_spec_and_every_spec_has_a_module(self):
        """
        GIVEN the survey test modules and the folders under openspec/specs/
        WHEN they are compared
        THEN every module names a spec or is listed as unmapped, and every spec has a module
             or is listed as tested elsewhere / not yet
        """
        stray, missing = lineage_problems(*self._actual())
        self.assertEqual(stray, [], 'test modules naming no spec: add the spec, rename the module, '
                                    'or list it in UNMAPPED_MODULES with a reason')
        self.assertEqual(missing, [], 'specs without survey/tests/test_<capability>.py: add the module '
                                      'or list the spec in SPECS_WITHOUT_SURVEY_TESTS')

    def test_allow_lists_carry_no_stale_entries(self):
        """
        GIVEN the two allow-lists
        WHEN a listed module now has a spec, or a listed spec now has a module or is gone
        THEN the entry is reported, so the lists only ever shrink
        """
        module_files, spec_dirs = self._actual()
        modules, specs = _module_capabilities(module_files), set(spec_dirs)
        self.assertEqual(sorted(u for u in UNMAPPED_MODULES if u in specs or u not in modules), [])
        self.assertEqual(sorted(s for s in SPECS_WITHOUT_SURVEY_TESTS if s in modules or s not in specs), [])

    def test_new_spec_without_module_is_reported(self):
        """
        GIVEN a new spec folder foo-bar and no test_foo_bar.py
        WHEN the lineage is checked
        THEN foo-bar is reported as missing
        """
        _, missing = lineage_problems(['test_public_stories.py'], ['public-stories', 'foo-bar'],
                                      unmapped={}, untested={})
        self.assertEqual(missing, ['foo-bar'])

    def test_module_naming_no_spec_is_reported(self):
        """
        GIVEN a module test_misc_stuff.py with no spec and no allow-list entry
        WHEN the lineage is checked
        THEN the module is reported
        """
        stray, _ = lineage_problems(['test_misc_stuff.py', 'helpers.py'], [], unmapped={}, untested={})
        self.assertEqual(stray, ['misc-stuff'])
