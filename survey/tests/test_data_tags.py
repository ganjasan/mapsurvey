"""Spec: data-tags (change data-tags, #673, epic #676).

Datasets and surveys carry free workspace tags; the Data catalogue and the survey dashboard filter by
them; tags ride the REST API and MCP.
"""
from django.test import TestCase
from django.urls import reverse

from api.tests.helpers import V1Client, make_pro_org, make_v1_survey, mint
from data.datasets import sync
from data.models import Dataset, Tag
from data.tags import set_tags
from mcp.tests.helpers import McpClient, data_of
from survey.models import SurveyMapLayer


class _TagFixture(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org('TagOrg', 'tagowner')
        self.survey, _s = make_v1_survey(self.org, self.owner, name='Riverside survey', status='published')
        self.other, _s2 = make_v1_survey(self.org, self.owner, name='Other survey', status='published')
        SurveyMapLayer.objects.create(survey=None, organization=self.org, name='Trees', geojson='')
        SurveyMapLayer.objects.create(survey=None, organization=self.org, name='Benches', geojson='')
        sync(self.org)
        self.trees = Dataset.objects.get(name='Trees')
        self.benches = Dataset.objects.get(name='Benches')
        self.client.force_login(self.owner)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()


class TaggingTest(_TagFixture):
    """Requirement: Datasets and surveys carry workspace tags."""

    def test_dataset_and_survey_share_one_tag(self):
        """
        GIVEN a dataset and a survey of one workspace
        WHEN the dataset is tagged "Riverside plan 2027" on its page and the survey "riverside plan 2027" on its panel
        THEN the workspace has one tag carried by both
        """
        self.client.post(reverse('editor_data_dataset', args=[self.trees.pk]),
                         {'action': 'details', 'name': 'Trees', 'tags': 'Riverside plan 2027'})
        r = self.client.post(reverse('editor_survey_tags', args=[self.survey.uuid]), {'tags': 'riverside plan 2027'})
        self.assertEqual(r.json()['tags'], ['Riverside plan 2027'])
        tag = Tag.objects.get(organization=self.org)
        self.assertEqual(list(tag.datasets.all()), [self.trees])
        self.assertEqual(list(tag.surveys.all()), [self.survey])

    def test_a_tag_nothing_carries_is_gone(self):
        """
        GIVEN a tag carried by one dataset only
        WHEN the dataset drops it
        THEN the tag is gone
        """
        set_tags(self.org, self.trees, ['Parks'])
        set_tags(self.org, self.trees, [])
        self.assertFalse(Tag.objects.exists())


class FilterTest(_TagFixture):
    """Requirement: Lists filter by tag."""

    def setUp(self):
        super().setUp()
        set_tags(self.org, self.trees, ['Riverside plan 2027'])
        set_tags(self.org, self.survey, ['Riverside plan 2027'])

    def test_catalogue_filter(self):
        """
        GIVEN Trees carries the tag and Benches does not
        WHEN the catalogue is filtered by it
        THEN only Trees is listed, with its tag shown
        """
        html = self.client.get(reverse('editor_data') + '?tag=riverside-plan-2027').content.decode()
        self.assertIn('<strong>Trees</strong>', html)
        self.assertNotIn('<strong>Benches</strong>', html)
        self.assertIn('data-row-tag="riverside-plan-2027"', html)

    def test_dashboard_filter(self):
        """
        GIVEN one survey carries the tag
        WHEN the dashboard is filtered by it
        THEN only that survey is listed
        """
        html = self.client.get(reverse('editor') + '?tag=riverside-plan-2027').content.decode()
        self.assertIn('Riverside survey', html)
        self.assertNotIn('Other survey', html)
        self.assertIn('data-card-tag="riverside-plan-2027"', html)


class ApiTest(_TagFixture):
    """Requirement: Tags ride the API and MCP."""

    def test_rest_api(self):
        """
        GIVEN an API token of the owner
        WHEN the client puts ["Riverside plan 2027"] on a survey
        THEN the survey lists the tag and the list filtered by it returns only that survey
        """
        api = V1Client(self.client, mint(self.owner)[0])
        r = api.put(f'/surveys/{self.survey.uuid}/tags', {'tags': ['Riverside plan 2027']})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['tags'], ['Riverside plan 2027'])
        items = api.get('/surveys', {'tag': 'Riverside plan 2027'}).json()['items']
        self.assertEqual([i['name'] for i in items], ['Riverside survey'])

    def test_mcp(self):
        """
        GIVEN an MCP session of the owner
        WHEN set_survey_tags puts ["Parks"] on a survey
        THEN list_surveys with tag "parks" returns it
        """
        mcp = McpClient(self.client, mint(self.owner)[0])
        mcp.initialize()
        data = data_of(mcp.call('set_survey_tags', {'survey': str(self.other.uuid), 'tags': ['Parks']}))
        self.assertEqual(data['tags'], ['Parks'])
        listed = data_of(mcp.call('list_surveys', {'tag': 'parks'}))
        self.assertEqual([i['name'] for i in listed['items']], ['Other survey'])
