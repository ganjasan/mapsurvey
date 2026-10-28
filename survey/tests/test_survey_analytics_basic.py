"""Tests that no capability owns yet: survey-analytics-basic.

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
import json
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
from survey.analytics import SurveyAnalyticsService
from survey.tests.helpers import _make_org


class AnalyticsServiceTest(TestCase):
    """Tests for SurveyAnalyticsService."""

    def setUp(self):
        from survey.analytics import SurveyAnalyticsService
        self.SurveyAnalyticsService = SurveyAnalyticsService

        self.org = _make_org('AnalyticsOrg')
        self.user = User.objects.create_user('analyticsowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

        self.survey = SurveyHeader.objects.create(
            name='analytics_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section1 = SurveySection.objects.create(
            survey_header=self.survey, name='section1', code='S1', is_head=True,
        )
        self.section2 = SurveySection.objects.create(
            survey_header=self.survey, name='section2', code='S2',
        )
        self.section1.next_section = self.section2
        self.section1.save()

        self.q_choice = Question.objects.create(
            survey_section=self.section1, name='Satisfaction', code='q1',
            input_type='choice', order_number=1,
            choices=[{'code': 1, 'name': 'Good'}, {'code': 2, 'name': 'Bad'}],
        )
        self.q_number = Question.objects.create(
            survey_section=self.section1, name='Travel time', code='q2',
            input_type='number', order_number=2,
        )
        self.q_text = Question.objects.create(
            survey_section=self.section2, name='Comments', code='q3',
            input_type='text', order_number=1,
        )
        self.q_point = Question.objects.create(
            survey_section=self.section2, name='Location', code='q4',
            input_type='point', order_number=2,
        )

    def _create_completed_session(self, choice_code=1, number=10, text='Great', point=None):
        """Helper: create a session with answers in both sections."""
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(
            survey_session=session, question=self.q_choice,
            selected_choices=[choice_code],
        )
        Answer.objects.create(
            survey_session=session, question=self.q_number,
            numeric=number,
        )
        Answer.objects.create(
            survey_session=session, question=self.q_text,
            text=text,
        )
        if point:
            Answer.objects.create(
                survey_session=session, question=self.q_point,
                point=point,
            )
        return session

    def _create_abandoned_session(self):
        """Helper: create a session with no answers."""
        return SurveySession.objects.create(survey=self.survey)

    def _create_partial_session(self, choice_code=1, number=5):
        """Helper: create a session with answers only in section1."""
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(
            survey_session=session, question=self.q_choice,
            selected_choices=[choice_code],
        )
        Answer.objects.create(
            survey_session=session, question=self.q_number,
            numeric=number,
        )
        return session

    def test_overview_with_completed_and_abandoned(self):
        """
        GIVEN a survey with 3 completed, 2 abandoned, and 1 partial session
        WHEN get_overview is called
        THEN total=6, completed=3, rate=50
        """
        self._create_completed_session()
        self._create_completed_session(choice_code=2, number=20, text='OK')
        self._create_completed_session(choice_code=1, number=5, text='Fine')
        self._create_abandoned_session()
        self._create_abandoned_session()
        self._create_partial_session()

        service = self.SurveyAnalyticsService(self.survey)
        overview = service.get_overview()

        self.assertEqual(overview['total_sessions'], 6)
        self.assertEqual(overview['completed_count'], 3)
        self.assertEqual(overview['completion_rate'], 50)

    def test_overview_empty_survey(self):
        """
        GIVEN a survey with no sessions
        WHEN get_overview is called
        THEN returns zeros
        """
        service = self.SurveyAnalyticsService(self.survey)
        overview = service.get_overview()

        self.assertEqual(overview['total_sessions'], 0)
        self.assertEqual(overview['completed_count'], 0)
        self.assertEqual(overview['completion_rate'], 0)

    def test_daily_sessions(self):
        """
        GIVEN sessions created on the same day
        WHEN get_daily_sessions is called
        THEN returns one entry with correct counts
        """
        self._create_completed_session()
        self._create_abandoned_session()

        service = self.SurveyAnalyticsService(self.survey)
        daily = service.get_daily_sessions()

        self.assertEqual(len(daily), 1)
        self.assertEqual(daily[0]['total'], 2)
        self.assertEqual(daily[0]['completed'], 1)

    def test_question_stats_choice(self):
        """
        GIVEN 3 choice answers (2x Good, 1x Bad)
        WHEN get_question_stats is called for the choice question
        THEN returns correct distribution
        """
        self._create_completed_session(choice_code=1)
        self._create_completed_session(choice_code=1)
        self._create_completed_session(choice_code=2)

        service = self.SurveyAnalyticsService(self.survey)
        stat = service.get_question_stats(self.q_choice)

        self.assertEqual(stat['type'], 'choices')
        self.assertEqual(stat['choice_labels'], ['Good', 'Bad'])
        self.assertEqual(stat['choice_counts'], [2, 1])
        self.assertEqual(stat['total_answers'], 3)

    def test_question_stats_number(self):
        """
        GIVEN numeric answers [5, 10, 20]
        WHEN get_question_stats is called for the number question
        THEN returns correct avg, median, min, max
        """
        self._create_completed_session(number=5)
        self._create_completed_session(number=10)
        self._create_completed_session(number=20)

        service = self.SurveyAnalyticsService(self.survey)
        stat = service.get_question_stats(self.q_number)

        self.assertEqual(stat['type'], 'number')
        self.assertEqual(stat['count'], 3)
        self.assertAlmostEqual(stat['avg'], 11.7, places=1)
        self.assertEqual(stat['median'], 10)
        self.assertEqual(stat['min_val'], 5)
        self.assertEqual(stat['max_val'], 20)

    def test_question_stats_number_all_values_equal(self):
        """
        GIVEN three numeric answers with the same value (min == max)
        WHEN get_question_stats is called
        THEN it returns a single-bucket histogram instead of raising KeyError
        """
        self._create_completed_session(number=5)
        self._create_completed_session(number=5)
        self._create_completed_session(number=5)

        service = self.SurveyAnalyticsService(self.survey)
        stat = service.get_question_stats(self.q_number)

        self.assertEqual(stat['count'], 3)
        self.assertEqual(stat['min_val'], 5)
        self.assertEqual(stat['max_val'], 5)
        self.assertIn('hist_labels_json', stat)
        self.assertIn('hist_counts_json', stat)
        self.assertIn('hist_bins_json', stat)
        self.assertEqual(json.loads(stat['hist_counts_json']), [3])
        self.assertEqual(json.loads(stat['hist_bins_json']), [[5, 5]])

    def test_text_answers_pagination(self):
        """
        GIVEN 25 text answers
        WHEN get_text_answers is called with page=2, page_size=10
        THEN returns answers 11-20 with correct page info
        """
        for i in range(25):
            session = SurveySession.objects.create(survey=self.survey)
            Answer.objects.create(
                survey_session=session, question=self.q_text,
                text=f'Answer {i+1}',
            )

        service = self.SurveyAnalyticsService(self.survey)
        result = service.get_text_answers(self.q_text, page=2, page_size=10)

        self.assertEqual(len(result['answers']), 10)
        self.assertEqual(result['page'], 2)
        self.assertEqual(result['total_pages'], 3)
        self.assertEqual(result['total'], 25)

    def test_geo_feature_collection(self):
        """
        GIVEN 2 point answers
        WHEN get_geo_feature_collection is called
        THEN returns FeatureCollection with 2 features
        """
        self._create_completed_session(point=Point(2.35, 48.86))
        self._create_completed_session(point=Point(4.83, 45.76))

        service = self.SurveyAnalyticsService(self.survey)
        fc = service.get_geo_feature_collection()

        self.assertEqual(fc['type'], 'FeatureCollection')
        self.assertEqual(len(fc['features']), 2)
        self.assertEqual(fc['features'][0]['properties']['question'], 'Location')
        self.assertEqual(fc['features'][0]['properties']['type'], 'point')


class AnalyticsViewTest(TestCase):
    """Tests for analytics dashboard views."""

    def setUp(self):
        self.org = _make_org('AnalyticsViewOrg')
        self.owner = User.objects.create_user('dashowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.client.login(username='dashowner', password='pass')

        # Set active org in session
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

        self.survey = SurveyHeader.objects.create(
            name='dash_test', organization=self.org,
            created_by=self.owner, status='published',
        )
        section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.q = Question.objects.create(
            survey_section=section, name='Q1', code='q1',
            input_type='text', order_number=1,
        )
        sess = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=sess, question=self.q, text='Hello')

    def test_dashboard_requires_auth(self):
        """
        GIVEN an unauthenticated user
        WHEN GET analytics dashboard
        THEN redirect to login
        """
        self.client.logout()
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/analytics/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    @override_settings(RESPONSES_V2=False)
    def test_dashboard_renders(self):
        """
        GIVEN an authenticated survey owner and Responses v2 off
        WHEN GET analytics dashboard
        THEN returns 200 with analytics data

        Pinned to RESPONSES_V2=False: these are the v1 KPI labels. v2 replaced
        the dashboard with its own pane set and carries its own tests
        (ResponsesV2* classes).
        """
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/analytics/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Total Sessions')
        self.assertContains(response, 'Completed')
        self.assertContains(response, 'Completion Rate')

    def test_text_answers_partial(self):
        """
        GIVEN a survey with text answers
        WHEN GET text answers HTMX endpoint
        THEN returns 200 with answer text
        """
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/analytics/questions/{self.q.id}/text/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hello')
