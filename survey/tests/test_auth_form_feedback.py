"""Tests for the `auth-form-feedback` capability (openspec/specs/auth-form-feedback/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, override_settings
from django.urls import reverse


class PasswordChecklistTest(TestCase):
    """The checklist must describe the validators the server actually runs."""

    def setUp(self):
        # Two tests here register from 127.0.0.1: start with empty registration
        # rate-limit counters, whatever ran earlier in this worker's Redis db.
        from django.core.cache import cache
        cache.clear()

    def test_every_configured_validator_has_a_checklist_rule(self):
        """
        GIVEN the project's AUTH_PASSWORD_VALIDATORS
        WHEN the checklist rules are derived
        THEN no configured validator is missing a rule
        """
        from survey.password_rules import unmapped_validators

        missing = unmapped_validators()
        self.assertEqual(
            missing, [],
            "AUTH_PASSWORD_VALIDATORS contains validators with no checklist "
            "entry (%s). Add them to VALIDATOR_RULES in survey/password_rules.py "
            "— otherwise the registration page advertises rules that do not "
            "match what the server enforces." % ", ".join(missing),
        )

    def test_registration_page_renders_the_checklist(self):
        """
        GIVEN the registration page
        WHEN it is fetched
        THEN it contains one checklist item per configured rule
        """
        from survey.password_rules import password_checklist_rules

        response = self.client.get("/accounts/register/")
        body = response.content.decode()
        self.assertIn("data-password-checklist", body)
        for rule in password_checklist_rules():
            self.assertIn('data-rule="%s"' % rule["check"], body)

    def test_common_password_is_accepted_with_advice_not_rejected(self):
        """
        GIVEN password composition is advisory, not enforced (2026-08-17)
        WHEN registration is submitted with a well-known common password
        THEN the account is created rather than the form rejecting it
        """
        from django.contrib.auth.models import User as _U
        from django.test import override_settings

        response = self.client.post("/accounts/register/", {
            "username": "commonpw",
            "email": "commonpw@example.com",
            "password1": "password123",
            "password2": "password123",
            "website": "",
            "accept_terms": "on",
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(_U.objects.filter(username="commonpw").exists())

    def test_password_similar_to_email_is_accepted(self):
        """
        GIVEN UserAttributeSimilarityValidator is no longer configured
        WHEN a password closely resembling the email is submitted
        THEN the account is created — this is the exact rejection that cost a
             real signup on 2026-08-17
        """
        from django.contrib.auth.models import User as _U
        from django.test import override_settings

        response = self.client.post("/accounts/register/", {
            "username": "marcuswildner",
            "email": "marcuswildner@example.com",
            "password1": "marcuswildner",
            "password2": "marcuswildner",
            "website": "",
            "accept_terms": "on",
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(_U.objects.filter(username="marcuswildner").exists())

    def test_short_password_is_still_rejected(self):
        """
        GIVEN MinimumLengthValidator remains the one enforced rule
        WHEN a seven-character password is submitted
        THEN the form rejects it and no User is created
        """
        from django.contrib.auth.models import User as _U
        from django.test import override_settings

        response = self.client.post("/accounts/register/", {
            "username": "shortpw",
            "email": "shortpw@example.com",
            "password1": "Xx12345",
            "password2": "Xx12345",
            "website": "",
            "accept_terms": "on",
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(_U.objects.filter(username="shortpw").exists())

    def test_advisory_rules_are_marked_as_advisory(self):
        """
        GIVEN rules that the server does not enforce
        WHEN the registration page renders them
        THEN they carry data-advisory so they are not styled as errors
        """
        from survey.password_rules import password_checklist_rules

        response = self.client.get("/accounts/register/")
        body = response.content.decode()
        advisory = [r for r in password_checklist_rules() if r["advisory"]]

        self.assertTrue(advisory, "expected at least one advisory rule")
        for rule in advisory:
            self.assertIn('data-rule="%s"' % rule["check"], body)
        self.assertIn("data-advisory", body)

    def test_username_help_text_drops_the_150_character_ceiling(self):
        """
        GIVEN the registration page
        WHEN it is fetched
        THEN the username help text states allowed characters, not a ceiling
             nobody reaches
        """
        response = self.client.get("/accounts/register/")
        body = response.content.decode()
        self.assertNotIn("150 characters or fewer", body)


class SignInFormRetentionTest(TestCase):
    """A wrong password must not also wipe the username."""

    def test_failed_sign_in_keeps_username_and_clears_password(self):
        """
        GIVEN an existing user
        WHEN sign-in is submitted with the right username and a wrong password
        THEN the re-rendered page carries the username and no password value
        """
        from django.contrib.auth.models import User as _U

        _U.objects.create_user(username="keeper", password="Xx12345!secure")
        response = self.client.post(reverse("login"), {
            "username": "keeper",
            "password": "wrong-password",
        })
        body = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('value="keeper"', body)
        self.assertNotIn("wrong-password", body)

    def test_failure_message_does_not_enumerate_accounts(self):
        """
        GIVEN one existing user and one identifier with no account
        WHEN each is submitted with a bad password
        THEN both responses carry the same failure message
        """
        from django.contrib.auth.models import User as _U

        _U.objects.create_user(username="exists", password="Xx12345!secure")

        known = self.client.post(reverse("login"), {
            "username": "exists", "password": "wrong-password",
        }).content.decode()
        unknown = self.client.post(reverse("login"), {
            "username": "nobody-here", "password": "wrong-password",
        }).content.decode()

        message = "Invalid username/email or password"
        self.assertIn(message, known)
        self.assertIn(message, unknown)
