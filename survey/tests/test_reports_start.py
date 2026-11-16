"""Spec: reports-start (change reports-start, #705, epic #712).

A report starts from a card: a draft built by rules from what people answered, in one of four
arrangements, a blank report, or a copy; nothing unfinished reaches a visitor; the start page is
linked where the data is.
"""
from django.contrib.gis.geos import Point
from django.test import TestCase
from django.urls import reverse

from api.tests.helpers import make_member, make_pro_org, make_v1_survey
from reports import drafting
from reports.models import Report, ReportBlock
from survey.models import Answer, Question, SurveySection, SurveySession
from survey.services.context import Actor

LONG = 'The crossing by the school is where I hold my breath every single morning.'


class _Start(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org('StartOrg', 'reportstartowner')
        self.survey, self.section = make_v1_survey(self.org, self.owner, name='Riverside plan', status='published')
        SurveySection.objects.filter(pk=self.section.pk).update(title='About you')
        self.places = SurveySection.objects.create(survey_header=self.survey, name='s2', title='Places', code='S2')
        SurveySection.objects.filter(pk=self.section.pk).update(next_section=self.places)
        self.transport = self.question(self.section, 'TRANSPORT', 'choice', 0,
                                       choices=[{'code': 1, 'name': 'Car'}, {'code': 2, 'name': 'Bike'}])
        self.unanswered = self.question(self.section, 'NOBODY', 'choice', 1, choices=[{'code': 1, 'name': 'Yes'}])
        self.why = self.question(self.section, 'WHY', 'text', 2)
        self.spot = self.question(self.places, 'SPOT', 'point', 0)
        for i in range(4):
            s = SurveySession.objects.create(survey=self.survey)
            Answer.objects.create(survey_session=s, question=self.transport, selected_choices=[1 + i % 2])
            Answer.objects.create(survey_session=s, question=self.why, text=f'{LONG} ({i})')
            Answer.objects.create(survey_session=s, question=self.spot, point=Point(30.0 + i * 1e-5, 59.0))
        self.actor = Actor(user=self.owner, ip=None, surface='editor')
        self.login(self.owner)
        self.start = reverse('editor_report_start')

    def question(self, section, code, input_type, order, **fields):
        return Question.objects.create(survey_section=section, code=code, name=f'Question {code}',
                                       input_type=input_type, order_number=order, **fields)

    def login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def post(self, **data):
        data.setdefault('survey', str(self.survey.uuid))
        return self.client.post(self.start, data)

    def preview(self, report):
        return self.client.get(reverse('editor_report_preview', args=[report.uuid])).content.decode()


class CardsTest(_Start):
    """Requirement: A report starts from a card."""

    def test_one_click_drafts_a_report(self):
        """
        GIVEN an editor on the start page with a survey chosen
        WHEN they press the "Consultation summary" card
        THEN a new unpublished report of that survey exists and its editor opens
        """
        page = self.client.get(self.start)
        self.assertContains(page, 'data-template="summary"')
        response = self.post(kind='draft', template='summary')
        report = Report.objects.get()
        self.assertRedirects(response, reverse('editor_report', args=[report.uuid]))
        self.assertEqual((report.survey_id, report.is_published, report.template),
                         (self.survey.id, False, 'summary'))

    def test_a_blank_report(self):
        """
        GIVEN an editor on the start page
        WHEN they press "Blank report"
        THEN an unpublished report without a home survey opens in the editor
        """
        response = self.post(kind='blank')
        report = Report.objects.get()
        self.assertRedirects(response, reverse('editor_report', args=[report.uuid]))
        self.assertEqual((report.survey_id, report.is_published, report.blocks.count()), (None, False, 0))

    def test_a_viewer(self):
        """
        GIVEN a viewer
        WHEN they open the start page or post a card
        THEN the answer is 404 and no report is made
        """
        self.login(make_member(self.org, 'startviewer', role='viewer'))
        self.assertEqual(self.client.get(self.start).status_code, 404)
        self.assertEqual(self.post(kind='blank').status_code, 404)
        self.assertFalse(Report.objects.exists())

    def test_no_survey_to_draft_from(self):
        """
        GIVEN a workspace without a published survey
        WHEN an editor opens the start page
        THEN it offers the blank report and says why no draft is offered
        """
        other_org, other_owner = make_pro_org('EmptyStartOrg', 'emptystartowner')
        self.client.force_login(other_owner)
        session = self.client.session
        session['active_org_id'] = other_org.id
        session.save()
        html = self.client.get(self.start).content.decode()
        self.assertIn('data-testid="report-start-no-survey"', html)
        self.assertIn('data-testid="report-start-blank"', html)
        self.assertNotIn('data-template="summary"', html)


class RulesTest(_Start):
    """Requirement: The draft is built by rules from what people answered."""

    def test_a_block_for_every_answered_question(self):
        """
        GIVEN an answered choice question, an answered map question and a choice question nobody answered
        WHEN a draft is made
        THEN it holds a chart for the first, a map for the second and nothing for the third
        """
        report = drafting.build_draft(self.actor, self.survey)
        codes = {(b.block_type, b.question_code) for b in report.blocks.all() if b.question_code}
        self.assertEqual(codes, {('chart', 'TRANSPORT'), ('map', 'SPOT')})
        headings = [b.content['en'] for b in report.blocks.filter(block_type='heading')]
        self.assertEqual(headings, ['About you', 'Places', 'What happens next'])
        self.assertIn('{responses}', report.intro['body']['en'])

    def test_who_took_part_comes_first(self):
        """
        GIVEN a draft
        WHEN its blocks are read in order
        THEN key numbers come first and the engagement block is the first data block
        """
        report = drafting.build_draft(self.actor, self.survey)
        types = [b.block_type for b in report.blocks.all()]
        self.assertEqual(types[:2], ['numbers', 'engagement'])
        self.assertEqual(types.index('engagement'), min(types.index(t) for t in ('engagement', 'chart', 'map')))
        self.assertEqual(sorted(b.order for b in report.blocks.all()), list(range(len(types))))

    def test_the_surveys_own_report_stays(self):
        """
        GIVEN a survey that already has a report with one block
        WHEN a draft is made
        THEN that report keeps its block and a second report exists
        """
        first = Report.objects.create(survey=self.survey, slug='first-report')
        ReportBlock.objects.create(report=first, block_type='chart', question=self.transport)
        draft = drafting.build_draft(self.actor, self.survey)
        self.assertNotEqual(draft.pk, first.pk)
        self.assertEqual(first.blocks.count(), 1)
        self.assertEqual(self.survey.report.pk, first.pk)


class UnfinishedTest(_Start):
    """Requirement: Nothing unfinished reaches a visitor."""

    def test_quotes_to_pick_from(self):
        """
        GIVEN a free-text question with answers and a draft published as it is
        WHEN the report's page is opened
        THEN it shows none of those answers, and the editor holds them in a hidden Quotes block
        """
        report = drafting.build_draft(self.actor, self.survey)
        quotes = report.blocks.get(block_type='quotes')
        self.assertTrue(quotes.is_hidden)
        self.assertEqual(len(quotes.config['items']), 4)
        report.is_published = True
        report.save()
        html = self.client.get(reverse('public_results', args=[report.slug])).content.decode()
        self.assertNotIn('hold my breath', html)

    def test_prompts_are_hidden(self):
        """
        GIVEN a draft published as it is
        WHEN its page is opened
        THEN it shows no prompt
        """
        report = drafting.build_draft(self.actor, self.survey)
        html = self.preview(report)
        self.assertNotIn('Write what this part of the survey showed', html)
        self.assertNotIn('Say what will be done', html)
        self.assertTrue(report.blocks.filter(block_type='text', is_hidden=True).exists())
        self.assertFalse(report.is_published)


class ArrangementsTest(_Start):
    """Requirement: A draft comes in four arrangements."""

    def test_every_arrangement_renders(self):
        """
        GIVEN one survey
        WHEN each of the four arrangements is made through the start page
        THEN each report's preview opens and shows at least one block
        """
        for key in drafting.TEMPLATES:
            self.post(kind='draft', template=key)
            report = Report.objects.get(template=key)
            html = self.preview(report)
            self.assertIn('data-block-id=', html, key)
            self.assertIn(report.title.split(':')[0], html, key)
        self.assertEqual(Report.objects.count(), 4)

    def test_the_council_paper_uses_tables(self):
        """
        GIVEN the Council paper
        WHEN its blocks are read
        THEN its headings are numbered and its choice block is a table
        """
        report = drafting.build_draft(self.actor, self.survey, 'council')
        headings = [b.content['en'] for b in report.blocks.filter(block_type='heading')]
        self.assertEqual(headings, ['1. Background', '2. Who took part', '3. What residents said', '4. Places',
                                    '5. Recommendations'])
        self.assertEqual(report.blocks.get(block_type='chart').viz, 'table')

    def test_the_update_and_you_said(self):
        """
        GIVEN the Engagement update and You said — we did
        WHEN their blocks are read
        THEN the update holds numbers, engagement and the map with the link to take part; the other
             puts each result under a "You said" heading
        """
        update = drafting.build_draft(self.actor, self.survey, 'update')
        self.assertEqual([b.block_type for b in update.blocks.all()], ['numbers', 'engagement', 'map'])
        self.assertTrue(update.show_participate_cta)
        yousaid = drafting.build_draft(self.actor, self.survey, 'yousaid')
        self.assertEqual([b.block_type for b in yousaid.blocks.all()],
                         ['heading', 'chart', 'text', 'heading', 'map', 'text'])
        self.assertTrue(yousaid.blocks.filter(block_type='heading').first().content['en'].startswith('You said: '))


class CopyTest(_Start):
    """Requirement: A report can be copied."""

    def test_copying(self):
        """
        GIVEN a published draft
        WHEN an editor copies it from the start page
        THEN a second report with the same blocks exists, unpublished, and the first is unchanged
        """
        original = drafting.build_draft(self.actor, self.survey)
        original.is_published = True
        original.save()
        before = [b.block_type for b in original.blocks.all()]
        response = self.post(kind='copy', report=str(original.uuid))
        copy = Report.objects.exclude(pk=original.pk).get()
        self.assertRedirects(response, reverse('editor_report', args=[copy.uuid]))
        self.assertEqual([b.block_type for b in copy.blocks.all()], before)
        self.assertEqual((copy.is_published, copy.visibility, copy.template), (False, 'workspace', 'summary'))
        self.assertTrue(copy.title.endswith('(copy)'))
        original.refresh_from_db()
        self.assertTrue(original.is_published)


class EntryTest(_Start):
    """Requirement: A report can be started where the data is."""

    def test_from_responses(self):
        """
        GIVEN an editor on the Responses page of a published survey
        WHEN the page is rendered
        THEN it offers "Make a report" leading to the start page with that survey chosen
        """
        html = self.client.get(reverse('editor_survey_analytics', args=[self.survey.uuid])).content.decode()
        self.assertIn(f'{self.start}?survey={self.survey.uuid}&amp;from=responses', html)
        page = self.client.get(self.start, {'survey': str(self.survey.uuid), 'from': 'responses'})
        self.assertEqual(page.context['chosen'].pk, self.survey.pk)
        self.assertEqual(page.context['surface'], 'responses')
