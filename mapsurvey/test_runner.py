"""Project test runner (change test-suite-speed, #272).

Applies the settings a test run needs and production must never get, for every
``manage.py test`` whatever started it (``run_tests.sh``, an agent, an IDE):

- a fast password hasher: ~350 ``setUp`` methods create users, and PBKDF2 per
  ``create_user``/``login`` was a large share of the run;
- a throw-away ``MEDIA_ROOT``, so tests stop writing into the checkout's
  ``mediafiles/`` and parallel workers never delete each other's files;
- under ``--parallel``, one Redis database per worker. django-redis
  ``cache.clear()`` is ``FLUSHDB``: in a shared database one worker's clear
  wipes the rate-limit and activity keys another worker's test is counting on.

``override_settings`` rather than assignment, because its ``setting_changed``
signal is what resets the hasher cache, the storages and the cache handlers.
"""
import shutil
import tempfile

from django.conf import settings
from django.test import override_settings
from django.test import runner as django_runner

# Redis ships with 16 logical databases (0..15).
REDIS_DATABASES = 16


def _split_redis_url(url):
    """``redis://host:port/1`` -> (``redis://host:port``, 1); no db part = 0."""
    head, sep, tail = url.rpartition('/')
    if sep and tail.isdigit() and '://' in head:
        return head, int(tail)
    return url.rstrip('/'), 0


def worker_cache_settings(caches, worker_id):
    """CACHES with the default Redis cache moved to database ``base + worker_id``."""
    caches = {alias: dict(conf) for alias, conf in caches.items()}
    default = caches['default']
    base_url, base_db = _split_redis_url(default['LOCATION'])
    default['LOCATION'] = f'{base_url}/{base_db + worker_id}'
    return caches


def max_workers(caches):
    """How many workers can each get a Redis database above the run's own."""
    _, base_db = _split_redis_url(caches['default']['LOCATION'])
    return REDIS_DATABASES - 1 - base_db


def _init_worker(*args, **kwargs):
    # Module-level: multiprocessing needs to find the initializer by name.
    django_runner._init_worker(*args, **kwargs)
    override_settings(
        CACHES=worker_cache_settings(settings.CACHES, django_runner._worker_id),
    ).enable()


class MapsurveyParallelTestSuite(django_runner.ParallelTestSuite):
    init_worker = _init_worker


class MapsurveyTestRunner(django_runner.DiscoverRunner):
    parallel_test_suite = MapsurveyParallelTestSuite

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parallel = min(self.parallel, max_workers(settings.CACHES))

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._media_root = tempfile.mkdtemp(prefix='mapsurvey-test-media-')
        self._test_settings = override_settings(
            PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
            MEDIA_ROOT=self._media_root,
        )
        self._test_settings.enable()

    def teardown_test_environment(self, **kwargs):
        self._test_settings.disable()
        shutil.rmtree(self._media_root, ignore_errors=True)
        super().teardown_test_environment(**kwargs)
