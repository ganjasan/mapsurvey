"""Tests for the `ranking-question` capability (openspec/specs/ranking-question/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from io import BytesIO
import json
import zipfile
from survey.models import SurveyHeader, SurveySection, Question, Answer, Membership
from survey.analytics import SurveyAnalyticsService
from survey.tests.helpers import _make_org


class RankingQuestionTest(TestCase):
    """The ranking question: a strict total order, enforced (change ranking-question)."""

    ITEMS = ['Pineapple on pizza', 'Cream in Carbonara', 'Cutting spaghetti']

    def setUp(self):
        self.org = _make_org('RankingOrg')
        self.user = User.objects.create_user('rankinguser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='ranking_survey', organization=self.org, created_by=self.user,
            status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.question = Question.objects.create(
            survey_section=self.section, name='Worst food crime', code='q_rank',
            input_type='ranking', order_number=1,
            choices=[{"code": i, "name": name} for i, name in enumerate(self.ITEMS, start=1)],
        )

    def _open(self):
        return self.client.get(f'/surveys/{self.survey.uuid}/s1/')

    def _submit(self, order):
        return self.client.post(f'/surveys/{self.survey.uuid}/s1/', {'q_rank': order})

    def test_items_render_in_the_creators_order(self):
        """
        GIVEN a ranking question the respondent has not answered
        WHEN the section opens
        THEN the items appear in the order the creator defined
        """
        content = self._open().content.decode()

        positions = [content.index(name) for name in self.ITEMS]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('data-ranking', content)

    def test_a_submitted_order_is_stored_as_the_permutation(self):
        """
        GIVEN a respondent who drags the third item to the top
        WHEN the section is submitted
        THEN the stored answer is the codes in the respondent's order
        """
        self._open()
        self._submit(['3', '1', '2'])

        answer = Answer.objects.get(question=self.question)
        self.assertEqual(answer.selected_choices, [3, 1, 2])

    def test_the_order_round_trips_on_the_way_back(self):
        """
        GIVEN a respondent who already ranked the items
        WHEN they navigate back to the section
        THEN the items render in the order they left them
        """
        self._open()
        self._submit(['3', '1', '2'])

        content = self._open().content.decode()

        self.assertLess(content.index(self.ITEMS[2]), content.index(self.ITEMS[0]))
        self.assertLess(content.index(self.ITEMS[0]), content.index(self.ITEMS[1]))

    def test_only_a_permutation_is_stored(self):
        """
        GIVEN submissions that are not permutations of the question's items
        WHEN each is submitted
        THEN nothing is stored and the section still submits

        The widget cannot produce these, so they are tampering or a bug; a
        half-order stored as if it were an answer would be worse than none.
        """
        cases = {
            'repeated item': ['1', '1', '2'],
            'missing item': ['1', '2'],
            'unknown code': ['1', '2', '99'],
            'extra item': ['1', '2', '3', '3'],
            'empty': [],
        }
        for label, order in cases.items():
            with self.subTest(case=label):
                Answer.objects.all().delete()
                self._open()

                response = self._submit(order)

                self.assertIn(response.status_code, (200, 302))
                self.assertFalse(Answer.objects.filter(question=self.question).exists())

    def test_export_gives_one_column_per_item_holding_its_rank(self):
        """
        GIVEN a respondent who ranked the three items
        WHEN the creator exports the survey
        THEN the CSV carries one column per item, valued by that item's rank
        """
        self._open()
        self._submit(['3', '1', '2'])

        self.client.login(username='rankinguser', password='pass')
        response = self.client.get(f'/surveys/{self.survey.uuid}/download')
        with zipfile.ZipFile(BytesIO(response.content), 'r') as zf:
            csv_name = [n for n in zf.namelist() if n.endswith('.csv')][0]
            csv_text = zf.read(csv_name).decode('utf-8')

        header, row = csv_text.split('\n')[0], csv_text.split('\n')[1]
        for name in self.ITEMS:
            self.assertIn(f'Worst food crime: {name}', header)
        # Cutting spaghetti was dragged to the top, so it ranks 1.
        columns = header.split(',')
        values = row.split(',')
        rank_of = dict(zip(columns, values))
        self.assertEqual(rank_of['Worst food crime: Cutting spaghetti'], '1')
        self.assertEqual(rank_of['Worst food crime: Pineapple on pizza'], '2')
        self.assertEqual(rank_of['Worst food crime: Cream in Carbonara'], '3')

    def test_analytics_does_not_break_on_the_new_type(self):
        """
        GIVEN a ranking question with an answer
        WHEN the analytics dashboard computes its stats
        THEN it reports an answer count rather than failing

        A rank-aware chart is a follow-up; not crashing is this change's bar.
        """
        from survey.analytics import SurveyAnalyticsService

        self._open()
        self._submit(['3', '1', '2'])

        stats = SurveyAnalyticsService(self.survey).get_question_stats(self.question)

        self.assertEqual(stats['type'], 'other')
        self.assertEqual(stats['total_answers'], 1)

    def test_live_preview_renders_a_ranking_draft(self):
        """
        GIVEN the question dialog's live preview
        WHEN a ranking draft with three items is posted
        THEN the preview renders the draggable list
        """
        self.client.force_login(self.user)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/question-preview/',
            {'input_type': 'ranking', 'name': 'Worst food crime',
             'choices_json': json.dumps([{"code": i, "name": n}
                                         for i, n in enumerate(self.ITEMS, start=1)])},
        )

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('data-ranking', html)
        for name in self.ITEMS:
            self.assertIn(name, html)


class RankingEmptyAndExampleTest(TestCase):
    """A ranking with no items, and where animation is allowed to run."""

    def setUp(self):
        self.org = _make_org('RankingEmptyOrg')
        self.user = User.objects.create_user('rankempty', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='ranking_empty', organization=self.org, created_by=self.user, status='draft',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.url = f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/question-preview/'

    def test_a_ranking_without_items_says_what_is_missing(self):
        """
        GIVEN a ranking draft the creator has just picked, with no items yet
        WHEN the preview renders
        THEN it points at the Choices editor instead of showing a drag hint
             over an empty list
        """
        html = self.client.post(self.url, {
            'input_type': 'ranking', 'name': 'Order these', 'choices_json': '',
        }).content.decode()

        self.assertIn('ranking__empty', html)
        self.assertNotIn('ranking__hint', html)

    def test_type_examples_may_animate_and_the_pane_may_not(self):
        """
        GIVEN the same draft rendered as a type example and as the live pane
        WHEN each is requested
        THEN only the example carries the class the animations key on

        The pane shows the creator's own question while they type into it; a
        question that fidgets under the cursor is worse than a still one.
        """
        example = self.client.post(self.url, {
            'input_type': 'ranking', 'name': 'Order these', 'example': '1',
            'choices_json': '[{"code":1,"name":"Apples"},{"code":2,"name":"Bananas"}]',
        }).content.decode()
        pane = self.client.post(self.url, {
            'input_type': 'ranking', 'name': 'Order these',
            'choices_json': '[{"code":1,"name":"Apples"},{"code":2,"name":"Bananas"}]',
        }).content.decode()

        self.assertIn('is-type-example', example)
        self.assertNotIn('is-type-example', pane)
