"""Tests for the `sign-in-grace-period` capability (change login-grace-period, #487).

A new account signs in at once and has 24 hours to confirm its address. After
that a correct password is refused with the real reason and a fresh link;
nothing goes live from an unconfirmed address.
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from survey import email_verification as ev
from survey.models import (
    ContentReview, EmailVerification, Invitation, Membership, Question, SurveyCollaborator, SurveyHeader,
)
from survey.tests.helpers import (
    _InlineThread, _LOCMEM_CACHE, _activation_key, _make_org, _make_survey_with_section,
)

PASSWORD = "Xx12345!secure"


def _account(username="fresh", hours_ago=1, confirmed=False, **kw):
    """An account registered `hours_ago`, confirmed or not."""
    user = User.objects.create_user(username=username, email=f"{username}@example.org", password=PASSWORD, **kw)
    user.date_joined = timezone.now() - timedelta(hours=hours_ago)
    user.save(update_fields=["date_joined"])
    EmailVerification.objects.create(user=user, verified_at=timezone.now() if confirmed else None)
    return user


class _Base(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)  # leave no rate-limit counters for the next test in this worker
        mail.outbox = []
        patcher = mock.patch("threading.Thread", _InlineThread)
        patcher.start()
        self.addCleanup(patcher.stop)


class EmailVerificationRuleTest(TestCase):
    """The one rule in survey/email_verification.py."""

    def test_no_row_counts_as_confirmed(self):
        """
        GIVEN an account made without registration (createsuperuser, admin)
        WHEN its confirmation is asked
        THEN it is confirmed and may sign in
        """
        user = User.objects.create_user(username="admin_made", password="x")
        self.assertTrue(ev.is_verified(user))
        self.assertTrue(ev.can_sign_in(user))

    def test_grace_period_then_refusal(self):
        """
        GIVEN unconfirmed accounts registered 1 and 25 hours ago
        WHEN can_sign_in is asked
        THEN the first may sign in and the second awaits confirmation
        """
        early, late = _account("early", hours_ago=1), _account("late", hours_ago=25)
        self.assertTrue(ev.can_sign_in(early))
        self.assertFalse(ev.awaits_confirmation(early))
        self.assertFalse(ev.can_sign_in(late))
        self.assertTrue(ev.awaits_confirmation(late))

    def test_ban_beats_confirmation(self):
        """
        GIVEN a confirmed account that is banned
        WHEN can_sign_in and awaits_confirmation are asked
        THEN it may not sign in and is not told to confirm anything
        """
        user = _account("banned", confirmed=True, is_active=False)
        self.assertFalse(ev.can_sign_in(user))
        self.assertFalse(ev.awaits_confirmation(user))

    @override_settings(SIGN_IN_GRACE_HOURS=2)
    def test_grace_hours_follow_the_setting(self):
        """
        GIVEN SIGN_IN_GRACE_HOURS = 2
        WHEN an unconfirmed account registered 3 hours ago is asked about
        THEN its grace period is over
        """
        self.assertFalse(ev.can_sign_in(_account("short", hours_ago=3)))

    def test_mask_email(self):
        """
        GIVEN an address
        WHEN it is masked
        THEN only the first character of the local part and the domain remain
        """
        self.assertEqual(ev.mask_email("alice@example.org"), "a•••@example.org")
        self.assertEqual(ev.mask_email("broken"), "•••")

    def test_migration_rule(self):
        """
        GIVEN active, never-activated, banned (signed in) and banned (phishing confirmed) accounts without rows
        WHEN sync_accounts runs twice
        THEN active ones are confirmed, the never-activated one becomes active and unconfirmed,
             banned ones stay banned and are not asked to confirm, and the second run changes nothing
        """
        active = User.objects.create_user(username="active", password="x")
        never = User.objects.create_user(username="never", password="x", is_active=False)
        banned = User.objects.create_user(username="banned", password="x", is_active=False)
        banned.last_login = timezone.now()
        banned.save(update_fields=["last_login"])
        phisher = User.objects.create_user(username="phisher", password="x", is_active=False)
        org = _make_org("Phish")
        survey, _ = _make_survey_with_section(org, "lure", owner=phisher)
        ContentReview.objects.create(survey=survey, status="confirmed")

        first = ev.sync_accounts(User, EmailVerification, ContentReview)
        second = ev.sync_accounts(User, EmailVerification, ContentReview)

        for user in (active, never, banned, phisher):
            user.refresh_from_db()
        self.assertEqual(first, (3, 1))
        self.assertEqual(second, (0, 0))
        self.assertTrue(active.is_active and ev.is_verified(active))
        self.assertTrue(never.is_active)
        self.assertFalse(ev.is_verified(never))
        self.assertFalse(banned.is_active)
        self.assertFalse(phisher.is_active)
        self.assertFalse(ev.awaits_confirmation(phisher))


class RegistrationSignsInTest(_Base):
    def test_registration_signs_in_and_sends_one_link(self):
        """
        GIVEN a visitor on the registration page
        WHEN they submit a valid registration
        THEN the account is active, unconfirmed, signed in, sent to the editor, and one mail went out
        """
        response = self.client.post("/accounts/register/", {
            "username": "newcomer", "email": "newcomer@example.org",
            "password1": PASSWORD, "password2": PASSWORD,
            "website": "", "accept_terms": "on",
        })

        user = User.objects.get(username="newcomer")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/editor/")
        self.assertTrue(user.is_active)
        self.assertFalse(ev.is_verified(user))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertEqual(len(mail.outbox), 1)

    def test_invited_address_joins_only_after_confirmation(self):
        """
        GIVEN a workspace that invited an address by mail
        WHEN someone registers with that address, and later confirms it
        THEN registration alone joins nothing; confirming joins the workspace
        """
        org = _make_org("Inviting")
        inviter = User.objects.create_user(username="inviter", password="x")
        Invitation.objects.create(email="invitee@example.org", organization=org, role="editor", invited_by=inviter)
        self.client.post("/accounts/register/", {
            "username": "invitee", "email": "invitee@example.org",
            "password1": PASSWORD, "password2": PASSWORD,
            "website": "", "accept_terms": "on",
        })
        user = User.objects.get(username="invitee")
        self.assertFalse(Membership.objects.filter(user=user, organization=org).exists())

        self.client.post("/accounts/activate/", {"activation_key": _activation_key("invitee")})

        self.assertTrue(Membership.objects.filter(user=user, organization=org, role="editor").exists())


class SignInTest(_Base):
    def _sign_in(self, username, password=PASSWORD):
        return self.client.post(reverse("login"), {"username": username, "password": password})

    def test_unconfirmed_within_grace_signs_in(self):
        """
        GIVEN an unconfirmed account registered an hour ago
        WHEN it signs in with the correct password
        THEN sign-in succeeds and no mail is sent
        """
        user = _account("early", hours_ago=1)
        response = self._sign_in("early")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertEqual(len(mail.outbox), 0)

    def test_past_grace_names_the_reason_and_sends_a_link(self):
        """
        GIVEN an unconfirmed account registered 25 hours ago
        WHEN it signs in with the correct password (by email, any case)
        THEN no session, the not-confirmed message with the masked address, one fresh link
        """
        _account("late", hours_ago=25)
        response = self._sign_in("LATE@example.org")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(response, "You did not confirm your email address within 24 hours")
        self.assertContains(response, "l•••@example.org")
        self.assertNotContains(response, "Invalid username/email or password")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["late@example.org"])

    def test_wrong_password_past_grace_stays_generic(self):
        """
        GIVEN the same unconfirmed account past its grace period
        WHEN it is submitted with a wrong password
        THEN the generic message shows and nothing is sent
        """
        _account("late", hours_ago=25)
        response = self._sign_in("late", password="wrong")
        self.assertContains(response, "Invalid username/email or password")
        self.assertNotContains(response, "•••")
        self.assertEqual(len(mail.outbox), 0)

    def test_banned_account_stays_generic(self):
        """
        GIVEN a banned account (confirmed or not)
        WHEN it signs in with its correct password
        THEN the generic message shows and nothing is sent
        """
        _account("banned_new", hours_ago=25, is_active=False)
        _account("banned_old", confirmed=True, is_active=False)
        for username in ("banned_new", "banned_old"):
            response = self._sign_in(username)
            self.assertContains(response, "Invalid username/email or password")
        self.assertEqual(len(mail.outbox), 0)

    def test_repeated_attempts_respect_the_daily_cap(self):
        """
        GIVEN a per-address daily cap of 2
        WHEN the correct password is submitted five times past the deadline
        THEN the message shows each time and only two mails go out
        """
        _account("late", hours_ago=25)
        with override_settings(RESEND_ACTIVATION_RATE_LIMIT_DAY=2, CACHES=_LOCMEM_CACHE):
            cache.clear()
            responses = [self._sign_in("late") for _ in range(5)]
        for response in responses:
            self.assertContains(response, "You did not confirm your email address")
        self.assertContains(responses[-1], "We have already sent a confirmation link")
        self.assertEqual(len(mail.outbox), 2)

    def test_link_after_the_deadline_signs_in(self):
        """
        GIVEN an unconfirmed account 30 hours old
        WHEN it confirms through a valid activation link
        THEN the address is confirmed and the session is authenticated
        """
        user = _account("late", hours_ago=30)
        self.client.post("/accounts/activate/", {"activation_key": _activation_key("late")})
        self.assertTrue(ev.is_verified(User.objects.get(pk=user.pk)))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)


class GracePeriodSessionTest(_Base):
    def test_session_ends_at_the_deadline(self):
        """
        GIVEN an unconfirmed creator signed in, now 26 hours after registering
        WHEN they load the editor
        THEN they are signed out, sent to sign-in, and that page says why
        """
        user = _account("sleeper", hours_ago=26)
        self.client.force_login(user)

        response = self.client.get("/editor/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/accounts/login/")
        self.assertNotIn("_auth_user_id", self.client.session)
        page = self.client.get("/accounts/login/")
        self.assertContains(page, "You did not confirm your email address within 24 hours")
        self.assertEqual(len(mail.outbox), 1)

    def test_htmx_call_gets_401_with_redirect(self):
        """
        GIVEN the same expired session
        WHEN an HTMX request arrives
        THEN 401 with HX-Redirect to sign-in
        """
        self.client.force_login(_account("sleeper", hours_ago=26))
        response = self.client.get("/editor/", HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["HX-Redirect"], "/accounts/login/")

    def test_confirmed_session_continues(self):
        """
        GIVEN a creator who confirmed before the deadline
        WHEN they load the editor 26 hours after registering
        THEN the session continues
        """
        self.client.force_login(_account("good", hours_ago=26, confirmed=True))
        self.client.get("/editor/")
        self.assertIn("_auth_user_id", self.client.session)

    def test_respondent_pages_are_untouched(self):
        """
        GIVEN the expired unconfirmed session
        WHEN it opens a respondent URL
        THEN the session is not ended there
        """
        self.client.force_login(_account("sleeper", hours_ago=26))
        self.client.get("/surveys/does-not-exist/")
        self.assertIn("_auth_user_id", self.client.session)


class HeldUntilConfirmedTest(_Base):
    def setUp(self):
        super().setUp()
        self.user = _account("builder", hours_ago=1)
        self.org = _make_org("Builder WS")
        Membership.objects.create(user=self.user, organization=self.org, role="owner")
        self.survey, self.section = _make_survey_with_section(self.org, "draft_one", owner=self.user)
        SurveyCollaborator.objects.create(user=self.user, survey=self.survey, role="owner")
        Question.objects.create(survey_section=self.section, name="Q", input_type="text", order_number=1)
        self.client.force_login(self.user)

    def test_editor_publish_is_refused(self):
        """
        GIVEN an unconfirmed creator in the grace period
        WHEN they publish a draft survey from the editor
        THEN 403 email_unconfirmed and the survey stays a draft
        """
        response = self.client.post(
            reverse("editor_survey_transition", args=[self.survey.uuid]), {"status": "published"})
        self.assertEqual(response.status_code, 403)
        self.assertTrue(response.json()["email_unconfirmed"])
        self.assertEqual(SurveyHeader.objects.get(pk=self.survey.pk).status, "draft")

    def test_editor_publish_works_once_confirmed(self):
        """
        GIVEN the same creator after confirming
        WHEN they publish
        THEN the survey is published
        """
        ev.mark_verified(self.user)
        with mock.patch("survey.services.publishing.screen_survey"):
            self.client.post(reverse("editor_survey_transition", args=[self.survey.uuid]), {"status": "published"})
        self.assertEqual(SurveyHeader.objects.get(pk=self.survey.pk).status, "published")

    def test_invitation_is_refused(self):
        """
        GIVEN an unconfirmed workspace owner
        WHEN they invite a colleague
        THEN no invitation is created and no mail is sent
        """
        self.client.post(reverse("org_send_invitation", args=[self.org.slug]),
                         {"email": "colleague@example.org", "role": "editor"})
        self.assertFalse(Invitation.objects.filter(email="colleague@example.org").exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_building_works_and_the_banner_shows(self):
        """
        GIVEN an unconfirmed creator in the grace period
        WHEN they open the survey in the editor
        THEN the page renders with the confirm-your-email banner
        """
        response = self.client.get(reverse("editor_survey_detail", args=[self.survey.uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirm your email address.")
        self.assertContains(response, "builder@example.org")

    def test_banner_resend_sends_a_link(self):
        """
        GIVEN the banner's "Send the link again"
        WHEN it is pressed
        THEN one mail goes out and the script gets {sent: true}
        """
        response = self.client.post(reverse("resend_own_confirmation"), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.json(), {"sent": True})
        self.assertEqual(len(mail.outbox), 1)

    def test_banner_gone_once_confirmed(self):
        """
        GIVEN a confirmed creator
        WHEN they open the editor
        THEN no banner renders
        """
        ev.mark_verified(self.user)
        response = self.client.get(reverse("editor_survey_detail", args=[self.survey.uuid]))
        self.assertNotContains(response, "Confirm your email address.")


class ApiAndMcpTest(_Base):
    """REST and MCP refuse a publish from an unconfirmed account; tokens end with the grace period."""

    def setUp(self):
        super().setUp()
        from api.tests.helpers import make_pro_org, make_v1_survey, mint
        self.org, self.owner = make_pro_org()
        self.owner.date_joined = timezone.now() - timedelta(hours=1)
        self.owner.save(update_fields=["date_joined"])
        EmailVerification.objects.create(user=self.owner, verified_at=None)
        self.survey, section = make_v1_survey(self.org, self.owner)
        Question.objects.create(survey_section=section, name="Q", input_type="text", order_number=1)
        self.token = mint(self.owner)[0]

    def test_rest_publish_is_403_email_unconfirmed(self):
        """
        GIVEN a token of an unconfirmed account in its grace period
        WHEN it publishes through the REST API
        THEN 403 email_unconfirmed and the survey is unchanged
        """
        from api.tests.helpers import LOCMEM, V1Client
        with LOCMEM:
            api = V1Client(self.client, self.token)
            me = api.call("GET", "/me")
            response = api.post(f"/surveys/{self.survey.uuid}/publish", {})
        self.assertEqual(me.status_code, 200)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "email_unconfirmed")
        self.assertEqual(SurveyHeader.objects.get(pk=self.survey.pk).status, "draft")

    def test_mcp_publish_is_refused(self):
        """
        GIVEN the same token over MCP
        WHEN publish_survey is called with confirm
        THEN an isError result with email_unconfirmed
        """
        from api.tests.helpers import LOCMEM
        from mcp.tests.helpers import MCP_SETTINGS, McpClient, error_of
        with LOCMEM, MCP_SETTINGS:
            client = McpClient(self.client, self.token)
            client.initialize()
            envelope = error_of(client.call("publish_survey", {"survey": str(self.survey.uuid), "confirm": True}))
        self.assertEqual(envelope["error"], "email_unconfirmed")

    def test_token_stops_after_the_grace_period(self):
        """
        GIVEN the account is now 25 hours old and still unconfirmed
        WHEN the token is used
        THEN 401 invalid_token
        """
        from api.tests.helpers import LOCMEM, V1Client
        self.owner.date_joined = timezone.now() - timedelta(hours=25)
        self.owner.save(update_fields=["date_joined"])
        with LOCMEM:
            response = V1Client(self.client, self.token).call("GET", "/me")
        self.assertEqual(response.status_code, 401)
