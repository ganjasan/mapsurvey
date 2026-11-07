"""Tests for the `map-style-import-export` capability (change map-styles-import-export, #544).

The portable document, export from the library, import with validation and name
suffixing, and the Pro rules around both.
"""
import json
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from billing.tests.helpers import make_sub, trial_used_elsewhere
from survey.map_styles import io as style_io
from survey.map_styles import tasks as style_tasks
from survey.models import MapStyle, MapStyleVersion, Membership
from survey.tests.helpers import _make_org
from survey.tests.test_map_style_library import ready_style


def _doc(**overrides):
    doc = {'format': style_io.FORMAT, 'version': 1, 'name': 'House style', 'base': 'mapbox/streets-v12',
           'settings': {'poi': False, 'park': '#cfe6b8', 'water': '#2f8f86'}}
    doc.update(overrides)
    return doc


def _file(doc, name='style.json'):
    body = doc if isinstance(doc, bytes) else json.dumps(doc).encode()
    return SimpleUploadedFile(name, body, content_type='application/json')


class _IoFixture(TestCase):
    def setUp(self):
        self.org = _make_org('IoOrg')
        self.owner = User.objects.create_user('ioowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        make_sub(self.org)
        self.style = ready_style(self.org, name='House style', mapbox_id='artemkonuchov/abc',
                                 settings={'poi': False, 'park': '#cfe6b8'})
        self.client.login(username='ioowner', password='pass')
        self.import_url = reverse('org_map_style_import', args=[self.org.slug])

    def export(self, uuid):
        return self.client.get(reverse('org_map_style_export', args=[self.org.slug, uuid]))


class ExportTest(_IoFixture):
    """Spec: map-style-import-export / Requirement: The export is one self-contained JSON document."""

    def test_export_of_a_workspace_style(self):
        """
        GIVEN a Pro workspace's style whose latest version has park #cfe6b8 and a Mapbox id
        WHEN an editor exports it
        THEN the attachment carries format, version 1, name, base and the settings, and never the Mapbox id
        """
        response = self.export(self.style.uuid)
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment; filename="mapsurvey-style-house-style.json"', response['Content-Disposition'])
        doc = json.loads(response.content)
        self.assertEqual((doc['format'], doc['version'], doc['name'], doc['base']),
                         (style_io.FORMAT, 1, 'House style', 'mapbox/streets-v12'))
        self.assertEqual(doc['settings']['park'], '#cfe6b8')
        self.assertNotIn('artemkonuchov/abc', response.content.decode())
        self.assertNotIn('uuid', doc)
        self.assertNotIn(str(self.style.uuid), response.content.decode())

    def test_export_of_presets(self):
        """
        GIVEN the presets
        WHEN Paper A and Satellite are exported
        THEN Paper A downloads with preset: paper and Satellite answers 404
        """
        paper = MapStyle.objects.get(organization__isnull=True, key='paper')
        satellite = MapStyle.objects.get(organization__isnull=True, key='satellite')
        doc = json.loads(self.export(paper.uuid).content)
        self.assertEqual(doc['preset'], 'paper')
        self.assertFalse(doc['settings'].get('poi', True))
        self.assertEqual(self.export(satellite.uuid).status_code, 404)

    def test_viewer_cannot_export(self):
        """
        GIVEN a member with the viewer role
        WHEN they request an export
        THEN the response is 403
        """
        viewer = User.objects.create_user('ioviewer', password='pass')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        self.client.login(username='ioviewer', password='pass')
        self.assertEqual(self.export(self.style.uuid).status_code, 403)


class ImportTest(_IoFixture):
    """Spec: map-style-import-export / Requirement: Import creates a workspace style from a valid document."""

    def test_round_trip(self):
        """
        GIVEN an exported style
        WHEN the file is imported into another workspace
        THEN that workspace has a new style of the same name, version 1 pending with the same settings,
             the publish task is enqueued and the event is emitted
        """
        exported = self.export(self.style.uuid).content
        other = _make_org('IoOther')
        Membership.objects.create(user=self.owner, organization=other, role='owner')
        make_sub(other, ppg_subscription_id='954875')
        with mock.patch.object(style_tasks.publish_map_style_version, 'delay') as delay, \
                self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('org_map_style_import', args=[other.slug]), {'file': _file(exported)})
        self.assertEqual(response.status_code, 302)
        style = MapStyle.objects.get(organization=other)
        self.assertEqual(style.name, 'House style')
        version = style.versions.get()
        self.assertEqual((version.number, version.status), (1, MapStyleVersion.PENDING))
        from survey.map_styles import controls
        normalised, _errors = controls.clean_settings(controls.form_values(self.style.latest_ready().settings))
        self.assertEqual(version.settings, normalised)
        self.assertIs(version.settings['poi'], False)
        self.assertEqual(version.settings['park'], '#cfe6b8')
        delay.assert_called_once_with(version.pk)

    def test_name_taken(self):
        """
        GIVEN a workspace that already has "House style"
        WHEN a document named "House style" is imported
        THEN the new style is "House style (2)", and a third import "House style (3)"
        """
        with mock.patch.object(style_tasks.publish_map_style_version, 'delay'):
            self.client.post(self.import_url, {'file': _file(_doc())})
            self.client.post(self.import_url, {'file': _file(_doc())})
        names = sorted(MapStyle.objects.filter(organization=self.org).values_list('name', flat=True))
        self.assertEqual(names, ['House style', 'House style (2)', 'House style (3)'])

    def test_unknown_keys_dropped_bad_colours_refused(self):
        """
        GIVEN a document with a layers key and a bad water colour, then one with only the layers key
        WHEN they are imported
        THEN the first is refused naming water, the second imports without layers
        """
        bad = _doc(settings={'layers': [{'id': 'x'}], 'water': 'blue'})
        response = self.client.post(self.import_url, {'file': _file(bad)}, follow=True)
        self.assertContains(response, 'water')
        self.assertEqual(MapStyle.objects.filter(organization=self.org).count(), 1)
        ok = _doc(name='Clean', settings={'layers': [{'id': 'x'}], 'park': '#dcefd2'})
        with mock.patch.object(style_tasks.publish_map_style_version, 'delay'):
            self.client.post(self.import_url, {'file': _file(ok)})
        version = MapStyle.objects.get(organization=self.org, name='Clean').versions.get()
        self.assertNotIn('layers', version.settings)
        self.assertEqual(version.settings['park'], '#dcefd2')

    def test_wrong_format_or_version(self):
        """
        GIVEN a non-JSON file, a document of another format and a version-2 document
        WHEN they are imported
        THEN nothing is created and the page names the reason
        """
        cases = (
            (_file(b'not json'), 'not a Mapsurvey map style'),
            (_file({'format': 'something-else', 'version': 1}), 'not a Mapsurvey map style'),
            (_file(_doc(version=2)), 'newer Mapsurvey'),
        )
        for upload, needle in cases:
            response = self.client.post(self.import_url, {'file': upload}, follow=True)
            self.assertContains(response, needle)
        self.assertEqual(MapStyle.objects.filter(organization=self.org).count(), 1)

    def test_unsupported_base_and_missing_name(self):
        """
        GIVEN documents with an unsupported base and with no name
        WHEN they are imported
        THEN both are refused with the reason
        """
        response = self.client.post(self.import_url, {'file': _file(_doc(base='mapbox/outdoors-v12'))}, follow=True)
        self.assertContains(response, 'not supported')
        response = self.client.post(self.import_url, {'file': _file(_doc(name=''))}, follow=True)
        self.assertContains(response, 'no name')
        self.assertEqual(MapStyle.objects.filter(organization=self.org).count(), 1)

    def test_free_workspace_with_spent_trial(self):
        """
        GIVEN a Free workspace whose map_styles allowance is spent
        WHEN an import is posted
        THEN the Pro-required page answers and nothing is created
        """
        from billing.models import Subscription
        Subscription.objects.filter(organization=self.org).delete()
        trial_used_elsewhere(self.org)
        response = self.client.post(self.import_url, {'file': _file(_doc(name='Blocked'))})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(MapStyle.objects.filter(organization=self.org, name='Blocked').exists())

    def test_viewer_cannot_import(self):
        """
        GIVEN a member with the viewer role
        WHEN they post an import
        THEN the response is 403
        """
        viewer = User.objects.create_user('ioviewer2', password='pass')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        self.client.login(username='ioviewer2', password='pass')
        self.assertEqual(self.client.post(self.import_url, {'file': _file(_doc())}).status_code, 403)

    def test_library_page_offers_import_and_export(self):
        """
        GIVEN the library page for an editor
        WHEN it renders
        THEN it has the import form and Export on the workspace style, Paper A and Streets but not Satellite
        """
        html = self.client.get(reverse('org_map_styles', args=[self.org.slug])).content.decode()
        self.assertIn(self.import_url, html)
        self.assertIn(f'/map-styles/{self.style.uuid}/export.json', html)
        for key, expected in (('paper', True), ('streets', True), ('satellite', False), ('topo', False)):
            uuid = MapStyle.objects.get(organization__isnull=True, key=key).uuid
            self.assertEqual(f'/map-styles/{uuid}/export.json' in html, expected, key)
