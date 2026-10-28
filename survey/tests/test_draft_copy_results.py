"""Tests for the `draft-copy-results` capability (openspec/specs/draft-copy-results/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership, SurveyCollaborator, PublicResultsPage
from survey.analytics import SurveyAnalyticsService
from survey.versioning import clone_survey_for_draft
from survey.tests.helpers import _make_org


class DraftCopyResultsScopeTest(TestCase):
    """Results read from a draft copy: the family by default, the draft on request."""

    def setUp(self):
        from survey.versioning import clone_survey_for_draft
        self.org = _make_org('DraftScopeOrg')
        self.user = User.objects.create_user('draft_scope_owner', password='pw')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='draft_scope_survey', organization=self.org, created_by=self.user,
            status='published',
        )
        SurveyCollaborator.objects.create(user=self.user, survey=self.survey, role='owner')
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', title='S1', code='S1', is_head=True,
        )
        self.question = Question.objects.create(
            survey_section=self.section, name='Colour', input_type='choice',
            code='QCOL', order_number=1,
            choices=[{'code': 1, 'name': 'Red'}, {'code': 2, 'name': 'Blue'}],
        )

        # Two real responses on the published survey.
        self.real_sessions = [SurveySession.objects.create(survey=self.survey)
                              for _ in range(2)]
        for s in self.real_sessions:
            Answer.objects.create(survey_session=s, question=self.question,
                                  selected_choices=[1])

        # A draft with one test session from previewing it.
        self.draft = clone_survey_for_draft(self.survey)
        SurveyCollaborator.objects.get_or_create(
            user=self.user, survey=self.draft, defaults={'role': 'owner'},
        )
        self.draft_question = Question.objects.get(
            survey_section__survey_header=self.draft, code='QCOL',
        )
        self.draft_session = SurveySession.objects.create(survey=self.draft)
        Answer.objects.create(survey_session=self.draft_session,
                              question=self.draft_question, selected_choices=[2])

    def _service(self, survey=None, **kw):
        from survey.analytics import SurveyAnalyticsService
        return SurveyAnalyticsService(survey or self.draft, **kw)

    # ─── scope helpers ───────────────────────────────────────────────────────

    def test_canonical_of_a_draft_is_the_published_survey(self):
        """
        GIVEN a draft copy of a published survey
        WHEN the canonical is resolved from the draft
        THEN it is the published survey, not the draft
        """
        from survey.versioning import canonical_of

        self.assertEqual(canonical_of(self.draft).id, self.survey.id)

    def test_family_excludes_the_draft_but_the_action_scope_includes_it(self):
        """
        GIVEN a survey with a draft copy
        WHEN the family and the action scope are built from the draft
        THEN only the action scope contains the draft header
        """
        from survey.versioning import family_ids, family_ids_with_draft

        self.assertNotIn(self.draft.id, family_ids(self.draft))
        self.assertIn(self.survey.id, family_ids(self.draft))
        self.assertIn(self.draft.id, family_ids_with_draft(self.draft))

    # ─── default scope ───────────────────────────────────────────────────────

    def test_draft_results_report_the_published_responses(self):
        """
        GIVEN a draft copy of a survey holding two responses
        WHEN its Results is read with no version filter
        THEN the published survey's responses are reported
        """
        self.assertEqual(self._service().get_overview()['total_sessions'], 2)

    def test_draft_test_sessions_are_not_in_the_default_scope(self):
        """
        GIVEN a draft copy with a test session of its own
        WHEN its Results is read with no version filter
        THEN the test session is not among the reported sessions
        """
        reported = set(self._service().base_qs.values_list('id', flat=True))
        self.assertNotIn(self.draft_session.id, reported)

    def test_canonical_results_ignore_the_draft(self):
        """
        GIVEN a published survey whose draft copy has test sessions
        WHEN the canonical's Results is read with no version filter
        THEN only the published responses are reported
        """
        self.assertEqual(
            self._service(survey=self.survey).get_overview()['total_sessions'], 2,
        )

    # ─── the draft scope ─────────────────────────────────────────────────────

    def test_draft_scope_reports_the_test_sessions_alone(self):
        """
        GIVEN a family with a draft copy holding one test session
        WHEN the version filter is 'draft'
        THEN only that session is reported
        """
        service = self._service(version='draft')
        self.assertEqual(service.scope.value, 'draft')
        self.assertEqual(list(service.base_qs.values_list('id', flat=True)),
                         [self.draft_session.id])

    def test_draft_scope_is_reachable_from_the_canonical(self):
        """
        GIVEN a published survey with a draft copy
        WHEN 'draft' is requested on the canonical's Results
        THEN the draft's test sessions are reported
        """
        service = self._service(survey=self.survey, version='draft')
        self.assertEqual(service.scope.ids, {self.draft.id})

    def test_draft_scope_falls_back_when_no_draft_exists(self):
        """
        GIVEN a survey with no draft copy
        WHEN the version filter is 'draft'
        THEN the whole family is reported
        """
        from survey.versioning import resolve_version_scope

        SurveySession.objects.filter(survey=self.draft).delete()
        self.draft.delete()
        scope = resolve_version_scope(self.survey, 'draft')
        self.assertEqual(scope.value, 'all')
        self.assertEqual(scope.ids, {self.survey.id})

    def test_draft_scope_answers_report_under_the_cloned_question(self):
        """
        GIVEN a draft whose test session answered a question cloned from the canonical
        WHEN question stats are built under the draft scope
        THEN the answer is reported under that question
        """
        stats = {s['question'].code: s
                 for s in self._service(version='draft').get_all_question_stats()}
        self.assertEqual(stats['QCOL']['total_answers'], 1)
        self.assertEqual(stats['QCOL']['choice_counts'][1], 1)  # 'Blue', the draft answer

    def test_a_question_added_only_in_the_draft_is_reported(self):
        """
        GIVEN a question that exists only in the draft, answered by a test session
        WHEN question stats are built under the draft scope
        THEN that question appears with its answer
        """
        draft_section = SurveySection.objects.get(survey_header=self.draft)
        new_q = Question.objects.create(
            survey_section=draft_section, name='New only', input_type='text',
            code='QNEW', order_number=9,
        )
        Answer.objects.create(survey_session=self.draft_session, question=new_q,
                              text='draft words')
        codes = [s['question'].code
                 for s in self._service(version='draft').get_all_question_stats()]
        self.assertIn('QNEW', codes)

    def test_published_scope_is_unaffected_by_draft_questions(self):
        """
        GIVEN a draft copy carrying clones of the published questions
        WHEN question stats are built with no version filter
        THEN only the published answers are counted
        """
        stats = {s['question'].code: s
                 for s in self._service().get_all_question_stats()}
        self.assertEqual(stats['QCOL']['total_answers'], 2)
        self.assertEqual(stats['QCOL']['choice_counts'][0], 2)  # 'Red', the published answers

    # ─── the picker ──────────────────────────────────────────────────────────

    def test_version_choices_offer_the_draft_on_a_single_version_survey(self):
        """
        GIVEN a single-version survey with a draft copy
        WHEN the version picker choices are built
        THEN they render and include the draft option
        """
        from survey.analytics import version_choices

        values = [c['value'] for c in version_choices(self.survey)]
        self.assertEqual(values, ['all', 'v1', 'draft'])

    def test_version_choices_omit_the_draft_when_there_is_none(self):
        """
        GIVEN a single-version survey with no draft copy
        WHEN the version picker choices are built
        THEN there is nothing to choose between
        """
        from survey.analytics import version_choices

        SurveySession.objects.filter(survey=self.draft).delete()
        self.draft.delete()
        self.assertEqual(version_choices(self.survey), [])

    # ─── session actions ─────────────────────────────────────────────────────

    def test_a_draft_session_can_be_opened(self):
        """
        GIVEN a session listed under the draft scope
        WHEN its detail partial is requested
        THEN the session is served
        """
        self.client.login(username='draft_scope_owner', password='pw')
        url = f'/editor/surveys/{self.draft.uuid}/analytics/sessions/{self.draft_session.id}/'
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_a_foreign_session_is_still_rejected(self):
        """
        GIVEN a session belonging to an unrelated survey
        WHEN it is requested on this survey's analytics
        THEN it is not found
        """
        other = SurveyHeader.objects.create(
            name='other_survey', organization=self.org, created_by=self.user,
            status='published',
        )
        foreign = SurveySession.objects.create(survey=other)
        self.client.login(username='draft_scope_owner', password='pw')
        url = f'/editor/surveys/{self.draft.uuid}/analytics/sessions/{foreign.id}/'
        self.assertEqual(self.client.get(url).status_code, 404)

    # ─── neighbours ──────────────────────────────────────────────────────────

    def test_export_from_the_draft_returns_the_published_rows(self):
        """
        GIVEN a draft copy of a survey with responses
        WHEN data is downloaded from the draft's uuid with no version parameter
        THEN the published family's headers are exported
        """
        from survey.views import _get_version_surveys

        exported = [h.id for h, _ in _get_version_surveys(self.draft, None)]
        self.assertEqual(exported, [self.survey.id])

    def test_public_results_ignore_draft_test_sessions(self):
        """
        GIVEN a survey with a public results page and a previewed draft copy
        WHEN the page's clean session set is built
        THEN the draft's test session is not in it
        """
        from survey.models import PublicResultsPage
        from survey.public_results import PublicResultsService

        page = PublicResultsPage.objects.create(survey=self.survey, slug='draft-scope-page')
        service = PublicResultsService(page)
        self.assertNotIn(self.draft_session.id, service._clean_ids)
        self.assertEqual(len(service._clean_ids), 2)
