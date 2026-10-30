"""`rest-api-v1`: input schemas are allow-lists, rich text and redirects go
through the editor's own rules, rules are checked strictly."""
from django.test import TestCase

from survey.models import Question, SurveyHeader

from .helpers import LOCMEM, V1Client, make_pro_org, make_v1_survey, mint


@LOCMEM
class V1SchemasTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner)
        self.token, _ = mint(self.owner)
        self.api = V1Client(self.client, self.token)
        self.base = f'/surveys/{self.survey.uuid}'

    def _question(self, **body):
        body.setdefault('name', 'Q')
        body.setdefault('input_type', 'text_line')
        response = self.api.post(f'{self.base}/sections/{self.section.pk}/questions', body)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def test_forbidden_fields_are_refused_by_name(self):
        """
        GIVEN a PATCH carrying organization, status and owner beside a name
        WHEN it is sent
        THEN 422 validation names the three fields and nothing changes
        """
        response = self.api.patch(self.base, {'name': 'renamed', 'organization': 5, 'status': 'published',
                                              'owner': 1})
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body['error'], 'validation')
        self.assertTrue({'organization', 'status', 'owner'} <= set(body['fields']))
        self.survey.refresh_from_db()
        self.assertEqual((self.survey.name, self.survey.status), ('v1_survey', 'draft'))

    def test_geojson_gz_is_not_a_question_field(self):
        """
        GIVEN a question create carrying geojson_gz
        WHEN it is sent
        THEN 422 and no question exists
        """
        response = self.api.post(f'{self.base}/sections/{self.section.pk}/questions',
                                 {'name': 'Q', 'input_type': 'text', 'geojson_gz': 'x'})
        self.assertEqual(response.status_code, 422)
        self.assertIn('geojson_gz', response.json()['fields'])
        self.assertFalse(Question.objects.exists())

    def test_script_in_subtext_matches_the_editor(self):
        """
        GIVEN subtext with a script and markup
        WHEN it is saved through the API and through the editor form
        THEN both rows hold the same sanitised bytes
        """
        dirty = '<script>alert(1)</script><b>ok</b>'
        created = self._question(subtext=dirty)
        self.client.force_login(self.owner)
        self.client.post(f'/editor/surveys/{self.survey.uuid}/sections/{self.section.pk}/questions/new/',
                         {'name': 'Editor', 'input_type': 'text_line', 'color': '#000000', 'subtext': dirty})
        self.assertEqual(created['subtext'], Question.objects.get(name='Editor').subtext)
        self.assertNotIn('<script', created['subtext'])

    def test_bad_redirects_are_refused(self):
        """
        GIVEN "#https://…", "javascript:alert(1)" and "#thanks"
        WHEN each is set as redirect_url
        THEN each is 422 on redirect_url and the stored value stays "#"
        """
        for value in ('#https://example.org', 'javascript:alert(1)', '#thanks'):
            response = self.api.patch(self.base, {'redirect_url': value})
            self.assertEqual(response.status_code, 422, value)
            self.assertIn('redirect_url', response.json()['fields'])
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.redirect_url, '#')
        self.assertEqual(self.api.patch(self.base, {'redirect_url': 'https://example.org/done'}).status_code, 200)

    def test_rule_naming_a_later_question_is_refused(self):
        """
        GIVEN a text question followed by a choice question
        WHEN the first is given a rule controlled by the second
        THEN 422 on visibility_rule
        """
        first = self._question(name='First')
        self._question(name='Later', input_type='choice', choices=[{'code': 1, 'name': 'Yes'}])
        later = Question.objects.get(name='Later')
        response = self.api.patch(f'{self.base}/questions/{first["id"]}',
                                  {'visibility_rule': {'question_code': later.code, 'choice_codes': [1]}})
        self.assertEqual(response.status_code, 422)
        self.assertIn('visibility_rule', response.json()['fields'])

    def test_unknown_input_type_refused(self):
        """
        GIVEN an input_type that does not exist
        WHEN a question is created with it
        THEN 422 on input_type
        """
        response = self.api.post(f'{self.base}/sections/{self.section.pk}/questions',
                                 {'name': 'Q', 'input_type': 'teleport'})
        self.assertEqual(response.status_code, 422)
        self.assertIn('input_type', response.json()['fields'])

    def test_create_fill_publish(self):
        """
        GIVEN a Pro owner token with every scope
        WHEN it creates a survey, adds a choice question to its section and publishes
        THEN the survey is published and its public URL is in the response
        """
        response = self.api.post('/surveys', {'name': 'From the API', 'workspace': self.org.slug})
        self.assertEqual(response.status_code, 201, response.content)
        created = response.json()
        section_id = created['sections'][0]
        q = self.api.post(f'/surveys/{created["uuid"]}/sections/{section_id}/questions',
                          {'name': 'Colour?', 'input_type': 'choice',
                           'choices': [{'code': 1, 'name': 'Red'}, {'code': 2, 'name': 'Blue'}]})
        self.assertEqual(q.status_code, 201, q.content)
        self.assertEqual([c['code'] for c in q.json()['choices']], [1, 2])
        published = self.api.post(f'/surveys/{created["uuid"]}/publish', {})
        self.assertEqual(published.status_code, 200, published.content)
        self.assertEqual(published.json()['status'], 'published')
        self.assertIsNone(published.json()['review'])
        self.assertIn(f'/surveys/{created["uuid"]}/', published.json()['url'])
        self.assertTrue(SurveyHeader.objects.get(uuid=created['uuid']).collaborators.filter(user=self.owner).exists())


class V1SurveyPeriodTest(TestCase):
    """rest-api-v1: Survey period over the API (change survey-schedule)."""

    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner, status='published')
        self.token, _ = mint(self.owner)
        self.api = V1Client(self.client, self.token)
        self.base = f'/surveys/{self.survey.uuid}'

    @staticmethod
    def _instant(days, hours=0):
        from datetime import timedelta
        from django.utils import timezone
        return (timezone.now() + timedelta(days=days, hours=hours)).replace(second=0, microsecond=0)

    @staticmethod
    def _parse(value):
        from datetime import datetime
        return datetime.fromisoformat(value.replace('Z', '+00:00')) if value else None

    def test_read_and_set(self):
        """
        GIVEN an owner token
        WHEN it PATCHes opens_at and closes_at with a +06:00 offset and the Bishkek zone
        THEN the response and the list carry the same instants in UTC and the zone
        """
        from zoneinfo import ZoneInfo
        opens, closes = self._instant(3), self._instant(30)
        tz = ZoneInfo('Asia/Bishkek')
        response = self.api.patch(self.base, {
            'opens_at': opens.astimezone(tz).isoformat(),
            'closes_at': closes.astimezone(tz).isoformat(),
            'schedule_timezone': 'Asia/Bishkek'})
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual((self._parse(body['opens_at']), self._parse(body['closes_at'])), (opens, closes))
        self.assertTrue(body['opens_at'].endswith('Z') or body['opens_at'].endswith('+00:00'))
        self.assertEqual(body['schedule_timezone'], 'Asia/Bishkek')
        listed = self.api.get('/surveys').json()['items'][0]
        self.assertEqual(self._parse(listed['closes_at']), closes)

    def test_clear_the_end(self):
        """
        GIVEN a survey with both ends
        WHEN closes_at is PATCHed to null
        THEN closes_at is null and opens_at unchanged
        """
        opens, closes = self._instant(-1), self._instant(5)
        SurveyHeader.objects.filter(pk=self.survey.pk).update(opens_at=opens, closes_at=closes)
        response = self.api.patch(self.base, {'closes_at': None})
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertIsNone(body['closes_at'])
        self.assertEqual(self._parse(body['opens_at']), opens)

    def test_invalid_order(self):
        """
        GIVEN a stored opens_at ten days ahead
        WHEN a PATCH sets closes_at five days ahead
        THEN the response is 422 validation naming closes_at and nothing is stored
        """
        SurveyHeader.objects.filter(pk=self.survey.pk).update(opens_at=self._instant(10))
        response = self.api.patch(self.base, {'closes_at': self._instant(5).isoformat()})
        self.assertEqual(response.status_code, 422, response.content)
        self.assertIn('closes_at', response.json()['fields'])
        self.survey.refresh_from_db()
        self.assertIsNone(self.survey.closes_at)

    def test_unpublished_changes_write_to_the_live_survey(self):
        """
        GIVEN a published survey with unpublished changes
        WHEN a PATCH on the draft's uuid sets closes_at
        THEN the canonical survey holds it and the draft row holds nothing
        """
        from survey.services import publishing as svc_publishing
        from survey.services.context import Actor
        draft = svc_publishing.create_draft(Actor(user=self.owner), self.survey)
        closes = self._instant(8)
        response = self.api.patch(f'/surveys/{draft.uuid}', {'closes_at': closes.isoformat()})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self._parse(response.json()['closes_at']), closes)
        self.survey.refresh_from_db()
        draft.refresh_from_db()
        self.assertEqual(self.survey.closes_at, closes)
        self.assertIsNone(draft.closes_at)
