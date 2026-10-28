"""Tests for the `responses-navigation` capability (openspec/specs/responses-navigation/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
from survey.models import SurveyEvent
from survey.tests.helpers import _make_org


class ResponsesV2SwitchTest(TestCase):
    """RESPONSES_V2 kill switch selects between legacy and v2 Responses templates."""

    def setUp(self):
        self.org = _make_org('RespV2Org')
        self.owner = User.objects.create_user('respv2owner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.client.login(username='respv2owner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.survey = SurveyHeader.objects.create(
            name='respv2_test', organization=self.org,
            created_by=self.owner, status='published',
        )
        section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        Question.objects.create(
            survey_section=section, name='Q1', code='q1',
            input_type='text', order_number=1,
        )
        self.url = f'/editor/surveys/{self.survey.uuid}/analytics/'

    @override_settings(RESPONSES_V2=False)
    def test_switch_off_serves_legacy_template(self):
        """
        GIVEN RESPONSES_V2 is off
        WHEN GET the analytics dashboard
        THEN the legacy template renders with its original navigation markup
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'editor/analytics_dashboard.html')
        # Legacy navigation markers: Data/Performance sub-tabs + split-pane engine
        self.assertContains(response, 'switchAnalyticsTab')
        self.assertContains(response, 'pane-data')
        self.assertNotContains(response, 'rv2-panerow')

    @override_settings(RESPONSES_V2=True)
    def test_switch_on_serves_v2_template(self):
        """
        GIVEN RESPONSES_V2 is on
        WHEN GET the analytics dashboard
        THEN the v2 template renders the flat pane row and no legacy sub-tab row
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'editor/analytics_dashboard_v2.html')
        self.assertContains(response, 'rv2-panerow')
        # The five flat panes exist as containers
        for pane in ('overview', 'map', 'responses', 'charts', 'performance'):
            self.assertContains(response, f'data-pane-content="{pane}"')
        # The stacked navigation must not come along
        self.assertNotContains(response, 'switchAnalyticsTab')
        self.assertNotContains(response, '_renderTree')


@override_settings(RESPONSES_V2=True)
class ResponsesV2NavigationTest(TestCase):
    """Flat pane set: badge, deep links, Performance honesty (tracked labels)."""

    def setUp(self):
        self.org = _make_org('RespV2NavOrg')
        self.owner = User.objects.create_user('respv2navowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.client.login(username='respv2navowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.survey = SurveyHeader.objects.create(
            name='respv2_nav', organization=self.org,
            created_by=self.owner, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.q = Question.objects.create(
            survey_section=self.section, name='Q1', code='q1',
            input_type='text', order_number=1,
        )
        self.url = f'/editor/surveys/{self.survey.uuid}/analytics/'

    def test_violations_badge_on_responses_pane_item(self):
        """
        GIVEN a survey with one empty (flagged) session and empty sessions shown
        WHEN GET the v2 dashboard
        THEN the Responses pane item carries the violations badge
        """
        SurveySession.objects.create(survey=self.survey)  # no answers → 'empty'
        self.client.cookies['rv2_show_empty'] = '1'
        response = self.client.get(self.url)
        self.assertContains(response, 'rv2-responses-badge')

    def test_no_badge_without_violations(self):
        """
        GIVEN a survey whose only session is clean
        WHEN GET the v2 dashboard
        THEN no violations badge renders
        """
        sess = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=sess, question=self.q, text='fine')
        response = self.client.get(self.url)
        self.assertNotContains(response, 'rv2-responses-badge')

    def test_traffic_sources_deep_link_survives(self):
        """
        GIVEN the Share page links to #traffic-sources
        WHEN the v2 dashboard renders
        THEN the router maps that anchor to the Performance pane
        """
        response = self.client.get(self.url)
        self.assertContains(response, "'traffic-sources': 'performance'")

    def test_performance_kpis_labeled_as_tracked(self):
        """
        GIVEN a survey with one tracked session event
        WHEN GET the v2 dashboard
        THEN Performance KPIs are labeled as tracked-visit metrics
        """
        sess = SurveySession.objects.create(survey=self.survey)
        SurveyEvent.objects.create(session=sess, event_type='session_start')
        response = self.client.get(self.url)
        self.assertContains(response, 'tracked visits')

    def test_funnel_renders_step_columns_without_chartjs_canvas(self):
        """
        GIVEN two started sessions of which one viewed the head section
        WHEN GET the dashboard
        THEN the Performance pane has one .perf-funnel-step with a 50% fill and no funnelChart canvas
        """
        for viewed in (True, False):
            sess = SurveySession.objects.create(survey=self.survey)
            SurveyEvent.objects.create(session=sess, event_type='session_start')
            if viewed:
                SurveyEvent.objects.create(
                    session=sess, event_type='section_view',
                    metadata={'section_name': self.section.name},
                )
        response = self.client.get(self.url)
        html = response.content.decode()
        self.assertEqual(html.count('class="perf-funnel-step"'), 1)
        self.assertIn('class="perf-funnel-fill" style="height:50%;--reached:50%;"', html)
        self.assertContains(response, '1 reached')
        self.assertContains(response, '1 dropped')
        self.assertNotIn('funnelChart', html)

    def _branch_pane(self, viewed_c=None, rule=None, starts=25):
        """A → B (shown when Q = Yes) → C; 25 tracked sessions so rates are not gated."""
        b = SurveySection.objects.create(survey_header=self.survey, name='s2', code='S2')
        c = SurveySection.objects.create(survey_header=self.survey, name='s3', code='S3')
        self.section.next_section = b
        self.section.save()
        b.next_section = c
        b.save()
        q = Question.objects.create(
            survey_section=self.section, name='Show B?', code='q_show_b', input_type='choice',
            order_number=2, choices=[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}],
        )
        b.visibility_rule = rule if rule is not None else {"question_code": "q_show_b", "choice_codes": [1]}
        b.save()
        yes = starts - 5  # 5 sessions skipped by the rule = 20% of 25 starts
        for i in range(starts):
            sess = SurveySession.objects.create(survey=self.survey)
            SurveyEvent.objects.create(session=sess, event_type='session_start')
            SurveyEvent.objects.create(session=sess, event_type='section_view', metadata={'section_name': 's1'})
            Answer.objects.create(survey_session=sess, question=q, selected_choices=[1 if i < yes else 2])
            if i < yes:
                SurveyEvent.objects.create(session=sess, event_type='section_view', metadata={'section_name': 's2'})
            if viewed_c is not None and i < viewed_c:
                SurveyEvent.objects.create(session=sess, event_type='section_view', metadata={'section_name': 's3'})

    def test_funnel_conditional_step_markup(self):
        """
        GIVEN section B behind a valid rule that skipped 5 of 25 sessions
        WHEN GET the dashboard
        THEN B's column is .is-conditional with a 'Shown when' badge, a 20% skipped band,
             a 'skipped by rule' line, no dropped line, and the legend is rendered
        """
        self._branch_pane()
        html = self.client.get(self.url).content.decode()
        self.assertEqual(html.count('class="perf-funnel-step is-conditional"'), 1)
        self.assertIn('Shown when Show B? = Yes', html)
        self.assertIn('class="perf-funnel-skipped" style="bottom:80%;height:20%;--skipped:20%;"', html)
        self.assertIn('5 skipped by rule', html)
        column_b = html.split('class="perf-funnel-step is-conditional"')[1].split('class="perf-funnel-step"')[0]
        self.assertNotIn('dropped', column_b)
        self.assertIn('class="perf-funnel-legend"', html)
        self.assertIn('100% of the 20 eligible', html)

    def test_funnel_successor_caption_names_the_baseline(self):
        """
        GIVEN A → conditional B → C where C is reached by 23 of the 25 who saw A
        WHEN GET the dashboard
        THEN C's dropped line says 'since step 1'
        """
        self._branch_pane(viewed_c=23)
        html = self.client.get(self.url).content.decode()
        self.assertIn('2 dropped', html)
        self.assertIn('since step 1', html)

    def test_funnel_broken_rule_badge(self):
        """
        GIVEN section B whose rule points at a missing question
        WHEN GET the dashboard
        THEN B carries the warning badge, is not conditional, and has no skipped band
        """
        self._branch_pane(rule={"question_code": "gone", "choice_codes": [1]})
        html = self.client.get(self.url).content.decode()
        self.assertIn('Rule broken', html)
        self.assertIn('controlling question not found', html)
        self.assertNotIn('class="perf-funnel-step is-conditional"', html)
        self.assertNotIn('class="perf-funnel-skipped"', html)

    def test_small_sample_funnel_notice(self):
        """
        GIVEN fewer than 20 tracked sessions with section views
        WHEN GET the v2 dashboard
        THEN the funnel shows the small-sample notice instead of drop alarms
        """
        sess = SurveySession.objects.create(survey=self.survey)
        SurveyEvent.objects.create(session=sess, event_type='session_start')
        SurveyEvent.objects.create(
            session=sess, event_type='section_view',
            metadata={'section_name': self.section.name},
        )
        response = self.client.get(self.url)
        self.assertContains(response, 'perf-small-sample')
        self.assertContains(response, 'Sample too small')


class ResponsesV2MobileTest(TestCase):
    """Mobile tier: bottom bar vocabulary, phone card list."""

    def setUp(self):
        self.org = _make_org('RespV2MobOrg')
        self.owner = User.objects.create_user('respv2mobowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.client.login(username='respv2mobowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.survey = SurveyHeader.objects.create(
            name='respv2_mob', organization=self.org,
            created_by=self.owner, status='published',
        )
        section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        q = Question.objects.create(
            survey_section=section, name='Q1', code='q1',
            input_type='text', order_number=1,
        )
        sess = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=sess, question=q, text='card text here')
        self.dash_url = f'/editor/surveys/{self.survey.uuid}/analytics/'
        self.table_url = f'/editor/surveys/{self.survey.uuid}/analytics/table/'

    @override_settings(RESPONSES_V2=True, MOBILE_EDITOR_NAV=True)
    def test_v2_bottom_bar_vocabulary(self):
        """
        GIVEN the v2 switch and mobile nav are on
        WHEN GET the dashboard
        THEN the bottom bar carries Overview/Map/Responses/Perf and no Table
             or Charts items
        """
        response = self.client.get(self.dash_url)
        content = response.content.decode()
        bar = content[content.index('mobile-tabbar'):]
        self.assertIn('data-pane="overview"', bar)
        self.assertIn('data-pane="responses"', bar)
        self.assertIn('data-pane="performance"', bar)
        self.assertNotIn('data-pane="table"', bar)
        self.assertNotIn('data-pane="charts"', bar)

    @override_settings(RESPONSES_V2=False, MOBILE_EDITOR_NAV=True)
    def test_legacy_bottom_bar_unchanged(self):
        """
        GIVEN the v2 switch is off
        WHEN GET the dashboard
        THEN the bottom bar keeps the legacy Table/Map/Charts/Perf items
        """
        response = self.client.get(self.dash_url)
        content = response.content.decode()
        bar = content[content.index('mobile-tabbar'):]
        self.assertIn('data-pane="table"', bar)
        self.assertIn('data-pane="charts"', bar)
        self.assertNotIn('data-pane="overview"', bar)

    @override_settings(RESPONSES_V2=True)
    def test_phone_card_list_renders_rows(self):
        """
        GIVEN the v2 switch is on
        WHEN GET the table partial
        THEN the phone card list renders the same rows as the grid
        """
        response = self.client.get(self.table_url)
        self.assertContains(response, 'rv2-mcards')
        self.assertContains(response, 'rv2-mcard')
        self.assertContains(response, 'card text here')

    @override_settings(RESPONSES_V2=False)
    def test_legacy_table_has_no_card_list(self):
        """
        GIVEN the v2 switch is off
        WHEN GET the table partial
        THEN no card list markup ships
        """
        response = self.client.get(self.table_url)
        self.assertNotContains(response, 'rv2-mcards')
