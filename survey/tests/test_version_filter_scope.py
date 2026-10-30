"""Tests for the `version-filter-scope` capability (openspec/specs/version-filter-scope/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from io import BytesIO
import zipfile
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
from survey.analytics import SurveyAnalyticsService
from survey.tests.helpers import _make_org, _zip_text


class VersionedDownloadTest(TestCase):
    """Tests for download_data with version filter query parameter."""

    def setUp(self):
        self.org = _make_org('DownloadOrg')
        self.user = User.objects.create_user(username='dluser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='dluser', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='dl_survey', organization=self.org, created_by=self.user,
            status='published', version_number=2,
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec', code='S1', is_head=True,
        )
        self.question = Question.objects.create(
            survey_section=self.section, code='Q1', order_number=1,
            name='Q?', input_type='text',
        )
        self.session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(
            survey_session=self.session, question=self.question, text='v2 answer',
        )
        # Create archived version
        self.archived = SurveyHeader.objects.create(
            name='dl_survey', organization=self.org, status='closed',
            is_canonical=False, canonical_survey=self.survey, version_number=1,
        )
        self.arch_section = SurveySection.objects.create(
            survey_header=self.archived, name='sec_old', code='S1_old', is_head=True,
        )
        self.arch_question = Question.objects.create(
            survey_section=self.arch_section, code='Q1_old', order_number=1,
            name='Old Q?', input_type='text',
        )
        self.arch_session = SurveySession.objects.create(survey=self.archived)
        Answer.objects.create(
            survey_session=self.arch_session, question=self.arch_question,
            text='v1 answer',
        )

    def test_download_latest_returns_zip(self):
        """
        GIVEN a canonical survey
        WHEN download_data is called with version=latest
        THEN a ZIP file is returned
        """
        url = f'/surveys/{self.survey.uuid}/download?version=latest'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')

    def test_download_specific_version(self):
        """
        GIVEN a canonical survey with archived version 1
        WHEN download_data is called with version=v1
        THEN a ZIP file containing v1 data is returned
        """
        url = f'/surveys/{self.survey.uuid}/download?version=v1'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        # Verify the zip contains data (CSV with v1 answer)
        zip_buffer = BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            filenames = zf.namelist()
            self.assertTrue(len(filenames) > 0)

    def test_download_all_versions(self):
        """
        GIVEN a canonical survey with an archived version
        WHEN download_data is called with version=all
        THEN a ZIP file with prefixed filenames for both versions is returned
        """
        url = f'/surveys/{self.survey.uuid}/download?version=all'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        zip_buffer = BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            filenames = zf.namelist()
            # Should have files prefixed with version numbers
            has_v2 = any(f.startswith('v2_') for f in filenames)
            has_v1 = any(f.startswith('v1_') for f in filenames)
            self.assertTrue(has_v2 or has_v1)

    def test_download_no_version_param_returns_whole_family(self):
        """
        GIVEN a canonical survey with an archived version
        WHEN download_data is called without a version param
        THEN it defaults to the whole family, matching what analytics reports
        """
        url = f'/surveys/{self.survey.uuid}/download'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        body = _zip_text(response)
        self.assertIn('v2 answer', body)
        self.assertIn('v1 answer', body)


class VersionScopeResolverTest(TestCase):
    """Tests for the shared version filter resolver (backlog #114)."""

    def setUp(self):
        self.org = _make_org('ScopeOrg')
        self.survey = SurveyHeader.objects.create(
            name='scope_survey', organization=self.org,
            status='published', version_number=3,
        )
        self.archived = SurveyHeader.objects.create(
            name='scope_survey', organization=self.org, status='closed',
            is_canonical=False, canonical_survey=self.survey, version_number=2,
        )
        self.solo = SurveyHeader.objects.create(
            name='solo_survey', organization=self.org,
            status='published', version_number=1,
        )

    def test_no_value_resolves_to_the_family(self):
        """
        GIVEN a survey with an archived version
        WHEN the version filter is absent
        THEN the scope is the whole family
        """
        from survey.versioning import resolve_version_scope

        scope = resolve_version_scope(self.survey, None)
        self.assertEqual(scope.value, 'all')
        self.assertEqual(scope.ids, {self.survey.id, self.archived.id})
        self.assertTrue(scope.is_family)

    def test_all_resolves_to_the_family(self):
        """
        GIVEN a survey with an archived version
        WHEN the version filter is 'all'
        THEN the scope is the whole family, canonical first
        """
        from survey.versioning import resolve_version_scope

        scope = resolve_version_scope(self.survey, 'all')
        self.assertEqual([h.id for h in scope.headers], [self.survey.id, self.archived.id])

    def test_latest_resolves_to_the_canonical_version_alone(self):
        """
        GIVEN a survey with an archived version
        WHEN the version filter is 'latest'
        THEN only the canonical version is in scope
        """
        from survey.versioning import resolve_version_scope

        scope = resolve_version_scope(self.survey, 'latest')
        self.assertEqual(scope.value, 'v3')
        self.assertEqual(scope.ids, {self.survey.id})
        self.assertFalse(scope.is_family)

    def test_latest_and_explicit_current_version_agree(self):
        """
        GIVEN a survey whose canonical version is v3
        WHEN 'latest' and 'v3' are resolved
        THEN both give the same scope
        """
        from survey.versioning import resolve_version_scope

        self.assertEqual(
            resolve_version_scope(self.survey, 'latest').ids,
            resolve_version_scope(self.survey, 'v3').ids,
        )

    def test_archived_version_resolves_alone(self):
        """
        GIVEN a survey with archived v2
        WHEN the version filter is 'v2'
        THEN only the archived header is in scope
        """
        from survey.versioning import resolve_version_scope

        self.assertEqual(resolve_version_scope(self.survey, 'v2').ids, {self.archived.id})

    def test_bare_number_is_accepted(self):
        """
        GIVEN a survey with archived v2
        WHEN the version filter is '2' without the v prefix
        THEN it resolves to the same version as 'v2'
        """
        from survey.versioning import resolve_version_scope

        self.assertEqual(resolve_version_scope(self.survey, '2').ids, {self.archived.id})

    def test_unparseable_value_falls_back_to_the_family(self):
        """
        GIVEN a survey with an archived version
        WHEN the version filter is not a version at all
        THEN the scope falls back to the family
        """
        from survey.versioning import resolve_version_scope

        scope = resolve_version_scope(self.survey, 'bogus')
        self.assertEqual(scope.value, 'all')
        self.assertEqual(scope.ids, {self.survey.id, self.archived.id})

    def test_version_outside_the_family_falls_back_to_the_family(self):
        """
        GIVEN a survey whose highest version is 3
        WHEN the version filter names v99
        THEN the scope falls back to the family rather than to an empty set
        """
        from survey.versioning import resolve_version_scope

        self.assertEqual(
            resolve_version_scope(self.survey, 'v99').ids,
            {self.survey.id, self.archived.id},
        )

    def test_single_version_survey_is_never_a_family(self):
        """
        GIVEN a survey with no archived versions
        WHEN any filter value is resolved
        THEN the scope holds that survey alone and is not a family
        """
        from survey.versioning import resolve_version_scope

        for value in (None, 'all', 'latest', 'v1', 'bogus'):
            with self.subTest(value=value):
                scope = resolve_version_scope(self.solo, value)
                self.assertEqual(scope.ids, {self.solo.id})
                self.assertFalse(scope.is_family)

    def test_an_archived_header_resolves_against_its_family(self):
        """
        GIVEN an archived version header rather than the canonical one
        WHEN a filter value is resolved against it
        THEN the family is resolved from the canonical survey all the same
        """
        from survey.versioning import resolve_version_scope

        scope = resolve_version_scope(self.archived, 'all')
        self.assertEqual(scope.ids, {self.survey.id, self.archived.id})


class VersionFilterParityTest(TestCase):
    """Analytics and the export must answer the same question for the same URL.

    Backlog #114: they used to disagree on the default, on 'latest', and on
    unparseable values.
    """

    def setUp(self):
        self.org = _make_org('ParityOrg')
        self.user = User.objects.create_user(username='parityuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='parityuser', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='parity_survey', organization=self.org, created_by=self.user,
            status='published', version_number=2,
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec', code='S1', is_head=True,
        )
        self.question = Question.objects.create(
            survey_section=self.section, code='Q1', order_number=1,
            name='Q?', input_type='text',
        )
        Answer.objects.create(
            survey_session=SurveySession.objects.create(survey=self.survey),
            question=self.question, text='current answer',
        )
        self.archived = SurveyHeader.objects.create(
            name='parity_survey', organization=self.org, status='closed',
            is_canonical=False, canonical_survey=self.survey, version_number=1,
        )
        arch_section = SurveySection.objects.create(
            survey_header=self.archived, name='sec_old', code='S1', is_head=True,
        )
        arch_question = Question.objects.create(
            survey_section=arch_section, code='Q1', order_number=1,
            name='Q?', input_type='text',
        )
        for _ in range(3):
            Answer.objects.create(
                survey_session=SurveySession.objects.create(survey=self.archived),
                question=arch_question, text='archived answer',
            )

    def test_both_surfaces_resolve_every_value_identically(self):
        """
        GIVEN a survey with a current and an archived version
        WHEN each accepted filter value is resolved on both surfaces
        THEN the analytics scope and the exported headers are the same set
        """
        from survey.analytics import resolve_version_scope as analytics_scope
        from survey.views import _get_version_surveys

        for value in (None, '', 'all', 'latest', 'v2', 'v1', '1', 'bogus', 'v99'):
            with self.subTest(value=value):
                export_ids = {s.id for s, _ in _get_version_surveys(self.survey, value)}
                self.assertEqual(analytics_scope(self.survey, value), export_ids)

    def test_analytics_and_export_agree_on_the_default_count(self):
        """
        GIVEN 1 session on the current version and 3 on the archived one
        WHEN neither surface is given a version parameter
        THEN both report all 4 (this is the 111-vs-2 bug)
        """
        service = SurveyAnalyticsService(self.survey, version='all')
        self.assertEqual(service.get_overview()['total_sessions'], 4)

        response = self.client.get(f'/surveys/{self.survey.uuid}/download')
        body = _zip_text(response)
        self.assertIn('current answer', body)
        self.assertIn('archived answer', body)

    def test_latest_narrows_both_surfaces(self):
        """
        GIVEN a survey with an archived version
        WHEN version=latest is requested
        THEN analytics reports only the current version's session
        AND the export contains only the current version's answer
        """
        service = SurveyAnalyticsService(self.survey, version='latest')
        self.assertEqual(service.get_overview()['total_sessions'], 1)

        response = self.client.get(f'/surveys/{self.survey.uuid}/download?version=latest')
        body = _zip_text(response)
        self.assertIn('current answer', body)
        self.assertNotIn('archived answer', body)

    def test_family_export_prefixes_each_version(self):
        """
        GIVEN a survey with two versions
        WHEN the whole family is exported
        THEN each version's files carry its own vN_ prefix
        """
        response = self.client.get(f'/surveys/{self.survey.uuid}/download?version=all')
        with zipfile.ZipFile(BytesIO(response.content), 'r') as zf:
            names = zf.namelist()
        self.assertTrue(any(n.startswith('v2_') for n in names), names)
        self.assertTrue(any(n.startswith('v1_') for n in names), names)

    def test_single_version_export_is_never_prefixed(self):
        """
        GIVEN a survey with no archived versions
        WHEN it is exported with version=all
        THEN the filenames carry no version prefix
        """
        solo = SurveyHeader.objects.create(
            name='solo_parity', organization=self.org, created_by=self.user,
            status='published', version_number=1,
        )
        section = SurveySection.objects.create(
            survey_header=solo, name='sec', code='S1', is_head=True,
        )
        question = Question.objects.create(
            survey_section=section, code='Q1', order_number=1,
            name='Q?', input_type='text',
        )
        Answer.objects.create(
            survey_session=SurveySession.objects.create(survey=solo),
            question=question, text='solo answer',
        )

        response = self.client.get(f'/surveys/{solo.uuid}/download?version=all')
        with zipfile.ZipFile(BytesIO(response.content), 'r') as zf:
            names = zf.namelist()
        self.assertTrue(names)
        self.assertFalse([n for n in names if n.startswith('v1_')], names)

    def test_dashboard_download_button_carries_the_version_scope(self):
        """
        GIVEN the analytics dashboard filtered to one version
        WHEN the page is rendered
        THEN its Export data opener preselects that same version in the export dialog
        """
        url = f'/editor/surveys/{self.survey.uuid}/analytics/?version=v1'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.content.decode(),
            rf'data-survey-uuid="{self.survey.uuid}"[^>]*data-version="v1"',
        )


class VersionListScopeTest(TestCase):
    """A comma-separated `version` value names several versions (issue #496)."""

    def setUp(self):
        self.org = _make_org('ListScopeOrg')
        self.user = User.objects.create_user(username='listscope', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='list_survey', organization=self.org, created_by=self.user,
            status='published', version_number=4,
        )
        self.headers = {4: self.survey}
        for num in (3, 2, 1):
            self.headers[num] = SurveyHeader.objects.create(
                name='list_survey', organization=self.org, status='closed',
                is_canonical=False, canonical_survey=self.survey, version_number=num,
            )
        self.draft = SurveyHeader.objects.create(
            name='list_survey', organization=self.org, status='draft',
            is_canonical=False, published_version=self.survey, version_number=5,
        )
        for num, header in self.headers.items():
            section = SurveySection.objects.create(
                survey_header=header, name='sec', code='S1', is_head=True,
            )
            question = Question.objects.create(
                survey_section=section, code='Q1', order_number=1, name='Q?', input_type='text',
            )
            session = SurveySession.objects.create(survey=header)
            Answer.objects.create(survey_session=session, question=question, text=f'answer of v{num}')

    def _scope(self, value):
        from survey.versioning import resolve_version_scope
        return resolve_version_scope(self.survey, value)

    def test_list_resolves_to_named_versions_in_family_order(self):
        """
        GIVEN a survey with versions v1–v4 (v4 canonical)
        WHEN `v2,v4` is resolved
        THEN the scope is v4 then v2 — canonical first, whatever the list order
        """
        scope = self._scope('v2,v4')
        self.assertEqual([h.version_number for h in scope.headers], [4, 2])
        self.assertEqual(scope.value, 'v4,v2')
        self.assertTrue(scope.is_family)

    def test_order_duplicates_and_spelling_do_not_matter(self):
        """
        GIVEN the same survey
        WHEN `v2,v3,3`, `3,v2` and ` V3 , latest ,v2` are resolved
        THEN the first two name the same versions and `latest` adds the canonical one
        """
        self.assertEqual(self._scope('v2,v3,3').ids, self._scope('3,v2').ids)
        self.assertEqual(
            self._scope(' V3 , latest ,v2').ids,
            {self.headers[4].id, self.headers[3].id, self.headers[2].id},
        )

    def test_unknown_entries_are_dropped(self):
        """
        GIVEN the same survey
        WHEN `v2,v99,bogus` is resolved
        THEN the scope is v2 alone, a single version, not a family
        """
        scope = self._scope('v2,v99,bogus')
        self.assertEqual(scope.ids, {self.headers[2].id})
        self.assertEqual(scope.value, 'v2')
        self.assertFalse(scope.is_family)

    def test_nothing_resolvable_falls_back_to_the_family(self):
        """
        GIVEN the same survey
        WHEN `v98,v99` or a bare comma is resolved
        THEN the scope is the whole family, as for one unrecognised value
        """
        family = {h.id for h in self.headers.values()}
        for value in ('v98,v99', ','):
            with self.subTest(value=value):
                scope = self._scope(value)
                self.assertEqual(scope.ids, family)
                self.assertEqual(scope.value, 'all')

    def test_all_inside_a_list_widens_to_the_family(self):
        """
        GIVEN the same survey
        WHEN `v2,all` is resolved, or a list naming every version
        THEN the scope is the whole family under the value `all`
        """
        family = {h.id for h in self.headers.values()}
        for value in ('v2,all', 'v1,v2,v3,v4'):
            with self.subTest(value=value):
                scope = self._scope(value)
                self.assertEqual(scope.ids, family)
                self.assertEqual(scope.value, 'all')

    def test_draft_never_joins_a_list(self):
        """
        GIVEN a survey with a draft copy
        WHEN `draft,v2,v3` is resolved
        THEN the scope is v2 and v3, without the draft copy
        """
        scope = self._scope('draft,v2,v3')
        self.assertEqual(scope.ids, {self.headers[3].id, self.headers[2].id})
        self.assertNotIn(self.draft.id, scope.ids)

    def test_single_values_are_unchanged(self):
        """
        GIVEN the same survey
        WHEN `all`, `v2`, `draft` and no value are resolved
        THEN they resolve as before lists existed
        """
        family = {h.id for h in self.headers.values()}
        self.assertEqual(self._scope(None).ids, family)
        self.assertEqual(self._scope('all').ids, family)
        self.assertEqual(self._scope('v2').ids, {self.headers[2].id})
        self.assertEqual(self._scope('draft').ids, {self.draft.id})

    def test_analytics_reports_the_list(self):
        """
        GIVEN the same survey with one session per version
        WHEN the Responses analytics service is built for `v2,v3`
        THEN it counts exactly the sessions of v2 and v3
        """
        service = SurveyAnalyticsService(self.survey, version='v2,v3')
        self.assertEqual(service.base_qs.count(), 2)

    def test_download_of_two_versions_holds_only_their_answers_with_prefixes(self):
        """
        GIVEN the same survey with one answer per version
        WHEN the legacy archive is downloaded with `version=v2,v3`
        THEN it holds the v2 and v3 answers only, in `v3_` and `v2_` files
        """
        self.client.login(username='listscope', password='pass')
        response = self.client.get(f'/surveys/{self.survey.uuid}/download?version=v2,v3')
        self.assertEqual(response.status_code, 200)
        names = zipfile.ZipFile(BytesIO(response.content)).namelist()
        self.assertTrue(any(n.startswith('v3_') for n in names), names)
        self.assertTrue(any(n.startswith('v2_') for n in names), names)
        self.assertFalse(any(n.startswith(('v1_', 'v4_')) for n in names), names)
        body = _zip_text(response)
        self.assertIn('answer of v2', body)
        self.assertIn('answer of v3', body)
        self.assertNotIn('answer of v1', body)
        self.assertNotIn('answer of v4', body)
