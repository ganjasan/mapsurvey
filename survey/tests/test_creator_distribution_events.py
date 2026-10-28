"""Tests for the `creator-distribution-events` capability (openspec/specs/creator-distribution-events/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.urls import reverse
from survey.models import SurveyHeader, SurveySection, Membership, SurveyCollaborator
from unittest.mock import patch as _ai_patch
from survey import product_events as _pe
from survey.tests.helpers import _make_org


class DistributionEventsTest(TestCase):
    """responses_viewed / data_exported server-side, share captures client-side."""

    def setUp(self):
        self.org = _make_org('DistOrg')
        self.owner = User.objects.create_user('dist_owner', password='x')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='dist_survey', organization=self.org, redirect_url='#',
            status='published', created_by=self.owner,
        )
        SurveyCollaborator.objects.create(user=self.owner, survey=self.survey, role='owner')
        SurveySection.objects.create(
            survey_header=self.survey, name='section1',
            start_map_postion=Point(0, 0), start_map_zoom=10,
        )
        self.client.force_login(self.owner)

    def test_responses_page_emits_responses_viewed(self):
        """
        GIVEN a signed-in owner
        WHEN they open the responses page
        THEN one responses_viewed event with the survey id is emitted
        """
        with _ai_patch('survey.analytics_views.pe.emit') as emit:
            response = self.client.get(reverse('editor_survey_analytics', args=[self.survey.uuid]))
        self.assertEqual(response.status_code, 200)
        calls = [c for c in emit.call_args_list if c.args[0] == _pe.RESPONSES_VIEWED]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[2], {'survey_id': str(self.survey.id)})

    def test_download_emits_data_exported(self):
        """
        GIVEN a signed-in owner
        WHEN they download the responses ZIP
        THEN one data_exported event with format zip is emitted and the ZIP is served
        """
        with _ai_patch('survey.views.pe.emit') as emit:
            response = self.client.get(reverse('download_data', args=[str(self.survey.uuid)]))
        self.assertEqual(response.status_code, 200)
        calls = [c for c in emit.call_args_list if c.args[0] == _pe.DATA_EXPORTED]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[2]['format'], 'zip')

    def test_share_page_captures_are_guarded_and_urlless(self):
        """
        GIVEN the share page
        WHEN it renders
        THEN the copy and QR handlers capture guarded PostHog events whose payload
             names the survey id and surface, never the URL
        """
        response = self.client.get(reverse('editor_survey_share', args=[self.survey.uuid]))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("window.posthog && posthog.capture", html)
        self.assertIn("trackShare('share_link_copied')", html)
        self.assertIn("trackShare('qr_shown')", html)
        self.assertIn("survey_id: SHARE_SURVEY_ID, surface: 'share_page'", html)
