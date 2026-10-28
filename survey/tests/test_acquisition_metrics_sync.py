"""Tests for the `acquisition-metrics-sync` capability (openspec/specs/acquisition-metrics-sync/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from survey.models import SurveyHeader, SurveySession
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache as _cache
from survey.demo import demo_survey_uuid, record_demo_open
from survey.models import DemoOpen
from survey.tests.helpers import _make_org


class DemoOpenRecordingTest(TestCase):
    """Recording demo opens without putting identity on the shared session table."""

    def setUp(self):
        _cache.clear()
        self.org = _make_org("DemoOrg")
        self.demo = SurveyHeader.objects.create(
            name="demo_survey", organization=self.org, status="published",
        )
        self.other = SurveyHeader.objects.create(
            name="other_survey", organization=self.org, status="published",
        )
        self.demo_url = f"https://mapsurvey.org/surveys/{self.demo.uuid}"

    def tearDown(self):
        _cache.clear()

    def _request(self, user=None):
        req = RequestFactory().get("/")
        req.user = user or AnonymousUser()
        return req

    def test_anonymous_demo_session_is_recorded_without_a_user(self):
        """
        GIVEN an unauthenticated visitor
        WHEN they start a session on the demo survey
        THEN a demo-open entry is recorded with no user attached
        """
        session = SurveySession.objects.create(survey=self.demo)

        with self.settings(DEMO_SURVEY_URL=self.demo_url):
            record_demo_open(session, self._request())

        entry = DemoOpen.objects.get()
        self.assertEqual(entry.session_id, session.id)
        self.assertIsNone(entry.user_id)

    def test_signed_in_demo_session_records_the_user(self):
        """
        GIVEN an authenticated user
        WHEN they start a session on the demo survey
        THEN the demo-open entry references that user
        """
        user = User.objects.create_user(username="demo_visitor", password="x")
        session = SurveySession.objects.create(survey=self.demo)

        with self.settings(DEMO_SURVEY_URL=self.demo_url):
            record_demo_open(session, self._request(user))

        self.assertEqual(DemoOpen.objects.get().user_id, user.id)

    def test_other_surveys_are_not_recorded(self):
        """
        GIVEN a session on a survey that is not the demo
        WHEN recording runs
        THEN no demo-open entry exists and the session carries no identity
        """
        session = SurveySession.objects.create(survey=self.other)

        with self.settings(DEMO_SURVEY_URL=self.demo_url):
            record_demo_open(session, self._request())

        self.assertEqual(DemoOpen.objects.count(), 0)
        self.assertFalse(hasattr(session, "user_id"))

    def test_unresolvable_demo_url_records_nothing_and_does_not_raise(self):
        """
        GIVEN a demo URL that is unset, malformed, or points at a missing survey
        WHEN a session is started
        THEN recording is a no-op and no error reaches the respondent
        """
        session = SurveySession.objects.create(survey=self.demo)

        for url in ("", "https://mapsurvey.org/surveys/not-a-uuid",
                    "https://mapsurvey.org/surveys/49f57261-3709-478e-8a8a-7b61cebeac92"):
            _cache.clear()
            with self.settings(DEMO_SURVEY_URL=url):
                self.assertIsNone(record_demo_open(session, self._request()))

        self.assertEqual(DemoOpen.objects.count(), 0)

    def test_uuid_extraction(self):
        """
        GIVEN demo URLs in the shapes the setting takes
        WHEN the UUID is extracted
        THEN a well-formed URL yields the UUID and anything else yields None
        """
        with self.settings(DEMO_SURVEY_URL="http://localhost:8000/surveys/"
                                           "49f57261-3709-478e-8a8a-7b61cebeac92"):
            self.assertEqual(str(demo_survey_uuid()),
                             "49f57261-3709-478e-8a8a-7b61cebeac92")
        with self.settings(DEMO_SURVEY_URL="http://localhost:8000/surveys/nope"):
            self.assertIsNone(demo_survey_uuid())
        with self.settings(DEMO_SURVEY_URL=""):
            self.assertIsNone(demo_survey_uuid())
