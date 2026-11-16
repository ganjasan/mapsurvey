"""Tests that no capability owns yet: response-validation-management.

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point, Polygon
import json
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
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


class AnswerLintingErrorsTest(TestCase):
    """The one per-answer note left: crossed polygon edges (change responses-required-unanswered)."""

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
        WHEN crossed_shapes is called
        THEN the answer's question is noted for that session
        """
        s = SurveySession.objects.create(survey=self.survey)
        # Bowtie polygon: self-intersecting
        bowtie = Polygon(((0, 0), (1, 1), (1, 0), (0, 1), (0, 0)))
        Answer.objects.create(survey_session=s, question=self.q_polygon, polygon=bowtie)
        Answer.objects.create(survey_session=s, question=self.q_required, text='Alice')

        answers = list(Answer.objects.filter(survey_session=s, parent_answer_id__isnull=True).select_related('question'))
        crossed = SurveyAnalyticsService.crossed_shapes(answers)
        self.assertEqual(crossed.get(s.id), {self.q_polygon.id})

    def test_valid_polygon_no_lint(self):
        """
        GIVEN a polygon answer with valid geometry
        WHEN crossed_shapes is called
        THEN nothing is noted
        """
        s = SurveySession.objects.create(survey=self.survey)
        valid_poly = Polygon(((0, 0), (1, 0), (1, 1), (0, 1), (0, 0)))
        Answer.objects.create(survey_session=s, question=self.q_polygon, polygon=valid_poly)
        Answer.objects.create(survey_session=s, question=self.q_required, text='Bob')

        answers = list(Answer.objects.filter(survey_session=s, parent_answer_id__isnull=True).select_related('question'))
        self.assertEqual(SurveyAnalyticsService.crossed_shapes(answers), {})

    def test_table_page_includes_lints(self):
        """
        GIVEN a session with lint errors
        WHEN get_table_page is called
        THEN its row carries the crossed-edges note on the polygon column
        """
        s = SurveySession.objects.create(survey=self.survey)
        bowtie = Polygon(((0, 0), (1, 1), (1, 0), (0, 1), (0, 0)))
        Answer.objects.create(survey_session=s, question=self.q_polygon, polygon=bowtie)
        Answer.objects.create(survey_session=s, question=self.q_required, text='Data')

        svc = SurveyAnalyticsService(self.survey)
        result = svc.get_table_page()
        self.assertEqual(result['rows'][0]['lints'], {str(self.q_polygon.id): ['self_intersection']})


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


