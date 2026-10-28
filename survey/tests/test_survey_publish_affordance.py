"""Tests for the `survey-publish-affordance` capability (openspec/specs/survey-publish-affordance/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from survey.models import SurveyHeader, SurveySection, Membership
from survey.tests.helpers import _make_org


class SurveyPrimaryActionTest(TestCase):
    """The Survey context bar surfaces a state-driven primary publish action.

    Mirrors the Public results tab: Preview + one primary action in every state,
    so a survey's own "open for responses" is not buried in the status chip.
    """

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = Client()
        self.org = _make_org("SPA Org")
        self.owner = User.objects.create_user(username="spaowner", password="pw12345")
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="spa_survey", organization=self.org, status="draft", is_canonical=True,
        )
        SurveySection.objects.create(survey_header=self.survey, name="s", code="S1", is_head=True)
        self.url = "/editor/surveys/{}/".format(self.survey.uuid)

    def _get_as_owner(self, status):
        SurveyHeader.objects.filter(pk=self.survey.pk).update(status=status)
        self.client.login(username="spaowner", password="pw12345")
        return self.client.get(self.url)

    def test_draft_shows_publish(self):
        """
        GIVEN a draft survey
        WHEN the owner opens the Survey tab
        THEN a primary Publish action is present
        """
        r = self._get_as_owner("draft")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "doTransition('published')")
        self.assertContains(r, "Publish")

    @override_settings(MOBILE_EDITOR_NAV=False)
    def test_testing_surfaces_open_for_responses(self):
        """
        GIVEN a survey in testing
        WHEN the owner opens the Survey tab
        THEN the primary "Publish — open for responses" action is in the bar, not only the chip
        """
        r = self._get_as_owner("testing")
        self.assertEqual(r.status_code, 200)
        # The chip already carries this label; the change adds it to the context
        # bar too, so it must now appear at least twice (chip + bar).
        self.assertContains(r, "Publish — open for responses", count=2)

    @override_settings(MOBILE_EDITOR_NAV=False)
    def test_published_shows_open_state_and_close(self):
        """
        GIVEN a published (open) survey
        WHEN the owner opens the Survey tab
        THEN an Open state and an inline Close action are shown
        """
        r = self._get_as_owner("published")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "doTransition('closed')")
        self.assertContains(r, "> Close")
        self.assertContains(r, "> Open</span>")

    def test_closed_shows_closed_state_and_reopen(self):
        """
        GIVEN a closed survey
        WHEN the owner opens the Survey tab
        THEN a Closed state and an inline Reopen action are shown
        """
        r = self._get_as_owner("closed")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Reopen")
        self.assertContains(r, "doTransition('published')")

    def test_non_owner_sees_only_preview(self):
        """
        GIVEN a viewer (below owner) and a testing survey
        WHEN they open the Survey tab
        THEN no publish/close/reopen primary action renders
        """
        viewer = User.objects.create_user(username="spaviewer", password="pw12345")
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        SurveyHeader.objects.filter(pk=self.survey.pk).update(status="testing")
        self.client.login(username="spaviewer", password="pw12345")
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        # The lifecycle JS is always on the page; assert the *button* is absent by
        # its visible label, which only the owner-only primary-action include emits.
        self.assertNotContains(r, "Publish — open for responses")
