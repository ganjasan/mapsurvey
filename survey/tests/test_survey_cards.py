"""Tests for the `survey-cards` capability (openspec/specs/survey-cards/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from survey.models import SurveyHeader
from survey.tests.helpers import _make_org


class SurveyHeaderVisibilityTest(TestCase):
    """Tests for SurveyHeader visibility and is_archived fields."""

    def setUp(self):
        self.org = _make_org()

    def test_default_visibility_is_private(self):
        """
        GIVEN a new SurveyHeader
        WHEN created without specifying visibility
        THEN visibility should default to 'private'
        """
        survey = SurveyHeader.objects.create(name="test_vis", organization=self.org)
        self.assertEqual(survey.visibility, "private")

    def test_default_is_archived_is_false(self):
        """
        GIVEN a new SurveyHeader
        WHEN created without specifying is_archived
        THEN is_archived should default to False
        """
        survey = SurveyHeader.objects.create(name="test_arch", organization=self.org)
        self.assertFalse(survey.is_archived)

    def test_visibility_choices(self):
        """
        GIVEN a SurveyHeader
        WHEN setting visibility to each valid choice
        THEN each value should be accepted
        """
        for vis in ("private", "demo", "public"):
            survey = SurveyHeader.objects.create(name=f"test_{vis}", visibility=vis, organization=self.org)
            self.assertEqual(survey.visibility, vis)
