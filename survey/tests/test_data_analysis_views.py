"""Spec: data-analysis-views (change data-analysis-views, #692, epic #712).

Engagement, cross-tab, coverage and density as view kinds of the Data module: what a dataset holds
decides the kinds it takes, every count leaves masked under K, a map kind is a grid with cells
under K left out, and every surface reads the same result.
"""
from datetime import timedelta

from django.contrib.gis.geos import LineString, Point, Polygon
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from api.tests.helpers import V1Client, make_pro_org, make_v1_survey, mint
from data import dataviews, services
from data.datasets import sync
from data.models import Dataset, DatasetView
from survey.models import Answer, Question, SurveyMapLayer, SurveySession
from survey.services.context import Actor

TRANSPORT = [{'code': 1, 'name': 'Car'}, {'code': 2, 'name': 'Bike'}, {'code': 3, 'name': 'Bus'}]
AGE = [{'code': 1, 'name': 'Under 30'}, {'code': 2, 'name': 'Over 60'}]


def _square(x, y, size=0.002):
    return Polygon(((x, y), (x + size, y), (x + size, y + size), (x, y + size), (x, y)))


class _Fixture(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org('AnalysisOrg', 'analysisowner')
        self.survey, self.section = make_v1_survey(self.org, self.owner, name='Riverside', status='published')
        self.actor = Actor(user=self.owner, ip='', surface='test')
        self.client.force_login(self.owner)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def question(self, code, input_type, **fields):
        return Question.objects.create(survey_section=self.section, code=code, name=fields.pop('name', code),
                                       input_type=input_type, **fields)

    def session(self, **fields):
        return SurveySession.objects.create(survey=self.survey, **fields)

    def dataset(self, kind, code=''):
        sync(self.org)
        return Dataset.objects.get(kind=kind, survey=self.survey, question_code=code)

    def view(self, dataset, kind, **config):
        return services.create_view(self.actor, dataset, f'{kind} view', kind=kind, config=config)


class KindsTest(_Fixture):
    """Requirement: A view kind follows what its dataset holds."""

    def test_coverage_of_a_line_question(self):
        """
        GIVEN the answers dataset of a line question
        WHEN an editor creates a coverage view on it
        THEN the view is saved with kind coverage
        """
        self.question('ROUTE', 'line')
        view = self.view(self.dataset('answers', 'ROUTE'), 'coverage')
        self.assertEqual(view.kind, 'coverage')

    def test_coverage_of_a_point_question(self):
        """
        GIVEN the answers dataset of a point question
        WHEN an editor posts a coverage view on its page
        THEN the view is refused and the page names the kinds the dataset allows
        """
        self.question('SPOT', 'point')
        ds = self.dataset('answers', 'SPOT')
        self.assertEqual(dataviews.kinds_for(ds), ('grid', 'density'))
        r = self.client.post(reverse('editor_data_dataset', args=[ds.pk]),
                             {'action': 'view_create', 'name': 'Covered', 'kind': 'coverage'})
        self.assertFalse(DatasetView.objects.exists())
        self.assertIn('Density', r.content.decode())

    def test_crosstab_on_a_layer(self):
        """
        GIVEN a layer dataset
        WHEN a view of kind crosstab is posted on it
        THEN the view is refused
        """
        layer = SurveyMapLayer.objects.create(survey=None, organization=self.org, name='Trees', geojson='')
        sync(self.org)
        with self.assertRaises(services.DataRefused):
            services.create_view(self.actor, Dataset.objects.get(layer=layer), 'Table', kind='crosstab',
                                 config={'rows': 'A', 'columns': 'B'})


class EngagementTest(_Fixture):
    """Requirement: An engagement view counts opened, answered and finished."""

    def setUp(self):
        super().setUp()
        q = self.question('WHY', 'text')
        now = timezone.now()
        # 6 clean sessions over two days: 4 answered, 3 of them finished.
        for i in range(6):
            s = self.session(start_datetime=now - timedelta(days=0 if i < 5 else 3),
                             required_complete=i < 3)
            if i < 4:
                Answer.objects.create(survey_session=s, question=q, text='because')
        self.question_why = q
        self.view_obj = self.view(self.dataset('responses'), 'engagement')

    def steps(self):
        data = dataviews.result(self.view_obj)
        return {s['key']: s['display'] for s in data['steps']}, data

    def test_the_three_steps(self):
        """
        GIVEN 6 clean sessions of which 4 hold an answer and 3 are completed, K = 3
        WHEN the engagement view is computed
        THEN its steps read opened 6, answered 4, finished 3
        """
        steps, _data = self.steps()
        self.assertEqual(steps, {'opened': '6', 'answered': '4', 'finished': '3'})

    def test_moderated_and_trashed_sessions_do_not_count(self):
        """
        GIVEN one more session on hold and another in the trash, both with an answer
        WHEN the engagement view is computed
        THEN the steps do not change
        """
        held = self.session(validation_status='on_hold', start_datetime=timezone.now())
        trashed = self.session(is_deleted=True, start_datetime=timezone.now())
        for s in (held, trashed):
            Answer.objects.create(survey_session=s, question=self.question_why, text='x')
        steps, _data = self.steps()
        self.assertEqual(steps, {'opened': '6', 'answered': '4', 'finished': '3'})

    def test_a_quiet_day_is_masked(self):
        """
        GIVEN a day of collection with a single opened session, K = 3
        WHEN the engagement view is computed
        THEN that day's opened count shows as "<3" and carries no value
        """
        _steps, data = self.steps()
        self.assertEqual(data['period'], 'day')
        quiet = data['series'][0]['opened']
        self.assertEqual((quiet['display'], quiet['value'], quiet['masked']), ('<3', None, True))
        self.assertEqual(data['series'][-1]['opened']['value'], 5)


class CrosstabTest(_Fixture):
    """Requirement: A cross-tab view counts distinct respondents for two questions."""

    def setUp(self):
        super().setUp()
        self.transport = self.question('TRANSPORT', 'choice', choices=TRANSPORT)
        self.age = self.question('AGE', 'choice', choices=AGE)
        self.answer(4, transport=1, age=1)      # Car, under 30
        self.answer(3, transport=2, age=2)      # Bike, over 60
        self.ds = self.dataset('responses')

    def answer(self, n, transport, age, survey=None, questions=None):
        transport_q, age_q = questions or (self.transport, self.age)
        for _i in range(n):
            s = SurveySession.objects.create(survey=survey or self.survey)
            Answer.objects.create(survey_session=s, question=transport_q, selected_choices=[transport])
            Answer.objects.create(survey_session=s, question=age_q, selected_choices=[age])

    def table(self):
        view = DatasetView.objects.filter(kind='crosstab').first() or self.view(
            self.ds, 'crosstab', rows='TRANSPORT', columns='AGE')
        return dataviews.result(view)

    def test_counts_per_pair(self):
        """
        GIVEN 4 respondents answered Car and Under 30, 3 answered Bike and Over 60, K = 3
        WHEN the cross-tab of transport by age is computed
        THEN the table shows 4 and 3 in those cells and 0 elsewhere
        """
        data = self.table()
        self.assertEqual([[c['display'] for c in line] for line in data['cells']],
                         [['4', '0'], ['0', '3'], ['0', '0']])
        self.assertEqual([i['label'] for i in data['rows']['items']], ['Car', 'Bike', 'Bus'])
        self.assertEqual(data['respondents']['value'], 7)

    def test_a_small_cell_is_masked_and_its_margins_withheld(self):
        """
        GIVEN one respondent answered Bike and Under 30, K = 3
        WHEN the cross-tab is computed
        THEN that cell shows "<3" with no value; the totals of its row and column and the number
             who answered both are withheld, so no total gives the cell away
        """
        self.answer(1, transport=2, age=1)
        data = self.table()
        cell = data['cells'][1][0]
        self.assertEqual((cell['display'], cell['value']), ('<3', None))
        self.assertEqual(data['rows']['items'][1]['total'], {'value': None, 'display': '—', 'masked': True})
        self.assertEqual(data['columns']['items'][0]['total']['value'], None)
        self.assertEqual(data['rows']['items'][0]['total']['value'], 4)        # the Car row gives nothing away
        self.assertEqual(data['respondents']['value'], None)
        import json
        self.assertNotIn('"value": 1,', json.dumps(data))

    def test_a_question_that_is_not_a_choice(self):
        """
        GIVEN a free-text question WHY
        WHEN a cross-tab view names it
        THEN the view is refused naming the question
        """
        self.question('WHY', 'text')
        with self.assertRaises(services.DataRefused) as ctx:
            self.view(self.ds, 'crosstab', rows='TRANSPORT', columns='WHY')
        self.assertIn('WHY', ctx.exception.message)

    def test_the_question_was_replaced_by_publishing(self):
        """
        GIVEN a cross-tab view, then the survey's questions replaced by new rows with the same codes
              (as publishing unpublished changes does) while the old rows move to an archived version
        WHEN the view is computed after 3 more respondents answered the new rows
        THEN it counts the answers of both versions
        """
        self.table()
        from survey.models import SurveyHeader, SurveySection
        archived = SurveyHeader.objects.create(organization=self.org, name='Riverside v1', is_canonical=False,
                                               canonical_survey=self.survey, version_number=1)
        SurveySession.objects.filter(survey=self.survey).update(survey=archived)
        SurveySection.objects.filter(pk=self.section.pk).update(survey_header=archived)
        section = SurveySection.objects.create(survey_header=self.survey, name='s', code='S1', is_head=True)
        new_transport = Question.objects.create(survey_section=section, code='TRANSPORT', name='Transport',
                                                input_type='choice', choices=TRANSPORT)
        new_age = Question.objects.create(survey_section=section, code='AGE', name='Age', input_type='choice',
                                          choices=AGE)
        self.answer(3, transport=1, age=1, questions=(new_transport, new_age))
        data = self.table()
        self.assertEqual(data['cells'][0][0]['value'], 7)
        self.assertEqual(data['cells'][1][1]['value'], 3)


class CellsTest(_Fixture):
    """Requirement: Coverage and density views are grids."""

    def test_overlapping_areas(self):
        """
        GIVEN 4 respondents each drew an area over the park and a fifth drew one elsewhere, K = 3
        WHEN the coverage view is computed
        THEN it holds cells with 4 respondents and a share of 0.8, and none where the fifth drew
        """
        q = self.question('PARK', 'polygon')
        for _i in range(4):
            Answer.objects.create(survey_session=self.session(), question=q, polygon=_square(30.0, 59.0))
        Answer.objects.create(survey_session=self.session(), question=q, polygon=_square(30.2, 59.2))
        data = dataviews.result(self.view(self.dataset('answers', 'PARK'), 'coverage'))
        self.assertTrue(data['features'])
        self.assertEqual({(f['properties']['respondents'], f['properties']['share']) for f in data['features']},
                         {(4, 0.8)})
        self.assertTrue(all(f['geometry']['coordinates'][0][0][0] < 30.1 for f in data['features']))
        self.assertEqual((data['respondents_total'], data['respondents_hidden']), (5, 1))

    def test_several_marks_from_one_respondent(self):
        """
        GIVEN 3 respondents placed 7 points between them in one cell, K = 3
        WHEN the density view is computed
        THEN the cell says 7 marks and 3 respondents
        """
        q = self.question('SPOT', 'point')
        for marks in (4, 2, 1):
            s = self.session()
            for i in range(marks):
                Answer.objects.create(survey_session=s, question=q, point=Point(30.0 + i * 1e-6, 59.0))
        data = dataviews.result(self.view(self.dataset('answers', 'SPOT'), 'density'))
        self.assertEqual([f['properties'] for f in data['features']], [{'respondents': 3, 'marks': 7}])
        self.assertEqual(data['max_marks'], 7)

    def test_many_marks_from_too_few_people(self):
        """
        GIVEN 2 respondents placed 20 points in one cell, K = 3
        WHEN the density view is computed
        THEN it holds no cell
        """
        q = self.question('SPOT', 'point')
        for _r in range(2):
            s = self.session()
            for i in range(10):
                Answer.objects.create(survey_session=s, question=q, point=Point(30.0 + i * 1e-6, 59.0))
        data = dataviews.result(self.view(self.dataset('answers', 'SPOT'), 'density'))
        self.assertEqual(data['features'], [])

    def test_a_line_is_never_sent(self):
        """
        GIVEN 3 respondents drew the same route
        WHEN the coverage view's GeoJSON is read
        THEN it holds polygons of cells only
        """
        q = self.question('ROUTE', 'line')
        for _i in range(3):
            Answer.objects.create(survey_session=self.session(), question=q,
                                  line=LineString((30.0, 59.0), (30.01, 59.0)))
        view = self.view(self.dataset('answers', 'ROUTE'), 'coverage')
        data = dataviews.result(view)
        self.assertTrue(data['features'])
        self.assertEqual({f['geometry']['type'] for f in data['features']}, {'Polygon'})


class SurfacesTest(_Fixture):
    """Requirement: An analysis view is read the same on every surface."""

    def setUp(self):
        super().setUp()
        transport = self.question('TRANSPORT', 'choice', choices=TRANSPORT, name='How do you travel?')
        age = self.question('AGE', 'choice', choices=AGE, name='Your age')
        for n, t, a in ((4, 1, 1), (1, 2, 1)):
            for _i in range(n):
                s = self.session()
                Answer.objects.create(survey_session=s, question=transport, selected_choices=[t])
                Answer.objects.create(survey_session=s, question=age, selected_choices=[a])
        self.ds = self.dataset('responses')

    def test_the_owner_reads_a_crosstab_over_the_api(self):
        """
        GIVEN a cross-tab with a cell of one respondent, K = 3
        WHEN the workspace owner reads the view's data with a token
        THEN that cell comes back masked
        """
        api = V1Client(self.client, mint(self.owner)[0])
        created = api.post(f'/datasets/{self.ds.pk}/views',
                           {'name': 'Travel by age', 'kind': 'crosstab',
                            'config': {'rows': 'TRANSPORT', 'columns': 'AGE'}})
        self.assertEqual(created.status_code, 201, created.content)
        data = api.get(f'/datasets/{self.ds.pk}/views/{created.json()["id"]}/data').json()
        self.assertEqual(data['cells'][1][0], {'value': None, 'display': '<3', 'masked': True})
        self.assertEqual(data['cells'][0][0]['value'], 4)

    def test_preview_on_the_dataset_page(self):
        """
        GIVEN an editor created a cross-tab from the dataset page
        WHEN they open its preview
        THEN the page shows the table with its masked cell and how many answered both questions
        """
        page = reverse('editor_data_dataset', args=[self.ds.pk])
        self.client.post(page, {'action': 'view_create', 'name': 'Travel by age', 'kind': 'crosstab',
                                'rows': 'TRANSPORT', 'columns': 'AGE'})
        view = DatasetView.objects.get(kind='crosstab')
        listing = self.client.get(page).content.decode()
        self.assertIn('How do you travel? × Your age', listing)
        html = self.client.get(reverse('editor_data_view', args=[self.ds.pk, view.pk])).content.decode()
        self.assertIn('&lt;3', html)
        self.assertIn('too small to show', html)
        self.assertNotIn('5 respondents', html)
        self.assertIn('Aggregated · K = 3', html)
