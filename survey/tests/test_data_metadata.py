"""Spec: data-metadata (change data-metadata, #669, epic #676).

Every dataset has a page with its details; a layer dataset has a field dictionary; a private field
never leaves the dataset's own editor; labels replace raw field names where people read them.
"""
import csv
import io
import json

from django.contrib.gis.geos import Point
from django.test import TestCase
from django.urls import reverse

from api.tests.helpers import V1Client, make_member, make_pro_org, make_v1_survey, mint
from data.datasets import sync
from data.models import Dataset
from mcp.tests.helpers import McpClient, data_of
from survey.layers import build_map_layers_metadata, rebuild_layer, style_summary
from survey.models import LayerObject, SurveyMapLayer


class _MetadataFixture(TestCase):
    """A published survey with a layer of two trees; `INSP_EMAIL` is private, `TR_HGT_M` is
    labelled "Tree height (m)"."""

    def setUp(self):
        self.org, self.owner = make_pro_org('MetaOrg', 'metaowner')
        self.survey, self.section = make_v1_survey(self.org, self.owner, name='Trees', status='published')
        self.layer = SurveyMapLayer.objects.create(survey=self.survey, name='Street trees', geojson='')
        for i, (species, height, email) in enumerate([('Lime', 12, 'a@council.example'),
                                                       ('Oak', 9, 'b@council.example')]):
            LayerObject.objects.create(layer=self.layer, key=f't{i}', title=species, position=i,
                                       geometry=Point(30.0 + i / 100, 59.0),
                                       properties={'species': species, 'TR_HGT_M': height, 'INSP_EMAIL': email})
        sync(self.org)
        self.dataset = Dataset.objects.get(layer=self.layer)
        self.dataset.fields = [
            {'name': 'species', 'label': 'Species', 'type': 'text', 'private': False},
            {'name': 'TR_HGT_M', 'label': 'Tree height (m)', 'type': 'number', 'private': False},
            {'name': 'INSP_EMAIL', 'label': 'INSP_EMAIL', 'type': 'text', 'private': True},
        ]
        self.dataset.save()
        rebuild_layer(self.layer)

    def login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def page_url(self):
        return reverse('editor_data_dataset', args=[self.dataset.pk])


class DetailsTest(_MetadataFixture):
    """Requirement: Every dataset has a page with its details."""

    def test_editor_sets_licence_and_theme(self):
        """
        GIVEN a workspace editor collaborating on the survey
        WHEN they save licence CC BY 4.0 and theme Environment on the layer's page
        THEN the dataset stores both and the page shows them
        """
        from survey.models import SurveyCollaborator
        editor = make_member(self.org, 'metaeditor', role='editor')
        SurveyCollaborator.objects.create(user=editor, survey=self.survey, role='editor')
        self.login(editor)
        response = self.client.post(self.page_url(), {
            'action': 'details', 'name': 'Street trees', 'description': 'Council trees',
            'theme': 'ENVI', 'maintainer': 'Parks team', 'update_frequency': 'monthly', 'licence': 'cc-by-4.0'})
        self.assertEqual(response.status_code, 302)
        self.dataset.refresh_from_db()
        self.assertEqual((self.dataset.licence, self.dataset.theme, self.dataset.maintainer),
                         ('cc-by-4.0', 'ENVI', 'Parks team'))
        html = self.client.get(self.page_url()).content.decode()
        self.assertIn('value="cc-by-4.0" selected', html)

    def test_licence_outside_the_list_is_refused(self):
        """
        GIVEN the owner on the dataset page
        WHEN the licence `gpl-3.0` is posted
        THEN nothing is saved and the form names the field
        """
        self.login(self.owner)
        response = self.client.post(self.page_url(), {'action': 'details', 'name': 'Renamed', 'licence': 'gpl-3.0'})
        self.assertEqual(response.status_code, 200)
        self.dataset.refresh_from_db()
        self.assertEqual((self.dataset.name, self.dataset.licence), ('Street trees', ''))
        self.assertIn('is-invalid', response.content.decode())

    def test_viewer_cannot_edit(self):
        """
        GIVEN a workspace viewer
        WHEN they post the details form
        THEN the request is refused and the dataset is unchanged
        """
        viewer = make_member(self.org, 'metaviewer', role='viewer')
        self.login(viewer)
        self.assertEqual(self.client.get(self.page_url()).status_code, 200)
        response = self.client.post(self.page_url(), {'action': 'details', 'name': 'Hijacked'})
        self.assertEqual(response.status_code, 403)
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.name, 'Street trees')

    def test_editor_without_the_survey_gets_404(self):
        """
        GIVEN a workspace editor who is no collaborator of the survey
        WHEN they open the survey layer's dataset page
        THEN the page is not found
        """
        self.login(make_member(self.org, 'stranger', role='editor'))
        self.assertEqual(self.client.get(self.page_url()).status_code, 404)


class DictionaryTest(_MetadataFixture):
    """Requirement: A layer dataset has an editable field dictionary."""

    def test_labelling_a_field(self):
        """
        GIVEN the dictionary of the layer
        WHEN the owner sets the label of `species` to "Tree species"
        THEN the dictionary stores the label and the field keeps its name
        """
        self.login(self.owner)
        html = self.client.get(self.page_url()).content.decode()
        self.assertIn('data-field="INSP_EMAIL"', html)   # the editor sees private fields
        post = {'action': 'fields'}
        for i, f in enumerate(self.dataset.fields):
            post.update({f'name_{i}': f['name'], f'label_{i}': f['label'], f'type_{i}': f['type']})
            if f['private']:
                post[f'private_{i}'] = '1'
        post['label_0'] = 'Tree species'
        self.client.post(self.page_url(), post)
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.fields[0]['name'], 'species')
        self.assertEqual(self.dataset.fields[0]['label'], 'Tree species')
        self.assertTrue(self.dataset.fields[2]['private'])

    def test_survey_layer_fields_appear_undocumented(self):
        """
        GIVEN a survey layer whose objects carry `colour` and nobody documented it
        WHEN the owner opens its page
        THEN the dictionary lists `colour` with the label `colour`
        """
        other = SurveyMapLayer.objects.create(survey=self.survey, name='Benches', geojson='')
        LayerObject.objects.create(layer=other, key='b1', geometry=Point(30, 59), properties={'colour': 'green'})
        rebuild_layer(other)
        sync(self.org)
        self.login(self.owner)
        ds = Dataset.objects.get(layer=other)
        html = self.client.get(reverse('editor_data_dataset', args=[ds.pk])).content.decode()
        self.assertIn('data-field="colour"', html)
        self.assertIn('value="colour"', html)


class PrivateFieldTest(_MetadataFixture):
    """Requirement: A private field never leaves the dataset's own editor."""

    def test_respondent_map(self):
        """
        GIVEN `INSP_EMAIL` is private
        WHEN a respondent's map fetches the layer
        THEN no feature carries it, while public fields are there
        """
        url = reverse('survey_layer_geojson', kwargs={'survey_slug': str(self.survey.uuid), 'layer_id': self.layer.pk})
        body = self.client.get(url).content.decode()
        self.assertNotIn('INSP_EMAIL', body)
        self.assertNotIn('council.example', body)
        self.assertIn('TR_HGT_M', body)

    def test_rest_api_and_mcp(self):
        """
        GIVEN `INSP_EMAIL` is private
        WHEN an API client lists the layer's objects over REST and over MCP
        THEN no object's properties carry it
        """
        token = mint(self.owner)[0]
        api = V1Client(self.client, token)
        r = api.get(f'/surveys/{self.survey.uuid}/layers/{self.layer.pk}/objects')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['items'])
        for item in r.json()['items']:
            self.assertNotIn('INSP_EMAIL', item['properties'])
            self.assertIn('species', item['properties'])
        mcp = McpClient(self.client, token)
        mcp.initialize()
        data = data_of(mcp.call('list_layer_objects', {'survey': str(self.survey.uuid), 'layer_id': self.layer.pk}))
        self.assertTrue(data['items'])
        self.assertFalse(any('INSP_EMAIL' in o['properties'] for o in data['items']))

    def test_survey_zip_export(self):
        """
        GIVEN `INSP_EMAIL` is private
        WHEN the survey's layers are serialised for the ZIP
        THEN neither the objects nor the derived GeoJSON carry it
        """
        from survey.serialization import serialize_layer_objects
        objects = serialize_layer_objects(self.layer, 0)
        self.assertFalse(any('INSP_EMAIL' in o['properties'] for o in objects))
        self.layer.refresh_from_db()
        self.assertNotIn('INSP_EMAIL', self.layer.geojson)

    def test_pickers_summaries_and_map_metadata(self):
        """
        GIVEN `INSP_EMAIL` is private and the layer's label field and style rule name it
        WHEN the editor lists property names, asks for its value summary, and a map reads the metadata
        THEN the field is not offered, the summary is empty and neither label nor rule reaches the map
        """
        self.layer.refresh_from_db()
        self.assertNotIn('INSP_EMAIL', self.layer.property_names)
        self.assertIn('species', self.layer.property_names)
        self.assertEqual(style_summary(self.layer, 'INSP_EMAIL')['kind'], 'empty')
        self.layer.label_field = 'INSP_EMAIL'
        self.layer.style = {'by': {'field': 'INSP_EMAIL', 'mode': 'categories',
                                   'classes': [{'value': 'a@council.example', 'label': 'a@council.example'}]}}
        self.layer.save(update_fields=['label_field', 'style'])
        meta = next(m for m in build_map_layers_metadata(self.survey) if m['id'] == self.layer.pk)
        self.assertEqual(meta['label_field'], '')
        self.assertNotIn('by', meta['style'])
        self.assertNotIn('council.example', json.dumps(meta))

    def test_budget_cost_property(self):
        """
        GIVEN a budget whose items come from the layer and whose cost property is private
        WHEN the items are built for a respondent
        THEN no item carries a cost read from that field
        """
        from survey.budget import _layer_items
        from survey.models import Question
        self.dataset.fields[1]['private'] = True   # TR_HGT_M as the "cost"
        self.dataset.save()
        q = Question.objects.create(survey_section=self.section, code='BUD', name='Budget',
                                    input_type='budget', layer=self.layer)
        self.assertTrue(all(item['cost'] is None for item in _layer_items(q, 'TR_HGT_M')))

    def test_api_write_keeps_the_private_value(self):
        """
        GIVEN an object with a private `INSP_EMAIL`
        WHEN an API client replaces its properties with {"species": "Elm"}
        THEN the object keeps its private value
        """
        token = mint(self.owner)[0]
        api = V1Client(self.client, token)
        r = api.patch(f'/surveys/{self.survey.uuid}/layers/{self.layer.pk}/objects/t0', {'properties': {'species': 'Elm'}})
        self.assertEqual(r.status_code, 200, r.content)
        obj = LayerObject.objects.get(layer=self.layer, key='t0')
        self.assertEqual(obj.properties['species'], 'Elm')
        self.assertEqual(obj.properties['INSP_EMAIL'], 'a@council.example')

    def test_making_a_field_private_takes_effect_at_once(self):
        """
        GIVEN `species` is public and served in the layer GeoJSON
        WHEN the owner marks it private on the dataset page
        THEN the next layer GeoJSON carries no `species`
        """
        self.layer.refresh_from_db()
        self.assertIn('species', self.layer.geojson)
        self.login(self.owner)
        post = {'action': 'fields'}
        for i, f in enumerate(self.dataset.fields):
            post.update({f'name_{i}': f['name'], f'label_{i}': f['label'], f'type_{i}': f['type'], f'private_{i}': '1'})
        self.client.post(self.page_url(), post)
        self.layer.refresh_from_db()
        self.assertNotIn('"species"', self.layer.geojson)
        self.assertNotIn('Lime', self.layer.geojson.split('"_title"')[0])


class LabelsTest(_MetadataFixture):
    """Requirement: Labels replace raw field names where people read them."""

    def test_object_card(self):
        """
        GIVEN the layer labels `TR_HGT_M` as "Tree height (m)"
        WHEN a respondent opens object t0's card
        THEN it reads "Tree height (m)" with its value, never the raw name, and no private field
        """
        url = reverse('survey_layer_object', kwargs={'survey_slug': str(self.survey.uuid),
                                                     'layer_id': self.layer.pk, 'key': 't0'})
        card = self.client.get(url).json()
        self.assertIn({'label': 'Tree height (m)', 'value': '12'}, card['fields'])
        text = json.dumps(card)
        self.assertNotIn('TR_HGT_M', text)
        self.assertNotIn('council.example', text)

    def test_download(self):
        """
        GIVEN a labelled dataset with a private column
        WHEN the owner downloads it as CSV and as GeoJSON
        THEN the header and the keys carry the labels and no private column
        """
        self.login(self.owner)
        url = reverse('editor_data_download', args=[self.dataset.pk])
        body = b''.join(self.client.get(url + '?format=csv').streaming_content).decode()
        header = next(csv.reader(io.StringIO(body)))
        self.assertIn('Tree height (m)', header)
        self.assertNotIn('TR_HGT_M', header)
        self.assertNotIn('council.example', body)
        geo = json.loads(b''.join(self.client.get(url + '?format=geojson').streaming_content))
        self.assertEqual(geo['features'][0]['properties']['Tree height (m)'], 12)
        self.assertNotIn('INSP_EMAIL', json.dumps(geo))
