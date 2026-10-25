"""`rest-api-v1` + `reference-overlay-layers` (change api-v2-layers, #411):
layer and object writes over the API, the shared-map path, and the link rule
on every surface."""
import json

from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from survey.models import AuditLog, LayerObject, Question, SurveyMapLayer, SurveySession, Answer

from .helpers import LOCMEM, V1Client, make_member, make_pro_org, make_v1_survey, mint


def _points(n=3):
    return {'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'properties': {'name': f'Bench {i}', 'kind': 'wood' if i % 2 else 'metal'},
         'geometry': {'type': 'Point', 'coordinates': [13.4 + i / 100, 52.5]}} for i in range(n)]}


@LOCMEM
class LayersApiTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        self.survey, self.section = make_v1_survey(self.org, self.owner)
        self.api = V1Client(self.client, mint(self.owner)[0])
        self.base = f'/surveys/{self.survey.uuid}'

    def _create(self, **body):
        response = self.api.post(f'{self.base}/layers', {'name': 'Benches', 'geojson': _points(), **body})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    # ── layers ──

    def test_layer_from_inline_geojson_and_list_still_reads(self):
        """
        GIVEN an owner and a FeatureCollection of three named points
        WHEN it is posted as a layer
        THEN 201 with three objects titled from "name", the list route still answers, and it is audited
        """
        data = self._create()
        self.assertEqual(data['feature_count'], 3)
        self.assertFalse(data['live'])
        titles = set(LayerObject.objects.filter(layer_id=data['id']).values_list('title', flat=True))
        self.assertEqual(titles, {'Bench 0', 'Bench 1', 'Bench 2'})
        listed = self.api.get(f'{self.base}/layers')
        self.assertEqual(listed.status_code, 200, listed.content)
        self.assertEqual([l['id'] for l in listed.json()], [data['id']])
        self.assertTrue(AuditLog.objects.filter(action='layer_create').exists())

    def test_upload_and_empty_layer(self):
        """
        GIVEN a GeoJSON file and then no GeoJSON at all
        WHEN they are posted
        THEN the file becomes a layer named after it and the empty post an empty layer
        """
        f = SimpleUploadedFile('stops.geojson', json.dumps(_points(2)).encode(), content_type='application/geo+json')
        up = self.client.post(f'/api/v1{self.base}/layers/upload', {'file': f},
                              HTTP_AUTHORIZATION=f'Bearer {self.api.token}')
        self.assertEqual(up.status_code, 201, up.content)
        self.assertEqual(up.json()['name'], 'stops')
        empty = self.api.post(f'{self.base}/layers', {'name': 'Draft layer'})
        self.assertEqual(empty.status_code, 201)
        self.assertEqual(empty.json()['feature_count'], 0)

    def test_projected_coordinates_are_refused(self):
        """
        GIVEN coordinates in metres
        WHEN posted
        THEN 422 saying WGS84 and no layer exists
        """
        gj = {'type': 'Feature', 'properties': {}, 'geometry': {'type': 'Point', 'coordinates': [392000, 5820000]}}
        response = self.api.post(f'{self.base}/layers', {'name': 'x', 'geojson': gj})
        self.assertEqual(response.status_code, 422)
        self.assertIn('WGS84', response.json()['detail'])
        self.assertFalse(SurveyMapLayer.objects.exists())

    def test_editor_is_not_enough_and_eleventh_layer(self):
        """
        GIVEN an editor, and an owner whose survey holds 10 layers
        WHEN each posts a layer
        THEN the editor gets 403 forbidden_role and the owner 409 limit_reached
        """
        editor = make_member(self.org, 'layer_editor', role='editor')
        from survey.models import SurveyCollaborator
        SurveyCollaborator.objects.create(user=editor, survey=self.survey, role='editor')
        response = self.api.post(f'{self.base}/layers', {'name': 'x'}, token=mint(editor)[0])
        self.assertEqual(response.status_code, 403)
        for i in range(10):
            SurveyMapLayer.objects.create(survey=self.survey, name=f'L{i}', geojson='', position=i)
        response = self.api.post(f'{self.base}/layers', {'name': 'x'})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error'], 'limit_reached')

    def test_patch_style_without_loading_geometry(self):
        """
        GIVEN a layer
        WHEN it is renamed and given a category style, under query capture
        THEN the style is normalised, the legend lists the classes, and no query selects geojson_gz
        """
        layer_id = self._create()['id']
        style = {'by': {'field': 'kind', 'mode': 'categories',
                        'classes': [{'value': 'wood', 'color': '#00aa00'}, {'value': 'metal', 'color': '#aaaaaa'}]}}
        with CaptureQueriesContext(connection) as ctx:
            response = self.api.patch(f'{self.base}/layers/{layer_id}', {'name': 'Seats', 'style': style})
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data['name'], 'Seats')
        self.assertEqual(data['style']['by']['field'], 'kind')
        self.assertTrue(data['legend'])
        self.assertFalse(any('geojson_gz' in q['sql'] and 'SELECT' in q['sql'].upper().split('FROM')[0]
                             for q in ctx.captured_queries))

    def test_unknown_label_field_and_bad_color(self):
        """
        GIVEN a layer
        WHEN label_field names a property it does not have, and color is not #rrggbb
        THEN both are 422 naming the field
        """
        layer_id = self._create()['id']
        r1 = self.api.patch(f'{self.base}/layers/{layer_id}', {'label_field': 'nope'})
        self.assertEqual((r1.status_code, list(r1.json()['fields'])), (422, ['label_field']))
        r2 = self.api.patch(f'{self.base}/layers/{layer_id}', {'color': 'red'})
        self.assertEqual((r2.status_code, list(r2.json()['fields'])), (422, ['color']))

    def test_layer_in_use_and_order(self):
        """
        GIVEN a layer bound to "Rate these benches" and a second layer
        WHEN the first is deleted and the order is reversed
        THEN the delete is 409 naming the question, and the order applies
        """
        first = self._create()['id']
        second = self._create(name='Stops')['id']
        Question.objects.create(survey_section=self.section, name='Rate these benches', input_type='layer_objects',
                                order_number=1, code='RATE', layer_id=first)
        response = self.api.call('DELETE', f'{self.base}/layers/{first}')
        self.assertEqual(response.status_code, 409)
        self.assertIn('Rate these benches', response.json()['detail'])
        ordered = self.api.call('PUT', f'{self.base}/layers/order', {'layer_ids': [second, first]})
        self.assertEqual(ordered.status_code, 200, ordered.content)
        self.assertEqual([l['id'] for l in ordered.json()['items']], [second, first])
        bad = self.api.call('PUT', f'{self.base}/layers/order', {'layer_ids': [second]})
        self.assertEqual(bad.status_code, 422)

    # ── objects ──

    def test_object_crud(self):
        """
        GIVEN a layer
        WHEN an object is created, read, patched and deleted
        THEN each step answers and the layer's feature count follows
        """
        layer_id = self._create()['id']
        url = f'{self.base}/layers/{layer_id}/objects'
        created = self.api.post(url, {'key': 'new', 'title': 'New bench', 'link': 'https://city.example/b',
                                      'geometry': {'type': 'Point', 'coordinates': [13.5, 52.5]}})
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(SurveyMapLayer.objects.get(pk=layer_id).feature_count, 4)
        patched = self.api.patch(f'{url}/new', {'title': 'Renamed', 'description': '<p>Shade <script>x</script></p>'})
        self.assertEqual(patched.json()['title'], 'Renamed')
        self.assertNotIn('<script', patched.json()['description'])
        self.assertEqual(self.api.get(f'{url}/new').json()['link'], 'https://city.example/b')
        listed = self.api.get(url, {'limit': 2}).json()
        self.assertEqual(len(listed['items']), 2)
        self.assertEqual(self.api.call('DELETE', f'{url}/new').status_code, 200)
        self.assertEqual(SurveyMapLayer.objects.get(pk=layer_id).feature_count, 3)

    def test_script_link_and_duplicate_key(self):
        """
        GIVEN a layer
        WHEN an object is created with a javascript: link, and another with an existing key
        THEN the first is 422 naming link, the second 409, and neither is stored
        """
        layer_id = self._create()['id']
        url = f'{self.base}/layers/{layer_id}/objects'
        point = {'type': 'Point', 'coordinates': [13.5, 52.5]}
        bad = self.api.post(url, {'key': 'x', 'link': 'javascript:alert(1)', 'geometry': point})
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(list(bad.json()['fields']), ['link'])
        self.assertFalse(LayerObject.objects.filter(layer_id=layer_id, key='x').exists())
        existing = LayerObject.objects.filter(layer_id=layer_id).first().key
        dup = self.api.post(url, {'key': existing, 'geometry': point})
        self.assertEqual(dup.status_code, 409)

    # ── shared map ──

    def test_shared_map_from_answers_and_moderation(self):
        """
        GIVEN a point question BENCH with one answer
        WHEN an Objects-on-the-map question is created with layer_from_answers BENCH, and the mark is hidden
        THEN the question is bound to a question-sourced layer, its objects are read-only, and the status applies
        """
        point_q = Question.objects.create(survey_section=self.section, name='Where?', input_type='point',
                                          order_number=1, code='BENCH')
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=session, question=point_q, point=Point(13.4, 52.5))
        created = self.api.post(f'{self.base}/sections/{self.section.pk}/questions',
                                {'name': 'Rate the marks', 'input_type': 'layer_objects',
                                 'layer_from_answers': 'BENCH'})
        self.assertEqual(created.status_code, 201, created.content)
        layer = SurveyMapLayer.objects.get(pk=created.json()['layer_id'])
        self.assertEqual((layer.source, layer.source_question_code), ('question', 'BENCH'))
        key = LayerObject.objects.filter(layer=layer).first().key
        url = f'{self.base}/layers/{layer.pk}/objects'
        self.assertEqual(self.api.patch(f'{url}/{key}', {'title': 'x'}).status_code, 409)
        status = self.api.patch(f'{url}/{key}/status', {'status': 'hidden'})
        self.assertEqual(status.status_code, 200, status.content)
        self.assertEqual(LayerObject.objects.get(layer=layer, key=key).status, 'hidden')


class LinkRuleTest(TestCase):
    """The link rule outside the API: the object editor, imports, the card."""

    def setUp(self):
        from survey.layers import layer_owner
        self.org, self.owner = make_pro_org()
        self.survey, _section = make_v1_survey(self.org, self.owner, status='published')
        self.layer = SurveyMapLayer.objects.create(survey=layer_owner(self.survey), name='L', geojson='', position=1)
        self.obj = LayerObject.objects.create(layer=self.layer, key='a', title='A', geometry=Point(13.4, 52.5),
                                              link='javascript:alert(1)', position=1)
        self.client.force_login(self.owner)

    def test_editor_refuses_a_script_link(self):
        """
        GIVEN the object editor
        WHEN the owner saves link javascript:alert(document.cookie)
        THEN 400 about the link and the stored link is unchanged
        """
        url = f'/editor/surveys/{self.survey.uuid}/layers/{self.layer.pk}/objects/a/'
        response = self.client.patch(url, json.dumps({'link': 'javascript:alert(document.cookie)'}),
                                     content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('http', response.json()['error'])
        self.obj.refresh_from_db()
        self.assertEqual(self.obj.link, 'javascript:alert(1)')

    def test_card_never_hands_out_a_bad_link(self):
        """
        GIVEN an object stored before the rule with a javascript: link
        WHEN the card payload is built
        THEN it carries no link
        """
        from survey.layer_assets import object_card_payload
        self.assertEqual(object_card_payload(self.obj)['link'], '')

    def test_imports_drop_and_count_bad_links(self):
        """
        GIVEN a GeoJSON import mapping a link property with one data: link and one https link
        WHEN the features are imported
        THEN the https link is kept, the bad one dropped and counted
        """
        from survey.layers import objects_from_features
        features = [
            {'type': 'Feature', 'properties': {'url': 'data:text/html,<script>'},
             'geometry': {'type': 'Point', 'coordinates': [13.4, 52.5]}},
            {'type': 'Feature', 'properties': {'url': 'https://ok.example'},
             'geometry': {'type': 'Point', 'coordinates': [13.5, 52.5]}},
        ]
        report = objects_from_features(self.layer, features, mapping={'link': 'url'})
        self.assertEqual(report['invalid_links'], 1)
        links = set(LayerObject.objects.filter(layer=self.layer).exclude(key='a').values_list('link', flat=True))
        self.assertEqual(links, {'', 'https://ok.example'})

    def test_csv_import_drops_a_bad_link(self):
        """
        GIVEN a CSV row with link data:text/html,<script>
        WHEN it is imported in the object editor
        THEN the object is created without a link and the report counts one invalid link
        """
        csv = 'title,lat,lng,link\nStop,52.5,13.4,"data:text/html,<script>"\n'
        url = f'/editor/surveys/{self.survey.uuid}/layers/{self.layer.pk}/import/csv/'
        response = self.client.post(url, {'file': SimpleUploadedFile('o.csv', csv.encode(), content_type='text/csv')})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json().get('invalid_links'), 1)
        self.assertEqual(LayerObject.objects.get(layer=self.layer, title='Stop').link, '')
