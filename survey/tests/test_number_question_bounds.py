"""Tests for the `number-question-bounds` capability
(openspec/specs/number-question-bounds/spec.md, change responses-required-unanswered, #691).

Min / Max of a number question limit what a respondent can submit: the input refuses an
out-of-range value, the section POST stores nothing for one, and only number questions offer
the two settings.
"""
import re

from django.test import TestCase

from survey.models import Answer, Question, SurveyHeader, SurveySection, SurveySession
from survey.services.questions import parse_validation_settings
from survey.tests.helpers import _make_org


class NumberBoundsTest(TestCase):

    def setUp(self):
        self.org = _make_org('BoundsOrg')
        self.survey = SurveyHeader.objects.create(
            name='bounds_survey', organization=self.org, status='published', redirect_url='#',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', title='S1', code='S1', is_head=True,
        )
        self.age = Question.objects.create(
            survey_section=self.section, name='Age', code='AGE', input_type='number', order_number=1,
            validation_settings={'min_value': 0, 'max_value': 120},
        )
        self.count = Question.objects.create(
            survey_section=self.section, name='Count', code='COUNT', input_type='number', order_number=2,
        )
        self.url = f'/surveys/{self.survey.uuid}/s1/'

    def _stored(self, question):
        sid = self.client.session['survey_session_id']
        return list(Answer.objects.filter(survey_session_id=sid, question=question).values_list('numeric', flat=True))

    def test_input_carries_the_bounds(self):
        """
        GIVEN a number question with Min 0 and Max 120
        WHEN the respondent page renders
        THEN its input carries min="0" and max="120", and an unbounded one carries neither
        """
        html = self.client.get(self.url).content.decode()
        tag = re.search(r'<input[^>]*\sname="AGE"[^>]*>', html).group(0)
        self.assertIn('min="0"', tag)
        self.assertIn('max="120"', tag)
        tag = re.search(r'<input[^>]*\sname="COUNT"[^>]*>', html).group(0)
        self.assertNotIn('min=', tag)
        self.assertNotIn('max=', tag)

    def test_tampered_out_of_range_value_is_not_stored(self):
        """
        GIVEN the same question
        WHEN a section POST carries 150
        THEN no answer is stored for it, and the rest of the page is stored
        """
        self.client.get(self.url)
        self.client.post(self.url, {'AGE': '150', 'COUNT': '7'})
        self.assertEqual(self._stored(self.age), [])
        self.assertEqual(self._stored(self.count), [7.0])

    def test_value_inside_bounds_is_stored(self):
        """
        GIVEN the same question
        WHEN the respondent submits 42
        THEN 42 is stored
        """
        self.client.get(self.url)
        self.client.post(self.url, {'AGE': '42'})
        self.assertEqual(self._stored(self.age), [42.0])

    def test_no_bounds_any_number_is_stored(self):
        """
        GIVEN a number question without Min / Max
        WHEN the respondent submits -1000000
        THEN it is stored
        """
        self.client.get(self.url)
        self.client.post(self.url, {'COUNT': '-1000000'})
        self.assertEqual(self._stored(self.count), [-1000000.0])

    def test_text_in_a_number_field_is_not_stored(self):
        """
        GIVEN any number question
        WHEN a scripted POST carries "abc"
        THEN nothing is stored and the page does not fail
        """
        self.client.get(self.url)
        resp = self.client.post(self.url, {'COUNT': 'abc'})
        self.assertIn(resp.status_code, (200, 302))
        self.assertEqual(self._stored(self.count), [])
        self.assertTrue(SurveySession.objects.exists())

    def test_only_number_questions_keep_bounds(self):
        """
        GIVEN the modal's Min / Max fields
        WHEN a number question and a range question are saved with them
        THEN the number question keeps them and the range question does not
        """
        data = {'vs_min_value': '1', 'vs_max_value': '10'}
        self.assertEqual(parse_validation_settings('number', data), {'min_value': 1.0, 'max_value': 10.0})
        self.assertEqual(parse_validation_settings('range', data), {})

    def test_emptied_bound_is_removed(self):
        """
        GIVEN a number question with Min 0 and Max 120
        WHEN it is saved with Max emptied
        THEN only Min remains
        """
        vs = parse_validation_settings('number', {'vs_min_value': '0', 'vs_max_value': ''},
                                       base={'min_value': 0, 'max_value': 120})
        self.assertEqual(vs, {'min_value': 0.0})

    def test_editor_modal_offers_bounds_for_number_only(self):
        """
        GIVEN the question modal
        WHEN its script decides which settings block to show
        THEN the Min / Max block is tied to the number type alone
        """
        from django.template.loader import get_template
        source = open(get_template('editor/partials/question_form_modal.html').origin.name).read()
        self.assertIn("numEl.style.display = (t === 'number') ? 'block' : 'none';", source)
        self.assertNotIn('vs_outlier_sigma', source)
        self.assertNotIn('vs_min_length', source)
        self.assertNotIn('vs_area_outlier_factor', source)
