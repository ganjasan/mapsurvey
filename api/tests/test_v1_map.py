"""`rest-api-v1` + `map-layer-placement` + `survey-study-area` (change map-layers-study-area): where
layers show and the study area over the API, through the same services as the editor."""
from django.test import TestCase

from survey.layers import section_layer_ids
from survey.models import LayerPlacement, StudyArea, SurveyHeader

from .helpers import LOCMEM, V1Client, make_pro_org, make_v1_survey, mint

SQUARE = {'type': 'Polygon', 'coordinates': [[
    [13.39, 52.49], [13.41, 52.49], [13.41, 52.51], [13.39, 52.51], [13.39, 52.49]]]}


@LOCMEM
class MapApiTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner)
        self.api = V1Client(self.client, mint(self.owner)[0])
        self.base = f'/surveys/{self.survey.uuid}'

    def _layer(self):
        body = {'name': 'Benches', 'geojson': {'type': 'Feature', 'properties': {},
                                                'geometry': {'type': 'Point', 'coordinates': [13.4, 52.5]}}}
        response = self.api.post(f'{self.base}/layers', body)
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['id']

    def test_place_through_the_api(self):
        """
        GIVEN a Pro token with write scope and a layer of the survey
        WHEN it PUTs a placement for the section only, lists placements, then DELETEs it
        THEN the section map shows the layer, the list names the scope, and then the layer is on no map
        """
        layer_id = self._layer()
        code = self.section.code
        response = self.api.call('PUT', f'{self.base}/layers/{layer_id}/placement',
                                 {'scope': 'sections', 'sections': [code]})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(section_layer_ids(self.section), [layer_id])
        listed = self.api.get(f'{self.base}/placements').json()['items']
        self.assertEqual([(p['layer_id'], p['scope'], p['sections']) for p in listed], [(layer_id, 'sections', [code])])
        self.assertEqual(self.api.call('DELETE', f'{self.base}/layers/{layer_id}/placement').json(), {'removed': True})
        self.assertEqual(section_layer_ids(self.section), [])

    def test_place_a_layer_that_is_not_linked(self):
        """
        GIVEN a layer id the survey does not use
        WHEN a client places it
        THEN 422 naming the layer
        """
        from survey.models import SurveyMapLayer
        loose = SurveyMapLayer.objects.create(survey=None, organization=self.org, name='Loose', geojson='')
        response = self.api.call('PUT', f'{self.base}/layers/{loose.pk}/placement', {'scope': 'all'})
        self.assertEqual(response.status_code, 422)
        self.assertIn(str(loose.pk), response.json()['detail'])
        self.assertFalse(LayerPlacement.objects.filter(layer=loose).exists())

    def test_unknown_field_is_refused(self):
        """
        GIVEN a placement body with a field the API does not know
        THEN 422 and nothing changes (strict schemas)
        """
        layer_id = self._layer()
        before = list(LayerPlacement.objects.values_list('scope', flat=True))
        response = self.api.call('PUT', f'{self.base}/layers/{layer_id}/placement', {'scope': 'all', 'visible': True})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(list(LayerPlacement.objects.values_list('scope', flat=True)), before)

    def test_study_area_round_trip(self):
        """
        GIVEN a published survey
        WHEN a client sets a study area with refusal and a message, patches the fog off, reads it and clears it
        THEN each step answers with the area's state, no unpublished changes appear, and it is gone at the end
        """
        self.survey.status = 'published'
        self.survey.save()
        response = self.api.call('PUT', f'{self.base}/study-area',
                                  {'geometry': SQUARE, 'source': 'draw', 'refuse_outside': True,
                                   'message': {'en': 'Inside only.'}})
        self.assertEqual(response.status_code, 200, response.content)
        area = response.json()['study_area']
        self.assertEqual((area['fog'], area['refuse_outside'], area['message']), (True, True, {'en': 'Inside only.'}))
        patched = self.api.call('PATCH', f'{self.base}/study-area', {'fog': False}).json()['study_area']
        self.assertFalse(patched['fog'])
        self.assertEqual(self.api.get(f'{self.base}/study-area').json()['study_area']['geometry']['type'], 'MultiPolygon')
        self.assertFalse(SurveyHeader.objects.filter(published_version=self.survey).exists())
        self.assertEqual(self.api.call('DELETE', f'{self.base}/study-area').json(), {'removed': True})
        self.assertFalse(StudyArea.objects.exists())

    def test_not_a_polygon(self):
        """
        GIVEN a LineString as the study area
        THEN 422 with the geometry field and nothing stored
        """
        response = self.api.call('PUT', f'{self.base}/study-area',
                                  {'geometry': {'type': 'LineString', 'coordinates': [[13.4, 52.5], [13.5, 52.6]]}})
        self.assertEqual(response.status_code, 422)
        self.assertIn('geometry', response.json().get('fields', {}))
        self.assertFalse(StudyArea.objects.exists())
