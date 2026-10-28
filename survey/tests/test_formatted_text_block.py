"""Tests for the `formatted-text-block` capability (openspec/specs/formatted-text-block/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import translation
from survey.models import SurveyHeader, SurveySection, Question, Membership
from survey.tests.helpers import _make_org


class FormattedTextBlockEditorTest(TestCase):
    """The Formatted Text block (`input_type='html'`) is authored in a WYSIWYG.

    Its subtext is the block's whole body and is rendered `|safe` to
    respondents, which makes both properties tested here load-bearing: the body
    must not be capped at a tweet's length, and it must not be able to carry a
    script to the respondent's browser.
    """

    def setUp(self):
        self.org = _make_org('FormattedTextOrg')
        self.user = User.objects.create_user(username='ft_editor', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='ft_editor', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='ft_survey', visibility='private', organization=self.org,
            created_by=self.user, available_languages=['en', 'de'],
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section 1', code='S1',
            is_head=True,
        )

    def _create_block(self, subtext, **extra):
        data = {'name': 'intro_block', 'input_type': 'html', 'color': '#000000',
                'subtext': subtext}
        data.update(extra)
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/',
            data,
        )
        self.assertEqual(response.status_code, 200)
        return Question.objects.get(survey_section=self.section, name='intro_block')

    def test_body_longer_than_the_old_column_is_kept(self):
        """
        GIVEN a Formatted Text body far longer than the former 512-char cap
        WHEN the creator saves the block
        THEN the whole body is stored and reaches the respondent
        """
        body = '<p>' + ('Mapping the neighbourhood. ' * 60) + '</p>'
        self.assertGreater(len(body), 512)

        block = self._create_block(body)

        self.assertEqual(block.subtext, body)
        SurveyHeader.objects.filter(pk=self.survey.pk).update(status='published')
        # A multilingual survey asks for a language before it shows a section.
        self.client.post(f'/surveys/{self.survey.uuid}/language/', {'language': 'en'})
        content = self.client.get(
            f'/surveys/{self.survey.uuid}/sec1/', follow=True).content.decode()
        self.assertIn('Mapping the neighbourhood.', content)

    def test_formatting_survives_the_save(self):
        """
        GIVEN a body with a heading, a bold run and a list
        WHEN the block is saved
        THEN the markup is stored rather than escaped away
        """
        block = self._create_block(
            '<h2>Welcome</h2><p><strong>Read this first.</strong></p><ul><li>One</li></ul>')

        self.assertIn('<h2>Welcome</h2>', block.subtext)
        self.assertIn('<strong>Read this first.</strong>', block.subtext)
        self.assertIn('<li>One</li>', block.subtext)

    def test_script_is_stripped_from_the_body(self):
        """
        GIVEN a body carrying a script tag and an inline event handler
        WHEN the block is saved
        THEN both are gone and the allow-listed formatting stays

        The block renders |safe, so an unsanitized body would be stored XSS
        aimed at every respondent of the survey.
        """
        block = self._create_block(
            '<h2>Hi</h2><script>alert(1)</script><p onclick="steal()">Text</p>')

        self.assertNotIn('<script>', block.subtext)
        self.assertNotIn('onclick', block.subtext)
        self.assertIn('<h2>Hi</h2>', block.subtext)
        self.assertIn('Text', block.subtext)

    def test_translated_body_is_sanitized_too(self):
        """
        GIVEN a German translation of a Formatted Text body carrying a script
        WHEN it is written through the Translations tab (the modal's block is a
             read-only mirror since change translation-table)
        THEN the stored translation is sanitized like the base language
        """
        from survey import translation_table as tt
        from survey.services.context import Actor

        block = self._create_block('<p>Hello</p>')
        tt.apply(Actor(user=self.user), self.survey, 'de',
                 {f'question:{block.code}:subtext': '<p>Hallo</p><script>alert(1)</script>'})

        translation = block.translations.get(language='de')
        self.assertNotIn('<script>', translation.subtext)
        self.assertIn('<p>Hallo</p>', translation.subtext)

    def test_other_types_keep_the_creator_sentence_intact(self):
        """
        GIVEN a text question whose subtext contains angle brackets
        WHEN it is saved
        THEN the sentence survives, escaped rather than swallowed

        Subtext renders |safe for every type now, so "takes <5 minutes" has to
        be escaped — running it through the tag allow-list alone would drop
        "<5 minutes" as an unknown tag.
        """
        self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/',
            {'name': 'Duration', 'input_type': 'text', 'color': '#000000',
             'subtext': 'takes <5 minutes'},
        )

        q = Question.objects.get(survey_section=self.section, name='Duration')
        self.assertEqual(q.subtext, 'takes &lt;5 minutes')

    def test_dialog_ships_the_editor_mount(self):
        """
        GIVEN the question dialog
        WHEN it is opened
        THEN it carries the Quill mount and, per language, the read-only mirror
             that links to the Translations tab (change translation-table)

        A server-side test suite would otherwise pass with a dead editor: every
        assertion above works fine against the plain one-line input.
        """
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/')
        content = response.content.decode()

        self.assertIn('id="html-body-quill"', content)
        self.assertIn('id="translations-de"', content)
        self.assertNotIn('data-translation-quill="de"', content)
        self.assertIn('new Quill(', content)


class RichSubtextAndSubheadingTest(TestCase):
    """Question subtext and section subheading are creator rich text.

    Both render as markup to respondents now, so the interesting cases are the
    ones where a value is NOT markup: text typed before the editors existed,
    text from an AI draft, and text that merely looks like a tag.
    """

    def setUp(self):
        self.org = _make_org('RichTextOrg')
        self.user = User.objects.create_user(username='rich_editor', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='rich_editor', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='rich_survey', visibility='private', organization=self.org,
            created_by=self.user,
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section 1', code='S1',
            is_head=True,
        )

    def _respondent_page(self):
        # Structural edits are blocked on a published survey, so the tests build
        # the survey as a draft and publish it only to look at the result.
        SurveyHeader.objects.filter(pk=self.survey.pk).update(status='published')
        return self.client.get(f'/surveys/{self.survey.uuid}/sec1/').content.decode()

    def test_formatted_subtext_reaches_the_respondent(self):
        """
        GIVEN a question whose subtext carries bold and a link
        WHEN a respondent opens the section
        THEN the markup renders instead of being printed as tags
        """
        Question.objects.create(
            survey_section=self.section, name='Q1', code='q1', input_type='text',
            order_number=1,
            subtext='<p>Read <strong>this</strong> and the <a href="/rules">rules</a>.</p>',
        )

        content = self._respondent_page()

        self.assertIn('<strong>this</strong>', content)
        self.assertIn('href="/rules"', content)
        self.assertNotIn('&lt;strong&gt;', content)

    def test_angle_brackets_typed_by_a_creator_are_kept(self):
        """
        GIVEN a creator typing "takes <5 minutes" into the subtext editor
        WHEN the question is saved
        THEN the stored value escapes it, so the respondent still reads "<5 minutes"

        Quill wraps typed text in <p>, so the value arriving here is markup whose
        payload is the literal text — sanitizing alone would eat "<5 minutes" as
        an unknown tag.
        """
        self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/',
            {'name': 'Duration', 'input_type': 'text', 'color': '#000000',
             'subtext': '<p>takes &lt;5 minutes</p>'},
        )

        q = Question.objects.get(survey_section=self.section, name='Duration')
        self.assertEqual(q.subtext, '<p>takes &lt;5 minutes</p>')
        self.assertIn('takes &lt;5 minutes', self._respondent_page())

    def test_plain_text_from_a_machine_is_escaped_not_sanitized(self):
        """
        GIVEN plain text containing angle brackets, as an AI draft or an old ZIP supplies it
        WHEN it is stored through the import path
        THEN it is escaped, not fed to the tag allow-list

        nh3 would drop "<5 minutes" as an unknown tag; escaping is what keeps the
        creator's sentence intact.
        """
        from survey.html_sanitize import coerce_creator_html

        self.assertEqual(coerce_creator_html('takes <5 minutes & counting'),
                         'takes &lt;5 minutes &amp; counting')

    def test_script_is_stripped_from_subtext_of_any_type(self):
        """
        GIVEN a subtext on an ordinary question carrying a script tag
        WHEN it is saved
        THEN the script is gone — subtext renders |safe for every type now
        """
        self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/',
            {'name': 'Trap', 'input_type': 'text', 'color': '#000000',
             'subtext': '<p>hi</p><script>alert(1)</script>'},
        )

        q = Question.objects.get(survey_section=self.section, name='Trap')
        self.assertNotIn('<script>', q.subtext)
        self.assertIn('<p>hi</p>', q.subtext)

    def test_section_subheading_is_sanitized_on_save(self):
        """
        GIVEN a section subheading containing a script
        WHEN the section panel saves it
        THEN the stored subheading keeps the formatting and drops the script

        The subheading was already rendered |safe before it had an editor, so
        this closes a hole rather than opening one.
        """
        self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/',
            {'title': 'Section 1', 'code': 'S1',
             'subheading': '<p>Map the <em>hot</em> spots</p><script>alert(1)</script>'},
        )

        self.section.refresh_from_db()
        self.assertNotIn('<script>', self.section.subheading)
        self.assertIn('<em>hot</em>', self.section.subheading)

    def test_editor_ships_the_subtext_and_subheading_editors(self):
        """
        GIVEN the question dialog and the section panel
        WHEN they render
        THEN each carries its rich-text mount

        Server-side assertions above pass just as well against the old plain
        inputs; this is what fails if the editor stops being wired up.
        """
        dialog = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/'
        ).content.decode()
        panel = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/'
        ).content.decode()

        self.assertIn('id="subtext-quill"', dialog)
        self.assertIn('id="section-subheading-quill"', panel)
