"""Spec: data-versions (change data-versions, #671, epic #676).

A new version of a layer dataset is matched by key and previewed before saving; applying it updates
objects in place so their answers survive, and every consumer shows it; versions have a history.
"""
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from api.tests.helpers import make_pro_org, make_v1_survey
from data.models import DataImportJob, Dataset, DatasetVersion
from survey.models import Answer, LayerObject, Question, SurveySession

V1 = b'TREE_ID,SPECIES,HEIGHT,latitude,longitude\nT1,Lime,10,51.50,-0.12\nT2,Oak,8,51.51,-0.13\nT3,Ash,6,51.52,-0.14\n'
V2 = b'TREE_ID,SPECIES,HEIGHT,latitude,longitude\nT1,Lime,12,51.50,-0.12\nT2,Oak,8,51.51,-0.13\nT4,Elm,3,51.53,-0.15\n'


def _eager():
    from data.tasks import run_data_import, run_data_version
    return (patch('data.tasks.run_data_import.delay', side_effect=lambda job_id: run_data_import(job_id)),
            patch('data.tasks.run_data_version.delay',
                  side_effect=lambda job_id, apply=False: run_data_version(job_id, apply)))


class _VersionFixture(TestCase):
    """A Pro workspace whose owner uploaded trees T1–T3 keyed on TREE_ID."""

    def setUp(self):
        self.org, self.owner = make_pro_org('VerOrg', 'verowner')
        self.client.force_login(self.owner)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        self.p1, self.p2 = _eager()
        self.p1.start()
        self.p2.start()
        self.addCleanup(self.p1.stop)
        self.addCleanup(self.p2.stop)
        self.client.post('/editor/data/upload/', {'file': SimpleUploadedFile('trees.csv', V1)})
        self.dataset = DataImportJob.objects.get(target__isnull=True).dataset
        self.layer = self.dataset.layer
        self.page = reverse('editor_data_dataset', args=[self.dataset.pk])

    def upload_version(self, content=V2):
        self.client.post(self.page, {'action': 'version', 'file': SimpleUploadedFile('trees-2027.csv', content)})
        return DataImportJob.objects.filter(target=self.dataset).latest('created_at')

    def apply(self, job, note='Spring 2027 inspection'):
        self.client.post(self.page, {'action': 'apply', 'job': job.pk, 'note': note})
        job.refresh_from_db()
        return job


class PreviewTest(_VersionFixture):
    """Requirement: A new version is previewed before it is saved."""

    def test_preview_counts(self):
        """
        GIVEN trees T1, T2, T3
        WHEN a file with T1 changed, T2 unchanged and T4 new is uploaded as a new version
        THEN the preview reads 1 added, 1 changed, 1 removed, 1 unchanged and nothing changed yet
        """
        self.assertEqual(self.layer.key_field, 'TREE_ID')
        job = self.upload_version()
        self.assertEqual(job.status, 'preview', job.error)
        r = job.report
        self.assertEqual((r['added'], r['changed'], r['removed'], r['unchanged']), (1, 1, 1, 1))
        self.assertEqual(sorted(self.layer.items.values_list('key', flat=True)), ['t1', 't2', 't3'])
        self.assertTrue(job.file)
        html = self.client.get(self.page).content.decode()
        self.assertIn('1 added · 1 changed · 1 removed · 1 unchanged', html)

    def test_dataset_without_a_key_field(self):
        """
        GIVEN the dataset's layer has no key field
        WHEN a new version is uploaded
        THEN the job fails asking for a key column
        """
        type(self.layer).objects.filter(pk=self.layer.pk).update(key_field='')
        job = self.upload_version()
        self.assertEqual(job.status, 'failed')
        self.assertIn('key', job.error)


class ApplyTest(_VersionFixture):
    """Requirement: Applying a version updates objects in place."""

    def test_answers_survive(self):
        """
        GIVEN a respondent's answer attached to tree T1
        WHEN a version changing T1's height is applied
        THEN the answer still points at T1, which carries the new height, and T3 is gone
        """
        survey, section = make_v1_survey(self.org, self.owner, name='Trees survey', status='published')
        objects_q = Question.objects.create(survey_section=section, code='OBJ', name='Trees',
                                            input_type='layer_objects', layer=self.layer)
        sub = Question.objects.create(survey_section=section, code='OK', name='Healthy?', input_type='text',
                                      parent_question_id=objects_q)
        t1 = LayerObject.objects.get(layer=self.layer, key='t1')
        session = SurveySession.objects.create(survey=survey)
        answer = Answer.objects.create(survey_session=session, question=sub, layer_object=t1, text='yes')
        job = self.upload_version()
        self.assertEqual(job.report['removed_answers'], 0)
        job = self.apply(job)
        self.assertEqual(job.status, 'done', job.error)
        answer.refresh_from_db()
        self.assertEqual(answer.layer_object_id, t1.pk)
        t1.refresh_from_db()
        self.assertEqual(str(t1.properties['HEIGHT']), '12')
        self.assertEqual(sorted(self.layer.items.values_list('key', flat=True)), ['t1', 't2', 't4'])
        self.assertFalse(job.file)

    def test_every_consumer_shows_the_new_version(self):
        """
        GIVEN the dataset is public and linked into a survey
        WHEN a version is applied
        THEN the survey's layer GeoJSON carries the new tree and not the removed one
        """
        survey, _s = make_v1_survey(self.org, self.owner, name='Linked survey', status='published')
        Dataset.objects.filter(pk=self.dataset.pk).update(privacy_class='public')
        self.client.post(reverse('editor_survey_layer_link', args=[survey.uuid]), {'dataset': self.dataset.pk})
        self.apply(self.upload_version())
        url = reverse('survey_layer_geojson', kwargs={'survey_slug': str(survey.uuid), 'layer_id': self.layer.pk})
        body = self.client.get(url).content.decode()
        self.assertIn('Elm', body)
        self.assertNotIn('Ash', body)

    def test_above_a_survey_maps_limit_while_linked(self):
        """
        GIVEN the dataset is linked into a survey
        WHEN the new version has more than 5,000 objects
        THEN the job fails naming the limit and the dataset is unchanged
        """
        survey, _s = make_v1_survey(self.org, self.owner, name='Linked survey', status='published')
        Dataset.objects.filter(pk=self.dataset.pk).update(privacy_class='public')
        self.client.post(reverse('editor_survey_layer_link', args=[survey.uuid]), {'dataset': self.dataset.pk})
        rows = ['TREE_ID,latitude,longitude'] + [f'X{i},51.{i % 90:02d},-0.{i % 90:02d}' for i in range(5001)]
        job = self.upload_version('\n'.join(rows).encode())
        self.assertEqual(job.status, 'failed')
        self.assertIn('5000', job.error.replace(',', ''))
        self.assertEqual(self.layer.items.count(), 3)


class HistoryTest(_VersionFixture):
    """Requirement: Versions have a history."""

    def test_history(self):
        """
        GIVEN a dataset uploaded once
        WHEN a version is applied with the note "Spring 2027 inspection"
        THEN the page lists version 2 with that note and its author, and version 1 as the first upload
        """
        self.apply(self.upload_version())
        self.assertEqual(list(DatasetVersion.objects.filter(dataset=self.dataset).values_list('number', flat=True)), [2, 1])
        html = self.client.get(self.page).content.decode()
        row = html.split('data-version="2"')[1].split('</tr>')[0]
        self.assertIn('Spring 2027 inspection', row)
        self.assertIn(self.owner.get_full_name() or self.owner.username, row)
        self.assertIn('First upload', html.split('data-version="1"')[1].split('</tr>')[0])
