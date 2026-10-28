"""Tests for the `responses-overview` capability (openspec/specs/responses-overview/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, SimpleTestCase, override_settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.urls import reverse
from survey.models import Organization, SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
from survey.analytics import SurveyAnalyticsService
import os
from django.conf import settings as dj_settings
from survey.tests.helpers import _make_org


class ResponsesV2OverviewTest(TestCase):
    """Overview pane: default pane, KPI deltas, feeds, empty/no-geo branches."""

    def setUp(self):
        self.org = _make_org('RespV2OvOrg')
        self.owner = User.objects.create_user('respv2ovowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.client.login(username='respv2ovowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.survey = SurveyHeader.objects.create(
            name='respv2_ov', organization=self.org,
            created_by=self.owner, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.q_text = Question.objects.create(
            survey_section=self.section, name='Comment', code='q1',
            input_type='text', order_number=1,
        )
        self.q_point = Question.objects.create(
            survey_section=self.section, name='Where', code='q2',
            input_type='point', order_number=2,
        )
        self.url = f'/editor/surveys/{self.survey.uuid}/analytics/'

    def _make_session(self, started, with_geo=False, text=None):
        sess = SurveySession.objects.create(survey=self.survey, start_datetime=started)
        if text is not None:
            Answer.objects.create(survey_session=sess, question=self.q_text, text=text)
        if with_geo:
            from django.contrib.gis.geos import Point
            Answer.objects.create(
                survey_session=sess, question=self.q_point, point=Point(74.6, 42.9),
            )
        return sess

    def test_overview_extras_daily_deltas(self):
        """
        GIVEN sessions started yesterday and today (one with a geo answer today)
        WHEN get_overview_extras runs
        THEN responses_today and geo_features_today count only today's activity
        """
        from datetime import timedelta
        from django.utils import timezone as dj_tz
        from survey.analytics import SurveyAnalyticsService
        now = dj_tz.localtime()
        self._make_session(now - timedelta(days=1), with_geo=True, text='old')
        self._make_session(now, with_geo=True, text='fresh')
        extras = SurveyAnalyticsService(self.survey).get_overview_extras()
        self.assertEqual(extras['responses_today'], 1)
        self.assertEqual(extras['geo_features_today'], 1)

    def test_overview_extras_excludes_deleted_sessions(self):
        """
        GIVEN a trashed session from today
        WHEN get_overview_extras runs
        THEN it appears in neither delta nor the latest feed
        """
        from django.utils import timezone as dj_tz
        from survey.analytics import SurveyAnalyticsService
        now = dj_tz.localtime()
        live = self._make_session(now, text='live')
        trashed = self._make_session(now, text='trashed')
        trashed.is_deleted = True
        trashed.save()
        extras = SurveyAnalyticsService(self.survey).get_overview_extras()
        self.assertEqual(extras['responses_today'], 1)
        feed_ids = [item['id'] for item in extras['latest_feed']]
        self.assertIn(live.id, feed_ids)
        self.assertNotIn(trashed.id, feed_ids)

    def test_latest_feed_sequence_and_excerpt(self):
        """
        GIVEN three sessions in start order
        WHEN get_overview_extras runs
        THEN the latest feed is newest-first with per-survey sequence numbers
             and a text excerpt
        """
        from datetime import timedelta
        from django.utils import timezone as dj_tz
        from survey.analytics import SurveyAnalyticsService
        now = dj_tz.localtime()
        self._make_session(now - timedelta(hours=3), text='first')
        self._make_session(now - timedelta(hours=2), text='second')
        self._make_session(now - timedelta(hours=1), text='third')
        extras = SurveyAnalyticsService(self.survey).get_overview_extras()
        feed = extras['latest_feed']
        self.assertEqual([f['seq'] for f in feed], [3, 2, 1])
        self.assertEqual(feed[0]['text_excerpt'], 'third')

    @override_settings(RESPONSES_V2=True)
    def test_overview_renders_by_default_with_kpis(self):
        """
        GIVEN a survey with responses
        WHEN GET the v2 dashboard
        THEN the Overview pane content (KPI strip, latest feed) is rendered
        """
        from django.utils import timezone as dj_tz
        self._make_session(dj_tz.localtime(), with_geo=True, text='hello world')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'rv2-kpi-strip')
        self.assertContains(response, 'rv2-latest')
        self.assertContains(response, 'hello world')

    @override_settings(RESPONSES_V2=True)
    def test_overview_empty_state(self):
        """
        GIVEN a survey with zero sessions
        WHEN GET the v2 dashboard
        THEN the empty state renders instead of zero-filled KPI cards
        """
        response = self.client.get(self.url)
        self.assertContains(response, 'rv2-empty-state')
        self.assertContains(response, 'No responses yet')
        self.assertContains(response, 'Share survey')
        self.assertNotContains(response, 'rv2-kpi-strip')

    @override_settings(RESPONSES_V2=True)
    def test_overview_no_geo_branch(self):
        """
        GIVEN a survey without geo questions but with a response
        WHEN GET the v2 dashboard
        THEN the Overview renders without the map thumbnail block
        """
        from django.utils import timezone as dj_tz
        self.q_point.delete()
        self._make_session(dj_tz.localtime(), text='no geo here')
        response = self.client.get(self.url)
        self.assertContains(response, 'rv2-kpi-strip')
        self.assertNotContains(response, 'id="rv2-ov-map"')
class ResponsesMapEmptyStateTest(TestCase):
    """The empty Responses map tells the two stories apart (bug reported 2026-09-05)."""

    def setUp(self):
        from django.contrib.auth.models import User
        self.org = Organization.objects.create(name="Empty Map Org")
        self.survey = SurveyHeader.objects.create(name="empty_map", organization=self.org, redirect_url="/t/", status='published')
        self.section = SurveySection.objects.create(survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True)
        owner = User.objects.create_user('emptyowner', 'e@example.com', 'pw')
        Membership.objects.create(user=owner, organization=self.org, role='admin')
        self.client.login(username='emptyowner', password='pw')
        self.url = reverse('editor_survey_analytics', kwargs={'survey_uuid': self.survey.uuid})

    def test_geo_question_without_answers(self):
        """
        GIVEN a survey with a point question and no answers
        WHEN the owner opens Responses
        THEN the map pane says there are no map answers yet, not that there are no geo questions
        """
        Question.objects.create(survey_section=self.section, code="Q1", name="Where?", input_type="point", order_number=1)
        html = self.client.get(self.url).content.decode()
        self.assertIn('No map answers yet', html)
        self.assertNotIn('No geo questions in this survey', html)

    def test_no_geo_question(self):
        """
        GIVEN a survey without any geo question
        WHEN the owner opens Responses
        THEN the map pane says there are no geo questions and offers to add one
        """
        Question.objects.create(survey_section=self.section, code="T1", name="Text", input_type="text", order_number=1)
        html = self.client.get(self.url).content.decode()
        self.assertIn('No geo questions in this survey', html)
        self.assertIn('Add a map question', html)


class EditorMapSizingGuardTest(SimpleTestCase):
    """Guards for the Overview thumbnail that stayed on the world view (landing-showcase-refresh)."""

    def _read(self, *parts):
        import os
        from django.conf import settings as dj_settings
        with open(os.path.join(dj_settings.BASE_DIR, *parts), encoding='utf-8') as fh:
            return fh.read()

    def test_has_size_measures_the_container(self):
        """
        GIVEN editor_map.js
        WHEN hasSize decides whether a map can draw
        THEN it reads the container's size, never Leaflet's size cached at construction
        """
        js = self._read('survey', 'assets', 'js', 'editor_map.js')
        body = js[js.index('function hasSize'):js.index('function whenSized')]
        code = '\n'.join(l for l in body.splitlines() if not l.strip().startswith('//'))
        self.assertIn('clientWidth', code)
        self.assertNotIn('getSize()', code)

    def test_overview_start_view_is_not_set_after_mount(self):
        """
        GIVEN the Overview pane script
        WHEN the thumbnail map is mounted
        THEN its world view is a construction option, and no setView follows mount()
        """
        tpl = self._read('survey', 'templates', 'editor', 'partials', 'analytics_overview_pane.html')
        self.assertIn('center: [0, 0], zoom: 2', tpl)
        self.assertNotIn('m.setView(', tpl)
