"""Spec: data-upload (change data-upload, #668, epic #676).

A file becomes a workspace dataset through a background job: formats, reprojection, the report,
private columns, limits.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from data.models import DataImportJob, Dataset
from survey.models import LayerObject, Membership

from .helpers import _make_org


def _eager():
    from data.tasks import run_data_import
    return patch('data.tasks.run_data_import.delay', side_effect=lambda job_id: run_data_import(job_id))


class _UploadFixture(TestCase):
    def setUp(self):
        self.org = _make_org('UpOrg')
        self.owner = User.objects.create_user('upowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.client.force_login(self.owner)
        s = self.client.session
        s['active_org_id'] = self.org.id
        s.save()

    def upload(self, name, content):
        with _eager():
            return self.client.post('/editor/data/upload/', {'file': SimpleUploadedFile(name, content)})

    def job(self):
        return DataImportJob.objects.get(organization=self.org)


class FormatsTest(_UploadFixture):
    """Requirement: A file becomes a workspace dataset in one step."""

    def test_csv_with_eastings_and_northings(self):
        """
        GIVEN a CSV with easting/northing columns in British National Grid
        WHEN it is uploaded
        THEN a private workspace dataset holds points at the matching WGS 84 positions
        """
        csv_text = 'TREE_ID,SPECIES,easting,northing\nT1,Lime,530000,180000\nT2,Oak,530100,180100\n'
        self.upload('trees.csv', csv_text.encode())
        job = self.job()
        self.assertEqual(job.status, 'done', job.error)
        self.assertIn('27700', job.report['crs'])
        ds = job.dataset
        self.assertEqual((ds.kind, ds.privacy_class), ('layer', 'private'))
        self.assertIsNone(ds.layer.survey_id)
        self.assertEqual(ds.layer.organization_id, self.org.id)
        pt = LayerObject.objects.get(layer=ds.layer, key='t1').geometry   # keys are slugified
        self.assertAlmostEqual(pt.x, -0.13, delta=0.01)
        self.assertAlmostEqual(pt.y, 51.51, delta=0.01)
        self.assertFalse(job.file)

    def test_csv_with_latitude_longitude(self):
        """
        GIVEN a CSV with latitude/longitude columns
        WHEN it is uploaded
        THEN its points keep their coordinates
        """
        self.upload('stops.csv', b'name,latitude,longitude\nA,59.9,30.3\n')
        job = self.job()
        self.assertEqual(job.status, 'done', job.error)
        pt = job.dataset.layer.items.get().geometry
        self.assertAlmostEqual(pt.x, 30.3, places=4)

    def test_unknown_projected_csv_is_refused(self):
        """
        GIVEN a CSV whose coordinates fit neither lon/lat nor the British National Grid
        WHEN it is uploaded
        THEN the job fails with a message asking for WGS 84
        """
        self.upload('utm.csv', b'id,x,y\n1,4500000,5600000\n')
        job = self.job()
        self.assertEqual(job.status, 'failed')
        self.assertIn('WGS 84', job.error)

    @unittest.skipUnless(shutil.which('ogr2ogr'), 'needs ogr2ogr to build the fixture')
    def test_geopackage_in_a_national_grid_is_reprojected(self):
        """
        GIVEN a GeoPackage whose layer is in EPSG:27700
        WHEN it is uploaded
        THEN its object lies at the matching WGS 84 position
        """
        tmp = tempfile.mkdtemp()
        try:
            src = os.path.join(tmp, 'in.geojson')
            with open(src, 'w') as fh:
                json.dump({'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {'id': 'A'},
                           'geometry': {'type': 'Point', 'coordinates': [530000, 180000]}}]}, fh)
            out = os.path.join(tmp, 'out.gpkg')
            subprocess.run(['ogr2ogr', '-f', 'GPKG', '-a_srs', 'EPSG:27700', out, src], check=True,
                           capture_output=True)
            with open(out, 'rb') as fh:
                self.upload('register.gpkg', fh.read())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        job = self.job()
        self.assertEqual(job.status, 'done', job.error)
        pt = job.dataset.layer.items.get().geometry
        self.assertAlmostEqual(pt.x, -0.13, delta=0.01)
        self.assertAlmostEqual(pt.y, 51.51, delta=0.01)


class SyncDuringImportTest(_UploadFixture):
    """Regression (found on the dev server): a catalogue load syncing the registry while the import
    runs must not make the job fail on the one-dataset-per-layer constraint."""

    def test_sync_in_the_middle_of_an_import(self):
        """
        GIVEN an import during which the registry is synced (as a polling catalogue would)
        WHEN the import finishes
        THEN the job is done and the layer has exactly one dataset, private, with its fields
        """
        from data.datasets import sync
        from survey import layers
        real = layers.rebuild_layer

        def rebuild_and_sync(layer):
            out = real(layer)
            sync(self.org)
            return out

        with patch('survey.layers.rebuild_layer', side_effect=rebuild_and_sync):
            self.upload('stops.csv', b'name,latitude,longitude,email\nA,59.9,30.3,x@y.org\n')
        job = self.job()
        self.assertEqual(job.status, 'done', job.error)
        rows = Dataset.objects.filter(layer=job.dataset.layer)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.get().privacy_class, 'private')
        self.assertTrue(rows.get().fields)


class ReportTest(_UploadFixture):
    """Requirements: the report lists problems without failing; personal columns are private."""

    def test_rows_without_a_location_are_skipped_and_reported(self):
        """
        GIVEN a CSV with 10 rows of which 2 have empty coordinates
        WHEN it is uploaded
        THEN 8 objects are created and the report counts 2 rows without a location
        """
        rows = ['id,latitude,longitude'] + [f'{i},59.{i},30.{i}' for i in range(8)] + ['8,,', '9,,']
        self.upload('pts.csv', '\n'.join(rows).encode())
        job = self.job()
        self.assertEqual(job.status, 'done', job.error)
        self.assertEqual(job.report['created'], 8)
        self.assertEqual(job.report['no_location'], 2)

    def test_an_inspectors_email_column_is_private(self):
        """
        GIVEN a column INSP_EMAIL holding email addresses
        WHEN the file is uploaded
        THEN the field dictionary marks it private and the report names it
        """
        self.upload('t.csv', b'id,latitude,longitude,INSP_EMAIL\n1,59.9,30.3,a@b.org\n2,59.8,30.2,c@d.org\n')
        job = self.job()
        fields = {f['name']: f for f in job.dataset.fields}
        self.assertTrue(fields['INSP_EMAIL']['private'])
        self.assertFalse(fields['id']['private'])
        self.assertEqual(job.report['private_fields'], ['INSP_EMAIL'])


class PrivateOnArrivalTest(_UploadFixture):
    """Regression (found by the data-api tests): the import rebuilt the layer's cached GeoJSON
    before the dataset row with its field dictionary existed, so private columns were cached."""

    def test_cached_geojson_has_no_private_column_after_upload(self):
        """
        GIVEN a CSV with an email column
        WHEN it is uploaded
        THEN the layer's cached GeoJSON carries neither the column nor its values
        """
        self.upload('t.csv', b'id,latitude,longitude,INSP_EMAIL\n1,59.9,30.3,a@b.org\n')
        layer = self.job().dataset.layer
        layer.refresh_from_db()
        self.assertNotIn('INSP_EMAIL', layer.geojson)
        self.assertNotIn('a@b.org', layer.geojson)
        self.assertNotIn('INSP_EMAIL', layer.property_names)


class LimitsAndVisibilityTest(_UploadFixture):
    """Requirements: uploads respect the workspace's limits; workspace datasets for every member."""

    def test_too_large_for_free_is_refused_before_any_job(self):
        """
        GIVEN a Free workspace
        WHEN a 12 MB file is uploaded
        THEN no job is created and the message names the 10 MB limit
        """
        response = self.client.post('/editor/data/upload/',
                                    {'file': SimpleUploadedFile('big.csv', b'0' * (12 * 1024 * 1024))}, follow=True)
        self.assertFalse(DataImportJob.objects.exists())
        self.assertContains(response, '10 MB')

    def test_every_member_sees_an_upload(self):
        """
        GIVEN an owner's upload
        WHEN a workspace editor opens the catalogue
        THEN the editor sees the dataset, labelled Uploaded
        """
        self.upload('stops.csv', b'name,latitude,longitude\nA,59.9,30.3\n')
        editor = User.objects.create_user('upeditor', password='pass')
        Membership.objects.create(user=editor, organization=self.org, role='editor')
        self.client.force_login(editor)
        s = self.client.session
        s['active_org_id'] = self.org.id
        s.save()
        html = self.client.get('/editor/data/').content.decode()
        self.assertIn('<strong>stops</strong>', html)
        self.assertIn('Uploaded', html)
        self.assertEqual(Dataset.objects.filter(organization=self.org, kind='layer').count(), 1)
