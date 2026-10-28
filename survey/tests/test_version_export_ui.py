"""Tests for the `version-export-ui` capability (openspec/specs/version-export-ui/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
import json
import re
from survey.models import SurveyHeader, SurveySection, Question, Membership
from survey.tests.helpers import _make_org


class DashboardVersionDownloadUITest(TestCase):
    """The survey card menu opens the export dialog with the version list on the opener
    (spec version-export-ui, modified by responses-export-formats)."""

    def setUp(self):
        self.org = _make_org('DlUIOrg')
        self.user = User.objects.create_user(username='dluiuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='dluiuser', password='pass')

    def test_single_version_opener_has_no_version_list(self):
        """
        GIVEN a survey with version_number=1 and no archived versions
        WHEN the dashboard is loaded
        THEN the card's "Export data" opener carries an empty version list and no direct download link
        """
        survey = SurveyHeader.objects.create(
            name='single_v', organization=self.org, status='published',
            version_number=1,
        )
        response = self.client.get('/editor/')
        content = response.content.decode()
        self.assertIn(f'data-survey-uuid="{survey.uuid}"', content)
        self.assertIn("data-versions='[]'", content)
        self.assertNotIn(f'/surveys/{survey.uuid}/download', content)
        self.assertIn('Export data', content)
        self.assertIn('id="exportModal"', content)

    def test_multi_version_opener_lists_versions(self):
        """
        GIVEN a survey with version_number=3 and two archived versions
        WHEN the dashboard is loaded
        THEN the opener's version list holds "All versions", "Current (v3)", "v2" and "v1", in that order
        """
        canonical = SurveyHeader.objects.create(
            name='multi_v', organization=self.org, status='published',
            version_number=3,
        )
        SurveyHeader.objects.create(
            name='multi_v', organization=self.org, status='closed',
            is_canonical=False, canonical_survey=canonical, version_number=2,
        )
        SurveyHeader.objects.create(
            name='multi_v', organization=self.org, status='closed',
            is_canonical=False, canonical_survey=canonical, version_number=1,
        )
        response = self.client.get('/editor/')
        content = response.content.decode()
        m = re.search(r"data-versions='(\[.*?\])'", content)
        self.assertIsNotNone(m, content[:500])
        versions = json.loads(m.group(1))
        self.assertEqual([v['value'] for v in versions], ['all', 'latest', 'v2', 'v1'])
        self.assertEqual(versions[1]['label'], 'Current (v3)')
        self.assertIn('Backup (survey file)', content)
        self.assertIn('?mode=full', content)

    def test_prefetched_versions_avoid_n_plus_one(self):
        """
        GIVEN multiple surveys with archived versions
        WHEN the dashboard is loaded
        THEN archived versions are prefetched (available as prefetched_archived_versions)
        """
        for i in range(3):
            canonical = SurveyHeader.objects.create(
                name=f'prefetch_test_{i}', organization=self.org,
                status='published', version_number=2,
            )
            SurveyHeader.objects.create(
                name=f'prefetch_test_{i}', organization=self.org,
                status='closed', is_canonical=False,
                canonical_survey=canonical, version_number=1,
            )
        response = self.client.get('/editor/')
        surveys = response.context['survey_headers']
        for s in surveys:
            self.assertTrue(hasattr(s, 'prefetched_archived_versions'))

    def test_card_opener_knows_about_file_questions(self):
        """
        GIVEN one survey with a photo question and one without
        WHEN the dashboard is loaded
        THEN the first card's opener says data-has-files="1" and the second "0"
        """
        with_files = SurveyHeader.objects.create(name='with_files', organization=self.org, status='published')
        sec = SurveySection.objects.create(survey_header=with_files, name='s', code='S1', is_head=True)
        Question.objects.create(survey_section=sec, name='Photo', code='PH', input_type='photo')
        without = SurveyHeader.objects.create(name='without_files', organization=self.org, status='published')
        content = self.client.get('/editor/').content.decode()
        self.assertRegex(content, rf'data-survey-uuid="{with_files.uuid}"[^>]*data-has-files="1"')
        self.assertRegex(content, rf'data-survey-uuid="{without.uuid}"[^>]*data-has-files="0"')
