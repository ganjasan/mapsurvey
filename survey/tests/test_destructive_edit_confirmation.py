"""Tests for the `destructive-edit-confirmation` capability (openspec/specs/destructive-edit-confirmation/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership
from survey.tests.helpers import _make_org


class AnswerCountHelpersTest(TestCase):
    """Counting what a delete would destroy.

    Tested directly rather than only through the views: an undercount here
    understates the damage in a warning whose whole purpose is to state that
    number truthfully.
    """

    def setUp(self):
        self.org = _make_org('CountOrg')
        self.user = User.objects.create_user('countuser', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='count_survey', organization=self.org, created_by=self.user,
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.session = SurveySession.objects.create(survey=self.survey)

    def _question(self, code, parent=None, section=None):
        return Question.objects.create(
            survey_section=section or self.section, code=code, name=code,
            input_type='text', order_number=1, parent_question_id=parent,
        )

    def _answers(self, question, how_many, parent=None):
        for _ in range(how_many):
            Answer.objects.create(
                survey_session=self.session, question=question,
                parent_answer_id=parent, text='x',
            )

    def test_question_with_no_answers_counts_zero(self):
        """
        GIVEN a question nobody has answered
        WHEN its answers are counted
        THEN the count is zero
        """
        question = self._question('q1')

        self.assertEqual(question.answer_count(), 0)

    def test_question_counts_its_own_answers(self):
        """
        GIVEN a question with three answers
        WHEN its answers are counted
        THEN the count is three
        """
        question = self._question('q1')
        self._answers(question, 3)

        self.assertEqual(question.answer_count(), 3)

    def test_question_count_includes_subquestion_answers(self):
        """
        GIVEN a question with 2 answers whose sub-question has 5
        WHEN its answers are counted
        THEN the count is 7 — the sub-question's answers die with the parent
        """
        parent = self._question('q_parent')
        child = self._question('q_child', parent=parent)
        self._answers(parent, 2)
        self._answers(child, 5)

        self.assertEqual(parent.answer_count(), 7)

    def test_question_count_reaches_deeper_nesting(self):
        """
        GIVEN a sub-question that itself has a sub-question with answers
        WHEN the top question's answers are counted
        THEN answers at every depth are included
        """
        top = self._question('q_top')
        middle = self._question('q_middle', parent=top)
        bottom = self._question('q_bottom', parent=middle)
        self._answers(top, 1)
        self._answers(middle, 2)
        self._answers(bottom, 4)

        self.assertEqual(top.answer_count(), 7)

    def test_subquestion_counts_only_itself(self):
        """
        GIVEN a sub-question with answers alongside its parent's
        WHEN the sub-question's answers are counted
        THEN the parent's answers are not included
        """
        parent = self._question('q_parent')
        child = self._question('q_child', parent=parent)
        self._answers(parent, 2)
        self._answers(child, 5)

        self.assertEqual(child.answer_count(), 5)

    def test_section_count_spans_questions_and_subquestions(self):
        """
        GIVEN a section with two questions holding 4 and 6 answers, one of them
              with a sub-question holding 3
        WHEN the section's answers are counted
        THEN the count is 13
        """
        first = self._question('q1')
        second = self._question('q2')
        child = self._question('q2_child', parent=second)
        self._answers(first, 4)
        self._answers(second, 6)
        self._answers(child, 3)

        self.assertEqual(self.section.answer_count(), 13)

    def test_section_count_ignores_other_sections(self):
        """
        GIVEN answers in a neighbouring section
        WHEN this section's answers are counted
        THEN the neighbour's answers are not included
        """
        other_section = SurveySection.objects.create(
            survey_header=self.survey, name='s2', code='S2',
        )
        self._answers(self._question('q1'), 2)
        self._answers(self._question('q_other', section=other_section), 9)

        self.assertEqual(self.section.answer_count(), 2)

    def test_section_with_no_answers_counts_zero(self):
        """
        GIVEN a section whose questions have no answers
        WHEN its answers are counted
        THEN the count is zero
        """
        self._question('q1')

        self.assertEqual(self.section.answer_count(), 0)


class DeleteAnswerGuardTest(TestCase):
    """The editor must not destroy collected answers without saying so."""

    def setUp(self):
        self.org = _make_org('GuardOrg')
        self.user = User.objects.create_user('guarduser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='guard_survey', organization=self.org, created_by=self.user,
            status='draft',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.question = Question.objects.create(
            survey_section=self.section, name='Comment', code='q1',
            input_type='text', order_number=1,
        )
        self.session = SurveySession.objects.create(survey=self.survey)
        self.client.login(username='guarduser', password='pass')

    def _answer(self, question, how_many=1):
        for _ in range(how_many):
            Answer.objects.create(
                survey_session=self.session, question=question, text='x',
            )

    def _delete_question(self, question=None, acknowledge=False):
        question = question or self.question
        url = f'/editor/surveys/{self.survey.uuid}/questions/{question.id}/delete/'
        data = {'confirm_delete_answers': 'true'} if acknowledge else {}
        return self.client.post(url, data)

    def _delete_section(self, section=None, acknowledge=False):
        section = section or self.section
        url = f'/editor/surveys/{self.survey.uuid}/sections/{section.id}/delete/'
        data = {'confirm_delete_answers': 'true'} if acknowledge else {}
        return self.client.post(url, data)

    # ── Refusal and acknowledgement ───────────────────────────────────────

    def test_delete_without_acknowledgement_is_refused(self):
        """
        GIVEN a question with three answers
        WHEN deletion is requested without acknowledgement
        THEN the request is refused, reports the count, and destroys nothing
        """
        self._answer(self.question, 3)

        response = self._delete_question()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['answers_at_risk'], 3)
        self.assertTrue(Question.objects.filter(pk=self.question.pk).exists())
        self.assertEqual(Answer.objects.filter(question=self.question).count(), 3)

    def test_delete_with_acknowledgement_proceeds(self):
        """
        GIVEN a question with answers
        WHEN deletion is requested with acknowledgement
        THEN the question and its answers are deleted
        """
        self._answer(self.question, 3)

        response = self._delete_question(acknowledge=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Question.objects.filter(pk=self.question.pk).exists())
        self.assertEqual(Answer.objects.count(), 0)

    def test_question_without_answers_deletes_in_one_step(self):
        """
        GIVEN a question nobody has answered
        WHEN deletion is requested without acknowledgement
        THEN it is deleted without a refusal
        """
        response = self._delete_question()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Question.objects.filter(pk=self.question.pk).exists())

    def test_reported_count_includes_subquestion_answers(self):
        """
        GIVEN a question with 2 answers whose sub-question has 5
        WHEN deletion is requested without acknowledgement
        THEN the reported count is 7
        """
        sub = Question.objects.create(
            survey_section=self.section, name='Sub', code='q1s',
            input_type='text', order_number=1, parent_question_id=self.question,
        )
        self._answer(self.question, 2)
        self._answer(sub, 5)

        response = self._delete_question()

        self.assertEqual(response.json()['answers_at_risk'], 7)

    # ── Sections ──────────────────────────────────────────────────────────

    def test_section_count_spans_questions_and_subquestions(self):
        """
        GIVEN a section holding two questions with 4 and 6 answers, one with a
              sub-question holding 3
        WHEN deletion is requested without acknowledgement
        THEN the reported count is 13
        """
        second = Question.objects.create(
            survey_section=self.section, name='Second', code='q2',
            input_type='text', order_number=2,
        )
        sub = Question.objects.create(
            survey_section=self.section, name='Sub', code='q2s',
            input_type='text', order_number=1, parent_question_id=second,
        )
        self._answer(self.question, 4)
        self._answer(second, 6)
        self._answer(sub, 3)

        response = self._delete_section()

        self.assertEqual(response.json()['answers_at_risk'], 13)

    def test_refused_section_delete_leaves_ordering_intact(self):
        """
        GIVEN a section with answers sitting between two others
        WHEN deletion is refused
        THEN the section still exists and its neighbours still link to it

        The re-linking runs before the delete in the view, so a guard placed
        after it would rewrite the chain around a section that survives.
        """
        first = self.section
        middle = SurveySection.objects.create(
            survey_header=self.survey, name='s2', code='S2',
        )
        last = SurveySection.objects.create(
            survey_header=self.survey, name='s3', code='S3',
        )
        first.next_section = middle
        first.save()
        middle.prev_section = first
        middle.next_section = last
        middle.save()
        last.prev_section = middle
        last.save()
        middle_question = Question.objects.create(
            survey_section=middle, name='Q', code='q_mid',
            input_type='text', order_number=1,
        )
        self._answer(middle_question, 2)

        response = self._delete_section(middle)

        self.assertEqual(response.status_code, 409)
        self.assertTrue(SurveySection.objects.filter(pk=middle.pk).exists())
        first.refresh_from_db()
        last.refresh_from_db()
        self.assertEqual(first.next_section_id, middle.pk)
        self.assertEqual(last.prev_section_id, middle.pk)

    def test_section_without_answers_deletes_in_one_step(self):
        """
        GIVEN a section whose questions have no answers
        WHEN deletion is requested without acknowledgement
        THEN it is deleted without a refusal
        """
        response = self._delete_section()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(SurveySection.objects.filter(pk=self.section.pk).exists())

    # ── The versioning explanation ────────────────────────────────────────

    def test_never_published_survey_gets_the_versioning_explanation(self):
        """
        GIVEN a survey that has never been published
        WHEN a delete is refused
        THEN the response says the versioning explanation applies
        """
        self._answer(self.question, 1)

        response = self._delete_question()

        self.assertTrue(response.json()['explain_versioning'])

    def test_draft_copy_of_published_survey_does_not(self):
        """
        GIVEN a draft copy of a published survey
        WHEN a delete is refused
        THEN the versioning explanation does not apply — that author already
             has version protection, so the sentence would be false
        """
        published = SurveyHeader.objects.create(
            name='published_one', organization=self.org, created_by=self.user,
            status='published',
        )
        draft = SurveyHeader.objects.create(
            name='published_one_draft', organization=self.org, created_by=self.user,
            status='draft', published_version=published, is_canonical=False,
        )
        section = SurveySection.objects.create(
            survey_header=draft, name='s1', code='S1', is_head=True,
        )
        question = Question.objects.create(
            survey_section=section, name='Q', code='q1',
            input_type='text', order_number=1,
        )
        Answer.objects.create(
            survey_session=SurveySession.objects.create(survey=draft),
            question=question, text='x',
        )

        response = self.client.post(
            f'/editor/surveys/{draft.uuid}/questions/{question.id}/delete/'
        )

        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.json()['explain_versioning'])

    # ── The read-only lock still wins ─────────────────────────────────────

    def test_published_survey_refuses_with_403_not_409(self):
        """
        GIVEN a published survey
        WHEN deletion is requested, even with acknowledgement
        THEN the structural lock refuses it and nothing is deleted
        """
        self._answer(self.question, 1)
        self.survey.status = 'published'
        self.survey.save()

        response = self._delete_question(acknowledge=True)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Question.objects.filter(pk=self.question.pk).exists())
