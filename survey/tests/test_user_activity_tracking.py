"""Tests for the `user-activity-tracking` capability (openspec/specs/user-activity-tracking/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from unittest.mock import patch
from datetime import timedelta as _timedelta


class LastActivityMiddlewareTest(TestCase):
    """Tests for LastActivityMiddleware recording UserActivity."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user(username="mw_user", password="x")

    def test_authenticated_request_records_activity(self):
        """
        GIVEN a logged-in user
        WHEN they make an authenticated request
        THEN a UserActivity row is created with a recent last_activity
        """
        from survey.models import UserActivity
        c = Client()
        c.login(username="mw_user", password="x")
        c.get("/")
        ua = UserActivity.objects.get(user=self.user)
        self.assertAlmostEqual(
            ua.last_activity, timezone.now(), delta=_timedelta(minutes=1),
        )

    def test_anonymous_request_records_nothing(self):
        """
        GIVEN no authenticated user
        WHEN an anonymous request is made
        THEN no UserActivity row is created
        """
        from survey.models import UserActivity
        Client().get("/")
        self.assertEqual(UserActivity.objects.count(), 0)

    def test_throttle_skips_write_within_window(self):
        """
        GIVEN a user who already recorded activity within the throttle window
        WHEN they make another request before the window elapses
        THEN last_activity is not rewritten; clearing the gate lets the next
             request write again
        """
        from django.core.cache import cache
        from survey.models import UserActivity
        c = Client()
        c.login(username="mw_user", password="x")
        c.get("/")
        ua = UserActivity.objects.get(user=self.user)
        old = timezone.now() - _timedelta(days=1)
        UserActivity.objects.filter(pk=ua.pk).update(last_activity=old)

        c.get("/")  # throttled: cache gate still set, no write
        ua.refresh_from_db()
        self.assertEqual(ua.last_activity, old)

        cache.clear()  # gate cleared -> next request writes again
        c.get("/")
        ua.refresh_from_db()
        self.assertGreater(ua.last_activity, old)

    def test_write_failure_does_not_break_request(self):
        """
        GIVEN the activity write raises
        WHEN an authenticated request is handled
        THEN the request is still served (the error is swallowed)
        """
        from unittest.mock import patch
        c = Client()
        c.login(username="mw_user", password="x")
        with patch(
            "survey.middleware.UserActivity.objects.update_or_create",
            side_effect=Exception("boom"),
        ):
            resp = c.get("/")
        self.assertLess(resp.status_code, 500)
