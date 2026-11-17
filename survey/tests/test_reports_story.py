"""Spec: reports-story (change reports-story, #704, epic #712).

A report reads as a linear story: an opening, then headings, text, pictures, key numbers and
quotes the author wrote, between the blocks that show data; two half-width blocks share a row.
"""
from django.test import TestCase
from django.urls import reverse

from api.tests.helpers import make_pro_org
from reports import services, story
from reports.models import SNAPSHOT_VERSION, Report, ReportBlock
from reports.render import build_context, story_rows
from survey.services.context import Actor


class _Story(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org('StoryOrg', 'storyowner')
        self.actor = Actor(user=self.owner, ip=None, surface='editor')
        self.report = Report.objects.create(
            organization=self.org, slug='what-residents-said', is_published=True, visibility='unlisted',
            intro={'title': {'en': 'What residents said'}, 'body': {'en': 'Over three weeks 146 residents answered.'},
                   'eyebrow': {'en': 'Neighbourhood plan · survey report'}})

    def block(self, block_type, **fields):
        fields.setdefault('order', self.report.blocks.count())
        return ReportBlock.objects.create(report=self.report, block_type=block_type, **fields)

    def page(self):
        return self.client.get(reverse('public_results', args=[self.report.slug])).content.decode()


class LinearStoryTest(_Story):
    """Requirement: A report is a linear story."""

    def test_the_opening(self):
        """
        GIVEN a report with a line above the title, a title and an opening paragraph
        WHEN its page is opened
        THEN the line stands above the title and the paragraph under it
        """
        html = self.page()
        eyebrow, title, lead = (html.index('Neighbourhood plan · survey report'), html.index('<h1>What residents said'),
                                html.rindex('Over three weeks 146 residents answered.'))
        self.assertTrue(eyebrow < title < lead)

    def test_two_half_width_blocks(self):
        """
        GIVEN two consecutive half-width blocks followed by a full-width one
        WHEN the report is rendered
        THEN the two share a row and the third has its own
        """
        self.block('heading', content={'en': 'Left'}, width='half')
        self.block('heading', content={'en': 'Right'}, width='half')
        self.block('heading', content={'en': 'Below'})
        rows = build_context(self.report)['rows']
        self.assertEqual([[b['title'] for b in row] for row in rows], [['Left', 'Right'], ['Below']])
        self.assertEqual(self.page().count('class="rp-row pair"'), 1)

    def test_a_lone_half_width_block(self):
        """
        GIVEN a half-width block followed by a full-width one, then three halves in a row
        WHEN the rows are built
        THEN the lone half has its own row, and the three make a pair and a single
        """
        blocks = [{'id': i, 'width': w} for i, w in enumerate(['half', 'full', 'half', 'half', 'half'])]
        self.assertEqual([[b['id'] for b in row] for row in story_rows(blocks)], [[0], [1], [2, 3], [4]])


class AuthorBlocksTest(_Story):
    """Requirement: The author writes headings, text, key numbers and quotes."""

    def test_key_numbers(self):
        """
        GIVEN a Key numbers block with "447 | residents answered" and "1,921 | places pinned"
        WHEN the page is opened
        THEN it shows each number with its label
        """
        block = self.block('numbers')
        services.update_block(self.actor, block,
                              items=story.items_from_lines('numbers', '447 | residents answered\n1,921 | places pinned')['items'])
        html = self.page()
        self.assertIn('<li><b>447</b><span>residents answered</span></li>', html)
        self.assertIn('<li><b>1,921</b><span>places pinned</span></li>', html)

    def test_a_quote_with_its_source(self):
        """
        GIVEN a Quotes block with "Give us the bridge back. | Pin: needs attention"
        WHEN the page is opened
        THEN it shows the quote and its source line
        """
        block = self.block('quotes')
        services.update_block(self.actor, block,
                              items=story.items_from_lines('quotes', 'Give us the bridge back. | Pin: needs attention')['items'])
        html = self.page()
        self.assertIn('Give us the bridge back.', html)
        self.assertIn('<cite>Pin: needs attention</cite>', html)

    def test_script_in_a_text_block(self):
        """
        GIVEN a Text block saved with a script element and a bold word
        WHEN the page is opened
        THEN the bold word is kept and no script reaches the page
        """
        block = self.block('text')
        services.update_block(self.actor, block,
                              content='<p>Three places are <strong>green</strong>.</p><script>alert("x")</script>')
        html = self.page()
        self.assertIn('<strong>green</strong>', html)
        self.assertNotIn('alert("x")', html)

    def test_an_empty_block(self):
        """
        GIVEN a Quotes block with no quote and a Heading with no text
        WHEN the page is opened
        THEN neither is shown
        """
        quotes, heading = self.block('quotes'), self.block('heading')
        html = self.page()
        self.assertNotIn(f'data-block-id="{quotes.id}"', html)
        self.assertNotIn(f'data-block-id="{heading.id}"', html)
        self.assertIn('No results to show yet.', html)

    def test_a_page_frozen_before_text_was_rich(self):
        """
        GIVEN a frozen snapshot whose text block is plain text with an angle bracket
        WHEN the page is opened
        THEN the text is shown escaped
        """
        self.report.mode = 'frozen'
        self.report.snapshot_version = SNAPSHOT_VERSION
        self.report.snapshot = {'snapshot_version': SNAPSHOT_VERSION, 'lang': 'en', 'response_count': 0,
                                'blocks': [{'id': 1, 'block_type': 'text', 'viz': 'auto', 'title': '',
                                            'body': 'It takes <5 minutes <b>on foot</b>'}]}
        self.report.save()
        html = self.page()
        self.assertIn('It takes &lt;5 minutes &lt;b&gt;on foot&lt;/b&gt;', html)
