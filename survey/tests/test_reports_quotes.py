"""Spec: reports-quotes (change report-quotes-from-answers, #749, epic #712).

The Quotes block takes its quotes from the answers as well as from the author's keyboard: the block's
panel lists the written answers of a survey, a picked quote remembers the survey and question it came
from and whether it was cut since, the block has three layouts, and a quote carrying an email
address, a phone number or a web address is named before publishing and marked on the canvas.
"""
from django.test import TestCase
from django.urls import reverse

from api.tests.helpers import make_pro_org, make_v1_survey
from reports.checks import run
from reports.models import Report, ReportBlock
from reports.quotes import contact_flags
from survey.models import Answer, Question, SurveySession

LONG = 'The riverside path floods every spring and nobody clears the drains.'
SHORT = 'Too wet.'
OTHER = 'We would love more benches along the river near the old mill.'


class _Quotes(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org('QuotesOrg', 'reportquotesowner')
        self.survey, self.section = make_v1_survey(self.org, self.owner, name='Riverside', status='published')
        self.change = Question.objects.create(survey_section=self.section, code='CHANGE', name='What would you change?',
                                              input_type='text', order_number=1)
        self.like = Question.objects.create(survey_section=self.section, code='LIKE', name='What do you like?',
                                            input_type='text_line', order_number=2)
        self.answer(self.change, SHORT)
        self.answer(self.change, LONG)
        self.answer(self.like, OTHER)
        self.report = Report.objects.create(survey=self.survey, slug='riverside-quotes',
                                            intro={'title': {'en': 'What we heard'}})
        self.block = ReportBlock.objects.create(report=self.report, block_type='quotes', order=0)
        self.client.force_login(self.owner)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def answer(self, question, text, **session_fields):
        session = SurveySession.objects.create(survey=self.survey, **session_fields)
        Answer.objects.create(survey_session=session, question=question, text=text)
        return session

    def url(self, name, *args):
        return reverse(name, args=[self.report.uuid, *args])

    def picker(self, **params):
        return self.client.get(self.url('editor_report_block_quotes', self.block.id), params).content.decode()

    def save_rows(self, rows, **extra):
        data = {'rows': '1', 'autosave': '1', 'text': [r[0] for r in rows], 'source': [r[1] for r in rows],
                'ref': [r[2] if len(r) > 2 else '' for r in rows]}
        data.update(extra)
        response = self.client.post(self.url('editor_report_block_edit', self.block.id), data,
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.block.refresh_from_db()
        return self.block.config

    @property
    def ref(self):
        return f'{self.survey.uuid}:CHANGE'


class PickTest(_Quotes):
    """Requirement: The author picks quotes from the answers."""

    def test_answers_are_listed_readable_first(self):
        """
        GIVEN a survey with a short and a readable answer to "What would you change?"
        WHEN the Quotes block's picker opens
        THEN it offers both free-text questions, lists the readable answer before the short one,
             and says how many there are
        """
        html = self.picker()
        self.assertIn('What would you change?', html)
        self.assertIn('What do you like?', html)
        self.assertLess(html.index(LONG), html.index(SHORT))
        self.assertIn('2 answers', html)
        self.assertNotIn(OTHER, html)

    def test_another_question_and_a_search(self):
        """
        GIVEN answers to two questions
        WHEN the picker is asked for the second question, then for the first with the word "drains"
        THEN it lists that question's answer, then only the answer holding the word
        """
        self.assertIn(OTHER, self.picker(question='LIKE'))
        html = self.picker(question='CHANGE', q='DRAINS')
        self.assertIn(LONG, html)
        self.assertNotIn(SHORT, html)

    def test_moderated_and_trashed_sessions_are_left_out(self):
        """
        GIVEN one answer in a trashed session and one in a session not approved
        WHEN the picker opens
        THEN neither is listed
        """
        self.answer(self.change, 'A trashed answer that is long enough to be readable.', is_deleted=True)
        self.answer(self.change, 'A moderated answer that is long enough to be readable.',
                    validation_status='not_approved')
        html = self.picker()
        self.assertNotIn('A trashed answer', html)
        self.assertNotIn('A moderated answer', html)

    def test_a_survey_of_another_workspace(self):
        """
        GIVEN a survey of another workspace with written answers
        WHEN the picker is asked for it by its uuid
        THEN its answers are not listed
        """
        other_org, other_owner = make_pro_org('OtherOrg', 'reportquotesother')
        other, section = make_v1_survey(other_org, other_owner, name='Elsewhere', status='published')
        q = Question.objects.create(survey_section=section, code='CHANGE', name='Secret question', input_type='text')
        s = SurveySession.objects.create(survey=other)
        Answer.objects.create(survey_session=s, question=q, text='A secret answer from another workspace entirely.')
        html = self.picker(source=str(other.uuid))
        self.assertNotIn('secret answer', html)
        self.assertNotIn('Secret question', html)

    def test_a_picked_answer_is_shown_as_added(self):
        """
        GIVEN the readable answer was added to the block with its question as the source
        WHEN the picker opens again
        THEN that answer is shown as added and the other still offers "Add"
        """
        config = self.save_rows([(LONG, 'What would you change?', self.ref)])
        self.assertEqual(config['items'][0]['source'], 'What would you change?')
        html = self.picker()
        taken = html[html.index(LONG) - 120:html.index(LONG)]
        self.assertIn('is-taken', taken)
        self.assertIn('data-qpick-add', html[html.index(SHORT):])

    def test_a_viewer_of_the_survey_route_is_refused(self):
        """
        GIVEN a stranger signed in
        WHEN they ask for the picker of the report
        THEN the answer is 404
        """
        from django.contrib.auth.models import User
        stranger = User.objects.create_user('quotesstranger', password='x')
        self.client.force_login(stranger)
        response = self.client.get(self.url('editor_report_block_quotes', self.block.id))
        self.assertEqual(response.status_code, 404)


class OriginTest(_Quotes):
    """Requirement: A picked quote says where it comes from."""

    def test_a_picked_quote_keeps_its_origin(self):
        """
        GIVEN an answer added from the picker
        WHEN the block is saved
        THEN the quote keeps the survey and the question code and is not marked shortened,
             and the canvas labels it "From answers"
        """
        config = self.save_rows([(LONG, 'What would you change?', self.ref)])
        self.assertEqual(config['items'][0]['ref'], {'survey': str(self.survey.uuid), 'question': 'CHANGE'})
        self.assertNotIn('shortened', config['items'][0])
        page = self.client.get(self.url('editor_report')).content.decode()
        self.assertIn('From answers', page)
        self.assertNotIn('From answers, shortened', page)

    def test_the_author_trims_a_picked_quote(self):
        """
        GIVEN a picked quote
        WHEN the author cuts its last words and the block is saved
        THEN the quote is marked shortened, and the canvas says so
        """
        config = self.save_rows([('The riverside path floods every spring', 'What would you change?', self.ref)])
        self.assertTrue(config['items'][0]['shortened'])
        self.assertIn('From answers, shortened', self.client.get(self.url('editor_report')).content.decode())

    def test_a_quote_written_by_hand(self):
        """
        GIVEN a quote typed by the author, and one whose ref names no survey
        WHEN the block is saved
        THEN neither carries an origin, and readers' page shows neither label
        """
        config = self.save_rows([('Typed by hand.', ''), ('Odd ref.', '', '00000000-0000-0000-0000-000000000000:X')])
        self.assertEqual([set(item) for item in config['items']], [{'text', 'source'}, {'text', 'source'}])
        self.report.is_published = True
        self.report.save()
        page = self.client.get(reverse('public_results', args=[self.report.slug])).content.decode()
        self.assertIn('Typed by hand.', page)
        self.assertNotIn('From answers', page)


class LayoutTest(_Quotes):
    """Requirement: The quotes are laid out as the author chooses."""

    def test_cards(self):
        """
        GIVEN a Quotes block with two quotes
        WHEN the author sets its layout to cards
        THEN the layout is stored, survives a later save of the rows, and the page draws cards
        """
        self.save_rows([('One.', ''), ('Two.', '')], quote_style='cards')
        self.assertEqual(self.block.config['style'], 'cards')
        config = self.save_rows([('One.', ''), ('Two.', ''), ('Three.', '')])
        self.assertEqual(config['style'], 'cards')
        self.report.is_published = True
        self.report.save()
        page = self.client.get(reverse('public_results', args=[self.report.slug])).content.decode()
        self.assertIn('quotes quotes-cards', page)

    def test_an_unknown_layout_is_the_list(self):
        """
        GIVEN a save asking for a layout that does not exist
        WHEN the block is saved
        THEN it keeps the default list
        """
        config = self.save_rows([('One.', '')], quote_style='carousel')
        self.assertNotIn('style', config)

    def test_the_api_sets_the_layout(self):
        """
        GIVEN the blocks layer the REST API and MCP write through
        WHEN a spec sets the layout to pull, then to something else
        THEN the first is stored and the second refused
        """
        from reports import blocks
        from survey.services.context import Actor
        actor = Actor(user=self.owner, ip='127.0.0.1', surface='api')
        blocks.change(actor, self.block, {'style': 'pull', 'items': [{'text': 'A quote.'}]})
        self.block.refresh_from_db()
        self.assertEqual(self.block.config['style'], 'pull')
        with self.assertRaises(blocks.BlockRefused):
            blocks.change(actor, self.block, {'style': 'carousel'})


class ContactTest(_Quotes):
    """Requirement: Quotes that carry contact details are named before publishing."""

    def test_what_counts_as_contact_details(self):
        """
        GIVEN quotes with an email address, a phone number, a web address, a year and a plain sentence
        WHEN they are checked
        THEN the first three are flagged for what they carry and the last two are not
        """
        self.assertEqual(contact_flags('Write to anna.k@example.org please'), ['email'])
        self.assertEqual(contact_flags('Call me on +44 7700 900123 about the bench'), ['phone'])
        self.assertEqual(contact_flags('See www.riverside-friends.org for photos'), ['url'])
        self.assertEqual(contact_flags('It has been like this since 2019.'), [])
        self.assertEqual(contact_flags('More trees, fewer cars.'), [])

    def test_named_before_publishing_and_marked_on_the_canvas(self):
        """
        GIVEN a visible quote with a phone number and one without
        WHEN the checks run and the builder opens
        THEN "Before you publish" lists the first as carrying contact details, and the canvas marks
             that row only
        """
        phone = 'Call me on +44 7700 900123 about the bench'
        self.save_rows([(phone, ''), ('More trees, fewer cars.', '')])
        checks = run(self.report)
        item = next(i for i in checks.privacy if i.key == 'quote_contact')
        self.assertEqual(item.detail, [phone])
        self.assertTrue(checks.needs_ack)
        page = self.client.get(self.url('editor_report')).content.decode()
        self.assertEqual(page.count('class="rb-q-contact"'), 1)
        self.assertIn('Carries a phone number', page)


class InPlaceTest(_Quotes):
    """Requirement: The quotes are edited in place (and reports-editor: the empty Quotes block)."""

    def test_an_empty_block_shows_its_two_actions(self):
        """
        GIVEN a Quotes block with no quote
        WHEN the builder opens
        THEN the canvas shows "Pick from answers" and "Write a quote" with its line about readers,
             no quote row, and not the old note
        """
        page = self.client.get(self.url('editor_report')).content.decode()
        canvas = page[page.index('id="block-%d"' % self.block.id):]
        canvas = canvas[:canvas.index('</section>')]
        self.assertIn('data-testid="quotes-empty"', canvas)
        self.assertIn('Pick from answers', canvas)
        self.assertIn('Write a quote', canvas)
        self.assertIn('Readers see nothing here until the block has a quote.', canvas)
        self.assertNotIn('Left out of the report until it has a quote.', canvas)
        rows = canvas[canvas.index('data-rows="quotes"'):canvas.index('<template')]
        self.assertNotIn('<blockquote', rows)
        self.assertIn('data-rows-empty', canvas)

    def test_rows_carry_a_grip_and_their_order_is_saved(self):
        """
        GIVEN a block with three quotes
        WHEN the rows are posted in another order (what a drag sends)
        THEN the block keeps that order, and each row on the canvas has a drag grip
        """
        self.save_rows([('One.', ''), ('Two.', ''), ('Three.', '')])
        config = self.save_rows([('Three.', ''), ('One.', ''), ('Two.', '')])
        self.assertEqual([i['text'] for i in config['items']], ['Three.', 'One.', 'Two.'])
        page = self.client.get(self.url('editor_report')).content.decode()
        self.assertGreaterEqual(page.count('class="lb-row-grip"'), 3)
        self.assertIn('data-rows-sortable', page)

    def test_the_picker_is_outside_the_blocks_form(self):
        """
        GIVEN a Quotes block
        WHEN the builder opens
        THEN its panel holds the picker card after the block's form, so choosing a survey or
             typing a search never saves the block
        """
        page = self.client.get(self.url('editor_report')).content.decode()
        pane = page[page.index('data-pane="%d"' % self.block.id):]
        self.assertLess(pane.index('</form>'), pane.index('data-quote-picker'))
