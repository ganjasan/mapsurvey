"""Spec: data-views (change data-views, #672, epic #676).

A view is a saved filter, field set and colour over a dataset; it is picked like a dataset by
surveys and Site map blocks; a view of aggregated data stays a grid of counts.
"""
import json

from django.contrib.gis.geos import Point
from django.test import TestCase
from django.urls import reverse

from api.tests.helpers import make_pro_org, make_v1_survey
from data.datasets import sync
from data.models import Dataset, DatasetView
from survey.layers import rebuild_layer
from survey.models import Answer, LayerObject, Question, Site, SurveyMapLayer, SurveySession


class _ViewFixture(TestCase):
    """A public workspace dataset of three trees (two poor, one good) with a private INSP_EMAIL."""

    def setUp(self):
        self.org, self.owner = make_pro_org('ViewOrg', 'viewowner')
        self.survey, self.section = make_v1_survey(self.org, self.owner, name='Trees survey', status='published')
        self.layer = SurveyMapLayer.objects.create(survey=None, organization=self.org, name='Street trees', geojson='')
        for i, (cond, height) in enumerate([('poor', 12), ('good', 9), ('poor', 4)]):
            LayerObject.objects.create(layer=self.layer, key=f't{i}', title=f'Tree {i}', position=i,
                                       geometry=Point(-0.12 + i / 1000, 51.5),
                                       properties={'CONDITION': cond, 'HEIGHT': height, 'SPECIES': 'Lime',
                                                   'INSP_EMAIL': f'i{i}@council.example'})
        sync(self.org)
        self.dataset = Dataset.objects.get(layer=self.layer)
        self.dataset.privacy_class = 'public'
        self.dataset.fields = [
            {'name': 'CONDITION', 'label': 'Condition', 'type': 'text', 'private': False},
            {'name': 'HEIGHT', 'label': 'Height', 'type': 'number', 'private': False},
            {'name': 'SPECIES', 'label': 'Species', 'type': 'text', 'private': False},
            {'name': 'INSP_EMAIL', 'label': 'INSP_EMAIL', 'type': 'text', 'private': True}]
        self.dataset.save()
        rebuild_layer(self.layer)
        self.client.force_login(self.owner)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.page = reverse('editor_data_dataset', args=[self.dataset.pk])

    def create_view(self, **extra):
        data = {'action': 'view_create', 'name': 'Poor condition', 'color': '#aa0000',
                'field_0': 'CONDITION', 'op_0': 'eq', 'value_0': 'poor', 'fields': ['CONDITION', 'HEIGHT']}
        data.update(extra)
        return self.client.post(self.page, data)


class ViewTest(_ViewFixture):
    """Requirement: A view is a saved filter, field set and colour over a dataset."""

    def test_creating_a_view(self):
        """
        GIVEN a tree dataset
        WHEN the owner creates "Poor condition" with CONDITION is "poor"
        THEN the dataset page lists the view
        """
        self.create_view()
        view = DatasetView.objects.get(dataset=self.dataset)
        self.assertEqual((view.kind, view.conditions[0]['value']), ('objects', 'poor'))
        self.assertIn('Poor condition', self.client.get(self.page).content.decode())

    def test_condition_on_a_private_field(self):
        """
        GIVEN INSP_EMAIL is private
        WHEN a view is posted with a condition on it
        THEN the view is refused
        """
        self.create_view(field_0='INSP_EMAIL', value_0='i0@council.example')
        self.assertFalse(DatasetView.objects.exists())

    def test_view_in_use_cannot_be_deleted(self):
        """
        GIVEN a survey shows the view
        WHEN the owner deletes the view
        THEN the view stays
        """
        self.create_view()
        view = DatasetView.objects.get()
        self.client.post(reverse('editor_survey_layer_link', args=[self.survey.uuid]),
                         {'dataset': f'{self.dataset.pk}:{view.pk}'})
        self.client.post(self.page, {'action': 'view_delete', 'view': view.pk})
        self.assertTrue(DatasetView.objects.filter(pk=view.pk).exists())


class PickTest(_ViewFixture):
    """Requirement: A view is picked like a dataset."""

    def test_survey_map_shows_the_view(self):
        """
        GIVEN the survey links the view "Poor condition" keeping CONDITION and HEIGHT
        WHEN a respondent's map fetches the layer
        THEN only the two poor trees come back, without SPECIES or the private field, and a good tree's card is not found
        """
        self.create_view()
        view = DatasetView.objects.get()
        r = self.client.post(reverse('editor_survey_layer_link', args=[self.survey.uuid]),
                             {'dataset': f'{self.dataset.pk}:{view.pk}'})
        self.assertEqual(r.status_code, 201, r.content)
        self.client.logout()
        url = reverse('survey_layer_geojson', kwargs={'survey_slug': str(self.survey.uuid), 'layer_id': self.layer.pk})
        gj = json.loads(self.client.get(url).content)
        self.assertEqual(sorted(f['properties']['_key'] for f in gj['features']), ['t0', 't2'])
        props = gj['features'][0]['properties']
        self.assertIn('HEIGHT', props)
        self.assertNotIn('SPECIES', props)
        self.assertNotIn('INSP_EMAIL', props)
        card = reverse('survey_layer_object', kwargs={'survey_slug': str(self.survey.uuid),
                                                      'layer_id': self.layer.pk, 'key': 't1'})
        self.assertEqual(self.client.get(card).status_code, 404)
        from survey.layers import build_map_layers_metadata
        self.assertEqual(build_map_layers_metadata(self.survey)[0]['color'], '#aa0000')

    def test_site_map_block_shows_the_view(self):
        """
        GIVEN a Site map block showing the view
        WHEN its GeoJSON is fetched
        THEN only the matching trees come back
        """
        self.create_view()
        view = DatasetView.objects.get()
        site = Site.objects.create(organization=self.org, title='Park', slug='park-v', created_by=self.owner,
                                   is_published=True)
        self.client.post(reverse('editor_site_block_add', args=[site.uuid]),
                         {'kind': 'map', 'dataset': f'{self.dataset.pk}:{view.pk}'})
        block = site.blocks.get(kind='map')
        self.assertEqual(block.data['view'], view.pk)
        gj = json.loads(self.client.get(reverse('site_block_dataset', args=[site.slug, block.pk])).content)
        self.assertEqual(sorted(f['properties']['_key'] for f in gj['features']), ['t0', 't2'])


class AggregatedTest(TestCase):
    """Requirement: A view of aggregated data stays aggregated."""

    def setUp(self):
        self.org, self.owner = make_pro_org('AggViewOrg', 'aggowner')
        self.survey, section = make_v1_survey(self.org, self.owner, name='Where', status='published')
        q = Question.objects.create(survey_section=section, code='WHERE', name='Where?', input_type='point')
        for i in range(5):
            s = SurveySession.objects.create(survey=self.survey)
            Answer.objects.create(survey_session=s, question=q, point=Point(30.0 + i * 1e-6, 59.0))
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=q, point=Point(31.0, 60.0))
        sync(self.org)
        self.dataset = Dataset.objects.get(kind='answers', survey=self.survey)
        self.client.force_login(self.owner)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.client.post(reverse('editor_data_dataset', args=[self.dataset.pk]),
                         {'action': 'view_create', 'name': 'Where, as counts'})
        self.view = DatasetView.objects.get(dataset=self.dataset)

    def test_grid_in_a_site_block(self):
        """
        GIVEN a view of a point question's answers: 5 respondents in one place, 1 elsewhere, K = 3
        WHEN a Site map block shows it and its GeoJSON is fetched
        THEN there is one cell with 5 respondents and no point
        """
        self.assertEqual(self.view.kind, 'grid')
        site = Site.objects.create(organization=self.org, title='Results', slug='results-v', created_by=self.owner,
                                   is_published=True)
        self.client.post(reverse('editor_site_block_add', args=[site.uuid]),
                         {'kind': 'map', 'dataset': f'{self.dataset.pk}:{self.view.pk}'})
        block = site.blocks.get(kind='map')
        self.client.logout()
        gj = json.loads(self.client.get(reverse('site_block_dataset', args=[site.slug, block.pk])).content)
        self.assertEqual([f['properties']['respondents'] for f in gj['features']], [5])
        self.assertTrue(all(f['geometry']['type'] == 'Polygon' for f in gj['features']))

    def test_not_a_survey_layer(self):
        """
        GIVEN a grid view of answers
        WHEN the owner links it into a survey
        THEN the link is refused
        """
        other, _s = make_v1_survey(self.org, self.owner, name='Other', status='published')
        r = self.client.post(reverse('editor_survey_layer_link', args=[other.uuid]),
                             {'dataset': f'{self.dataset.pk}:{self.view.pk}'})
        self.assertEqual(r.status_code, 400)
