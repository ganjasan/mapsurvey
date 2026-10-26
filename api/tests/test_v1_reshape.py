"""`rest-api-v1` (change api-v2-structure, #412): question groups, duplicates and
copies, moving a question, versions and restore, icon search."""
from django.contrib.gis.geos import Point
from django.test import TestCase

from survey.models import (
    Answer, AuditLog, LayerObject, Question, QuestionGroup, SurveyHeader, SurveyMapLayer, SurveySection,
    SurveySession,
)

from .helpers import LOCMEM, V1Client, make_member, make_pro_org, make_v1_survey, mint


@LOCMEM
class V1ReshapeTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner)
        self.api = V1Client(self.client, mint(self.owner)[0])
        self.base = f'/surveys/{self.survey.uuid}'

    def _q(self, name, section=None, **body):
        section = section or self.section
        response = self.api.post(f'{self.base}/sections/{section.pk}/questions',
                                 {'name': name, 'input_type': 'text_line', **body})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def _publish(self):
        self.survey.status = 'published'
        self.survey.save(update_fields=['status'])

    # ── groups ──

    def test_group_three_questions(self):
        """
        GIVEN four questions in a draft survey's section
        WHEN a group is posted with question_ids [q2, q3, q4]
        THEN 201 with those members, the section lists the group, q2 carries its group_id
        """
        q1, q2, q3, q4 = (self._q(f'Q{i}') for i in range(4))
        response = self.api.post(f'{self.base}/sections/{self.section.pk}/groups',
                                 {'title': 'About you', 'display_style': 'card',
                                  'question_ids': [q2['id'], q3['id'], q4['id']]})
        self.assertEqual(response.status_code, 201, response.content)
        group = response.json()
        self.assertEqual(group['question_ids'], [q2['id'], q3['id'], q4['id']])
        section = self.api.get(f'{self.base}/sections/{self.section.pk}').json()
        self.assertEqual(section['groups'], [group['id']])
        self.assertEqual(self.api.get(f'{self.base}/questions/{q2["id"]}').json()['group_id'], group['id'])
        listed = self.api.get(f'{self.base}/sections/{self.section.pk}/groups').json()
        self.assertEqual([g['id'] for g in listed], [group['id']])

    def test_live_survey_wording_in_place_structure_refused(self):
        """
        GIVEN a group on a published survey
        WHEN its title is patched, then a group is created
        THEN the title changes with a group_update audit row; the create is 409 draft_required
        """
        group = QuestionGroup.objects.create(survey_section=self.section, title='Old', order_number=5)
        self._publish()
        patched = self.api.patch(f'{self.base}/groups/{group.pk}', {'title': 'New'})
        self.assertEqual(patched.status_code, 200, patched.content)
        self.assertEqual(patched.json()['title'], 'New')
        self.assertTrue(AuditLog.objects.filter(action='group_update').exists())
        created = self.api.post(f'{self.base}/sections/{self.section.pk}/groups', {'title': 'X'})
        self.assertEqual(created.status_code, 409)
        self.assertEqual(created.json()['error'], 'draft_required')

    def test_delete_with_questions_guards_answers(self):
        """
        GIVEN a group whose member has an answer
        WHEN it is deleted with with_questions=true, without and then with the acknowledgement
        THEN 409 answers_at_risk first and nothing deleted; then 204 and both are gone
        """
        q = self._q('Member')
        group = self.api.post(f'{self.base}/sections/{self.section.pk}/groups',
                              {'title': 'G', 'question_ids': [q['id']]}).json()
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=session, question_id=q['id'], text='x')
        refused = self.api.delete(f'{self.base}/groups/{group["id"]}?with_questions=true')
        self.assertEqual(refused.status_code, 409)
        self.assertEqual(refused.json()['error'], 'answers_at_risk')
        self.assertTrue(Question.objects.filter(pk=q['id']).exists())
        done = self.api.delete(f'{self.base}/groups/{group["id"]}?with_questions=true&acknowledge_answer_loss=true')
        self.assertEqual(done.status_code, 204)
        self.assertFalse(Question.objects.filter(pk=q['id']).exists())
        self.assertFalse(QuestionGroup.objects.filter(pk=group['id']).exists())

    def test_group_of_another_survey_is_404(self):
        """
        GIVEN a group in another survey of the same owner
        WHEN it is read through this survey's path
        THEN 404
        """
        other, other_section = make_v1_survey(self.org, self.owner, name='other')
        group = QuestionGroup.objects.create(survey_section=other_section, title='G', order_number=1)
        self.assertEqual(self.api.get(f'{self.base}/groups/{group.pk}').status_code, 404)

    # ── duplicate and copy ──

    def test_duplicate_question_with_subquestions(self):
        """
        GIVEN a point question with two sub-questions
        WHEN it is duplicated
        THEN 201 with a new question right after it, " (copy)", new code, two copied sub-questions
        """
        point = self._q('Spot', input_type='point')
        for name in ('Why', 'When'):
            self.api.post(f'{self.base}/questions/{point["id"]}/subquestions', {'name': name, 'input_type': 'text'})
        response = self.api.post(f'{self.base}/questions/{point["id"]}/duplicate')
        self.assertEqual(response.status_code, 201, response.content)
        copy = response.json()
        self.assertEqual(copy['name'], 'Spot (copy)')
        self.assertNotEqual(copy['code'], point['code'])
        self.assertEqual(len(copy['subquestions']), 2)
        self.assertEqual(copy['order'], point['order'] + 1)

    def test_duplicate_section_and_copy_from_another_survey(self):
        """
        GIVEN a section with a question, and a second survey of the same owner
        WHEN the section is duplicated, and the question and the section are copied into the other survey
        THEN each is 201; the copies carry the content; an unreadable source is 404
        """
        q = self._q('Bench?')
        dup = self.api.post(f'{self.base}/sections/{self.section.pk}/duplicate')
        self.assertEqual(dup.status_code, 201, dup.content)
        self.assertEqual(dup.json()['title'], 'Section 1 (copy)')
        other, other_section = make_v1_survey(self.org, self.owner, name='other')
        obase = f'/surveys/{other.uuid}'
        copied = self.api.post(f'{obase}/sections/{other_section.pk}/questions/copy', {'source_question_id': q['id']})
        self.assertEqual(copied.status_code, 201, copied.content)
        self.assertEqual(copied.json()['name'], 'Bench?')
        section_copy = self.api.post(f'{obase}/sections/copy', {'source_section_id': self.section.pk})
        self.assertEqual(section_copy.status_code, 201, section_copy.content)
        self.assertEqual(SurveySection.objects.filter(survey_header=other).count(), 2)

        stranger_org, stranger = make_pro_org('Stranger Org', 'stranger')
        hidden, hidden_section = make_v1_survey(stranger_org, stranger, name='hidden')
        hidden_q = Question.objects.create(survey_section=hidden_section, code='HQ', name='h', input_type='text')
        refused = self.api.post(f'{obase}/sections/{other_section.pk}/questions/copy',
                                {'source_question_id': hidden_q.pk})
        self.assertEqual(refused.status_code, 404)

    def test_duplicate_survey_with_layer(self):
        """
        GIVEN a published survey with an Objects question bound to a 3-object layer and one response
        WHEN it is duplicated over the API
        THEN 201 with a new draft "(copy)" whose question is bound to its own 3-object layer, no sessions,
             and the counts in the body
        """
        layer = SurveyMapLayer.objects.create(survey=self.survey, name='Benches')
        for i in range(3):
            LayerObject.objects.create(layer=layer, key=f'b{i}', geometry=Point(13.4, 52.5 + i / 100))
        q = Question.objects.create(survey_section=self.section, code='OBJ', name='Benches',
                                    input_type='layer_objects', layer=layer, order_number=1)
        self._publish()
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=session, question=q, text='x')

        response = self.api.post(f'{self.base}/duplicate')
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body['status'], 'draft')
        self.assertEqual(body['name'], 'v1_survey (copy)')
        self.assertEqual((body['sections'], body['questions'], body['layers']), (1, 1, 1))
        copy = SurveyHeader.objects.get(uuid=body['uuid'])
        bound = Question.objects.get(survey_section__survey_header=copy, code='OBJ')
        self.assertEqual(bound.layer.survey_id, copy.pk)
        self.assertEqual(LayerObject.objects.filter(layer=bound.layer).count(), 3)
        self.assertFalse(SurveySession.objects.filter(survey=copy).exists())

    def test_duplicate_survey_needs_workspace_editor(self):
        """
        GIVEN a workspace viewer who can read the survey
        WHEN they duplicate it
        THEN 403 forbidden_role
        """
        viewer = make_member(self.org, 'ws_viewer', role='viewer')
        api = V1Client(self.client, mint(viewer)[0])
        response = api.post(f'{self.base}/duplicate')
        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(response.json()['error'], 'forbidden_role')

    # ── move ──

    def test_move_to_another_section_keeps_answers(self):
        """
        GIVEN an answered question and a second section with one question
        WHEN it is moved there with position 0
        THEN it is the first question of that section and its answer still exists
        """
        q = self._q('Moving')
        second = self.api.post(f'{self.base}/sections', {'title': 'Second'}).json()
        second_section = SurveySection.objects.get(pk=second['id'])
        existing = self._q('Already there', section=second_section)
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=session, question_id=q['id'], text='x')
        response = self.api.post(f'{self.base}/questions/{q["id"]}/move', {'section_id': second['id'], 'position': 0})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['question']['section_id'], second['id'])
        listed = self.api.get(f'{self.base}/sections/{second["id"]}').json()['questions']
        self.assertEqual(listed, [q['id'], existing['id']])
        self.assertEqual(Answer.objects.filter(question_id=q['id']).count(), 1)

    def test_move_into_popup_needs_acknowledgement(self):
        """
        GIVEN an answered text question and a point question
        WHEN the text question is moved into the point's pop-up without acknowledgement
        THEN 409 answers_at_risk and it is still top-level
        """
        q = self._q('Note')
        point = self._q('Spot', input_type='point')
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=session, question_id=q['id'], text='x')
        response = self.api.post(f'{self.base}/questions/{q["id"]}/move', {'parent_id': point['id']})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error'], 'answers_at_risk')
        self.assertIsNone(Question.objects.get(pk=q['id']).parent_question_id_id)

    # ── versions ──

    def test_versions_and_restore(self):
        """
        GIVEN a published survey at version 2 with archived version 1
        WHEN versions are listed and version 1 is restored
        THEN the list is [2 current, 1]; the restore is 201 with an unpublished-changes uuid, audited;
             a second restore is 409 conflict and an unknown version 404
        """
        self._publish()
        archived = SurveyHeader.objects.create(organization=self.org, name='v1_survey', status='closed',
                                               canonical_survey=self.survey, is_canonical=False, version_number=1)
        SurveySection.objects.create(survey_header=archived, name='old', title='Old', code='S1', is_head=True)
        self.survey.version_number = 2
        self.survey.save(update_fields=['version_number'])
        listed = self.api.get(f'{self.base}/versions')
        self.assertEqual(listed.status_code, 200, listed.content)
        self.assertEqual([(v['version'], v['current']) for v in listed.json()], [(2, True), (1, False)])
        self.assertEqual(self.api.post(f'{self.base}/versions/9/restore').status_code, 404)
        restored = self.api.post(f'{self.base}/versions/1/restore')
        self.assertEqual(restored.status_code, 201, restored.content)
        draft = SurveyHeader.objects.get(uuid=restored.json()['unpublished_changes'])
        self.assertEqual(list(SurveySection.objects.filter(survey_header=draft).values_list('title', flat=True)),
                         ['Old'])
        self.assertTrue(AuditLog.objects.filter(action='version_restore').exists())
        again = self.api.post(f'{self.base}/versions/1/restore')
        self.assertEqual(again.status_code, 409)
        self.assertEqual(again.json()['error'], 'conflict')

    # ── icons ──

    def test_icon_search(self):
        """
        GIVEN the icon catalog
        WHEN "скамейка" is searched in Russian, "bus" in the maki set, and nonsense
        THEN temaki:bench is found, every maki result is maki:…, and nonsense is an empty list
        """
        ru = self.api.get('/icons', {'q': 'скамейка', 'lang': 'ru'})
        self.assertEqual(ru.status_code, 200, ru.content)
        self.assertEqual(ru.json()[0]['value'], 'temaki:bench')
        maki = self.api.get('/icons', {'q': 'bus', 'set': 'maki'}).json()
        self.assertTrue(maki and all(i['value'].startswith('maki:') for i in maki))
        self.assertEqual(self.api.get('/icons', {'q': 'zzqqxx'}).json(), [])
        self.assertEqual(self.api.get('/icons', {'q': 'bus', 'set': 'nope'}).status_code, 422)
