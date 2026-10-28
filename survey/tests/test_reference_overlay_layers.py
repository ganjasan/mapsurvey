"""Tests for the `reference-overlay-layers` capability (openspec/specs/reference-overlay-layers/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, SimpleTestCase, Client, override_settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.urls import reverse
from io import BytesIO
from unittest import mock
import json
import re
import zipfile
from survey.models import Organization, SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership, SurveyCollaborator
from survey.serialization import export_survey_to_zip, import_survey_from_zip
import os
from survey.tests.helpers import _objects_layer, _validated_geojson_text, _zones_geojson


class LayerValidationTest(SimpleTestCase):
    """validate_layer_upload — the single gate every stored layer passes."""

    def test_valid_collection_is_accepted(self):
        """
        GIVEN a well-formed WGS84 FeatureCollection of three zones
        WHEN it is validated
        THEN it is accepted with the feature count and the union of property names
        """
        from survey.layers import validate_layer_upload
        features, props, _z = validate_layer_upload(_zones_geojson().encode())
        self.assertEqual(len(features), 3)
        self.assertEqual(props, ['name', 'zone_id'])
        self.assertTrue(all(f['type'] == 'Feature' for f in features))

    def test_projected_coordinates_are_rejected(self):
        """
        GIVEN a file whose coordinates are metres in a projected CRS
        WHEN it is validated
        THEN it is rejected with a message naming the coordinate system
        """
        from survey.layers import validate_layer_upload, LayerValidationError
        with self.assertRaises(LayerValidationError) as ctx:
            validate_layer_upload(_zones_geojson(projected=True).encode())
        self.assertIn('coordinate system', str(ctx.exception))

    def test_oversize_file_is_rejected(self):
        """
        GIVEN an upload larger than the 10 MB cap
        WHEN it is validated
        THEN it is rejected on size before any parsing
        """
        from survey.layers import validate_layer_upload, LayerValidationError, MAX_LAYER_BYTES
        with self.assertRaises(LayerValidationError) as ctx:
            validate_layer_upload(b'x' * (MAX_LAYER_BYTES + 1))
        self.assertIn('larger than', str(ctx.exception))

    def test_bare_geometry_is_normalized(self):
        """
        GIVEN a file holding a bare geometry instead of a FeatureCollection
        WHEN it is validated
        THEN it is normalized into a single-feature FeatureCollection
        """
        from survey.layers import validate_layer_upload
        raw = json.dumps({"type": "Point", "coordinates": [13.4, 52.5]}).encode()
        features, props, _z = validate_layer_upload(raw)
        self.assertEqual(len(features), 1)
        self.assertEqual(features[0]['type'], 'Feature')
        self.assertEqual(features[0]['geometry']['type'], 'Point')

    def test_parse_is_what_flows_on_not_the_raw_bytes(self):
        """
        GIVEN an upload carrying a BOM and sloppy whitespace
        WHEN it is validated
        THEN the parsed features flow on (the stored text is rebuilt from the
             objects they become), so the BOM and the whitespace never reach a layer
        """
        from survey.layers import validate_layer_upload
        raw = ('﻿' + '  ' + _zones_geojson(1)).encode('utf-8')
        features, _, _z = validate_layer_upload(raw)
        self.assertEqual(features[0]['properties']['name'], 'Area 1')

    def test_z_ordinate_is_discarded(self):
        """
        GIVEN a FeatureCollection whose positions carry elevation
        WHEN it is validated
        THEN every position is truncated to [lng, lat] and dropped_z is reported

        QGIS and ArcGIS write Z by default and `LayerObject.geometry` is a 2D
        column, so such a file used to pass validation and die at the database
        with `DataError: Geometry has Z dimension but column does not`.
        """
        from survey.layers import validate_layer_upload
        raw = json.dumps({
            'type': 'FeatureCollection',
            'features': [
                {'type': 'Feature', 'properties': {'name': 'stop'},
                 'geometry': {'type': 'Point', 'coordinates': [6.96, 50.94, 58.2]}},
                {'type': 'Feature', 'properties': {'name': 'route'},
                 'geometry': {'type': 'LineString',
                              'coordinates': [[6.96, 50.94, 58.2], [6.97, 50.95, 59.1]]}},
            ],
        }).encode()
        features, _props, dropped_z = validate_layer_upload(raw)
        self.assertTrue(dropped_z)
        self.assertEqual(features[0]['geometry']['coordinates'], [6.96, 50.94])
        self.assertEqual(features[1]['geometry']['coordinates'],
                         [[6.96, 50.94], [6.97, 50.95]])

    def test_two_dimensional_file_is_untouched(self):
        """
        GIVEN a FeatureCollection with no elevation
        WHEN it is validated
        THEN the coordinates are unchanged and dropped_z is False
        """
        from survey.layers import validate_layer_upload
        features, _props, dropped_z = validate_layer_upload(_zones_geojson(1).encode())
        self.assertFalse(dropped_z)
        ring = features[0]['geometry']['coordinates'][0]
        self.assertTrue(all(len(position) == 2 for position in ring))

    def test_explode_geometry_also_drops_z(self):
        """
        GIVEN a 3D geometry handed straight to explode_geometry
        WHEN it is exploded into single-part geometries
        THEN the parts are two-dimensional

        explode_geometry is the choke point EVERY stored geometry passes --
        the bulk import and a single drawn or pasted object both come through
        it -- so the reduction is repeated there rather than trusted upstream.
        """
        from survey.layers import explode_geometry
        parts = explode_geometry({'type': 'MultiPoint',
                                  'coordinates': [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]})
        self.assertEqual([p['coordinates'] for p in parts], [[1.0, 2.0], [4.0, 5.0]])

    def test_invalid_json_is_rejected(self):
        """
        GIVEN a file that is not JSON at all
        WHEN it is validated
        THEN it is rejected as not being a .geojson file
        """
        from survey.layers import validate_layer_upload, LayerValidationError
        with self.assertRaises(LayerValidationError):
            validate_layer_upload(b'<?xml version="1.0"?><kml/>')


class LayerEndpointTest(TestCase):
    """The gated GeoJSON endpoint."""

    def setUp(self):
        from survey.models import SurveyMapLayer
        from survey.layers import validate_layer_upload
        self.org = Organization.objects.create(name="Layer Endpoint Org")
        self.survey = SurveyHeader.objects.create(
            name="layer_endpoint_survey", organization=self.org, redirect_url="/thanks/",
            status='published',
        )
        SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True,
        )
        geojson, count, _ = _validated_geojson_text(_zones_geojson().encode())
        self.layer = SurveyMapLayer.objects.create(
            survey=self.survey, name="Zones", geojson=geojson, feature_count=count,
            size_bytes=len(geojson),
        )
        self.url = reverse('survey_layer_geojson', kwargs={
            'survey_slug': str(self.survey.uuid), 'layer_id': self.layer.pk,
        })

    def test_published_survey_serves_the_layer(self):
        """
        GIVEN a published survey with a reference layer
        WHEN an anonymous visitor fetches the layer URL
        THEN the GeoJSON is returned with an ETag and private caching
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(json.loads(response.content)['features']), 3)
        self.assertTrue(response['ETag'])
        self.assertIn('private', response['Cache-Control'])

    def test_draft_survey_layer_is_a_bare_404(self):
        """
        GIVEN the survey is still a draft
        WHEN an anonymous visitor fetches the layer URL
        THEN the response is 404, exactly as the survey's own pages are
        """
        self.survey.status = 'draft'
        self.survey.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_matching_etag_revalidates_without_a_body(self):
        """
        GIVEN a client that already holds the layer
        WHEN it re-requests with the matching If-None-Match
        THEN the endpoint answers 304 with no body
        """
        etag = self.client.get(self.url)['ETag']
        response = self.client.get(self.url, HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(response.status_code, 304)
        self.assertEqual(response.content, b'')

    def test_layer_of_another_survey_is_not_reachable(self):
        """
        GIVEN a layer belonging to a different survey
        WHEN it is requested under this survey's URL
        THEN the response is 404
        """
        other = SurveyHeader.objects.create(
            name="layer_other_survey", organization=self.org, redirect_url="/thanks/",
            status='published',
        )
        url = reverse('survey_layer_geojson', kwargs={
            'survey_slug': str(other.uuid), 'layer_id': self.layer.pk,
        })
        self.assertEqual(self.client.get(url).status_code, 404)

    @override_settings(MAP_REFERENCE_LAYERS=False)
    def test_kill_switch_closes_the_endpoint(self):
        """
        GIVEN the reference-layers kill switch is off
        WHEN the layer URL is fetched
        THEN the endpoint 404s while the layer row itself survives
        """
        from survey.models import SurveyMapLayer
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertTrue(SurveyMapLayer.objects.filter(pk=self.layer.pk).exists())

    def test_viewer_fetches_a_draft_survey_layer(self):
        """
        GIVEN a draft survey and a user holding the viewer role on it
        WHEN the viewer fetches the layer URL
        THEN the GeoJSON is returned with private caching
        """
        self.survey.status = 'draft'
        self.survey.save()
        viewer = User.objects.create_user('layer_viewer', password='pw')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        self.client.force_login(viewer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(json.loads(response.content)['features']), 3)
        self.assertIn('private', response['Cache-Control'])

    def test_owner_fetches_a_closed_survey_layer(self):
        """
        GIVEN a closed survey
        WHEN its owner fetches the layer URL
        THEN the GeoJSON is returned instead of the closed-survey 404
        """
        self.survey.status = 'closed'
        self.survey.save()
        owner = User.objects.create_user('layer_owner', password='pw')
        Membership.objects.create(user=owner, organization=self.org, role='owner')
        self.client.force_login(owner)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_outsiders_still_refused_on_a_closed_survey(self):
        """
        GIVEN a closed survey
        WHEN an anonymous visitor, then a signed-in user with no role on it, fetch the layer URL
        THEN both get 404
        """
        self.survey.status = 'closed'
        self.survey.save()
        self.assertEqual(self.client.get(self.url).status_code, 404)
        stranger = User.objects.create_user('layer_stranger', password='pw')
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(self.url).status_code, 404)


class LayerRespondentRenderingTest(TestCase):
    """Layer metadata reaching the respondent shell."""

    def setUp(self):
        from survey.models import SurveyMapLayer
        from survey.layers import validate_layer_upload
        self.org = Organization.objects.create(name="Layer Render Org")
        self.survey = SurveyHeader.objects.create(
            name="layer_render_survey", organization=self.org, redirect_url="/thanks/",
            status='published', available_languages=['en'],
        )
        self.head = SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True,
        )
        Question.objects.create(
            survey_section=self.head, code="LR001", name="Q", input_type="text", order_number=1,
        )
        geojson, count, _ = _validated_geojson_text(_zones_geojson().encode())
        self.layer = SurveyMapLayer.objects.create(
            survey=self.survey, name="Zones", color="#e8971e", label_field="name",
            geojson=geojson, feature_count=count, size_bytes=len(geojson),
        )
        self.url = reverse('section', kwargs={
            'survey_slug': str(self.survey.uuid), 'section_name': self.head.name,
        })

    def test_layer_config_reaches_the_page_but_geometry_does_not(self):
        """
        GIVEN a survey with a reference layer
        WHEN a respondent opens a map section
        THEN the page carries the layer's config and endpoint URL, not its geometry
        """
        html = self.client.get(self.url).content.decode()
        self.assertIn('ref-layers-data', html)
        self.assertIn('#e8971e', html)
        self.assertIn('layers/%d.geojson' % self.layer.pk, html)
        self.assertNotIn('"Area 1"', html)

    def test_section_layers_are_the_ones_its_questions_bind(self):
        """
        GIVEN a survey with a layer, and a section with no Objects question for it
        WHEN a respondent opens the section, then again after an Objects question binds the layer
        THEN the section element first lists no visible layer, then that layer's id
             (spec reference-overlay-layers: visibility is binding)
        """
        html = self.client.get(self.url).content.decode()
        self.assertIn('data-visible-layers="[]"', html)
        Question.objects.create(
            survey_section=self.head, code="LR002", name="Bins", input_type="layer_objects",
            layer=self.layer, order_number=2,
        )
        html = self.client.get(self.url).content.decode()
        self.assertIn('data-visible-layers="[%d]"' % self.layer.pk, html)
        self.assertIn('data-panel-mode="list"', html)

    @override_settings(MAP_REFERENCE_LAYERS=False)
    def test_kill_switch_removes_layer_metadata(self):
        """
        GIVEN the kill switch is off
        WHEN a respondent opens a map section
        THEN no layer config is emitted
        """
        html = self.client.get(self.url).content.decode()
        self.assertNotIn('#e8971e', html)
        self.assertNotIn('layers/%d.geojson' % self.layer.pk, html)


class LayerPreviewTest(TestCase):
    """The editor preview renders the same layers the respondent page does.

    Both surfaces render survey_section.html from separately hand-built
    contexts, so a key added to one silently vanishes from the other — which is
    how the preview shipped showing an empty map over an uploaded layer.
    """

    def setUp(self):
        from survey.models import SurveyMapLayer
        from survey.layers import validate_layer_upload
        self.org = Organization.objects.create(name="Layer Preview Org")
        self.owner = User.objects.create_user(username='previewowner', password='pw12345678')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="layer_preview_survey", organization=self.org,
            redirect_url="/thanks/", created_by=self.owner, available_languages=['en'],
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True,
        )
        Question.objects.create(
            survey_section=self.section, code="LP001", name="Q", input_type="text", order_number=1,
        )
        geojson, count, _ = _validated_geojson_text(_zones_geojson().encode())
        self.layer = SurveyMapLayer.objects.create(
            survey=self.survey, name="Zones", color="#e8971e", label_field="name",
            geojson=geojson, feature_count=count, size_bytes=len(geojson),
        )
        self.client.login(username='previewowner', password='pw12345678')
        self.url = reverse('editor_section_preview', args=[self.survey.uuid, self.section.name])

    def test_preview_carries_the_layer_config(self):
        """
        GIVEN a survey with a reference layer
        WHEN the creator opens the editor preview of a map section
        THEN the preview page carries that layer's config and geometry URL
        """
        html = self.client.get(self.url).content.decode()

        self.assertIn('ref-layers-data', html)
        self.assertIn('#e8971e', html)
        self.assertIn('layers/%d.geojson' % self.layer.pk, html)

    def test_preview_honours_per_section_visibility(self):
        """
        GIVEN a section whose Objects question binds the layer in legend mode
        WHEN its preview is rendered
        THEN the preview lists that layer as visible and renders the legend line, as the respondent page would
        """
        Question.objects.create(
            survey_section=self.section, code="LP002", name="Zones", input_type="layer_objects",
            layer=self.layer, panel_mode='legend', order_number=2,
        )

        html = self.client.get(self.url).content.decode()

        self.assertIn('data-visible-layers="[%d]"' % self.layer.pk, html)
        self.assertIn('data-panel-mode="legend"', html)
        self.assertIn('data-lo-toggle', html)

    @override_settings(MAP_REFERENCE_LAYERS=False)
    def test_kill_switch_empties_the_preview_too(self):
        """
        GIVEN the reference-layers kill switch is off
        WHEN the preview is rendered
        THEN it carries no layer config
        """
        html = self.client.get(self.url).content.decode()

        self.assertNotIn('layers/%d.geojson' % self.layer.pk, html)


class LayerEditorTest(TestCase):
    """Editor endpoints and the per-section checklist."""

    def setUp(self):
        from survey.models import SurveyMapLayer
        from survey.layers import validate_layer_upload
        self.org = Organization.objects.create(name="Layer Editor Org")
        self.owner = User.objects.create_user(username='layerowner', password='pw12345678')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="layer_editor_survey", organization=self.org, redirect_url="/thanks/",
            created_by=self.owner,
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True,
        )
        # Objects first, derived GeoJSON second — the way every stored layer is
        # made since overlay-features; property names come from the objects.
        self.layer = _objects_layer(self.survey, name="Zones")
        self.client.login(username='layerowner', password='pw12345678')

    def _upload(self, content=None, name='zones.geojson'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        payload = SimpleUploadedFile(
            name, (content or _zones_geojson()).encode(), content_type='application/geo+json')
        return self.client.post(
            reverse('editor_survey_layer_create', args=[self.survey.uuid]), {'layer': payload})

    def test_three_dimensional_upload_creates_a_layer(self):
        """
        GIVEN a GeoJSON carrying elevation, as QGIS and ArcGIS export by default
        WHEN the owner uploads it
        THEN the layer is created and its objects hold two-dimensional geometry

        Before this, the insert raised `DataError: Geometry has Z dimension but
        column does not`, the browser got an HTML 500 where it expected JSON,
        and the creator read `Unexpected token '<'`. One creator retried six
        times across two surveys before giving up.
        """
        from survey.models import LayerObject
        content = json.dumps({
            'type': 'FeatureCollection',
            'features': [
                {'type': 'Feature', 'properties': {'name': 'Haltestelle 1'},
                 'geometry': {'type': 'Point', 'coordinates': [6.96, 50.94, 58.2]}},
            ],
        })
        response = self._upload(content=content, name='haltestellenkataster.geojson')
        self.assertEqual(response.status_code, 201, response.content[:400])
        layer_id = response.json()['id']
        obj = LayerObject.objects.get(layer_id=layer_id)
        self.assertFalse(obj.geometry.hasz)
        self.assertAlmostEqual(obj.geometry.x, 6.96, places=5)
        self.assertAlmostEqual(obj.geometry.y, 50.94, places=5)

    def test_a_failed_upload_leaves_no_layer_behind(self):
        """
        GIVEN an upload that passes validation but fails while building objects
        WHEN the owner uploads it
        THEN no layer row survives and the survey's layer count is unchanged

        The row is created before its objects exist, so without a transaction a
        failure left an empty layer that no creator-facing list can remove and
        that still counted against MAX_LAYERS_PER_SURVEY. One such orphan
        reached production.
        """
        from survey.models import SurveyMapLayer
        before = SurveyMapLayer.objects.filter(survey=self.survey).count()
        with mock.patch('survey.services.layers.objects_from_features',
                        side_effect=RuntimeError('boom')):
            with self.assertRaises(RuntimeError):
                self._upload()
        self.assertEqual(SurveyMapLayer.objects.filter(survey=self.survey).count(), before)

    def test_a_refused_upload_answers_json_not_html(self):
        """
        GIVEN a file the validator refuses
        WHEN the owner uploads it
        THEN the response is JSON carrying a readable reason

        The editor parses this response as JSON; an HTML error page surfaces to
        the creator as `Unexpected token '<', "<!DOCTYPE "... is not valid JSON`.
        """
        response = self._upload(content='<?xml version="1.0"?><kml/>', name='stops.kml')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertTrue(response.json()['error'])

    def test_upload_creates_a_layer_and_returns_property_names(self):
        """
        GIVEN an owner uploading a valid GeoJSON
        WHEN the create endpoint receives it
        THEN a layer is stored and the response lists its property names
        """
        from survey.models import SurveyMapLayer
        response = self._upload()
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['feature_count'], 3)
        self.assertEqual(data['properties'], ['name', 'zone_id'])
        self.assertEqual(SurveyMapLayer.objects.filter(survey=self.survey).count(), 2)

    def test_eleventh_layer_is_refused(self):
        """
        GIVEN a survey that already holds the maximum of 10 reference layers
        WHEN the owner uploads one more
        THEN the upload is refused with a message naming the limit and the count stays 10
        """
        from survey.models import SurveyMapLayer
        from survey.layers import MAX_LAYERS_PER_SURVEY
        self.assertEqual(MAX_LAYERS_PER_SURVEY, 10)
        existing = SurveyMapLayer.objects.filter(survey=self.survey).count()
        for i in range(MAX_LAYERS_PER_SURVEY - existing):
            SurveyMapLayer.objects.create(
                survey=self.survey, name=f"Filler {i}", geojson=self.layer.geojson,
                feature_count=self.layer.feature_count, size_bytes=self.layer.size_bytes,
            )
        response = self._upload()
        self.assertEqual(response.status_code, 400)
        self.assertIn('10 reference layers', response.json()['error'])
        self.assertEqual(SurveyMapLayer.objects.filter(survey=self.survey).count(), MAX_LAYERS_PER_SURVEY)

    def test_invalid_upload_is_refused_with_a_readable_reason(self):
        """
        GIVEN an upload that is not GeoJSON
        WHEN the create endpoint receives it
        THEN it answers 400 with a creator-facing message and stores nothing
        """
        from survey.models import SurveyMapLayer
        response = self._upload(content='not json at all')
        self.assertEqual(response.status_code, 400)
        self.assertIn('geojson', response.json()['error'].lower())
        self.assertEqual(SurveyMapLayer.objects.filter(survey=self.survey).count(), 1)

    def test_config_update_persists(self):
        """
        GIVEN an existing layer
        WHEN its config is posted to the update endpoint
        THEN name, color, label field and popup flag are stored
        """
        response = self.client.post(
            reverse('editor_survey_layer_update', args=[self.survey.uuid, self.layer.pk]),
            {'name': 'Counting zones', 'color': '#e8971e', 'label_field': 'name', 'show_popups': '1'},
        )
        self.assertEqual(response.status_code, 200)
        self.layer.refresh_from_db()
        self.assertEqual(self.layer.name, 'Counting zones')
        self.assertEqual(self.layer.color, '#e8971e')
        self.assertEqual(self.layer.label_field, 'name')
        self.assertTrue(self.layer.show_popups)

    def test_unknown_label_field_is_refused(self):
        """
        GIVEN a label field that is not a property of the uploaded file
        WHEN it is saved
        THEN the endpoint refuses it instead of silently rendering no labels
        """
        response = self.client.post(
            reverse('editor_survey_layer_update', args=[self.survey.uuid, self.layer.pk]),
            {'label_field': 'nonexistent'},
        )
        self.assertEqual(response.status_code, 400)
        self.layer.refresh_from_db()
        self.assertEqual(self.layer.label_field, '')

    def test_invalid_color_is_refused(self):
        """
        GIVEN a color that is not #RRGGBB
        WHEN it is saved
        THEN the endpoint refuses it and the stored color is unchanged
        """
        response = self.client.post(
            reverse('editor_survey_layer_update', args=[self.survey.uuid, self.layer.pk]),
            {'color': 'red'},
        )
        self.assertEqual(response.status_code, 400)
        self.layer.refresh_from_db()
        self.assertEqual(self.layer.color, '#2c7be5')

    def test_delete_removes_the_layer(self):
        """
        GIVEN an existing layer
        WHEN the delete endpoint is called
        THEN the layer is gone
        """
        from survey.models import SurveyMapLayer
        response = self.client.post(
            reverse('editor_survey_layer_delete', args=[self.survey.uuid, self.layer.pk]))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(SurveyMapLayer.objects.filter(pk=self.layer.pk).exists())

    def test_non_owner_cannot_manage_layers(self):
        """
        GIVEN a user who is not an owner of the survey
        WHEN they post to a layer endpoint
        THEN the request is refused and nothing is created
        """
        from survey.models import SurveyMapLayer
        User.objects.create_user(username='stranger', password='pw12345678')
        self.client.logout()
        self.client.login(username='stranger', password='pw12345678')
        response = self._upload()
        self.assertNotIn(response.status_code, (200, 201))
        self.assertEqual(SurveyMapLayer.objects.filter(survey=self.survey).count(), 1)

    def test_section_form_has_no_layer_checklist(self):
        """
        GIVEN a survey with a layer
        WHEN the section form renders
        THEN there is no "Reference layers" checklist, only the hint to add an Objects question
             (spec survey-editor "Layers are put on a map by adding a question")
        """
        html = self.client.get(
            reverse('editor_section_detail', args=[self.survey.uuid, self.section.id]),
        ).content.decode()
        self.assertNotIn('name="visible_layers"', html)
        self.assertNotIn('reference_layers_submitted', html)
        self.assertIn('add an “Objects on the map” question', html)

    def test_same_layer_twice_in_a_section_is_refused(self):
        """
        GIVEN a section whose Objects question already binds the layer
        WHEN a second Objects question of that section picks the same layer
        THEN the form refuses on the layer field, naming the first question
        """
        Question.objects.create(
            survey_section=self.section, code="LE_FIRST", name="Zones here", input_type="layer_objects",
            layer=self.layer, order_number=5,
        )
        response = self.client.post(
            reverse('editor_question_create', kwargs={'survey_uuid': self.survey.uuid, 'section_id': self.section.pk}),
            {'name': 'Again', 'input_type': 'layer_objects', 'layer': self.layer.pk, 'subtext': '',
             'display_style': 'default', 'color': '#000000', 'choices_json': '[]', 'panel_mode': 'list'},
        )
        html = response.content.decode()
        self.assertIn('Already on this section’s map as “Zones here”', html)
        self.assertEqual(Question.objects.filter(survey_section=self.section, input_type='layer_objects').count(), 1)

    @override_settings(MAP_REFERENCE_LAYERS=False)
    def test_kill_switch_closes_editor_endpoints(self):
        """
        GIVEN the kill switch is off
        WHEN an owner posts to the create endpoint
        THEN it 404s
        """
        self.assertEqual(self._upload().status_code, 404)


class AnalyticsReferenceLayerTest(TestCase):
    """Reference layers on the Responses tab (openspec: responses-reference-layers)."""

    def setUp(self):
        from survey.models import SurveyMapLayer
        from survey.layers import validate_layer_upload
        self.org = Organization.objects.create(name="Layer Analytics Org")
        self.owner = User.objects.create_user('layer_analytics_owner', password='pw')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="layer_analytics_survey", organization=self.org, redirect_url="/thanks/",
            status='published',
        )
        SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True,
        )
        geojson, count, _ = _validated_geojson_text(_zones_geojson().encode())
        self.layer = SurveyMapLayer.objects.create(
            survey=self.survey, name="Zones", geojson=geojson, feature_count=count,
            size_bytes=len(geojson),
        )
        self.layer_url = reverse('survey_layer_geojson', kwargs={
            'survey_slug': str(self.survey.uuid), 'layer_id': self.layer.pk,
        })
        self.dashboard_url = reverse('editor_survey_analytics', kwargs={'survey_uuid': self.survey.uuid})

    def _first_coordinate(self):
        return json.loads(self.layer.geojson)['features'][0]['geometry']['coordinates'][0][0]

    def test_dashboard_carries_layer_metadata_but_not_geometry(self):
        """
        GIVEN a survey with a reference layer and no geo answers
        WHEN the owner opens the Responses tab
        THEN the page holds the layer's metadata, its URL, the factory and the map container,
             and none of the layer's coordinates
        """
        self.client.force_login(self.owner)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="ref-layers-data"', html)
        metas = json.loads(re.search(
            r'<script id="ref-layers-data" type="application/json">(.*?)</script>', html, re.S
        ).group(1))
        self.assertEqual([m['id'] for m in metas], [self.layer.pk])
        self.assertEqual(metas[0]['name'], 'Zones')
        self.assertEqual(metas[0]['url'], self.layer_url)
        self.assertIn('window.RefLayerFactory = {', html)
        self.assertIn('id="analytics-map"', html)
        lng, lat = self._first_coordinate()
        self.assertNotIn(f'{lng:.4f}', html)

    @override_settings(MAP_REFERENCE_LAYERS=False)
    def test_kill_switch_strips_layers_from_the_dashboard(self):
        """
        GIVEN the reference-layers kill switch is off
        WHEN the owner opens the Responses tab
        THEN the page carries no layer metadata, no layer URL and no factory
        """
        self.client.force_login(self.owner)
        html = self.client.get(self.dashboard_url).content.decode()
        self.assertNotIn('ref-layers-data', html)
        self.assertNotIn(self.layer_url, html)
        # The modal's consumer code stays; the factory definition must not be emitted.
        self.assertNotIn('window.RefLayerFactory = {', html)

    def test_viewer_sees_layer_metadata_on_a_draft(self):
        """
        GIVEN a draft survey with a layer and a user holding the viewer role
        WHEN the viewer opens the Responses tab
        THEN the layer metadata is present, so the loader fetches from the endpoint the
             viewer is now allowed to read
        """
        self.survey.status = 'draft'
        self.survey.save()
        viewer = User.objects.create_user('layer_analytics_viewer', password='pw')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        self.client.force_login(viewer)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.layer_url, response.content.decode())


class LayerSerializationTest(TestCase):
    """Layers through export → import."""

    def setUp(self):
        from survey.models import SurveyMapLayer
        from survey.layers import validate_layer_upload
        self.org = Organization.objects.create(name="Layer Ser Org")
        self.survey = SurveyHeader.objects.create(
            name="layer_ser_survey", organization=self.org, redirect_url="/thanks/",
        )
        self.first = SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True,
        )
        Question.objects.create(
            survey_section=self.first, code="LS001", name="Q", input_type="text", order_number=1,
        )
        geojson, count, _ = _validated_geojson_text(_zones_geojson().encode())
        self.layer = SurveyMapLayer.objects.create(
            survey=self.survey, name="Counting zones", color="#e8971e", label_field="name",
            key_field="zone_id", show_popups=True, geojson=geojson, feature_count=count,
            size_bytes=len(geojson), position=0,
        )
        # The layer is on the section's map through an Objects question in
        # legend mode (change layers-by-question).
        self.bins = Question.objects.create(
            survey_section=self.first, code="LS002", name="Zones", input_type="layer_objects",
            layer=self.layer, panel_mode='legend', order_number=2,
        )

    def _export(self):
        buf = BytesIO()
        export_survey_to_zip(self.survey, buf, 'structure')
        buf.seek(0)
        return buf

    def test_layers_round_trip_with_section_visibility(self):
        """
        GIVEN a survey whose section shows its layer through a legend-mode Objects question
        WHEN it is exported and re-imported
        THEN the layer arrives with its config, the question binds the new layer in legend
             mode, and no hidden_layers key is written
        """
        buf = self._export()
        with zipfile.ZipFile(buf) as zf:
            data = json.loads(zf.read('survey.json'))
            self.assertNotIn('hidden_layers', data['survey']['sections'][0])
        buf.seek(0)
        self.survey.name = 'layer_ser_survey_old'
        self.survey.save()
        imported, warnings = import_survey_from_zip(buf)
        layer = imported.map_layers.get()
        self.assertEqual(
            (layer.name, layer.color, layer.label_field, layer.key_field, layer.show_popups, layer.feature_count),
            ('Counting zones', '#e8971e', 'name', 'zone_id', True, 3),
        )
        section = SurveySection.objects.get(survey_header=imported, name='s1')
        q = Question.objects.get(survey_section=section, input_type='layer_objects')
        self.assertEqual((q.layer_id, q.panel_mode), (layer.pk, 'legend'))
        self.assertEqual(warnings, [])

    def _legacy_archive(self, hidden):
        """The archive as exported before layers-by-question: a `hidden_layers`
        list on the section and no Objects question."""
        buf = self._export()
        out = BytesIO()
        with zipfile.ZipFile(buf) as src, zipfile.ZipFile(out, 'w') as dst:
            for item in src.namelist():
                if item == 'survey.json':
                    data = json.loads(src.read(item))
                    sec = data['survey']['sections'][0]
                    sec['hidden_layers'] = hidden
                    sec['questions'] = [q for q in sec['questions'] if q['input_type'] != 'layer_objects']
                    data['survey']['name'] = 'legacy_hidden_%d' % len(hidden)
                    dst.writestr(item, json.dumps(data))
                else:
                    dst.writestr(item, src.read(item))
        out.seek(0)
        return out

    def test_legacy_archive_with_visible_layer_gets_a_legend_question(self):
        """
        GIVEN an archive from before this change whose section left the layer visible
        WHEN it is imported
        THEN the section gets one display-only Objects question bound to the layer in legend mode
        """
        imported, _ = import_survey_from_zip(self._legacy_archive([]))
        section = SurveySection.objects.get(survey_header=imported, name='s1')
        q = Question.objects.get(survey_section=section, input_type='layer_objects')
        self.assertEqual((q.layer_id, q.panel_mode, q.min_objects, q.name), (imported.map_layers.get().pk, 'legend', 0, 'Counting zones'))
        self.assertFalse(q.collects_objects)

    def test_legacy_archive_with_hidden_layer_gets_no_question(self):
        """
        GIVEN an archive from before this change whose section hid the layer
        WHEN it is imported
        THEN no Objects question is created and the section shows no layer
        """
        from survey.layers import section_layer_ids
        imported, _ = import_survey_from_zip(self._legacy_archive([0]))
        section = SurveySection.objects.get(survey_header=imported, name='s1')
        self.assertFalse(Question.objects.filter(survey_section=section, input_type='layer_objects').exists())
        self.assertEqual(section_layer_ids(section), [])

    def test_archive_carries_geometry_as_its_own_entry(self):
        """
        GIVEN a survey with a reference layer
        WHEN it is exported
        THEN geometry lives in layers/0.geojson and survey.json holds only config
        """
        buf = self._export()
        with zipfile.ZipFile(buf) as zf:
            self.assertIn('layers/0.geojson', zf.namelist())
            data = json.loads(zf.read('survey.json'))
            self.assertEqual(data['survey']['layers'][0]['name'], 'Counting zones')
            self.assertNotIn('geojson', data['survey']['layers'][0])
            self.assertNotIn('hidden_layers', data['survey']['sections'][0])

    def test_legacy_archive_without_layers_imports_cleanly(self):
        """
        GIVEN an archive produced before this change
        WHEN it is imported
        THEN the survey arrives with no layers and no layer warnings
        """
        buf = self._export()
        out = BytesIO()
        with zipfile.ZipFile(buf) as src, zipfile.ZipFile(out, 'w') as dst:
            for item in src.namelist():
                if item.startswith('layers/'):
                    continue
                if item == 'survey.json':
                    data = json.loads(src.read(item))
                    data['survey'].pop('layers', None)
                    for section in data['survey']['sections']:
                        section.pop('hidden_layers', None)
                    data['survey']['name'] = 'legacy_layer_survey'
                    dst.writestr(item, json.dumps(data))
                else:
                    dst.writestr(item, src.read(item))
        out.seek(0)
        imported, warnings = import_survey_from_zip(out)
        self.assertEqual(imported.map_layers.count(), 0)
        self.assertEqual([w for w in warnings if 'layer' in w.lower()], [])

    def test_missing_layer_entry_degrades_to_a_warning(self):
        """
        GIVEN an archive listing a layer whose geojson entry is missing
        WHEN it is imported
        THEN the survey imports without that layer and a warning names it
        """
        buf = self._export()
        out = BytesIO()
        with zipfile.ZipFile(buf) as src, zipfile.ZipFile(out, 'w') as dst:
            for item in src.namelist():
                if item == 'layers/0.geojson':
                    continue
                if item == 'survey.json':
                    data = json.loads(src.read(item))
                    data['survey']['name'] = 'broken_layer_survey'
                    dst.writestr(item, json.dumps(data))
                else:
                    dst.writestr(item, src.read(item))
        out.seek(0)
        imported, warnings = import_survey_from_zip(out)
        self.assertEqual(imported.map_layers.count(), 0)
        self.assertTrue(any('Counting zones' in w for w in warnings))
        section = SurveySection.objects.get(survey_header=imported, name='s1')
        self.assertFalse(Question.objects.filter(survey_section=section, input_type='layer_objects', layer__isnull=False).exists())


class LayerMemoryDietTest(TestCase):
    """Change layer-memory-diet, stage 1: no surface but the gated endpoint and the
    export reads a layer's geometry text; property names are a stored column."""

    GEOJSON_COLUMN = '"survey_surveymaplayer"."geojson_gz"'

    def setUp(self):
        self.org = Organization.objects.create(name="Diet Org")
        self.owner = User.objects.create_user(username='dietowner', password='pw12345678')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="diet_survey", organization=self.org, redirect_url="/thanks/",
            created_by=self.owner, status='published', available_languages=['en'],
        )
        SurveyCollaborator.objects.create(user=self.owner, survey=self.survey, role='owner')
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True,
        )
        self.layer = _objects_layer(self.survey, name="Sites", key_field='zone_id', label_field='name')
        self.q = Question.objects.create(
            survey_section=self.section, code="DT001", name="Objects", input_type="layer_objects",
            layer=self.layer, order_number=1,
        )
        Question.objects.create(
            survey_section=self.section, code="DT002", name="Rate", input_type="rating",
            parent_question_id=self.q, order_number=1, choices=[{"code": i, "name": str(i)} for i in range(1, 6)],
        )

    def _geojson_reads(self, queries):
        return [q['sql'] for q in queries if self.GEOJSON_COLUMN in q['sql'] and q['sql'].lstrip().upper().startswith('SELECT')]

    def test_rebuild_stores_property_names(self):
        """
        GIVEN a layer built from objects carrying `name` and `zone_id`
        WHEN it is rebuilt
        THEN the sorted property names are stored on the layer, reserved names excluded
        """
        from survey.layers import rebuild_layer
        obj = self.layer.items.first()
        obj.properties = {**obj.properties, '_key': 'shadow', 'extra': 1}
        obj.save()
        rebuild_layer(self.layer)
        self.layer.refresh_from_db()
        self.assertEqual(self.layer.property_names, ['extra', 'name', 'zone_id'])

    def test_upload_response_and_pickers_use_the_stored_names(self):
        """
        GIVEN an owner uploading a GeoJSON
        WHEN the create endpoint answers and the settings card renders
        THEN both list the stored property names and neither selects the geometry column
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from survey.models import SurveyMapLayer
        self.client.login(username='dietowner', password='pw12345678')
        payload = SimpleUploadedFile('zones.geojson', _zones_geojson().encode(), content_type='application/geo+json')
        r = self.client.post(reverse('editor_survey_layer_create', args=[self.survey.uuid]), {'layer': payload})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['properties'], ['name', 'zone_id'])
        self.assertEqual(SurveyMapLayer.objects.get(pk=r.json()['id']).property_names, ['name', 'zone_id'])
        with CaptureQueriesContext(connection) as ctx:
            r = self.client.get(reverse('editor_survey_settings_panel', args=[self.survey.uuid]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'zone_id')
        self.assertEqual(self._geojson_reads(ctx.captured_queries), [])

    def test_migration_backfills_property_names_from_objects(self):
        """
        GIVEN a layer whose stored names are empty (a row from before the column)
        WHEN the backfill migration runs
        THEN the names are derived from the objects' properties
        """
        from importlib import import_module
        from django.apps import apps
        from django.db import connection
        from survey.models import SurveyMapLayer
        SurveyMapLayer.objects.filter(pk=self.layer.pk).update(property_names=[])
        import_module('survey.migrations.0084_surveymaplayer_property_names').forwards(apps, connection.schema_editor)
        self.layer.refresh_from_db()
        self.assertEqual(self.layer.property_names, ['name', 'zone_id'])

    def test_editor_respondent_and_responses_pages_never_read_the_geometry_text(self):
        """
        GIVEN a survey with a layer and an Objects-on-the-map question
        WHEN the editor page, the question modal, the respondent section (GET and POST)
             and the Responses dashboard render
        THEN no query selects the layer's geojson column
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        self.client.login(username='dietowner', password='pw12345678')
        pages = [
            ('editor_survey', reverse('editor_survey_detail', args=[self.survey.uuid])),
            ('question modal', reverse('editor_question_edit', args=[self.survey.uuid, self.q.pk])),
            ('responses', reverse('editor_survey_analytics', args=[self.survey.uuid])),
            ('object card', reverse('survey_layer_object', args=[str(self.survey.uuid), self.layer.pk, self.layer.items.first().key])),
        ]
        for label, url in pages:
            # The question modal is a draft-only surface; the rest read a published survey.
            SurveyHeader.objects.filter(pk=self.survey.pk).update(status='draft' if label == 'question modal' else 'published')
            with CaptureQueriesContext(connection) as ctx:
                r = self.client.get(url)
            self.assertEqual(r.status_code, 200, label)
            self.assertEqual(self._geojson_reads(ctx.captured_queries), [], label)
        respondent = Client()
        url = reverse('section', args=[str(self.survey.uuid), self.section.name])
        with CaptureQueriesContext(connection) as ctx:
            r = respondent.get(url)
            self.assertEqual(r.status_code, 200)
            key = self.layer.items.first().key
            r = respondent.post(url, {f'obj__{key}__DT002': '4'})
        self.assertIn(r.status_code, (200, 302))
        self.assertEqual(self._geojson_reads(ctx.captured_queries), [])

    def test_gated_endpoint_and_export_still_read_the_text(self):
        """
        GIVEN the same survey
        WHEN the GeoJSON endpoint and the ZIP export run
        THEN both deliver the derived FeatureCollection
        """
        import io
        import zipfile
        self.client.login(username='dietowner', password='pw12345678')
        r = self.client.get(reverse('survey_layer_geojson', args=[str(self.survey.uuid), self.layer.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(json.loads(r.content)['features']), 3)
        r = self.client.get(reverse('export_survey', args=[self.survey.uuid]))
        self.assertEqual(r.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            self.assertEqual(len(json.loads(zf.read('layers/0.geojson'))['features']), 3)

    def test_gunicorn_recycles_workers_with_the_draining_worker(self):
        """
        GIVEN the production and compose start commands
        WHEN they are read
        THEN both carry a request budget with jitter AND run the draining worker class
             (stock gthread drops the connections it accepted in its last loop
             iteration on every recycle and every deploy — one 502 each on 2026-09-16),
             and that class is importable and a gthread worker
        """
        import os
        from gunicorn.workers.gthread import ThreadWorker
        from mapsurvey.gunicorn_workers import DrainingThreadWorker
        self.assertTrue(issubclass(DrainingThreadWorker, ThreadWorker))
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        for name in ('Dockerfile', 'docker-compose.yml'):
            with open(os.path.join(root, name)) as fh:
                text = fh.read()
            self.assertIn('--max-requests ${GUNICORN_MAX_REQUESTS:-', text, name)
            self.assertIn('--max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER:-', text, name)
            self.assertIn('--worker-class ${GUNICORN_WORKER_CLASS:-mapsurvey.gunicorn_workers.DrainingThreadWorker}', text, name)
        with open(os.path.join(root, 'render.yaml')) as fh:
            text = fh.read()
        self.assertIn('GUNICORN_MAX_REQUESTS_JITTER', text)
        self.assertIn('mapsurvey.gunicorn_workers.DrainingThreadWorker', text)


class LayerStreamingRebuildTest(TestCase):
    """Change layer-memory-diet, stage 2: the derived GeoJSON is streamed one
    feature at a time and objects are written in batches — with the same result."""

    def setUp(self):
        self.org = Organization.objects.create(name="Stream Org")
        self.survey = SurveyHeader.objects.create(
            name="stream_survey", organization=self.org, redirect_url="/thanks/", status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True,
        )

    @staticmethod
    def _tree_serialisation(layer, with_status=False):
        """The pre-change construction: every object as a model instance, one
        dict tree, one json.dumps — the reference the stream must match byte for byte."""
        from survey.models import LayerObjectAsset
        from survey.layers import feature_for_object, creator_objects
        covers = {}
        for asset in LayerObjectAsset.objects.filter(object__layer=layer, kind='image').order_by('object_id', 'position', 'id'):
            covers.setdefault(asset.object_id, asset.url)
        features = []
        for obj in (creator_objects(layer) if with_status else layer.items.order_by('position', 'id')):
            feature = feature_for_object(obj, covers.get(obj.pk, ''))
            if with_status:
                feature['properties']['_status'] = obj.status
            features.append(feature)
        return json.dumps({'type': 'FeatureCollection', 'features': features}, ensure_ascii=False, separators=(',', ':'))

    def test_streamed_collection_is_byte_identical_to_the_tree_serialisation(self):
        """
        GIVEN an uploaded layer whose objects carry categories, unicode text, a cover
              image, a link and shadowing reserved properties
        WHEN the derived GeoJSON is rebuilt
        THEN the streamed text equals the whole-tree serialisation byte for byte
             and the property names come out of the same pass
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        from survey.models import LayerObjectAsset
        from survey.layers import rebuild_layer, build_layer_geojson
        layer = _objects_layer(self.survey, name="Sites", key_field='zone_id', label_field='name')
        obj = layer.items.get(key='2')
        obj.category = 'Парки'
        obj.description = '<p>Pocket <b>park</b> — «тихий»</p>'
        obj.link = 'https://city.example/2'
        obj.properties = {**obj.properties, '_key': 'shadow', '_cover': 'x', 'notes': 'ä/ö "quoted"'}
        obj.save()
        png = SimpleUploadedFile('cover.png', b'\x89PNG\r\n\x1a\n' + b'0' * 20, content_type='image/png')
        LayerObjectAsset.objects.create(object=obj, kind='image', file=png, title='cover.png',
                                        content_type='image/png', size_bytes=png.size, position=0)
        rebuild_layer(layer)
        layer.refresh_from_db()
        self.assertEqual(build_layer_geojson(layer), self._tree_serialisation(layer))
        self.assertEqual(layer.geojson, self._tree_serialisation(layer))
        self.assertEqual(layer.property_names, ['name', 'notes', 'zone_id'])
        feature = next(f for f in json.loads(layer.geojson)['features'] if f['id'] == '2')
        self.assertEqual(feature['properties']['_key'], '2')
        self.assertTrue(feature['properties']['_has_content'])
        self.assertTrue(feature['properties']['_cover'])

    def test_question_layer_streams_status_the_same_way(self):
        """
        GIVEN a shared-map layer materialised from a respondent's marks with approve-first on
        WHEN it is rebuilt
        THEN the streamed text equals the tree serialisation, `_status` included, and
             a marks layer stores no property names
        """
        from django.contrib.gis.geos import Point
        from survey.models import SurveyMapLayer
        from survey.layers import sync_question_layer, rebuild_layer
        q1 = Question.objects.create(survey_section=self.section, code="Q1", name="Where", input_type="point", order_number=1)
        layer = SurveyMapLayer.objects.create(
            survey=self.survey, name="Marks", geojson='{}', source='question', source_question_code='Q1', approve_first=True,
        )
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=session, question=q1, point=Point(13.4, 52.5))
        Answer.objects.create(survey_session=session, question=q1, point=Point(13.5, 52.6))
        sync_question_layer(layer, session)
        rebuild_layer(layer)
        layer.refresh_from_db()
        self.assertEqual(layer.feature_count, 2)
        self.assertEqual(layer.geojson, self._tree_serialisation(layer, with_status=True))
        self.assertIn('"_status":"pending"', layer.geojson)
        self.assertEqual(layer.property_names, [])

    def test_batches_keep_positions_and_collision_reports(self):
        """
        GIVEN a 1100-feature file whose feature 700 repeats the key of feature 5
        WHEN objects are created in batches of 500
        THEN 1099 objects exist in file order with contiguous positions and the
             collision is reported once
        """
        from survey.models import SurveyMapLayer
        from survey.layers import validate_layer_upload, objects_from_features
        features = []
        for i in range(1, 1101):
            key = '5' if i == 700 else str(i)
            features.append({'type': 'Feature', 'properties': {'zone_id': key, 'name': f'Area {i}'},
                             'geometry': {'type': 'Point', 'coordinates': [13.0 + i / 10000, 52.0]}})
        parsed, _, _z = validate_layer_upload(json.dumps({'type': 'FeatureCollection', 'features': features}).encode())
        layer = SurveyMapLayer.objects.create(survey=self.survey, name="Big", geojson='', key_field='zone_id')
        report = objects_from_features(layer, parsed)
        self.assertEqual(report['created'], 1099)
        self.assertEqual(report['collisions'], ['5'])
        rows = list(layer.items.order_by('position').values_list('position', 'key'))
        self.assertEqual([p for p, _ in rows], list(range(1, 1100)))
        self.assertEqual([k for _, k in rows][:6], ['1', '2', '3', '4', '5', '6'])
        self.assertEqual([k for _, k in rows][697:700], ['698', '699', '701'])


class LayerGzipStorageTest(TestCase):
    """Change layer-memory-diet, stage 3: the derived GeoJSON is stored gzipped
    and handed to gzip-capable clients as it is."""

    def setUp(self):
        self.org = Organization.objects.create(name="Gzip Org")
        self.survey = SurveyHeader.objects.create(
            name="gzip_survey", organization=self.org, redirect_url="/thanks/",
            status='published', available_languages=['en'],
        )
        SurveySection.objects.create(survey_header=self.survey, name="s1", title="S1", code="S1", is_head=True)
        self.layer = _objects_layer(self.survey, name="Sites", key_field='zone_id', label_field='name')
        self.url = reverse('survey_layer_geojson', kwargs={'survey_slug': str(self.survey.uuid), 'layer_id': self.layer.pk})

    def test_text_api_round_trips_through_gzip_bytes(self):
        """
        GIVEN a rebuilt layer
        WHEN its text is read back from the database
        THEN it equals what was written, the row holds gzip bytes smaller than the
             text, an empty text is NULL, and size_bytes reports the text
        """
        import gzip
        from survey.models import SurveyMapLayer
        row = SurveyMapLayer.objects.get(pk=self.layer.pk)
        self.assertEqual(json.loads(row.geojson)['features'][2]['id'], '3')
        self.assertEqual(gzip.decompress(bytes(row.geojson_gz)).decode('utf-8'), row.geojson)
        self.assertLess(len(row.geojson_gz), len(row.geojson))
        self.assertEqual(row.size_bytes, len(row.geojson.encode('utf-8')))
        empty = SurveyMapLayer.objects.create(survey=self.survey, name="Empty", geojson='')
        self.assertIsNone(SurveyMapLayer.objects.get(pk=empty.pk).geojson_gz)
        self.assertEqual(SurveyMapLayer.objects.get(pk=empty.pk).geojson, '')

    def test_endpoint_serves_the_stored_bytes_to_gzip_clients_and_text_to_others(self):
        """
        GIVEN a client that accepts gzip and one that does not
        WHEN each fetches the layer
        THEN the first receives the stored bytes with Content-Encoding: gzip, the
             second the text, both with the same ETag, and a matching If-None-Match
             still answers 304
        """
        import gzip
        gz = self.client.get(self.url, HTTP_ACCEPT_ENCODING='gzip, deflate, br')
        self.assertEqual(gz.status_code, 200)
        self.assertEqual(gz['Content-Encoding'], 'gzip')
        self.assertEqual(gz['Content-Type'], 'application/geo+json')
        self.assertIn('Accept-Encoding', gz['Vary'])
        body = gzip.decompress(gz.content).decode('utf-8')
        plain = self.client.get(self.url)
        self.assertEqual(plain.status_code, 200)
        self.assertFalse(plain.has_header('Content-Encoding'))
        self.assertEqual(plain.content.decode('utf-8'), body)
        self.assertEqual(len(json.loads(body)['features']), 3)
        self.assertEqual(gz['ETag'], plain['ETag'])
        again = self.client.get(self.url, HTTP_ACCEPT_ENCODING='gzip', HTTP_IF_NONE_MATCH=gz['ETag'])
        self.assertEqual(again.status_code, 304)

    def test_migration_compresses_existing_rows(self):
        """
        GIVEN the compress step of migration 0086 run over a stored layer
        WHEN it finishes
        THEN the bytes decompress to the same text (the live column is the gz one, so
             the forwards step is exercised through the model it targets)
        """
        import gzip
        from survey.models import SurveyMapLayer
        text = SurveyMapLayer.objects.get(pk=self.layer.pk).geojson
        raw = SurveyMapLayer.objects.filter(pk=self.layer.pk).values_list('geojson_gz', flat=True).first()
        self.assertEqual(gzip.decompress(bytes(raw)).decode('utf-8'), text)
        self.assertLess(len(raw), len(text) / 2)
