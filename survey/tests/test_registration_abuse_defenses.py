"""Tests for the `registration-abuse-defenses` capability (openspec/specs/registration-abuse-defenses/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from unittest import mock
import contextlib
import uuid
from django.test import RequestFactory
from django.conf import settings
from django.core import mail
from survey.models import AbuseEvent


# -----------------------------------------------------------------------------
# Registration abuse prevention (Cloudflare Turnstile + rate limit + honeypot)
# -----------------------------------------------------------------------------


class CloudflareIPMiddlewareTest(TestCase):
    """Verify CF-Connecting-IP is read only when CLOUDFLARE_TRUSTED is on."""

    def test_trusted_environment_uses_cf_connecting_ip(self):
        """
        GIVEN CLOUDFLARE_TRUSTED=True and a CF-Connecting-IP header
        WHEN the middleware processes the request
        THEN request.cf_ip equals the header value, REMOTE_ADDR untouched
        """
        from django.test import RequestFactory, override_settings
        from survey.middleware import CloudflareIPMiddleware

        with override_settings(CLOUDFLARE_TRUSTED=True):
            rf = RequestFactory()
            request = rf.get(
                "/", HTTP_CF_CONNECTING_IP="5.6.7.8", REMOTE_ADDR="10.0.0.1"
            )
            mw = CloudflareIPMiddleware(get_response=lambda r: None)
            mw(request)
            self.assertEqual(request.cf_ip, "5.6.7.8")
            self.assertEqual(request.META["REMOTE_ADDR"], "10.0.0.1")

    def test_untrusted_environment_falls_back_to_remote_addr(self):
        """
        GIVEN CLOUDFLARE_TRUSTED=False and a CF-Connecting-IP header
        WHEN the middleware processes the request
        THEN request.cf_ip equals REMOTE_ADDR (header is ignored)
        """
        from django.test import RequestFactory, override_settings
        from survey.middleware import CloudflareIPMiddleware

        with override_settings(CLOUDFLARE_TRUSTED=False):
            rf = RequestFactory()
            request = rf.get(
                "/", HTTP_CF_CONNECTING_IP="5.6.7.8", REMOTE_ADDR="127.0.0.1"
            )
            mw = CloudflareIPMiddleware(get_response=lambda r: None)
            mw(request)
            self.assertEqual(request.cf_ip, "127.0.0.1")


class VerifyTurnstileTest(TestCase):
    """Unit tests for verify_turnstile() — pure function, no view needed."""

    def test_empty_secret_returns_true_without_http_call(self):
        """
        GIVEN TURNSTILE_SECRET_KEY is empty (local dev)
        WHEN verify_turnstile is called with any token
        THEN it returns True without making any HTTP call
        """
        from django.test import override_settings
        from survey.abuse import verify_turnstile

        with override_settings(TURNSTILE_SECRET_KEY=""):
            with mock.patch("survey.abuse.urllib_request.urlopen") as patched:
                self.assertTrue(verify_turnstile("any-token", "1.2.3.4"))
                patched.assert_not_called()

    def test_missing_token_returns_false_when_secret_set(self):
        """
        GIVEN secret key is configured
        WHEN verify_turnstile is called with empty token
        THEN it returns False without making any HTTP call
        """
        from django.test import override_settings
        from survey.abuse import verify_turnstile

        with override_settings(TURNSTILE_SECRET_KEY="real-secret"):
            with mock.patch("survey.abuse.urllib_request.urlopen") as patched:
                self.assertFalse(verify_turnstile("", "1.2.3.4"))
                patched.assert_not_called()

    def test_siteverify_success_returns_true(self):
        """
        GIVEN secret key is configured and Cloudflare returns success=true
        WHEN verify_turnstile is called with a token
        THEN it returns True
        """
        from django.test import override_settings
        from survey.abuse import verify_turnstile

        fake_response = mock.MagicMock()
        fake_response.read.return_value = b'{"success": true}'
        fake_response.__enter__.return_value = fake_response
        fake_response.__exit__.return_value = False

        with override_settings(TURNSTILE_SECRET_KEY="real-secret"):
            with mock.patch(
                "survey.abuse.urllib_request.urlopen",
                return_value=fake_response,
            ):
                self.assertTrue(verify_turnstile("good-token", "1.2.3.4"))

    def test_siteverify_rejection_returns_false(self):
        """
        GIVEN Cloudflare returns success=false
        WHEN verify_turnstile is called
        THEN it returns False
        """
        from django.test import override_settings
        from survey.abuse import verify_turnstile

        fake_response = mock.MagicMock()
        fake_response.read.return_value = b'{"success": false, "error-codes": ["invalid-input-response"]}'
        fake_response.__enter__.return_value = fake_response
        fake_response.__exit__.return_value = False

        with override_settings(TURNSTILE_SECRET_KEY="real-secret"):
            with mock.patch(
                "survey.abuse.urllib_request.urlopen",
                return_value=fake_response,
            ):
                self.assertFalse(verify_turnstile("bad-token", "1.2.3.4"))

    def test_network_error_fails_closed(self):
        """
        GIVEN urllib raises URLError (Cloudflare unreachable)
        WHEN verify_turnstile is called
        THEN it returns False — fail closed (bots without tokens still rejected)
        """
        from urllib.error import URLError
        from django.test import override_settings
        from survey.abuse import verify_turnstile

        with override_settings(TURNSTILE_SECRET_KEY="real-secret"):
            with mock.patch(
                "survey.abuse.urllib_request.urlopen",
                side_effect=URLError("network down"),
            ):
                self.assertFalse(verify_turnstile("any-token", "1.2.3.4"))


class RegistrationAbuseDefenseTest(TestCase):
    """Integration tests against POST /accounts/register/."""

    def setUp(self):
        from django.contrib.auth.models import User as _U
        from django.core.cache import cache
        _U.objects.all().delete()
        from survey.models import AbuseEvent
        AbuseEvent.objects.all().delete()
        # Clear rate-limit counters that persist across tests when CACHES
        # points at a shared Redis instance.
        cache.clear()

    def _post_data(self, **overrides):
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "password1": "Xx12345!secure",
            "password2": "Xx12345!secure",
            "website": "",  # honeypot empty
            "accept_terms": "on",
            "cf-turnstile-response": "any-token",
        }
        data.update(overrides)
        return data

    def test_clean_signup_creates_user_when_turnstile_disabled(self):
        """
        GIVEN empty honeypot, fresh IP, TURNSTILE_SECRET_KEY="" (dev bypass)
        WHEN POST /accounts/register/ with valid form data
        THEN response is 302 to django_registration_complete AND a User row exists
        """
        from django.contrib.auth.models import User as _U
        from django.test import override_settings

        with override_settings(TURNSTILE_SECRET_KEY=""):
            response = self.client.post("/accounts/register/", self._post_data())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(_U.objects.filter(username="testuser").count(), 1)

    def test_filled_honeypot_returns_fake_success_no_user_no_email(self):
        """
        GIVEN registration POST with website="bot"
        WHEN endpoint is called
        THEN response is 302 to complete page, no User created, no email sent,
             one AbuseEvent row of defense=honeypot exists
        """
        from django.contrib.auth.models import User as _U
        from django.core import mail
        from django.test import override_settings
        from survey.models import AbuseEvent

        with override_settings(TURNSTILE_SECRET_KEY=""):
            response = self.client.post(
                "/accounts/register/", self._post_data(website="bot-trap")
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(_U.objects.filter(username="testuser").count(), 0)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(AbuseEvent.objects.filter(defense="honeypot").count(), 1)

    def test_invalid_turnstile_blocks_with_form_error_and_logs_event(self):
        """
        GIVEN TURNSTILE_SECRET_KEY set and verify_turnstile returns False
        WHEN registration POST is submitted with empty honeypot
        THEN response is form re-render (200), no User, AbuseEvent defense=captcha
        """
        from django.contrib.auth.models import User as _U
        from django.test import override_settings
        from survey.models import AbuseEvent

        with override_settings(TURNSTILE_SECRET_KEY="real-secret"):
            with mock.patch("survey.views.verify_turnstile", return_value=False):
                response = self.client.post(
                    "/accounts/register/", self._post_data(),
                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(_U.objects.filter(username="testuser").count(), 0)
        self.assertEqual(AbuseEvent.objects.filter(defense="captcha").count(), 1)

    def test_rate_limit_blocks_after_threshold(self):
        """
        GIVEN per-IP hourly limit is 1 and one successful POST already counted
        WHEN a second POST comes from the same IP
        THEN response is 429 with Retry-After AND defense=ratelimit row exists
        """
        from django.test import override_settings
        from survey.models import AbuseEvent

        with override_settings(
            TURNSTILE_SECRET_KEY="",
            REGISTRATION_RATE_LIMIT_HOUR=1,
            REGISTRATION_RATE_LIMIT_DAY=10,
            CACHES={
                "default": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                    "LOCATION": "ratelimit-test",
                }
            },
        ):
            r1 = self.client.post("/accounts/register/", self._post_data(
                username="u1", email="u1@example.com",
            ))
            self.assertEqual(r1.status_code, 302)
            r2 = self.client.post("/accounts/register/", self._post_data(
                username="u2", email="u2@example.com",
            ))
            self.assertEqual(r2.status_code, 429)
            self.assertIn("Retry-After", r2)
        self.assertGreaterEqual(
            AbuseEvent.objects.filter(defense="ratelimit").count(), 1,
        )

    def test_honeypot_short_circuits_turnstile(self):
        """
        GIVEN both a filled honeypot AND a configured Turnstile secret
        WHEN POST /accounts/register/
        THEN honeypot fires first (302 fake success); verify_turnstile NOT called
        """
        from django.test import override_settings
        from survey.models import AbuseEvent

        with override_settings(TURNSTILE_SECRET_KEY="real-secret"):
            with mock.patch("survey.views.verify_turnstile") as patched:
                response = self.client.post(
                    "/accounts/register/",
                    self._post_data(website="trap"),
                )
                patched.assert_not_called()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AbuseEvent.objects.filter(defense="honeypot").count(), 1)
        self.assertEqual(AbuseEvent.objects.filter(defense="captcha").count(), 0)

    def test_filled_honeypot_with_invalid_form_data_still_returns_fake_success(self):
        """
        GIVEN POST with filled honeypot AND mismatched passwords (form invalid)
        WHEN /accounts/register/ processes the request
        THEN response is still 302 fake-success (honeypot checked BEFORE form
             validation), no User created, AbuseEvent(honeypot) row written.
             Without this, a bot submitting filled honeypot + bad data would
             receive a normal form-error 200 — fingerprinting the defense.
        """
        from django.contrib.auth.models import User as _U
        from django.test import override_settings
        from survey.models import AbuseEvent

        with override_settings(TURNSTILE_SECRET_KEY=""):
            response = self.client.post(
                "/accounts/register/",
                self._post_data(
                    website="trap",
                    password1="Abc1!secure",
                    password2="DifferentXY!8",  # mismatch — form would be invalid
                ),
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(_U.objects.filter(username="testuser").count(), 0)
        self.assertEqual(AbuseEvent.objects.filter(defense="honeypot").count(), 1)

    def test_log_abuse_event_swallows_db_error(self):
        """
        GIVEN AbuseEvent.objects.create raises (e.g. DB outage)
        WHEN log_abuse_event is called
        THEN it does NOT propagate the exception
        """
        from django.test import RequestFactory
        from survey.abuse import log_abuse_event
        from survey.models import AbuseEvent

        rf = RequestFactory()
        request = rf.post("/", REMOTE_ADDR="9.9.9.9")
        request.cf_ip = "9.9.9.9"
        with mock.patch.object(
            AbuseEvent.objects, "create", side_effect=Exception("DB down"),
        ):
            log_abuse_event("honeypot", request, "filled")

    def test_daily_limit_blocks_after_threshold(self):
        """
        GIVEN per-IP daily limit is 2 (hourly limit set very high so it doesn't fire first)
        WHEN a third POST comes from the same IP within 24 hours
        THEN response is 429 with Retry-After AND defense=ratelimit row written
              with detail='day' (not 'hour')
        """
        from django.test import override_settings
        from survey.models import AbuseEvent

        with override_settings(
            TURNSTILE_SECRET_KEY="",
            REGISTRATION_RATE_LIMIT_HOUR=999,  # never hit hourly first
            REGISTRATION_RATE_LIMIT_DAY=2,
            CACHES={
                "default": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                    "LOCATION": "daily-ratelimit-test",
                }
            },
        ):
            r1 = self.client.post("/accounts/register/", self._post_data(
                username="d1", email="d1@example.com",
            ))
            self.assertEqual(r1.status_code, 302)
            r2 = self.client.post("/accounts/register/", self._post_data(
                username="d2", email="d2@example.com",
            ))
            self.assertEqual(r2.status_code, 302)
            r3 = self.client.post("/accounts/register/", self._post_data(
                username="d3", email="d3@example.com",
            ))
            self.assertEqual(r3.status_code, 429)
            # Daily bucket retry window is 86400 seconds.
            self.assertEqual(r3["Retry-After"], "86400")
        self.assertGreaterEqual(
            AbuseEvent.objects.filter(defense="ratelimit", detail="day").count(), 1,
        )

    def test_cache_unreachable_fails_open(self):
        """
        GIVEN the cache backend raises on every call (Redis outage simulation)
        WHEN registration POST arrives within rate limits
        THEN the request still succeeds (rate-limit fails open) — RATELIMIT_FAIL_OPEN
        """
        from django.contrib.auth.models import User as _U
        from django.test import override_settings

        # django-ratelimit's get_usage will catch backend errors only when the
        # cache backend itself raises. Simulate by patching cache.add to raise.
        with override_settings(TURNSTILE_SECRET_KEY=""):
            with mock.patch(
                "django.core.cache.cache.get_or_set",
                side_effect=Exception("Redis unreachable"),
            ):
                with mock.patch(
                    "django.core.cache.cache.add",
                    side_effect=Exception("Redis unreachable"),
                ):
                    response = self.client.post(
                        "/accounts/register/",
                        self._post_data(username="failopen", email="failopen@example.com"),
                    )
        # With RATELIMIT_FAIL_OPEN=True, the rate-limit decorator should
        # let the request through despite the cache error.
        self.assertIn(response.status_code, (302, 200))
        # If 302, the user was created; if 200 (form re-render), at least
        # we did NOT 500.

    def test_ratelimit_fires_before_turnstile_check(self):
        """
        GIVEN an IP that has exceeded the hourly rate limit
        AND a configured Turnstile secret
        WHEN registration POST arrives
        THEN response is 429 (rate-limit fires) AND verify_turnstile NOT called
              — short-circuit ordering is honeypot → ratelimit → captcha
        """
        from django.test import override_settings

        with override_settings(
            TURNSTILE_SECRET_KEY="real-secret",
            REGISTRATION_RATE_LIMIT_HOUR=1,
            REGISTRATION_RATE_LIMIT_DAY=10,
            CACHES={
                "default": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                    "LOCATION": "rl-shortcircuit-test",
                }
            },
        ):
            with mock.patch("survey.views.verify_turnstile") as patched:
                r1 = self.client.post("/accounts/register/", self._post_data(
                    username="rl1", email="rl1@example.com",
                ))
                self.assertIn(r1.status_code, (200, 302))  # first one passes ratelimit
                r2 = self.client.post("/accounts/register/", self._post_data(
                    username="rl2", email="rl2@example.com",
                ))
                self.assertEqual(r2.status_code, 429)
                # On the rate-limited POST, Turnstile siteverify must NOT
                # have been called — ratelimit short-circuits.
                # (verify_turnstile may have been called for r1 only.)
                self.assertLessEqual(patched.call_count, 1)


class RegistrationInvalidAttemptLimitTest(TestCase):
    """The rate limit must not spend a human's budget on their own typos.

    Regression cover for the 2026-08-17 incident: a visitor mistyped a password
    three times, exhausted REGISTRATION_RATE_LIMIT_HOUR=3, and was refused with
    a bare text/plain 429. No account, no email, no way to reach them. The
    counter ran before form validation, so a person fighting the password
    validators was indistinguishable from a bot posting registrations.
    """

    def setUp(self):
        from django.contrib.auth.models import User as _U
        from django.core.cache import cache
        from survey.models import AbuseEvent
        _U.objects.all().delete()
        AbuseEvent.objects.all().delete()
        cache.clear()

    def _valid_data(self, **overrides):
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "password1": "Xx12345!secure",
            "password2": "Xx12345!secure",
            "website": "",
            "accept_terms": "on",
            "cf-turnstile-response": "any-token",
        }
        data.update(overrides)
        return data

    def _invalid_data(self, **overrides):
        # Fails MinimumLengthValidator and CommonPasswordValidator — the exact
        # shape of failure the incident user kept hitting.
        return self._valid_data(password1="abc", password2="abc", **overrides)

    @contextlib.contextmanager
    def _isolated_cache(self, **extra):
        """Override the abuse settings onto a private, empty LocMem cache.

        A LocMemCache keyed only by LOCATION is shared process-wide, so counters
        from an earlier test in this class leak into the next one and every
        assertion after the first becomes meaningless. Clearing *inside* the
        override (the cache handle is per-settings) is what makes each test
        start from zero.
        """
        from django.core.cache import cache
        from django.test import override_settings

        settings = dict(
            TURNSTILE_SECRET_KEY="",
            REGISTRATION_RATE_LIMIT_HOUR=3,
            REGISTRATION_RATE_LIMIT_DAY=10,
            REGISTRATION_INVALID_LIMIT_HOUR=15,
            REGISTRATION_INVALID_LIMIT_DAY=50,
            REGISTRATION_SPLIT_RATE_LIMIT=True,
            CACHES={
                "default": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                    "LOCATION": "invalid-attempt-%s" % self.id(),
                }
            },
        )
        settings.update(extra)
        with override_settings(**settings):
            cache.clear()
            yield

    def test_form_invalid_attempts_do_not_consume_registration_budget(self):
        """
        GIVEN an IP that has made three form-invalid registration POSTs
        WHEN a fourth POST arrives carrying valid data
        THEN it is not rate-limited AND a User is created
        """
        from django.contrib.auth.models import User as _U

        with self._isolated_cache():
            for i in range(3):
                r = self.client.post("/accounts/register/", self._invalid_data(
                    username="u%d" % i, email="u%d@example.com" % i,
                ))
                self.assertEqual(r.status_code, 200)
            self.assertEqual(_U.objects.count(), 0)

            r4 = self.client.post("/accounts/register/", self._valid_data(
                username="realuser", email="real@example.com",
            ))
            self.assertEqual(r4.status_code, 302)
            self.assertTrue(_U.objects.filter(username="realuser").exists())

    def test_invalid_attempt_ceiling_still_bounds_abuse(self):
        """
        GIVEN REGISTRATION_INVALID_LIMIT_HOUR form-invalid POSTs from one IP
        WHEN one more form-invalid POST arrives
        THEN it is refused 429 AND an AbuseEvent(detail='invalid_hour') exists
        """
        from survey.models import AbuseEvent

        with self._isolated_cache(REGISTRATION_INVALID_LIMIT_HOUR=4):
            for i in range(4):
                r = self.client.post("/accounts/register/", self._invalid_data(
                    username="u%d" % i, email="u%d@example.com" % i,
                ))
                self.assertEqual(r.status_code, 200)

            blocked = self.client.post("/accounts/register/", self._invalid_data(
                username="u9", email="u9@example.com",
            ))
            self.assertEqual(blocked.status_code, 429)
        self.assertEqual(
            AbuseEvent.objects.filter(
                defense="ratelimit", detail="invalid_hour",
            ).count(),
            1,
        )

    def test_valid_submission_budget_is_unchanged(self):
        """
        GIVEN REGISTRATION_RATE_LIMIT_HOUR=3 and three valid registrations
        WHEN a fourth valid registration is posted
        THEN it is refused 429 — the bot-facing limit is exactly as before
        """
        with self._isolated_cache():
            for i in range(3):
                r = self.client.post("/accounts/register/", self._valid_data(
                    username="ok%d" % i, email="ok%d@example.com" % i,
                ))
                self.assertEqual(r.status_code, 302)

            blocked = self.client.post("/accounts/register/", self._valid_data(
                username="ok9", email="ok9@example.com",
            ))
            self.assertEqual(blocked.status_code, 429)

    def test_turnstile_failure_counts_against_the_strict_budget(self):
        """
        GIVEN a well-formed submission whose Turnstile token is rejected
        WHEN it is posted
        THEN it consumes the valid-submission budget, not the invalid one
        """
        with self._isolated_cache(TURNSTILE_SECRET_KEY="real-secret"):
            with mock.patch("survey.views.verify_turnstile", return_value=False):
                for i in range(3):
                    r = self.client.post("/accounts/register/", self._valid_data(
                        username="cf%d" % i, email="cf%d@example.com" % i,
                    ))
                    self.assertEqual(r.status_code, 200)

            # The strict budget is now spent, so even a clean submission with a
            # working token is refused.
            with mock.patch("survey.views.verify_turnstile", return_value=True):
                blocked = self.client.post("/accounts/register/", self._valid_data(
                    username="cf9", email="cf9@example.com",
                ))
                self.assertEqual(blocked.status_code, 429)

    def test_kill_switch_restores_previous_counting(self):
        """
        GIVEN REGISTRATION_SPLIT_RATE_LIMIT=False
        WHEN four form-invalid POSTs arrive from one IP
        THEN the fourth is refused 429, as it was before this change
        """
        with self._isolated_cache(REGISTRATION_SPLIT_RATE_LIMIT=False):
            for i in range(3):
                r = self.client.post("/accounts/register/", self._invalid_data(
                    username="k%d" % i, email="k%d@example.com" % i,
                ))
                self.assertEqual(r.status_code, 200)

            blocked = self.client.post("/accounts/register/", self._invalid_data(
                username="k9", email="k9@example.com",
            ))
            self.assertEqual(blocked.status_code, 429)

    def test_rate_limited_response_is_a_rendered_page(self):
        """
        GIVEN an IP that has exhausted its registration budget
        WHEN it posts again
        THEN the 429 is HTML with Retry-After, links to sign-in and password
             reset, and discloses no threshold values
        """
        with self._isolated_cache(REGISTRATION_RATE_LIMIT_HOUR=1):
            self.client.post("/accounts/register/", self._valid_data(
                username="p1", email="p1@example.com",
            ))
            blocked = self.client.post("/accounts/register/", self._valid_data(
                username="p2", email="p2@example.com",
            ))

            self.assertEqual(blocked.status_code, 429)
            self.assertIn("Retry-After", blocked)
            self.assertIn("text/html", blocked["Content-Type"])
            body = blocked.content.decode()
            self.assertIn(reverse("login"), body)
            self.assertIn(reverse("password_reset"), body)
            # Thresholds must not leak — knowing them makes the defense
            # trivial to pace against.
            self.assertNotIn("REGISTRATION_RATE_LIMIT", body)

    def test_redis_outage_still_fails_open(self):
        """
        GIVEN the cache backend raises on every access
        WHEN a valid registration is posted
        THEN the limiter does not block it and the User is created
        """
        from django.contrib.auth.models import User as _U

        with self._isolated_cache():
            with mock.patch(
                "survey.abuse.get_usage", side_effect=Exception("redis down"),
            ), mock.patch(
                "survey.abuse.is_ratelimited", side_effect=Exception("redis down"),
            ):
                r = self.client.post("/accounts/register/", self._valid_data(
                    username="openuser", email="open@example.com",
                ))
            self.assertEqual(r.status_code, 302)
            self.assertTrue(_U.objects.filter(username="openuser").exists())


class RegistrationAcceptTermsTest(TestCase):
    """Sign-up requires the 16+ / Terms confirmation; the honeypot still wins."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def _data(self, **overrides):
        data = {
            'username': 'termsuser', 'email': 'terms@example.com',
            'password1': 'Xx12345!secure', 'password2': 'Xx12345!secure',
            'website': '', 'cf-turnstile-response': 'any-token', 'accept_terms': 'on',
        }
        data.update(overrides)
        return {k: v for k, v in data.items() if v is not None}

    def test_registration_page_shows_checkbox_and_terms_link(self):
        """
        GIVEN an anonymous visitor
        WHEN they open the registration page
        THEN it renders the accept_terms checkbox and a link to /terms/
        """
        response = Client().get('/accounts/register/')
        self.assertContains(response, 'name="accept_terms"')
        self.assertContains(response, 'href="/terms/"')

    def test_checkbox_sits_inside_its_label_in_the_styled_row(self):
        """
        GIVEN the terms checkbox must sit beside its sentence, not centred above it (#300)
        WHEN the registration page is rendered
        THEN the checkbox is inside its label within the form-check-terms row, and the page carries
             the rule that keeps a checkbox there at its natural size
        """
        html = Client().get('/accounts/register/').content.decode()
        row = html[html.index('class="form-group form-check-terms"'):]
        row = row[:row.index('</label>')]
        self.assertIn('<label', row)
        self.assertIn('type="checkbox" name="accept_terms"', row)
        # Text and link in one span: as separate flex items the link would become its own column.
        self.assertRegex(row, r'<span>I am 16 or older and accept the <a href="/terms/"[^>]*>Terms of use</a></span>')
        self.assertIn('.auth-card .form-check-terms input[type="checkbox"]', html)

    def test_missing_confirmation_is_rejected(self):
        """
        GIVEN valid registration data without accept_terms
        WHEN it is submitted
        THEN the form re-renders with an accept_terms error and no user is created
        """
        with override_settings(TURNSTILE_SECRET_KEY=''):
            response = self.client.post('/accounts/register/', self._data(accept_terms=None),
                                        REMOTE_ADDR='10.%d.%d.%d' % tuple(uuid.uuid4().bytes[:3]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('accept_terms', response.context['form'].errors)
        self.assertFalse(User.objects.filter(username='termsuser').exists())

    def test_confirmed_registration_creates_user(self):
        """
        GIVEN valid registration data with accept_terms checked
        WHEN it is submitted
        THEN the user is created and the response redirects
        """
        with override_settings(TURNSTILE_SECRET_KEY=''):
            response = self.client.post('/accounts/register/', self._data(),
                                        REMOTE_ADDR='10.%d.%d.%d' % tuple(uuid.uuid4().bytes[:3]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='termsuser').exists())

    def test_honeypot_still_wins_without_confirmation(self):
        """
        GIVEN a submission that fills the honeypot and omits accept_terms
        WHEN it is submitted
        THEN the bot gets the fake-success redirect and no user is created
        """
        with override_settings(TURNSTILE_SECRET_KEY=''):
            response = self.client.post('/accounts/register/', self._data(website='bot', accept_terms=None),
                                        REMOTE_ADDR='10.%d.%d.%d' % tuple(uuid.uuid4().bytes[:3]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(username='termsuser').exists())
