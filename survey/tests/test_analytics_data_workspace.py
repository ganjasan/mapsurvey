"""Tests for the `analytics-data-workspace` capability (openspec/specs/analytics-data-workspace/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, SimpleTestCase, override_settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point, Polygon
from django.utils import timezone
import json
import re
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
from survey.analytics import SurveyAnalyticsService
from survey.versioning import clone_survey_for_draft
from django.conf import settings
import os
from survey.tests.helpers import _make_org, _objects_layer


class AnalyticsAnswerEditTest(TestCase):
    """Inline answer edit from Responses (change fix-answer-edit-geo-500)."""

    def setUp(self):
        self.org = _make_org('AnswerEditOrg')
        self.owner = User.objects.create_user('answereditor', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.client.login(username='answereditor', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.survey = SurveyHeader.objects.create(
            name='answer_edit', organization=self.org,
            created_by=self.owner, status='published',
        )
        section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.q_point = Question.objects.create(
            survey_section=section, name='Where', code='where',
            input_type='point', order_number=1,
        )
        self.q_poly = Question.objects.create(
            survey_section=section, name='Area', code='area',
            input_type='polygon', order_number=2,
        )
        self.q_text = Question.objects.create(
            survey_section=section, name='Why', code='why',
            input_type='text', order_number=3,
        )
        self.sess = SurveySession.objects.create(survey=self.survey)

    def _edit(self, question, value):
        return self.client.post(
            f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{self.sess.id}/answers/{question.id}/edit/',
            data=json.dumps({'value': value}), content_type='application/json',
        )

    def test_multi_feature_geo_answer_is_refused_not_crashed(self):
        """
        GIVEN a session with three root answers to a point question
        WHEN an editor POSTs a new value for that session and question
        THEN the response is 400 and the three answers are unchanged
        """
        for x in (1, 2, 3):
            Answer.objects.create(survey_session=self.sess, question=self.q_point, point=Point(x, x))
        response = self._edit(self.q_point, 'anything')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            sorted(a.point.x for a in Answer.objects.filter(question=self.q_point)), [1, 2, 3],
        )

    def test_unanswered_geo_question_creates_nothing(self):
        """
        GIVEN a session with no answer to a polygon question
        WHEN an editor POSTs a value for it
        THEN the response is 400 and no answer row is created
        """
        response = self._edit(self.q_poly, 'anything')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Answer.objects.filter(question=self.q_poly).exists())

    def test_text_edit_updates_earliest_of_duplicates(self):
        """
        GIVEN a session with two root answers to a text question
        WHEN an editor POSTs "new" for it
        THEN the response is 204 and the earliest answer's text is "new"
        """
        first = Answer.objects.create(survey_session=self.sess, question=self.q_text, text='a')
        second = Answer.objects.create(survey_session=self.sess, question=self.q_text, text='b')
        response = self._edit(self.q_text, 'new')
        self.assertEqual(response.status_code, 204)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.text, second.text), ('new', 'b'))

    def test_text_edit_creates_missing_answer(self):
        """
        GIVEN a session with no answer to a text question
        WHEN an editor POSTs "hello" for it
        THEN the response is 204 and one answer with that text exists
        """
        response = self._edit(self.q_text, 'hello')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(
            list(Answer.objects.filter(question=self.q_text).values_list('text', flat=True)), ['hello'],
        )

    @override_settings(RESPONSES_V2=False)
    def test_table_offers_edit_only_on_editable_columns(self):
        """
        GIVEN a Responses table with a point column and a text column
        WHEN an editor renders the legacy table
        THEN only the text cells carry the double-click edit handler
        """
        Answer.objects.create(survey_session=self.sess, question=self.q_point, point=Point(1, 1))
        Answer.objects.create(survey_session=self.sess, question=self.q_text, text='why not')
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/analytics/table/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn(f"startCellEdit(this, {self.sess.id}, '{self.q_text.id}'", html)
        self.assertNotIn(f"startCellEdit(this, {self.sess.id}, '{self.q_point.id}'", html)
        self.assertNotIn(f"startCellEdit(this, {self.sess.id}, '{self.q_poly.id}'", html)


class ResponsesV2TableTest(TestCase):
    """v2 response table: column defaults, chips, status chip, row activation."""

    def setUp(self):
        self.org = _make_org('RespV2TblOrg')
        self.owner = User.objects.create_user('respv2tblowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.client.login(username='respv2tblowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.survey = SurveyHeader.objects.create(
            name='respv2_tbl', organization=self.org,
            created_by=self.owner, status='published',
        )
        self.s1 = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.q = Question.objects.create(
            survey_section=self.s1, name='Comment', code='q1',
            input_type='text', order_number=1,
        )
        self.sess_complete = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(
            survey_session=self.sess_complete, question=self.q, text='done here',
        )
        self.sess_empty = SurveySession.objects.create(survey=self.survey)
        self.url = f'/editor/surveys/{self.survey.uuid}/analytics/table/'
        # These tests exercise the table with its empty session listed, so they
        # show empty sessions the way a creator does (spec responses-empty-sessions).
        self.client.cookies['rv2_show_empty'] = '1'

    def test_duration_reads_the_session_row(self):
        """
        GIVEN a completed session (end_datetime), an abandoned one (last_activity_at only) and
              an untimed one, with no events at all
        WHEN the v2 table is built
        THEN Duration is m:ss for the completed one, m:ss+ for the abandoned one, and empty for the third
        """
        from datetime import timedelta
        from django.utils import timezone
        from survey.analytics import SurveyAnalyticsService
        t0 = timezone.now() - timedelta(hours=1)
        SurveySession.objects.filter(pk=self.sess_complete.pk).update(
            start_datetime=t0, end_datetime=t0 + timedelta(minutes=3, seconds=20),
            last_activity_at=t0 + timedelta(minutes=3, seconds=20))
        SurveySession.objects.filter(pk=self.sess_empty.pk).update(
            start_datetime=t0, last_activity_at=t0 + timedelta(seconds=45))
        untimed = SurveySession.objects.create(survey=self.survey, start_datetime=t0)
        page = SurveyAnalyticsService(self.survey, version='all').get_table_page(page=1, page_size=10, v2=True)
        by_id = {r['session_id']: r for r in page['rows']}
        self.assertEqual(by_id[self.sess_complete.pk]['duration_display'], '3:20')
        self.assertEqual(by_id[self.sess_empty.pk]['duration_display'], '0:45+')
        self.assertTrue(by_id[self.sess_empty.pk]['duration_open'])
        self.assertIsNone(by_id[untimed.pk]['duration_display'])

    def test_layer_questions_get_no_table_column(self):
        """
        GIVEN a survey with a text question and an Objects-on-the-map question bound to a layer
        WHEN the response table is built
        THEN the Objects question has no column — its answers live per object on its sub-questions
        """
        from survey.analytics import SurveyAnalyticsService
        layer = _objects_layer(self.survey, name="Bins")
        Question.objects.create(survey_section=self.s1, name='Bins', code='lq', input_type='layer_objects',
                                layer=layer, order_number=2)
        page = SurveyAnalyticsService(self.survey, version='all').get_table_page(page=1, page_size=10)
        self.assertEqual([c['input_type'] for c in page['columns'] if c['input_type']], ['text'])

    def test_table_read_from_a_draft_copy_keys_cells_on_the_published_question(self):
        """
        GIVEN a published survey with one answered text question and a draft copy of it
        WHEN the response table is built from the draft (scope: the published family)
        THEN the question column's key equals the published question's id, so the stored
             answer lands in that column rather than under the draft clone's id
        """
        draft = clone_survey_for_draft(self.survey)
        clone = Question.objects.get(survey_section__survey_header=draft, code='q1')
        self.assertNotEqual(clone.pk, self.q.pk)
        from survey.analytics import SurveyAnalyticsService
        page = SurveyAnalyticsService(draft, version='all').get_table_page(page=1, page_size=10)
        keys = [c['key'] for c in page['columns'] if c['input_type'] == 'text']
        self.assertEqual(keys, [str(self.q.pk)])
        row = next(r for r in page['rows'] if r['session_id'] == self.sess_complete.pk)
        self.assertEqual(row['cells'].get(str(self.q.pk)), 'done here')

    @override_settings(RESPONSES_V2=True)
    def test_v2_column_defaults(self):
        """
        GIVEN the v2 switch is on
        WHEN GET the table partial
        THEN Started/Duration lead the columns and language is default-hidden
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Started', content)
        self.assertIn('Duration', content)
        # Started column renders before the question column
        self.assertLess(content.index('Started'), content.index('Comment'))
        self.assertContains(response, 'default-hidden-cols')
        self.assertContains(response, '"language"')

    @override_settings(RESPONSES_V2=True)
    def test_v2_toolbar_chips_replace_sidebar_controls(self):
        """
        GIVEN one clean and one empty session
        WHEN GET the table partial
        THEN the all/complete/issues/trash chips render with counts and the
             legacy Hide fields / Trash buttons are gone
        """
        response = self.client.get(self.url)
        self.assertContains(response, 'rv2-chip-all')
        self.assertContains(response, 'rv2-chip-complete')
        self.assertContains(response, 'rv2-chip-issues')
        self.assertContains(response, 'rv2-chip-trash')
        self.assertContains(response, 'All 2')
        self.assertContains(response, 'Complete 1')
        self.assertNotContains(response, 'Hide fields')
        self.assertNotContains(response, 'trash-toggle-btn')

    @override_settings(RESPONSES_V2=True)
    def test_v2_complete_filter(self):
        """
        GIVEN one completed and one empty session
        WHEN GET the table with issues=complete
        THEN only the completed session's row is returned
        """
        response = self.client.get(self.url + '?issues=complete')
        content = response.content.decode()
        self.assertIn(f'data-session-id="{self.sess_complete.id}"', content)
        self.assertNotIn(
            f'onclick="rv2RowOpen(event, {self.sess_empty.id})"', content,
        )

    @override_settings(RESPONSES_V2=True)
    def test_v2_row_activation_and_status_chip(self):
        """
        GIVEN the v2 switch is on
        WHEN GET the table partial
        THEN rows carry the click handler and a status chip, and the per-row
             eye icon and status select are gone
        """
        response = self.client.get(self.url)
        self.assertContains(response, 'rv2RowOpen(event,')
        self.assertContains(response, 'rv2-status-chip')
        self.assertNotContains(response, 'fa-eye" style')
        self.assertNotContains(response, 'validation-select')

    @override_settings(RESPONSES_V2=True)
    def test_v2_sequence_numbers(self):
        """
        GIVEN two answered sessions in start order
        WHEN GET the table partial
        THEN rows show per-survey sequence numbers, not raw database ids
        """
        Answer.objects.create(survey_session=self.sess_empty, question=self.q, text='now answered')
        extra = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=extra, question=self.q, text='also answered')
        self.sess_complete.is_deleted = True
        self.sess_complete.save()
        response = self.client.get(self.url)
        content = response.content.decode()
        # Two active answered sessions → sequences 1 and 2; the newest session's
        # raw pk is greater than any sequence and must not leak into the # column.
        self.assertIn('#1\n', content)
        self.assertIn('#2\n', content)
        self.assertNotIn(f'#{extra.id}\n', content)

    @override_settings(RESPONSES_V2=True)
    def test_issues_menu_offers_individual_violation_types(self):
        """
        GIVEN a survey whose answered session skipped the last section (one
              violation type) and an empty session, shown
        WHEN GET the table partial
        THEN the Issues chip opens a multi-select menu and per-type counts ship
             with the partial, so individual violations stay selectable — but
             "empty" is not among them: the show/hide control owns empty sessions
        """
        s2 = SurveySection.objects.create(survey_header=self.survey, name='s2', code='S2')
        self.s1.next_section = s2
        self.s1.save()
        Question.objects.create(survey_section=s2, name='Last', code='q2', input_type='text', order_number=1)
        response = self.client.get(self.url)
        self.assertContains(response, 'rv2IssuesMenu(event,')
        self.assertContains(response, 'anomaly-counts-data')
        content = response.content.decode()
        self.assertIn('"incomplete"', content)
        self.assertNotIn('"empty"', content.split('id="anomaly-counts-data">')[1].split('<')[0])

    @override_settings(RESPONSES_V2=True)
    def test_issues_multi_select_filters_rows(self):
        """
        GIVEN sessions flagged with different violation types
        WHEN GET the table with a comma-separated issues param
        THEN rows matching any selected type are returned and the chip reports
             how many types are selected
        """
        response = self.client.get(self.url + '?issues=empty,fast')
        self.assertContains(response, '2 selected')
        content = response.content.decode()
        self.assertIn(f'data-session-id="{self.sess_empty.id}"', content)
        self.assertNotIn(f'data-session-id="{self.sess_complete.id}"', content)

    @override_settings(RESPONSES_V2=True)
    def test_free_text_search_across_columns(self):
        """
        GIVEN one session whose answer text is "done here"
        WHEN GET the table with q=done
        THEN only that session's row survives, and a non-matching query
             returns none
        """
        response = self.client.get(self.url + '?q=done')
        content = response.content.decode()
        self.assertIn(f'data-session-id="{self.sess_complete.id}"', content)
        self.assertNotIn(f'data-session-id="{self.sess_empty.id}"', content)

        empty_result = self.client.get(self.url + '?q=zzzznotfound')
        self.assertContains(empty_result, 'No responses')

    @override_settings(RESPONSES_V2=True)
    def test_search_box_renders_with_current_query(self):
        """
        GIVEN an active search
        WHEN GET the table partial
        THEN the toolbar search box renders holding that query
        """
        response = self.client.get(self.url + '?q=done')
        self.assertContains(response, 'rv2-search-input')
        self.assertContains(response, 'value="done"')

    @override_settings(RESPONSES_V2=True)
    def test_sequence_column_sorts_by_sequence(self):
        """
        GIVEN the "#" column displays per-survey sequence numbers
        WHEN GET the table sorted by that column ascending
        THEN rows come out in sequence order, not raw-pk order
        """
        import re
        response = self.client.get(self.url + '?sort=id&dir=asc')
        content = response.content.decode()
        seqs = [int(m) for m in re.findall(r'#(\d+)\n', content)]
        self.assertEqual(seqs, sorted(seqs))
        desc = self.client.get(self.url + '?sort=id&dir=desc')
        seqs_desc = [int(m) for m in re.findall(r'#(\d+)\n', desc.content.decode())]
        self.assertEqual(seqs_desc, sorted(seqs_desc, reverse=True))

    @override_settings(RESPONSES_V2=True)
    def test_filtered_ids_ship_for_select_all_matching(self):
        """
        GIVEN a filtered set larger than one page
        WHEN GET the table partial with a small page size
        THEN the full filtered id list ships so "Select all N matching" can
             outreach the visible page
        """
        response = self.client.get(self.url + '?page_size=10')
        self.assertContains(response, 'filtered-session-ids')
        content = response.content.decode()
        import json as _json, re as _re
        m = _re.search(r'id="filtered-session-ids">(\[[^<]*\])<', content)
        self.assertIsNotNone(m)
        ids = _json.loads(m.group(1))
        self.assertEqual(len(ids), 2)  # both sessions, beyond any single page

    @override_settings(RESPONSES_V2=False)
    def test_legacy_table_unchanged(self):
        """
        GIVEN the v2 switch is off
        WHEN GET the table partial
        THEN the legacy toolbar renders and no v2 chips appear
        """
        response = self.client.get(self.url)
        self.assertContains(response, 'Hide fields')
        self.assertContains(response, 'validation-select')
        self.assertNotContains(response, 'rv2-chip-all')
        self.assertNotContains(response, 'rv2-status-chip')


@override_settings(RESPONSES_V2=True)
class ResponsesV2FilterPillsTest(TestCase):
    """Global filter pills row and cross-filter discoverability."""

    def setUp(self):
        self.org = _make_org('RespV2PillOrg')
        self.owner = User.objects.create_user('respv2pillowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.client.login(username='respv2pillowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.survey = SurveyHeader.objects.create(
            name='respv2_pill', organization=self.org,
            created_by=self.owner, status='published',
        )
        SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.url = f'/editor/surveys/{self.survey.uuid}/analytics/'

    def test_pills_bar_is_single_and_global(self):
        """
        GIVEN the v2 dashboard
        WHEN it renders
        THEN exactly one pills bar exists, above the pane containers, carrying
             the v2 class the engine's count logic keys on
        """
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertEqual(content.count('id="filter-pills-bar"'), 1)
        self.assertContains(response, 'rv2-filter-pills')
        # Bar comes before the pane containers (shared across panes)
        self.assertLess(
            content.index('id="filter-pills-bar"'),
            content.index('data-pane-content="overview"'),
        )
        # Engine ships the filtered-vs-total count for the v2 bar
        self.assertContains(response, 'rv2-pills-count')
        self.assertContains(response, 'of ')

    def test_first_time_filter_hint(self):
        """
        GIVEN a creator who never filtered
        WHEN the Charts pane renders
        THEN the click-to-filter hint is present with its dismissal wiring
        """
        response = self.client.get(self.url)
        self.assertContains(response, 'rv2-filter-hint')
        self.assertContains(response, 'rv2FilterHintSeen')


@override_settings(RESPONSES_V2=True)
class ResponsesV2SplitViewTest(TestCase):
    """Split view v2: explicit labeled mode, persistence, reset, map resize."""

    def setUp(self):
        self.org = _make_org('RespV2SplitOrg')
        self.owner = User.objects.create_user('respv2splitowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.client.login(username='respv2splitowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.survey = SurveyHeader.objects.create(
            name='respv2_split', organization=self.org,
            created_by=self.owner, status='published',
        )
        SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.url = f'/editor/surveys/{self.survey.uuid}/analytics/'

    def test_split_is_labeled_and_resettable(self):
        """
        GIVEN the v2 dashboard
        WHEN it renders
        THEN Split view is a labeled control with a visible reset, and the
             legacy split tree is absent
        """
        response = self.client.get(self.url)
        self.assertContains(response, 'Split view')
        self.assertContains(response, 'rv2-split-btn')
        self.assertContains(response, 'Reset layout')
        self.assertNotContains(response, '_renderTree')

    def test_selection_manager_rewires_cross_pane_repaint(self):
        """
        GIVEN the v2 dashboard (which does not run the legacy split-tree bootstrap)
        WHEN it renders
        THEN the SelectionManager→FilterManager repaint subscription ships, so a
             selection made on the map redraws charts, table rows and the
             selection bar (regression: owner found map/chart selection dead)
        """
        response = self.client.get(self.url)
        self.assertContains(response, 'selectionManager.onChange')
        self.assertContains(response, '_renderSelection')

    def test_split_persists_per_survey_and_resizes_map(self):
        """
        GIVEN the v2 dashboard
        WHEN it renders
        THEN split state persists under a survey-scoped key, both active panes
             are indicated, and pane-geometry changes re-measure the map
        """
        response = self.client.get(self.url)
        self.assertContains(response, f'rv2Split_{self.survey.uuid}')
        self.assertContains(response, 'active-secondary')
        self.assertContains(response, 'invalidateSize')


class CrossFilteringServiceTest(TestCase):
    """Tests for cross-filtering analytics features."""

    def setUp(self):
        from survey.analytics import SurveyAnalyticsService
        self.SurveyAnalyticsService = SurveyAnalyticsService

        self.org = _make_org('CrossFilterOrg')
        self.user = User.objects.create_user('cfowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

        self.survey = SurveyHeader.objects.create(
            name='crossfilter_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.q_gender = Question.objects.create(
            survey_section=self.section, name='Gender', code='qg',
            input_type='choice', order_number=1,
            choices=[{'code': 1, 'name': 'Male'}, {'code': 2, 'name': 'Female'}],
        )
        self.q_rating = Question.objects.create(
            survey_section=self.section, name='Rating', code='qr',
            input_type='rating', order_number=2,
            choices=[
                {'code': 1, 'name': 'Bad'},
                {'code': 2, 'name': 'OK'},
                {'code': 3, 'name': 'Good'},
            ],
        )
        self.q_text = Question.objects.create(
            survey_section=self.section, name='Comment', code='qt',
            input_type='text', order_number=3,
        )
        self.q_point = Question.objects.create(
            survey_section=self.section, name='Location', code='qp',
            input_type='point', order_number=4,
        )

        # Session 1: Male, Good rating, "Nice" comment, point
        self.s1 = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=self.s1, question=self.q_gender, selected_choices=[1])
        Answer.objects.create(survey_session=self.s1, question=self.q_rating, selected_choices=[3])
        Answer.objects.create(survey_session=self.s1, question=self.q_text, text='Nice')
        Answer.objects.create(survey_session=self.s1, question=self.q_point, point=Point(2.35, 48.86))

        # Session 2: Female, Bad rating, "Awful" comment
        self.s2 = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=self.s2, question=self.q_gender, selected_choices=[2])
        Answer.objects.create(survey_session=self.s2, question=self.q_rating, selected_choices=[1])
        Answer.objects.create(survey_session=self.s2, question=self.q_text, text='Awful')

        # Session 3: Male, Bad rating, "Meh" comment
        self.s3 = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=self.s3, question=self.q_gender, selected_choices=[1])
        Answer.objects.create(survey_session=self.s3, question=self.q_rating, selected_choices=[1])
        Answer.objects.create(survey_session=self.s3, question=self.q_text, text='Meh')

    def test_answer_matrix_structure(self):
        """
        GIVEN 3 sessions with choice and rating answers
        WHEN get_answer_matrix is called
        THEN returns list of session dicts with correct structure
        """
        service = self.SurveyAnalyticsService(self.survey)
        matrix = service.get_answer_matrix()

        self.assertEqual(len(matrix), 3)
        sids = {m['sid'] for m in matrix}
        self.assertEqual(sids, {self.s1.id, self.s2.id, self.s3.id})

        for entry in matrix:
            self.assertIn('sid', entry)
            self.assertIn('d', entry)
            self.assertIn('a', entry)
            # Each session should have gender and rating answers
            self.assertIn(str(self.q_gender.id), entry['a'])
            self.assertIn(str(self.q_rating.id), entry['a'])
            # Text and point questions should NOT be in matrix
            self.assertNotIn(str(self.q_text.id), entry['a'])
            self.assertNotIn(str(self.q_point.id), entry['a'])

    def test_answer_matrix_values(self):
        """
        GIVEN session 1 with Male (1) and Good (3)
        WHEN get_answer_matrix is called
        THEN session 1 entry has correct choice codes
        """
        service = self.SurveyAnalyticsService(self.survey)
        matrix = service.get_answer_matrix()

        s1_entry = next(m for m in matrix if m['sid'] == self.s1.id)
        self.assertEqual(s1_entry['a'][str(self.q_gender.id)], [1])
        self.assertEqual(s1_entry['a'][str(self.q_rating.id)], [3])

    def test_geo_feature_has_session_id(self):
        """
        GIVEN a session with a point answer
        WHEN get_geo_feature_collection is called
        THEN each feature has session_id in properties
        """
        service = self.SurveyAnalyticsService(self.survey)
        fc = service.get_geo_feature_collection()

        self.assertEqual(len(fc['features']), 1)
        self.assertEqual(fc['features'][0]['properties']['session_id'], self.s1.id)

    def test_question_stats_has_choice_codes(self):
        """
        GIVEN a choice question
        WHEN get_question_stats is called
        THEN stat includes choice_codes and choice_codes_json
        """
        service = self.SurveyAnalyticsService(self.survey)
        stat = service.get_question_stats(self.q_gender)

        self.assertEqual(stat['choice_codes'], [1, 2])
        self.assertEqual(stat['choice_codes_json'], '[1, 2]')

    def test_text_answers_filtered_by_session_ids(self):
        """
        GIVEN 3 text answers from 3 sessions
        WHEN get_text_answers is called with session_ids={s1, s3}
        THEN returns only 2 answers from those sessions
        """
        service = self.SurveyAnalyticsService(self.survey)
        result = service.get_text_answers(
            self.q_text, session_ids={self.s1.id, self.s3.id},
        )

        self.assertEqual(result['total'], 2)
        texts = {a.text for a in result['answers']}
        self.assertEqual(texts, {'Nice', 'Meh'})

    def test_text_answers_empty_session_ids(self):
        """
        GIVEN 3 text answers
        WHEN get_text_answers is called with session_ids=set() (empty)
        THEN returns 0 answers
        """
        service = self.SurveyAnalyticsService(self.survey)
        result = service.get_text_answers(self.q_text, session_ids=set())

        self.assertEqual(result['total'], 0)
        self.assertEqual(len(result['answers']), 0)

    def test_text_answers_no_filter(self):
        """
        GIVEN 3 text answers
        WHEN get_text_answers is called with session_ids=None
        THEN returns all 3 answers
        """
        service = self.SurveyAnalyticsService(self.survey)
        result = service.get_text_answers(self.q_text, session_ids=None)

        self.assertEqual(result['total'], 3)


class CrossFilteringViewTest(TestCase):
    """Tests for cross-filtering view helpers and endpoints."""

    def setUp(self):
        self.org = _make_org('CrossFilterViewOrg')
        self.owner = User.objects.create_user('cfvowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.client.login(username='cfvowner', password='pass')

        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

        self.survey = SurveyHeader.objects.create(
            name='cfview_test', organization=self.org,
            created_by=self.owner, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.q_choice = Question.objects.create(
            survey_section=self.section, name='Color', code='qc',
            input_type='choice', order_number=1,
            choices=[{'code': 1, 'name': 'Red'}, {'code': 2, 'name': 'Blue'}],
        )
        self.q_text = Question.objects.create(
            survey_section=self.section, name='Why', code='qw',
            input_type='text', order_number=2,
        )

        # Session A: Red, "I like red"
        self.sa = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=self.sa, question=self.q_choice, selected_choices=[1])
        Answer.objects.create(survey_session=self.sa, question=self.q_text, text='I like red')

        # Session B: Blue, "I like blue"
        self.sb = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=self.sb, question=self.q_choice, selected_choices=[2])
        Answer.objects.create(survey_session=self.sb, question=self.q_text, text='I like blue')

    def test_parse_filter_param_valid(self):
        """
        GIVEN a valid filter string '7:1,3;12:2'
        WHEN _parse_filter_param is called
        THEN returns correct dict
        """
        from survey.analytics_views import _parse_filter_param
        result = _parse_filter_param('7:1,3;12:2')
        self.assertEqual(result, {7: [1, 3], 12: [2]})

    def test_parse_filter_param_empty(self):
        """
        GIVEN an empty string
        WHEN _parse_filter_param is called
        THEN returns empty dict
        """
        from survey.analytics_views import _parse_filter_param
        self.assertEqual(_parse_filter_param(''), {})
        self.assertEqual(_parse_filter_param(None), {})

    def test_parse_filter_param_invalid(self):
        """
        GIVEN an invalid filter string
        WHEN _parse_filter_param is called
        THEN returns empty dict without raising
        """
        from survey.analytics_views import _parse_filter_param
        self.assertEqual(_parse_filter_param('garbage'), {})
        self.assertEqual(_parse_filter_param('abc:xyz'), {})

    def test_resolve_filtered_session_ids_single_filter(self):
        """
        GIVEN sessions with Red(1) and Blue(2) answers
        WHEN _resolve_filtered_session_ids filters for Red (code=1)
        THEN returns only session A
        """
        from survey.analytics_views import _resolve_filtered_session_ids
        result = _resolve_filtered_session_ids(
            self.survey, {self.q_choice.id: [1]},
        )
        self.assertEqual(result, {self.sa.id})

    def test_resolve_filtered_session_ids_no_filter(self):
        """
        GIVEN no filters
        WHEN _resolve_filtered_session_ids is called with empty dict
        THEN returns None (no filtering)
        """
        from survey.analytics_views import _resolve_filtered_session_ids
        result = _resolve_filtered_session_ids(self.survey, {})
        self.assertIsNone(result)

    def test_dashboard_includes_answer_matrix(self):
        """
        GIVEN a survey with choice answers
        WHEN GET analytics dashboard
        THEN response contains answer-matrix-data script tag
        """
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/analytics/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'answer-matrix-data')
        self.assertContains(response, 'FilterManager')

    def test_text_answers_with_filter_param(self):
        """
        GIVEN sessions with Red and Blue answers
        WHEN GET text answers with filters=<choice_id>:1 (Red only)
        THEN returns only the text answer from the Red session
        """
        filters = f'{self.q_choice.id}:1'
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/analytics/questions/{self.q_text.id}/text/'
            f'?filters={filters}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'I like red')
        self.assertNotContains(response, 'I like blue')


class InlineEditingTest(TestCase):
    """Tests for inline answer editing."""

    def setUp(self):
        self.org = _make_org('EditOrg')
        self.user = User.objects.create_user('editowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.viewer = User.objects.create_user('editviewer', password='pass')
        Membership.objects.create(user=self.viewer, organization=self.org, role='viewer')
        self.survey = SurveyHeader.objects.create(
            name='edit_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.q_text = Question.objects.create(
            survey_section=self.section, name='Name', code='q1',
            input_type='text', order_number=1,
        )
        self.q_number = Question.objects.create(
            survey_section=self.section, name='Age', code='q2',
            input_type='number', order_number=2,
        )
        self.q_choice = Question.objects.create(
            survey_section=self.section, name='Color', code='q3',
            input_type='choice', order_number=3,
            choices=[{'code': 1, 'name': 'Red'}, {'code': 2, 'name': 'Blue'}],
        )

    def _login_owner(self):
        self.client.login(username='editowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def _login_viewer(self):
        self.client.login(username='editviewer', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def _post_edit(self, session_id, question_id, value):
        url = f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{session_id}/answers/{question_id}/edit/'
        return self.client.post(url, json.dumps({'value': value}), content_type='application/json')

    def test_edit_text_answer(self):
        """
        GIVEN a session with a text answer
        WHEN POST to edit with new text
        THEN the answer text is updated
        """
        s = SurveySession.objects.create(survey=self.survey)
        a = Answer.objects.create(survey_session=s, question=self.q_text, text='Alice')
        self._login_owner()
        resp = self._post_edit(s.id, self.q_text.id, 'Bob')
        self.assertEqual(resp.status_code, 204)
        a.refresh_from_db()
        self.assertEqual(a.text, 'Bob')

    def test_edit_number_answer(self):
        """
        GIVEN a session with a number answer
        WHEN POST to edit with new number
        THEN the answer numeric is updated
        """
        s = SurveySession.objects.create(survey=self.survey)
        a = Answer.objects.create(survey_session=s, question=self.q_number, numeric=25)
        self._login_owner()
        resp = self._post_edit(s.id, self.q_number.id, 30)
        self.assertEqual(resp.status_code, 204)
        a.refresh_from_db()
        self.assertEqual(a.numeric, 30)

    def test_edit_choice_answer(self):
        """
        GIVEN a session with a choice answer
        WHEN POST to edit with new choice code
        THEN selected_choices is updated
        """
        s = SurveySession.objects.create(survey=self.survey)
        a = Answer.objects.create(survey_session=s, question=self.q_choice, selected_choices=[1])
        self._login_owner()
        resp = self._post_edit(s.id, self.q_choice.id, 2)
        self.assertEqual(resp.status_code, 204)
        a.refresh_from_db()
        self.assertEqual(a.selected_choices, [2])

    def test_create_answer_for_blank_cell(self):
        """
        GIVEN a session with no answer for a question
        WHEN POST to edit
        THEN a new answer is created
        """
        s = SurveySession.objects.create(survey=self.survey)
        self._login_owner()
        resp = self._post_edit(s.id, self.q_text.id, 'New value')
        self.assertEqual(resp.status_code, 204)
        self.assertTrue(Answer.objects.filter(survey_session=s, question=self.q_text).exists())
        self.assertEqual(Answer.objects.get(survey_session=s, question=self.q_text).text, 'New value')

    def test_viewer_cannot_edit(self):
        """
        GIVEN a viewer user
        WHEN POST to edit answer
        THEN response is 403
        """
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.q_text, text='Alice')
        self._login_viewer()
        resp = self._post_edit(s.id, self.q_text.id, 'Hacked')
        self.assertEqual(resp.status_code, 403)


class AnalyticsHeatLayerGuardTest(TestCase):
    """The analytics heat layer must not draw into a 0x0 canvas.

    The guard is on the layer rather than on the callers: `invalidateSize()` is
    called from sixteen places across the analytics templates, and a per-caller
    guard would neither cover them all nor cover the next one added.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='heat_owner', password='pass')
        self.org = _make_org('HeatOrg')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(name='heat_survey', organization=self.org)
        section = SurveySection.objects.create(
            survey_header=self.survey, name='sec', code='S1', is_head=True)
        # Both dashboards include the geo map only when the survey has geo
        # features, so an empty survey renders the "no geo questions" placeholder
        # and the guard would look absent. One stored point is the minimum that
        # puts the heat layer on the page at all.
        question = Question.objects.create(
            survey_section=section, code='Q_PT', name='Where?',
            input_type='point', order_number=1)
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=session, question=question,
                              point=Point(13.405, 52.52))
        self.client.login(username='heat_owner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def test_heat_layer_redraw_is_guarded(self):
        """
        GIVEN the analytics dashboard
        WHEN it renders
        THEN the heat layer's redraw guard is defined and applied at creation
        """
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/analytics/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('function _guardHeatRedraw(layer)', html)
        self.assertIn('_guardHeatRedraw(heatLayer);', html)

    def test_guard_precedes_adding_the_layer_to_the_map(self):
        """
        GIVEN the heat layer creation code
        WHEN the layer is wrapped
        THEN the wrapping happens before addTo(), so the first redraw is guarded too
        """
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/analytics/')
        html = response.content.decode()
        guard_at = html.index('_guardHeatRedraw(heatLayer);')
        add_at = html.index('heatLayer.addTo(this._map);')
        self.assertLess(guard_at, add_at)


class EditorMapLifecycleGuardTest(SimpleTestCase):
    """Every map on the Responses page mounts through EditorMap, and the helper
    keeps the contract that makes that safe.

    Four maps -- Map pane, Overview thumbnail, drawer mini-map, response modal
    -- each had a private answer to "is there a map here already, how do I get
    rid of it, when can I draw". The drawer's answer held the instance in a
    page global and called remove() on it after HTMX had discarded its DOM:
    one throw, a half-cleared container id, then "Map container is being
    reused by another instance" on every later open (PostHog 01a0a273, three
    issues in five seconds). openspec: responses-map-lifecycle.

    This is the class-level guard, per the lesson on #194: a test pinned to the
    four surfaces that exist today would let the fifth ship the old pattern
    green. It scans the analytics templates' SOURCE for a raw `L.map(` and
    reads the helper's source for the parts a browser test cannot pin. There
    is no JavaScript runner in this repository; behaviour is verified in a
    browser (tasks 5.2-5.4).
    """

    TEMPLATES = os.path.join(settings.BASE_DIR, 'survey', 'templates', 'editor')
    HELPER = os.path.join(settings.BASE_DIR, 'survey', 'assets', 'js', 'editor_map.js')

    def _analytics_templates(self):
        found = []
        for root, _dirs, files in os.walk(self.TEMPLATES):
            for filename in files:
                if filename.endswith('.html') and (
                        filename.startswith('analytics_') or filename.startswith('_analytics_')):
                    found.append(os.path.join(root, filename))
        self.assertTrue(found, 'no analytics templates found -- the scan is looking in the wrong place')
        return found

    def _helper_source(self):
        with open(self.HELPER, encoding='utf-8') as fh:
            return fh.read()

    def test_no_analytics_template_mounts_leaflet_directly(self):
        """
        GIVEN every analytics template under editor/
        WHEN its source is scanned for a raw Leaflet mount
        THEN none calls `L.map(` -- every map goes through EditorMap.mount
        """
        offenders = []
        for path in self._analytics_templates():
            with open(path, encoding='utf-8') as fh:
                for lineno, line in enumerate(fh, start=1):
                    if 'L.map(' in line:
                        offenders.append(f'{os.path.relpath(path, self.TEMPLATES)}:{lineno}: {line.strip()}')
        self.assertEqual(offenders, [], 'raw L.map() outside EditorMap:\n  ' + '\n  '.join(offenders))

    def test_no_page_global_holds_a_responses_map(self):
        """
        GIVEN the analytics templates
        WHEN scanned for the globals that used to hold the drawer and modal maps
        THEN none remains -- an instance that lives on its element cannot outlive it
        """
        offenders = []
        for path in self._analytics_templates():
            with open(path, encoding='utf-8') as fh:
                body = fh.read()
            for name in ('_sessionMiniMap', 'initSessionMiniMap', '_sessionGeoMap'):
                if name in body:
                    offenders.append(f'{os.path.relpath(path, self.TEMPLATES)}: {name}')
        self.assertEqual(offenders, [], '\n  '.join(offenders))

    def test_helper_disposes_without_throwing_and_clears_the_container(self):
        """
        GIVEN the helper's source
        WHEN dispose() is read
        THEN Leaflet's remove() is inside a try, and the container's Leaflet id
             is cleared outside it -- so a half-torn map cannot poison the
             element for the next mount
        """
        source = self._helper_source()
        dispose_at = source.index('function dispose(')
        body = source[dispose_at:source.index('function sweep(')]
        self.assertIn('try {', body)
        self.assertIn('map.remove();', body)
        self.assertLess(body.index('try {'), body.index('map.remove();'))
        self.assertIn('delete el._leaflet_id', body)
        self.assertLess(body.index('} catch (e) {'), body.index('delete el._leaflet_id'),
                        'the id must be cleared after the try/catch, whatever remove() managed')

    def test_helper_disposes_on_htmx_cleanup_and_waits_for_size(self):
        """
        GIVEN the helper's source
        WHEN mount() and whenSized() are read
        THEN the map is disposed on htmx:beforeCleanupElement (while its element is
             still attached), the instance is kept on the element, and readiness
             is observed with ResizeObserver rather than timed
        """
        source = self._helper_source()
        self.assertIn("addEventListener('htmx:beforeCleanupElement'", source)
        self.assertIn('el._editorMap = map;', source)
        self.assertIn('new ResizeObserver(', source)
        self.assertNotIn('setTimeout(', source, 'readiness must be observed, not guessed')

    def test_helper_is_loaded_by_the_editor_base(self):
        """
        GIVEN editor_base.html
        WHEN its script includes are read
        THEN editor_map.js is loaded there -- the drawer partial arrives by swap and
             needs the helper to exist before its inline script runs
        """
        path = os.path.join(self.TEMPLATES, 'editor_base.html')
        with open(path, encoding='utf-8') as fh:
            body = fh.read()
        self.assertIn("{% static 'js/editor_map.js' %}", body)


class EditorMapLifecycleRenderTest(TestCase):
    """The four Responses maps reach the page through EditorMap.mount.

    Source scans prove no template bypasses the helper; these prove the helper
    and the four call sites actually render on both dashboards and on the
    detail endpoint the drawer swaps in.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='maplife_owner', password='pass')
        self.org = _make_org('MapLifeOrg')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(name='maplife_survey', organization=self.org)
        section = SurveySection.objects.create(
            survey_header=self.survey, name='sec', code='S1', is_head=True)
        q_pt = Question.objects.create(
            survey_section=section, code='Q_PT', name='Where?',
            input_type='point', order_number=1)
        q_pg = Question.objects.create(
            survey_section=section, code='Q_PG', name='Which area?',
            input_type='polygon', order_number=2)
        self.session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=self.session, question=q_pt,
                              point=Point(13.405, 52.52))
        Answer.objects.create(survey_session=self.session, question=q_pg,
                              polygon=Polygon(((13.40, 52.52), (13.41, 52.52),
                                               (13.41, 52.53), (13.40, 52.53), (13.40, 52.52))))
        self.client.login(username='maplife_owner', password='pass')
        s = self.client.session
        s['active_org_id'] = self.org.id
        s.save()
        self.dash_url = f'/editor/surveys/{self.survey.uuid}/analytics/'
        self.detail_url = f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{self.session.id}/'

    @override_settings(RESPONSES_V2=True)
    def test_v2_dashboard_mounts_its_three_maps_through_the_helper(self):
        """
        GIVEN the v2 Responses page for a survey with geo answers
        WHEN it renders
        THEN the helper is loaded and the Map pane, the Overview thumbnail and the
             response modal all mount through EditorMap.mount
        """
        response = self.client.get(self.dash_url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('js/editor_map', html)
        self.assertIn("EditorMap.mount('analytics-map'", html)
        self.assertIn('EditorMap.mount(mapEl', html)
        self.assertIn("EditorMap.mount('session-geo-modal-map'", html)
        self.assertIn("EditorMap.dispose('session-geo-modal-map')", html)

    @override_settings(RESPONSES_V2=False)
    def test_v1_dashboard_mounts_the_map_pane_through_the_helper(self):
        """
        GIVEN the legacy Responses page (RESPONSES_V2 off)
        WHEN it renders
        THEN the helper is loaded and the Map pane mounts through EditorMap.mount
        """
        response = self.client.get(self.dash_url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('js/editor_map', html)
        self.assertIn("EditorMap.mount('analytics-map'", html)

    def test_session_detail_mounts_the_mini_map_through_the_helper(self):
        """
        GIVEN the session detail partial the drawer (and the v1 modal) swaps in
        WHEN it renders for a session with geo answers
        THEN the mini-map mounts through EditorMap.mount with its layers inside the
             ready callback, and no modal hook or page global remains
        """
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("EditorMap.mount('session-mini-map'", html)
        self.assertNotIn('shown.bs.modal', html)
        self.assertNotIn('_sessionMiniMap', html)
        self.assertNotIn('L.map(', html)
        mount_at = html.index("EditorMap.mount('session-mini-map'")
        self.assertLess(mount_at, html.index('layer.addTo(map);'),
                        'layers must be added inside the ready callback, after the mount')
        self.assertLess(mount_at, html.index('map.fitBounds('))
