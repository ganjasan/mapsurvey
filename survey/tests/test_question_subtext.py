"""Tests for the `question-subtext` capability (openspec/specs/question-subtext/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
import re
from survey.models import SurveyHeader, SurveySection, Question, Membership
from survey.tests.helpers import _make_org


class QuestionSubtextRenderingTest(TestCase):
    """Where a question's subtext reaches the respondent, per input type.

    A table test on purpose: the bug this fixes existed because nothing
    asserted the mapping, so a type could be added — or a branch changed —
    and quietly stop delivering text a creator wrote.
    """

    # input_type -> (name shown to respondent, subtext shown to respondent)
    EXPECTED = {
        'text':        (True, True),
        'text_line':   (True, True),
        'number':      (True, True),
        'choice':      (True, True),
        'multichoice': (True, True),
        'range':       (True, True),
        'rating':      (True, True),
        'datetime':    (True, True),
        'point':       (True, True),
        'line':        (True, True),
        'polygon':     (True, True),
        'spraycan':    (True, True),
        # The name identifies the block in the editor and is used as an
        # internal label in published surveys; rendering it would put
        # "html_block_1" on the respondent's screen.
        'html':        (False, True),
        'image':       (False, True),
        'ranking':     (True, True),
        # File questions are card questions: the section template renders
        # name and subtext, the widget renders only the control.
        'photo':       (True, True),
        'audio':       (True, True),
        'document':    (True, True),
        # Thumbs is a card question like rating; the block's title is its name
        # and its subtext renders under the heading (layer_objects.html).
        'thumbs':      (True, True),
        'layer_objects': (True, True),
    }

    def test_every_input_type_has_a_decision(self):
        """
        GIVEN the table above
        WHEN it is compared with INPUT_TYPE_CHOICES
        THEN every type the model offers appears in it

        Without this the table only checks the types someone remembered to
        list: `ranking` was added later, silently dropped its subtext, and the
        table passed because it never looked at the model.
        """
        from survey.models import INPUT_TYPE_CHOICES

        self.assertEqual({value for value, _ in INPUT_TYPE_CHOICES}, set(self.EXPECTED))

    def setUp(self):
        self.org = _make_org('SubtextOrg')
        self.user = User.objects.create_user('subtextuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='subtext_survey', organization=self.org, created_by=self.user,
            status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        choice_types = ('choice', 'multichoice', 'range', 'rating')
        for order, (input_type, _expected) in enumerate(self.EXPECTED.items(), start=1):
            Question.objects.create(
                survey_section=self.section, name=f'NAME_{input_type.upper()}',
                code=f'q_{input_type}', input_type=input_type, order_number=order,
                subtext=f'SUBTEXT_{input_type.upper()}',
                choices=[{"code": c, "name": str(c)} for c in (1, 2, 3)]
                        if input_type in choice_types else None,
            )

    def test_every_type_delivers_what_the_table_says(self):
        """
        GIVEN one question of every input type, each with a name and subtext
        WHEN a respondent opens the section
        THEN name and subtext appear exactly where the table says they should
        """
        content = self.client.get(f'/surveys/{self.survey.uuid}/s1/').content.decode()

        for input_type, (name_shown, subtext_shown) in self.EXPECTED.items():
            with self.subTest(input_type=input_type):
                self.assertEqual(
                    f'NAME_{input_type.upper()}' in content, name_shown,
                    f'{input_type}: name should {"" if name_shown else "not "}render',
                )
                self.assertEqual(
                    f'SUBTEXT_{input_type.upper()}' in content, subtext_shown,
                    f'{input_type}: subtext should {"" if subtext_shown else "not "}render',
                )

    def test_subtext_sits_between_the_question_and_its_input(self):
        """
        GIVEN a text question with subtext
        WHEN it renders
        THEN the subtext comes after the question text and before the input,
             which is where a respondent reads it before answering
        """
        content = self.client.get(f'/surveys/{self.survey.uuid}/s1/').content.decode()

        name_at = content.index('NAME_TEXT')
        subtext_at = content.index('SUBTEXT_TEXT')
        # The input's id, not its name: the card wrapper carries
        # data-field-name="q_text", which contains name="q_text" as a
        # substring and matches earlier than the input itself.
        input_at = content.index('id="id_q_text"')

        self.assertLess(name_at, subtext_at)
        self.assertLess(subtext_at, input_at)

    def test_the_editor_preview_shows_subtext_too(self):
        """
        GIVEN the question dialog's live preview
        WHEN a draft carrying subtext is previewed
        THEN the preview shows it, so the dialog and the survey agree
        """
        self.client.force_login(self.user)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/question-preview/',
            {'input_type': 'text', 'name': 'How was it?', 'subtext': 'One line, please'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('One line, please', response.content.decode())

    def test_rich_text_subtext_renders_once_inside_a_block_wrapper(self):
        """
        GIVEN one question of every input type whose subtext is rich text
              (`<p>…</p>`, which is what the Quill editor saves)
        WHEN a respondent opens the section
        THEN every hint renders exactly once, and no `<p>` is open around it

        A `<p>` cannot hold a `<p>`: the browser closes the styled wrapper
        empty and puts the creator's paragraph beside it unstyled — bigger
        than the question title. On a geo button the multi-feature script then
        refilled the empty wrapper, so the hint showed twice (#315). Python's
        test client does not parse HTML the way a browser does, so the guard is
        on the markup: the nearest unclosed tag before the hint must not be a
        `<p>`.
        """
        for question in Question.objects.all():
            question.subtext = f'<p>SUBTEXT_{question.input_type.upper()}</p>'
            question.save(update_fields=['subtext'])

        content = self.client.get(f'/surveys/{self.survey.uuid}/s1/').content.decode()

        for input_type in self.EXPECTED:
            with self.subTest(input_type=input_type):
                hint = f'<p>SUBTEXT_{input_type.upper()}</p>'
                self.assertEqual(content.count(hint), 1, f'{input_type}: hint should render once')
                before = content[:content.index(hint)]
                last_open = max((m.start() for m in re.finditer(r'<p[\s>]', before)), default=-1)
                self.assertLess(
                    last_open, before.rfind('</p>') if last_open >= 0 else 0,
                    f'{input_type}: hint is nested in an open <p>',
                )

    def test_the_editor_preview_keeps_a_rich_text_hint_in_its_wrapper(self):
        """
        GIVEN the question dialog's live preview
        WHEN a draft with a rich-text hint is previewed
        THEN the hint sits directly inside the `question-card__subtext` block
        """
        self.client.force_login(self.user)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/question-preview/',
            {'input_type': 'text', 'name': 'How was it?', 'subtext': '<p>One line, please</p>'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.content.decode(),
            r'<div class="question-card__subtext"><p>One line, please</p></div>',
        )

    def test_sub_question_popups_render_the_section_cards(self):
        """
        GIVEN a point question whose sub-questions carry rich-text hints, and a
              rating sub-question in the stars style
        WHEN a respondent opens the section
        THEN the popup form handed to the map has each hint inside its card and
             the stars partial — the same markup as the section form (#320)

        The popups used to be Form.as_p(), which dropped the hint (it lives on
        the widget, not in help_text) and rendered any rating as bare radios.
        """
        geo = Question.objects.get(code='q_point')
        Question.objects.create(
            survey_section=self.section, parent_question_id=geo, name='Why here?',
            code='sq_text', input_type='text', order_number=1, subtext='<p>SUB_HINT_TEXT</p>',
        )
        Question.objects.create(
            survey_section=self.section, parent_question_id=geo, name='How hot?',
            code='sq_rating', input_type='rating', order_number=2, display_style='stars',
            subtext='<p>SUB_HINT_RATING</p>', choices=[{"code": c, "name": str(c)} for c in (1, 2, 3)],
        )

        response = self.client.get(f'/surveys/{self.survey.uuid}/s1/')
        popup = response.context['subquestions_forms']['q_point']

        for hint in ('SUB_HINT_TEXT', 'SUB_HINT_RATING'):
            with self.subTest(hint=hint):
                self.assertIn(f'<div class="question-card__subtext"><p>{hint}</p></div>', popup)
        self.assertIn('rating-stars', popup)
        self.assertEqual(len(re.findall(r'class="question-card[ "]', popup)), 2)

    def test_a_question_without_subtext_renders_no_empty_line(self):
        """
        GIVEN a question whose creator left subtext blank
        WHEN it renders
        THEN no subtext element is emitted for it
        """
        Question.objects.all().delete()
        Question.objects.create(
            survey_section=self.section, name='Just a question', code='q_bare',
            input_type='text', order_number=1, subtext='',
        )

        content = self.client.get(f'/surveys/{self.survey.uuid}/s1/').content.decode()

        self.assertIn('Just a question', content)
        self.assertNotIn('question-card__subtext', content)
