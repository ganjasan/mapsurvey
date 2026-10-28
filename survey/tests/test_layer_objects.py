"""Tests for the `layer-objects` capability (openspec/specs/layer-objects/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from io import BytesIO
from unittest.mock import patch
import json
import zipfile
from survey.models import Organization, SurveyHeader, SurveySection, Question, Membership
from survey.serialization import export_survey_to_zip, import_survey_from_zip
from survey.versioning import clone_survey_for_draft
from survey.tests.helpers import _objects_layer, _validated_geojson_text, _zones_geojson


class LayerObjectsModelTest(TestCase):
    """Objects are the source; the layer GeoJSON is derived (spec layer-objects)."""

    def setUp(self):
        self.org = Organization.objects.create(name="Objects Org")
        self.survey = SurveyHeader.objects.create(
            name="objects_survey", organization=self.org, redirect_url="/thanks/", status='published',
        )
        SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True,
        )

    def test_import_creates_objects_and_derived_geojson(self):
        """
        GIVEN a validated 3-zone FeatureCollection with a key field
        WHEN it is imported into a layer
        THEN 3 objects exist keyed by zone_id, titled by name, and the derived
             GeoJSON carries the raw properties plus the reserved fields
        """
        layer = _objects_layer(self.survey, key_field='zone_id', label_field='name')
        self.assertEqual(layer.items.count(), 3)
        self.assertEqual(sorted(layer.items.values_list('key', flat=True)), ['1', '2', '3'])
        self.assertEqual(layer.items.get(key='2').title, 'Area 2')
        self.assertEqual(layer.feature_count, 3)
        feature = json.loads(layer.geojson)['features'][0]
        self.assertEqual(feature['properties']['name'], 'Area 1')
        self.assertEqual(feature['properties']['_key'], '1')
        self.assertEqual(feature['properties']['_title'], 'Area 1')
        self.assertFalse(feature['properties']['_has_content'])

    def test_object_write_rebuilds_geojson_and_bumps_etag(self):
        """
        GIVEN an imported layer
        WHEN an object is renamed and the layer rebuilt
        THEN the served GeoJSON carries the new title and the ETag changes
        """
        from survey.layers import rebuild_layer
        layer = _objects_layer(self.survey, key_field='zone_id')
        url = reverse('survey_layer_geojson', kwargs={'survey_slug': str(self.survey.uuid), 'layer_id': layer.pk})
        etag_before = self.client.get(url)['ETag']
        obj = layer.items.get(key='1')
        obj.title = 'Renamed zone'
        obj.save()
        rebuild_layer(layer)
        response = self.client.get(url)
        titles = [f['properties']['_title'] for f in json.loads(response.content)['features']]
        self.assertIn('Renamed zone', titles)
        self.assertNotEqual(response['ETag'], etag_before)

    def test_key_collision_is_reported_not_duplicated(self):
        """
        GIVEN a layer that already holds key "2"
        WHEN the same file is imported again with the key field
        THEN no duplicate objects are created and the collisions are reported
        """
        from survey.layers import objects_from_features, validate_layer_upload
        layer = _objects_layer(self.survey, key_field='zone_id')
        geojson, _, _ = _validated_geojson_text(_zones_geojson().encode())
        report = objects_from_features(layer, json.loads(geojson)['features'])
        self.assertEqual(report['created'], 0)
        self.assertEqual(sorted(report['collisions']), ['1', '2', '3'])
        self.assertEqual(layer.items.count(), 3)

    def test_raw_properties_survive_and_reserved_names_are_not_clobbered(self):
        """
        GIVEN a feature carrying simplestyle and a property named like a reserved field
        WHEN it is imported
        THEN the object keeps the properties and the derived feature re-emits them
             alongside the reserved fields
        """
        feature = {"type": "Feature",
                   "properties": {"stroke": "#0a0", "custom": 7, "_key": "spoof", "name": "P"},
                   "geometry": {"type": "Point", "coordinates": [10.0, 50.0]}}
        text = json.dumps({"type": "FeatureCollection", "features": [feature]})
        layer = _objects_layer(self.survey, geojson_text=text)
        obj = layer.items.get()
        self.assertEqual(obj.properties['custom'], 7)
        props = json.loads(layer.geojson)['features'][0]['properties']
        self.assertEqual(props['stroke'], '#0a0')
        self.assertEqual(props['_key'], obj.key)
        self.assertNotEqual(props['_key'], 'spoof')

    def test_multipart_geometry_is_exploded(self):
        """
        GIVEN a MultiPolygon feature with two parts
        WHEN it is imported
        THEN two objects exist, keyed <key>-1 and <key>-2
        """
        ring = lambda x: [[x, 0], [x + 1, 0], [x + 1, 1], [x, 1], [x, 0]]
        feature = {"type": "Feature", "properties": {"id": "mp"},
                   "geometry": {"type": "MultiPolygon", "coordinates": [[ring(0)], [ring(5)]]}}
        text = json.dumps({"type": "FeatureCollection", "features": [feature]})
        layer = _objects_layer(self.survey, geojson_text=text, key_field='id')
        self.assertEqual(sorted(layer.items.values_list('key', flat=True)), ['mp-1', 'mp-2'])

    def test_feature_cap_refuses_another_object(self):
        """
        GIVEN a layer at the feature cap
        WHEN one more object is checked against the caps
        THEN a human-readable refusal names the cap
        """
        from survey.layers import check_object_caps, LayerValidationError, MAX_LAYER_FEATURES
        layer = _objects_layer(self.survey)
        with patch('survey.layers.MAX_LAYER_FEATURES', 3):
            with self.assertRaises(LayerValidationError) as ctx:
                check_object_caps(layer, adding=1)
        self.assertIn('limit is 3', str(ctx.exception))
        self.assertEqual(MAX_LAYER_FEATURES, 5000)


class LayerObjectCardEndpointTest(TestCase):
    """GET /surveys/<uuid>/layers/<id>/objects/<key>/ — gated like the layer."""

    def setUp(self):
        self.org = Organization.objects.create(name="Card Org")
        self.survey = SurveyHeader.objects.create(
            name="card_survey", organization=self.org, redirect_url="/thanks/", status='published',
        )
        SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True,
        )
        self.layer = _objects_layer(self.survey, key_field='zone_id')

    def _url(self, key='1'):
        return reverse('survey_layer_object', kwargs={
            'survey_slug': str(self.survey.uuid), 'layer_id': self.layer.pk, 'key': key})

    def test_card_is_served_with_sanitized_description(self):
        """
        GIVEN an object whose description carries a script tag
        WHEN the card is fetched
        THEN the payload has the visible text and no script element
        """
        obj = self.layer.items.get(key='1')
        obj.description = '<p>Pocket park</p><script>alert(1)</script>'
        obj.link = 'https://city.example/p'
        obj.save()
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('Pocket park', data['description'])
        self.assertNotIn('<script', data['description'])
        self.assertEqual(data['link'], 'https://city.example/p')
        self.assertEqual(data['assets'], [])

    def test_card_of_a_draft_survey_is_a_bare_404(self):
        """
        GIVEN the survey is a draft
        WHEN an anonymous visitor fetches an object card
        THEN the response is 404, exactly as the layer endpoint behaves
        """
        self.survey.status = 'draft'
        self.survey.save()
        self.assertEqual(self.client.get(self._url()).status_code, 404)

    def test_unknown_key_is_404(self):
        """
        GIVEN a published survey
        WHEN a key that is not in the layer is requested
        THEN 404
        """
        self.assertEqual(self.client.get(self._url('nope')).status_code, 404)

    @override_settings(MAP_REFERENCE_LAYERS=False)
    def test_kill_switch_hides_the_card(self):
        """
        GIVEN the layers kill switch is off
        WHEN a card is fetched
        THEN 404
        """
        self.assertEqual(self.client.get(self._url()).status_code, 404)


class LayerObjectAssetTest(TestCase):
    """Attachment validation, cover and the derived _cover field."""

    def setUp(self):
        self.org = Organization.objects.create(name="Asset Org")
        self.survey = SurveyHeader.objects.create(
            name="asset_survey", organization=self.org, redirect_url="/thanks/", status='published',
        )
        SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True,
        )
        self.layer = _objects_layer(self.survey, key_field='zone_id')
        self.obj = self.layer.items.get(key='1')

    def _png(self, name='render.png', size=None):
        from django.core.files.uploadedfile import SimpleUploadedFile
        body = b'\x89PNG\r\n\x1a\n' + (b'0' * (size or 64))
        return SimpleUploadedFile(name, body, content_type='image/png')

    def test_first_image_is_the_cover_and_reaches_the_geojson(self):
        """
        GIVEN an object with no images
        WHEN a PNG is attached and the layer rebuilt
        THEN the asset lives under a random layer_assets/ key, is the cover, and
             the derived feature's _cover points at it with _has_content true
        """
        from survey.models import LayerObjectAsset
        from survey.layer_assets import validate_asset_upload
        from survey.layers import rebuild_layer
        upload = self._png()
        kind, content_type = validate_asset_upload(self.obj, upload)
        self.assertEqual((kind, content_type), ('image', 'image/png'))
        asset = LayerObjectAsset.objects.create(
            object=self.obj, kind=kind, file=upload, title=upload.name,
            content_type=content_type, size_bytes=upload.size)
        self.assertRegex(asset.file.name, r'^layer_assets/[0-9a-f]{32}\.png$')
        self.assertEqual(self.obj.cover, asset)
        rebuild_layer(self.layer)
        feature = next(f for f in json.loads(self.layer.geojson)['features'] if f['properties']['_key'] == '1')
        self.assertEqual(feature['properties']['_cover'], asset.url)
        self.assertTrue(feature['properties']['_has_content'])
        card = self.client.get(reverse('survey_layer_object', kwargs={
            'survey_slug': str(self.survey.uuid), 'layer_id': self.layer.pk, 'key': '1'})).json()
        self.assertEqual(card['cover'], asset.url)
        self.assertEqual(card['assets'][0]['kind'], 'image')

    def test_spoofed_and_oversized_files_are_refused(self):
        """
        GIVEN a .png whose bytes are not PNG, and a file over the per-file cap
        WHEN each is validated
        THEN both are refused with a readable reason and no row is created
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        from survey.layer_assets import validate_asset_upload, AssetRejected
        spoof = SimpleUploadedFile('x.png', b'not a png at all', content_type='image/png')
        with self.assertRaises(AssetRejected):
            validate_asset_upload(self.obj, spoof)
        big = SimpleUploadedFile('big.png', b'\x89PNG\r\n\x1a\n' + b'0' * 32, content_type='image/png')
        big.size = 26 * 1024 * 1024
        with self.assertRaises(AssetRejected) as ctx:
            validate_asset_upload(self.obj, big)
        self.assertIn('25 MB', str(ctx.exception.message))
        self.assertEqual(self.obj.assets.count(), 0)

    def test_unsupported_type_is_refused(self):
        """
        GIVEN an SVG upload (a stored-XSS vector on a public bucket)
        WHEN it is validated
        THEN it is refused
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        from survey.layer_assets import validate_asset_upload, AssetRejected
        svg = SimpleUploadedFile('a.svg', b'<svg/>', content_type='image/svg+xml')
        with self.assertRaises(AssetRejected):
            validate_asset_upload(self.obj, svg)

    def test_per_object_cap(self):
        """
        GIVEN an object already carrying the maximum number of attachments
        WHEN another is validated
        THEN it is refused with the cap in the message
        """
        from survey.models import LayerObjectAsset
        from survey.layer_assets import validate_asset_upload, AssetRejected, MAX_ASSETS_PER_OBJECT
        for i in range(MAX_ASSETS_PER_OBJECT):
            LayerObjectAsset.objects.create(object=self.obj, kind='embed',
                                            embed_url='https://www.youtube.com/embed/abcdef', position=i)
        with self.assertRaises(AssetRejected) as ctx:
            validate_asset_upload(self.obj, self._png())
        self.assertIn(str(MAX_ASSETS_PER_OBJECT), str(ctx.exception.message))

    def test_per_layer_cap(self):
        """
        GIVEN a layer whose attachments already total the layer cap
        WHEN one more file is validated
        THEN it is refused
        """
        from survey.models import LayerObjectAsset
        from survey.layer_assets import validate_asset_upload, AssetRejected, MAX_ASSET_BYTES_PER_LAYER
        other = self.layer.items.get(key='2')
        LayerObjectAsset.objects.create(object=other, kind='video', embed_url='',
                                        size_bytes=MAX_ASSET_BYTES_PER_LAYER)
        with self.assertRaises(AssetRejected) as ctx:
            validate_asset_upload(self.obj, self._png())
        self.assertIn('200 MB', str(ctx.exception.message))

    def test_embed_host_allow_list(self):
        """
        GIVEN YouTube, youtu.be and Vimeo links and a link on another host
        WHEN they are normalized
        THEN the three become player URLs and the other is refused
        """
        from survey.layer_assets import normalize_embed_url, AssetRejected
        self.assertEqual(normalize_embed_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ'),
                         'https://www.youtube.com/embed/dQw4w9WgXcQ')
        self.assertEqual(normalize_embed_url('https://youtu.be/dQw4w9WgXcQ?t=4'),
                         'https://www.youtube.com/embed/dQw4w9WgXcQ')
        self.assertEqual(normalize_embed_url('https://vimeo.com/123456789'),
                         'https://player.vimeo.com/video/123456789')
        with self.assertRaises(AssetRejected):
            normalize_embed_url('https://evil.example/v?v=dQw4w9WgXcQ')
        with self.assertRaises(AssetRejected):
            normalize_embed_url('javascript:alert(1)')


class LayerOwnershipTest(TestCase):
    """Layers belong to the canonical survey; versions and draft copies borrow them (D-3)."""

    def setUp(self):
        self.org = Organization.objects.create(name="Owner Org")
        self.owner = User.objects.create_user(username='canonowner', password='pw12345678')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.canonical = SurveyHeader.objects.create(
            name="canonical_survey", organization=self.org, redirect_url="/thanks/",
            status='published', created_by=self.owner,
        )
        SurveySection.objects.create(
            survey_header=self.canonical, name="s1", title="S1", code="S1", is_head=True,
        )
        self.layer = _objects_layer(self.canonical, key_field='zone_id')

    def test_draft_copy_reads_the_canonical_layers_without_copying(self):
        """
        GIVEN a published survey with a layer
        WHEN a draft copy is created
        THEN the copy resolves the same layer through layers_for and no layer row is duplicated
        """
        from survey.versioning import clone_survey_for_draft
        from survey.layers import layers_for
        from survey.models import SurveyMapLayer
        draft = clone_survey_for_draft(self.canonical)
        self.assertEqual(list(layers_for(draft)), [self.layer])
        self.assertEqual(SurveyMapLayer.objects.count(), 1)

    def test_draft_copy_serves_the_canonical_layer_geometry(self):
        """
        GIVEN a draft copy of a published survey with a layer
        WHEN the owner fetches the layer by the draft's uuid
        THEN the canonical layer's GeoJSON is served
        """
        from survey.versioning import clone_survey_for_draft
        draft = clone_survey_for_draft(self.canonical)
        self.client.login(username='canonowner', password='pw12345678')
        url = reverse('survey_layer_geojson', kwargs={'survey_slug': str(draft.uuid), 'layer_id': self.layer.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(json.loads(response.content)['features']), 3)

    def test_archived_version_reads_the_canonical_layers(self):
        """
        GIVEN an archived version pointing at the canonical survey
        WHEN layers are resolved for it
        THEN they are the canonical survey's
        """
        from survey.layers import layers_for
        version = SurveyHeader.objects.create(
            name="canonical_survey_v1", organization=self.org, redirect_url="/thanks/",
            status='closed', canonical_survey=self.canonical, is_canonical=False, version_number=1,
        )
        self.assertEqual(list(layers_for(version)), [self.layer])


class LayerSplitMigrationTest(TestCase):
    """0068: FD-1 layers become objects, losslessly."""

    def _run_forwards(self):
        from django.apps import apps
        from django.db import connection
        from importlib import import_module
        module = import_module('survey.migrations.0068_split_layers_into_objects')
        module.forwards(apps, connection.schema_editor)

    def setUp(self):
        self.org = Organization.objects.create(name="Migration Org")
        self.survey = SurveyHeader.objects.create(
            name="migration_survey", organization=self.org, redirect_url="/thanks/",
        )

    def test_zones_layer_migrates_losslessly(self):
        """
        GIVEN a pre-objects layer storing a 35-polygon FeatureCollection keyed by zone_id
        WHEN the split migration runs
        THEN 35 objects exist keyed by zone_id, the derived GeoJSON has 35 features
             with the same bbox, and geojson_legacy holds the original text
        """
        from survey.models import SurveyMapLayer
        from survey.layers import validate_layer_upload, bbox_of_collection
        geojson, count, _ = _validated_geojson_text(_zones_geojson(count=35).encode())
        layer = SurveyMapLayer.objects.create(
            survey=self.survey, name="Legacy", geojson=geojson, feature_count=count,
            size_bytes=len(geojson), key_field='zone_id', label_field='name',
        )
        self._run_forwards()
        layer.refresh_from_db()
        self.assertEqual(layer.items.count(), 35)
        self.assertEqual(layer.items.get(key='35').title, 'Area 35')
        self.assertEqual(len(json.loads(layer.geojson)['features']), 35)
        for derived, original in zip(bbox_of_collection(layer.geojson), bbox_of_collection(geojson)):
            self.assertAlmostEqual(derived, original, places=6)
        self.assertEqual(layer.geojson_legacy, geojson)
        self.assertEqual(layer.feature_count, 35)

    def test_duplicate_key_field_falls_back_to_generated_keys(self):
        """
        GIVEN a legacy layer whose key_field values repeat
        WHEN the migration runs
        THEN keys are f-<index> and every feature still becomes an object
        """
        from survey.models import SurveyMapLayer
        from survey.layers import validate_layer_upload
        parsed = json.loads(_zones_geojson(count=3))
        for f in parsed['features']:
            f['properties']['zone_id'] = 1
        geojson, count, _ = _validated_geojson_text(json.dumps(parsed).encode())
        layer = SurveyMapLayer.objects.create(
            survey=self.survey, name="Dupes", geojson=geojson, feature_count=count,
            size_bytes=len(geojson), key_field='zone_id',
        )
        self._run_forwards()
        self.assertEqual(sorted(layer.items.values_list('key', flat=True)), ['f-1', 'f-2', 'f-3'])

    def test_migration_is_idempotent(self):
        """
        GIVEN a layer that already has objects
        WHEN the migration runs again
        THEN nothing is duplicated
        """
        layer = _objects_layer(self.survey)
        self._run_forwards()
        self.assertEqual(layer.items.count(), 3)


class LayerObjectsSerializationTest(TestCase):
    """Objects and attachments through export → import (survey-serialization delta)."""

    def setUp(self):
        from survey.models import LayerObjectAsset
        from django.core.files.uploadedfile import SimpleUploadedFile
        from survey.layers import rebuild_layer
        self.org = Organization.objects.create(name="Obj Ser Org")
        self.survey = SurveyHeader.objects.create(
            name="obj_ser_survey", organization=self.org, redirect_url="/thanks/",
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True,
        )
        Question.objects.create(
            survey_section=self.section, code="OS001", name="Q", input_type="text", order_number=1,
        )
        self.layer = _objects_layer(self.survey, name="Sites", key_field='zone_id', label_field='name')
        self.obj = self.layer.items.get(key='2')
        self.obj.description = '<p>Pocket <b>park</b></p>'
        self.obj.link = 'https://city.example/2'
        self.obj.category = 'Парки'
        self.obj.save()
        png = SimpleUploadedFile('render.png', b'\x89PNG\r\n\x1a\n' + b'0' * 40, content_type='image/png')
        LayerObjectAsset.objects.create(object=self.obj, kind='image', file=png, title='render.png',
                                        content_type='image/png', size_bytes=png.size, position=0)
        LayerObjectAsset.objects.create(object=self.obj, kind='embed', title='walkthrough',
                                        embed_url='https://www.youtube.com/embed/dQw4w9WgXcQ', position=1)
        rebuild_layer(self.layer)

    def _export(self):
        buf = BytesIO()
        export_survey_to_zip(self.survey, buf, 'structure')
        buf.seek(0)
        return buf

    def test_archive_carries_objects_manifest_and_asset_bytes(self):
        """
        GIVEN a layer with an object carrying an image and an embed
        WHEN the survey is exported
        THEN the archive has objects.json, the asset file, and the derived GeoJSON keyed by _key
        """
        with zipfile.ZipFile(self._export()) as zf:
            names = zf.namelist()
            self.assertIn('layers/0/objects.json', names)
            self.assertTrue(any(n.startswith('layers/0/assets/') and n.endswith('.png') for n in names))
            manifest = json.loads(zf.read('layers/0/objects.json'))
            entry = next(e for e in manifest if e['key'] == '2')
            self.assertEqual(entry['description'], '<p>Pocket <b>park</b></p>')
            self.assertEqual([a['kind'] for a in entry['assets']], ['image', 'embed'])
            geo = json.loads(zf.read('layers/0.geojson'))
            self.assertEqual(sorted(f['properties']['_key'] for f in geo['features']), ['1', '2', '3'])

    def test_objects_and_attachments_round_trip(self):
        """
        GIVEN the exported archive
        WHEN it is imported
        THEN keys, titles, descriptions, links, categories and both attachments arrive,
             with the image copied into storage under a fresh random key
        """
        buf = self._export()
        self.survey.name = 'obj_ser_survey_old'
        self.survey.save()
        imported, warnings = import_survey_from_zip(buf)
        self.assertEqual(warnings, [])
        layer = imported.map_layers.get()
        self.assertEqual(sorted(layer.items.values_list('key', flat=True)), ['1', '2', '3'])
        obj = layer.items.get(key='2')
        self.assertEqual((obj.title, obj.category, obj.link), ('Area 2', 'Парки', 'https://city.example/2'))
        self.assertIn('<b>park</b>', obj.description)
        kinds = list(obj.assets.values_list('kind', flat=True))
        self.assertEqual(kinds, ['image', 'embed'])
        image = obj.assets.get(kind='image')
        self.assertRegex(image.file.name, r'^layer_assets/[0-9a-f]{32}\.png$')
        self.assertNotEqual(image.file.name, self.obj.assets.get(kind='image').file.name)
        self.assertEqual(obj.assets.get(kind='embed').embed_url, 'https://www.youtube.com/embed/dQw4w9WgXcQ')
        self.assertNotIn('_key', obj.properties)
        self.assertEqual(layer.feature_count, 3)

    def test_missing_asset_file_is_a_warning(self):
        """
        GIVEN an archive whose manifest names an asset entry that is absent
        WHEN it is imported
        THEN the object imports without that asset and the warning names the file
        """
        buf = self._export()
        stripped = BytesIO()
        with zipfile.ZipFile(buf) as src, zipfile.ZipFile(stripped, 'w') as dst:
            for name in src.namelist():
                if not name.startswith('layers/0/assets/'):
                    dst.writestr(name, src.read(name))
        stripped.seek(0)
        self.survey.name = 'obj_ser_survey_old'
        self.survey.save()
        imported, warnings = import_survey_from_zip(stripped)
        obj = imported.map_layers.get().items.get(key='2')
        self.assertEqual(list(obj.assets.values_list('kind', flat=True)), ['embed'])
        self.assertTrue(any('is missing' in w for w in warnings), warnings)

    def test_fd1_archive_without_manifest_creates_objects(self):
        """
        GIVEN an FD-1-era archive: layers/0.geojson without reserved fields and no objects.json
        WHEN it is imported
        THEN objects are created from the features with keys and titles as the migration derives them
        """
        buf = self._export()
        rebuilt = BytesIO()
        with zipfile.ZipFile(buf) as src, zipfile.ZipFile(rebuilt, 'w') as dst:
            for name in src.namelist():
                if name.startswith('layers/0/'):
                    continue
                if name == 'layers/0.geojson':
                    dst.writestr(name, _zones_geojson())
                else:
                    dst.writestr(name, src.read(name))
        rebuilt.seek(0)
        self.survey.name = 'obj_ser_survey_old'
        self.survey.save()
        imported, warnings = import_survey_from_zip(rebuilt)
        layer = imported.map_layers.get()
        self.assertEqual(sorted(layer.items.values_list('key', flat=True)), ['1', '2', '3'])
        self.assertEqual(layer.items.get(key='1').title, 'Area 1')
        self.assertEqual(layer.items.get(key='1').assets.count(), 0)
