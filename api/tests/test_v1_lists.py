"""`rest-api-v1`: cursor pagination, survey listing, responses."""
from django.contrib.gis.geos import Point
from django.test import TestCase

from survey.models import Answer, Question, SurveySession

from .helpers import LOCMEM, V1Client, make_pro_org, make_v1_survey, mint


@LOCMEM
class V1ListsTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner)
        self.q = Question.objects.create(survey_section=self.section, name='Where?', input_type='point',
                                         order_number=1, code='PT')
        self.sub = Question.objects.create(survey_section=self.section, name='Why?', input_type='text',
                                           order_number=1, code='WHY', parent_question_id=self.q)
        self.api = V1Client(self.client, mint(self.owner)[0])

    def _session(self, answered=True):
        session = SurveySession.objects.create(survey=self.survey)
        if answered:
            parent = Answer.objects.create(survey_session=session, question=self.q, point=Point(13.4, 52.5))
            Answer.objects.create(survey_session=session, question=self.sub, text='Shade',
                                  parent_answer_id=parent)
        return session

    def test_empty_sessions_hidden_by_default(self):
        """
        GIVEN one empty and one answered session
        WHEN responses are listed, then with include_empty
        THEN one item, then two; the answered one carries #1, its point and its nested sub-answer
        """
        self._session(answered=False)
        answered = self._session()
        items = self.api.get(f'/surveys/{self.survey.uuid}/responses').json()['items']
        self.assertEqual([i['id'] for i in items], [answered.pk])
        item = items[0]
        self.assertEqual(item['number'], 1)
        self.assertEqual(item['answers'][0]['geometry']['type'], 'Point')
        self.assertEqual(item['answers'][0]['answers'][0]['text'], 'Shade')
        self.assertNotIn('ip', str(item).lower().replace('ship', ''))
        everything = self.api.get(f'/surveys/{self.survey.uuid}/responses', {'include_empty': 'true'}).json()
        self.assertEqual(len(everything['items']), 2)

    def test_limit_is_clamped_and_cursor_pages(self):
        """
        GIVEN three answered sessions
        WHEN limit=10000 and then limit=2 with its next cursor
        THEN all three at once; then two and one, without overlap
        """
        ids = [self._session().pk for _ in range(3)]
        self.assertEqual(len(self.api.get(f'/surveys/{self.survey.uuid}/responses', {'limit': 10000}).json()['items']), 3)
        first = self.api.get(f'/surveys/{self.survey.uuid}/responses', {'limit': 2}).json()
        second = self.api.get(f'/surveys/{self.survey.uuid}/responses',
                              {'limit': 2, 'cursor': first['next_cursor']}).json()
        got = [i['id'] for i in first['items'] + second['items']]
        self.assertEqual(sorted(got), sorted(ids))
        self.assertIsNone(second['next_cursor'])

    def test_cursor_from_another_survey_is_400(self):
        """
        GIVEN a next_cursor from survey A's responses
        WHEN it is sent to survey B's responses, or tampered with
        THEN 400 bad_cursor
        """
        for _ in range(2):
            self._session()
        cursor = self.api.get(f'/surveys/{self.survey.uuid}/responses', {'limit': 1}).json()['next_cursor']
        other, _ = make_v1_survey(self.org, self.owner, 'other')
        response = self.api.get(f'/surveys/{other.uuid}/responses', {'cursor': cursor})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'bad_cursor')
        tampered = self.api.get(f'/surveys/{self.survey.uuid}/responses', {'cursor': cursor + 'x'})
        self.assertEqual(tampered.status_code, 400)

    def test_survey_list_counts_free_workspaces(self):
        """
        GIVEN the caller owns a Pro and a Free workspace (whose owners used their Pro trial), each with a survey
        WHEN surveys are listed
        THEN only the Pro survey is listed and hidden_by_plan is 1
        """
        from billing.tests.helpers import trial_used_elsewhere
        from survey.models import Membership
        from .helpers import make_free_org
        free, _ = make_free_org('Free', 'free_owner3')
        Membership.objects.create(user=self.owner, organization=free, role='owner')
        trial_used_elsewhere(free)
        make_v1_survey(free, self.owner, 'free_one')
        body = self.api.get('/surveys').json()
        self.assertEqual([s['name'] for s in body['items']], ['v1_survey'])
        self.assertEqual(body['hidden_by_plan'], 1)
