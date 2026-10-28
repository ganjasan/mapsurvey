"""Tests for the `cross-version-analytics` capability (openspec/specs/cross-version-analytics/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership, PublicResultsPage
from survey.analytics import SurveyAnalyticsService
from survey.versioning import clone_survey_for_draft, publish_draft
from survey.tests.helpers import _make_org


class VersionFamilyHelpersTest(TestCase):
    """Tests for family_ids / family_sessions / lineage_map (cross-version scope)."""

    def setUp(self):
        from survey.versioning import clone_survey_for_draft, publish_draft
        self.org = _make_org('FamOrg')
        self.survey = SurveyHeader.objects.create(
            name='fam_survey', organization=self.org, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', title='S1', code='S1', is_head=True,
        )
        self.q_keep = Question.objects.create(
            survey_section=self.section, name='Keep me', input_type='choice',
            code='QKEEP', order_number=1,
            choices=[{'code': 1, 'name': 'Yes'}, {'code': 2, 'name': 'No'}],
        )
        self.q_drop = Question.objects.create(
            survey_section=self.section, name='Drop me', input_type='text',
            code='QDROP', order_number=2,
        )
        self.q_retype = Question.objects.create(
            survey_section=self.section, name='Retype me', input_type='text',
            code='QTYPE', order_number=3,
        )
        # two v1 sessions with answers (one soft-deleted)
        self.sess1 = SurveySession.objects.create(survey=self.survey)
        self.sess2 = SurveySession.objects.create(survey=self.survey, is_deleted=True)
        Answer.objects.create(survey_session=self.sess1, question=self.q_keep,
                              selected_choices=[1])
        Answer.objects.create(survey_session=self.sess1, question=self.q_drop,
                              text='historical')

        # v2: drop QDROP, retype QTYPE (text -> number), keep QKEEP
        draft = clone_survey_for_draft(self.survey)
        Question.objects.filter(survey_section__survey_header=draft, code='QDROP').delete()
        Question.objects.filter(
            survey_section__survey_header=draft, code='QTYPE'
        ).update(input_type='number')
        self.canonical = publish_draft(draft, force=True)
        self.archived = SurveyHeader.objects.get(
            canonical_survey=self.canonical, version_number=1,
        )

    def test_family_ids_spans_versions_excludes_drafts(self):
        """
        GIVEN a canonical survey with an archived v1 and a live draft copy
        WHEN family_ids is called (from either family member)
        THEN it returns canonical + archived, never the draft copy
        """
        from survey.versioning import clone_survey_for_draft, family_ids
        draft2 = clone_survey_for_draft(self.canonical)
        expected = {self.canonical.id, self.archived.id}
        self.assertEqual(family_ids(self.canonical), expected)
        self.assertEqual(family_ids(self.archived), expected)  # resolves canonical first
        self.assertNotIn(draft2.id, family_ids(self.canonical))

    def test_family_sessions_counts_each_session_once(self):
        """
        GIVEN sessions that were moved to the archived version at publish
        WHEN family_sessions is called on the canonical
        THEN old sessions are included exactly once; deleted ones only on request
        """
        from survey.versioning import family_sessions
        new_sess = SurveySession.objects.create(survey=self.canonical)
        ids = list(family_sessions(self.canonical).values_list('id', flat=True))
        self.assertEqual(sorted(ids), sorted([self.sess1.id, new_sess.id]))
        self.assertEqual(family_sessions(self.canonical, include_deleted=True).count(), 3)

    def test_lineage_merges_compatible_question(self):
        """
        GIVEN QKEEP present in v1 (original) and v2 (clone with a new id)
        WHEN lineage_map is built
        THEN both question objects share one lineage keyed (QKEEP, choice)
        """
        from survey.versioning import lineage_map
        lm = lineage_map(self.canonical)
        entry = lm[('QKEEP', 'choice')]
        self.assertEqual(len(entry['question_ids']), 2)
        self.assertIn(self.q_keep.id, entry['question_ids'])
        self.assertIsNotNone(entry['current'])
        self.assertNotEqual(entry['current'].id, self.q_keep.id)  # clone, new id
        self.assertEqual(entry['versions'], 'v1–v2')

    def test_lineage_breaks_on_input_type_change(self):
        """
        GIVEN QTYPE changed from text (v1) to number (v2)
        WHEN lineage_map is built
        THEN two separate lineages exist: archived text and current number
        """
        from survey.versioning import lineage_map
        lm = lineage_map(self.canonical)
        old = lm[('QTYPE', 'text')]
        new = lm[('QTYPE', 'number')]
        self.assertIsNone(old['current'])
        self.assertEqual(old['versions'], 'v1')
        self.assertIsNotNone(new['current'])
        self.assertEqual(new['versions'], 'v2')

    def test_deleted_question_is_archived_lineage_after_current(self):
        """
        GIVEN QDROP deleted in v2 but answered in v1
        WHEN lineage_map is built
        THEN QDROP is an archived-only lineage, ordered after current lineages
        """
        from survey.versioning import lineage_map
        lm = lineage_map(self.canonical)
        entry = lm[('QDROP', 'text')]
        self.assertIsNone(entry['current'])
        self.assertEqual(entry['versions'], 'v1')
        keys = list(lm.keys())
        first_archived = min(i for i, k in enumerate(keys) if lm[k]['current'] is None)
        last_current = max(i for i, k in enumerate(keys) if lm[k]['current'] is not None)
        self.assertGreater(first_archived, last_current)

    def test_public_results_service_uses_family_scope(self):
        """
        GIVEN a published results page on the canonical survey
        WHEN the service collects survey ids
        THEN it matches family_ids (refactored onto the shared helper)
        """
        from survey.public_results import PublicResultsService
        from survey.versioning import family_ids
        from survey.models import PublicResultsPage
        page = PublicResultsPage.objects.create(
            survey=self.canonical, slug='fam-page', is_published=True,
        )
        svc = PublicResultsService(page)
        self.assertEqual(svc._survey_ids, family_ids(self.canonical))
        self.assertEqual(svc.response_count(), 1)  # sess1 only (sess2 deleted)


class CrossVersionAnalyticsTest(TestCase):
    """Analytics, dashboard and public-results aggregation across versions."""

    def setUp(self):
        from survey.versioning import clone_survey_for_draft, publish_draft
        self.org = _make_org('XVerOrg')
        self.user = User.objects.create_user('xver_owner', password='pw')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='xver_survey', organization=self.org, created_by=self.user,
            status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', title='S1', code='S1', is_head=True,
        )
        self.q_keep = Question.objects.create(
            survey_section=self.section, name='Keep', input_type='choice',
            code='QKEEP', order_number=1,
            choices=[{'code': 1, 'name': 'Yes'}, {'code': 2, 'name': 'No'}],
        )
        self.q_dropchoice = Question.objects.create(
            survey_section=self.section, name='Transport', input_type='choice',
            code='QCH', order_number=2,
            choices=[{'code': 1, 'name': 'Car'}, {'code': 2, 'name': 'Bike'},
                     {'code': 3, 'name': 'Bus'}],
        )
        self.q_drop = Question.objects.create(
            survey_section=self.section, name='Legacy note', input_type='text',
            code='QDROP', order_number=3,
        )

        # two completed v1 sessions (single section → any answer completes)
        self.v1_sess1 = SurveySession.objects.create(survey=self.survey)
        self.v1_sess2 = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=self.v1_sess1, question=self.q_keep,
                              selected_choices=[1])
        Answer.objects.create(survey_session=self.v1_sess1, question=self.q_dropchoice,
                              selected_choices=[3])
        Answer.objects.create(survey_session=self.v1_sess1, question=self.q_drop,
                              text='old words')
        Answer.objects.create(survey_session=self.v1_sess2, question=self.q_keep,
                              selected_choices=[2])

        # v2: remove QDROP, remove choice code 3 from QCH
        from survey.versioning import clone_survey_for_draft as _clone, publish_draft as _publish
        draft = _clone(self.survey)
        Question.objects.filter(survey_section__survey_header=draft, code='QDROP').delete()
        Question.objects.filter(survey_section__survey_header=draft, code='QCH').update(
            choices=[{'code': 1, 'name': 'Car'}, {'code': 2, 'name': 'Bike'}],
        )
        self.canonical = _publish(draft, force=True)
        self.archived = SurveyHeader.objects.get(canonical_survey=self.canonical)

        # one completed v2 session on the cloned questions
        self.v2_keep = Question.objects.get(
            survey_section__survey_header=self.canonical, code='QKEEP',
        )
        self.v2_sess = SurveySession.objects.create(survey=self.canonical)
        Answer.objects.create(survey_session=self.v2_sess, question=self.v2_keep,
                              selected_choices=[1])

    def _service(self, **kw):
        from survey.analytics import SurveyAnalyticsService
        return SurveyAnalyticsService(self.canonical, **kw)

    def test_overview_spans_family_and_counts_completion_per_version(self):
        """
        GIVEN 2 completed v1 sessions (moved to the archive at publish) + 1 on v2
        WHEN get_overview runs with the default (all) scope
        THEN totals and completions span both versions
        """
        overview = self._service().get_overview()
        self.assertEqual(overview['total_sessions'], 3)
        self.assertEqual(overview['completed_count'], 3)

    def test_version_filter_isolates_single_version(self):
        """
        GIVEN sessions on v1 and v2
        WHEN the service is scoped to a single version
        THEN only that version's sessions are counted
        """
        self.assertEqual(self._service(version='v1').get_overview()['total_sessions'], 2)
        self.assertEqual(self._service(version='v2').get_overview()['total_sessions'], 1)

    def test_choice_stats_merge_lineage_and_flag_removed_code(self):
        """
        GIVEN QKEEP answered in v1 (codes 1,2) and v2 (code 1), and QCH code 3
              answered in v1 but removed from the v2 choice set
        WHEN question stats are built
        THEN QKEEP counts merge across versions and code 3 appears flagged
        """
        stats = {s['question'].code: s for s in self._service().get_all_question_stats()}
        keep = stats['QKEEP']
        self.assertEqual(keep['total_answers'], 3)
        self.assertEqual(keep['choice_counts'][keep['choice_codes'].index(1)], 2)

        ch = stats['QCH']
        self.assertIn(3, ch['choice_codes'])
        idx = ch['choice_codes'].index(3)
        self.assertIn('no longer offered', ch['choice_labels'][idx])
        self.assertIn('Bus', ch['choice_labels'][idx])
        self.assertEqual(ch['choice_counts'][idx], 1)

    def test_deleted_question_shows_as_archived_stat(self):
        """
        GIVEN QDROP removed in v2 but answered in v1
        WHEN question stats are built
        THEN it appears as an archived lineage with its historical answers
        """
        stats = {s['question'].code: s for s in self._service().get_all_question_stats()}
        drop = stats['QDROP']
        self.assertTrue(drop['archived'])
        self.assertEqual(drop['total_answers'], 1)
        self.assertEqual(drop['versions'], 'v1')

    def test_table_merges_columns_and_labels_archived(self):
        """
        GIVEN the family table
        WHEN a page is built
        THEN v1 and v2 answers share one QKEEP column, QDROP column is
             version-labeled, and rows carry a version chip
        """
        result = self._service().get_table_page()
        cols = {c['key']: c for c in result['columns']}
        self.assertIn('version', cols)
        labels = [c['label'] for c in result['columns']]
        self.assertTrue(any('Legacy note (v1)' == l for l in labels))

        rows = {r['session_id']: r for r in result['rows']}
        rep_key = str(self.v2_keep.id)  # current question is the representative
        self.assertEqual(rows[self.v1_sess1.id]['cells'][rep_key], 'Yes')
        self.assertEqual(rows[self.v2_sess.id]['cells'][rep_key], 'Yes')
        self.assertEqual(rows[self.v1_sess1.id]['version'], 'v1')
        self.assertEqual(rows[self.v2_sess.id]['version'], 'v2')

    def test_dashboard_card_counts_survive_publish(self):
        """
        GIVEN a survey republished as v2
        WHEN the dashboard renders
        THEN the card still counts every family session
        """
        self.client.force_login(self.user)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        response = self.client.get('/editor/')
        card = [s for s in response.context['survey_headers'] if s.id == self.canonical.id][0]
        self.assertEqual(card.session_count, 3)
        self.assertEqual(card.completed_count, 3)

    def test_public_results_answers_resolve_lineage_both_directions(self):
        """
        GIVEN a results page whose block question FK may point at either the
              archived v1 object or the current v2 clone
        WHEN answers are collected
        THEN both resolve to the same lineage-wide set
        """
        from survey.public_results import PublicResultsService
        from survey.models import PublicResultsPage
        page = PublicResultsPage.objects.create(
            survey=self.canonical, slug='xver-page', is_published=True,
            k_anonymity_threshold=1,
        )
        svc = PublicResultsService(page)
        self.assertEqual(svc._answers(self.q_keep).count(), 3)     # archived FK
        self.assertEqual(svc._answers(self.v2_keep).count(), 3)    # current FK
        data = svc._choice_data(self.v2_keep)
        yes = [i for i in data['items'] if i['code'] == 1][0]
        self.assertEqual(yes['value'], 2)

    def test_choice_code_guard_reallocates_reused_code(self):
        """
        GIVEN QCH whose code 3 was answered historically and then removed
        WHEN a new choice arrives claiming code 3
        THEN it is reallocated above every code ever used
        """
        from survey.editor_views import _guard_choice_codes
        current = Question.objects.get(
            survey_section__survey_header=self.canonical, code='QCH',
        )
        new_choices = [
            {'code': 1, 'name': 'Car'}, {'code': 2, 'name': 'Bike'},
            {'code': 3, 'name': 'Train'},   # reuse of the answered code 3
        ]
        guarded = _guard_choice_codes(current, new_choices)
        self.assertEqual(guarded[2]['name'], 'Train')
        self.assertEqual(guarded[2]['code'], 4)  # max(1,2,3)+1
        # existing codes untouched
        self.assertEqual([guarded[0]['code'], guarded[1]['code']], [1, 2])

    def test_delete_survey_trashes_without_touching_family_data(self):
        """
        GIVEN a canonical survey with an archived version holding sessions
        WHEN the owner deletes the survey
        THEN it lands in Trash and every family member's data is still intact
        """
        self.client.force_login(self.user)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.client.post(f'/editor/delete/{self.canonical.uuid}/')
        self.canonical.refresh_from_db()
        self.assertTrue(self.canonical.is_trashed)
        self.assertEqual(
            SurveySession.objects.filter(
                id__in=[self.v1_sess1.id, self.v1_sess2.id, self.v2_sess.id],
            ).count(),
            3,
        )

    def test_purge_removes_whole_family(self):
        """
        GIVEN a trashed canonical survey with an archived version holding sessions
        WHEN the trash purge runs
        THEN sessions and headers of every family member are gone
        """
        from survey.trash import purge_survey
        purge_survey(self.canonical)
        self.assertFalse(SurveyHeader.objects.filter(id__in=[self.canonical.id, self.archived.id]).exists())
        self.assertFalse(SurveySession.objects.filter(
            id__in=[self.v1_sess1.id, self.v1_sess2.id, self.v2_sess.id],
        ).exists())
