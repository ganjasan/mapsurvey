"""Tests for the `uuid-survey-identification` capability (openspec/specs/uuid-survey-identification/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from io import BytesIO
import json
import zipfile
from survey.models import Organization, SurveyHeader, SurveySection
from survey.serialization import import_survey_from_zip, ImportError, FORMAT_VERSION


class UUIDSurveyIdentificationTest(TestCase):
    """Tests for UUID-based survey identification and dual-lookup behavior."""

    def setUp(self):
        self.client = Client()
        self.org = Organization.objects.create(name="UUID Test Org")
        self.survey = SurveyHeader.objects.create(
            name="unique_survey",
            organization=self.org,
            status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="section1",
            title="Test Section",
            code="S1",
            is_head=True,
        )

    def test_two_surveys_with_same_name_can_coexist(self):
        """
        GIVEN the name field no longer has unique constraint
        WHEN two surveys are created with the same name
        THEN both exist in the database with different UUIDs
        """
        survey_a = SurveyHeader.objects.create(name="same_name", organization=self.org)
        survey_b = SurveyHeader.objects.create(name="same_name", organization=self.org)

        self.assertEqual(SurveyHeader.objects.filter(name="same_name").count(), 2)
        self.assertNotEqual(survey_a.uuid, survey_b.uuid)

    def test_public_url_with_unique_name_resolves(self):
        """
        GIVEN a survey with a unique name
        WHEN accessing the public URL with that name
        THEN the survey resolves correctly
        """
        response = self.client.get('/surveys/unique_survey/')
        self.assertEqual(response.status_code, 302)  # redirects to section

    def test_public_url_with_ambiguous_name_returns_404(self):
        """
        GIVEN two surveys with the same name
        WHEN accessing the public URL with that name
        THEN the server returns 404
        """
        SurveyHeader.objects.create(name="ambiguous", organization=self.org, status='published')
        SurveyHeader.objects.create(name="ambiguous", organization=self.org, status='published')

        response = self.client.get('/surveys/ambiguous/')
        self.assertEqual(response.status_code, 404)

    def test_public_url_with_uuid_resolves(self):
        """
        GIVEN a survey with a UUID
        WHEN accessing the public URL with that UUID as slug
        THEN the survey resolves correctly
        """
        response = self.client.get(f'/surveys/{self.survey.uuid}/')
        self.assertEqual(response.status_code, 302)  # redirects to section

    def test_public_url_with_uuid_resolves_ambiguous_name(self):
        """
        GIVEN two surveys with the same name
        WHEN accessing the public URL with one survey's UUID
        THEN the correct survey resolves
        """
        survey_a = SurveyHeader.objects.create(name="dup_name", organization=self.org, status='published')
        SurveySection.objects.create(
            survey_header=survey_a, name="sec1", code="SA", is_head=True,
        )
        survey_b = SurveyHeader.objects.create(name="dup_name", organization=self.org, status='published')
        SurveySection.objects.create(
            survey_header=survey_b, name="sec1", code="SB", is_head=True,
        )

        response_a = self.client.get(f'/surveys/{survey_a.uuid}/')
        self.assertEqual(response_a.status_code, 302)

        response_b = self.client.get(f'/surveys/{survey_b.uuid}/')
        self.assertEqual(response_b.status_code, 302)

    def test_import_survey_with_duplicate_name_succeeds(self):
        """
        GIVEN a survey with name 'unique_survey' already exists
        WHEN importing a ZIP with the same survey name
        THEN the import succeeds and both surveys coexist
        """
        survey_data = {
            "version": FORMAT_VERSION,
            "survey": {
                "name": "unique_survey",
                "sections": [
                    {
                        "name": "imported_sec",
                        "code": "IS",
                        "is_head": True,
                        "questions": []
                    }
                ]
            },
            "option_groups": []
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_data))
        import_buffer.seek(0)

        result_survey, warnings = import_survey_from_zip(import_buffer)

        self.assertEqual(result_survey.name, "unique_survey")
        self.assertEqual(SurveyHeader.objects.filter(name="unique_survey").count(), 2)
        self.assertNotEqual(result_survey.uuid, self.survey.uuid)

    def test_data_only_import_ambiguous_name_raises_error(self):
        """
        GIVEN two surveys with the same name
        WHEN data-only import references that ambiguous name
        THEN it raises ImportError
        """
        SurveyHeader.objects.create(name="unique_survey", organization=self.org)
        # Now there are two surveys named "unique_survey"

        responses_data = {
            "version": FORMAT_VERSION,
            "exported_at": "2024-01-01T12:00:00Z",
            "survey_name": "unique_survey",
            "sessions": []
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("responses.json", json.dumps(responses_data))
        import_buffer.seek(0)

        with self.assertRaises(ImportError) as context:
            import_survey_from_zip(import_buffer)
        self.assertIn("Multiple surveys", str(context.exception))

    def test_survey_has_uuid_auto_generated(self):
        """
        GIVEN a new survey created without specifying uuid
        WHEN the survey is saved
        THEN it has a non-null UUID automatically assigned
        """
        survey = SurveyHeader.objects.create(name="auto_uuid_test", organization=self.org)
        self.assertIsNotNone(survey.uuid)

    def test_survey_uuid_is_unique(self):
        """
        GIVEN multiple surveys
        WHEN checking their UUIDs
        THEN all UUIDs are distinct
        """
        surveys = [SurveyHeader.objects.create(name=f"uuid_test_{i}", organization=self.org) for i in range(5)]
        uuids = [s.uuid for s in surveys]
        self.assertEqual(len(uuids), len(set(uuids)))
