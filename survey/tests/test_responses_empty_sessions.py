"""Tests for the `responses-empty-sessions` capability (openspec/specs/responses-empty-sessions/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import override_settings
from django.contrib.gis.geos import Point
from io import BytesIO
import zipfile
from survey.models import SurveySession, Answer
from survey.analytics import SurveyAnalyticsService
from urllib.parse import urlencode
from survey.tests.helpers import _EmptySessionFixture, _validated_geojson_text, _zones_geojson


class EmptySessionDefinitionTest(_EmptySessionFixture):
    """One helper decides emptiness for every surface."""

    def test_session_without_answers_is_empty(self):
        """
        GIVEN one answered and one unanswered session
        WHEN the helpers split them
        THEN only the unanswered one is empty
        """
        from survey.analytics import empty_sessions, nonempty_sessions
        answered = self._session()
        blank = self._session(answered=False)
        qs = SurveySession.objects.filter(survey=self.survey)
        self.assertEqual(list(empty_sessions(qs)), [blank])
        self.assertEqual(list(nonempty_sessions(qs)), [answered])

    def test_child_only_session_is_empty(self):
        """
        GIVEN a session whose only answer row has a parent answer
        WHEN emptiness is decided
        THEN the session is empty (only top-level answers count)
        """
        from survey.analytics import empty_sessions
        other = self._session(answered=False)
        parent = Answer.objects.create(survey_session=other, question=self.q_point, point=Point(1, 2))
        child_only = self._session(answered=False)
        Answer.objects.create(survey_session=child_only, question=self.q_sub,
                              parent_answer_id=parent, text='x')
        self.assertIn(child_only, empty_sessions(SurveySession.objects.all()))
        self.assertNotIn(other, empty_sessions(SurveySession.objects.all()))

    def test_hidden_answer_counts(self):
        """
        GIVEN a session whose only answer was hidden by moderation
        WHEN emptiness is decided
        THEN the session is not empty
        """
        from survey.analytics import empty_sessions
        sess = self._session(answered=False)
        Answer.objects.create(survey_session=sess, question=self.q_text, text='rude', hidden=True)
        self.assertFalse(empty_sessions(SurveySession.objects.filter(pk=sess.pk)).exists())

    def test_layer_object_answer_counts(self):
        """
        GIVEN a session whose only answer is about a layer object
        WHEN emptiness is decided
        THEN the session is not empty
        """
        from survey.analytics import empty_sessions
        from survey.models import LayerObject, SurveyMapLayer
        geojson, count, _ = _validated_geojson_text(_zones_geojson().encode())
        layer = SurveyMapLayer.objects.create(
            survey=self.survey, name='Zones', geojson=geojson, feature_count=count, size_bytes=len(geojson),
        )
        obj = LayerObject.objects.create(layer=layer, key='o-1', title='Zone 1', position=1,
                                         geometry=Point(13.4, 52.5))
        sess = self._session(answered=False)
        Answer.objects.create(survey_session=sess, question=self.q_text, layer_object=obj, text='nice')
        self.assertFalse(empty_sessions(SurveySession.objects.filter(pk=sess.pk)).exists())

    def test_issue_and_helper_agree(self):
        """
        GIVEN an answered and an empty session
        WHEN compute_session_issues runs
        THEN exactly the helper's empty session carries the 'empty' issue
        """
        answered = self._session()
        blank = self._session(answered=False)
        issues = SurveyAnalyticsService(self.survey).compute_session_issues([answered.id, blank.id])
        self.assertIn('empty', issues[blank.id])
        self.assertNotIn('empty', issues[answered.id])


class EmptySessionServiceTest(_EmptySessionFixture):
    """SurveyAnalyticsService with include_empty False/True."""

    def test_default_keeps_every_session(self):
        """
        GIVEN 3 answered and 2 empty sessions
        WHEN the service is built with the default arguments
        THEN it counts all 5 (survey list, legacy dashboard unchanged)
        """
        for _ in range(3):
            self._session()
        for _ in range(2):
            self._session(answered=False)
        self.assertEqual(SurveyAnalyticsService(self.survey).get_overview()['total_sessions'], 5)

    def test_hidden_empties_leave_kpis(self):
        """
        GIVEN 2 sessions that answered the last section and 2 empty sessions
        WHEN the service hides empty sessions
        THEN total is 2, completion is 100%, nothing is flagged and empty_count is 2
        """
        self._session()
        self._session()
        self._session(answered=False)
        self._session(answered=False)
        service = SurveyAnalyticsService(self.survey, include_empty=False)
        overview = service.get_overview()
        self.assertEqual(overview['total_sessions'], 2)
        self.assertEqual(overview['completion_rate'], 100)
        self.assertEqual(overview['flagged_count'], 0)
        self.assertEqual(service.empty_count, 2)

    def test_empty_count_ignores_trash(self):
        """
        GIVEN one live empty session and one trashed empty session
        WHEN empty_count is read
        THEN it counts only the live one
        """
        self._session(answered=False)
        self._session(answered=False, is_deleted=True)
        self.assertEqual(SurveyAnalyticsService(self.survey, include_empty=False).empty_count, 1)

    def test_feeds_skip_hidden_empties(self):
        """
        GIVEN 30 recent empty sessions and one older answered session
        WHEN the overview extras are built with empties hidden
        THEN neither feed lists an empty session
        """
        answered = self._session()
        empties = [self._session(answered=False).id for _ in range(30)]
        extras = SurveyAnalyticsService(self.survey, include_empty=False).get_overview_extras()
        self.assertEqual([f['id'] for f in extras['latest_feed']], [answered.id])
        self.assertFalse(set(empties) & {f['id'] for f in extras['needs_review']})

    def test_sequence_numbers_count_responses_only(self):
        """
        GIVEN sessions A (answered), B (empty), C (answered) in start order
        WHEN sequence numbers are read with empties hidden and shown
        THEN A is #1, C is #2 both times and B has no number
        """
        a = self._session()
        b = self._session(answered=False)
        c = self._session()
        for include_empty in (False, True):
            service = SurveyAnalyticsService(self.survey, include_empty=include_empty)
            page = service.get_table_page(v2=True)
            seq = {r['session_id']: r['seq'] for r in page['rows']}
            self.assertEqual(seq[a.id], 1)
            self.assertEqual(seq[c.id], 2)
            if include_empty:
                self.assertIsNone(seq[b.id])
            else:
                self.assertNotIn(b.id, seq)

    def test_table_counts_and_issue_menu(self):
        """
        GIVEN 2 answered and 3 empty sessions
        WHEN the v2 table page is built with empties shown
        THEN All counts 5 but the Issues count and menu leave 'empty' out
        """
        self._session()
        self._session()
        for _ in range(3):
            self._session(answered=False)
        page = SurveyAnalyticsService(self.survey, include_empty=True).get_table_page(v2=True)
        self.assertEqual(page['v2_counts']['all'], 5)
        self.assertEqual(page['v2_counts']['issues'], 0)
        self.assertNotIn('empty', page['anomaly_counts'])


@override_settings(RESPONSES_V2=True)
class EmptySessionPageTest(_EmptySessionFixture):
    """The v2 Responses page: default, cookie, headline, trash, empty state."""

    def test_default_hides_and_states_the_count(self):
        """
        GIVEN 3 answered and 2 empty sessions
        WHEN the creator opens Responses without the cookie
        THEN the responses KPI reads 3 and the line says 2 opened without answering, with Show
        """
        for _ in range(3):
            self._session()
        for _ in range(2):
            self._session(answered=False)
        response = self.client.get(self.url)
        self.assertEqual(response.context['total_sessions'], 3)
        self.assertEqual(response.context['empty_count'], 2)
        self.assertContains(response, '2 opened without answering (hidden)')
        self.assertContains(response, 'rv2-empty-show')

    def test_cookie_shows_them(self):
        """
        GIVEN the same sessions and the rv2_show_empty cookie
        WHEN the creator opens Responses, also under a version scope
        THEN all 5 are counted and the control offers Hide
        """
        for _ in range(3):
            self._session()
        for _ in range(2):
            self._session(answered=False)
        self.client.cookies['rv2_show_empty'] = '1'
        for url in (self.url, self.url + '?version=all'):
            response = self.client.get(url)
            self.assertEqual(response.context['total_sessions'], 5)
            self.assertContains(response, 'rv2-empty-hide')

    def test_no_line_without_empties(self):
        """
        GIVEN only answered sessions
        WHEN the creator opens Responses
        THEN no empty-session line or toggle renders
        """
        self._session()
        response = self.client.get(self.url)
        self.assertNotContains(response, 'data-testid="rv2-empty-sessions"')

    def test_only_empties_show_the_empty_state_with_count(self):
        """
        GIVEN 12 empty sessions and nothing else
        WHEN the creator opens Responses
        THEN the "No responses yet" state renders with "12 opened without answering" and Show
        """
        for _ in range(12):
            self._session(answered=False)
        response = self.client.get(self.url)
        self.assertContains(response, 'No responses yet')
        self.assertContains(response, '12 opened without answering')
        self.assertContains(response, 'rv2-empty-show')

    def test_table_hides_by_default_and_trash_ignores_the_choice(self):
        """
        GIVEN an answered session, a live empty session and a trashed empty session
        WHEN the table loads normally and in trash mode
        THEN the normal table lists only the answered one and trash lists the trashed empty one
        """
        answered = self._session()
        self._session(answered=False)
        trashed = self._session(answered=False, is_deleted=True)
        normal = self.client.get(self.table_url)
        self.assertEqual([r['session_id'] for r in normal.context['rows']], [answered.id])
        self.assertContains(normal, '1 opened without answering (hidden)')
        trash = self.client.get(self.table_url + '?trash=1')
        self.assertEqual([r['session_id'] for r in trash.context['rows']], [trashed.id])

    def test_shown_empty_row_has_no_number(self):
        """
        GIVEN an answered session and an empty one, empties shown
        WHEN the table renders
        THEN the answered row reads #1 and the empty row a dash
        """
        self._session()
        self._session(answered=False)
        self.client.cookies['rv2_show_empty'] = '1'
        html = self.client.get(self.table_url).content.decode()
        self.assertIn('#1', html)
        self.assertRegex(html, r'<td data-col="id">\s*—')

    @override_settings(RESPONSES_V2=False)
    def test_legacy_dashboard_lists_every_session(self):
        """
        GIVEN 1 answered and 1 empty session and RESPONSES_V2 off
        WHEN the legacy dashboard renders
        THEN it counts both
        """
        self._session()
        self._session(answered=False)
        self.assertEqual(self.client.get(self.url).context['total_sessions'], 2)


class EmptySessionExportTest(_EmptySessionFixture):
    """Every export format leaves empty sessions out."""

    def _download(self, **params):
        from urllib.parse import urlencode
        url = f'/surveys/{self.survey.uuid}/download'
        if params:
            url += '?' + urlencode(params)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        if hasattr(response, 'streaming_content'):
            return b''.join(response.streaming_content)
        return response.content

    def _sheet_session_ids(self, body):
        import openpyxl
        ws = openpyxl.load_workbook(BytesIO(body))['sessions']
        rows = list(ws.iter_rows(values_only=True))
        col = list(rows[0]).index('session_id')
        return {r[col] for r in rows[1:]}

    def test_xlsx_leaves_empties_out(self):
        """
        GIVEN 3 answered and 2 empty sessions
        WHEN the creator exports Excel
        THEN the sessions sheet has the 3 answered sessions
        """
        answered = {self._session().id for _ in range(3)}
        for _ in range(2):
            self._session(answered=False)
        self.assertEqual(self._sheet_session_ids(self._download(format='xlsx')), answered)

    def test_include_all_does_not_bring_them_back(self):
        """
        GIVEN an answered trashed session and an empty session
        WHEN the creator exports with include_all=1 and with completed_only=1 as well
        THEN the trashed answered one is present with include_all and the empty one never is
        """
        trashed = self._session(is_deleted=True)
        blank = self._session(answered=False)
        ids = self._sheet_session_ids(self._download(format='xlsx', include_all='1'))
        self.assertIn(trashed.id, ids)
        self.assertNotIn(blank.id, ids)
        ids = self._sheet_session_ids(self._download(format='xlsx', include_all='1', completed_only='1'))
        self.assertNotIn(blank.id, ids)

    def test_legacy_zip_and_csv_leave_empties_out(self):
        """
        GIVEN one answered and one empty session
        WHEN the creator downloads the legacy archive and the CSV format
        THEN neither carries the empty session's id
        """
        answered = self._session()
        blank = self._session(answered=False)
        for params in ({}, {'format': 'csv'}):
            with zipfile.ZipFile(BytesIO(self._download(**params))) as zf:
                text = ''.join(
                    zf.read(n).decode('utf-8-sig', 'ignore') for n in zf.namelist() if n.endswith('.csv')
                )
            self.assertRegex(text, rf'(^|[,\n"]){answered.id}([,\r\n"]|$)')
            self.assertNotRegex(text, rf'(^|[,\n"]){blank.id}([,\r\n"]|$)')

    @override_settings(RESPONSES_V2=True)
    def test_dialog_states_the_rule(self):
        """
        GIVEN a survey with responses
        WHEN the Responses page renders the export dialog
        THEN it says sessions without answers are never exported
        """
        self._session()
        response = self.client.get(self.url)
        self.assertContains(response, 'export-empty-note')


class EmptySessionWhitespaceTest(_EmptySessionFixture):
    """Whitespace-only values are blank in the section POST."""

    def _post(self, data):
        self.client.get('/surveys/empty_sess_survey/s1/')
        session_id = self.client.session['survey_session_id']
        response = self.client.post('/surveys/empty_sess_survey/s1/', data)
        self.assertLess(response.status_code, 500)
        return session_id

    def test_spaces_create_no_answer(self):
        """
        GIVEN a respondent on the section
        WHEN the only text field holds "   "
        THEN no answer is stored and the session stays empty
        """
        sid = self._post({'ES_T': '   '})
        self.assertFalse(Answer.objects.filter(survey_session_id=sid).exists())

    def test_spaces_in_number_do_not_crash(self):
        """
        GIVEN a respondent on the section
        WHEN the number field holds "  "
        THEN the POST does not fail and no answer is stored for it
        """
        sid = self._post({'ES_N': '  '})
        self.assertFalse(Answer.objects.filter(survey_session_id=sid, question=self.q_num).exists())

    def test_surrounding_spaces_trimmed(self):
        """
        GIVEN a respondent on the section
        WHEN the text field holds "  bus stop  " and the number " 4 "
        THEN the stored text is "bus stop" and the number 4
        """
        sid = self._post({'ES_T': '  bus stop  ', 'ES_N': ' 4 '})
        self.assertEqual(Answer.objects.get(survey_session_id=sid, question=self.q_text).text, 'bus stop')
        self.assertEqual(Answer.objects.get(survey_session_id=sid, question=self.q_num).numeric, 4)

    def test_object_answer_of_spaces_is_blank(self):
        """
        GIVEN posted object fields
        WHEN an object's text value is only spaces
        THEN the parser drops it and keeps the real value
        """
        from django.http import QueryDict
        from survey.views import _parse_object_fields, OBJECT_FIELD_PREFIX
        post = QueryDict(mutable=True)
        post.setlist(f'{OBJECT_FIELD_PREFIX}o-1__C1', ['   '])
        post.setlist(f'{OBJECT_FIELD_PREFIX}o-2__C1', [' ok '])
        self.assertEqual(_parse_object_fields(post), {'o-2': {'C1': [' ok ']}})
