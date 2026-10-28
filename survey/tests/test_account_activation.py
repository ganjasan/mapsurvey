"""Tests for the `account-activation` capability (openspec/specs/account-activation/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from unittest import mock
from django.conf import settings
from django.core import mail
from survey.models import AbuseEvent
from survey.tests.helpers import _InlineThread, _LOCMEM_CACHE, _activation_key


class ActivationAutoLoginTest(TestCase):
    """/accounts/activate/ — confirm page on GET, activation + login on POST."""

    def setUp(self):
        from django.core.cache import cache
        User.objects.all().delete()
        cache.clear()
        self.user = User.objects.create_user(
            username="newbie", email="newbie@example.com", password="x"
        )
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

    def _get(self, key):
        return self.client.get("/accounts/activate/", {"activation_key": key})

    def _confirm(self, key):
        return self.client.post("/accounts/activate/", {"activation_key": key})

    def _activate(self, key):
        """Full human flow: open the emailed link, then press the button."""
        self._get(key)
        return self._confirm(key)

    def test_get_shows_confirm_page_without_activating(self):
        """
        GIVEN an inactive account and a valid activation key
        WHEN the activation URL is merely opened (GET)
        THEN a confirmation page with the confirm form renders, the account
             stays inactive, and no session is created
        """
        resp = self._get(_activation_key("newbie"))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Confirm my email")
        self.assertContains(resp, 'name="activation_key"')
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_scanner_get_and_head_do_not_activate(self):
        """
        GIVEN a mail-security scanner that pre-fetches emailed links
        WHEN it issues GET and HEAD requests against a valid activation URL
        THEN the account remains inactive — the human's later click still
             gets the full activation + auto-login
        """
        key = _activation_key("newbie")
        self.client.get("/accounts/activate/", {"activation_key": key})
        self.client.head(f"/accounts/activate/?activation_key={key}")

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_valid_key_activates_and_signs_user_in(self):
        """
        GIVEN an inactive account and a valid, unexpired activation key
        WHEN the user opens the link and submits the confirmation form
        THEN the account becomes active, the session is authenticated as that
             user, and the response redirects to LOGIN_REDIRECT_URL
        """
        resp = self._activate(_activation_key("newbie"))

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], settings.LOGIN_REDIRECT_URL)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_activation_emits_one_live_funnel_event_and_replay_none(self):
        """
        GIVEN an inactive account and a valid activation key
        WHEN the user confirms activation, then the same key is posted again
        THEN exactly one creator_activated_account is emitted for that user
             (the direct POST path bypasses form_valid, which is where the
             library sends user_activated) and the replay emits nothing
        """
        from unittest import mock

        from survey import product_events as pe

        key = _activation_key("newbie")
        with mock.patch("survey.signals.pe.emit") as emit:
            self._activate(key)
            self._confirm(key)          # already activated: must stay silent
        calls = [c for c in emit.call_args_list if c.args[0] == pe.CREATOR_ACTIVATED]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[1], self.user.pk)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_activation_records_last_login(self):
        """
        GIVEN an inactive account with last_login unset
        WHEN it is activated through the activation URL
        THEN last_login is populated, as it would be by any interactive login
        """
        self.assertIsNone(self.user.last_login)

        self._activate(_activation_key("newbie"))

        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login)

    def test_expired_key_shows_failure_page_with_resend_link(self):
        """
        GIVEN an activation key older than ACCOUNT_ACTIVATION_DAYS
        WHEN the activation URL is opened
        THEN the failure page renders directly (no confirm button) and offers
             the resend flow instead of suggesting re-registration
        """
        key = _activation_key("newbie")
        with override_settings(ACCOUNT_ACTIVATION_DAYS=0):
            resp = self._get(key)

        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertContains(resp, "/accounts/activate/resend/")
        self.assertNotContains(resp, "Confirm my email")
        self.assertNotContains(resp, "Try registering again")

    def test_expired_key_post_does_not_activate(self):
        """
        GIVEN an expired activation key submitted straight to the POST handler
        WHEN the confirmation form is posted
        THEN the failure page renders and the account stays inactive
        """
        key = _activation_key("newbie")
        with override_settings(ACCOUNT_ACTIVATION_DAYS=0):
            resp = self._confirm(key)

        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_missing_key_shows_failure_page(self):
        """
        GIVEN no activation_key querystring parameter
        WHEN the activation URL is opened
        THEN the failure page renders rather than raising
        """
        resp = self.client.get("/accounts/activate/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Activation Failed")

    def test_replayed_key_on_active_account_redirects_to_login(self):
        """
        GIVEN a valid key whose account was already activated earlier
        WHEN the activation URL is opened again by an anonymous visitor
        THEN they are redirected to the login page — no failure page, and no
             confirm button that could only dead-end
        """
        key = _activation_key("newbie")
        self._activate(key)
        self.client.logout()

        resp = self._get(key)        # re-opened link

        self.assertEqual(resp.status_code, 302)
        self.assertIn(settings.LOGIN_URL, resp["Location"])

    def test_replayed_confirmation_does_not_sign_anyone_in(self):
        """
        GIVEN a valid key for an already-active account
        WHEN the confirmation form is posted again by an anonymous visitor
        THEN no session is created — the key must not work as a reusable
             login credential for the rest of its validity window
        """
        key = _activation_key("newbie")
        self._activate(key)
        self.client.logout()

        resp = self._confirm(key)

        self.assertEqual(resp.status_code, 302)
        self.assertIn(settings.LOGIN_URL, resp["Location"])
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_replayed_key_while_signed_in_goes_to_editor(self):
        """
        GIVEN an already-active account whose owner is signed in
        WHEN they re-open the activation link (e.g. from history)
        THEN they land on the editor rather than a failure page
        """
        key = _activation_key("newbie")
        self._activate(key)          # activates and signs in

        resp = self._get(key)

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], settings.LOGIN_REDIRECT_URL)

    def test_key_for_unknown_username_shows_failure_page(self):
        """
        GIVEN a correctly signed key naming an account that does not exist
        WHEN the activation URL is opened
        THEN the failure page renders and nobody is signed in
        """
        resp = self._get(_activation_key("ghost"))

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_activation_window_default_is_seven_days(self):
        """
        GIVEN no ACCOUNT_ACTIVATION_DAYS override in the environment
        WHEN settings are loaded
        THEN the activation window is 7 days, not the previous 1
        """
        self.assertEqual(settings.ACCOUNT_ACTIVATION_DAYS, 7)


class ResendActivationTest(TestCase):
    """POST /accounts/activate/resend/ — re-issue an activation email."""

    URL = "/accounts/activate/resend/"

    def setUp(self):
        from django.core.cache import cache
        from survey.models import AbuseEvent
        User.objects.all().delete()
        AbuseEvent.objects.all().delete()
        cache.clear()
        mail.outbox = []
        self.inactive = User.objects.create_user(
            username="dormant", email="dormant@example.com", password="x"
        )
        self.inactive.is_active = False
        self.inactive.save(update_fields=["is_active"])
        User.objects.create_user(
            username="live", email="live@example.com", password="x"
        )

    def _post(self, email, **overrides):
        data = {"email": email, "website": ""}
        data.update(overrides)
        with mock.patch("threading.Thread", _InlineThread):
            return self.client.post(self.URL, data)

    def _assert_neutral(self, resp):
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], "/accounts/activate/resend/done/")

    def test_form_renders(self):
        """
        GIVEN an anonymous visitor
        WHEN they open the resend form
        THEN it renders with an email field
        """
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'name="email"')

    def test_inactive_account_receives_working_activation_link(self):
        """
        GIVEN an account that never activated
        WHEN its email is submitted to the resend form
        THEN one activation email is sent and its key activates the account
        """
        resp = self._post("dormant@example.com")

        self._assert_neutral(resp)
        self.assertEqual(len(mail.outbox), 1)

        key = _activation_key("dormant")
        self.client.post("/accounts/activate/", {"activation_key": key})
        self.inactive.refresh_from_db()
        self.assertTrue(self.inactive.is_active)

    def test_email_match_is_case_insensitive(self):
        """
        GIVEN a registered address stored in lowercase
        WHEN the resend form is submitted with different casing
        THEN the activation email is still sent
        """
        self._post("DORMANT@Example.COM")
        self.assertEqual(len(mail.outbox), 1)

    def test_unknown_email_sends_nothing_but_looks_identical(self):
        """
        GIVEN an email address matching no account
        WHEN it is submitted to the resend form
        THEN no mail is sent and the response is the same neutral redirect
        """
        resp = self._post("nobody@example.com")

        self._assert_neutral(resp)
        self.assertEqual(len(mail.outbox), 0)

    def test_already_active_account_sends_nothing_but_looks_identical(self):
        """
        GIVEN an already-activated account
        WHEN its email is submitted to the resend form
        THEN no activation mail is sent and the response is the same neutral
             redirect, so the flow cannot be used to probe account state
        """
        resp = self._post("live@example.com")

        self._assert_neutral(resp)
        self.assertEqual(len(mail.outbox), 0)

    def test_malformed_email_looks_identical(self):
        """
        GIVEN an unparseable email address
        WHEN it is submitted to the resend form
        THEN the response is the same neutral redirect, not a form-error page
        """
        resp = self._post("not-an-email")

        self._assert_neutral(resp)
        self.assertEqual(len(mail.outbox), 0)

    def test_filled_honeypot_sends_nothing_and_logs_event(self):
        """
        GIVEN a bot that fills the hidden honeypot field
        WHEN it submits a real inactive address
        THEN no mail is sent and one honeypot AbuseEvent is recorded
        """
        from survey.models import AbuseEvent

        resp = self._post("dormant@example.com", website="bot-trap")

        self._assert_neutral(resp)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(
            AbuseEvent.objects.filter(defense="honeypot", detail="resend_filled").count(), 1
        )

    def test_per_ip_rate_limit_stops_mail_and_logs_event(self):
        """
        GIVEN the per-IP hourly resend limit set to 1
        WHEN a second request arrives from the same IP
        THEN no further mail is sent, the response stays neutral, and a
             ratelimit AbuseEvent is recorded
        """
        from survey.models import AbuseEvent

        with override_settings(RESEND_ACTIVATION_RATE_LIMIT_HOUR=1,
                               CACHES=_LOCMEM_CACHE):
            self._post("dormant@example.com")
            self.assertEqual(len(mail.outbox), 1)
            resp = self._post("dormant@example.com")

        self._assert_neutral(resp)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            AbuseEvent.objects.filter(defense="ratelimit", detail="resend_hour").count(), 1
        )

    def test_per_email_rate_limit_caps_one_inbox(self):
        """
        GIVEN the per-email daily limit set to 1
        WHEN a second request targets the same address from a different IP
        THEN no second mail is sent — an attacker rotating IPs still cannot
             bomb one inbox
        """
        from survey.models import AbuseEvent

        with override_settings(RESEND_ACTIVATION_RATE_LIMIT_DAY=1,
                               CACHES=_LOCMEM_CACHE), \
                mock.patch("threading.Thread", _InlineThread):
            self.client.post(
                self.URL, {"email": "dormant@example.com", "website": ""},
                REMOTE_ADDR="10.0.0.1",
            )
            self.assertEqual(len(mail.outbox), 1)
            self.client.post(
                self.URL, {"email": "dormant@example.com", "website": ""},
                REMOTE_ADDR="10.0.0.2",
            )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            AbuseEvent.objects.filter(defense="ratelimit", detail="resend_day").count(), 1
        )

    def test_rate_limit_fails_open_when_cache_is_down(self):
        """
        GIVEN a cache backend that raises on every call
        WHEN the resend form is submitted
        THEN the request is still processed and the mail goes out (fail-open,
             matching the registration endpoint's accepted trade-off)
        """
        with mock.patch(
            "survey.views.is_ratelimited", side_effect=Exception("redis down")
        ):
            resp = self._post("dormant@example.com")

        self._assert_neutral(resp)
        self.assertEqual(len(mail.outbox), 1)
