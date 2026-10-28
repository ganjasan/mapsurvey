"""Tests for the `survey-oembed` capability (openspec/specs/survey-oembed/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from survey.tests.helpers import _EmbedSurveyMixin


class OEmbedTest(_EmbedSurveyMixin, TestCase):

    def _call(self, survey, host='testserver', **params):
        query = {'url': f'http://{host}/surveys/{survey.uuid}/', 'format': 'json', **params}
        return self.client.get('/oembed/', query)

    def test_published_survey_resolves(self):
        """
        GIVEN a published survey
        WHEN the oEmbed endpoint is asked about its URL
        THEN a rich payload with the snippet comes back, readable cross-origin
        """
        survey = self._make_embed_survey()
        response = self._call(survey)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['type'], 'rich')
        self.assertEqual(payload['version'], '1.0')
        self.assertEqual(payload['title'], survey.name)
        self.assertEqual(payload['provider_name'], 'Mapsurvey')
        self.assertIn(f'/surveys/{survey.uuid}/?embed=1', payload['html'])
        # Iframely drops an oEmbed html that contains a script, so the payload is the bare iframe
        # with the size as attributes (what embed parsers read); the Share snippet keeps the script.
        self.assertNotIn('<script', payload['html'])
        self.assertIn('width="800" height="720"', payload['html'])
        self.assertEqual((payload['width'], payload['height']), (800, 720))
        self.assertEqual(response['Access-Control-Allow-Origin'], '*')

    def test_payload_uses_the_public_scheme_behind_the_proxy(self):
        """
        GIVEN a request forwarded over https
        WHEN the endpoint describes a survey
        THEN html and provider_url say https:// and the discovery link on the survey page does too
        """
        survey = self._make_embed_survey()
        payload = self.client.get(
            '/oembed/', {'url': f'https://testserver/surveys/{survey.uuid}/'}, HTTP_X_FORWARDED_PROTO='https',
        ).json()
        self.assertIn(f'https://testserver/surveys/{survey.uuid}/?embed=1', payload['html'])
        self.assertEqual(payload['provider_url'], 'https://testserver/')
        page = self.client.get(f'/surveys/{survey.uuid}/sec1/', HTTP_X_FORWARDED_PROTO='https')
        self.assertContains(page, 'href="https://testserver/oembed/?url=https%3A%2F%2Ftestserver%2Fsurveys%2F')

    def test_max_dimensions_are_honoured(self):
        """
        GIVEN maxwidth and maxheight
        WHEN the endpoint is called
        THEN width/height and the snippet use them
        """
        survey = self._make_embed_survey()
        payload = self._call(survey, maxwidth=600, maxheight=500).json()
        self.assertEqual((payload['width'], payload['height']), (600, 500))
        self.assertIn('width:600px', payload['html'])
        self.assertIn('height:500px', payload['html'])

    def test_unpublished_survey_is_not_described(self):
        """
        GIVEN draft, testing, closed and password-protected surveys
        WHEN the endpoint is asked about each
        THEN it answers 404 without the survey's name or UUID
        """
        surveys = [self._make_embed_survey(status=s, suffix=s) for s in ('draft', 'testing', 'closed')]
        locked = self._make_embed_survey(suffix='locked')
        locked.set_password('respondent-gate')
        locked.save()
        surveys.append(locked)
        for survey in surveys:
            response = self._call(survey)
            self.assertEqual(response.status_code, 404, survey.status)
            body = response.content.decode()
            self.assertNotIn(survey.name, body)
            self.assertNotIn(str(survey.uuid), body)

    def test_foreign_url_is_refused(self):
        """
        GIVEN a survey URL on another host
        WHEN the endpoint is called
        THEN it answers 404
        """
        survey = self._make_embed_survey()
        self.assertEqual(self._call(survey, host='other.example').status_code, 404)
        self.assertEqual(self.client.get('/oembed/', {'url': 'http://testserver/'}).status_code, 404)
        self.assertEqual(self.client.get('/oembed/').status_code, 404)

    def test_xml_is_not_offered(self):
        """
        GIVEN format=xml
        WHEN the endpoint is called
        THEN it answers 501
        """
        survey = self._make_embed_survey()
        self.assertEqual(self._call(survey, format='xml').status_code, 501)

    def test_discovery_link_on_a_published_survey(self):
        """
        GIVEN a published, password-free survey
        WHEN its first section is rendered
        THEN the head carries the oEmbed discovery link
        """
        survey = self._make_embed_survey()
        response = self.client.get(f'/surveys/{survey.uuid}/sec1/')
        self.assertContains(response, 'type="application/json+oembed"')
        self.assertContains(response, '/oembed/?url=')

    def test_no_discovery_link_on_a_password_protected_survey(self):
        """
        GIVEN a published survey with a password
        WHEN its owner (who bypasses the gate) renders the first section
        THEN the head carries no oEmbed discovery link
        """
        survey = self._make_embed_survey()
        survey.set_password('respondent-gate')
        survey.save()
        self.client.login(username='embed_owner', password='pass')
        response = self.client.get(f'/surveys/{survey.uuid}/sec1/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'application/json+oembed')
