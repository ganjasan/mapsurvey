"""Tests for the `responses-required-unanswered` capability
(openspec/specs/responses-required-unanswered/spec.md, change responses-required-unanswered, #691).

One stored definition of "required questions unanswered" / "completed", the triggers that keep
it current, the quiet marker and filter on Responses, and the signals that were removed.
"""
import json

from django.contrib.auth.models import User
from django.contrib.gis.geos import Point, Polygon
from django.test import TestCase
from django.utils import timezone

from survey import required_state
from survey.analytics import SurveyAnalyticsService, completed_session_filter, family_completion_counts
from survey.models import (
    Answer, Membership, Question, QuestionGroup, SurveyEvent, SurveyHeader, SurveySection, SurveySession,
)
from survey.tests.helpers import _make_org, _objects_layer


class _RequiredFixture(TestCase):
    """A published three-page survey: page 1 asks "Who are you?" (choice, required) and
    "Your name" (required text); page 2 asks "How often?" (optional number); page 3 asks
    "Anything else?" (required text)."""

    def setUp(self):
        self.org = _make_org('ReqOrg')
        self.owner = User.objects.create_user('reqowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.client.login(username='reqowner', password='pass')
        s = self.client.session
        s['active_org_id'] = self.org.id
        s.save()
        self.survey = SurveyHeader.objects.create(
            name='req_survey', organization=self.org, created_by=self.owner,
            status='published', redirect_url='#',
        )
        self.s1 = SurveySection.objects.create(survey_header=self.survey, name='p1', title='P1', code='P1', is_head=True)
        self.s2 = SurveySection.objects.create(survey_header=self.survey, name='p2', title='P2', code='P2')
        self.s3 = SurveySection.objects.create(survey_header=self.survey, name='p3', title='P3', code='P3')
        self.s1.next_section = self.s2
        self.s1.save()
        self.s2.next_section = self.s3
        self.s2.save()
        self.q_who = Question.objects.create(
            survey_section=self.s1, name='Who are you?', code='WHO', input_type='choice', order_number=1,
            required=True, choices=[{'code': 1, 'name': 'Cyclist'}, {'code': 2, 'name': 'Driver'}],
        )
        self.q_name = Question.objects.create(
            survey_section=self.s1, name='Your name', code='NAME', input_type='text', order_number=2, required=True,
        )
        self.q_often = Question.objects.create(
            survey_section=self.s2, name='How often?', code='OFTEN', input_type='number', order_number=1,
        )
        self.q_else = Question.objects.create(
            survey_section=self.s3, name='Anything else?', code='ELSE', input_type='text', order_number=1, required=True,
        )
        self._clock = timezone.now() - timezone.timedelta(days=1)

    def _session(self, **kwargs):
        self._clock += timezone.timedelta(minutes=1)
        kwargs.setdefault('start_datetime', self._clock)
        return SurveySession.objects.create(survey=self.survey, **kwargs)

    def _answer(self, session, question, **values):
        return Answer.objects.create(survey_session=session, question=question, **values)

    def _full(self, session):
        self._answer(session, self.q_who, selected_choices=[1])
        self._answer(session, self.q_name, text='Ann')
        self._answer(session, self.q_else, text='No')
        return session

    def _refreshed(self, session):
        required_state.refresh(session)
        session.refresh_from_db()
        return session


class MissingRequiredRulesTest(_RequiredFixture):
    """The rules of the one definition."""

    def test_required_question_on_a_later_page_never_reached(self):
        """
        GIVEN a respondent who answered page 1 and left
        WHEN the state is computed
        THEN the required question on page 3 is missing and the session is not completed
        """
        s = self._session()
        self._answer(s, self.q_who, selected_choices=[1])
        self._answer(s, self.q_name, text='Ann')
        s = self._refreshed(s)
        self.assertEqual(s.required_missing, ['ELSE'])
        self.assertFalse(s.required_complete)

    def test_optional_page_skipped_is_complete(self):
        """
        GIVEN every required question answered and the optional page 2 skipped
        WHEN the state is computed
        THEN nothing is missing
        """
        s = self._refreshed(self._full(self._session()))
        self.assertEqual(s.required_missing, [])
        self.assertTrue(s.required_complete)

    def test_missing_codes_follow_survey_order(self):
        """
        GIVEN a session with only page 2 answered
        WHEN the state is computed
        THEN the missing codes are listed in survey order
        """
        s = self._session()
        self._answer(s, self.q_often, numeric=3)
        self.assertEqual(required_state.missing_required(s), ['WHO', 'NAME', 'ELSE'])

    def test_question_hidden_by_its_rule_is_not_missing(self):
        """
        GIVEN a required question shown only to cyclists
        WHEN a driver's session is judged
        THEN that question is not missing; a cyclist without it misses it
        """
        bike = Question.objects.create(
            survey_section=self.s1, name='Your bike', code='BIKE', input_type='text', order_number=3,
            required=True, visibility_rule={'question_code': 'WHO', 'choice_codes': [1]},
        )
        driver = self._session()
        self._answer(driver, self.q_who, selected_choices=[2])
        self._answer(driver, self.q_name, text='Bo')
        self._answer(driver, self.q_else, text='-')
        self.assertEqual(required_state.missing_required(driver), [])
        cyclist = self._full(self._session())
        self.assertEqual(required_state.missing_required(cyclist), [bike.code])

    def test_hidden_section_holds_no_missing_question(self):
        """
        GIVEN page 3 shown only to cyclists
        WHEN a driver's session without page 3 is judged
        THEN page 3's required question is not missing
        """
        self.s3.visibility_rule = {'question_code': 'WHO', 'choice_codes': [1]}
        self.s3.save()
        driver = self._session()
        self._answer(driver, self.q_who, selected_choices=[2])
        self._answer(driver, self.q_name, text='Bo')
        self.assertEqual(required_state.missing_required(driver), [])

    def test_group_rule_hides_its_members(self):
        """
        GIVEN a group on page 1 shown only to cyclists, holding a required question
        WHEN a driver's session is judged
        THEN the member is not missing
        """
        group = QuestionGroup.objects.create(
            survey_section=self.s1, title='Bikes', order_number=3,
            visibility_rule={'question_code': 'WHO', 'choice_codes': [1]},
        )
        Question.objects.create(
            survey_section=self.s1, name='Gears', code='GEARS', input_type='text', order_number=4,
            required=True, group=group,
        )
        driver = self._session()
        self._answer(driver, self.q_who, selected_choices=[2])
        self._answer(driver, self.q_name, text='Bo')
        self._answer(driver, self.q_else, text='-')
        self.assertEqual(required_state.missing_required(driver), [])

    def test_operator_only_question_counts_for_paper_sessions_only(self):
        """
        GIVEN a required question shown to operators only
        WHEN an online session and a paper session, both without it, are judged
        THEN it is missing for the paper session and not for the online one
        """
        Question.objects.create(
            survey_section=self.s1, name='Sheet checked by', code='CHECKED', input_type='text', order_number=3,
            required=True, audience='operators',
        )
        online = self._full(self._session())
        paper = self._full(self._session(source=SurveySession.SOURCE_PAPER))
        self.assertEqual(required_state.missing_required(online), [])
        self.assertEqual(required_state.missing_required(paper), ['CHECKED'])

    def test_geo_minimum(self):
        """
        GIVEN a required point question asking for at least 3 places
        WHEN a session placed 2, and another placed 3
        THEN it is missing for the first only
        """
        where = Question.objects.create(
            survey_section=self.s2, name='Where?', code='WHERE', input_type='point', order_number=2,
            required=True, validation_settings={'min_features': 3},
        )
        two = self._full(self._session())
        three = self._full(self._session())
        for _ in range(2):
            self._answer(two, where, point=Point(74.6, 42.9))
        for _ in range(3):
            self._answer(three, where, point=Point(74.6, 42.9))
        self.assertEqual(required_state.missing_required(two), ['WHERE'])
        self.assertEqual(required_state.missing_required(three), [])

    def test_objects_minimum(self):
        """
        GIVEN an "Objects on the map" question asking about at least 2 objects
        WHEN a session answered about 1 object
        THEN it is missing; about 2 objects, it is not
        """
        layer = _objects_layer(self.survey)
        objects_q = Question.objects.create(
            survey_section=self.s2, name='Rate zones', code='ZONES', input_type='layer_objects', order_number=3,
            layer=layer, min_objects=2,
        )
        rate = Question.objects.create(
            survey_section=self.s2, name='Like it?', code='ZONES_LIKE', input_type='thumbs', order_number=1,
            parent_question_id=objects_q,
        )
        first, second = list(layer.items.all()[:2])
        one = self._full(self._session())
        self._answer(one, rate, layer_object=first, selected_choices=[1])
        self.assertEqual(required_state.missing_required(one), ['ZONES'])
        self._answer(one, rate, layer_object=second, selected_choices=[0])
        self.assertEqual(required_state.missing_required(one), [])

    def test_blank_row_left_by_inline_editing_does_not_count(self):
        """
        GIVEN a required text answer cleared to '' (the row stays)
        WHEN the state is computed
        THEN the question is missing
        """
        s = self._full(self._session())
        Answer.objects.filter(survey_session=s, question=self.q_name).update(text='')
        self.assertEqual(required_state.missing_required(s), ['NAME'])

    def test_html_and_image_blocks_are_never_required(self):
        """
        GIVEN a Formatted Text block stored with required=True
        WHEN a full session is judged
        THEN nothing is missing
        """
        Question.objects.create(
            survey_section=self.s1, name='Intro', code='INTRO', input_type='html', order_number=0, required=True,
        )
        self.assertEqual(required_state.missing_required(self._full(self._session())), [])

    def test_no_required_questions_means_every_answered_session_completes(self):
        """
        GIVEN a survey with no required questions and 4 answered sessions
        WHEN the sessions are recomputed
        THEN all 4 are completed
        """
        Question.objects.filter(survey_section__survey_header=self.survey).update(required=False)
        for _ in range(4):
            self._answer(self._session(), self.q_often, numeric=1)
        required_state.refresh_many(SurveySession.objects.filter(survey=self.survey))
        self.assertEqual(completed_session_filter(SurveySession.objects.filter(survey=self.survey)).count(), 4)

    def test_empty_session_is_never_completed(self):
        """
        GIVEN an empty session (nothing answered)
        WHEN completed sessions are counted
        THEN it is not among them, whatever its stored flag says
        """
        self._session()
        self.assertEqual(completed_session_filter(SurveySession.objects.filter(survey=self.survey)).count(), 0)

    def test_refresh_many_writes_every_session_of_many_headers(self):
        """
        GIVEN sessions on two surveys, one missing a required question
        WHEN refresh_many runs over all of them
        THEN each session's state is written and empty sessions are skipped
        """
        full = self._full(self._session())
        partial = self._session()
        self._answer(partial, self.q_who, selected_choices=[1])
        other = SurveyHeader.objects.create(name='req_other', organization=self.org)
        sec = SurveySection.objects.create(survey_header=other, name='o', title='O', code='O', is_head=True)
        oq = Question.objects.create(survey_section=sec, name='X', code='OX', input_type='text', order_number=1)
        o_sess = SurveySession.objects.create(survey=other)
        Answer.objects.create(survey_session=o_sess, question=oq, text='x')
        self._session()  # empty
        written = required_state.refresh_many(SurveySession.objects.all())
        self.assertEqual(written, 3)
        partial.refresh_from_db()
        self.assertEqual(partial.required_missing, ['NAME', 'ELSE'])
        full.refresh_from_db()
        self.assertTrue(full.required_complete)


class RequiredStateTriggersTest(_RequiredFixture):
    """The stored state follows every write that can change it."""

    def test_section_post_stores_the_state(self):
        """
        GIVEN a respondent on page 1
        WHEN they submit page 1 with both answers
        THEN their session misses only page 3's question
        """
        self.client.get(f'/surveys/{self.survey.uuid}/p1/')
        self.client.post(f'/surveys/{self.survey.uuid}/p1/', {'WHO': '1', 'NAME': 'Ann'})
        session = SurveySession.objects.get(pk=self.client.session['survey_session_id'])
        self.assertEqual(session.required_missing, ['ELSE'])
        self.assertFalse(session.required_complete)

    def test_resubmitting_a_page_without_an_answer_recomputes(self):
        """
        GIVEN a respondent who answered every required question
        WHEN they go back to page 1 and submit it with the name cleared
        THEN the session shows the name as missing
        """
        self.client.get(f'/surveys/{self.survey.uuid}/p1/')
        self.client.post(f'/surveys/{self.survey.uuid}/p1/', {'WHO': '1', 'NAME': 'Ann'})
        self.client.post(f'/surveys/{self.survey.uuid}/p3/', {'ELSE': 'no'})
        session = SurveySession.objects.get(pk=self.client.session['survey_session_id'])
        self.assertTrue(session.required_complete)
        self.client.post(f'/surveys/{self.survey.uuid}/p1/', {'WHO': '1', 'NAME': ''})
        session.refresh_from_db()
        self.assertEqual(session.required_missing, ['NAME'])

    def test_inline_answer_edit_recomputes(self):
        """
        GIVEN a completed session
        WHEN the creator clears its required text answer inline on Responses
        THEN the question becomes missing
        """
        s = self._refreshed(self._full(self._session()))
        url = f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{s.id}/answers/{self.q_name.id}/edit/'
        resp = self.client.post(url, json.dumps({'value': ''}), content_type='application/json')
        self.assertEqual(resp.status_code, 204)
        s.refresh_from_db()
        self.assertEqual(s.required_missing, ['NAME'])

    def test_ticking_required_on_a_live_survey_recomputes_every_session(self):
        """
        GIVEN a published survey whose 3 sessions are all complete, 2 of them without "How often?"
        WHEN the creator ticks Required on "How often?"
        THEN 1 session is completed and 2 show the question as missing
        """
        from survey.services import questions as question_service
        from survey.services.context import Actor
        sessions = [self._full(self._session()) for _ in range(3)]
        self._answer(sessions[0], self.q_often, numeric=2)
        required_state.refresh_many(SurveySession.objects.filter(survey=self.survey))
        qs = SurveySession.objects.filter(survey=self.survey)
        self.assertEqual(completed_session_filter(qs).count(), 3)
        with self.captureOnCommitCallbacks(execute=True):
            question_service.update(Actor(user=self.owner), self.q_often,
                                    {'required': True}, partial=True)
        self.assertEqual(completed_session_filter(qs).count(), 1)
        sessions[1].refresh_from_db()
        self.assertEqual(sessions[1].required_missing, ['OFTEN'])

    def test_survey_refresh_goes_to_the_worker_above_the_sync_limit(self):
        """
        GIVEN a survey with more non-empty sessions than the in-request limit
        WHEN a survey-wide recompute is scheduled and the broker refuses the task
        THEN it runs inline anyway, so no state is left stale
        """
        from unittest import mock
        s = self._full(self._session())
        SurveySession.objects.filter(pk=s.pk).update(required_complete=False, required_missing=['X'])
        with mock.patch.object(required_state, 'SYNC_LIMIT', 0), \
                mock.patch('survey.tasks.recompute_required_state.delay', side_effect=OSError('no broker')):
            with self.captureOnCommitCallbacks(execute=True):
                required_state.schedule_survey_refresh(self.survey.id)
        s.refresh_from_db()
        self.assertTrue(s.required_complete)

    def test_publishing_keeps_old_sessions_state(self):
        """
        GIVEN a session answered on v1 and a draft that adds a required question
        WHEN the draft is published
        THEN the old session keeps its state, judged against the version it answered
        """
        from survey.versioning import clone_survey_for_draft, publish_draft
        s = self._refreshed(self._full(self._session()))
        draft = clone_survey_for_draft(self.survey)
        sec = draft.surveysection_set.get(code='P2')
        Question.objects.create(survey_section=sec, name='Postcode', code='POST', input_type='text',
                                order_number=5, required=True)
        publish_draft(draft, force=True)
        s.refresh_from_db()
        self.assertTrue(s.required_complete)
        self.assertEqual(s.required_missing, [])


class CompletionAgreementTest(_RequiredFixture):
    """Every surface that says "completed" reads the one stored state."""

    def setUp(self):
        super().setUp()
        for _ in range(3):
            self._full(self._session())
        for _ in range(2):
            self._answer(self._session(), self.q_often, numeric=1)
        required_state.refresh_many(SurveySession.objects.filter(survey=self.survey))

    def test_overview_chip_export_and_api_agree(self):
        """
        GIVEN 5 answered sessions, 3 with every required question answered
        WHEN the Overview, the Complete chip, completed_only export and the API summary count
        THEN each says 3 (60 %)
        """
        from api.v1.responses import build_summary
        from survey.export import excluded_sessions, version_parts
        from survey.response_scope import responses_scope
        service = SurveyAnalyticsService(self.survey)
        overview = service.get_overview()
        self.assertEqual((overview['completed_count'], overview['completion_rate']), (3, 60))
        table = SurveyAnalyticsService(self.survey, include_empty=False).get_table_page(v2=True)
        self.assertEqual(table['v2_counts']['complete'], 3)
        self.assertEqual(table['v2_counts']['required'], 2)
        parts = version_parts(self.survey, None)
        every = SurveySession.objects.filter(survey=self.survey).count()
        self.assertEqual(every - len(excluded_sessions(parts, False, True)), 3)
        summary = build_summary(self.survey, responses_scope(self.survey))
        self.assertEqual((summary['completed'], summary['completion_rate']), (3, 60))

    def test_dashboard_card_matches_overview(self):
        """
        GIVEN the same survey
        WHEN the dashboard card numbers are computed
        THEN completed equals the Overview's
        """
        total, completed = family_completion_counts([self.survey])[self.survey.id]
        self.assertEqual(completed, SurveyAnalyticsService(self.survey).get_overview()['completed_count'])
        self.assertEqual(completed, 3)


class RequiredMarkerTest(_RequiredFixture):
    """The quiet marker, its tooltip and the one filter."""

    def setUp(self):
        super().setUp()
        self.full = self._refreshed(self._full(self._session()))
        self.partial = self._session()
        self._answer(self.partial, self.q_who, selected_choices=[1])
        self.partial = self._refreshed(self.partial)
        self.table_url = f'/editor/surveys/{self.survey.uuid}/analytics/table/'

    def test_tooltip_names_the_unanswered_questions(self):
        """
        GIVEN a session that missed "Your name" and "Anything else?"
        WHEN the Responses table renders
        THEN its marker's tooltip names both, in plain words
        """
        html = self.client.get(self.table_url).content.decode()
        self.assertIn('data-testid="required-mark"', html)
        self.assertIn("Didn't answer 2 required questions: Your name, Anything else?", html)

    def test_marker_carries_no_issue_wording_or_error_colour(self):
        """
        GIVEN the same table
        WHEN it renders
        THEN there is no Issues chip, no violation wording and no red badge on the marker
        """
        html = self.client.get(self.table_url).content.decode()
        self.assertNotIn('rv2-chip-issues', html)
        self.assertNotIn('Violations', html)
        self.assertNotIn('Missing req.', html)

    def test_filter_returns_exactly_the_marked_sessions(self):
        """
        GIVEN one complete and one partial session
        WHEN the table is filtered with required=missing, then required=complete
        THEN it lists only the partial session, then only the complete one
        """
        missing = SurveyAnalyticsService(self.survey, include_empty=False).get_table_page(
            v2=True, required_filter='missing')
        self.assertEqual([r['session_id'] for r in missing['rows']], [self.partial.id])
        self.assertEqual(missing['v2_counts']['required'], 1)
        complete = SurveyAnalyticsService(self.survey, include_empty=False).get_table_page(
            v2=True, required_filter='complete')
        self.assertEqual([r['session_id'] for r in complete['rows']], [self.full.id])

    def test_old_issues_parameter_is_ignored(self):
        """
        GIVEN an old link with issues=duplicate
        WHEN the table loads
        THEN every row is listed
        """
        resp = self.client.get(self.table_url + '?issues=duplicate')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['total'], 2)

    def test_marker_column_sorts_by_number_missing(self):
        """
        GIVEN the two sessions
        WHEN the table is sorted by the Required column, descending
        THEN the partial session comes first
        """
        page = SurveyAnalyticsService(self.survey, include_empty=False).get_table_page(
            v2=True, sort_col='required', sort_dir='desc')
        self.assertEqual(page['rows'][0]['session_id'], self.partial.id)

    def test_crossed_polygon_gets_the_quiet_note(self):
        """
        GIVEN a session that drew a bow-tie polygon
        WHEN the table renders
        THEN that cell carries the crossed-edges tooltip, and a short text answer carries none
        """
        area = Question.objects.create(
            survey_section=self.s2, name='Area', code='AREA', input_type='polygon', order_number=2,
        )
        bowtie = Polygon(((0, 0), (1, 1), (1, 0), (0, 1), (0, 0)))
        self._answer(self.full, area, polygon=bowtie)
        Answer.objects.filter(survey_session=self.full, question=self.q_else).update(text='ok')
        html = self.client.get(self.table_url).content.decode()
        self.assertIn('The edges of this shape cross each other. It may not open correctly in GIS software.', html)
        self.assertNotIn('suspiciously short', html)


class RemovedSignalsTest(_RequiredFixture):
    """Duplicate, fast and last-section "incomplete" are gone, with their settings."""

    def test_same_user_agent_sessions_carry_no_mark(self):
        """
        GIVEN two complete sessions started ten minutes apart from the same User-Agent
        WHEN the table is computed
        THEN neither carries a mark and both count as completed
        """
        ua = 'Mozilla/5.0 (Linux; Android 10; K) Chrome/120 Mobile'
        a = self._refreshed(self._full(self._session()))
        b = self._refreshed(self._full(self._session()))
        now = timezone.now()
        SurveyEvent.objects.create(session=a, event_type='session_start', created_at=now, metadata={'user_agent': ua})
        SurveyEvent.objects.create(session=b, event_type='session_start', created_at=now + timezone.timedelta(minutes=10),
                                   metadata={'user_agent': ua})
        page = SurveyAnalyticsService(self.survey, include_empty=False).get_table_page(v2=True)
        self.assertTrue(all(not r['required'] and not r['lints'] for r in page['rows']))
        self.assertEqual(page['v2_counts']['complete'], 2)

    def test_validation_settings_endpoint_is_gone(self):
        """
        GIVEN the old validation-settings URL
        WHEN it is requested
        THEN it does not exist
        """
        resp = self.client.get(f'/editor/surveys/{self.survey.uuid}/analytics/validation-settings/')
        self.assertEqual(resp.status_code, 404)

    def test_overview_has_no_flagged_tile_or_needs_review(self):
        """
        GIVEN a survey with a partial session
        WHEN the Responses page renders
        THEN there is no flagged KPI, no Responses-tab badge and no Needs review block
        """
        s = self._session()
        self._answer(s, self.q_who, selected_choices=[1])
        self._refreshed(s)
        html = self.client.get(f'/editor/surveys/{self.survey.uuid}/analytics/').content.decode()
        self.assertNotIn('rv2-needs-review', html)
        self.assertNotIn('rv2-responses-badge', html)
        self.assertNotIn('rv2-flag', html)
        self.assertNotIn('validationSettingsModal', html)

    def test_bulk_delete_asks_with_the_count_in_the_app_dialog(self):
        """
        GIVEN the Responses page
        WHEN its bulk-action script renders
        THEN trash and permanent delete ask through the app's dialog with the number of responses
        """
        html = self.client.get(f'/editor/surveys/{self.survey.uuid}/analytics/').content.decode()
        self.assertIn('Move __N__ responses to trash? You can restore them from the trash.', html)
        self.assertIn('Permanently delete __N__ responses? This cannot be undone.', html)
        self.assertIn('window.Dialog.confirm', html)
        self.assertNotIn("if (confirmMsg && !confirm(confirmMsg))", html)
