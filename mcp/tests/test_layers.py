"""`mcp-server` (change api-v2-layers, #411 PR 2): layer tools over the layer
service -- same rules as the editor and REST, confirm on deletes."""
from django.contrib.gis.geos import Point
from django.test import TestCase

from survey.models import Answer, LayerObject, Question, SurveyMapLayer, SurveySession

from api import scopes
from .helpers import LOCMEM, MCP_SETTINGS, McpClient, data_of, error_of, make_pro_org, make_v1_survey, mint

STOPS = {'type': 'FeatureCollection', 'features': [
    {'type': 'Feature', 'properties': {'name': f'Stop {i}'},
     'geometry': {'type': 'Point', 'coordinates': [13.4 + i / 100, 52.5]}} for i in range(3)]}


@LOCMEM
@MCP_SETTINGS
class LayerToolsTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner)
        self.mcp = McpClient(self.client, mint(self.owner)[0])
        self.mcp.initialize()
        self.ref = {'survey': str(self.survey.uuid)}

    def _create(self):
        return data_of(self.mcp.call('create_layer', {**self.ref, 'name': 'Stops', 'geojson': STOPS}))

    def test_map_context_from_a_chat(self):
        """
        GIVEN a FeatureCollection of three bus stops
        WHEN create_layer is called
        THEN the survey has a layer with three objects titled from "name", listed by list_layers
        """
        layer = self._create()
        self.assertEqual(layer['feature_count'], 3)
        self.assertEqual(layer['import']['created'], 3)
        self.assertEqual([l['id'] for l in data_of(self.mcp.call('list_layers', self.ref))['items']], [layer['id']])
        objects = data_of(self.mcp.call('list_layer_objects', {**self.ref, 'layer_id': layer['id']}))['items']
        self.assertEqual({o['title'] for o in objects}, {'Stop 0', 'Stop 1', 'Stop 2'})

    def test_delete_needs_confirmation(self):
        """
        GIVEN a layer
        WHEN delete_layer is called without confirm, then with it
        THEN the first is confirmation_required and the layer remains; the second deletes it
        """
        layer_id = self._create()['id']
        error = error_of(self.mcp.call('delete_layer', {**self.ref, 'layer_id': layer_id}))
        self.assertEqual(error['error'], 'confirmation_required')
        self.assertTrue(SurveyMapLayer.objects.filter(pk=layer_id).exists())
        data_of(self.mcp.call('delete_layer', {**self.ref, 'layer_id': layer_id, 'confirm': True}))
        self.assertFalse(SurveyMapLayer.objects.filter(pk=layer_id).exists())

    def test_objects_and_the_link_rule(self):
        """
        GIVEN a layer
        WHEN an object is added with a javascript: link, then with an https link, then updated and deleted
        THEN the first is a validation error on link, the second is stored, the update applies, and the
             delete needs confirm
        """
        layer_id = self._create()['id']
        point = {'type': 'Point', 'coordinates': [13.6, 52.5]}
        bad = error_of(self.mcp.call('create_layer_object', {**self.ref, 'layer_id': layer_id, 'key': 'x',
                                                              'geometry': point, 'link': 'javascript:alert(1)'}))
        self.assertEqual(bad['error'], 'validation')
        self.assertIn('link', bad['fields'])
        made = data_of(self.mcp.call('create_layer_object', {**self.ref, 'layer_id': layer_id, 'key': 'x',
                                                              'geometry': point, 'link': 'https://ok.example'}))
        self.assertEqual(made['link'], 'https://ok.example')
        updated = data_of(self.mcp.call('update_layer_object', {**self.ref, 'layer_id': layer_id, 'key': 'x',
                                                                 'title': 'New stop'}))
        self.assertEqual(updated['title'], 'New stop')
        self.assertEqual(error_of(self.mcp.call('delete_layer_object', {**self.ref, 'layer_id': layer_id,
                                                                         'key': 'x'}))['error'],
                         'confirmation_required')
        data_of(self.mcp.call('delete_layer_object', {**self.ref, 'layer_id': layer_id, 'key': 'x',
                                                      'confirm': True}))
        self.assertFalse(LayerObject.objects.filter(layer_id=layer_id, key='x').exists())

    def test_style_and_order(self):
        """
        GIVEN two layers
        WHEN one is given a colour and the order is reversed
        THEN the colour is stored and list_layers follows the new order
        """
        first = self._create()['id']
        second = data_of(self.mcp.call('create_layer', {**self.ref, 'name': 'Empty'}))['id']
        styled = data_of(self.mcp.call('update_layer', {**self.ref, 'layer_id': first, 'color': '#123456'}))
        self.assertEqual(styled['color'], '#123456')
        data_of(self.mcp.call('reorder_layers', {**self.ref, 'layer_ids': [second, first]}))
        self.assertEqual([l['id'] for l in data_of(self.mcp.call('list_layers', self.ref))['items']], [second, first])

    def test_read_only_token_and_shared_map_moderation(self):
        """
        GIVEN a read-only token, and a shared map with one mark
        WHEN tools are listed for the token and the owner hides the mark
        THEN write tools are absent for the token and the mark becomes hidden
        """
        read_only, _ = mint(self.owner, scopes_=(scopes.SURVEYS_READ,))
        names = self.mcp.tools(token=read_only, session='')
        self.assertIn('list_layers', names)
        self.assertNotIn('create_layer', names)
        point_q = Question.objects.create(survey_section=self.section, name='Where?', input_type='point',
                                          order_number=1, code='BENCH')
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=session, question=point_q, point=Point(13.4, 52.5))
        q = data_of(self.mcp.call('add_question', {**self.ref, 'section_id': self.section.pk, 'name': 'Rate',
                                                   'input_type': 'layer_objects', 'layer_from_answers': 'BENCH'}))
        key = LayerObject.objects.filter(layer_id=q['layer_id']).first().key
        moderated = data_of(self.mcp.call('moderate_layer_object', {**self.ref, 'layer_id': q['layer_id'],
                                                                     'key': key, 'status': 'hidden'}))
        self.assertEqual(moderated['status'], 'hidden')
