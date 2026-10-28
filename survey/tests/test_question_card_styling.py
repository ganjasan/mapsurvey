"""Tests for the `question-card-styling` capability (openspec/specs/question-card-styling/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.contrib.gis.geos import Point
from django.urls import reverse
import re
from survey.models import Organization, SurveyHeader, SurveySection, Question
from survey.forms import SurveySectionAnswerForm
import os


class QuestionCardStylingTest(TestCase):
    """Tests for question card wrapper rendering in survey sections."""

    def setUp(self):
        self.client = Client()
        self.org = Organization.objects.create(name="Card Test Org")
        self.survey = SurveyHeader.objects.create(
            name="card_survey",
            organization=self.org,
            redirect_url="#",
            status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="section1",
            title="Section One",
            code="S1",
            is_head=True,
            start_map_postion=Point(30.5, 60.0),
            start_map_zoom=14,
        )

    def test_text_question_renders_in_card(self):
        """
        GIVEN a survey section with a text question
        WHEN the section page is rendered
        THEN the question is wrapped in a div.question-card
        """
        Question.objects.create(
            survey_section=self.section,
            name="Your name",
            input_type="text",
            order_number=1,
        )
        response = self.client.get('/surveys/card_survey/section1/')
        self.assertContains(response, 'class="question-card"')

    def test_choice_question_renders_in_card(self):
        """
        GIVEN a survey section with a choice question
        WHEN the section page is rendered
        THEN the question is wrapped in a div.question-card
        """
        Question.objects.create(
            survey_section=self.section,
            name="Agree?",
            input_type="choice",
            choices=[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}],
            order_number=1,
        )
        response = self.client.get('/surveys/card_survey/section1/')
        self.assertContains(response, 'class="question-card"')

    def test_geo_question_not_in_card(self):
        """
        GIVEN a survey section with a point geo question
        WHEN the section page is rendered
        THEN the question is NOT wrapped in a div.question-card
        """
        Question.objects.create(
            survey_section=self.section,
            name="Location",
            input_type="point",
            order_number=1,
        )
        response = self.client.get('/surveys/card_survey/section1/')
        self.assertNotContains(response, 'class="question-card"')

    def test_html_question_not_in_card(self):
        """
        GIVEN a survey section with an html question
        WHEN the section page is rendered
        THEN the question is NOT wrapped in a div.question-card
        """
        Question.objects.create(
            survey_section=self.section,
            name="Info",
            input_type="html",
            subtext="<p>Some info</p>",
            order_number=1,
        )
        response = self.client.get('/surveys/card_survey/section1/')
        self.assertNotContains(response, 'class="question-card"')

    def test_widget_has_question_type_attribute(self):
        """
        GIVEN a survey section with a choice question
        WHEN a SurveySectionAnswerForm is created
        THEN the field widget has question_type attribute set to 'choice'
        """
        q = Question.objects.create(
            survey_section=self.section,
            name="Agree?",
            input_type="choice",
            choices=[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}],
            order_number=1,
        )
        form = SurveySectionAnswerForm(
            initial={}, section=self.section, question=None,
            survey_session_id=None,
        )
        widget = form.fields[q.code].widget
        self.assertEqual(widget.question_type, 'choice')

    def test_mixed_questions_only_card_types_wrapped(self):
        """
        GIVEN a survey section with text and point questions
        WHEN the section page is rendered
        THEN only the text question has a question-card wrapper
        """
        Question.objects.create(
            survey_section=self.section,
            name="Your name",
            input_type="text",
            order_number=1,
        )
        Question.objects.create(
            survey_section=self.section,
            name="Location",
            input_type="point",
            order_number=2,
        )
        response = self.client.get('/surveys/card_survey/section1/')
        content = response.content.decode()
        self.assertEqual(content.count('class="question-card"'), 1)


class SectionFormMarkupTest(TestCase):
    """Change python312-django52-upgrade, D2: Django 5.0 changed what `{{ form }}`
    renders (div.html instead of table.html). The respondent section never used
    it — partials/survey_section_partial.html renders every question as a
    question-card through the project's widget templates — and this test keeps
    that fact true, so a future template that reaches for `{{ form }}` on a
    respondent page is caught here rather than by a respondent."""

    def setUp(self):
        self.org = Organization.objects.create(name="Markup Org")
        self.survey = SurveyHeader.objects.create(
            name="markup_survey", organization=self.org, redirect_url="/thanks/",
            status='published', available_languages=['en'],
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True,
        )
        Question.objects.create(survey_section=self.section, code="M1", name="Your name", input_type="text_line", order_number=1)
        Question.objects.create(survey_section=self.section, code="M2", name="Age", input_type="number", order_number=2)
        Question.objects.create(survey_section=self.section, code="M3", name="Where", input_type="point", order_number=3)

    def test_section_renders_question_cards_through_project_templates(self):
        """
        GIVEN a published survey whose section has a text, a number and a point question
        WHEN a respondent opens the section
        THEN the two form questions are question-cards with their labels, the point
             question renders as the project's draw-button widget (geo questions take
             the card-less branch of the partial), and Django's form-level template —
             table rows before 5.0, div wrappers since — appears nowhere on the page
        """
        r = Client().get(reverse('section', args=[str(self.survey.uuid), self.section.name]))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode('utf-8')
        self.assertEqual(html.count('class="question-card'), 2, html[:600])
        for label in ('Your name', 'Age', 'Where'):
            self.assertIn(label, html)
        self.assertIn('drawbutton', html)
        self.assertNotIn('<tr><th>', html)
        self.assertNotIn('<div>\n      <label', html)

    def test_no_respondent_template_renders_a_whole_form(self):
        """
        GIVEN the templates a respondent can be served
        WHEN they are scanned for form-level rendering
        THEN none uses `{{ form }}` or `as_p`/`as_table`/`as_div`/`as_ul` — the two
             legacy templates that do are rendered by no view
        """
        import os
        import re
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')
        offenders = []
        for dirpath, _dirs, files in os.walk(root):
            if os.sep + 'editor' in dirpath or os.sep + 'admin' in dirpath or os.sep + 'registration' in dirpath:
                continue
            for name in files:
                if not name.endswith('.html') or name in ('survey_section_block.html', 'answer.html'):
                    continue
                with open(os.path.join(dirpath, name), encoding='utf-8') as fh:
                    text = fh.read()
                # Prose in template comments may name as_p() (partials/question_fields.html
                # explains it replaced one); only rendered markup counts.
                text = re.sub(r'{%\s*comment\s*%}.*?{%\s*endcomment\s*%}|{#.*?#}', '', text, flags=re.S)
                if re.search(r'{{\s*form\s*}}|\.as_(p|table|div|ul)\b', text):
                    offenders.append(os.path.relpath(os.path.join(dirpath, name), root))
        self.assertEqual(offenders, [])
