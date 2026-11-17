"""Spec: data-api (change data-api, #674, epic #676).

The Data module in REST API v1 and MCP: an agent uploads, describes and links a register with the
MCP tools alone; REST reads and writes datasets under the editor's rules.
"""
import json
from unittest.mock import patch

from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from api.tests.helpers import V1Client, make_pro_org, make_v1_survey, mint
from data.datasets import sync
from data.models import Dataset, DatasetVersion
from mcp.tests.helpers import McpClient, data_of, error_of
from survey.models import Answer, Question, SurveySession

CSV = ('TREE_ID,SPECIES,TR_HGT_M,INSP_EMAIL,latitude,longitude\n'
       'T1,Lime,12,a@council.example,51.50,-0.12\nT2,Oak,9,b@council.example,51.51,-0.13\n')


def _eager():
    from data.tasks import run_data_import, run_data_version
    return (patch('data.tasks.run_data_import.delay', side_effect=lambda job_id: run_data_import(job_id)),
            patch('data.tasks.run_data_version.delay',
                  side_effect=lambda job_id, apply=False: run_data_version(job_id, apply)))


class _ApiFixture(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org('ApiDataOrg', 'apidataowner')
        self.survey, self.section = make_v1_survey(self.org, self.owner, name='Trees survey', status='published')
        self.token = mint(self.owner)[0]
        for p in _eager():
            p.start()
            self.addCleanup(p.stop)


class McpTest(_ApiFixture):
    """Requirement: An agent works with Data through MCP alone."""

    def setUp(self):
        super().setUp()
        self.mcp = McpClient(self.client, self.token)
        self.mcp.initialize()

    def upload(self):
        job = data_of(self.mcp.call('upload_dataset', {'filename': 'trees.csv', 'content': CSV}))
        job = data_of(self.mcp.call('get_dataset_job', {'job_id': job['id']}))
        self.assertEqual(job['status'], 'done', job)
        return job['dataset']

    def test_upload_describe_link(self):
        """
        GIVEN an MCP session of a workspace owner
        WHEN the agent uploads a tree CSV, sets its licence, labels a field, makes it public and links it into a survey
        THEN the survey's layer GeoJSON carries the trees with the field and no private column
        """
        ds_id = self.upload()
        ds = data_of(self.mcp.call('get_dataset', {'dataset_id': ds_id}))
        self.assertTrue(next(f for f in ds['fields'] if f['name'] == 'INSP_EMAIL')['private'])
        data_of(self.mcp.call('update_dataset', {'dataset_id': ds_id, 'licence': 'cc-by-4.0',
                                                 'theme': 'ENVI', 'privacy_class': 'public', 'tags': ['Riverside']}))
        ds = data_of(self.mcp.call('set_dataset_fields', {'dataset_id': ds_id,
                                                          'fields': [{'name': 'TR_HGT_M', 'label': 'Tree height (m)'}]}))
        self.assertEqual((ds['licence'], ds['privacy_class']), ('cc-by-4.0', 'public'))
        self.assertEqual(next(f for f in ds['fields'] if f['name'] == 'TR_HGT_M')['label'], 'Tree height (m)')
        link = data_of(self.mcp.call('link_dataset', {'survey': str(self.survey.uuid), 'dataset_id': ds_id}))
        layer_id = Dataset.objects.get(pk=ds_id).layer_id
        self.client.logout()
        url = reverse('survey_layer_geojson', kwargs={'survey_slug': str(self.survey.uuid), 'layer_id': layer_id})
        body = self.client.get(url).content.decode()
        self.assertIn('TR_HGT_M', body)
        self.assertIn('Lime', body)
        self.assertNotIn('council.example', body)
        self.assertTrue(link['id'])

    def test_private_dataset_cannot_be_linked(self):
        """
        GIVEN a freshly uploaded (private) dataset
        WHEN the agent links it into a survey
        THEN the call is refused with the message to make it public first
        """
        ds_id = self.upload()
        err = error_of(self.mcp.call('link_dataset', {'survey': str(self.survey.uuid), 'dataset_id': ds_id}))
        self.assertIn('public', json.dumps(err))


class RestTest(_ApiFixture):
    """Requirement: The REST API reads and writes datasets under the editor's rules."""

    def setUp(self):
        super().setUp()
        self.api = V1Client(self.client, self.token)
        r = self.client.post('/api/v1/datasets', {'file': SimpleUploadedFile('trees.csv', CSV.encode())},
                             HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(r.status_code, 202, r.content)
        self.ds_id = self.api.get(f'/dataset-jobs/{r.json()["id"]}').json()['dataset']

    def test_features_without_private_fields(self):
        """
        GIVEN an uploaded dataset with a private INSP_EMAIL column
        WHEN a client reads its features and the list of datasets
        THEN no feature carries INSP_EMAIL and the dataset is listed
        """
        body = self.api.get(f'/datasets/{self.ds_id}/features').content.decode()
        self.assertIn('Lime', body)
        self.assertNotIn('INSP_EMAIL', body)
        names = [d['name'] for d in self.api.get('/datasets').json()['items']]
        self.assertIn('trees', names)

    def test_collected_answers_stay_aggregated(self):
        """
        GIVEN a point question answered by 4 respondents in one place
        WHEN a client reads the answers dataset's features, then creates a view and reads its features
        THEN the first is refused with 409 and the view holds only cells with counts
        """
        q = Question.objects.create(survey_section=self.section, code='WHERE', name='Where?', input_type='point')
        for i in range(4):
            s = SurveySession.objects.create(survey=self.survey)
            Answer.objects.create(survey_session=s, question=q, point=Point(30.0 + i * 1e-6, 59.0))
        sync(self.org)
        ds = Dataset.objects.get(kind='answers', survey=self.survey)
        self.assertEqual(self.api.get(f'/datasets/{ds.pk}/features').status_code, 409)
        view = self.api.post(f'/datasets/{ds.pk}/views', {'name': 'Where, counted'})
        self.assertEqual(view.status_code, 201, view.content)
        gj = json.loads(self.api.get(f'/datasets/{ds.pk}/views/{view.json()["id"]}/features').content)
        self.assertEqual([f['properties'] for f in gj['features']], [{'respondents': 4}])

    def test_licence_outside_the_list(self):
        """
        GIVEN an uploaded dataset
        WHEN a client patches its licence to gpl-3.0
        THEN the call is refused with 422 naming the field
        """
        r = self.api.patch(f'/datasets/{self.ds_id}', {'licence': 'gpl-3.0'})
        self.assertEqual(r.status_code, 422)
        self.assertIn('licence', r.content.decode())

    def test_version_over_rest(self):
        """
        GIVEN an uploaded dataset keyed on TREE_ID
        WHEN a client uploads a new version and applies it with a note
        THEN the dataset lists version 2 with the note
        """
        v2 = CSV.replace('Lime,12', 'Lime,13')
        r = self.client.post(f'/api/v1/datasets/{self.ds_id}/versions',
                             {'file': SimpleUploadedFile('trees-2027.csv', v2.encode())},
                             HTTP_AUTHORIZATION=f'Bearer {self.token}')
        self.assertEqual(r.status_code, 202, r.content)
        job = self.api.get(f'/dataset-jobs/{r.json()["id"]}').json()
        self.assertEqual((job['status'], job['report']['changed']), ('preview', 1))
        self.api.post(f'/dataset-jobs/{job["id"]}/apply', {'note': 'Spring 2027'})
        versions = self.api.get(f'/datasets/{self.ds_id}').json()['versions']
        self.assertEqual((versions[0]['number'], versions[0]['note']), (2, 'Spring 2027'))
        self.assertTrue(DatasetVersion.objects.filter(dataset_id=self.ds_id, number=2).exists())


class AnalysisViewsApiTest(_ApiFixture):
    """Requirement: Analysis views are created and read through REST and MCP."""

    CHOICES_A = [{'code': 1, 'name': 'Car'}, {'code': 2, 'name': 'Bike'}]
    CHOICES_B = [{'code': 1, 'name': 'Under 30'}, {'code': 2, 'name': 'Over 60'}]

    def setUp(self):
        super().setUp()
        self.api = V1Client(self.client, self.token)
        a = Question.objects.create(survey_section=self.section, code='TRANSPORT', name='Transport',
                                    input_type='choice', choices=self.CHOICES_A)
        b = Question.objects.create(survey_section=self.section, code='AGE', name='Age',
                                    input_type='choice', choices=self.CHOICES_B)
        for n, x, y in ((4, 1, 1), (2, 2, 2)):
            for _i in range(n):
                s = SurveySession.objects.create(survey=self.survey)
                Answer.objects.create(survey_session=s, question=a, selected_choices=[x])
                Answer.objects.create(survey_session=s, question=b, selected_choices=[y])
        sync(self.org)
        self.responses = Dataset.objects.get(kind='responses', survey=self.survey)

    def _uploaded(self):
        r = self.client.post('/api/v1/datasets', {'file': SimpleUploadedFile('trees.csv', CSV.encode())},
                             HTTP_AUTHORIZATION=f'Bearer {self.token}')
        return self.api.get(f'/dataset-jobs/{r.json()["id"]}').json()['dataset']

    def test_creating_a_crosstab_over_rest(self):
        """
        GIVEN two choice questions answered by 4 + 2 respondents
        WHEN a client posts a crosstab view naming them and reads its data
        THEN the view is created and the table holds 4 and a masked cell
        """
        view = self.api.post(f'/datasets/{self.responses.pk}/views',
                             {'name': 'Travel by age', 'kind': 'crosstab',
                              'config': {'rows': 'TRANSPORT', 'columns': 'AGE'}})
        self.assertEqual(view.status_code, 201, view.content)
        self.assertEqual(view.json()['config'], {'rows': 'TRANSPORT', 'columns': 'AGE'})
        data = self.api.get(f'/datasets/{self.responses.pk}/views/{view.json()["id"]}/data').json()
        self.assertEqual(data['cells'][0][0]['value'], 4)
        self.assertEqual(data['cells'][1][1], {'value': None, 'display': '<3', 'masked': True})

    def test_a_kind_the_dataset_does_not_allow(self):
        """
        GIVEN a layer dataset
        WHEN a client posts kind engagement on it
        THEN the call is refused with 422 naming kind
        """
        refused = self.api.post(f'/datasets/{self._uploaded()}/views', {'name': 'Funnel', 'kind': 'engagement'})
        self.assertEqual(refused.status_code, 422, refused.content)
        self.assertIn('kind', json.dumps(refused.json()))

    def test_an_agent_reads_engagement(self):
        """
        GIVEN an MCP session of the workspace owner
        WHEN the agent creates an engagement view and calls get_dataset_view_data
        THEN the result holds the opened, answered and finished steps
        """
        mcp = McpClient(self.client, self.token)
        mcp.initialize()
        view = data_of(mcp.call('create_dataset_view', {'dataset_id': self.responses.pk, 'name': 'Funnel',
                                                        'kind': 'engagement'}))
        data = data_of(mcp.call('get_dataset_view_data', {'dataset_id': self.responses.pk, 'view_id': view['id']}))
        self.assertEqual([s['key'] for s in data['steps']], ['opened', 'answered', 'finished'])
        self.assertEqual(data['steps'][1]['value'], 6)

    def test_data_of_an_objects_view(self):
        """
        GIVEN an objects view of an uploaded layer
        WHEN a client reads its data
        THEN the call is refused with 409 naming the features endpoint
        """
        ds_id = self._uploaded()
        view = self.api.post(f'/datasets/{ds_id}/views', {'name': 'All trees'}).json()
        refused = self.api.get(f'/datasets/{ds_id}/views/{view["id"]}/data')
        self.assertEqual(refused.status_code, 409)
        self.assertIn('features', json.dumps(refused.json()))
