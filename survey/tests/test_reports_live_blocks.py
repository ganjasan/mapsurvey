"""Spec: reports-live-blocks (change reports-live-blocks, #704, epic #712).

Blocks that follow the data: a cross-tab and an engagement block over the Data module's analysis
views, a map that may show the marks themselves when its author says so, and numbers in the text
that are filled from the survey.
"""
import json

from django.contrib.gis.geos import Point
from django.test import TestCase
from django.urls import reverse

from api.tests.helpers import make_pro_org, make_v1_survey
from data.models import DatasetView
from reports import services
from reports.models import Report, ReportBlock
from reports.render import ReportService
from survey.models import Answer, Question, SurveySession
from survey.services.context import Actor

TRANSPORT = [{'code': 1, 'name': 'Car'}, {'code': 2, 'name': 'Bike'}]
AGE = [{'code': 1, 'name': 'Under 30'}, {'code': 2, 'name': 'Over 60'}]


class _Live(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org('LiveOrg', 'liveblocksowner')
        self.survey, self.section = make_v1_survey(self.org, self.owner, name='Riverside', status='published')
        self.transport = Question.objects.create(survey_section=self.section, code='TRANSPORT', name='Transport',
                                                 input_type='choice', choices=TRANSPORT)
        self.age = Question.objects.create(survey_section=self.section, code='AGE', name='Age',
                                           input_type='choice', choices=AGE)
        self.spot = Question.objects.create(survey_section=self.section, code='SPOT', name='Where', input_type='point')
        self.report = Report.objects.create(survey=self.survey, slug='riverside-story', is_published=True)
        self.actor = Actor(user=self.owner, ip=None, surface='editor')
        self.client.force_login(self.owner)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def respond(self, n, transport=None, age=None, points=0, **session_fields):
        sessions = []
        for _i in range(n):
            s = SurveySession.objects.create(survey=self.survey, **session_fields)
            if transport:
                Answer.objects.create(survey_session=s, question=self.transport, selected_choices=[transport])
            if age:
                Answer.objects.create(survey_session=s, question=self.age, selected_choices=[age])
            for i in range(points):
                Answer.objects.create(survey_session=s, question=self.spot, point=Point(30.0 + i * 1e-5, 59.0))
            sessions.append(s)
        return sessions

    def page(self):
        from django.core.cache import cache
        cache.clear()
        return self.client.get(reverse('public_results', args=[self.report.slug])).content.decode()

    def add(self, **post):
        return self.client.post(reverse('editor_report_block_add', args=[self.report.uuid]), post)


class CrosstabBlockTest(_Live):
    """Requirement: A cross-tab block shows two questions against each other."""

    def setUp(self):
        super().setUp()
        self.respond(4, transport=1, age=1)
        self.respond(1, transport=2, age=1)

    def test_adding_a_crosstab(self):
        """
        GIVEN two choice questions answered by five people
        WHEN an editor adds a cross-tab of transport by age
        THEN the page shows a table with the transport choices in rows and the age choices in columns
        """
        self.assertEqual(self.add(block_type='crosstab', rows='TRANSPORT', columns='AGE').status_code, 302)
        html = self.page()
        self.assertIn('<th scope="row">Car</th>', html)
        self.assertIn('<th scope="col">Under 30</th>', html)
        self.assertIn('<td>4</td>', html)

    def test_a_small_group(self):
        """
        GIVEN one respondent answered Bike and Under 30, K = 3
        WHEN the page is rendered
        THEN that cell reads "<3" and the block's payload carries no value for it
        """
        block = services.add_view_block(self.actor, self.report, 'crosstab', self.survey, rows='TRANSPORT', columns='AGE')
        payload = ReportService(self.report)._build_block(block)
        self.assertEqual(payload['data']['cells'][1][0], {'value': None, 'display': '<3', 'masked': True})
        self.assertIn('<td class="masked">&lt;3</td>', self.page())

    def test_the_reports_own_k(self):
        """
        GIVEN the same table and the report's K set to 1
        WHEN the block is rendered
        THEN the cell shows 1
        """
        block = services.add_view_block(self.actor, self.report, 'crosstab', self.survey, rows='TRANSPORT', columns='AGE')
        self.report.k_anonymity_threshold = 1
        self.report.save()
        payload = ReportService(self.report)._build_block(block)
        self.assertEqual(payload['data']['cells'][1][0]['value'], 1)

    def test_the_view_is_listed_in_data(self):
        """
        GIVEN a cross-tab block
        WHEN the responses dataset's views are read and its view is deleted
        THEN the dataset has a cross-tab view, and deleting it is refused while the block shows it
        """
        from data import services as data_services
        block = services.add_view_block(self.actor, self.report, 'crosstab', self.survey, rows='TRANSPORT', columns='AGE')
        view = DatasetView.objects.get(kind='crosstab')
        self.assertEqual((block.view_id, view.config), (view.pk, {'rows': 'TRANSPORT', 'columns': 'AGE'}))
        with self.assertRaises(data_services.DataRefused):
            data_services.delete_view(self.actor, view)
        again = services.add_view_block(self.actor, self.report, 'crosstab', self.survey, rows='TRANSPORT', columns='AGE')
        self.assertEqual(again.view_id, view.pk)

    def test_the_same_question_twice(self):
        """
        GIVEN an editor names one question for rows and columns
        WHEN the block is added
        THEN it is refused with a message and nothing is added
        """
        response = self.add(block_type='crosstab', rows='AGE', columns='AGE')
        self.assertEqual(response.status_code, 400)
        self.assertIn('two different questions', response.content.decode())
        self.assertFalse(ReportBlock.objects.exists())


class EngagementBlockTest(_Live):
    """Requirement: An engagement block shows who took part."""

    def test_the_three_steps(self):
        """
        GIVEN 6 clean sessions of which 4 answered and 3 finished
        WHEN an engagement block is added and the page opened
        THEN it shows 6 opened, 4 answered and 3 finished
        """
        self.respond(3, transport=1)
        self.respond(1, transport=1, required_complete=False)
        self.respond(2)
        self.assertEqual(self.add(block_type='engagement').status_code, 302)
        block = ReportBlock.objects.get(block_type='engagement')
        steps = {s['key']: s['display'] for s in ReportService(self.report)._build_block(block)['data']['steps']}
        self.assertEqual(steps, {'opened': '6', 'answered': '4', 'finished': '3'})
        html = self.page()
        self.assertIn('<b>6</b><span>opened the survey</span>', html)
        self.assertIn('<b>3</b><span>finished</span>', html)


class MarksTest(_Live):
    """Requirement: The author of a report may show the marks of a map block."""

    def setUp(self):
        super().setUp()
        self.respond(5, points=1)
        self.block = ReportBlock.objects.create(report=self.report, block_type='map', question=self.spot)
        self.edit = reverse('editor_report_block_edit', args=[self.report.uuid, self.block.pk])

    def payload(self):
        self.block.refresh_from_db()
        return ReportService(self.report)._build_block(self.block)

    def test_off_by_default(self):
        """
        GIVEN a new map block
        WHEN it is rendered
        THEN its payload holds cells and no mark
        """
        payload = self.payload()
        self.assertEqual(payload['data_type'], 'grid')
        self.assertNotIn('marks', payload)

    def test_switched_on(self):
        """
        GIVEN an editor switches "Show the marks themselves" on
        WHEN the block is rendered
        THEN the payload holds 5 point geometries with empty properties and no cell
        """
        self.client.post(self.edit, {'show_marks_present': '1', 'show_marks': 'on'},
                         HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        payload = self.payload()
        self.assertEqual(payload['data_type'], 'marks')
        self.assertEqual([(f['geometry']['type'], f['properties']) for f in payload['marks']['features']],
                         [('Point', {})] * 5)
        self.assertNotIn('cells', payload)
        self.assertNotIn('session', json.dumps(payload))

    def test_switched_off_again(self):
        """
        GIVEN the marks were on
        WHEN an autosave arrives without the box ticked
        THEN the payload holds cells again
        """
        self.block.config = {'marks': True}
        self.block.save()
        self.client.post(self.edit, {'show_marks_present': '1'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(self.payload()['data_type'], 'grid')


class TokensTest(_Live):
    """Requirement: Numbers in the text may follow the data."""

    def text(self, html):
        return ReportBlock.objects.create(report=self.report, block_type='text', content={'en': html},
                                          order=self.report.blocks.count())

    def test_a_live_number(self):
        """
        GIVEN a Text block "{responses} residents answered" and 4 answers
        WHEN the page is opened, and again after a fifth answer
        THEN it says 4, then 5
        """
        self.text('<p>{responses} residents answered</p>')
        self.respond(4, transport=1)
        self.assertIn('4 residents answered', self.page())
        self.respond(1, transport=1)
        self.assertIn('5 residents answered', self.page())

    def test_a_frozen_report(self):
        """
        GIVEN the report frozen at 4 answers, with the token in a text and in the opening
        WHEN a fifth answer arrives
        THEN the page still says 4 in both
        """
        self.text('<p>{responses} residents answered</p>')
        self.report.intro = {'title': {'en': 'T'}, 'body': {'en': 'So far {responses} people.'}}
        self.report.save()
        self.respond(4, transport=1)
        services.freeze(self.actor, self.report)
        self.respond(1, transport=1)
        html = self.page()
        self.assertIn('4 residents answered', html)
        self.assertIn('So far 4 people.', html)

    def test_marks_of_a_question(self):
        """
        GIVEN a key number "{marks:SPOT}" and 7 points from 4 residents
        WHEN the page is opened
        THEN it shows 7, and {respondents:SPOT} shows 4
        """
        ReportBlock.objects.create(report=self.report, block_type='numbers', config={'items': [
            {'value': '{marks:SPOT}', 'label': 'places'}, {'value': '{respondents:SPOT}', 'label': 'people'}]})
        self.respond(3, points=2)
        self.respond(1, points=1)
        html = self.page()
        self.assertIn('<b>7</b><span>places</span>', html)
        self.assertIn('<b>4</b><span>people</span>', html)

    def test_a_count_under_k(self):
        """
        GIVEN a token that counts 2 and K = 3
        WHEN the page is opened
        THEN it shows "<3"
        """
        self.text('<p>{responses} so far</p>')
        self.respond(2, transport=1)
        self.assertIn('&lt;3 so far', self.page())

    def test_a_token_that_cannot_be_filled(self):
        """
        GIVEN a report without a home survey saying "{responses}", and one naming an unknown code
        WHEN their pages are opened
        THEN the tokens are shown as written
        """
        self.text('<p>{marks:NOPE} marks</p>')
        self.assertIn('{marks:NOPE} marks', self.page())
        loose = Report.objects.create(organization=self.org, slug='no-home', is_published=True)
        ReportBlock.objects.create(report=loose, block_type='text', content={'en': '<p>{responses} answered</p>'})
        html = self.client.get(reverse('public_results', args=['no-home'])).content.decode()
        self.assertIn('{responses} answered', html)
