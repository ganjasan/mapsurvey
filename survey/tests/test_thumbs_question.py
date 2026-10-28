"""Tests for the `thumbs-question` capability (openspec/specs/thumbs-question/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from survey.models import Organization, SurveyHeader, SurveySection, Question, Answer, Membership
from survey.forms import SurveySectionAnswerForm


# ─── overlay-features: thumbs + layer_objects question types (group 3) ──────

class ThumbsQuestionTest(TestCase):
    """👍/👎 as a fixed two-choice type (spec thumbs-question)."""

    def setUp(self):
        self.org = Organization.objects.create(name="Thumbs Org")
        self.survey = SurveyHeader.objects.create(
            name="thumbs_survey", organization=self.org, redirect_url="/thanks/",
            status='published', available_languages=['en'],
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True,
        )
        self.q = Question.objects.create(
            survey_section=self.section, code="TH001", name="Build it?", input_type="thumbs", order_number=1,
        )
        self.q.choices = self.q.thumbs_choices()
        self.q.save()
        self.url = f'/surveys/{self.survey.uuid}/{self.section.name}/'

    def test_widget_renders_two_options(self):
        """
        GIVEN a thumbs question on a published survey
        WHEN the respondent opens the section
        THEN two thumb buttons render, with codes 1 and 0
        """
        self.client.get(f'/surveys/{self.survey.uuid}/')
        html = self.client.get(self.url).content.decode()
        self.assertIn('class="thumbs"', html)
        self.assertIn('data-thumb="1"', html)
        self.assertIn('data-thumb="0"', html)
        self.assertIn('fa-thumbs-down', html)

    def test_answer_is_stored_and_changeable(self):
        """
        GIVEN a respondent who taps 👍 and later 👎
        WHEN each submission is stored
        THEN the answer holds code 1, then code 0, and the export cell reads up/down
        """
        self.client.get(f'/surveys/{self.survey.uuid}/')
        self.client.get(self.url)
        self.client.post(self.url, {self.q.code: '1'})
        answer = Answer.objects.get(question=self.q)
        self.assertEqual(answer.selected_choices, [1])
        self.assertEqual(answer.get_selected_choice_names(), ['up'])
        self.client.post(self.url, {self.q.code: '0'})
        answer = Answer.objects.filter(question=self.q).order_by('-id').first()
        self.assertEqual(answer.selected_choices, [0])
        self.assertEqual(answer.get_selected_choice_names(), ['down'])

    def test_required_thumbs_validates_like_other_single_value_types(self):
        """
        GIVEN a required thumbs question
        WHEN the single-question form is bound without a value, then with 👍
        THEN validation fails on empty (the same client-side `required` path
             every choice type uses) and accepts the code
        """
        from django.core.exceptions import ValidationError
        self.q.required = True
        self.q.save()
        form = SurveySectionAnswerForm.single_question_form(self.q)
        field = form.fields[self.q.code]
        with self.assertRaises(ValidationError):
            field.clean('')
        self.assertEqual(field.clean('1'), '1')
        self.client.get(f'/surveys/{self.survey.uuid}/')
        html = self.client.get(self.url).content.decode()
        self.assertRegex(html, r'<input type="radio" name="%s" value="1"[^>]*required' % self.q.code)

    def test_editor_writes_the_fixed_choices(self):
        """
        GIVEN an owner creating a thumbs question through the editor
        WHEN the create endpoint saves it
        THEN the stored choices are the fixed up/down pair regardless of the posted choices_json
        """
        owner = User.objects.create_user(username='thumbsowner', password='pw12345678')
        Membership.objects.create(user=owner, organization=self.org, role='owner')
        self.survey.status = 'draft'
        self.survey.created_by = owner
        self.survey.save()
        self.client.login(username='thumbsowner', password='pw12345678')
        response = self.client.post(
            reverse('editor_question_create', kwargs={'survey_uuid': self.survey.uuid, 'section_id': self.section.pk}),
            {'name': 'Like it?', 'input_type': 'thumbs', 'subtext': '', 'display_style': 'default',
             'color': '#000000', 'choices_json': '[{"code": 5, "name": "x"}]'})
        self.assertEqual(response.status_code, 200)
        q = Question.objects.get(name='Like it?')
        self.assertEqual(q.choices, [{"code": 1, "name": "up"}, {"code": 0, "name": "down"}])

    def test_picker_lists_thumbs_with_the_questions(self):
        """
        GIVEN the type picker groups
        WHEN they are built from every input type
        THEN thumbs sits in the Questions group with the thumbs-up icon and its label
        """
        from survey.models import INPUT_TYPE_CHOICES
        from survey.question_types import picker_groups_for
        groups = dict(picker_groups_for(INPUT_TYPE_CHOICES))
        entry = next(t for t in groups['Questions'] if t['value'] == 'thumbs')
        self.assertEqual((entry['icon'], entry['label']), ('fa-thumbs-up', 'Thumbs up / down'))
