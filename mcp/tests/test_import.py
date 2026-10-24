"""`mcp-server`: import is a job on the private tier, parsed by the worker."""
from unittest import mock

from django.test import TestCase, override_settings

from survey.models import SurveyHeader, SurveyImportJob
from survey.tasks import run_survey_import

from .helpers import (
    LOCMEM, MCP_SETTINGS, McpClient, data_of, error_of, make_member, make_pro_org, make_v1_survey,
    minimal_survey_json, mint,
)


@LOCMEM
@MCP_SETTINGS
class ImportTest(TestCase):
    def setUp(self):
        self.org, self.owner = make_pro_org()
        make_v1_survey(self.org, self.owner)
        self.mcp = McpClient(self.client, mint(self.owner)[0])

    def test_import_returns_a_job_the_worker_finishes(self):
        """
        GIVEN a valid survey.json document
        WHEN import_survey is called with the task run inline
        THEN the result is a queued job on the private tier; afterwards the job is done, the survey exists
             and the archive is deleted
        """
        with mock.patch('mcp.tools.imports.run_survey_import.delay') as delay:
            data = data_of(self.mcp.call('import_survey', {'survey_json': minimal_survey_json('From MCP')}))
        self.assertEqual(data['status'], 'queued')
        job = SurveyImportJob.objects.get(pk=data['id'])
        delay.assert_called_once_with(job.pk)
        self.assertTrue(job.file.name.startswith('import_jobs/'))
        self.assertEqual(job.organization, self.org)
        self.assertEqual(job.user, self.owner)
        run_survey_import(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, 'done', job.error)
        self.assertEqual(SurveyHeader.objects.get(pk=job.survey_id).name, 'From MCP')
        self.assertFalse(job.file)
        polled = data_of(self.mcp.call('get_import_job', {'job_id': job.pk}))
        self.assertEqual(polled['status'], 'done')
        self.assertEqual(polled['survey'], str(job.survey.uuid))

    @override_settings(MCP_IMPORT_MAX_BYTES=100)
    def test_oversized_document_is_refused_before_anything_is_stored(self):
        """
        GIVEN a cap of 100 bytes
        WHEN import_survey is called
        THEN validation on survey_json and no job exists
        """
        with mock.patch('mcp.tools.imports.run_survey_import.delay') as delay:
            envelope = error_of(self.mcp.call('import_survey', {'survey_json': minimal_survey_json()}))
        self.assertEqual(envelope['error'], 'validation')
        self.assertIn('survey_json', envelope['fields'])
        self.assertFalse(SurveyImportJob.objects.exists())
        delay.assert_not_called()

    def test_someone_elses_job_is_not_found(self):
        """
        GIVEN a job of another member
        WHEN get_import_job names it
        THEN not_found
        """
        other = make_member(self.org, 'other_member')
        job = SurveyImportJob.objects.create(user=other, organization=self.org, original_name='x.zip')
        self.assertEqual(error_of(self.mcp.call('get_import_job', {'job_id': job.pk}))['error'], 'not_found')
