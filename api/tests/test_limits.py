"""`api-rate-limits`: per-token windows, named caps, per-IP failed attempts, fail-open."""
from unittest import mock

from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from .. import auth, limits
from ..errors import ApiError
from ..models import AUDIENCE_API
from .helpers import LOCMEM, bearer, make_org, mint

ME = reverse('api_me')


def principal_for(user):
    value, _ = mint(user)
    return value, auth.authenticate(RequestFactory().get('/', **bearer(value)), AUDIENCE_API)


@LOCMEM
class PerTokenWindowsTest(TestCase):
    def setUp(self):
        cache.clear()
        limits.reset_warning_for_tests()
        self.org, self.owner = make_org()
        self.value, _ = mint(self.owner)

    @override_settings(API_RATE_LIMITS={'api.write': (3, 60)})
    def test_write_window(self):
        """
        GIVEN a write limit of 3 per minute
        WHEN a token makes 4 POSTs
        THEN the 4th is 429 rate_limited with limit api.write and Retry-After ≤ 60
        """
        for _ in range(3):
            self.assertEqual(self.client.post(ME, **bearer(self.value)).status_code, 200)
        response = self.client.post(ME, **bearer(self.value))
        self.assertEqual(response.status_code, 429)
        body = response.json()
        self.assertEqual(body['error'], 'rate_limited')
        self.assertEqual(body['limit'], 'api.write')
        self.assertLessEqual(int(response['Retry-After']), 60)
        self.assertEqual(body['retry_after'], int(response['Retry-After']))

    @override_settings(API_RATE_LIMITS={'api.write': (3, 60)})
    def test_two_tokens_one_ip_independent(self):
        """
        GIVEN two tokens behind one client IP
        WHEN each spends its write budget
        THEN both get their full budget
        """
        other, _ = mint(self.owner)
        for _ in range(3):
            self.assertEqual(self.client.post(ME, **bearer(self.value)).status_code, 200)
            self.assertEqual(self.client.post(ME, **bearer(other)).status_code, 200)

    @override_settings(API_RATE_LIMITS={'api.write': (2, 60), 'api.read': (50, 60)})
    def test_reads_do_not_consume_writes(self):
        """
        GIVEN 40 GETs and 2 POSTs
        WHEN made within a minute
        THEN none is 429
        """
        for _ in range(40):
            response = self.client.get(ME, **bearer(self.value))
            self.assertEqual(response.status_code, 200, response.content)
        for _ in range(2):
            response = self.client.post(ME, **bearer(self.value))
            self.assertEqual(response.status_code, 200, response.content)

    @override_settings(API_RATE_LIMITS={'api.day': (4, 86400)})
    def test_daily_cap(self):
        """
        GIVEN a daily cap of 4
        WHEN a token makes 5 reads
        THEN the 5th is 429 with limit api.day
        """
        for _ in range(4):
            self.assertEqual(self.client.get(ME, **bearer(self.value)).status_code, 200)
        response = self.client.get(ME, **bearer(self.value))
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()['limit'], 'api.day')


@LOCMEM
class NamedCapsTest(TestCase):
    def setUp(self):
        cache.clear()
        self.org, self.owner = make_org()
        _, self.principal = principal_for(self.owner)

    @override_settings(API_RATE_LIMITS={'cap.survey_create': (2, 86400)})
    def test_named_cap(self):
        """
        GIVEN survey_create capped at 2 a day
        WHEN hit is called three times
        THEN the third raises 429 with limit survey_create
        """
        limits.hit(self.principal, 'survey_create')
        limits.hit(self.principal, 'survey_create')
        with self.assertRaises(ApiError) as cm:
            limits.hit(self.principal, 'survey_create')
        self.assertEqual(cm.exception.status, 429)
        self.assertEqual(cm.exception.extra['limit'], 'survey_create')
        self.assertIn('Retry-After', cm.exception.headers)

    def test_unregistered_action_is_a_programming_error(self):
        """
        GIVEN an action name not in DAILY_CAPS
        WHEN hit is called
        THEN KeyError
        """
        with self.assertRaises(KeyError):
            limits.hit(self.principal, 'surveys_frobnicate')

    def test_registry_values(self):
        """
        GIVEN the defaults
        WHEN read
        THEN the documented numbers hold
        """
        self.assertEqual(limits.DAILY_CAPS['survey_create'], 50)
        self.assertEqual(limits.DAILY_CAPS['survey_delete'], 20)
        self.assertEqual(limits.DEFAULT_LIMITS['api.read'], (600, 60))
        self.assertEqual(limits.DEFAULT_LIMITS['api.write'], (60, 60))
        self.assertEqual(limits.DEFAULT_LIMITS['api.day'], (5000, 86400))
        self.assertEqual(limits.DEFAULT_LIMITS['api.auth_fail'], (30, 60))


@LOCMEM
class FailedAttemptsTest(TestCase):
    def setUp(self):
        cache.clear()
        self.org, self.owner = make_org()
        self.value, _ = mint(self.owner)

    @override_settings(API_RATE_LIMITS={'api.auth_fail': (3, 60)})
    def test_token_guessing_is_cut_off_before_the_lookup(self):
        """
        GIVEN 3 failed attempts allowed per minute
        WHEN a 4th random bearer arrives from the same IP
        THEN 429 and no token lookup query
        """
        for _ in range(3):
            self.assertEqual(self.client.get(ME, **bearer('msk_' + 'q' * 43)).status_code, 401)
        with self.assertNumQueries(0):
            response = self.client.get(ME, **bearer('msk_' + 'w' * 43))
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()['limit'], 'api.auth_fail')
        # And a VALID token from that IP is now also refused with 429 for the window --
        # the budget is per IP; a legitimate client sharing it waits a minute.
        self.assertEqual(self.client.get(ME, **bearer(self.value)).status_code, 429)

    @override_settings(API_RATE_LIMITS={'api.auth_fail': (10, 60)})
    def test_valid_traffic_unaffected_by_a_few_failures(self):
        """
        GIVEN 5 failures from an IP within budget
        WHEN a valid token makes 20 calls from it
        THEN all succeed and successes do not count as failures
        """
        for _ in range(5):
            self.client.get(ME, **bearer('msk_' + 'q' * 43))
        for _ in range(20):
            self.assertEqual(self.client.get(ME, **bearer(self.value)).status_code, 200)
        exceeded, _ = limits.auth_failures_exceeded('127.0.0.1')
        self.assertFalse(exceeded)

    @override_settings(API_RATE_LIMITS={'api.auth_fail': (2, 60)})
    def test_malformed_values_count_too(self):
        """
        GIVEN prefix-less garbage
        WHEN sent three times
        THEN the third is 429
        """
        self.client.get(ME, **bearer('garbage'))
        self.client.get(ME, **bearer('garbage'))
        self.assertEqual(self.client.get(ME, **bearer('garbage')).status_code, 429)


@LOCMEM
class FailOpenTest(TestCase):
    def setUp(self):
        cache.clear()
        limits.reset_warning_for_tests()
        self.org, self.owner = make_org()
        self.value, _ = mint(self.owner)

    def test_cache_outage_lets_requests_through_and_warns_once(self):
        """
        GIVEN the cache raising on every operation
        WHEN two requests arrive
        THEN both succeed and one warning is logged
        """
        with mock.patch('api.limits.cache') as fake:
            fake.add.side_effect = RuntimeError('redis down')
            fake.get.side_effect = RuntimeError('redis down')
            fake.incr.side_effect = RuntimeError('redis down')
            with self.assertLogs('api.limits', level='WARNING') as logs:
                self.assertEqual(self.client.get(ME, **bearer(self.value)).status_code, 200)
                self.assertEqual(self.client.get(ME, **bearer(self.value)).status_code, 200)
        self.assertEqual(len(logs.records), 1)
