"""`mcp-server` + `map-layer-placement` + `survey-study-area` (change map-layers-study-area): the
placement and study area tools, over the same services as the editor and REST."""
from django.test import TestCase

from survey.layers import section_layer_ids
from survey.models import StudyArea

from .helpers import LOCMEM, MCP_SETTINGS, McpClient, data_of, error_of, make_pro_org, make_v1_survey, mint

STOPS = {'type': 'FeatureCollection', 'features': [
    {'type': 'Feature', 'properties': {'name': 'Stop'}, 'geometry': {'type': 'Point', 'coordinates': [13.4, 52.5]}}]}
SQUARE = {'type': 'Polygon', 'coordinates': [[
    [13.39, 52.49], [13.41, 52.49], [13.41, 52.51], [13.39, 52.51], [13.39, 52.49]]]}


@LOCMEM
@MCP_SETTINGS
class MapToolsTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner)
        self.mcp = McpClient(self.client, mint(self.owner)[0])
        self.mcp.initialize()
        self.ref = {'survey': str(self.survey.uuid)}

    def test_place_and_unplace(self):
        """
        GIVEN a layer created through create_layer (placed on every section by default)
        WHEN place_layer narrows it to the section, then unplace_layer takes it off
        THEN list_placements follows each step and the section map shows it, then not
        """
        layer_id = data_of(self.mcp.call('create_layer', {**self.ref, 'name': 'Stops', 'geojson': STOPS}))['id']
        listed = data_of(self.mcp.call('list_placements', self.ref))['items']
        self.assertEqual([(p['layer_id'], p['scope']) for p in listed], [(layer_id, 'all')])
        placed = data_of(self.mcp.call('place_layer', {**self.ref, 'layer_id': layer_id, 'scope': 'sections',
                                                       'sections': [self.section.code]}))
        self.assertEqual(placed['sections'], [self.section.code])
        self.assertEqual(section_layer_ids(self.section), [layer_id])
        self.assertEqual(data_of(self.mcp.call('unplace_layer', {**self.ref, 'layer_id': layer_id})), {'removed': True})
        self.assertEqual(section_layer_ids(self.section), [])

    def test_study_area_tools(self):
        """
        GIVEN a survey without a study area
        WHEN set_study_area, update_study_area, get_study_area and clear_study_area run in turn
        THEN each answers with the state (fog on by default, then off), and nothing is left at the end
        """
        self.assertIsNone(data_of(self.mcp.call('get_study_area', self.ref))['study_area'])
        area = data_of(self.mcp.call('set_study_area', {**self.ref, 'geometry': SQUARE}))['study_area']
        self.assertTrue(area['fog'])
        area = data_of(self.mcp.call('update_study_area', {**self.ref, 'fog': False, 'refuse_outside': True}))['study_area']
        self.assertEqual((area['fog'], area['refuse_outside']), (False, True))
        self.assertEqual(data_of(self.mcp.call('get_study_area', self.ref))['study_area']['source'], 'draw')
        self.assertEqual(data_of(self.mcp.call('clear_study_area', self.ref)), {'removed': True})
        self.assertFalse(StudyArea.objects.exists())

    def test_line_is_refused(self):
        """
        GIVEN a LineString sent as the study area
        THEN the tool answers a validation error and nothing is stored
        """
        error = error_of(self.mcp.call('set_study_area', {**self.ref, 'geometry': {
            'type': 'LineString', 'coordinates': [[13.4, 52.5], [13.5, 52.6]]}}))
        self.assertEqual(error['error'], 'validation')
        self.assertFalse(StudyArea.objects.exists())

    def test_section_study_area_tools(self):
        """
        GIVEN a map section
        WHEN set_section_study_area gives it an own area with refusal, then get_section_study_area reads it,
             and own without a geometry is asked on a fresh survey's section
        THEN the section is on its own area with the rule on; the second call is a validation error
             (change section-study-area)
        """
        ref = {**self.ref, 'section_id': self.section.pk}
        data = data_of(self.mcp.call('set_section_study_area', {**ref, 'mode': 'own', 'geometry': SQUARE,
                                                                'refuse_outside': True}))
        self.assertEqual(data['mode'], 'own')
        read = data_of(self.mcp.call('get_section_study_area', ref))
        self.assertEqual((read['effective'], read['own_area']['refuse_outside']), ('own', True))
        data_of(self.mcp.call('set_section_study_area', {**ref, 'mode': 'survey'}))
        error = error_of(self.mcp.call('set_section_study_area', {**ref, 'mode': 'nowhere'}))
        self.assertEqual(error['error'], 'validation')
        sections = data_of(self.mcp.call('get_study_area', self.ref))['sections']
        self.assertEqual([s['mode'] for s in sections], ['survey'])
