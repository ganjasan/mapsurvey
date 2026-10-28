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
