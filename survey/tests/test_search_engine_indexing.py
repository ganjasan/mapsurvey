"""Tests for the `search-engine-indexing` capability (openspec/specs/search-engine-indexing/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
import re
from survey.models import SurveyHeader, SurveySection, Membership, SurveyCollaborator
from survey.tests.helpers import _make_org


class SitemapExcludesUnpublishedTest(TestCase):
    """The sitemap advertised 61 drafts as crawlable URLs, every one a hard 404.

    `sitemap_xml` filtered on `visibility` alone while the landing page — the
    other consumer of the same decision — filtered on five conditions. These
    tests pin both consumers against `publicly_visible_surveys`.
    """

    def setUp(self):
        self.org = _make_org('SitemapOrg')
        self.owner = User.objects.create_user(username='sm_owner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')

    def _make_survey(self, status='published', visibility='public', **kwargs):
        survey = SurveyHeader.objects.create(
            name=f'sitemap_{status}_{visibility}_{kwargs.get("suffix", "")}',
            organization=self.org, status=status, visibility=visibility,
            created_by=self.owner,
            is_canonical=kwargs.get('is_canonical', True),
        )
        SurveyCollaborator.objects.create(user=self.owner, survey=survey, role='owner')
        return survey

    def test_published_survey_is_advertised(self):
        """
        GIVEN a canonical, public, published survey
        WHEN /sitemap.xml is fetched
        THEN its UUID appears in the sitemap
        """
        survey = self._make_survey(status='published')
        response = self.client.get('/sitemap.xml')
        self.assertContains(response, f'/surveys/{survey.uuid}/')

    def test_draft_survey_is_not_advertised(self):
        """
        GIVEN a public survey still in draft
        WHEN /sitemap.xml is fetched
        THEN its UUID does not appear — it would be a hard 404 for a crawler
        """
        survey = self._make_survey(status='draft')
        response = self.client.get('/sitemap.xml')
        self.assertNotContains(response, str(survey.uuid))

    def test_closed_and_archived_surveys_are_not_advertised(self):
        """
        GIVEN public surveys in closed and archived status
        WHEN /sitemap.xml is fetched
        THEN neither UUID appears — a search result leading to "survey closed"
             is a dead end
        """
        closed = self._make_survey(status='closed')
        archived = self._make_survey(status='archived')
        response = self.client.get('/sitemap.xml')
        self.assertNotContains(response, str(closed.uuid))
        self.assertNotContains(response, str(archived.uuid))

    def test_landing_page_renders_no_survey_list(self):
        """
        GIVEN surveys of every status
        WHEN the landing page is fetched
        THEN none of their UUIDs appear

        `index` computes a `surveys` queryset that `landing.html` never loops
        over. Pinned so that restoring the list is a deliberate act that has to
        face `publicly_visible_surveys` rather than reintroducing a second,
        divergent filter.
        """
        published = self._make_survey(status='published')
        closed = self._make_survey(status='closed')
        response = self.client.get('/')
        self.assertNotContains(response, str(published.uuid))
        self.assertNotContains(response, str(closed.uuid))

    def test_testing_survey_is_not_advertised(self):
        """
        GIVEN a demo-visibility survey in testing status
        WHEN /sitemap.xml is fetched
        THEN its UUID does not appear — testing is a pre-publication state
        """
        survey = self._make_survey(status='testing', visibility='demo')
        response = self.client.get('/sitemap.xml')
        self.assertNotContains(response, str(survey.uuid))

    def test_non_canonical_version_header_is_not_advertised(self):
        """
        GIVEN a published survey whose non-canonical version header is public
        WHEN /sitemap.xml is fetched
        THEN the version header's UUID does not appear — it duplicates the
             canonical survey
        """
        canonical = self._make_survey(status='published')
        version = self._make_survey(status='published', is_canonical=False, suffix='v')
        version.canonical_survey = canonical
        version.save()
        response = self.client.get('/sitemap.xml')
        self.assertNotContains(response, str(version.uuid))
        self.assertContains(response, str(canonical.uuid))

    def test_survey_superseded_by_published_version_is_not_advertised(self):
        """
        GIVEN a canonical survey whose published_version points elsewhere
        WHEN /sitemap.xml is fetched
        THEN its UUID does not appear
        """
        live = self._make_survey(status='published', suffix='live')
        superseded = self._make_survey(status='published', suffix='old')
        superseded.published_version = live
        superseded.save()
        response = self.client.get('/sitemap.xml')
        self.assertNotContains(response, str(superseded.uuid))

    def test_every_advertised_survey_url_is_reachable(self):
        """
        GIVEN surveys in every status and visibility combination
        WHEN each /surveys/<uuid>/ entry in the sitemap is requested anonymously
        THEN none of them responds 404

        This is the test that would have caught the original defect.
        """
        for status in ('draft', 'testing', 'published', 'closed', 'archived'):
            for visibility in ('public', 'demo', 'private'):
                self._make_survey(status=status, visibility=visibility, suffix=visibility)

        sitemap = self.client.get('/sitemap.xml').content.decode()
        entries = re.findall(r'<loc>[^<]*(/surveys/[0-9a-f-]{36}/)</loc>', sitemap)
        self.assertTrue(entries, 'sitemap advertised no survey URLs at all')
        for path in entries:
            self.assertNotEqual(
                self.client.get(path).status_code, 404,
                f'sitemap advertises {path}, which 404s',
            )


class UnpublishedSurveysAreNotIndexableTest(TestCase):
    """Crawlers reach unpublished surveys through links, not only the sitemap.

    Seven of the thirteen crawled UUIDs in the incident were `private` and were
    never in the sitemap at all — creators circulate a draft link before
    publishing and backlink crawlers follow it.
    """

    def setUp(self):
        self.org = _make_org('NoindexOrg')
        self.owner = User.objects.create_user(username='ni_owner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')

    def _make_survey(self, status, visibility='public'):
        survey = SurveyHeader.objects.create(
            name=f'noindex_{status}_{visibility}', organization=self.org,
            status=status, visibility=visibility, created_by=self.owner,
        )
        SurveyCollaborator.objects.create(user=self.owner, survey=survey, role='owner')
        SurveySection.objects.create(survey_header=survey, name='s1', is_head=True, code='s1')
        return survey

    def test_private_draft_reached_by_link_is_not_indexable(self):
        """
        GIVEN a private survey still in draft
        WHEN an anonymous visitor requests its URL
        THEN the response carries X-Robots-Tag: noindex
        """
        survey = self._make_survey('draft', visibility='private')
        response = self.client.get(f'/surveys/{survey.uuid}/')
        self.assertEqual(response['X-Robots-Tag'], 'noindex')

    def test_testing_survey_is_not_indexable(self):
        """
        GIVEN a testing survey with no password
        WHEN an anonymous visitor requests its URL
        THEN the response carries X-Robots-Tag: noindex
        """
        survey = self._make_survey('testing')
        response = self.client.get(f'/surveys/{survey.uuid}/')
        self.assertEqual(response['X-Robots-Tag'], 'noindex')

    def test_closed_survey_is_not_indexable(self):
        """
        GIVEN a closed survey
        WHEN an anonymous visitor requests its URL
        THEN the response carries X-Robots-Tag: noindex
        """
        survey = self._make_survey('closed')
        response = self.client.get(f'/surveys/{survey.uuid}/')
        self.assertEqual(response['X-Robots-Tag'], 'noindex')

    def test_published_survey_is_indexable(self):
        """
        GIVEN a canonical published survey
        WHEN an anonymous visitor requests its URL
        THEN the response carries no noindex header
        """
        survey = self._make_survey('published')
        response = self.client.get(f'/surveys/{survey.uuid}/')
        self.assertNotIn('X-Robots-Tag', response)

    def test_password_gate_for_unpublished_survey_is_not_indexable(self):
        """
        GIVEN a testing survey behind a password
        WHEN an anonymous visitor requests the password gate
        THEN the gate carries X-Robots-Tag: noindex
        """
        survey = self._make_survey('testing')
        survey.set_password('respondent-gate')
        survey.save()
        response = self.client.get(f'/surveys/{survey.uuid}/password/')
        self.assertEqual(response['X-Robots-Tag'], 'noindex')
