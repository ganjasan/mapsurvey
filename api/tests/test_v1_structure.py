"""`rest-api-v1`: sections and questions -- order, choices, sub-questions, deletes."""
from django.test import TestCase

from survey.models import Answer, Question, SurveySection, SurveySession

from .helpers import LOCMEM, V1Client, make_pro_org, make_v1_survey, mint


@LOCMEM
class V1StructureTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner)
        self.api = V1Client(self.client, mint(self.owner)[0])
        self.base = f'/surveys/{self.survey.uuid}'

    def _q(self, name, **body):
        body = {'name': name, 'input_type': 'text_line', **body}
        response = self.api.post(f'{self.base}/sections/{self.section.pk}/questions', body)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def test_section_layout_controls(self):
        """
        GIVEN a section
        WHEN it is patched to image / right / third, and then with panel_width "wide"
        THEN the first is stored and returned; the second is 422 naming panel_width
        """
        response = self.api.patch(f'{self.base}/sections/{self.section.pk}',
                                  {'layout': 'image', 'panel_side': 'right', 'panel_width': 'third'})
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual((body['layout'], body['panel_side'], body['panel_width']), ('image', 'right', 'third'))
        self.assertIsNone(body['stage_image'])
        self.section.refresh_from_db()
        self.assertEqual(self.section.panel_side, 'right')

        response = self.api.patch(f'{self.base}/sections/{self.section.pk}', {'panel_width': 'wide'})
        self.assertEqual(response.status_code, 422, response.content)
        self.assertIn('panel_width', response.content.decode())

    def test_section_content_alignment(self):
        """
        GIVEN a section
        WHEN it is patched to a centred column in the middle, and then with content_valign "bottom"
        THEN the first is stored and returned; the second is 422 naming content_valign
        """
        response = self.api.patch(f'{self.base}/sections/{self.section.pk}',
                                  {'content_width': 'column', 'content_valign': 'middle'})
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual((body['content_width'], body['content_valign']), ('column', 'middle'))

        response = self.api.patch(f'{self.base}/sections/{self.section.pk}', {'content_valign': 'bottom'})
        self.assertEqual(response.status_code, 422, response.content)
        self.assertIn('content_valign', response.content.decode())

    def test_section_order(self):
        """
        GIVEN two sections
        WHEN they are reordered, and then a list missing one is sent
        THEN the order flips; the incomplete list is 422
        """
        second = self.api.post(f'{self.base}/sections', {'title': 'Second'}).json()
        response = self.api.put(f'{self.base}/sections/order', {'section_ids': [second['id'], self.section.pk]})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([s['id'] for s in response.json()], [second['id'], self.section.pk])
        self.assertEqual(self.api.put(f'{self.base}/sections/order', {'section_ids': [second['id']]}).status_code, 422)

    def test_question_order(self):
        """
        GIVEN two questions
        WHEN they are reordered by id
        THEN the response lists them in the new order
        """
        a, b = self._q('A'), self._q('B')
        response = self.api.put(f'{self.base}/sections/{self.section.pk}/questions/order', {'items': [b['id'], a['id']]})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([q['id'] for q in response.json()], [b['id'], a['id']])

    def test_choices_keep_codes_and_take_new_ones(self):
        """
        GIVEN a choice question with options 1 and 2
        WHEN its choices are replaced with 1 and a new 3
        THEN the question holds codes 1 and 3
        """
        q = self._q('Colour', input_type='choice', choices=[{'code': 1, 'name': 'Red'}, {'code': 2, 'name': 'Blue'}])
        response = self.api.put(f'{self.base}/questions/{q["id"]}/choices',
                                {'choices': [{'code': 1, 'name': 'Red'}, {'code': 3, 'name': 'Green'}]})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([c['code'] for c in response.json()['choices']], [1, 3])

    def test_subquestion_on_a_point_question(self):
        """
        GIVEN a point question and a text question
        WHEN a sub-question is added to each
        THEN the point question takes it; the text question is 422
        """
        point = self._q('Where?', input_type='point')
        text = self._q('Why?')
        sub = self.api.post(f'{self.base}/questions/{point["id"]}/subquestions', {'name': 'What is here?', 'input_type': 'text'})
        self.assertEqual(sub.status_code, 201, sub.content)
        self.assertEqual(sub.json()['parent_id'], point['id'])
        self.assertEqual(self.api.get(f'{self.base}/questions/{point["id"]}').json()['subquestions'], [sub.json()['id']])
        refused = self.api.post(f'{self.base}/questions/{text["id"]}/subquestions', {'name': 'x', 'input_type': 'text'})
        self.assertEqual(refused.status_code, 422)

    def test_delete_with_answers_needs_acknowledgement(self):
        """
        GIVEN a section whose question has an answer
        WHEN the section is deleted without and then with acknowledge_answer_loss
        THEN first 409 answers_at_risk with the count, then 204 and the section is gone
        """
        second = self.api.post(f'{self.base}/sections', {'title': 'Second'}).json()
        q = Question.objects.create(survey_section_id=second['id'], name='Q', input_type='text', order_number=1)
        Answer.objects.create(survey_session=SurveySession.objects.create(survey=self.survey), question=q, text='x')
        first = self.api.delete(f'{self.base}/sections/{second["id"]}')
        self.assertEqual(first.status_code, 409)
        self.assertEqual((first.json()['error'], first.json()['count']), ('answers_at_risk', 1))
        second_try = self.api.delete(f'{self.base}/sections/{second["id"]}?acknowledge_answer_loss=true')
        self.assertEqual(second_try.status_code, 204)
        self.assertFalse(SurveySection.objects.filter(pk=second['id']).exists())

    def test_patch_section_fields_and_translations(self):
        """
        GIVEN a bilingual survey
        WHEN a section's title and its German title are patched
        THEN both are stored and the response shows them
        """
        self.survey.available_languages = ['en', 'de']
        self.survey.save(update_fields=['available_languages'])
        response = self.api.patch(f'{self.base}/sections/{self.section.pk}',
                                  {'title': 'Your area', 'translations': {'de': {'title': 'Ihre Gegend'}}})
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body['title'], 'Your area')
        self.assertEqual(body['translations']['de']['title'], 'Ihre Gegend')
        self.assertEqual(body['code'], 'S1')
