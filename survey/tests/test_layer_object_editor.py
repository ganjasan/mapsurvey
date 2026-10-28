"""Tests for the `layer-object-editor` capability (openspec/specs/layer-object-editor/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch
import json
from survey.models import Organization, SurveyHeader, SurveySection, Membership
from survey.tests.helpers import _objects_layer, _zones_geojson


class LayerObjectEditorTest(TestCase):
    """The object editor page and its JSON endpoints (spec layer-object-editor)."""

    def setUp(self):
        self.org = Organization.objects.create(name="LOE Org")
        self.owner = User.objects.create_user(username='loeowner', password='pw12345678')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.viewer = User.objects.create_user(username='loeviewer', password='pw12345678')
        Membership.objects.create(user=self.viewer, organization=self.org, role='viewer')
        self.survey = SurveyHeader.objects.create(
            name="loe_survey", organization=self.org, redirect_url="/thanks/", created_by=self.owner,
        )
        SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True,
        )
        self.layer = _objects_layer(self.survey, name="Sites", key_field='zone_id', label_field='name')
        self.client.login(username='loeowner', password='pw12345678')

    def _u(self, name, **kw):
        kw.setdefault('survey_uuid', self.survey.uuid)
        kw.setdefault('layer_id', self.layer.pk)
        return reverse(name, kwargs=kw)

    def _json(self, method, url, data=None, **extra):
        return getattr(self.client, method)(url, data=json.dumps(data or {}), content_type='application/json', **extra)

    def test_owner_opens_the_editor_page(self):
        """
        GIVEN an owner and a layer with three objects
        WHEN the editor page is requested
        THEN it renders the three columns with the objects embedded as JSON
        """
        response = self.client.get(self._u('editor_layer_objects'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="loe-rows"', html)
        self.assertIn('id="loe-map"', html)
        self.assertIn('id="loe-card"', html)
        self.assertIn('"key": "1"', html)
        self.assertNotIn('visible to respondents immediately', html)

    def test_published_survey_shows_the_live_banner(self):
        """
        GIVEN the survey is published
        WHEN the owner opens the editor
        THEN the page carries the "changes are visible immediately" banner
        """
        self.survey.status = 'published'
        self.survey.save()
        html = self.client.get(self._u('editor_layer_objects')).content.decode()
        self.assertIn('visible to respondents immediately', html)

    def test_viewer_is_refused(self):
        """
        GIVEN a viewer-role collaborator
        WHEN they request the editor page or an endpoint
        THEN the request is refused
        """
        self.client.login(username='loeviewer', password='pw12345678')
        self.assertIn(self.client.get(self._u('editor_layer_objects')).status_code, (403, 404))
        self.assertIn(self._json('post', self._u('editor_layer_objects_collection'), {}).status_code, (403, 404))

    @override_settings(MAP_REFERENCE_LAYERS=False)
    def test_kill_switch_hides_the_editor(self):
        """
        GIVEN the layers kill switch is off
        WHEN the editor page is requested
        THEN 404
        """
        self.assertEqual(self.client.get(self._u('editor_layer_objects')).status_code, 404)

    def test_draw_creates_an_object_and_rebuilds_the_layer(self):
        """
        GIVEN a drawn point geometry
        WHEN it is POSTed to the objects collection
        THEN an object with a generated key exists, its row and card come back, and
             the derived GeoJSON has four features
        """
        response = self._json('post', self._u('editor_layer_objects_collection'),
                              {'geometry': {'type': 'Point', 'coordinates': [-88.09, 38.73]}, 'title': ''})
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['object']['geometry']['type'], 'Point')
        self.assertTrue(data['row']['key'].startswith('o-'))
        self.assertEqual(data['summary']['object_count'], 4)
        self.layer.refresh_from_db()
        self.assertEqual(len(json.loads(self.layer.geojson)['features']), 4)

    def test_invalid_geometry_is_refused(self):
        """
        GIVEN a MultiPolygon (two parts) or garbage geometry
        WHEN POSTed as a new object
        THEN 400 with a readable message and no object created
        """
        ring = lambda x: [[x, 0], [x + 1, 0], [x + 1, 1], [x, 1], [x, 0]]
        bad = {'geometry': {'type': 'MultiPolygon', 'coordinates': [[ring(0)], [ring(3)]]}}
        self.assertEqual(self._json('post', self._u('editor_layer_objects_collection'), bad).status_code, 400)
        self.assertEqual(self._json('post', self._u('editor_layer_objects_collection'), {'geometry': 'nope'}).status_code, 400)
        self.assertEqual(self.layer.items.count(), 3)

    def test_geometry_move_rebuilds(self):
        """
        GIVEN an existing polygon object
        WHEN a new geometry is POSTed to its geometry endpoint
        THEN the object and the derived feature carry the new geometry
        """
        new = {'type': 'Point', 'coordinates': [10.0, 50.0]}
        response = self._json('post', self._u('editor_layer_object_geometry', key='1'), {'geometry': new})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.layer.items.get(key='1').geometry.geom_type, 'Point')
        feature = next(f for f in json.loads(self.layer.__class__.objects.get(pk=self.layer.pk).geojson)['features'] if f['properties']['_key'] == '1')
        self.assertEqual(feature['geometry']['type'], 'Point')

    def test_patch_autosaves_fields_and_sanitizes_description(self):
        """
        GIVEN a PATCH with a title, a category, a link and a description carrying a script
        WHEN it is applied
        THEN the fields are stored, the script is stripped, and the row reflects the change
        """
        response = self._json('patch', self._u('editor_layer_object', key='1'),
                              {'title': 'Ring road overpass', 'category': 'Roads',
                               'link': 'https://city.example/1', 'description': '<p>Plan</p><script>x()</script>'})
        self.assertEqual(response.status_code, 200)
        obj = self.layer.items.get(key='1')
        self.assertEqual((obj.title, obj.category, obj.link), ('Ring road overpass', 'Roads', 'https://city.example/1'))
        self.assertIn('Plan', obj.description)
        self.assertNotIn('<script', obj.description)
        self.assertEqual(response.json()['row']['category'], 'Roads')
        self.assertTrue(response.json()['row']['has_text'])

    def test_delete_reports_answer_count_and_removes(self):
        """
        GIVEN an object with no answers
        WHEN the answer-count endpoint and then DELETE are called
        THEN the count is 0 and the object is gone, layer rebuilt
        """
        self.assertEqual(self.client.get(self._u('editor_layer_object_answers', key='1')).json(), {'answers': 0})
        response = self.client.delete(self._u('editor_layer_object', key='1'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.layer.items.filter(key='1').exists())
        self.assertEqual(response.json()['summary']['object_count'], 2)

    def test_bulk_set_category(self):
        """
        GIVEN two selected objects
        WHEN bulk set_category is POSTed
        THEN both carry the category and the summary lists it
        """
        response = self._json('post', self._u('editor_layer_objects_bulk'),
                              {'action': 'set_category', 'category': 'Parks', 'keys': ['1', '2']})
        self.assertEqual(response.json()['affected'], 2)
        self.assertEqual(self.layer.items.filter(category='Parks').count(), 2)
        self.assertIn('Parks', response.json()['summary']['categories'])

    def test_asset_upload_embed_reorder_and_delete(self):
        """
        GIVEN an object
        WHEN a PNG is uploaded, a YouTube link embedded, the two reordered and the image deleted
        THEN each step returns the updated row and the assets end in the expected state
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        png = SimpleUploadedFile('render.png', b'\x89PNG\r\n\x1a\n' + b'0' * 40, content_type='image/png')
        up = self.client.post(self._u('editor_layer_asset_create', key='1'), {'file': png})
        self.assertEqual(up.status_code, 201)
        self.assertEqual(up.json()['asset']['kind'], 'image')
        self.assertEqual(up.json()['row']['assets'], {'image': 1})
        em = self.client.post(self._u('editor_layer_asset_create', key='1'), {'embed_url': 'https://youtu.be/dQw4w9WgXcQ'})
        self.assertEqual(em.status_code, 201)
        self.assertEqual(em.json()['asset']['url'], 'https://www.youtube.com/embed/dQw4w9WgXcQ')
        bad = self.client.post(self._u('editor_layer_asset_create', key='1'), {'embed_url': 'https://evil.example/v'})
        self.assertEqual(bad.status_code, 400)
        image_id, embed_id = up.json()['asset']['id'], em.json()['asset']['id']
        self._json('post', self._u('editor_layer_assets_reorder', key='1'), {'order': [embed_id, image_id]})
        obj = self.layer.items.get(key='1')
        self.assertEqual(list(obj.assets.values_list('kind', flat=True)), ['embed', 'image'])
        rm = self.client.delete(self._u('editor_layer_asset', key='1', asset_id=image_id))
        self.assertEqual(rm.status_code, 200)
        self.assertEqual(rm.json()['row']['assets'], {'embed': 1})

    def test_geojson_import_dry_run_then_confirm(self):
        """
        GIVEN a GeoJSON of two new zones with keys 10 and 11
        WHEN imported with dry_run and then for real, mapping name→title and zone_id→key
        THEN the dry run reports 2 to create without writing, and the real run creates them
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        parsed = json.loads(_zones_geojson(count=2))
        for i, f in enumerate(parsed['features']):
            f['properties']['zone_id'] = 10 + i
        body = json.dumps(parsed).encode()
        dry = self.client.post(self._u('editor_layer_import_geojson'), {
            'file': SimpleUploadedFile('more.geojson', body), 'dry_run': '1', 'map_key': 'zone_id', 'map_title': 'name'})
        self.assertEqual(dry.status_code, 200)
        self.assertEqual((dry.json()['created'], dry.json()['collisions'], dry.json()['dry_run']), (2, [], True))
        self.assertEqual(dry.json()['properties'], ['name', 'zone_id'])
        self.assertEqual(self.layer.items.count(), 3)
        real = self.client.post(self._u('editor_layer_import_geojson'), {
            'file': SimpleUploadedFile('more.geojson', body), 'map_key': 'zone_id', 'map_title': 'name'})
        self.assertEqual(real.json()['created'], 2)
        self.assertEqual(sorted(self.layer.items.values_list('key', flat=True)), ['1', '10', '11', '2', '3'])

    def test_csv_with_coordinates_creates_points(self):
        """
        GIVEN a CSV with title, lat, lng, category columns
        WHEN imported
        THEN one point object per row is created with those fields
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        csv_text = 'title,lat,lng,category\nStation A,55.75,37.62,Metro\nStation B,55.76,37.63,Tram\nBroken,x,y,Tram\n'
        response = self.client.post(self._u('editor_layer_import_csv'), {'file': SimpleUploadedFile('s.csv', csv_text.encode())})
        data = response.json()
        self.assertEqual((data['mode'], data['created'], data['invalid']), ('coordinates', 2, [3]))
        obj = self.layer.items.get(title='Station A')
        self.assertEqual((obj.category, obj.geometry.geom_type), ('Metro', 'Point'))

    def test_content_csv_matches_by_title_and_reports_unmatched(self):
        """
        GIVEN a CSV without coordinates carrying title, description and link
        WHEN imported
        THEN matching objects receive the content and the unmatched row is listed
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        csv_text = 'title,description,link\nArea 1,Pocket park,https://city.example/1\nNowhere,x,https://x\n'
        response = self.client.post(self._u('editor_layer_import_csv'), {'file': SimpleUploadedFile('c.csv', csv_text.encode())})
        data = response.json()
        self.assertEqual((data['mode'], data['updated'], data['unmatched']), ('content', 1, ['Nowhere']))
        obj = self.layer.items.get(key='1')
        self.assertIn('Pocket park', obj.description)
        self.assertEqual(obj.link, 'https://city.example/1')

    def test_photo_import_matches_by_key_then_title(self):
        """
        GIVEN photos named 2.png (a key) and area 3.png (a title) and stray.png
        WHEN uploaded as a batch
        THEN the first two are attached as covers and stray.png is reported unmatched
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        body = b'\x89PNG\r\n\x1a\n' + b'0' * 40
        files = [SimpleUploadedFile('2.png', body, content_type='image/png'),
                 SimpleUploadedFile('Area 3.png', body, content_type='image/png'),
                 SimpleUploadedFile('stray.png', body, content_type='image/png')]
        response = self.client.post(self._u('editor_layer_import_photos'), {'files': files})
        data = response.json()
        self.assertEqual((data['attached'], data['unmatched']), (2, ['stray.png']))
        self.assertIsNotNone(self.layer.items.get(key='2').cover)
        self.assertIsNotNone(self.layer.items.get(key='3').cover)
        self.assertIsNone(self.layer.items.get(key='1').cover)

    def test_new_empty_layer(self):
        """
        GIVEN the settings card's "New layer" action
        WHEN it POSTs
        THEN an empty layer exists on the canonical survey and the editor for it renders the empty state
        """
        response = self.client.post(reverse('editor_layer_create_empty', kwargs={'survey_uuid': self.survey.uuid}), {'name': 'Drawn'})
        self.assertEqual(response.status_code, 201)
        layer_id = response.json()['id']
        html = self.client.get(reverse('editor_layer_objects', kwargs={'survey_uuid': self.survey.uuid, 'layer_id': layer_id})).content.decode()
        self.assertIn('Add your first object', html)

    def test_feature_cap_on_create(self):
        """
        GIVEN the feature cap lowered to the current count
        WHEN another object is POSTed
        THEN 400 naming the cap
        """
        with patch('survey.layers.MAX_LAYER_FEATURES', 3):
            response = self._json('post', self._u('editor_layer_objects_collection'),
                                  {'geometry': {'type': 'Point', 'coordinates': [0, 0]}})
        self.assertEqual(response.status_code, 400)
        self.assertIn('limit is 3', response.json()['error'])

    def test_settings_card_links_to_the_editor(self):
        """
        GIVEN the Survey settings page
        WHEN the owner opens it
        THEN each layer card carries "Open editor" and the "New empty layer" action is present
        """
        html = self.client.get(reverse('editor_survey_settings_panel', args=[self.survey.uuid])).content.decode()
        self.assertIn(self._u('editor_layer_objects'), html)
        self.assertIn('ref-layers-new', html)
