"""Tests for the `survey-performance-analytics` capability (openspec/specs/survey-performance-analytics/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
import json
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
from survey.models import SurveyEvent, TrackedLink
from survey.events import emit_event, _classify_referrer, _parse_user_agent
from survey.analytics import PerformanceAnalyticsService
from survey.tests.helpers import _make_org


class UserAgentParserTest(TestCase):
    """Tests for user agent parsing into device, OS, and browser."""

    def test_chrome_windows_desktop(self):
        """
        GIVEN a Chrome on Windows UA string
        WHEN _parse_user_agent is called
        THEN device_type=desktop, os=Windows, browser=Chrome
        """
        ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        result = _parse_user_agent(ua)
        self.assertEqual(result['device_type'], 'desktop')
        self.assertEqual(result['os'], 'Windows')
        self.assertEqual(result['browser'], 'Chrome')

    def test_safari_iphone_mobile(self):
        """
        GIVEN an iPhone Safari UA string
        WHEN _parse_user_agent is called
        THEN device_type=mobile, os=iOS, browser=Safari
        """
        ua = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
        result = _parse_user_agent(ua)
        self.assertEqual(result['device_type'], 'mobile')
        self.assertEqual(result['os'], 'iOS')
        self.assertEqual(result['browser'], 'Safari')

    def test_firefox_linux_desktop(self):
        """
        GIVEN a Firefox on Linux UA string
        WHEN _parse_user_agent is called
        THEN device_type=desktop, os=Linux, browser=Firefox
        """
        ua = 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0'
        result = _parse_user_agent(ua)
        self.assertEqual(result['device_type'], 'desktop')
        self.assertEqual(result['os'], 'Linux')
        self.assertEqual(result['browser'], 'Firefox')

    def test_android_chrome_mobile(self):
        """
        GIVEN a Chrome on Android mobile UA string
        WHEN _parse_user_agent is called
        THEN device_type=mobile, os=Android, browser=Chrome
        """
        ua = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
        result = _parse_user_agent(ua)
        self.assertEqual(result['device_type'], 'mobile')
        self.assertEqual(result['os'], 'Android')
        self.assertEqual(result['browser'], 'Chrome')

    def test_ipad_tablet(self):
        """
        GIVEN an iPad UA string
        WHEN _parse_user_agent is called
        THEN device_type=tablet, os=iOS
        """
        ua = 'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
        result = _parse_user_agent(ua)
        self.assertEqual(result['device_type'], 'tablet')
        self.assertEqual(result['os'], 'iOS')

    def test_empty_ua(self):
        """
        GIVEN an empty UA string
        WHEN _parse_user_agent is called
        THEN all fields are 'unknown'
        """
        result = _parse_user_agent('')
        self.assertEqual(result['device_type'], 'unknown')
        self.assertEqual(result['os'], 'unknown')
        self.assertEqual(result['browser'], 'unknown')

    def test_edge_browser(self):
        """
        GIVEN an Edge browser UA string
        WHEN _parse_user_agent is called
        THEN browser=Edge
        """
        ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
        result = _parse_user_agent(ua)
        self.assertEqual(result['browser'], 'Edge')

    def test_yandex_browser(self):
        """
        GIVEN a Yandex Browser UA string
        WHEN _parse_user_agent is called
        THEN browser=Yandex
        """
        ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 YaBrowser/24.1.0 Safari/537.36'
        result = _parse_user_agent(ua)
        self.assertEqual(result['browser'], 'Yandex')


class ReferrerClassificationTest(TestCase):
    """Tests for referrer hostname extraction and bucketing."""

    def test_google_referrer(self):
        """
        GIVEN a referrer URL from google.com
        WHEN _classify_referrer is called
        THEN it returns host 'google.com' and bucket 'google'
        """
        host, bucket = _classify_referrer('https://www.google.com/search?q=survey')
        self.assertEqual(bucket, 'google')
        self.assertEqual(host, 'google.com')

    def test_direct_empty_referrer(self):
        """
        GIVEN an empty referrer string
        WHEN _classify_referrer is called
        THEN it returns empty host and bucket 'direct'
        """
        host, bucket = _classify_referrer('')
        self.assertEqual(bucket, 'direct')
        self.assertEqual(host, '')

    def test_direct_none_referrer(self):
        """
        GIVEN None as referrer
        WHEN _classify_referrer is called
        THEN it returns empty host and bucket 'direct'
        """
        host, bucket = _classify_referrer(None)
        self.assertEqual(bucket, 'direct')
        self.assertEqual(host, '')

    def test_social_instagram(self):
        """
        GIVEN a referrer URL from instagram.com
        WHEN _classify_referrer is called
        THEN it returns bucket 'social'
        """
        host, bucket = _classify_referrer('https://l.instagram.com/redirect?u=...')
        self.assertEqual(bucket, 'social')

    def test_unknown_domain_is_other(self):
        """
        GIVEN a referrer URL from an unrecognized domain
        WHEN _classify_referrer is called
        THEN it returns the bare hostname and bucket 'other'
        """
        host, bucket = _classify_referrer('https://example-blog.com/post/1')
        self.assertEqual(bucket, 'other')
        self.assertEqual(host, 'example-blog.com')

    def test_www_prefix_stripped(self):
        """
        GIVEN a referrer with www.facebook.com
        WHEN _classify_referrer is called
        THEN it returns 'facebook.com' and bucket 'social'
        """
        host, bucket = _classify_referrer('https://www.facebook.com/share')
        self.assertEqual(host, 'facebook.com')
        self.assertEqual(bucket, 'social')


class EmitEventTest(TestCase):
    """Tests for the emit_event function."""

    def setUp(self):
        self.org = _make_org('EventOrg')
        self.survey = SurveyHeader.objects.create(
            name='event_survey', organization=self.org, status='published',
        )
        self.session = SurveySession.objects.create(survey=self.survey)

    def test_emit_creates_event_row(self):
        """
        GIVEN a saved SurveySession
        WHEN emit_event is called with event_type='section_view'
        THEN a SurveyEvent row is created with correct fields
        """
        emit_event(self.session, 'section_view', {'section_name': 'intro'})
        ev = SurveyEvent.objects.get(session=self.session, event_type='section_view')
        self.assertEqual(ev.metadata['section_name'], 'intro')

    def test_emit_with_none_session(self):
        """
        GIVEN None as session
        WHEN emit_event is called
        THEN no exception is raised and no row is created
        """
        emit_event(None, 'section_view')
        self.assertEqual(SurveyEvent.objects.count(), 0)

    def test_emit_swallows_db_error(self):
        """
        GIVEN an unsaved session with no PK
        WHEN emit_event is called
        THEN no exception propagates to the caller
        """
        unsaved = SurveySession(survey=self.survey)
        try:
            emit_event(unsaved, 'session_start')
        except Exception as e:
            self.fail(f'emit_event raised unexpectedly: {e}')


class EventIntegrationTest(TestCase):
    """Tests for event emission in survey views."""

    def setUp(self):
        self.client = Client()
        self.org = _make_org('EventIntOrg')
        self.user = User.objects.create_user('eventuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='event_int_survey', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.question = Question.objects.create(
            survey_section=self.section, name='Q1', code='q1',
            input_type='text', order_number=1,
        )

    def test_session_start_on_first_visit(self):
        """
        GIVEN a published survey with one section
        WHEN a GET to the first section is made without an existing session
        THEN a session_start and section_view SurveyEvent are created
        """
        self.client.get(f'/surveys/{self.survey.uuid}/s1/')
        self.assertTrue(SurveyEvent.objects.filter(event_type='session_start').exists())
        self.assertTrue(SurveyEvent.objects.filter(event_type='section_view').exists())

    def test_no_duplicate_session_start_on_revisit(self):
        """
        GIVEN a session already created from visiting section s1
        WHEN the same section is visited again (back navigation)
        THEN no additional session_start event is created
        """
        self.client.get(f'/surveys/{self.survey.uuid}/s1/')
        start_count = SurveyEvent.objects.filter(event_type='session_start').count()
        self.client.get(f'/surveys/{self.survey.uuid}/s1/')
        self.assertEqual(
            SurveyEvent.objects.filter(event_type='session_start').count(),
            start_count,
        )

    def test_section_submit_on_post(self):
        """
        GIVEN an active session on section s1
        WHEN a POST with answer data is made
        THEN a section_submit event is created
        """
        self.client.get(f'/surveys/{self.survey.uuid}/s1/')
        self.client.post(f'/surveys/{self.survey.uuid}/s1/', {'q1': 'hello'})
        self.assertTrue(SurveyEvent.objects.filter(event_type='section_submit').exists())

    def test_survey_complete_on_thanks(self):
        """
        GIVEN an active session that submitted the last section
        WHEN the thanks page is visited
        THEN a survey_complete event is created
        """
        self.client.get(f'/surveys/{self.survey.uuid}/s1/')
        self.client.post(f'/surveys/{self.survey.uuid}/s1/', {'q1': 'hello'})
        self.client.get(f'/surveys/{self.survey.uuid}/thanks/')
        self.assertTrue(SurveyEvent.objects.filter(event_type='survey_complete').exists())

    def test_session_row_records_activity_and_completion(self):
        """
        GIVEN a respondent who opened the survey
        WHEN they submit a section, then reach the thanks page twice
        THEN the section submit stamps last_activity_at, the thanks page stamps end_datetime
             once (a reload keeps the first time) and both live on the session row
        """
        self.client.get(f'/surveys/{self.survey.uuid}/s1/')
        session = SurveySession.objects.get(pk=self.client.session['survey_session_id'])
        self.assertIsNone(session.last_activity_at)
        self.client.post(f'/surveys/{self.survey.uuid}/s1/', {'q1': 'hello'})
        session.refresh_from_db()
        self.assertIsNotNone(session.last_activity_at)
        self.assertIsNone(session.end_datetime)
        self.client.get(f'/surveys/{self.survey.uuid}/thanks/')
        session.refresh_from_db()
        first_end = session.end_datetime
        self.assertIsNotNone(first_end)
        session.mark_completed()
        session.refresh_from_db()
        self.assertEqual(session.end_datetime, first_end)

    def test_session_start_captures_referrer(self):
        """
        GIVEN a request with HTTP_REFERER from google.com
        WHEN the first section is visited
        THEN the session_start event metadata contains referrer_type='google'
        """
        self.client.get(
            f'/surveys/{self.survey.uuid}/s1/',
            HTTP_REFERER='https://www.google.com/search?q=test',
        )
        ev = SurveyEvent.objects.get(event_type='session_start')
        self.assertEqual(ev.metadata['referrer_type'], 'google')
        self.assertEqual(ev.metadata['referrer_host'], 'google.com')


class PageLoadTrackingTest(TestCase):
    """Tests for the fire-and-forget page_load AJAX endpoint."""

    def setUp(self):
        self.client = Client()
        self.org = _make_org('PLOrg')
        self.survey = SurveyHeader.objects.create(
            name='pl_survey', organization=self.org, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        # Visit section to create session
        self.client.get(f'/surveys/{self.survey.uuid}/s1/')
        self.session = SurveySession.objects.first()

    def test_valid_page_load_creates_event(self):
        """
        GIVEN a valid session_id matching the server session and a load_ms value
        WHEN POST is sent to /surveys/track/event/ with event_type=page_load
        THEN response is 204 and a page_load SurveyEvent is created
        """
        response = self.client.post(
            '/surveys/track/event/',
            data=json.dumps({
                'event_type': 'page_load',
                'session_id': self.session.pk,
                'load_ms': 1500,
                'section_name': 's1',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 204)
        ev = SurveyEvent.objects.filter(event_type='page_load').first()
        self.assertIsNotNone(ev)
        self.assertEqual(ev.metadata['load_ms'], 1500)

    def test_valid_page_leave_creates_event(self):
        """
        GIVEN a valid session and time_on_page_ms
        WHEN POST is sent with event_type=page_leave
        THEN response is 204 and a page_leave SurveyEvent is created
        """
        response = self.client.post(
            '/surveys/track/event/',
            data=json.dumps({
                'event_type': 'page_leave',
                'session_id': self.session.pk,
                'time_on_page_ms': 45000,
                'section_name': 's1',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 204)
        ev = SurveyEvent.objects.filter(event_type='page_leave').first()
        self.assertIsNotNone(ev)
        self.assertEqual(ev.metadata['time_on_page_ms'], 45000)
        # The beacon is the last trace an abandoning respondent leaves: the
        # session row records it (spec responses-overview "Session timing").
        self.session.refresh_from_db()
        self.assertIsNotNone(self.session.last_activity_at)

    def test_mismatched_session_returns_204_silently(self):
        """
        GIVEN a session_id in payload that does not match the server session
        WHEN POST is sent to /surveys/track/event/
        THEN response is 204 and no event is created
        """
        response = self.client.post(
            '/surveys/track/event/',
            data=json.dumps({
                'event_type': 'page_load',
                'session_id': 99999,
                'load_ms': 1000,
                'section_name': 's1',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(SurveyEvent.objects.filter(event_type='page_load').exists())

    def test_invalid_event_type_returns_400(self):
        """
        GIVEN an event_type not in the allowed set
        WHEN POST is sent to /surveys/track/event/
        THEN response is 400
        """
        response = self.client.post(
            '/surveys/track/event/',
            data=json.dumps({
                'event_type': 'session_start',
                'session_id': self.session.pk,
                'section_name': 's1',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_fields_returns_400(self):
        """
        GIVEN a payload missing session_id
        WHEN POST is sent to /surveys/track/event/
        THEN response is 400
        """
        response = self.client.post(
            '/surveys/track/event/',
            data=json.dumps({
                'event_type': 'page_load',
                'section_name': 's1',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_load_ms_returns_400(self):
        """
        GIVEN a load_ms value of 0 (invalid)
        WHEN POST is sent to /surveys/track/event/
        THEN response is 400
        """
        response = self.client.post(
            '/surveys/track/event/',
            data=json.dumps({
                'event_type': 'page_load',
                'session_id': self.session.pk,
                'load_ms': 0,
                'section_name': 's1',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)


class PerformanceAnalyticsServiceTest(TestCase):
    """Tests for PerformanceAnalyticsService query methods."""

    def setUp(self):
        self.org = _make_org('PerfOrg')
        self.survey = SurveyHeader.objects.create(
            name='perf_survey', organization=self.org, status='published',
        )
        self.s1 = SurveySession.objects.create(survey=self.survey)
        self.s2 = SurveySession.objects.create(survey=self.survey)

    def test_event_summary_counts(self):
        """
        GIVEN two sessions, one completed
        WHEN get_event_summary is called
        THEN session_starts=2, completions=1, completion_rate=50
        """
        from survey.analytics import PerformanceAnalyticsService
        emit_event(self.s1, 'session_start')
        emit_event(self.s2, 'session_start')
        emit_event(self.s1, 'survey_complete')

        svc = PerformanceAnalyticsService(self.survey)
        summary = svc.get_event_summary()
        self.assertEqual(summary['session_starts'], 2)
        self.assertEqual(summary['completions'], 1)
        self.assertEqual(summary['completion_rate'], 50)

    def _section(self, name, is_head=False):
        return SurveySection.objects.create(
            survey_header=self.survey, name=name, code=name.upper(), is_head=is_head,
        )

    def test_funnel_counts_a_session_once_however_often_it_reloads(self):
        """
        GIVEN one session that viewed section A three times and submitted it once
        WHEN get_funnel is called
        THEN A shows reached=1 and completed=1, while raw views stays 3
        """
        from survey.analytics import PerformanceAnalyticsService
        self._section('a', is_head=True)
        emit_event(self.s1, 'session_start')
        for _ in range(3):
            emit_event(self.s1, 'section_view', {'section_name': 'a'})
        emit_event(self.s1, 'section_submit', {'section_name': 'a'})

        step = PerformanceAnalyticsService(self.survey).get_funnel()[0]
        self.assertEqual(step['reached'], 1)
        self.assertEqual(step['completed'], 1)
        self.assertEqual(step['views'], 3)
        self.assertEqual(step['reached_pct'], 100)
        self.assertEqual(step['dropped'], 0)

    def test_funnel_percentages_are_relative_to_starts_and_previous_step(self):
        """
        GIVEN 10 started sessions, 8 of which viewed A and 5 viewed B
        WHEN get_funnel is called
        THEN A is 80% reached / 2 dropped (20%) and B is 50% reached / 3 dropped (38% of A)
        """
        from survey.analytics import PerformanceAnalyticsService
        a = self._section('a', is_head=True)
        b = self._section('b')
        a.next_section = b
        a.save()
        sessions = [SurveySession.objects.create(survey=self.survey) for _ in range(10)]
        for sess in sessions:
            emit_event(sess, 'session_start')
        for sess in sessions[:8]:
            emit_event(sess, 'section_view', {'section_name': 'a'})
        for sess in sessions[:5]:
            emit_event(sess, 'section_view', {'section_name': 'b'})

        fa, fb = PerformanceAnalyticsService(self.survey).get_funnel()
        self.assertEqual((fa['step'], fa['reached'], fa['reached_pct'], fa['dropped'], fa['dropped_pct']),
                         (1, 8, 80, 2, 20))
        self.assertEqual((fb['step'], fb['reached'], fb['reached_pct'], fb['dropped'], fb['dropped_pct']),
                         (2, 5, 50, 3, 38))

    def test_funnel_never_reports_negative_drop(self):
        """
        GIVEN section A reached by 1 session and later section B reached by 2
        WHEN get_funnel is called
        THEN B shows dropped=0 and dropped_pct=0
        """
        from survey.analytics import PerformanceAnalyticsService
        a = self._section('a', is_head=True)
        b = self._section('b')
        a.next_section = b
        a.save()
        emit_event(self.s1, 'session_start')
        emit_event(self.s2, 'session_start')
        emit_event(self.s1, 'section_view', {'section_name': 'a'})
        emit_event(self.s1, 'section_view', {'section_name': 'b'})
        emit_event(self.s2, 'section_view', {'section_name': 'b'})

        fb = PerformanceAnalyticsService(self.survey).get_funnel()[1]
        self.assertEqual(fb['reached'], 2)
        self.assertEqual(fb['dropped'], 0)
        self.assertEqual(fb['dropped_pct'], 0)

    # -- conditional sections (change funnel-conditional-sections) -----------------

    def _branch_survey(self, starts=10, viewed_a=10, yes=7, viewed_b=7, viewed_c=None, rule=None):
        """A → B (shown when Q = Yes) → C, with the given session counts."""
        from survey.visibility import CONTROLLER_TYPES  # noqa: F401 — documents the contract
        a = self._section('a', is_head=True)
        b = self._section('b')
        c = self._section('c')
        a.next_section = b
        a.save()
        b.next_section = c
        b.save()
        q = Question.objects.create(
            survey_section=a, name='Show B?', code='q_show_b', input_type='choice', order_number=1,
            choices=[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}],
        )
        b.visibility_rule = rule if rule is not None else {"question_code": "q_show_b", "choice_codes": [1]}
        b.save()
        sessions = [SurveySession.objects.create(survey=self.survey) for _ in range(starts)]
        for sess in sessions:
            emit_event(sess, 'session_start')
        for sess in sessions[:viewed_a]:
            emit_event(sess, 'section_view', {'section_name': 'a'})
        for i, sess in enumerate(sessions[:viewed_a]):
            Answer.objects.create(survey_session=sess, question=q, selected_choices=[1 if i < yes else 2])
        for sess in sessions[:viewed_b]:
            emit_event(sess, 'section_view', {'section_name': 'b'})
        if viewed_c is not None:
            for sess in sessions[:viewed_c]:
                emit_event(sess, 'section_view', {'section_name': 'c'})
        return sessions

    def test_funnel_rule_skipped_sessions_are_not_dropped(self):
        """
        GIVEN 10 started sessions, all viewed A, 7 answered Yes to the question that shows B, all 7 viewed B
        WHEN get_funnel is called
        THEN B is conditional with eligible=7, skipped=3, dropped=0, reached_pct=70
        """
        from survey.analytics import PerformanceAnalyticsService
        self._branch_survey()
        fb = PerformanceAnalyticsService(self.survey).get_funnel()[1]
        self.assertTrue(fb['conditional'])
        self.assertEqual((fb['eligible'], fb['skipped'], fb['dropped'], fb['dropped_pct'], fb['reached_pct']),
                         (7, 3, 0, 0, 70))
        self.assertEqual(fb['skipped_pct'], 30)
        self.assertEqual(fb['eligible_pct'], 100)
        self.assertEqual(fb['rule_label'], 'Show B? = Yes')

    def test_funnel_answered_rule_counts_any_selection(self):
        """
        GIVEN B shown when the question is answered at all (change
              visibility-answered-condition), 10 sessions viewing A and 7
              answering (Yes or No), 7 viewing B
        WHEN get_funnel is called
        THEN eligible counts every answered session, whichever option, and the
             label reads "Show B? answered"
        """
        from survey.analytics import PerformanceAnalyticsService
        sessions = self._branch_survey(yes=4, rule={"question_code": "q_show_b", "answered": True})
        # Three of the ten viewed A but never answered: strip their answers.
        Answer.objects.filter(survey_session__in=sessions[7:]).delete()
        fb = PerformanceAnalyticsService(self.survey).get_funnel()[1]
        self.assertTrue(fb['conditional'])
        self.assertEqual((fb['eligible'], fb['skipped'], fb['dropped']), (7, 3, 0))
        self.assertEqual(fb['rule_label'], 'Show B? answered')

    def test_funnel_loss_inside_a_branch_is_relative_to_eligible(self):
        """
        GIVEN the same survey but only 5 of the 7 eligible sessions viewed B
        WHEN get_funnel is called
        THEN B has eligible=7, skipped=3, dropped=2, dropped_pct=29 (2 of 7, not of 10)
        """
        from survey.analytics import PerformanceAnalyticsService
        self._branch_survey(viewed_b=5)
        fb = PerformanceAnalyticsService(self.survey).get_funnel()[1]
        self.assertEqual((fb['eligible'], fb['skipped'], fb['dropped'], fb['dropped_pct']), (7, 3, 2, 29))
        self.assertEqual(fb['eligible_pct'], 71)

    def test_funnel_broken_rule_falls_open(self):
        """
        GIVEN B's rule references a question code that does not exist
        WHEN get_funnel is called
        THEN B is unconditional, flagged rule_broken, and its drop follows the plain formula
        """
        from survey.analytics import PerformanceAnalyticsService
        self._branch_survey(rule={"question_code": "gone", "choice_codes": [1]})
        fb = PerformanceAnalyticsService(self.survey).get_funnel()[1]
        self.assertFalse(fb['conditional'])
        self.assertTrue(fb['rule_broken'])
        self.assertEqual(fb['rule_reason'], 'controlling question not found')
        self.assertEqual((fb['skipped'], fb['dropped'], fb['dropped_pct']), (0, 3, 30))

    def test_funnel_branch_does_not_inflate_its_successor(self):
        """
        GIVEN A reached by 10, conditional B by 7, C by 10
        WHEN get_funnel is called
        THEN C has dropped=0 and both B and C name step 1 as their baseline
        """
        from survey.analytics import PerformanceAnalyticsService
        self._branch_survey(viewed_c=10)
        fa, fb, fc = PerformanceAnalyticsService(self.survey).get_funnel()
        self.assertEqual(fa['baseline_step'], 0)
        self.assertEqual((fb['baseline_step'], fc['baseline_step']), (1, 1))
        self.assertEqual((fc['dropped'], fc['dropped_pct']), (0, 0))

    def test_funnel_real_loss_after_a_branch_is_measured_against_baseline(self):
        """
        GIVEN A reached by 10, conditional B by 7, C by 8
        WHEN get_funnel is called
        THEN C has dropped=2, dropped_pct=20 (against A's 10, not B's 7), baseline_step=1
        """
        from survey.analytics import PerformanceAnalyticsService
        self._branch_survey(viewed_c=8)
        fc = PerformanceAnalyticsService(self.survey).get_funnel()[2]
        self.assertEqual((fc['dropped'], fc['dropped_pct'], fc['baseline_step']), (2, 20, 1))

    def test_referrer_breakdown_groups_by_type(self):
        """
        GIVEN two session_start events from google and one direct
        WHEN get_referrer_breakdown is called
        THEN google has count 2 and appears first
        """
        from survey.analytics import PerformanceAnalyticsService
        emit_event(self.s1, 'session_start', {'referrer_type': 'google'})
        emit_event(self.s2, 'session_start', {'referrer_type': 'google'})
        s3 = SurveySession.objects.create(survey=self.survey)
        emit_event(s3, 'session_start', {'referrer_type': 'direct'})

        svc = PerformanceAnalyticsService(self.survey)
        refs = svc.get_referrer_breakdown()
        self.assertEqual(refs[0]['referrer_type'], 'google')
        self.assertEqual(refs[0]['count'], 2)

    def test_empty_survey_returns_safe_defaults(self):
        """
        GIVEN a survey with no events
        WHEN all service methods are called
        THEN they return empty lists or zero counts without error
        """
        from survey.analytics import PerformanceAnalyticsService
        svc = PerformanceAnalyticsService(self.survey)
        summary = svc.get_event_summary()
        self.assertEqual(summary['session_starts'], 0)
        self.assertIsNone(summary['median_load_ms'])
        self.assertEqual(svc.get_funnel(), [])
        self.assertEqual(svc.get_referrer_breakdown(), [])
        self.assertEqual(svc.get_page_load_stats(), [])

    def test_completion_by_referrer(self):
        """
        GIVEN two sessions from 'social', one completed
        WHEN get_completion_by_referrer is called
        THEN social has started=2, completed=1, rate=50
        """
        from survey.analytics import PerformanceAnalyticsService
        emit_event(self.s1, 'session_start', {'referrer_type': 'social'})
        emit_event(self.s2, 'session_start', {'referrer_type': 'social'})
        emit_event(self.s1, 'survey_complete')

        svc = PerformanceAnalyticsService(self.survey)
        result = svc.get_completion_by_referrer()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['started'], 2)
        self.assertEqual(result[0]['completed'], 1)
        self.assertEqual(result[0]['rate'], 50)


class UtmCaptureTest(TestCase):
    """Tests for UTM param capture via session storage and event metadata."""

    def setUp(self):
        self.client = Client()
        self.org = _make_org('UtmOrg')
        self.survey = SurveyHeader.objects.create(
            name='utmsurvey', organization=self.org, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', is_head=True, code='S1',
        )

    def test_utm_stored_in_session_on_survey_entry(self):
        """
        GIVEN a published survey
        WHEN the entry URL is visited with utm_source param
        THEN utm_params are stored in the session
        """
        self.client.get(f'/surveys/{self.survey.uuid}/?utm_source=newsletter&utm_medium=email')
        self.assertIn('utm_params', self.client.session)
        self.assertEqual(self.client.session['utm_params']['utm_source'], 'newsletter')
        self.assertEqual(self.client.session['utm_params']['utm_medium'], 'email')

    def test_utm_appears_in_session_start_event(self):
        """
        GIVEN utm_params stored in session from survey entry
        WHEN the first section is visited (creating session_start event)
        THEN the event metadata contains utm_source
        """
        # Visit entry URL to store UTM, then follow redirect to section
        self.client.get(f'/surveys/{self.survey.uuid}/?utm_source=social&utm_campaign=spring')
        self.client.get(f'/surveys/{self.survey.uuid}/s1/')
        event = SurveyEvent.objects.filter(event_type='session_start').last()
        self.assertIsNotNone(event)
        self.assertEqual(event.metadata.get('utm_source'), 'social')
        self.assertEqual(event.metadata.get('utm_campaign'), 'spring')

    def test_utm_consumed_after_session_start(self):
        """
        GIVEN utm_params stored in session
        WHEN the session_start event fires
        THEN utm_params are removed from the session
        """
        self.client.get(f'/surveys/{self.survey.uuid}/?utm_source=test')
        self.client.get(f'/surveys/{self.survey.uuid}/s1/')
        self.assertNotIn('utm_params', self.client.session)

    def test_no_utm_does_not_break(self):
        """
        GIVEN a request with no UTM params
        WHEN the session_start event fires
        THEN no utm_source in metadata and no error
        """
        self.client.get(f'/surveys/{self.survey.uuid}/s1/')
        event = SurveyEvent.objects.filter(event_type='session_start').last()
        self.assertIsNotNone(event)
        self.assertNotIn('utm_source', event.metadata)


class TrackedLinkModelTest(TestCase):
    """Tests for TrackedLink model."""

    def setUp(self):
        self.org = _make_org('LinkOrg')
        self.survey = SurveyHeader.objects.create(name='linksurvey', organization=self.org)

    def test_build_url_includes_all_params(self):
        """
        GIVEN a TrackedLink with source, medium, campaign
        WHEN build_url is called
        THEN the returned URL contains all three utm params
        """
        link = TrackedLink.objects.create(
            survey=self.survey, utm_source='fb', utm_medium='social', utm_campaign='q1',
        )
        url = link.build_url()
        self.assertIn('utm_source=fb', url)
        self.assertIn('utm_medium=social', url)
        self.assertIn('utm_campaign=q1', url)

    def test_build_url_omits_blank_params(self):
        """
        GIVEN a TrackedLink with only utm_source
        WHEN build_url is called
        THEN the URL contains utm_source but not utm_medium or utm_campaign
        """
        link = TrackedLink.objects.create(
            survey=self.survey, utm_source='direct',
        )
        url = link.build_url()
        self.assertIn('utm_source=direct', url)
        self.assertNotIn('utm_medium', url)
        self.assertNotIn('utm_campaign', url)


class CampaignAnalyticsTest(TestCase):
    """Tests for campaign breakdown analytics."""

    def setUp(self):
        self.org = _make_org('CampOrg')
        self.survey = SurveyHeader.objects.create(name='campsurvey', organization=self.org)
        self.s1 = SurveySession.objects.create(survey=self.survey)
        self.s2 = SurveySession.objects.create(survey=self.survey)
        emit_event(self.s1, 'session_start', {'utm_source': 'newsletter', 'utm_medium': 'email', 'utm_campaign': 'q1'})
        emit_event(self.s2, 'session_start', {'utm_source': 'newsletter', 'utm_medium': 'email', 'utm_campaign': 'q1'})
        emit_event(self.s1, 'survey_complete')

    def test_campaign_groups_by_utm_triple(self):
        """
        GIVEN two sessions with same UTM params, one completed
        WHEN get_campaign_breakdown is called
        THEN one row with started=2, completed=1, rate=50
        """
        svc = PerformanceAnalyticsService(self.survey)
        result = svc.get_campaign_breakdown()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['utm_source'], 'newsletter')
        self.assertEqual(result[0]['started'], 2)
        self.assertEqual(result[0]['completed'], 1)
        self.assertEqual(result[0]['rate'], 50)

    def test_campaign_excludes_non_utm_sessions(self):
        """
        GIVEN a session_start with no utm_source
        WHEN get_campaign_breakdown is called
        THEN that session is excluded
        """
        s3 = SurveySession.objects.create(survey=self.survey)
        emit_event(s3, 'session_start', {'referrer_type': 'direct'})
        svc = PerformanceAnalyticsService(self.survey)
        result = svc.get_campaign_breakdown()
        self.assertEqual(len(result), 1)


class SectionViewHtmxTrackingTest(TestCase):
    """Regression: section_view must fire for HTMX-navigated sections, not only the head."""

    def setUp(self):
        self.org = _make_org("SecTrackOrg")
        self.survey = SurveyHeader.objects.create(name="sec_track", organization=self.org,
                                                  status="published")
        self.s1 = SurveySection.objects.create(name="s1", survey_header=self.survey, is_head=True)
        self.s2 = SurveySection.objects.create(name="s2", survey_header=self.survey)
        self.s1.next_section = self.s2
        self.s1.save()
        self.s2.prev_section = self.s1
        self.s2.save()
        Question.objects.create(name="q1", survey_section=self.s1, input_type="text_line",
                                order_number=1, required=False)
        Question.objects.create(name="q2", survey_section=self.s2, input_type="text_line",
                                order_number=1, required=False)

    def test_htmx_forward_emits_section_view_for_next_section(self):
        """
        GIVEN a two-section survey
        WHEN the head section is viewed then submitted via HTMX (forward)
        THEN section_view is recorded for BOTH the head and the next section
             (before the fix, the next section stayed at 0 views)
        """
        c = Client()
        c.get(f"/surveys/{self.survey.name}/{self.s1.name}/")            # head via GET
        resp = c.post(f"/surveys/{self.survey.name}/{self.s1.name}/",
                      data={}, HTTP_HX_REQUEST="true")                    # submit head via HTMX
        self.assertEqual(resp.status_code, 200)

        viewed = set(SurveyEvent.objects.filter(event_type="section_view")
                     .values_list("metadata__section_name", flat=True))
        submitted = set(SurveyEvent.objects.filter(event_type="section_submit")
                        .values_list("metadata__section_name", flat=True))
        self.assertIn("s1", viewed)
        self.assertIn("s2", viewed)          # the fix: next section now records a view
        self.assertIn("s1", submitted)
