"""Tests for the `responses-detail-drawer` capability (openspec/specs/responses-detail-drawer/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
from survey.tests.helpers import _make_org


class ResponsesV2DrawerTest(TestCase):
    """Detail drawer: replaces the modal, reuses the detail endpoint, in-page confirm."""

    def setUp(self):
        self.org = _make_org('RespV2DrwOrg')
        self.owner = User.objects.create_user('respv2drwowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.client.login(username='respv2drwowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.survey = SurveyHeader.objects.create(
            name='respv2_drw', organization=self.org,
            created_by=self.owner, status='published',
        )
        section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.q = Question.objects.create(
            survey_section=section, name='Q1', code='q1',
            input_type='text', order_number=1,
        )
        self.sess = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=self.sess, question=self.q, text='drawer body')
        self.dash_url = f'/editor/surveys/{self.survey.uuid}/analytics/'
        self.detail_url = (
            f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{self.sess.id}/'
        )

    @override_settings(RESPONSES_V2=True)
    def test_drawer_replaces_modal(self):
        """
        GIVEN the v2 switch is on
        WHEN GET the dashboard
        THEN the drawer renders, the Session Details modal does not, and the
             engine's modal opener is overridden to the drawer
        """
        response = self.client.get(self.dash_url)
        self.assertContains(response, 'id="rv2-drawer"')
        self.assertContains(response, 'rv2-drawer-body')
        self.assertContains(response, 'rv2-drawer-prev')
        self.assertContains(response, 'rv2-drawer-next')
        self.assertNotContains(response, 'id="sessionDetailModal"')
        self.assertContains(response, 'window.loadSessionDetail = rv2OpenDrawer')

    @override_settings(RESPONSES_V2=True)
    def test_drawer_uses_inpage_confirm(self):
        """
        GIVEN the v2 switch is on
        WHEN GET the dashboard
        THEN destructive actions are overridden onto the in-page confirm bar
        """
        response = self.client.get(self.dash_url)
        self.assertContains(response, 'function rv2Confirm')
        self.assertContains(response, 'window.trashSession = function')
        self.assertContains(response, 'window.hardDeleteSession = function')
        self.assertContains(response, 'window._bulkAction = function')

    @override_settings(RESPONSES_V2=True)
    def test_detail_endpoint_carries_status_chips(self):
        """
        GIVEN an editor opens a session's detail partial with v2 on
        WHEN GET the session detail endpoint the drawer feeds from
        THEN the answers and the v2 status chips render
        """
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'drawer body')
        self.assertContains(response, 'rv2-detail-status')
        self.assertContains(response, 'rv2SetStatus')

    @override_settings(RESPONSES_V2=False)
    def test_legacy_detail_has_no_chips(self):
        """
        GIVEN the v2 switch is off
        WHEN GET the session detail endpoint
        THEN the partial renders without v2 status chips
        """
        response = self.client.get(self.detail_url)
        self.assertContains(response, 'drawer body')
        self.assertNotContains(response, 'rv2-detail-status')

    def test_status_roundtrip(self):
        """
        GIVEN a session with no status
        WHEN POST the set-status endpoint the chips call
        THEN the session's validation_status persists
        """
        url = (
            f'/editor/surveys/{self.survey.uuid}/analytics/'
            f'sessions/{self.sess.id}/status/'
        )
        response = self.client.post(url, {'validation_status': 'approved'})
        self.assertIn(response.status_code, (200, 204))
        self.sess.refresh_from_db()
        self.assertEqual(self.sess.validation_status, 'approved')


class SessionDetailViewTest(TestCase):
    """Tests for analytics session detail modal endpoint."""

    def setUp(self):
        self.org = _make_org('SessionDetailOrg')
        self.owner = User.objects.create_user('sdowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.client.login(username='sdowner', password='pass')

        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

        self.survey = SurveyHeader.objects.create(
            name='sd_test', organization=self.org,
            created_by=self.owner, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.q_choice = Question.objects.create(
            survey_section=self.section, name='Favorite', code='qf',
            input_type='choice', order_number=1,
            choices=[{'code': 1, 'name': 'Alpha'}, {'code': 2, 'name': 'Beta'}],
        )
        self.q_text = Question.objects.create(
            survey_section=self.section, name='Comment', code='qc',
            input_type='text', order_number=2,
        )
        self.q_point = Question.objects.create(
            survey_section=self.section, name='Location', code='qp',
            input_type='point', order_number=3,
        )

        self.sess = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(
            survey_session=self.sess, question=self.q_choice,
            selected_choices=[1],
        )
        Answer.objects.create(
            survey_session=self.sess, question=self.q_text,
            text='Great survey',
        )
        Answer.objects.create(
            survey_session=self.sess, question=self.q_point,
            point=Point(2.35, 48.86),
        )

    def test_session_detail_returns_200(self):
        """
        GIVEN a session with answers
        WHEN GET analytics session detail
        THEN returns 200 with answer data
        """
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{self.sess.id}/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alpha')
        self.assertContains(response, 'Great survey')
        self.assertContains(response, 'point feature')

    def test_session_detail_wrong_survey_404(self):
        """
        GIVEN a session from survey A
        WHEN GET session detail using survey B uuid
        THEN returns 404
        """
        other_survey = SurveyHeader.objects.create(
            name='other', organization=self.org,
            created_by=self.owner, status='published',
        )
        response = self.client.get(
            f'/editor/surveys/{other_survey.uuid}/analytics/sessions/{self.sess.id}/'
        )
        self.assertEqual(response.status_code, 404)

    def test_session_detail_requires_auth(self):
        """
        GIVEN an unauthenticated user
        WHEN GET session detail
        THEN redirect to login
        """
        self.client.logout()
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{self.sess.id}/'
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
