"""Tests for the `range-question-display` capability (openspec/specs/range-question-display/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from survey.models import SurveyHeader, SurveySection, Question, Answer, Membership
from survey.forms import SurveySectionAnswerForm
from survey.tests.helpers import _make_org


class RangeSliderOnlyTest(TestCase):
    """Range always renders as the slider (change range-slider-only).

    Display styles were briefly offered for range and retired: of 124
    production range questions, the only two non-default ones were a creator
    imitating the rating type. These tests pin the new invariant against the
    nine-point named-scale fixtures the retired feature was built on.
    """

    LABELS = [
        '(positive) Ger\u00e4usche', 'sehr angenehm', 'angenehm', 'eher angenehm',
        'neutral', 'eher st\u00f6rend', 'st\u00f6rend', 'sehr st\u00f6rend', '(negativer) L\u00e4rm',
    ]

    def setUp(self):
        self.org = _make_org('RangeSliderOrg')
        self.user = User.objects.create_user('rangeslideruser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.choices = [{"code": i + 1, "name": {"en": name}}
                        for i, name in enumerate(self.LABELS)]

    def _survey(self, display_style='default', rating_default='scale_strip'):
        survey = SurveyHeader.objects.create(
            name=f'range_slider_{display_style}_{id(self)}', organization=self.org,
            created_by=self.user, status='published',
            style_settings={'rating_display_style': rating_default},
        )
        section = SurveySection.objects.create(
            survey_header=survey, name='s1', code='S1', is_head=True,
        )
        question = Question.objects.create(
            survey_section=section, name='Loudness', code='q_range',
            input_type='range', order_number=1,
            choices=self.choices, display_style=display_style,
        )
        # Fresh client per survey: the respondent session binds to the first
        # survey a client visits (see the retired RangeDisplayStyleTest).
        self.client = Client()
        return survey, section, question

    def _get(self, survey):
        return self.client.get(f'/surveys/{survey.uuid}/s1/')

    def test_stored_choice_based_styles_render_as_the_slider(self):
        """
        GIVEN range questions whose stored display_style is default,
              scale_strip and list_pips (the latter exists in production)
        WHEN a respondent opens the section
        THEN every one renders as the slider, never through the scale partials
        """
        for style in ('default', 'scale_strip', 'list_pips'):
            with self.subTest(style=style):
                survey, _section, _q = self._survey(display_style=style)

                content = self._get(survey).content.decode()

                self.assertIn('type="range"', content)
                self.assertNotIn('rating-scale-strip__cell', content)
                self.assertNotIn('rating-list-pips', content)

    def test_stored_style_is_ignored_not_rewritten(self):
        """
        GIVEN a range question carrying list_pips from before the retirement
        WHEN a respondent answers through the slider
        THEN the answer stores as numeric and the stored style is untouched
        """
        survey, _section, question = self._survey(display_style='list_pips')
        self._get(survey)

        self.client.post(f'/surveys/{survey.uuid}/s1/', {'q_range': '5'})

        answer = Answer.objects.get(question=question)
        self.assertEqual(answer.numeric, 5)
        question.refresh_from_db()
        self.assertEqual(question.display_style, 'list_pips')

    def test_answers_collected_under_a_removed_style_prepopulate_the_slider(self):
        """
        GIVEN an answer collected while the question rendered as a labelled list
        WHEN the respondent navigates back, now on the slider
        THEN the slider is prepopulated with the stored value
        """
        survey, _section, _q = self._survey(display_style='list_pips')
        self._get(survey)
        self.client.post(f'/surveys/{survey.uuid}/s1/', {'q_range': '4'})

        content = self._get(survey).content.decode()

        self.assertIn('type="range"', content)
        self.assertIn('value="4"', content)

    def test_live_preview_ignores_posted_style_for_range(self):
        """
        GIVEN the question dialog's live preview endpoint
        WHEN a range draft is posted with display_style=list_pips
        THEN the preview renders the slider — the editor cannot even preview
             the removed combination
        """
        survey, section, _q = self._survey()
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

        response = self.client.post(
            f'/editor/surveys/{survey.uuid}/sections/{section.id}/question-preview/',
            {
                'input_type': 'range',
                'name': 'Loudness',
                'display_style': 'list_pips',
                'choices_json': '[{"code": 1, "name": "quiet"}, {"code": 9, "name": "loud"}]',
            },
        )

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('type="range"', html)
        self.assertNotIn('rating-list-pips', html)

    def test_rating_still_inherits_the_survey_default(self):
        """
        GIVEN a rating question with no style of its own
        WHEN the style is resolved
        THEN it inherits the survey-wide rating default, unchanged by the
             range retirement
        """
        _survey, _section, question = self._survey()
        question.input_type = 'rating'

        resolved = SurveySectionAnswerForm.resolve_display_style(question, 'list_pips')

        self.assertEqual(resolved, 'list_pips')

    def test_range_resolves_to_default_whatever_is_stored(self):
        """
        GIVEN a range question with a choice-based style stored
        WHEN the style is resolved
        THEN it is the slider, whatever the survey-wide rating default is
        """
        _survey, _section, question = self._survey(display_style='list_pips')

        resolved = SurveySectionAnswerForm.resolve_display_style(question, 'scale_strip')

        self.assertEqual(resolved, 'default')
