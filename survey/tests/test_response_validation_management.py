"""Tests that no capability owns yet: response-validation-management.

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point, Polygon
import json
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
from survey.models import SurveyEvent
from survey.analytics import SurveyAnalyticsService, SessionValidationService
from survey.tests.helpers import _make_org


class SessionValidationStatusTest(TestCase):
    """Tests for session validation status and soft-delete (trash) feature."""

    def setUp(self):
        self.org = _make_org('ValidationOrg')
        self.user = User.objects.create_user('valowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

        self.viewer = User.objects.create_user('valviewer', password='pass')
        Membership.objects.create(user=self.viewer, organization=self.org, role='viewer')

        self.survey = SurveyHeader.objects.create(
            name='validation_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.q_text = Question.objects.create(
            survey_section=self.section, name='Comment', code='q1',
            input_type='text', order_number=1,
        )
        self.q_point = Question.objects.create(
            survey_section=self.section, name='Location', code='q2',
            input_type='point', order_number=2,
        )

    def _create_session(self, **kwargs):
        session = SurveySession.objects.create(survey=self.survey, **kwargs)
        Answer.objects.create(survey_session=session, question=self.q_text, text='hello')
        return session

    def _login_owner(self):
        self.client.login(username='valowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def _login_viewer(self):
        self.client.login(username='valviewer', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    # -- Model defaults --

    def test_session_field_defaults(self):
        """
        GIVEN a newly created SurveySession
        WHEN no validation fields are set
        THEN defaults are validation_status='', is_deleted=False, deleted_at=None
        """
        s = SurveySession.objects.create(survey=self.survey)
        self.assertEqual(s.validation_status, '')
        self.assertFalse(s.is_deleted)
        self.assertIsNone(s.deleted_at)

    # -- QuerySet --

    def test_active_excludes_deleted(self):
        """
        GIVEN one active and one soft-deleted session
        WHEN SurveySession.objects.active() is called
        THEN only the active session is returned
        """
        s_active = self._create_session()
        s_deleted = self._create_session(is_deleted=True)
        active_qs = SurveySession.objects.active().filter(survey=self.survey)
        self.assertIn(s_active, active_qs)
        self.assertNotIn(s_deleted, active_qs)

    def test_deleted_returns_only_deleted(self):
        """
        GIVEN one active and one soft-deleted session
        WHEN SurveySession.objects.deleted() is called
        THEN only the deleted session is returned
        """
        s_active = self._create_session()
        s_deleted = self._create_session(is_deleted=True)
        deleted_qs = SurveySession.objects.deleted().filter(survey=self.survey)
        self.assertNotIn(s_active, deleted_qs)
        self.assertIn(s_deleted, deleted_qs)

    # -- SessionValidationService --

    def test_set_status_valid(self):
        """
        GIVEN a session with no status
        WHEN set_status is called with 'approved'
        THEN session.validation_status becomes 'approved'
        """
        s = self._create_session()
        svc = SessionValidationService()
        svc.set_status(s, 'approved')
        s.refresh_from_db()
        self.assertEqual(s.validation_status, 'approved')

    def test_set_status_invalid_raises(self):
        """
        GIVEN a session
        WHEN set_status is called with an invalid value
        THEN ValueError is raised
        """
        s = self._create_session()
        svc = SessionValidationService()
        with self.assertRaises(ValueError):
            svc.set_status(s, 'invalid_status')

    def test_trash_session(self):
        """
        GIVEN an active session
        WHEN trash() is called
        THEN is_deleted=True and deleted_at is set
        """
        s = self._create_session()
        svc = SessionValidationService()
        svc.trash(s)
        s.refresh_from_db()
        self.assertTrue(s.is_deleted)
        self.assertIsNotNone(s.deleted_at)

    def test_restore_session(self):
        """
        GIVEN a trashed session
        WHEN restore() is called
        THEN is_deleted=False and deleted_at is None
        """
        s = self._create_session(is_deleted=True)
        svc = SessionValidationService()
        svc.restore(s)
        s.refresh_from_db()
        self.assertFalse(s.is_deleted)
        self.assertIsNone(s.deleted_at)

    def test_hard_delete(self):
        """
        GIVEN a trashed session
        WHEN hard_delete() is called
        THEN the session is permanently removed from the database
        """
        s = self._create_session(is_deleted=True)
        sid = s.id
        svc = SessionValidationService()
        svc.hard_delete(s)
        self.assertFalse(SurveySession.objects.filter(id=sid).exists())

    # -- Analytics service with trashed sessions --

    def test_overview_excludes_trashed(self):
        """
        GIVEN 2 active sessions and 1 trashed session
        WHEN get_overview() is called
        THEN total_sessions is 2
        """
        self._create_session()
        self._create_session()
        self._create_session(is_deleted=True)
        svc = SurveyAnalyticsService(self.survey)
        overview = svc.get_overview()
        self.assertEqual(overview['total_sessions'], 2)

    def test_table_excludes_trashed(self):
        """
        GIVEN 2 active sessions and 1 trashed session
        WHEN get_table_page(show_trash=False) is called
        THEN only 2 rows are returned
        """
        self._create_session()
        self._create_session()
        self._create_session(is_deleted=True)
        svc = SurveyAnalyticsService(self.survey)
        result = svc.get_table_page(show_trash=False)
        self.assertEqual(result['total'], 2)

    def test_table_trash_mode(self):
        """
        GIVEN 2 active sessions and 1 trashed session
        WHEN get_table_page(show_trash=True) is called
        THEN only the trashed session is returned
        """
        self._create_session()
        self._create_session()
        self._create_session(is_deleted=True)
        svc = SurveyAnalyticsService(self.survey, include_deleted=True)
        result = svc.get_table_page(show_trash=True)
        self.assertEqual(result['total'], 1)

    def test_geo_excludes_trashed(self):
        """
        GIVEN a geo answer on an active session and one on a trashed session
        WHEN get_geo_feature_collection() is called
        THEN only the active session's feature is returned
        """
        s_active = self._create_session()
        Answer.objects.create(
            survey_session=s_active, question=self.q_point,
            point=Point(13.4, 52.5),
        )
        s_deleted = self._create_session(is_deleted=True)
        Answer.objects.create(
            survey_session=s_deleted, question=self.q_point,
            point=Point(13.5, 52.6),
        )
        svc = SurveyAnalyticsService(self.survey)
        geo = svc.get_geo_feature_collection()
        self.assertEqual(len(geo['features']), 1)

    # -- View endpoints --

    def test_set_status_endpoint(self):
        """
        GIVEN an active session and an editor user
        WHEN POST to set status with 'approved'
        THEN response is 204 and session status is updated
        """
        s = self._create_session()
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{s.id}/status/'
        resp = self.client.post(url, {'validation_status': 'approved'})
        self.assertEqual(resp.status_code, 204)
        s.refresh_from_db()
        self.assertEqual(s.validation_status, 'approved')

    def test_set_status_invalid_returns_400(self):
        """
        GIVEN an active session and an editor user
        WHEN POST with an invalid status value
        THEN response is 400
        """
        s = self._create_session()
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{s.id}/status/'
        resp = self.client.post(url, {'validation_status': 'bogus'})
        self.assertEqual(resp.status_code, 400)

    def test_trash_endpoint(self):
        """
        GIVEN an active session and an editor user
        WHEN POST to trash endpoint
        THEN response is 204 and session is soft-deleted
        """
        s = self._create_session()
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{s.id}/trash/'
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 204)
        s.refresh_from_db()
        self.assertTrue(s.is_deleted)

    def test_restore_endpoint(self):
        """
        GIVEN a trashed session and an editor user
        WHEN POST to restore endpoint
        THEN response is 204 and session is restored
        """
        s = self._create_session(is_deleted=True)
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{s.id}/restore/'
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 204)
        s.refresh_from_db()
        self.assertFalse(s.is_deleted)

    def test_hard_delete_endpoint(self):
        """
        GIVEN a trashed session and an editor user
        WHEN POST to hard delete endpoint
        THEN response is 204 and session is gone from DB
        """
        s = self._create_session(is_deleted=True)
        sid = s.id
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{sid}/delete/'
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(SurveySession.objects.filter(id=sid).exists())

    def test_viewer_cannot_trash(self):
        """
        GIVEN a viewer user
        WHEN POST to trash endpoint
        THEN response is 403
        """
        s = self._create_session()
        self._login_viewer()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{s.id}/trash/'
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)

    def test_table_view_trash_param(self):
        """
        GIVEN 2 active and 1 trashed session
        WHEN GET analytics table with ?trash=1
        THEN response contains only trashed sessions
        """
        active_one = self._create_session()
        active_two = self._create_session()
        trashed = self._create_session(is_deleted=True)
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/table/?trash=1'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        # See the note in test_table_view_issues_param: "1 trashed" lives only
        # in the pre-v2 toolbar, so this asserted chrome rather than filtering.
        body = resp.content.decode()
        self.assertIn(f'data-session-id="{trashed.id}"', body)
        for session in (active_one, active_two):
            self.assertNotIn(f'data-session-id="{session.id}"', body)


class BulkOperationsTest(TestCase):
    """Tests for bulk operations on survey sessions."""

    def setUp(self):
        self.org = _make_org('BulkOrg')
        self.user = User.objects.create_user('bulkowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

        self.viewer = User.objects.create_user('bulkviewer', password='pass')
        Membership.objects.create(user=self.viewer, organization=self.org, role='viewer')

        self.survey = SurveyHeader.objects.create(
            name='bulk_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.q_text = Question.objects.create(
            survey_section=self.section, name='Q', code='q1',
            input_type='text', order_number=1,
        )

    def _create_session(self, **kwargs):
        s = SurveySession.objects.create(survey=self.survey, **kwargs)
        Answer.objects.create(survey_session=s, question=self.q_text, text='data')
        return s

    def _login_owner(self):
        self.client.login(username='bulkowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def _login_viewer(self):
        self.client.login(username='bulkviewer', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def _post_json(self, url, data):
        return self.client.post(url, json.dumps(data), content_type='application/json')

    def test_bulk_set_status(self):
        """
        GIVEN 3 sessions
        WHEN bulk set status to 'approved'
        THEN all 3 sessions have validation_status='approved'
        """
        s1 = self._create_session()
        s2 = self._create_session()
        s3 = self._create_session()
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/bulk/status/'
        resp = self._post_json(url, {'session_ids': [s1.id, s2.id, s3.id], 'status': 'approved'})
        self.assertEqual(resp.status_code, 204)
        for s in [s1, s2, s3]:
            s.refresh_from_db()
            self.assertEqual(s.validation_status, 'approved')

    def test_bulk_trash(self):
        """
        GIVEN 2 active sessions
        WHEN bulk trash is called
        THEN both sessions are soft-deleted
        """
        s1 = self._create_session()
        s2 = self._create_session()
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/bulk/trash/'
        resp = self._post_json(url, {'session_ids': [s1.id, s2.id]})
        self.assertEqual(resp.status_code, 204)
        s1.refresh_from_db()
        s2.refresh_from_db()
        self.assertTrue(s1.is_deleted)
        self.assertTrue(s2.is_deleted)

    def test_bulk_restore(self):
        """
        GIVEN 2 trashed sessions
        WHEN bulk restore is called
        THEN both sessions are restored
        """
        s1 = self._create_session(is_deleted=True)
        s2 = self._create_session(is_deleted=True)
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/bulk/restore/'
        resp = self._post_json(url, {'session_ids': [s1.id, s2.id]})
        self.assertEqual(resp.status_code, 204)
        s1.refresh_from_db()
        s2.refresh_from_db()
        self.assertFalse(s1.is_deleted)
        self.assertFalse(s2.is_deleted)

    def test_bulk_hard_delete(self):
        """
        GIVEN 2 trashed sessions
        WHEN bulk hard delete is called
        THEN both sessions are permanently removed
        """
        s1 = self._create_session(is_deleted=True)
        s2 = self._create_session(is_deleted=True)
        ids = [s1.id, s2.id]
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/bulk/delete/'
        resp = self._post_json(url, {'session_ids': ids})
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(SurveySession.objects.filter(id__in=ids).count(), 0)

    def test_viewer_cannot_bulk_trash(self):
        """
        GIVEN a viewer user
        WHEN bulk trash is called
        THEN response is 403
        """
        s = self._create_session()
        self._login_viewer()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/bulk/trash/'
        resp = self._post_json(url, {'session_ids': [s.id]})
        self.assertEqual(resp.status_code, 403)

    def test_invalid_session_ids_ignored(self):
        """
        GIVEN a mix of valid and invalid session IDs
        WHEN bulk set status is called
        THEN valid sessions are updated, invalid ones are silently ignored
        """
        s = self._create_session()
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/bulk/status/'
        resp = self._post_json(url, {'session_ids': [s.id, 999999], 'status': 'on_hold'})
        self.assertEqual(resp.status_code, 204)
        s.refresh_from_db()
        self.assertEqual(s.validation_status, 'on_hold')


class AutoValidationBasicTest(TestCase):
    """Tests for auto-validation basic rules (empty, incomplete, missing required)."""

    def setUp(self):
        self.org = _make_org('AutoValOrg')
        self.user = User.objects.create_user('avowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

        self.survey = SurveyHeader.objects.create(
            name='autoval_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section1 = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.section2 = SurveySection.objects.create(
            survey_header=self.survey, name='sec2', code='S2',
        )
        self.section1.next_section = self.section2
        self.section1.save()

        self.q1_required = Question.objects.create(
            survey_section=self.section1, name='Name', code='q1',
            input_type='text', order_number=1, required=True,
        )
        self.q2_optional = Question.objects.create(
            survey_section=self.section1, name='Comment', code='q2',
            input_type='text', order_number=2, required=False,
        )
        self.q3_sec2 = Question.objects.create(
            survey_section=self.section2, name='Rating', code='q3',
            input_type='number', order_number=1, required=False,
        )

    def _create_completed_session(self):
        """Session with answers in both sections including required."""
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.q1_required, text='Alice')
        Answer.objects.create(survey_session=s, question=self.q2_optional, text='Nice')
        Answer.objects.create(survey_session=s, question=self.q3_sec2, numeric=5)
        return s

    def _create_empty_session(self):
        """Session with 0 answers."""
        return SurveySession.objects.create(survey=self.survey)

    def _create_incomplete_session(self):
        """Session with answers only in section1 (didn't reach section2)."""
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.q1_required, text='Bob')
        return s

    def _create_missing_required_session(self):
        """Session that visited section1 but skipped the required question."""
        s = SurveySession.objects.create(survey=self.survey)
        # Answered optional but not required
        Answer.objects.create(survey_session=s, question=self.q2_optional, text='Hello')
        Answer.objects.create(survey_session=s, question=self.q3_sec2, numeric=3)
        return s

    def test_empty_session_detected(self):
        """
        GIVEN a session with 0 answers
        WHEN compute_session_issues is called
        THEN 'empty' is in the issues list
        """
        s = self._create_empty_session()
        svc = SurveyAnalyticsService(self.survey)
        issues = svc.compute_session_issues([s.id])
        self.assertIn('empty', issues[s.id])

    def test_incomplete_session_detected(self):
        """
        GIVEN a session with answers only in section1
        WHEN compute_session_issues is called
        THEN 'incomplete' is in the issues list
        """
        s = self._create_incomplete_session()
        svc = SurveyAnalyticsService(self.survey)
        issues = svc.compute_session_issues([s.id])
        self.assertIn('incomplete', issues[s.id])

    def test_missing_required_detected(self):
        """
        GIVEN a session that visited section1 but skipped the required question
        WHEN compute_session_issues is called
        THEN 'missing_required' is in the issues list
        """
        s = self._create_missing_required_session()
        svc = SurveyAnalyticsService(self.survey)
        issues = svc.compute_session_issues([s.id])
        self.assertIn('missing_required', issues[s.id])

    def test_clean_session_no_issues(self):
        """
        GIVEN a completed session with all required answers
        WHEN compute_session_issues is called
        THEN the issues list is empty
        """
        s = self._create_completed_session()
        svc = SurveyAnalyticsService(self.survey)
        issues = svc.compute_session_issues([s.id])
        self.assertEqual(issues[s.id], [])

    def test_table_page_includes_issues(self):
        """
        GIVEN sessions with various issues
        WHEN get_table_page is called
        THEN each row has an 'issues' key
        """
        self._create_completed_session()
        self._create_empty_session()
        svc = SurveyAnalyticsService(self.survey)
        result = svc.get_table_page()
        for row in result['rows']:
            self.assertIn('issues', row)

    def test_table_page_issues_filter(self):
        """
        GIVEN 1 clean and 1 empty session
        WHEN get_table_page is called with issues_filter='empty'
        THEN only the empty session is returned
        """
        self._create_completed_session()
        self._create_empty_session()
        svc = SurveyAnalyticsService(self.survey)
        result = svc.get_table_page(issues_filter=['empty'])
        self.assertEqual(result['total'], 1)
        self.assertIn('empty', result['rows'][0]['issues'])

    def test_overview_includes_flagged_count(self):
        """
        GIVEN 1 clean and 2 flagged sessions
        WHEN get_overview is called
        THEN flagged_count is 2
        """
        self._create_completed_session()
        self._create_empty_session()
        self._create_incomplete_session()
        svc = SurveyAnalyticsService(self.survey)
        overview = svc.get_overview()
        self.assertEqual(overview['flagged_count'], 2)

    def test_table_view_issues_param(self):
        """
        GIVEN 1 clean and 1 empty session
        WHEN GET analytics table with ?issues=empty
        THEN response contains only the empty session
        """
        clean = self._create_completed_session()
        empty = self._create_empty_session()
        self.client.login(username='avowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        # Empty sessions are hidden by default on v2; the filter is exercised
        # with them shown (spec responses-empty-sessions).
        self.client.cookies['rv2_show_empty'] = '1'
        url = f'/editor/surveys/{self.survey.uuid}/analytics/table/?issues=empty'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        # Assert on the rows themselves, not on a toolbar string. The previous
        # assertion looked for "1 result", which only the pre-v2 toolbar
        # renders; RESPONSES_V2 replaced it with count chips and the test broke
        # while the filtering it covers kept working. Row checkboxes carry
        # data-session-id under both toolbars.
        body = resp.content.decode()
        self.assertIn(f'data-session-id="{empty.id}"', body)
        self.assertNotIn(f'data-session-id="{clean.id}"', body)


class AnswerLintingErrorsTest(TestCase):
    """Tests for answer-level linting: self-intersection and empty required."""

    def setUp(self):
        self.org = _make_org('LintOrg')
        self.user = User.objects.create_user('lintowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

        self.survey = SurveyHeader.objects.create(
            name='lint_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.q_polygon = Question.objects.create(
            survey_section=self.section, name='Area', code='q1',
            input_type='polygon', order_number=1,
        )
        self.q_required = Question.objects.create(
            survey_section=self.section, name='Name', code='q2',
            input_type='text', order_number=2, required=True,
        )
        self.q_optional = Question.objects.create(
            survey_section=self.section, name='Comment', code='q3',
            input_type='text', order_number=3, required=False,
        )

    def test_self_intersection_detected(self):
        """
        GIVEN a polygon answer with a self-intersecting geometry (bowtie)
        WHEN compute_answer_lints is called
        THEN 'self_intersection' is in the lint for that answer
        """
        s = SurveySession.objects.create(survey=self.survey)
        # Bowtie polygon: self-intersecting
        bowtie = Polygon(((0, 0), (1, 1), (1, 0), (0, 1), (0, 0)))
        Answer.objects.create(survey_session=s, question=self.q_polygon, polygon=bowtie)
        Answer.objects.create(survey_session=s, question=self.q_required, text='Alice')

        svc = SurveyAnalyticsService(self.survey)
        answers = list(Answer.objects.filter(survey_session=s, parent_answer_id__isnull=True).select_related('question'))
        questions = [self.q_polygon, self.q_required, self.q_optional]
        lints = svc.compute_answer_lints([s.id], answers, questions)
        self.assertIn('self_intersection', lints.get(s.id, {}).get(str(self.q_polygon.id), []))

    def test_valid_polygon_no_lint(self):
        """
        GIVEN a polygon answer with valid geometry
        WHEN compute_answer_lints is called
        THEN no lints for that answer
        """
        s = SurveySession.objects.create(survey=self.survey)
        valid_poly = Polygon(((0, 0), (1, 0), (1, 1), (0, 1), (0, 0)))
        Answer.objects.create(survey_session=s, question=self.q_polygon, polygon=valid_poly)
        Answer.objects.create(survey_session=s, question=self.q_required, text='Bob')

        svc = SurveyAnalyticsService(self.survey)
        answers = list(Answer.objects.filter(survey_session=s, parent_answer_id__isnull=True).select_related('question'))
        questions = [self.q_polygon, self.q_required, self.q_optional]
        lints = svc.compute_answer_lints([s.id], answers, questions)
        self.assertEqual(lints.get(s.id, {}).get(str(self.q_polygon.id), []), [])

    def test_empty_required_detected(self):
        """
        GIVEN a session that answered the optional but not the required question
        WHEN compute_answer_lints is called
        THEN 'empty_required' is in the lint for the required question
        """
        s = SurveySession.objects.create(survey=self.survey)
        # Only answer the optional question — skip required
        Answer.objects.create(survey_session=s, question=self.q_optional, text='Hello')

        svc = SurveyAnalyticsService(self.survey)
        answers = list(Answer.objects.filter(survey_session=s, parent_answer_id__isnull=True).select_related('question'))
        questions = [self.q_polygon, self.q_required, self.q_optional]
        lints = svc.compute_answer_lints([s.id], answers, questions)
        self.assertIn('empty_required', lints.get(s.id, {}).get(str(self.q_required.id), []))

    def test_has_errors_filter(self):
        """
        GIVEN 1 clean session and 1 session with a self-intersecting polygon
        WHEN get_table_page is called with issues_filter='has_errors'
        THEN only the session with errors is returned
        """
        # Clean session
        s1 = SurveySession.objects.create(survey=self.survey)
        valid_poly = Polygon(((0, 0), (1, 0), (1, 1), (0, 1), (0, 0)))
        Answer.objects.create(survey_session=s1, question=self.q_polygon, polygon=valid_poly)
        Answer.objects.create(survey_session=s1, question=self.q_required, text='Good')

        # Session with self-intersection
        s2 = SurveySession.objects.create(survey=self.survey)
        bowtie = Polygon(((0, 0), (1, 1), (1, 0), (0, 1), (0, 0)))
        Answer.objects.create(survey_session=s2, question=self.q_polygon, polygon=bowtie)
        Answer.objects.create(survey_session=s2, question=self.q_required, text='Bad')

        svc = SurveyAnalyticsService(self.survey)
        result = svc.get_table_page(issues_filter=['has_errors'])
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['rows'][0]['session_id'], s2.id)

    def test_table_page_includes_lints(self):
        """
        GIVEN a session with lint errors
        WHEN get_table_page is called
        THEN rows include 'lints' key
        """
        s = SurveySession.objects.create(survey=self.survey)
        bowtie = Polygon(((0, 0), (1, 1), (1, 0), (0, 1), (0, 0)))
        Answer.objects.create(survey_session=s, question=self.q_polygon, polygon=bowtie)
        Answer.objects.create(survey_session=s, question=self.q_required, text='Data')

        svc = SurveyAnalyticsService(self.survey)
        result = svc.get_table_page()
        self.assertIn('lints', result['rows'][0])
        self.assertTrue(result['rows'][0]['lints'])


class SessionTagsNotesTest(TestCase):
    """Tests for session tags and notes."""

    def setUp(self):
        self.org = _make_org('TagsOrg')
        self.user = User.objects.create_user('tagsowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='tags_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.q = Question.objects.create(
            survey_section=self.section, name='Q', code='q1',
            input_type='text', order_number=1,
        )

    def _login(self):
        self.client.login(username='tagsowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def test_field_defaults(self):
        """
        GIVEN a new session
        WHEN created with no tags/notes
        THEN defaults are tags=[] and notes=''
        """
        s = SurveySession.objects.create(survey=self.survey)
        self.assertEqual(s.tags, [])
        self.assertEqual(s.notes, '')

    def test_update_tags_endpoint(self):
        """
        GIVEN a session and an editor user
        WHEN POST to update tags with ['expert', 'verified']
        THEN tags are saved on the session
        """
        s = SurveySession.objects.create(survey=self.survey)
        self._login()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{s.id}/tags/'
        resp = self.client.post(url, json.dumps({'tags': ['expert', 'verified']}), content_type='application/json')
        self.assertEqual(resp.status_code, 204)
        s.refresh_from_db()
        self.assertEqual(s.tags, ['expert', 'verified'])

    def test_update_notes_endpoint(self):
        """
        GIVEN a session
        WHEN POST to update notes
        THEN notes are saved
        """
        s = SurveySession.objects.create(survey=self.survey)
        self._login()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{s.id}/tags/'
        resp = self.client.post(url, json.dumps({'notes': 'Important session'}), content_type='application/json')
        self.assertEqual(resp.status_code, 204)
        s.refresh_from_db()
        self.assertEqual(s.notes, 'Important session')

    def test_tags_in_table(self):
        """
        GIVEN a session with tags
        WHEN get_table_page is called
        THEN rows include tags
        """
        s = SurveySession.objects.create(survey=self.survey, tags=['spam', 'test'])
        Answer.objects.create(survey_session=s, question=self.q, text='hi')
        svc = SurveyAnalyticsService(self.survey)
        result = svc.get_table_page()
        self.assertEqual(result['rows'][0]['tags'], ['spam', 'test'])

    def test_tags_searchable(self):
        """
        GIVEN one session tagged 'expert' and one without
        WHEN col_search for tags column contains 'expert'
        THEN only the tagged session is returned
        """
        s1 = SurveySession.objects.create(survey=self.survey, tags=['expert'])
        Answer.objects.create(survey_session=s1, question=self.q, text='a')
        s2 = SurveySession.objects.create(survey=self.survey, tags=[])
        Answer.objects.create(survey_session=s2, question=self.q, text='b')
        svc = SurveyAnalyticsService(self.survey)
        result = svc.get_table_page(col_search={'tags': 'expert'})
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['rows'][0]['session_id'], s1.id)


class AutoValidationAdvancedTest(TestCase):
    """Tests for advanced auto-validation rules (fast completion, duplicates)."""

    def setUp(self):
        self.org = _make_org('AdvValOrg')
        self.user = User.objects.create_user('advvalowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='advval_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.q = Question.objects.create(
            survey_section=self.section, name='Q', code='q1',
            input_type='text', order_number=1,
        )

    def test_fast_completion_detected(self):
        """
        GIVEN a session completed in 5 seconds
        WHEN compute_session_issues is called
        THEN 'fast' is in the issues list
        """
        from django.utils import timezone as tz
        from datetime import timedelta
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.q, text='hi')
        now = tz.now()
        SurveyEvent.objects.create(session=s, event_type='session_start', created_at=now)
        SurveyEvent.objects.create(session=s, event_type='survey_complete', created_at=now + timedelta(seconds=5))
        svc = SurveyAnalyticsService(self.survey)
        issues = svc.compute_session_issues([s.id])
        self.assertIn('fast', issues[s.id])

    def test_normal_speed_not_flagged(self):
        """
        GIVEN a session completed in 120 seconds
        WHEN compute_session_issues is called
        THEN 'fast' is NOT in the issues list
        """
        from django.utils import timezone as tz
        from datetime import timedelta
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.q, text='hi')
        now = tz.now()
        SurveyEvent.objects.create(session=s, event_type='session_start', created_at=now)
        SurveyEvent.objects.create(session=s, event_type='survey_complete', created_at=now + timedelta(seconds=120))
        svc = SurveyAnalyticsService(self.survey)
        issues = svc.compute_session_issues([s.id])
        self.assertNotIn('fast', issues[s.id])

    def test_duplicate_sessions_detected(self):
        """
        GIVEN two sessions from the same user_agent within 30 minutes
        WHEN compute_session_issues is called
        THEN both have 'duplicate' in issues
        """
        from django.utils import timezone as tz
        from datetime import timedelta
        s1 = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s1, question=self.q, text='a')
        s2 = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s2, question=self.q, text='b')
        now = tz.now()
        ua = 'Mozilla/5.0 TestBrowser'
        SurveyEvent.objects.create(session=s1, event_type='session_start', created_at=now, metadata={'user_agent': ua})
        SurveyEvent.objects.create(session=s2, event_type='session_start', created_at=now + timedelta(minutes=10), metadata={'user_agent': ua})
        svc = SurveyAnalyticsService(self.survey)
        issues = svc.compute_session_issues([s1.id, s2.id])
        self.assertIn('duplicate', issues[s1.id])
        self.assertIn('duplicate', issues[s2.id])

    def test_unique_user_agents_not_duplicate(self):
        """
        GIVEN two sessions from different user_agents
        WHEN compute_session_issues is called
        THEN neither has 'duplicate'
        """
        from django.utils import timezone as tz
        s1 = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s1, question=self.q, text='a')
        s2 = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s2, question=self.q, text='b')
        now = tz.now()
        SurveyEvent.objects.create(session=s1, event_type='session_start', created_at=now, metadata={'user_agent': 'UA-1'})
        SurveyEvent.objects.create(session=s2, event_type='session_start', created_at=now, metadata={'user_agent': 'UA-2'})
        svc = SurveyAnalyticsService(self.survey)
        issues = svc.compute_session_issues([s1.id, s2.id])
        self.assertNotIn('duplicate', issues[s1.id])
        self.assertNotIn('duplicate', issues[s2.id])

    def test_duplicate_detected_for_each_close_pair_in_chain(self):
        """
        GIVEN three sessions A→B→C with the same user_agent
              where (A,B) are within the 1h dup window
              but (B,C) are 5 hours apart
        WHEN compute_session_issues is called
        THEN both A and B are flagged 'duplicate' (each pair checked, not only the last)
             and C is NOT flagged
        """
        from django.utils import timezone as tz
        from datetime import timedelta
        ua = 'Mozilla/5.0 ChainBrowser'
        now = tz.now()
        sessions = []
        for offset_minutes in (0, 10, 5 * 60 + 10):
            s = SurveySession.objects.create(survey=self.survey)
            Answer.objects.create(survey_session=s, question=self.q, text='x')
            SurveyEvent.objects.create(
                session=s, event_type='session_start',
                created_at=now + timedelta(minutes=offset_minutes),
                metadata={'user_agent': ua},
            )
            sessions.append(s)
        s_a, s_b, s_c = sessions

        svc = SurveyAnalyticsService(self.survey)
        issues = svc.compute_session_issues([s_a.id, s_b.id, s_c.id])

        self.assertIn('duplicate', issues[s_a.id])
        self.assertIn('duplicate', issues[s_b.id])
        self.assertNotIn('duplicate', issues[s_c.id])

    def test_duplicate_pair_outside_window_not_flagged(self):
        """
        GIVEN two sessions with the same user_agent 5 hours apart
              (well outside the 1h default dup window)
        WHEN compute_session_issues is called
        THEN neither has 'duplicate'
        """
        from django.utils import timezone as tz
        from datetime import timedelta
        ua = 'Mozilla/5.0 FarApart'
        now = tz.now()
        s1 = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s1, question=self.q, text='a')
        s2 = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s2, question=self.q, text='b')
        SurveyEvent.objects.create(session=s1, event_type='session_start', created_at=now, metadata={'user_agent': ua})
        SurveyEvent.objects.create(session=s2, event_type='session_start', created_at=now + timedelta(hours=5), metadata={'user_agent': ua})

        svc = SurveyAnalyticsService(self.survey)
        issues = svc.compute_session_issues([s1.id, s2.id])

        self.assertNotIn('duplicate', issues[s1.id])
        self.assertNotIn('duplicate', issues[s2.id])


class AnswerLintingWarningsTest(TestCase):
    """Tests for answer-level linting warnings (numeric outlier, short text, area outlier)."""

    def setUp(self):
        self.org = _make_org('WarnOrg')
        self.user = User.objects.create_user('warnowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='warn_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.q_number = Question.objects.create(
            survey_section=self.section, name='Age', code='q1',
            input_type='number', order_number=1,
        )
        self.q_text = Question.objects.create(
            survey_section=self.section, name='Comment', code='q2',
            input_type='text', order_number=2,
        )

    def test_numeric_outlier_detected(self):
        """
        GIVEN 10 sessions with age ~25 and 1 with age 999
        WHEN compute_answer_lints is called
        THEN the outlier has 'numeric_outlier' lint
        """
        sessions = []
        for i in range(10):
            s = SurveySession.objects.create(survey=self.survey)
            Answer.objects.create(survey_session=s, question=self.q_number, numeric=25 + i % 3)
            sessions.append(s)
        # Outlier
        s_out = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s_out, question=self.q_number, numeric=999)
        sessions.append(s_out)

        pks = [s.id for s in sessions]
        svc = SurveyAnalyticsService(self.survey)
        answers = list(Answer.objects.filter(survey_session_id__in=pks, parent_answer_id__isnull=True).select_related('question'))
        questions = [self.q_number, self.q_text]
        lints = svc.compute_answer_lints(pks, answers, questions)
        self.assertIn('numeric_outlier', lints.get(s_out.id, {}).get(str(self.q_number.id), []))

    def test_short_text_detected(self):
        """
        GIVEN a session with a 1-char text answer
        WHEN compute_answer_lints is called
        THEN 'short_text' is in the lint
        """
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.q_text, text='a')
        svc = SurveyAnalyticsService(self.survey)
        answers = list(Answer.objects.filter(survey_session=s, parent_answer_id__isnull=True).select_related('question'))
        lints = svc.compute_answer_lints([s.id], answers, [self.q_number, self.q_text])
        self.assertIn('short_text', lints.get(s.id, {}).get(str(self.q_text.id), []))

    def test_normal_text_no_warning(self):
        """
        GIVEN a session with a normal-length text answer
        WHEN compute_answer_lints is called
        THEN no 'short_text' lint
        """
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.q_text, text='This is a good answer')
        svc = SurveyAnalyticsService(self.survey)
        answers = list(Answer.objects.filter(survey_session=s, parent_answer_id__isnull=True).select_related('question'))
        lints = svc.compute_answer_lints([s.id], answers, [self.q_number, self.q_text])
        self.assertNotIn('short_text', lints.get(s.id, {}).get(str(self.q_text.id), []))


class ValidationSettingsTest(TestCase):
    """Tests for configurable validation settings."""

    def setUp(self):
        self.org = _make_org('SettingsOrg')
        self.user = User.objects.create_user('settingsowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='settings_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.q_number = Question.objects.create(
            survey_section=self.section, name='Score', code='q1',
            input_type='number', order_number=1,
        )

    def _login(self):
        self.client.login(username='settingsowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def test_custom_fast_threshold(self):
        """
        GIVEN survey with fast_threshold_seconds=15
        WHEN a session completes in 20 seconds
        THEN it is NOT flagged as 'fast' (would be flagged with default 30)
        """
        from django.utils import timezone as tz
        from datetime import timedelta
        self.survey.validation_settings = {'fast_threshold_seconds': 15}
        self.survey.save(update_fields=['validation_settings'])
        self.survey.refresh_from_db()
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.q_number, numeric=5)
        now = tz.now()
        SurveyEvent.objects.create(session=s, event_type='session_start', created_at=now)
        SurveyEvent.objects.create(session=s, event_type='survey_complete', created_at=now + timedelta(seconds=20))
        svc = SurveyAnalyticsService(self.survey)
        issues = svc.compute_session_issues([s.id])
        self.assertNotIn('fast', issues[s.id])

    def test_question_min_max_creates_lint(self):
        """
        GIVEN a question with min_value=0 and max_value=100
        WHEN an answer has numeric=150
        THEN 'out_of_range' is in the lint
        """
        self.q_number.validation_settings = {'min_value': 0, 'max_value': 100}
        self.q_number.save()
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.q_number, numeric=150)
        svc = SurveyAnalyticsService(self.survey)
        answers = list(Answer.objects.filter(survey_session=s, parent_answer_id__isnull=True).select_related('question'))
        lints = svc.compute_answer_lints([s.id], answers, [self.q_number])
        self.assertIn('out_of_range', lints.get(s.id, {}).get(str(self.q_number.id), []))

    def test_settings_endpoint_saves_and_returns(self):
        """
        GIVEN an editor user
        WHEN POST to validation settings then GET
        THEN settings are persisted and returned
        """
        self._login()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/validation-settings/'
        resp = self.client.post(url, json.dumps({'fast_threshold_seconds': 60, 'duplicate_window_hours': 2}), content_type='application/json')
        self.assertEqual(resp.status_code, 204)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['fast_threshold_seconds'], 60)
        self.assertEqual(data['duplicate_window_hours'], 2)
