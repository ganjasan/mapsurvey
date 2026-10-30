"""`rest-api-v1` (change api-v2-responses, #409): summary, text answers, one
question's GeoJSON, the signed export link and moderation."""
from datetime import timedelta
from unittest import mock

from django.contrib.gis.geos import Point, Polygon
from django.core import signing
from django.test import TestCase
from django.utils import timezone

from survey.models import Answer, AuditLog, Question, SurveySession

from .. import scopes
from .helpers import LOCMEM, V1Client, make_member, make_pro_org, make_v1_survey, mint


def _square(x, y):
    return Polygon(((x, y), (x + .01, y), (x + .01, y + .01), (x, y + .01), (x, y)))


@LOCMEM
class ResponsesApiTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner, status='published')
        self.choice = Question.objects.create(
            survey_section=self.section, name='Mode', input_type='choice', order_number=1, code='MODE',
            choices=[{'code': 1, 'name': 'Walk'}, {'code': 2, 'name': 'Bus'}, {'code': 9, 'name': 'Other', 'other': True}])
        self.text = Question.objects.create(survey_section=self.section, name='Why', input_type='text',
                                            order_number=2, code='WHY')
        self.area = Question.objects.create(survey_section=self.section, name='Area', input_type='polygon',
                                            order_number=3, code='AREA')
        self.need = Question.objects.create(
            survey_section=self.section, name='What is needed', input_type='multichoice', order_number=1,
            code='NEED', parent_question_id=self.area,
            choices=[{'code': 1, 'name': 'Light'}, {'code': 2, 'name': 'Trees'}])
        self.sessions = []
        for i, (choice, write_in, why) in enumerate([([1], None, 'safer'), ([1], None, ''),
                                                    ([9], 'bike lane', 'shade'), ([9], 'Bike  lane ', None)]):
            s = SurveySession.objects.create(survey=self.survey)
            Answer.objects.create(survey_session=s, question=self.choice, selected_choices=choice, text=write_in)
            if why is not None:
                Answer.objects.create(survey_session=s, question=self.text, text=why)
            geo = Answer.objects.create(survey_session=s, question=self.area, polygon=_square(13.4 + i / 100, 52.5))
            if i < 3:
                Answer.objects.create(survey_session=s, question=self.need, parent_answer_id=geo,
                                      selected_choices=[1] if i else [1, 2])
            self.sessions.append(s)
        SurveySession.objects.create(survey=self.survey)   # empty: never counted
        self.api = V1Client(self.client, mint(self.owner)[0])
        self.base = f'/surveys/{self.survey.uuid}'

    def _summary(self, **params):
        response = self.api.get(f'{self.base}/responses/summary', params or None)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def _entry(self, summary, code):
        return next(q for q in summary['questions'] if q['code'] == code)

    # ── summary ──

    def test_summary_counts_choices_and_write_ins(self):
        """
        GIVEN four answered sessions and one empty, two of them writing in "bike lane" variants
        WHEN the summary is asked
        THEN responses is 4, Walk and Other count 2 each, and the write-ins merge into one text with count 2
        """
        data = self._summary()
        self.assertEqual(data['responses'], 4)
        mode = self._entry(data, 'MODE')
        counts = {c['code']: c['count'] for c in mode['choices']}
        self.assertEqual(counts, {1: 2, 2: 0, 9: 2})
        self.assertEqual(mode['other_texts'], [{'text': 'bike lane', 'count': 2}])

    def test_subquestions_are_nested_under_the_map_question(self):
        """
        GIVEN a polygon question with four features and a multichoice sub-question answered on three
        WHEN the summary is asked
        THEN the polygon entry has features 4 and a nested entry for the sub-question with its counts
        """
        area = self._entry(self._summary(), 'AREA')
        self.assertEqual(area['features'], 4)
        need = area['subquestions'][0]
        self.assertEqual(need['code'], 'NEED')
        self.assertEqual(need['answered'], 3)
        self.assertEqual({c['code']: c['count'] for c in need['choices']}, {1: 3, 2: 1})

    def test_rejected_response_leaves_the_numbers(self):
        """
        GIVEN one of the four responses is not_approved
        WHEN the summary is asked with and without include_all
        THEN it reports 3, and 4 with include_all
        """
        self.sessions[0].validation_status = 'not_approved'
        self.sessions[0].save()
        self.assertEqual(self._summary()['responses'], 3)
        self.assertEqual(self._summary(include_all='true')['responses'], 4)
        self.assertEqual({c['code']: c['count'] for c in self._entry(self._summary(), 'MODE')['choices']}[1], 1)

    def test_scope_is_the_exports_session_set(self):
        """
        GIVEN answered, empty, rejected and trashed sessions
        WHEN the response scope and the export's exclusions are computed for each flag combination
        THEN the scope is exactly the sessions the export keeps
        """
        from survey import export
        from survey.response_scope import responses_scope
        self.sessions[0].validation_status = 'not_approved'
        self.sessions[0].save()
        self.sessions[1].is_deleted = True
        self.sessions[1].save()
        for include_all in (False, True):
            for completed_only in (False, True):
                parts = export.version_parts(self.survey, None)
                excluded = export.excluded_sessions(parts, include_all, completed_only)
                everything = set(SurveySession.objects.filter(survey=self.survey).values_list('id', flat=True))
                scope = responses_scope(self.survey, None, include_all, completed_only)
                self.assertEqual(set(scope.sessions.values_list('id', flat=True)), everything - excluded,
                                 (include_all, completed_only))

    def test_viewer_reads_outsider_does_not(self):
        """
        GIVEN a workspace viewer and a user from elsewhere
        WHEN each asks for the summary
        THEN the viewer gets 200 and the outsider 404
        """
        viewer = make_member(self.org, 'resp_viewer', role='viewer')
        self.assertEqual(self.api.get(f'{self.base}/responses/summary', token=mint(viewer)[0]).status_code, 200)
        _org, stranger = make_pro_org('Other Org', 'resp_stranger')
        self.assertEqual(self.api.get(f'{self.base}/responses/summary', token=mint(stranger)[0]).status_code, 404)

    def test_summary_needs_responses_read(self):
        """
        GIVEN a token without responses:read
        WHEN it asks for the summary
        THEN 403 scope_missing
        """
        token = mint(self.owner, scopes_=(scopes.SURVEYS_READ,))[0]
        response = self.api.get(f'{self.base}/responses/summary', token=token)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['error'], 'scope_missing')

    # ── text answers ──

    def test_text_answers_are_paged_and_skip_blanks(self):
        """
        GIVEN two non-blank text answers and one blank
        WHEN they are listed one at a time
        THEN two pages carry the two texts with their response numbers, and the second page ends the list
        """
        url = f'{self.base}/questions/{self.text.pk}/answers'
        first = self.api.get(url, {'limit': 1}).json()
        self.assertEqual(len(first['items']), 1)
        second = self.api.get(url, {'limit': 1, 'cursor': first['next_cursor']}).json()
        self.assertIsNone(second['next_cursor'])
        items = first['items'] + second['items']
        self.assertEqual({i['text'] for i in items}, {'safer', 'shade'})
        self.assertTrue(all(i['number'] for i in items))

    def test_text_answers_refuse_a_choice_question(self):
        """
        GIVEN a choice question
        WHEN its text answers are asked
        THEN 400 validation
        """
        response = self.api.get(f'{self.base}/questions/{self.choice.pk}/answers')
        self.assertEqual(response.status_code, 400)

    # ── GeoJSON ──

    def test_geojson_has_the_export_properties(self):
        """
        GIVEN a polygon question with a sub-question "What is needed"
        WHEN its GeoJSON is fetched
        THEN there are four features, each with the sub-question property, validation_status, and not truncated
        """
        data = self.api.get(f'{self.base}/questions/{self.area.pk}/geojson').json()
        self.assertEqual(data['type'], 'FeatureCollection')
        self.assertEqual(len(data['features']), 4)
        self.assertFalse(data['truncated'])
        props = data['features'][0]['properties']
        self.assertIn('What is needed', props)
        self.assertIn('validation_status', props)

    def test_geojson_stops_at_the_limit(self):
        """
        GIVEN a limit of 2 features
        WHEN the GeoJSON of four features is fetched
        THEN two features come back with truncated true
        """
        with mock.patch('api.v1.responses.GEOJSON_LIMIT', 2):
            data = self.api.get(f'{self.base}/questions/{self.area.pk}/geojson').json()
        self.assertEqual(len(data['features']), 2)
        self.assertTrue(data['truncated'])

    def test_geojson_refuses_a_non_map_question(self):
        """
        GIVEN a text question
        WHEN its GeoJSON is asked
        THEN 400 validation
        """
        self.assertEqual(self.api.get(f'{self.base}/questions/{self.text.pk}/geojson').status_code, 400)

    # ── export link ──

    def _link(self, **body):
        response = self.api.post(f'{self.base}/export-link', body)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()['url']

    def test_export_link_downloads_without_a_bearer(self):
        """
        GIVEN an export link for xlsx
        WHEN it is opened without any Authorization header
        THEN the workbook is returned and data_exported says api_link
        """
        url = self._link(format='xlsx')
        path = url.split('://', 1)[1].split('/', 1)[1]
        with mock.patch('survey.product_events.emit') as emit:
            response = self.client.get('/' + path)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b''.join(response.streaming_content).startswith(b'PK'))
        emit.assert_any_call('data_exported', self.owner.pk,
                             {'survey_id': str(self.survey.id), 'format': 'xlsx', 'surface': 'api_link'})

    def _path(self, url):
        return '/' + url.split('://', 1)[1].split('/', 1)[1]

    def test_a_version_list_scopes_the_summary_and_the_export_link(self):
        """
        GIVEN the canonical survey as v3 with four answered sessions and archived v2 and v1 with one each
        WHEN the summary is asked for `v3,v2` and an export link is made for `v2,v3`
        THEN the summary counts 5, the link carries the list, and the whole family still counts 6
        """
        from survey.models import SurveyHeader, SurveySection
        self.survey.version_number = 3
        self.survey.save(update_fields=['version_number'])
        for num in (2, 1):
            old = SurveyHeader.objects.create(name=self.survey.name, organization=self.org, status='closed',
                                              is_canonical=False, canonical_survey=self.survey, version_number=num)
            section = SurveySection.objects.create(survey_header=old, name='S', code='S1', is_head=True)
            why = Question.objects.create(survey_section=section, name='Why', input_type='text',
                                          order_number=1, code='WHY')
            Answer.objects.create(survey_session=SurveySession.objects.create(survey=old), question=why,
                                  text=f'answer of v{num}')
        self.assertEqual(self._summary(version='v3,v2')['responses'], 5)
        self.assertEqual(self._summary()['responses'], 6)
        token = self._link(format='csv', version='v2,v3').rsplit('/export-links/', 1)[1].strip('/')
        from api.v1.responses import LINK_SALT
        self.assertEqual(signing.loads(token, salt=LINK_SALT)['v'], 'v2,v3')

    def test_link_after_revocation_is_404(self):
        """
        GIVEN a link created with a token that is then revoked
        WHEN the link is opened
        THEN 404
        """
        value, profile = mint(self.owner)
        response = self.api.post(f'{self.base}/export-link', {'format': 'csv'}, token=value)
        path = self._path(response.json()['url'])
        profile.revoked_at = timezone.now()
        profile.save()
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_expired_or_tampered_link_is_404(self):
        """
        GIVEN a link opened 16 minutes later, and a link with a changed character
        WHEN each is opened
        THEN both are 404
        """
        path = self._path(self._link(format='csv'))
        later = timezone.now() + timedelta(minutes=16)
        with mock.patch('django.core.signing.time.time', return_value=later.timestamp()):
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.get(path[:-3] + 'xyz').status_code, 404)

    def test_link_rechecks_access(self):
        """
        GIVEN a viewer's link, after which the viewer loses their membership
        WHEN the link is opened
        THEN 404
        """
        viewer = make_member(self.org, 'link_viewer', role='viewer')
        value = mint(viewer)[0]
        path = self._path(self.api.post(f'{self.base}/export-link', {'format': 'csv'}, token=value).json()['url'])
        viewer.memberships.all().delete()
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_unknown_format_is_refused(self):
        """
        GIVEN an unknown format
        WHEN a link is asked for
        THEN 422 (the schema lists the formats)
        """
        response = self.api.post(f'{self.base}/export-link', {'format': 'docx'})
        self.assertIn(response.status_code, (400, 422))

    # ── moderation ──

    def test_reject_a_response(self):
        """
        GIVEN an editor token with responses:moderate
        WHEN it sets not_approved on a response
        THEN the status changes, an audit row records old and new, and the summary drops it
        """
        session = self.sessions[1]
        response = self.api.patch(f'{self.base}/responses/{session.pk}', {'validation_status': 'not_approved'})
        self.assertEqual(response.status_code, 200, response.content)
        session.refresh_from_db()
        self.assertEqual(session.validation_status, 'not_approved')
        row = AuditLog.objects.get(action='response_status')
        self.assertEqual(row.metadata['session_id'], session.pk)
        self.assertEqual(row.metadata['new'], 'not_approved')
        self.assertEqual(self._summary()['responses'], 3)

    def test_read_only_token_cannot_moderate(self):
        """
        GIVEN a token with only responses:read
        WHEN it sends the PATCH
        THEN 403 scope_missing naming responses:moderate
        """
        token = mint(self.owner, scopes_=(scopes.RESPONSES_READ,))[0]
        response = self.api.patch(f'{self.base}/responses/{self.sessions[0].pk}',
                                  {'validation_status': 'approved'}, token=token)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['scope'], 'responses:moderate')

    def test_viewer_cannot_moderate_and_foreign_session_is_404(self):
        """
        GIVEN a viewer with responses:moderate, and a session of another survey
        WHEN each PATCH is sent
        THEN the viewer gets 403 forbidden_role and the foreign session 404
        """
        viewer = make_member(self.org, 'mod_viewer', role='viewer')
        response = self.api.patch(f'{self.base}/responses/{self.sessions[0].pk}',
                                  {'validation_status': 'approved'}, token=mint(viewer)[0])
        self.assertEqual(response.status_code, 403)
        other, _ = make_v1_survey(self.org, self.owner, name='other_survey')
        foreign = SurveySession.objects.create(survey=other)
        response = self.api.patch(f'{self.base}/responses/{foreign.pk}', {'validation_status': 'approved'})
        self.assertEqual(response.status_code, 404)


class EditorStatusAuditTest(TestCase):
    def test_editor_status_change_is_audited(self):
        """
        GIVEN the Responses page's status action
        WHEN an editor sets on_hold
        THEN the same response_status audit row is written
        """
        org, owner = make_pro_org()
        survey, _section = make_v1_survey(org, owner)
        session = SurveySession.objects.create(survey=survey)
        self.client.force_login(owner)
        response = self.client.post(f'/editor/surveys/{survey.uuid}/analytics/sessions/{session.pk}/status/',
                                    {'validation_status': 'on_hold'})
        self.assertIn(response.status_code, (204, 302))
        row = AuditLog.objects.filter(action='response_status').first()
        self.assertIsNotNone(row)
        self.assertEqual(row.metadata['new'], 'on_hold')
