"""Tests for the `survey-serialization` capability (openspec/specs/survey-serialization/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point, LineString, Polygon
from django.urls import reverse
from django.utils import timezone
from io import BytesIO
from unittest.mock import patch
import json
import uuid
import zipfile
from survey.models import Organization, SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership, SurveyCollaborator
from survey.serialization import serialize_survey_to_dict, serialize_sections, serialize_questions, serialize_sessions, serialize_answers, geo_to_wkt, serialize_choices, export_survey_to_zip, validate_archive, import_survey_from_zip, ImportError, FORMAT_VERSION
from survey.models import SurveySectionTranslation, QuestionTranslation
import os
import tempfile
from django.core.management import call_command
from survey.tests.helpers import _eager_import, _make_org


class StructureSerializationTest(TestCase):
    """Tests for survey structure serialization."""

    def setUp(self):
        """Set up test data for structure serialization tests."""
        self.org = Organization.objects.create(name="Test Org")
        self.survey = SurveyHeader.objects.create(
            name="test_survey",
            organization=self.org,
            redirect_url="/thanks/"
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="section_one",
            title="First Section",
            subheading="Introduction",
            code="S1",
            is_head=True,
            start_map_postion=Point(30.5, 60.0),
            start_map_zoom=14
        )
        self.yes_no_choices = [
            {"code": 1, "name": {"en": "Yes", "ru": "Да"}},
            {"code": 0, "name": {"en": "No", "ru": "Нет"}},
        ]
        self.question = Question.objects.create(
            survey_section=self.section,
            code="Q001",
            order_number=1,
            name="Do you agree?",
            input_type="choice",
            choices=self.yes_no_choices,
            required=True
        )

    def test_serialize_survey_to_dict(self):
        """
        GIVEN a survey with organization
        WHEN serialize_survey_to_dict is called
        THEN it returns dict with name, organization, redirect_url, and sections
        """
        result = serialize_survey_to_dict(self.survey)

        self.assertEqual(result["name"], "test_survey")
        self.assertEqual(result["organization"], "Test Org")
        self.assertEqual(result["redirect_url"], "/thanks/")
        self.assertIn("sections", result)
        self.assertEqual(len(result["sections"]), 1)

    def test_serialize_question_with_inline_choices(self):
        """
        GIVEN a question with inline choices
        WHEN serialize_questions is called
        THEN the question includes choices array
        """
        result = serialize_questions(self.section)

        self.assertEqual(len(result), 1)
        question = result[0]
        self.assertIsNotNone(question["choices"])
        self.assertEqual(len(question["choices"]), 2)
        codes = [c["code"] for c in question["choices"]]
        self.assertIn(1, codes)
        self.assertIn(0, codes)

    def test_serialize_sections_with_geo(self):
        """
        GIVEN a survey section with geo point
        WHEN serialize_sections is called
        THEN it returns sections with WKT geo coordinates
        """
        result = serialize_sections(self.survey)

        self.assertEqual(len(result), 1)
        section = result[0]
        self.assertEqual(section["name"], "section_one")
        self.assertEqual(section["title"], "First Section")
        self.assertEqual(section["is_head"], True)
        self.assertIn("POINT", section["start_map_position"])
        self.assertEqual(section["start_map_zoom"], 14)

    def test_serialize_questions_with_hierarchy(self):
        """
        GIVEN a question with sub-questions
        WHEN serialize_questions is called
        THEN it returns questions with nested sub_questions
        """
        sub_question = Question.objects.create(
            survey_section=self.section,
            parent_question_id=self.question,
            code="Q001_1",
            order_number=1,
            name="Why do you agree?",
            input_type="text"
        )

        result = serialize_questions(self.section)

        self.assertEqual(len(result), 1)
        parent_q = result[0]
        self.assertEqual(parent_q["code"], "Q001")
        self.assertEqual(len(parent_q["sub_questions"]), 1)
        self.assertEqual(parent_q["sub_questions"][0]["code"], "Q001_1")

    def test_serialize_question_fields(self):
        """
        GIVEN a question with all fields populated
        WHEN serializing questions
        THEN all fields are included in the output
        """
        result = serialize_questions(self.section)

        question = result[0]
        self.assertEqual(question["code"], "Q001")
        self.assertEqual(question["order_number"], 1)
        self.assertEqual(question["name"], "Do you agree?")
        self.assertEqual(question["input_type"], "choice")
        self.assertIsNotNone(question["choices"])
        self.assertEqual(question["required"], True)


class DataSerializationTest(TestCase):
    """Tests for survey data serialization (sessions, answers, geo, choices)."""

    def setUp(self):
        """Set up test data for data serialization tests."""
        self.org = _make_org()
        self.survey = SurveyHeader.objects.create(name="data_test_survey", organization=self.org)
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="section_data",
            code="SD",
            is_head=True
        )
        self.rating_choices = [
            {"code": 1, "name": "Poor"},
            {"code": 5, "name": "Excellent"},
        ]
        self.text_question = Question.objects.create(
            survey_section=self.section,
            code="Q_TEXT",
            name="Your feedback",
            input_type="text"
        )
        self.choice_question = Question.objects.create(
            survey_section=self.section,
            code="Q_CHOICE",
            name="Rate us",
            input_type="choice",
            choices=self.rating_choices
        )
        self.point_question = Question.objects.create(
            survey_section=self.section,
            code="Q_POINT",
            name="Mark location",
            input_type="point"
        )
        self.line_question = Question.objects.create(
            survey_section=self.section,
            code="Q_LINE",
            name="Draw route",
            input_type="line"
        )
        self.polygon_question = Question.objects.create(
            survey_section=self.section,
            code="Q_POLY",
            name="Draw area",
            input_type="polygon"
        )
        self.session = SurveySession.objects.create(survey=self.survey)

    def test_serialize_sessions(self):
        """
        GIVEN a survey with sessions
        WHEN serialize_sessions is called
        THEN it returns list of sessions with datetime and answers
        """
        result = serialize_sessions(self.survey)

        self.assertEqual(len(result), 1)
        self.assertIn("start_datetime", result[0])
        self.assertIn("end_datetime", result[0])
        self.assertIn("answers", result[0])

    def test_session_timing_rides_the_archive(self):
        """
        GIVEN a session with last_activity_at set
        WHEN it is serialized and re-created from that data
        THEN last_activity_at survives the round trip, and a session without it inherits end_datetime
        """
        from datetime import timedelta
        from django.utils import timezone
        from survey.serialization import create_session
        seen = timezone.now() - timedelta(minutes=5)
        SurveySession.objects.filter(pk=self.session.pk).update(last_activity_at=seen)
        data = serialize_sessions(self.survey)[0]
        self.assertEqual(data["last_activity_at"], seen.isoformat())
        copy = create_session(self.survey, data)
        self.assertEqual(copy.last_activity_at, seen)
        done = timezone.now() - timedelta(minutes=1)
        legacy = create_session(self.survey, {"start_datetime": data["start_datetime"], "end_datetime": done.isoformat()})
        self.assertEqual(legacy.last_activity_at, done)

    def test_serialize_answers_with_text(self):
        """
        GIVEN a session with text answer
        WHEN serialize_answers is called
        THEN it returns answers with text field populated
        """
        answer = Answer.objects.create(
            survey_session=self.session,
            question=self.text_question,
            text="Great service!"
        )

        result = serialize_answers(self.session)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["question_code"], "Q_TEXT")
        self.assertEqual(result[0]["text"], "Great service!")

    def test_serialize_answers_with_choices(self):
        """
        GIVEN a session with choice answer
        WHEN serialize_answers is called
        THEN it returns answers with choice names
        """
        answer = Answer.objects.create(
            survey_session=self.session,
            question=self.choice_question,
            selected_choices=[5]
        )

        result = serialize_answers(self.session)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["question_code"], "Q_CHOICE")
        self.assertIn("Excellent", result[0]["choices"])

    def test_geo_to_wkt_point(self):
        """
        GIVEN a Point geometry
        WHEN geo_to_wkt is called
        THEN it returns WKT string representation
        """
        point = Point(30.5, 60.0)
        result = geo_to_wkt(point)

        self.assertIn("POINT", result)
        self.assertIn("30.5", result)
        self.assertIn("60", result)

    def test_geo_to_wkt_line(self):
        """
        GIVEN a LineString geometry
        WHEN geo_to_wkt is called
        THEN it returns WKT string representation
        """
        line = LineString((0, 0), (1, 1), (2, 2))
        result = geo_to_wkt(line)

        self.assertIn("LINESTRING", result)

    def test_geo_to_wkt_polygon(self):
        """
        GIVEN a Polygon geometry
        WHEN geo_to_wkt is called
        THEN it returns WKT string representation
        """
        polygon = Polygon(((0, 0), (0, 1), (1, 1), (1, 0), (0, 0)))
        result = geo_to_wkt(polygon)

        self.assertIn("POLYGON", result)

    def test_geo_to_wkt_none(self):
        """
        GIVEN None value
        WHEN geo_to_wkt is called
        THEN it returns None
        """
        result = geo_to_wkt(None)
        self.assertIsNone(result)

    def test_serialize_answers_with_geo(self):
        """
        GIVEN a session with geo answers (point, line, polygon)
        WHEN serialize_answers is called
        THEN it returns answers with WKT strings
        """
        Answer.objects.create(
            survey_session=self.session,
            question=self.point_question,
            point=Point(30.5, 60.0)
        )
        Answer.objects.create(
            survey_session=self.session,
            question=self.line_question,
            line=LineString((0, 0), (1, 1))
        )
        Answer.objects.create(
            survey_session=self.session,
            question=self.polygon_question,
            polygon=Polygon(((0, 0), (0, 1), (1, 1), (1, 0), (0, 0)))
        )

        result = serialize_answers(self.session)

        self.assertEqual(len(result), 3)
        point_answer = next(a for a in result if a["question_code"] == "Q_POINT")
        line_answer = next(a for a in result if a["question_code"] == "Q_LINE")
        poly_answer = next(a for a in result if a["question_code"] == "Q_POLY")

        self.assertIn("POINT", point_answer["point"])
        self.assertIn("LINESTRING", line_answer["line"])
        self.assertIn("POLYGON", poly_answer["polygon"])

    def test_serialize_answers_with_hierarchy(self):
        """
        GIVEN a parent answer with sub-answers
        WHEN serialize_answers is called
        THEN it returns answers with nested sub_answers
        """
        sub_question = Question.objects.create(
            survey_section=self.section,
            parent_question_id=self.text_question,
            code="Q_TEXT_SUB",
            name="More details",
            input_type="text"
        )
        parent_answer = Answer.objects.create(
            survey_session=self.session,
            question=self.text_question,
            text="Main feedback"
        )
        sub_answer = Answer.objects.create(
            survey_session=self.session,
            question=sub_question,
            parent_answer_id=parent_answer,
            text="Additional details"
        )

        result = serialize_answers(self.session)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "Main feedback")
        self.assertEqual(len(result[0]["sub_answers"]), 1)
        self.assertEqual(result[0]["sub_answers"][0]["text"], "Additional details")

    def test_serialize_choices(self):
        """
        GIVEN an answer with multiple selected choices
        WHEN serialize_choices is called
        THEN it returns list of choice names
        """
        answer = Answer.objects.create(
            survey_session=self.session,
            question=self.choice_question,
            selected_choices=[1, 5]
        )

        result = serialize_choices(answer)

        self.assertEqual(len(result), 2)
        self.assertIn("Poor", result)
        self.assertIn("Excellent", result)


class ZipCreationTest(TestCase):
    """Tests for ZIP archive creation with all modes."""

    def setUp(self):
        """Set up test data for ZIP creation tests."""
        self.org = _make_org()
        self.survey = SurveyHeader.objects.create(name="zip_test_survey", organization=self.org)
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="zip_section",
            code="ZS",
            is_head=True
        )
        self.question = Question.objects.create(
            survey_section=self.section,
            code="Q_ZIP",
            name="Test question",
            input_type="text"
        )
        self.session = SurveySession.objects.create(survey=self.survey)
        self.answer = Answer.objects.create(
            survey_session=self.session,
            question=self.question,
            text="Test response"
        )

    def test_export_structure_mode(self):
        """
        GIVEN a survey with structure
        WHEN export_survey_to_zip is called with mode=structure
        THEN it creates ZIP with survey.json only, no responses.json
        """
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")

        output.seek(0)
        with zipfile.ZipFile(output, 'r') as zf:
            names = zf.namelist()
            self.assertIn("survey.json", names)
            self.assertNotIn("responses.json", names)

            survey_data = json.loads(zf.read("survey.json"))
            self.assertEqual(survey_data["version"], FORMAT_VERSION)
            self.assertEqual(survey_data["mode"], "structure")
            self.assertEqual(survey_data["survey"]["name"], "zip_test_survey")

    def test_export_data_mode(self):
        """
        GIVEN a survey with responses
        WHEN export_survey_to_zip is called with mode=data
        THEN it creates ZIP with responses.json only, no survey.json
        """
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="data")

        output.seek(0)
        with zipfile.ZipFile(output, 'r') as zf:
            names = zf.namelist()
            self.assertNotIn("survey.json", names)
            self.assertIn("responses.json", names)

            responses_data = json.loads(zf.read("responses.json"))
            self.assertEqual(responses_data["version"], FORMAT_VERSION)
            self.assertEqual(responses_data["survey_name"], "zip_test_survey")
            self.assertEqual(len(responses_data["sessions"]), 1)

    def test_export_full_mode(self):
        """
        GIVEN a survey with structure and responses
        WHEN export_survey_to_zip is called with mode=full
        THEN it creates ZIP with both survey.json and responses.json
        """
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="full")

        output.seek(0)
        with zipfile.ZipFile(output, 'r') as zf:
            names = zf.namelist()
            self.assertIn("survey.json", names)
            self.assertIn("responses.json", names)

            survey_data = json.loads(zf.read("survey.json"))
            self.assertEqual(survey_data["mode"], "full")

    def test_export_default_mode_is_structure(self):
        """
        GIVEN a survey
        WHEN export_survey_to_zip is called without mode
        THEN it defaults to structure mode
        """
        output = BytesIO()
        export_survey_to_zip(self.survey, output)

        output.seek(0)
        with zipfile.ZipFile(output, 'r') as zf:
            names = zf.namelist()
            self.assertIn("survey.json", names)
            self.assertNotIn("responses.json", names)

    def test_export_includes_inline_choices(self):
        """
        GIVEN a survey with questions using inline choices
        WHEN export_survey_to_zip is called
        THEN the survey.json includes choices in questions
        """
        self.question.choices = [{"code": 1, "name": "A"}, {"code": 2, "name": "B"}]
        self.question.input_type = "choice"
        self.question.save()

        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")

        output.seek(0)
        with zipfile.ZipFile(output, 'r') as zf:
            survey_data = json.loads(zf.read("survey.json"))
            questions = survey_data["survey"]["sections"][0]["questions"]
            self.assertEqual(len(questions[0]["choices"]), 2)

    def test_export_includes_exported_at(self):
        """
        GIVEN a survey
        WHEN export_survey_to_zip is called
        THEN the JSON includes exported_at timestamp
        """
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")

        output.seek(0)
        with zipfile.ZipFile(output, 'r') as zf:
            survey_data = json.loads(zf.read("survey.json"))
            self.assertIn("exported_at", survey_data)
            self.assertIn("Z", survey_data["exported_at"])

    def test_validate_archive_valid_structure(self):
        """
        GIVEN a valid ZIP archive with survey.json
        WHEN validate_archive is called
        THEN it returns parsed data with has_structure=True
        """
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")
        output.seek(0)

        with zipfile.ZipFile(output, 'r') as zf:
            result = validate_archive(zf)

        self.assertTrue(result["has_structure"])
        self.assertFalse(result["has_data"])
        self.assertIsNotNone(result["survey_data"])

    def test_validate_archive_valid_full(self):
        """
        GIVEN a valid ZIP archive with both survey.json and responses.json
        WHEN validate_archive is called
        THEN it returns parsed data with has_structure=True and has_data=True
        """
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="full")
        output.seek(0)

        with zipfile.ZipFile(output, 'r') as zf:
            result = validate_archive(zf)

        self.assertTrue(result["has_structure"])
        self.assertTrue(result["has_data"])

    def test_validate_archive_empty_zip(self):
        """
        GIVEN a ZIP archive without survey.json or responses.json
        WHEN validate_archive is called
        THEN it raises ImportError
        """
        output = BytesIO()
        with zipfile.ZipFile(output, 'w') as zf:
            zf.writestr("readme.txt", "empty")
        output.seek(0)

        with zipfile.ZipFile(output, 'r') as zf:
            with self.assertRaises(ImportError) as context:
                validate_archive(zf)
            self.assertIn("survey.json", str(context.exception))

    def test_validate_archive_wrong_version(self):
        """
        GIVEN a ZIP archive with unsupported version
        WHEN validate_archive is called
        THEN it raises ImportError
        """
        output = BytesIO()
        with zipfile.ZipFile(output, 'w') as zf:
            zf.writestr("survey.json", json.dumps({
                "version": "2.0",
                "survey": {"name": "test"}
            }))
        output.seek(0)

        with zipfile.ZipFile(output, 'r') as zf:
            with self.assertRaises(ImportError) as context:
                validate_archive(zf)
            self.assertIn("Unsupported format version", str(context.exception))


class CLICommandTest(TestCase):
    """Tests for CLI export/import management commands."""

    def setUp(self):
        """Set up test data for CLI tests."""
        self.org = _make_org()
        self.survey = SurveyHeader.objects.create(name="cli_test_survey", organization=self.org)
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="cli_section",
            code="CS",
            is_head=True
        )
        self.question = Question.objects.create(
            survey_section=self.section,
            code="Q_CLI",
            name="CLI test question",
            input_type="text"
        )

    def test_export_command_to_file(self):
        """
        GIVEN a survey exists
        WHEN export_survey command is called with --output
        THEN it creates a valid ZIP file
        """
        import tempfile
        from django.core.management import call_command

        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
            output_path = f.name

        try:
            call_command('export_survey', 'cli_test_survey', '--output', output_path)

            with zipfile.ZipFile(output_path, 'r') as zf:
                self.assertIn("survey.json", zf.namelist())
        finally:
            import os
            os.unlink(output_path)

    def test_export_command_with_mode(self):
        """
        GIVEN a survey with responses
        WHEN export_survey command is called with --mode=full
        THEN it creates ZIP with both survey.json and responses.json
        """
        import tempfile
        from django.core.management import call_command

        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(
            survey_session=session,
            question=self.question,
            text="CLI response"
        )

        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
            output_path = f.name

        try:
            call_command('export_survey', 'cli_test_survey', '--mode', 'full', '--output', output_path)

            with zipfile.ZipFile(output_path, 'r') as zf:
                self.assertIn("survey.json", zf.namelist())
                self.assertIn("responses.json", zf.namelist())
        finally:
            import os
            os.unlink(output_path)

    def test_export_command_survey_not_found(self):
        """
        GIVEN no survey exists with given name
        WHEN export_survey command is called
        THEN it raises CommandError
        """
        from django.core.management import call_command
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError) as context:
            call_command('export_survey', 'nonexistent_survey')
        self.assertIn("not found", str(context.exception))

    def test_import_command_from_file(self):
        """
        GIVEN a valid ZIP archive file
        WHEN import_survey command is called
        THEN it creates the survey
        """
        import tempfile
        from django.core.management import call_command

        # First export to create a valid archive
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")
        output.seek(0)

        # Read and modify to use different name
        with zipfile.ZipFile(output, 'r') as zf:
            survey_json = json.loads(zf.read("survey.json"))

        survey_json["survey"]["name"] = "imported_cli_survey"

        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
            import_path = f.name

        try:
            with zipfile.ZipFile(import_path, 'w') as zf:
                zf.writestr("survey.json", json.dumps(survey_json))

            call_command('import_survey', import_path)

            self.assertTrue(SurveyHeader.objects.filter(name="imported_cli_survey").exists())
        finally:
            import os
            os.unlink(import_path)

    def test_import_command_file_not_found(self):
        """
        GIVEN a non-existent file path
        WHEN import_survey command is called
        THEN it raises CommandError
        """
        from django.core.management import call_command
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError) as context:
            call_command('import_survey', '/nonexistent/path/to/file.zip')
        self.assertIn("not found", str(context.exception))

    def test_import_command_duplicate_name_allowed(self):
        """
        GIVEN a ZIP archive with survey name that already exists
        WHEN import_survey command is called
        THEN the import succeeds (duplicate names are allowed)
        """
        import tempfile
        from django.core.management import call_command

        # Export existing survey
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")
        output.seek(0)

        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
            import_path = f.name

        try:
            with open(import_path, 'wb') as f:
                f.write(output.read())

            call_command('import_survey', import_path)
            self.assertEqual(SurveyHeader.objects.filter(name='cli_test_survey').count(), 2)
        finally:
            import os
            os.unlink(import_path)


class RoundTripTest(TestCase):
    """Tests for export/import round-trip integrity."""

    def setUp(self):
        self.org = _make_org()

    def test_roundtrip_structure_only(self):
        """
        GIVEN a complete survey with sections and questions
        WHEN exported and imported with mode=structure
        THEN the imported survey matches the original structure
        """
        # Create original survey
        survey = SurveyHeader.objects.create(
            name="roundtrip_survey",
            organization=self.org,
            redirect_url="https://example.org/completed/"
        )
        section1 = SurveySection.objects.create(
            survey_header=survey,
            name="section_a",
            title="First Section",
            code="SA",
            is_head=True,
            start_map_postion=Point(30.0, 60.0),
            start_map_zoom=15
        )
        section2 = SurveySection.objects.create(
            survey_header=survey,
            name="section_b",
            title="Second Section",
            code="SB",
            is_head=False
        )
        section1.next_section = section2
        section1.save()
        section2.prev_section = section1
        section2.save()

        rt_choices = [
            {"code": 1, "name": {"en": "Option A"}},
            {"code": 2, "name": {"en": "Option B"}},
        ]

        question1 = Question.objects.create(
            survey_section=section1,
            code="Q_RT1",
            order_number=1,
            name="Main question",
            input_type="choice",
            choices=rt_choices,
            required=True
        )
        sub_question = Question.objects.create(
            survey_section=section1,
            parent_question_id=question1,
            code="Q_RT1_SUB",
            order_number=1,
            name="Follow-up",
            input_type="text"
        )

        # Export
        output = BytesIO()
        export_survey_to_zip(survey, output, mode="structure")
        output.seek(0)

        # Modify name in archive for import
        with zipfile.ZipFile(output, 'r') as zf:
            survey_json = json.loads(zf.read("survey.json"))

        survey_json["survey"]["name"] = "roundtrip_imported"

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_json))
        import_buffer.seek(0)

        # Import
        imported_survey, warnings = import_survey_from_zip(import_buffer)

        # Verify structure
        self.assertEqual(imported_survey.name, "roundtrip_imported")
        self.assertEqual(imported_survey.organization.name, "TestOrg")
        self.assertEqual(imported_survey.redirect_url, "https://example.org/completed/")

        # Verify sections
        imported_sections = list(SurveySection.objects.filter(
            survey_header=imported_survey
        ).order_by('name'))
        self.assertEqual(len(imported_sections), 2)
        self.assertEqual(imported_sections[0].title, "First Section")
        self.assertEqual(imported_sections[0].is_head, True)
        self.assertEqual(imported_sections[0].start_map_zoom, 15)

        # Verify section links
        self.assertEqual(imported_sections[0].next_section, imported_sections[1])
        self.assertEqual(imported_sections[1].prev_section, imported_sections[0])

        # Verify questions
        imported_questions = list(Question.objects.filter(
            survey_section__survey_header=imported_survey,
            parent_question_id__isnull=True
        ))
        self.assertEqual(len(imported_questions), 1)
        self.assertEqual(imported_questions[0].name, "Main question")
        self.assertEqual(imported_questions[0].required, True)
        self.assertIsNotNone(imported_questions[0].choices)
        self.assertEqual(len(imported_questions[0].choices), 2)

        # Verify sub-questions
        sub_questions = list(Question.objects.filter(
            parent_question_id=imported_questions[0]
        ))
        self.assertEqual(len(sub_questions), 1)
        self.assertEqual(sub_questions[0].name, "Follow-up")

    def test_roundtrip_full_with_responses(self):
        """
        GIVEN a survey with sections, questions, and responses
        WHEN exported and imported with mode=full
        THEN the imported survey includes all responses
        """
        # Create survey
        survey = SurveyHeader.objects.create(name="full_roundtrip", organization=self.org)
        section = SurveySection.objects.create(
            survey_header=survey,
            name="full_section",
            code="FS",
            is_head=True
        )
        full_choices = [{"code": 1, "name": "Selected"}]

        text_q = Question.objects.create(
            survey_section=section,
            code="Q_FULL_TEXT",
            name="Text question",
            input_type="text"
        )
        choice_q = Question.objects.create(
            survey_section=section,
            code="Q_FULL_CHOICE",
            name="Choice question",
            input_type="choice",
            choices=full_choices
        )
        point_q = Question.objects.create(
            survey_section=section,
            code="Q_FULL_POINT",
            name="Point question",
            input_type="point"
        )

        # Create responses
        session = SurveySession.objects.create(survey=survey)
        Answer.objects.create(
            survey_session=session,
            question=text_q,
            text="User response"
        )
        Answer.objects.create(
            survey_session=session,
            question=choice_q,
            selected_choices=[1]
        )
        Answer.objects.create(
            survey_session=session,
            question=point_q,
            point=Point(31.0, 61.0)
        )

        # Export full
        output = BytesIO()
        export_survey_to_zip(survey, output, mode="full")
        output.seek(0)

        # Modify name in archive
        with zipfile.ZipFile(output, 'r') as zf:
            survey_json = json.loads(zf.read("survey.json"))
            responses_json = json.loads(zf.read("responses.json"))

        survey_json["survey"]["name"] = "full_roundtrip_imported"
        responses_json["survey_name"] = "full_roundtrip_imported"

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_json))
            zf.writestr("responses.json", json.dumps(responses_json))
        import_buffer.seek(0)

        # Import
        imported_survey, warnings = import_survey_from_zip(import_buffer)

        # Verify survey
        self.assertEqual(imported_survey.name, "full_roundtrip_imported")

        # Verify sessions
        sessions = list(SurveySession.objects.filter(survey=imported_survey))
        self.assertEqual(len(sessions), 1)

        # Verify answers
        answers = list(Answer.objects.filter(survey_session=sessions[0]))
        self.assertEqual(len(answers), 3)

        # Use question name instead of code, since codes may be remapped
        text_answer = next(a for a in answers if a.question.name == "Text question")
        self.assertEqual(text_answer.text, "User response")

        choice_answer = next(a for a in answers if a.question.name == "Choice question")
        self.assertEqual(choice_answer.selected_choices, [1])

        point_answer = next(a for a in answers if a.question.name == "Point question")
        self.assertIsNotNone(point_answer.point)

    def test_roundtrip_preserves_geo_data(self):
        """
        GIVEN a survey with geo answers (point, line, polygon)
        WHEN exported and imported
        THEN the geo data is preserved accurately
        """
        survey = SurveyHeader.objects.create(name="geo_roundtrip", organization=self.org)
        section = SurveySection.objects.create(
            survey_header=survey,
            name="geo_section",
            code="GS",
            is_head=True,
            start_map_postion=Point(30.317, 59.945)
        )
        point_q = Question.objects.create(
            survey_section=section,
            code="Q_GEO_PT",
            input_type="point"
        )
        line_q = Question.objects.create(
            survey_section=section,
            code="Q_GEO_LN",
            input_type="line"
        )
        poly_q = Question.objects.create(
            survey_section=section,
            code="Q_GEO_PG",
            input_type="polygon"
        )

        session = SurveySession.objects.create(survey=survey)
        original_point = Point(30.5, 60.0)
        original_line = LineString((0, 0), (1, 1), (2, 0))
        original_polygon = Polygon(((0, 0), (0, 2), (2, 2), (2, 0), (0, 0)))

        Answer.objects.create(survey_session=session, question=point_q, point=original_point)
        Answer.objects.create(survey_session=session, question=line_q, line=original_line)
        Answer.objects.create(survey_session=session, question=poly_q, polygon=original_polygon)

        # Export
        output = BytesIO()
        export_survey_to_zip(survey, output, mode="full")
        output.seek(0)

        # Modify name for import
        with zipfile.ZipFile(output, 'r') as zf:
            survey_json = json.loads(zf.read("survey.json"))
            responses_json = json.loads(zf.read("responses.json"))

        survey_json["survey"]["name"] = "geo_roundtrip_imported"
        responses_json["survey_name"] = "geo_roundtrip_imported"

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_json))
            zf.writestr("responses.json", json.dumps(responses_json))
        import_buffer.seek(0)

        # Import
        imported_survey, _ = import_survey_from_zip(import_buffer)

        # Verify geo section position
        imported_section = SurveySection.objects.get(survey_header=imported_survey)
        self.assertAlmostEqual(imported_section.start_map_postion.x, 30.317, places=3)
        self.assertAlmostEqual(imported_section.start_map_postion.y, 59.945, places=3)

        # Verify geo answers - use input_type since codes may be remapped
        session = SurveySession.objects.get(survey=imported_survey)
        answers = Answer.objects.filter(survey_session=session)

        point_ans = answers.get(question__input_type="point")
        self.assertAlmostEqual(point_ans.point.x, 30.5, places=1)
        self.assertAlmostEqual(point_ans.point.y, 60.0, places=1)

        line_ans = answers.get(question__input_type="line")
        self.assertEqual(len(line_ans.line.coords), 3)

        poly_ans = answers.get(question__input_type="polygon")
        self.assertIsNotNone(poly_ans.polygon)


class DataOnlyImportTest(TestCase):
    """Tests for data-only import to existing survey."""

    def setUp(self):
        """Create a survey for data-only import tests."""
        self.org = _make_org()
        self.survey = SurveyHeader.objects.create(name="existing_survey", organization=self.org)
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="existing_section",
            code="ES",
            is_head=True
        )
        self.data_import_choices = [{"code": 1, "name": "Choice A"}]
        self.text_q = Question.objects.create(
            survey_section=self.section,
            code="Q_EXIST_TEXT",
            name="Existing text question",
            input_type="text"
        )
        self.choice_q = Question.objects.create(
            survey_section=self.section,
            code="Q_EXIST_CHOICE",
            name="Existing choice question",
            input_type="choice",
            choices=self.data_import_choices
        )

    def test_data_only_import_to_existing_survey(self):
        """
        GIVEN an existing survey and data-only ZIP archive
        WHEN import_survey_from_zip is called
        THEN responses are added to the existing survey
        """
        # Create data-only archive
        responses_data = {
            "version": FORMAT_VERSION,
            "exported_at": "2024-01-01T12:00:00Z",
            "survey_name": "existing_survey",
            "sessions": [
                {
                    "start_datetime": "2024-01-01T10:00:00Z",
                    "end_datetime": "2024-01-01T10:30:00Z",
                    "answers": [
                        {
                            "question_code": "Q_EXIST_TEXT",
                            "text": "Imported response",
                            "numeric": None,
                            "yn": None,
                            "point": None,
                            "line": None,
                            "polygon": None,
                            "choices": [],
                            "sub_answers": []
                        },
                        {
                            "question_code": "Q_EXIST_CHOICE",
                            "text": None,
                            "numeric": None,
                            "yn": None,
                            "point": None,
                            "line": None,
                            "polygon": None,
                            "choices": ["Choice A"],
                            "sub_answers": []
                        }
                    ]
                }
            ]
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("responses.json", json.dumps(responses_data))
        import_buffer.seek(0)

        # Import
        result_survey, warnings = import_survey_from_zip(import_buffer)

        # For data-only import, the existing survey is returned
        self.assertEqual(result_survey, self.survey)

        # Verify session was added to existing survey
        sessions = SurveySession.objects.filter(survey=self.survey)
        self.assertEqual(sessions.count(), 1)

        # Verify answers
        session = sessions.first()
        answers = Answer.objects.filter(survey_session=session)
        self.assertEqual(answers.count(), 2)

        text_answer = answers.get(question=self.text_q)
        self.assertEqual(text_answer.text, "Imported response")

        choice_answer = answers.get(question=self.choice_q)
        self.assertEqual(choice_answer.selected_choices, [1])

    def test_data_only_import_requires_existing_survey(self):
        """
        GIVEN a data-only archive referencing non-existent survey
        WHEN import_survey_from_zip is called
        THEN it raises ImportError
        """
        responses_data = {
            "version": FORMAT_VERSION,
            "exported_at": "2024-01-01T12:00:00Z",
            "survey_name": "nonexistent_survey",
            "sessions": []
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("responses.json", json.dumps(responses_data))
        import_buffer.seek(0)

        with self.assertRaises(ImportError) as context:
            import_survey_from_zip(import_buffer)
        self.assertIn("requires existing survey", str(context.exception))

    def test_data_only_import_multiple_sessions(self):
        """
        GIVEN a data-only archive with multiple sessions
        WHEN import_survey_from_zip is called
        THEN all sessions are imported
        """
        responses_data = {
            "version": FORMAT_VERSION,
            "exported_at": "2024-01-01T12:00:00Z",
            "survey_name": "existing_survey",
            "sessions": [
                {
                    "start_datetime": "2024-01-01T10:00:00Z",
                    "end_datetime": None,
                    "answers": [
                        {"question_code": "Q_EXIST_TEXT", "text": "Session 1",
                         "numeric": None, "yn": None, "point": None, "line": None,
                         "polygon": None, "choices": [], "sub_answers": []}
                    ]
                },
                {
                    "start_datetime": "2024-01-02T10:00:00Z",
                    "end_datetime": None,
                    "answers": [
                        {"question_code": "Q_EXIST_TEXT", "text": "Session 2",
                         "numeric": None, "yn": None, "point": None, "line": None,
                         "polygon": None, "choices": [], "sub_answers": []}
                    ]
                },
                {
                    "start_datetime": "2024-01-03T10:00:00Z",
                    "end_datetime": None,
                    "answers": [
                        {"question_code": "Q_EXIST_TEXT", "text": "Session 3",
                         "numeric": None, "yn": None, "point": None, "line": None,
                         "polygon": None, "choices": [], "sub_answers": []}
                    ]
                }
            ]
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("responses.json", json.dumps(responses_data))
        import_buffer.seek(0)

        import_survey_from_zip(import_buffer)

        sessions = SurveySession.objects.filter(survey=self.survey)
        self.assertEqual(sessions.count(), 3)

        texts = [Answer.objects.get(survey_session=s).text for s in sessions]
        self.assertIn("Session 1", texts)
        self.assertIn("Session 2", texts)
        self.assertIn("Session 3", texts)


class ErrorCaseTest(TestCase):
    """Tests for error cases during import."""

    def setUp(self):
        self.org = _make_org()

    def test_invalid_zip_file(self):
        """
        GIVEN invalid data that is not a ZIP file
        WHEN import_survey_from_zip is called
        THEN it raises ImportError
        """
        invalid_data = BytesIO(b"This is not a ZIP file")

        with self.assertRaises(ImportError) as context:
            import_survey_from_zip(invalid_data)
        self.assertIn("Invalid ZIP", str(context.exception))

    def test_missing_survey_json_and_responses_json(self):
        """
        GIVEN a ZIP file without survey.json or responses.json
        WHEN import_survey_from_zip is called
        THEN it raises ImportError
        """
        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("readme.txt", "Nothing here")
        import_buffer.seek(0)

        with self.assertRaises(ImportError) as context:
            import_survey_from_zip(import_buffer)
        self.assertIn("must contain", str(context.exception))

    def test_invalid_json_in_survey(self):
        """
        GIVEN a ZIP file with invalid JSON in survey.json
        WHEN import_survey_from_zip is called
        THEN it raises ImportError
        """
        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", "{ invalid json }")
        import_buffer.seek(0)

        with self.assertRaises(ImportError) as context:
            import_survey_from_zip(import_buffer)
        self.assertIn("Invalid survey.json", str(context.exception))

    def test_unsupported_version(self):
        """
        GIVEN a ZIP file with unsupported format version
        WHEN import_survey_from_zip is called
        THEN it raises ImportError with version info
        """
        survey_data = {
            "version": "99.0",
            "survey": {"name": "test"},
            "option_groups": []
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_data))
        import_buffer.seek(0)

        with self.assertRaises(ImportError) as context:
            import_survey_from_zip(import_buffer)
        self.assertIn("Unsupported format version", str(context.exception))
        self.assertIn("99.0", str(context.exception))

    def test_missing_survey_name(self):
        """
        GIVEN a ZIP file with survey.json missing name field
        WHEN import_survey_from_zip is called
        THEN it raises ImportError
        """
        survey_data = {
            "version": FORMAT_VERSION,
            "survey": {"organization": "Test"},
            "option_groups": []
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_data))
        import_buffer.seek(0)

        with self.assertRaises(ImportError) as context:
            import_survey_from_zip(import_buffer)
        self.assertIn("survey.name", str(context.exception))

    def test_survey_duplicate_name_import_allowed(self):
        """
        GIVEN a survey already exists with the same name
        WHEN import_survey_from_zip is called
        THEN the import succeeds (duplicate names are allowed)
        """
        SurveyHeader.objects.create(name="duplicate_survey", organization=self.org)

        survey_data = {
            "version": FORMAT_VERSION,
            "survey": {
                "name": "duplicate_survey",
                "sections": [],
            },
            "option_groups": []
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_data))
        import_buffer.seek(0)

        result_survey, warnings = import_survey_from_zip(import_buffer)
        self.assertEqual(result_survey.name, "duplicate_survey")
        self.assertEqual(SurveyHeader.objects.filter(name="duplicate_survey").count(), 2)

    def test_invalid_input_type(self):
        """
        GIVEN a survey.json with invalid input_type for a question
        WHEN import_survey_from_zip is called
        THEN it raises ImportError
        """
        survey_data = {
            "version": FORMAT_VERSION,
            "survey": {
                "name": "invalid_input_type_survey",
                "sections": [
                    {
                        "name": "section1",
                        "code": "S1",
                        "is_head": True,
                        "questions": [
                            {
                                "code": "Q_INVALID",
                                "order_number": 1,
                                "name": "Invalid question",
                                "input_type": "invalid_type",
                                "sub_questions": []
                            }
                        ]
                    }
                ]
            },
            "option_groups": []
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_data))
        import_buffer.seek(0)

        with self.assertRaises(ImportError) as context:
            import_survey_from_zip(import_buffer)
        self.assertIn("Invalid input_type", str(context.exception))
        self.assertIn("invalid_type", str(context.exception))

    def test_answer_references_unknown_question(self):
        """
        GIVEN an existing survey and responses referencing unknown question
        WHEN import_survey_from_zip is called
        THEN it imports with warning and skips the answer
        """
        survey = SurveyHeader.objects.create(name="missing_ref_survey", organization=self.org)
        section = SurveySection.objects.create(
            survey_header=survey,
            name="missing_ref_section",
            code="MRS",
            is_head=True
        )
        Question.objects.create(
            survey_section=section,
            code="Q_EXISTS",
            name="Existing",
            input_type="text"
        )

        responses_data = {
            "version": FORMAT_VERSION,
            "survey_name": "missing_ref_survey",
            "sessions": [
                {
                    "start_datetime": "2024-01-01T10:00:00Z",
                    "end_datetime": None,
                    "answers": [
                        {"question_code": "Q_NONEXISTENT", "text": "Orphan",
                         "numeric": None, "yn": None, "point": None, "line": None,
                         "polygon": None, "choices": [], "sub_answers": []}
                    ]
                }
            ]
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("responses.json", json.dumps(responses_data))
        import_buffer.seek(0)

        result, warnings = import_survey_from_zip(import_buffer)

        # Should have a warning about missing question
        self.assertTrue(any("Q_NONEXISTENT" in w for w in warnings))

        # Session should still be created, but no answer
        sessions = SurveySession.objects.filter(survey=survey)
        self.assertEqual(sessions.count(), 1)
        self.assertEqual(Answer.objects.filter(survey_session=sessions.first()).count(), 0)

    def test_choice_references_missing_option(self):
        """
        GIVEN responses with choice name not in Question.choices
        WHEN import_survey_from_zip is called
        THEN it imports with warning and skips the choice
        """
        survey = SurveyHeader.objects.create(name="missing_choice_survey", organization=self.org)
        section = SurveySection.objects.create(
            survey_header=survey,
            name="missing_choice_section",
            code="MCS",
            is_head=True
        )
        Question.objects.create(
            survey_section=section,
            code="Q_CHOICE_TEST",
            name="Choice test",
            input_type="choice",
            choices=[{"code": 1, "name": "Valid Choice"}]
        )

        responses_data = {
            "version": FORMAT_VERSION,
            "survey_name": "missing_choice_survey",
            "sessions": [
                {
                    "start_datetime": "2024-01-01T10:00:00Z",
                    "end_datetime": None,
                    "answers": [
                        {"question_code": "Q_CHOICE_TEST", "text": None,
                         "numeric": None, "yn": None, "point": None, "line": None,
                         "polygon": None, "choices": ["Valid Choice", "Missing Choice"],
                         "sub_answers": []}
                    ]
                }
            ]
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("responses.json", json.dumps(responses_data))
        import_buffer.seek(0)

        result, warnings = import_survey_from_zip(import_buffer)

        # Should have warning about missing choice
        self.assertTrue(any("Missing Choice" in w for w in warnings))

        # Answer should exist with only valid choice code
        answer = Answer.objects.get(question__code="Q_CHOICE_TEST")
        self.assertEqual(answer.selected_choices, [1])

    def test_invalid_wkt_in_section(self):
        """
        GIVEN survey.json with invalid WKT for section geo point
        WHEN import_survey_from_zip is called
        THEN it raises ImportError
        """
        survey_data = {
            "version": FORMAT_VERSION,
            "survey": {
                "name": "invalid_wkt_survey",
                "sections": [
                    {
                        "name": "section1",
                        "code": "S1",
                        "is_head": True,
                        "start_map_position": "NOT VALID WKT",
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

        with self.assertRaises(ImportError) as context:
            import_survey_from_zip(import_buffer)
        self.assertIn("Invalid WKT", str(context.exception))

    def test_legacy_option_group_missing_code_uses_index(self):
        """
        GIVEN survey.json with legacy option_groups where choices missing 'code' field
        WHEN import_survey_from_zip is called
        THEN it converts to inline choices with auto-generated codes (1, 2, 3...)
        """
        survey_data = {
            "version": FORMAT_VERSION,
            "survey": {
                "name": "missing_choice_code_survey",
                "sections": [
                    {
                        "name": "section1",
                        "code": "S1",
                        "is_head": True,
                        "questions": [
                            {
                                "code": "Q_CHOICE",
                                "order_number": 1,
                                "name": "Choice question",
                                "input_type": "choice",
                                "option_group_name": "NoCodeGroup",
                                "sub_questions": []
                            }
                        ]
                    }
                ]
            },
            "option_groups": [
                {
                    "name": "NoCodeGroup",
                    "choices": [
                        {"name": "First"},
                        {"name": "Second"},
                        {"name": "Third"}
                    ]
                }
            ]
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_data))
        import_buffer.seek(0)

        imported_survey, warnings = import_survey_from_zip(import_buffer)

        # Should have created survey
        self.assertIsNotNone(imported_survey)

        # Question should have inline choices with sequential codes
        question = Question.objects.get(
            survey_section__survey_header=imported_survey,
            code="Q_CHOICE"
        )
        self.assertEqual(len(question.choices), 3)
        self.assertEqual(question.choices[0]["code"], 1)
        self.assertEqual(question.choices[1]["code"], 2)
        self.assertEqual(question.choices[2]["code"], 3)

    def test_section_code_truncated_to_max_length(self):
        """
        GIVEN survey.json with section code longer than 8 characters
        WHEN import_survey_from_zip is called
        THEN it truncates the code to 8 characters
        """
        survey_data = {
            "version": FORMAT_VERSION,
            "survey": {
                "name": "long_code_survey",
                "sections": [
                    {
                        "name": "section1",
                        "code": "VERYLONGCODE123",
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

        imported_survey, warnings = import_survey_from_zip(import_buffer)

        self.assertIsNotNone(imported_survey)
        section = SurveySection.objects.get(survey_header=imported_survey)
        self.assertEqual(section.code, "VERYLONG")
        self.assertEqual(len(section.code), 8)

    def test_choice_input_requires_choices(self):
        """
        GIVEN survey.json with choice question without choices
        WHEN import_survey_from_zip is called
        THEN it raises ImportError
        """
        survey_data = {
            "version": FORMAT_VERSION,
            "survey": {
                "name": "missing_og_survey",
                "sections": [
                    {
                        "name": "section1",
                        "code": "S1",
                        "is_head": True,
                        "questions": [
                            {
                                "code": "Q_NO_OG",
                                "order_number": 1,
                                "name": "Choice without choices",
                                "input_type": "choice",
                                "sub_questions": []
                            }
                        ]
                    }
                ]
            },
            "option_groups": []
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_data))
        import_buffer.seek(0)

        with self.assertRaises(ImportError) as context:
            import_survey_from_zip(import_buffer)
        self.assertIn("requires choices", str(context.exception))

    def test_unknown_legacy_option_group_name_raises_error(self):
        """
        GIVEN survey.json with question referencing non-existent legacy option_group
        WHEN import_survey_from_zip is called
        THEN it raises ImportError
        """
        survey_data = {
            "version": FORMAT_VERSION,
            "survey": {
                "name": "bad_og_ref_survey",
                "sections": [
                    {
                        "name": "section1",
                        "code": "S1",
                        "is_head": True,
                        "questions": [
                            {
                                "code": "Q_BAD_OG",
                                "order_number": 1,
                                "name": "Choice with bad option group",
                                "input_type": "choice",
                                "option_group_name": "NonExistentGroup",
                                "sub_questions": []
                            }
                        ]
                    }
                ]
            },
            "option_groups": []
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_data))
        import_buffer.seek(0)

        with self.assertRaises(ImportError) as context:
            import_survey_from_zip(import_buffer)
        self.assertIn("not found in option_groups", str(context.exception))


class CodeRemappingTest(TestCase):
    """Tests for question code remapping on collision."""

    def setUp(self):
        self.org = _make_org()

    def test_code_collision_generates_new_code(self):
        """
        GIVEN an existing question with same code as in archive
        WHEN import_survey_from_zip is called
        THEN it generates a new unique code for the imported question
        """
        # Create existing question with code that will collide
        existing_survey = SurveyHeader.objects.create(name="existing", organization=self.org)
        existing_section = SurveySection.objects.create(
            survey_header=existing_survey,
            name="existing_section",
            code="ES",
            is_head=True
        )
        Question.objects.create(
            survey_section=existing_section,
            code="Q_COLLISION",
            name="Existing question",
            input_type="text"
        )

        # Create archive with same question code
        survey_data = {
            "version": FORMAT_VERSION,
            "survey": {
                "name": "collision_test_survey",
                "sections": [
                    {
                        "name": "new_section",
                        "code": "NS",
                        "is_head": True,
                        "questions": [
                            {
                                "code": "Q_COLLISION",
                                "order_number": 1,
                                "name": "Imported question",
                                "input_type": "text",
                                "sub_questions": []
                            }
                        ]
                    }
                ]
            },
            "option_groups": []
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_data))
        import_buffer.seek(0)

        imported_survey, warnings = import_survey_from_zip(import_buffer)

        # Should have created survey
        self.assertIsNotNone(imported_survey)

        # Imported question should have different code
        imported_question = Question.objects.get(
            survey_section__survey_header=imported_survey
        )
        self.assertNotEqual(imported_question.code, "Q_COLLISION")
        self.assertTrue(imported_question.code.startswith("Q_"))
        self.assertEqual(imported_question.name, "Imported question")

    def test_code_remap_applies_to_responses(self):
        """
        GIVEN archive with code collision and responses referencing original code
        WHEN import_survey_from_zip is called
        THEN responses are linked using remapped code
        """
        # Create existing question with colliding code
        existing_survey = SurveyHeader.objects.create(name="existing2", organization=self.org)
        existing_section = SurveySection.objects.create(
            survey_header=existing_survey,
            name="existing_section2",
            code="ES2",
            is_head=True
        )
        Question.objects.create(
            survey_section=existing_section,
            code="Q_REMAP",
            name="Existing question",
            input_type="text"
        )

        # Archive with collision and responses
        survey_data = {
            "version": FORMAT_VERSION,
            "survey": {
                "name": "remap_test_survey",
                "sections": [
                    {
                        "name": "remap_section",
                        "code": "RS",
                        "is_head": True,
                        "questions": [
                            {
                                "code": "Q_REMAP",
                                "order_number": 1,
                                "name": "Imported question for remap",
                                "input_type": "text",
                                "sub_questions": []
                            }
                        ]
                    }
                ]
            },
            "option_groups": []
        }

        responses_data = {
            "version": FORMAT_VERSION,
            "survey_name": "remap_test_survey",
            "sessions": [
                {
                    "start_datetime": "2024-01-01T10:00:00Z",
                    "end_datetime": None,
                    "answers": [
                        {
                            "question_code": "Q_REMAP",
                            "text": "Remapped answer",
                            "numeric": None,
                            "yn": None,
                            "point": None,
                            "line": None,
                            "polygon": None,
                            "choices": [],
                            "sub_answers": []
                        }
                    ]
                }
            ]
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_data))
            zf.writestr("responses.json", json.dumps(responses_data))
        import_buffer.seek(0)

        imported_survey, warnings = import_survey_from_zip(import_buffer)

        # Get the imported question (has new code)
        imported_question = Question.objects.get(
            survey_section__survey_header=imported_survey
        )
        self.assertNotEqual(imported_question.code, "Q_REMAP")

        # Answer should be linked to the imported question with new code
        session = SurveySession.objects.get(survey=imported_survey)
        answer = Answer.objects.get(survey_session=session)
        self.assertEqual(answer.question, imported_question)
        self.assertEqual(answer.text, "Remapped answer")

    def test_code_remap_with_sub_questions(self):
        """
        GIVEN archive with parent question code collision and sub-questions
        WHEN import_survey_from_zip is called
        THEN sub-questions are correctly linked to remapped parent
        """
        # Create colliding code
        existing_survey = SurveyHeader.objects.create(name="existing3", organization=self.org)
        existing_section = SurveySection.objects.create(
            survey_header=existing_survey,
            name="existing_section3",
            code="ES3",
            is_head=True
        )
        Question.objects.create(
            survey_section=existing_section,
            code="Q_PARENT_REMAP",
            name="Existing parent",
            input_type="text"
        )

        survey_data = {
            "version": FORMAT_VERSION,
            "survey": {
                "name": "sub_remap_survey",
                "sections": [
                    {
                        "name": "sub_remap_section",
                        "code": "SRS",
                        "is_head": True,
                        "questions": [
                            {
                                "code": "Q_PARENT_REMAP",
                                "order_number": 1,
                                "name": "Imported parent",
                                "input_type": "text",
                                "sub_questions": [
                                    {
                                        "code": "Q_CHILD",
                                        "order_number": 1,
                                        "name": "Child question",
                                        "input_type": "text",
                                        "sub_questions": []
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
            "option_groups": []
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_data))
        import_buffer.seek(0)

        imported_survey, warnings = import_survey_from_zip(import_buffer)

        # Get parent (remapped)
        parent = Question.objects.get(
            survey_section__survey_header=imported_survey,
            parent_question_id__isnull=True
        )
        self.assertNotEqual(parent.code, "Q_PARENT_REMAP")

        # Get child
        child = Question.objects.get(
            survey_section__survey_header=imported_survey,
            parent_question_id__isnull=False
        )
        self.assertEqual(child.parent_question_id, parent)
        self.assertEqual(child.name, "Child question")

    def test_multiple_collisions(self):
        """
        GIVEN archive with multiple question code collisions
        WHEN import_survey_from_zip is called
        THEN all colliding codes are remapped uniquely
        """
        # Create multiple existing questions
        existing_survey = SurveyHeader.objects.create(name="existing4", organization=self.org)
        existing_section = SurveySection.objects.create(
            survey_header=existing_survey,
            name="existing_section4",
            code="ES4",
            is_head=True
        )
        Question.objects.create(survey_section=existing_section, code="Q_MULTI_1", input_type="text")
        Question.objects.create(survey_section=existing_section, code="Q_MULTI_2", input_type="text")
        Question.objects.create(survey_section=existing_section, code="Q_MULTI_3", input_type="text")

        survey_data = {
            "version": FORMAT_VERSION,
            "survey": {
                "name": "multi_collision_survey",
                "sections": [
                    {
                        "name": "multi_section",
                        "code": "MS",
                        "is_head": True,
                        "questions": [
                            {"code": "Q_MULTI_1", "order_number": 1, "name": "Q1", "input_type": "text", "sub_questions": []},
                            {"code": "Q_MULTI_2", "order_number": 2, "name": "Q2", "input_type": "text", "sub_questions": []},
                            {"code": "Q_MULTI_3", "order_number": 3, "name": "Q3", "input_type": "text", "sub_questions": []},
                        ]
                    }
                ]
            },
            "option_groups": []
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_data))
        import_buffer.seek(0)

        imported_survey, warnings = import_survey_from_zip(import_buffer)

        # All three should have new unique codes
        imported_questions = list(Question.objects.filter(
            survey_section__survey_header=imported_survey
        ))
        self.assertEqual(len(imported_questions), 3)

        codes = [q.code for q in imported_questions]
        self.assertNotIn("Q_MULTI_1", codes)
        self.assertNotIn("Q_MULTI_2", codes)
        self.assertNotIn("Q_MULTI_3", codes)

        # All codes should be unique
        self.assertEqual(len(set(codes)), 3)


class WebViewTest(TestCase):
    """Tests for Web views (auth, modes, upload)."""

    def setUp(self):
        """Set up test data and client."""
        self.client = Client()
        self.org = _make_org()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(name="web_test_survey", organization=self.org)
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="web_section",
            code="WS",
            is_head=True
        )
        self.question = Question.objects.create(
            survey_section=self.section,
            code="Q_WEB",
            name="Web test question",
            input_type="text"
        )

    def test_export_requires_authentication(self):
        """
        GIVEN an unauthenticated user
        WHEN accessing export URL directly
        THEN redirect to login page
        """
        response = self.client.get(f'/editor/export/{self.survey.uuid}/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_export_authenticated_structure_mode(self):
        """
        GIVEN an authenticated user
        WHEN accessing export URL with mode=structure
        THEN download ZIP file with survey.json
        """
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(f'/editor/export/{self.survey.uuid}/?mode=structure')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        self.assertIn('survey_web_test_survey_structure.zip', response['Content-Disposition'])

        # Verify ZIP contents
        zip_buffer = BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            self.assertIn("survey.json", zf.namelist())

    def test_export_authenticated_data_mode(self):
        """
        GIVEN an authenticated user and survey with responses
        WHEN accessing export URL with mode=data
        THEN download ZIP file with responses.json
        """
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(
            survey_session=session,
            question=self.question,
            text="Web response"
        )

        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(f'/editor/export/{self.survey.uuid}/?mode=data')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')

        zip_buffer = BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            self.assertIn("responses.json", zf.namelist())

    def test_export_authenticated_full_mode(self):
        """
        GIVEN an authenticated user
        WHEN accessing export URL with mode=full
        THEN download ZIP file with both survey.json and responses.json
        """
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(f'/editor/export/{self.survey.uuid}/?mode=full')

        self.assertEqual(response.status_code, 200)

        zip_buffer = BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            self.assertIn("survey.json", zf.namelist())
            self.assertIn("responses.json", zf.namelist())

    def test_export_default_mode_is_structure(self):
        """
        GIVEN an authenticated user
        WHEN accessing export URL without mode parameter
        THEN default to structure mode
        """
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(f'/editor/export/{self.survey.uuid}/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('structure.zip', response['Content-Disposition'])

    def test_export_survey_not_found(self):
        """
        GIVEN an authenticated user
        WHEN accessing export URL for non-existent survey UUID
        THEN the server returns 404
        """
        import uuid
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(f'/editor/export/{uuid.uuid4()}/')

        self.assertEqual(response.status_code, 404)

    def test_import_requires_authentication(self):
        """
        GIVEN an unauthenticated user
        WHEN accessing import URL
        THEN redirect to login page
        """
        response = self.client.post('/editor/import/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_import_requires_post(self):
        """
        GIVEN an authenticated user
        WHEN accessing import URL with GET
        THEN redirect to editor
        """
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get('/editor/import/')

        self.assertEqual(response.status_code, 302)
        self.assertIn('editor', response.url)

    def test_import_requires_file(self):
        """
        GIVEN an authenticated user
        WHEN posting to import URL without file
        THEN redirect with error message
        """
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post('/editor/import/')

        self.assertEqual(response.status_code, 302)

    def test_import_valid_file(self):
        """
        GIVEN an authenticated user and valid ZIP file
        WHEN posting to import URL
        THEN import survey and redirect with success message
        """
        # Create valid archive
        survey_data = {
            "version": FORMAT_VERSION,
            "survey": {
                "name": "imported_web_survey",
                "sections": [
                    {
                        "name": "imported_section",
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

        from django.core.files.uploadedfile import SimpleUploadedFile
        upload_file = SimpleUploadedFile(
            "import.zip",
            import_buffer.read(),
            content_type="application/zip"
        )

        self.client.login(username='testuser', password='testpass123')
        with _eager_import():
            response = self.client.post('/editor/import/', {'file': upload_file})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(SurveyHeader.objects.filter(name="imported_web_survey").exists())

    def test_import_invalid_file(self):
        """
        GIVEN an authenticated user and invalid ZIP file
        WHEN posting to import URL
        THEN redirect with error message
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        invalid_file = SimpleUploadedFile(
            "invalid.zip",
            b"not a valid zip file",
            content_type="application/zip"
        )

        self.client.login(username='testuser', password='testpass123')
        with _eager_import():
            response = self.client.post('/editor/import/', {'file': invalid_file})

        self.assertEqual(response.status_code, 302)

    def test_import_survey_duplicate_name_allowed(self):
        """
        GIVEN an authenticated user and archive with existing survey name
        WHEN posting to import URL
        THEN the import succeeds (duplicate names are allowed)
        """
        survey_data = {
            "version": FORMAT_VERSION,
            "survey": {
                "name": "web_test_survey",  # Already exists
                "sections": []
            },
            "option_groups": []
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_data))
        import_buffer.seek(0)

        from django.core.files.uploadedfile import SimpleUploadedFile
        upload_file = SimpleUploadedFile(
            "import.zip",
            import_buffer.read(),
            content_type="application/zip"
        )

        self.client.login(username='testuser', password='testpass123')
        with _eager_import():
            response = self.client.post('/editor/import/', {'file': upload_file})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(SurveyHeader.objects.filter(name='web_test_survey').count(), 2)


class TranslationSerializationTest(TestCase):
    """Tests for export/import of translations."""

    def setUp(self):
        """Set up test data with translations."""
        from survey.models import SurveySectionTranslation, QuestionTranslation
        self.SurveySectionTranslation = SurveySectionTranslation
        self.QuestionTranslation = QuestionTranslation

        self.org = Organization.objects.create(name="Serialization Test Org")
        self.survey = SurveyHeader.objects.create(
            name="serialization_test",
            organization=self.org,
            available_languages=["en", "ru", "de"]
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="section1",
            title="Original Section Title",
            subheading="Original Section Subheading",
            code="ST1",
            is_head=True
        )
        self.choices = [
            {"code": 1, "name": {"en": "Original Choice", "ru": "Русский выбор"}},
        ]
        self.question = Question.objects.create(
            survey_section=self.section,
            code="Q_SER",
            order_number=1,
            name="Original Question Name",
            subtext="Original Question Subtext",
            input_type="choice",
            choices=self.choices
        )

        # Create translations
        self.SurveySectionTranslation.objects.create(
            section=self.section,
            language="ru",
            title="Русский заголовок секции",
            subheading="Русский подзаголовок секции"
        )
        self.QuestionTranslation.objects.create(
            question=self.question,
            language="ru",
            name="Русский вопрос",
            subtext="Русский подтекст"
        )

    def test_export_includes_available_languages(self):
        """
        GIVEN a survey with available_languages
        WHEN exported to ZIP
        THEN survey.json contains available_languages field
        """
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")
        output.seek(0)

        with zipfile.ZipFile(output, 'r') as zf:
            survey_data = json.loads(zf.read("survey.json"))

        self.assertEqual(
            survey_data["survey"]["available_languages"],
            ["en", "ru", "de"]
        )

    def test_export_includes_section_translations(self):
        """
        GIVEN a section with translations
        WHEN exported to ZIP
        THEN section has translations array in survey.json
        """
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")
        output.seek(0)

        with zipfile.ZipFile(output, 'r') as zf:
            survey_data = json.loads(zf.read("survey.json"))

        section_data = survey_data["survey"]["sections"][0]
        self.assertIn("translations", section_data)
        self.assertEqual(len(section_data["translations"]), 1)
        self.assertEqual(section_data["translations"][0]["language"], "ru")
        self.assertEqual(section_data["translations"][0]["title"], "Русский заголовок секции")
        self.assertEqual(section_data["translations"][0]["subheading"], "Русский подзаголовок секции")

    def test_export_includes_question_translations(self):
        """
        GIVEN a question with translations
        WHEN exported to ZIP
        THEN question has translations array in survey.json
        """
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")
        output.seek(0)

        with zipfile.ZipFile(output, 'r') as zf:
            survey_data = json.loads(zf.read("survey.json"))

        question_data = survey_data["survey"]["sections"][0]["questions"][0]
        self.assertIn("translations", question_data)
        self.assertEqual(len(question_data["translations"]), 1)
        self.assertEqual(question_data["translations"][0]["language"], "ru")
        self.assertEqual(question_data["translations"][0]["name"], "Русский вопрос")
        self.assertEqual(question_data["translations"][0]["subtext"], "Русский подтекст")

    def test_export_includes_inline_choice_translations(self):
        """
        GIVEN a question with inline choices containing multilingual names
        WHEN exported to ZIP
        THEN question choices contain multilingual name dict
        """
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")
        output.seek(0)

        with zipfile.ZipFile(output, 'r') as zf:
            survey_data = json.loads(zf.read("survey.json"))

        question_data = survey_data["survey"]["sections"][0]["questions"][0]
        self.assertIsNotNone(question_data["choices"])
        self.assertEqual(len(question_data["choices"]), 1)
        choice = question_data["choices"][0]
        self.assertEqual(choice["code"], 1)
        self.assertEqual(choice["name"]["en"], "Original Choice")
        self.assertEqual(choice["name"]["ru"], "Русский выбор")

    def test_export_includes_session_language(self):
        """
        GIVEN a session with language set
        WHEN exported with mode=full
        THEN session has language field in responses.json
        """
        session = SurveySession.objects.create(
            survey=self.survey,
            language="ru"
        )

        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="full")
        output.seek(0)

        with zipfile.ZipFile(output, 'r') as zf:
            responses_data = json.loads(zf.read("responses.json"))

        self.assertEqual(responses_data["sessions"][0]["language"], "ru")

    def test_import_restores_available_languages(self):
        """
        GIVEN a ZIP with available_languages
        WHEN imported
        THEN survey has available_languages set
        """
        # Export
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")
        output.seek(0)

        # Modify name for import
        with zipfile.ZipFile(output, 'r') as zf:
            survey_json = json.loads(zf.read("survey.json"))

        survey_json["survey"]["name"] = "imported_translation_test"

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_json))
        import_buffer.seek(0)

        # Import
        imported_survey, _ = import_survey_from_zip(import_buffer)

        self.assertEqual(imported_survey.available_languages, ["en", "ru", "de"])

    def test_import_restores_section_translations(self):
        """
        GIVEN a ZIP with section translations
        WHEN imported
        THEN section has translations
        """
        # Export
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")
        output.seek(0)

        # Modify name for import
        with zipfile.ZipFile(output, 'r') as zf:
            survey_json = json.loads(zf.read("survey.json"))

        survey_json["survey"]["name"] = "imported_section_trans"

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_json))
        import_buffer.seek(0)

        # Import
        imported_survey, _ = import_survey_from_zip(import_buffer)

        section = SurveySection.objects.get(survey_header=imported_survey)
        self.assertEqual(section.get_translated_title("ru"), "Русский заголовок секции")
        self.assertEqual(section.get_translated_subheading("ru"), "Русский подзаголовок секции")

    def test_import_restores_question_translations(self):
        """
        GIVEN a ZIP with question translations
        WHEN imported
        THEN question has translations
        """
        # Export
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")
        output.seek(0)

        # Modify name for import
        with zipfile.ZipFile(output, 'r') as zf:
            survey_json = json.loads(zf.read("survey.json"))

        survey_json["survey"]["name"] = "imported_question_trans"

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_json))
        import_buffer.seek(0)

        # Import
        imported_survey, _ = import_survey_from_zip(import_buffer)

        question = Question.objects.get(
            survey_section__survey_header=imported_survey,
            name="Original Question Name"
        )
        self.assertEqual(question.get_translated_name("ru"), "Русский вопрос")
        self.assertEqual(question.get_translated_subtext("ru"), "Русский подтекст")

    def test_import_restores_inline_choice_translations(self):
        """
        GIVEN a ZIP with inline choices containing multilingual names
        WHEN imported
        THEN question has choices with multilingual names preserved
        """
        # Export
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")
        output.seek(0)

        # Modify name for import
        with zipfile.ZipFile(output, 'r') as zf:
            survey_json = json.loads(zf.read("survey.json"))

        survey_json["survey"]["name"] = "imported_choice_trans"

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_json))
        import_buffer.seek(0)

        # Import
        imported_survey, _ = import_survey_from_zip(import_buffer)

        # Verify inline choices with translations were imported
        imported_question = Question.objects.get(
            survey_section__survey_header=imported_survey,
            name="Original Question Name"
        )
        self.assertIsNotNone(imported_question.choices)
        self.assertEqual(len(imported_question.choices), 1)
        self.assertEqual(imported_question.get_choice_name(1, "en"), "Original Choice")
        self.assertEqual(imported_question.get_choice_name(1, "ru"), "Русский выбор")

    def test_import_restores_session_language(self):
        """
        GIVEN a ZIP with session language
        WHEN imported with mode=full
        THEN session has language set
        """
        # Create session with language
        session = SurveySession.objects.create(
            survey=self.survey,
            language="de"
        )
        Answer.objects.create(
            survey_session=session,
            question=self.question
        )

        # Export full
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="full")
        output.seek(0)

        # Modify name for import
        with zipfile.ZipFile(output, 'r') as zf:
            survey_json = json.loads(zf.read("survey.json"))
            responses_json = json.loads(zf.read("responses.json"))

        survey_json["survey"]["name"] = "imported_session_lang"
        responses_json["survey_name"] = "imported_session_lang"

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_json))
            zf.writestr("responses.json", json.dumps(responses_json))
        import_buffer.seek(0)

        # Import
        imported_survey, _ = import_survey_from_zip(import_buffer)

        imported_session = SurveySession.objects.get(survey=imported_survey)
        self.assertEqual(imported_session.language, "de")

    def test_import_legacy_format_converts_option_groups_to_inline_choices(self):
        """
        GIVEN a ZIP in legacy format with option_groups and option_group_name
        WHEN imported
        THEN question has inline choices with translations from legacy format
        """
        survey_json = {
            "version": "1.0",
            "exported_at": "2026-02-08T12:00:00Z",
            "mode": "structure",
            "survey": {
                "name": "test_legacy_choice_trans",
                "organization": None,
                "redirect_url": "#",
                "available_languages": ["en", "ru"],
                "sections": [{
                    "name": "test_section",
                    "title": "Test Section",
                    "subheading": None,
                    "code": "TEST",
                    "is_head": True,
                    "start_map_position": None,
                    "start_map_zoom": 12,
                    "next_section_name": None,
                    "prev_section_name": None,
                    "translations": [],
                    "questions": [{
                        "code": "Q_LEGACY_CHOICE",
                        "order_number": 1,
                        "name": "Test question",
                        "subtext": None,
                        "input_type": "choice",
                        "required": True,
                        "color": "#000000",
                        "icon_class": None,
                        "image": None,
                        "option_group_name": "LegacyGroup",
                        "translations": [],
                        "sub_questions": []
                    }]
                }]
            },
            "option_groups": [{
                "name": "LegacyGroup",
                "choices": [
                    {
                        "name": "Choice One",
                        "code": 1,
                        "translations": [{"language": "ru", "name": "Выбор Один"}]
                    },
                    {
                        "name": "Choice Two",
                        "code": 2,
                        "translations": [{"language": "ru", "name": "Выбор Два"}]
                    }
                ]
            }]
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_json))
        import_buffer.seek(0)

        # Import
        imported_survey, warnings = import_survey_from_zip(import_buffer)

        # Verify legacy choices were converted to inline choices with translations
        imported_question = Question.objects.get(
            survey_section__survey_header=imported_survey,
            code="Q_LEGACY_CHOICE"
        )
        self.assertIsNotNone(imported_question.choices)
        self.assertEqual(len(imported_question.choices), 2)
        self.assertEqual(imported_question.get_choice_name(1, "en"), "Choice One")
        self.assertEqual(imported_question.get_choice_name(1, "ru"), "Выбор Один")
        self.assertEqual(imported_question.get_choice_name(2, "en"), "Choice Two")
        self.assertEqual(imported_question.get_choice_name(2, "ru"), "Выбор Два")


class LifecycleSerializationTest(TestCase):
    """Tests for lifecycle fields in serialization."""

    def setUp(self):
        self.org = _make_org('SerOrg')
        self.survey = SurveyHeader.objects.create(
            name='ser_test', organization=self.org, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        Question.objects.create(
            survey_section=self.section, code='Q_SER1', name='Q1', input_type='text',
        )

    def test_export_includes_status(self):
        """
        GIVEN a published survey
        WHEN serialized
        THEN status field is included
        """
        data = serialize_survey_to_dict(self.survey)
        self.assertEqual(data['status'], 'published')

    def test_export_includes_has_password(self):
        """
        GIVEN a survey with password set
        WHEN serialized
        THEN has_password is True
        """
        self.survey.set_password('test')
        self.survey.save()
        data = serialize_survey_to_dict(self.survey)
        self.assertTrue(data['has_password'])

    def test_export_excludes_password_hash(self):
        """
        GIVEN a survey with password set
        WHEN serialized
        THEN password_hash is not in the dict
        """
        self.survey.set_password('test')
        self.survey.save()
        data = serialize_survey_to_dict(self.survey)
        self.assertNotIn('password_hash', data)
        self.assertNotIn('test_token', data)

    def test_import_defaults_to_draft(self):
        """
        GIVEN a survey archive without status field
        WHEN imported
        THEN created survey has status=draft
        """
        buf = BytesIO()
        export_survey_to_zip(self.survey, buf, mode='structure')
        buf.seek(0)
        # Modify the archive to remove status
        with zipfile.ZipFile(buf, 'r') as zf:
            content = json.loads(zf.read('survey.json'))
        del content['survey']['status']
        buf2 = BytesIO()
        with zipfile.ZipFile(buf2, 'w') as zf:
            zf.writestr('survey.json', json.dumps(content))
        buf2.seek(0)
        imported_survey, _ = import_survey_from_zip(buf2, organization=self.org)
        self.assertEqual(imported_survey.status, 'draft')

    def test_import_reads_status(self):
        """
        GIVEN a survey archive with status=published
        WHEN imported
        THEN created survey has status=published
        """
        buf = BytesIO()
        export_survey_to_zip(self.survey, buf, mode='structure')
        buf.seek(0)
        imported_survey, _ = import_survey_from_zip(buf, organization=self.org)
        self.assertEqual(imported_survey.status, 'published')

    def test_import_password_warning(self):
        """
        GIVEN a survey archive with has_password=true
        WHEN imported
        THEN warnings include password not imported message
        """
        self.survey.set_password('test')
        self.survey.save()
        buf = BytesIO()
        export_survey_to_zip(self.survey, buf, mode='structure')
        buf.seek(0)
        _, warnings = import_survey_from_zip(buf, organization=self.org)
        self.assertTrue(any('password' in w.lower() for w in warnings))

    def test_import_never_restores_password(self):
        """
        GIVEN a survey with password exported
        WHEN imported
        THEN imported survey has no password
        """
        self.survey.set_password('test')
        self.survey.save()
        buf = BytesIO()
        export_survey_to_zip(self.survey, buf, mode='structure')
        buf.seek(0)
        imported_survey, _ = import_survey_from_zip(buf, organization=self.org)
        self.assertFalse(imported_survey.has_password())


class GeolocationSerializationTest(TestCase):
    """Tests for use_geolocation field in serialization."""

    def setUp(self):
        self.org = _make_org('GeoLocOrg')
        self.survey = SurveyHeader.objects.create(
            name='geoloc_test', organization=self.org, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
            use_geolocation=True,
        )
        Question.objects.create(
            survey_section=self.section, code='Q1', name='Q1', input_type='point',
        )

    def test_export_import_roundtrip_preserves_use_geolocation(self):
        """
        GIVEN a section with use_geolocation=True
        WHEN exported and re-imported
        THEN the imported section has use_geolocation=True
        """
        buf = BytesIO()
        export_survey_to_zip(self.survey, buf, mode='structure')
        buf.seek(0)
        imported_survey, _ = import_survey_from_zip(buf, organization=self.org)
        imported_section = SurveySection.objects.get(survey_header=imported_survey)
        self.assertTrue(imported_section.use_geolocation)

    def test_import_without_use_geolocation_defaults_to_false(self):
        """
        GIVEN a survey archive without use_geolocation field in section data
        WHEN imported
        THEN the imported section has use_geolocation=False
        """
        buf = BytesIO()
        export_survey_to_zip(self.survey, buf, mode='structure')
        buf.seek(0)
        with zipfile.ZipFile(buf, 'r') as zf:
            content = json.loads(zf.read('survey.json'))
        for s in content['survey']['sections']:
            s.pop('use_geolocation', None)
        buf2 = BytesIO()
        with zipfile.ZipFile(buf2, 'w') as zf:
            zf.writestr('survey.json', json.dumps(content))
        buf2.seek(0)
        imported_survey, _ = import_survey_from_zip(buf2, organization=self.org)
        imported_section = SurveySection.objects.get(survey_header=imported_survey)
        self.assertFalse(imported_section.use_geolocation)


class SerializationVersioningTest(TestCase):
    """Tests that serialization export includes version and import reads it."""

    def setUp(self):
        self.org = _make_org('SerVerOrg')
        self.survey = SurveyHeader.objects.create(
            name='ser_ver', organization=self.org, version_number=3,
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec', code='S1', is_head=True,
        )

    def test_export_includes_version(self):
        """
        GIVEN a survey at version 3
        WHEN serialize_survey_to_dict is called
        THEN the output dict includes "version": 3
        """
        result = serialize_survey_to_dict(self.survey)
        self.assertEqual(result['version'], 3)

    def test_import_reads_version(self):
        """
        GIVEN a survey.json with version 5
        WHEN import_survey_from_zip is called
        THEN the imported SurveyHeader has version_number=5
        """
        survey_data = {
            "version": FORMAT_VERSION,
            "exported_at": "2026-02-16T12:00:00Z",
            "mode": "structure",
            "survey": {
                "name": "imported_versioned",
                "organization": None,
                "redirect_url": "#",
                "available_languages": [],
                "thanks_html": {},
                "status": "draft",
                "version": 5,
                "sections": [{
                    "name": "sec",
                    "title": "Section",
                    "subheading": None,
                    "code": "S1",
                    "is_head": True,
                    "start_map_position": None,
                    "start_map_zoom": 12,
                    "next_section_name": None,
                    "prev_section_name": None,
                    "translations": [],
                    "questions": [],
                }],
            },
        }
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_data))
        buf.seek(0)

        imported_survey, _ = import_survey_from_zip(buf)
        self.assertEqual(imported_survey.version_number, 5)

    def test_import_defaults_version_to_1(self):
        """
        GIVEN a survey.json without a version field
        WHEN import_survey_from_zip is called
        THEN the imported SurveyHeader has version_number=1
        """
        survey_data = {
            "version": FORMAT_VERSION,
            "exported_at": "2026-02-16T12:00:00Z",
            "mode": "structure",
            "survey": {
                "name": "imported_no_ver",
                "organization": None,
                "redirect_url": "#",
                "available_languages": [],
                "thanks_html": {},
                "status": "draft",
                # no "version" key
                "sections": [{
                    "name": "sec",
                    "title": "Section",
                    "subheading": None,
                    "code": "S1",
                    "is_head": True,
                    "start_map_position": None,
                    "start_map_zoom": 12,
                    "next_section_name": None,
                    "prev_section_name": None,
                    "translations": [],
                    "questions": [],
                }],
            },
        }
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_data))
        buf.seek(0)

        imported_survey, _ = import_survey_from_zip(buf)
        self.assertEqual(imported_survey.version_number, 1)

    def test_import_sets_is_canonical_true(self):
        """
        GIVEN a valid survey.json for import
        WHEN import_survey_from_zip is called
        THEN the imported SurveyHeader has is_canonical=True
        """
        survey_data = {
            "version": FORMAT_VERSION,
            "exported_at": "2026-02-16T12:00:00Z",
            "mode": "structure",
            "survey": {
                "name": "imported_canonical_check",
                "organization": None,
                "redirect_url": "#",
                "available_languages": [],
                "thanks_html": {},
                "status": "draft",
                "sections": [{
                    "name": "sec",
                    "title": "Section",
                    "subheading": None,
                    "code": "S1",
                    "is_head": True,
                    "start_map_position": None,
                    "start_map_zoom": 12,
                    "next_section_name": None,
                    "prev_section_name": None,
                    "translations": [],
                    "questions": [],
                }],
            },
        }
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_data))
        buf.seek(0)

        imported_survey, _ = import_survey_from_zip(buf)
        self.assertTrue(imported_survey.is_canonical)


class StructureImageExportTest(TestCase):
    """Structure export must read question images through the storage backend.

    `question.image.path` raises `NotImplementedError: This backend doesn't
    support absolute paths` on S3, so after media moved off local disk on
    2026-08-27 the structure export 500'd for every survey with a question
    image (PostHog issue 01a04ddb, 9 events on 2026-08-29).
    """

    def setUp(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.org = _make_org('ImgExportOrg')
        self.survey = SurveyHeader.objects.create(name="img_export", organization=self.org)
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="sec", code="S1", is_head=True)
        self.question = Question.objects.create(
            survey_section=self.section, code="Q_IMG", name="Illustrated",
            input_type="text", order_number=1)
        self.question.image.save(
            'diagram.png', SimpleUploadedFile('diagram.png', b'PNGDATA', 'image/png'), save=True)

    def test_structure_export_includes_the_image_bytes(self):
        """
        GIVEN a survey with a question image
        WHEN it is exported in structure mode
        THEN the archive holds the image bytes under images/structure/
        """
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")

        output.seek(0)
        with zipfile.ZipFile(output, 'r') as zf:
            entries = [n for n in zf.namelist() if n.startswith('images/structure/')]
            self.assertEqual(len(entries), 1, zf.namelist())
            self.assertEqual(zf.read(entries[0]), b'PNGDATA')

    def test_export_survives_a_backend_that_cannot_open_the_file(self):
        """
        GIVEN a storage backend that raises on open, the way S3 raises on .path
        WHEN the survey is exported
        THEN the archive is still written and a warning names the image

        Uses the exact exception S3Boto3Storage raises for `.path`, so the test
        fails again if anyone reintroduces a path-based read.
        """
        from unittest.mock import patch

        def boom(*args, **kwargs):
            raise NotImplementedError("This backend doesn't support absolute paths.")

        output = BytesIO()
        with patch.object(type(self.question.image), 'open', boom):
            warnings = export_survey_to_zip(self.survey, output, mode="structure")

        output.seek(0)
        with zipfile.ZipFile(output, 'r') as zf:
            self.assertIn("survey.json", zf.namelist())
            self.assertFalse([n for n in zf.namelist() if n.startswith('images/structure/')])
        self.assertTrue(any('Q_IMG' in w for w in warnings), warnings)


class MalformedArchiveImportTest(TestCase):
    """A creator's bad ZIP must produce a message, not a 500.

    `survey_data.get("redirect_url", "#")[:250]` reads as safe and is not: the
    default only fires when the key is ABSENT, so `"redirect_url": null` hands
    back None and the slice raises `TypeError: 'NoneType' object is not
    subscriptable`. That was PostHog issue 01a02d72 on 2026-08-23, on
    /editor/import/. Every archive field is content from outside this
    installation, and a hand-edited or foreign survey.json can null out or
    retype any of them.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='importer', password='pass')
        self.org = _make_org('ImportOrg')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='importer', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def _archive(self, survey_obj):
        """A minimal structure-only ZIP carrying the given survey dict."""
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('survey.json', json.dumps({
                'version': '1.0',
                'exported_at': '2026-08-30T00:00:00Z',
                'mode': 'structure',
                'survey': survey_obj,
            }))
        buf.seek(0)
        return buf

    def _valid_survey(self, **overrides):
        data = {
            'name': 'Imported survey',
            'redirect_url': '#',
            'available_languages': [],
            'sections': [{
                'name': 'first',
                'code': 'S1',
                'is_head': True,
                'questions': [{'code': 'Q1', 'name': 'Q', 'input_type': 'text_line'}],
            }],
        }
        data.update(overrides)
        return data

    def test_baseline_archive_imports(self):
        """
        GIVEN a well-formed structure archive
        WHEN it is imported
        THEN a survey is created

        Without this the null cases below could pass for the wrong reason.
        """
        survey, warnings = import_survey_from_zip(
            self._archive(self._valid_survey()),
            organization=self.org, created_by=self.user)
        self.assertIsNotNone(survey)
        self.assertEqual(survey.name, 'Imported survey')

    def test_explicit_null_text_field_is_treated_as_absent(self):
        """
        GIVEN an archive whose redirect_url is explicitly null
        WHEN it is imported
        THEN the import succeeds and the field falls back to its default

        This is the exact payload shape that produced the reported 500.
        """
        survey, _ = import_survey_from_zip(
            self._archive(self._valid_survey(redirect_url=None)),
            organization=self.org, created_by=self.user)
        self.assertIsNotNone(survey)
        self.assertEqual(survey.redirect_url, '#')

    def test_null_optional_fields_across_the_tree_do_not_raise(self):
        """
        GIVEN nulls in optional section and question fields
        WHEN the archive is imported
        THEN it still imports, treating each null as an absent key
        """
        data = self._valid_survey()
        data['sections'][0]['title'] = None
        data['sections'][0]['code'] = None
        data['sections'][0]['questions'][0]['color'] = None
        data['sections'][0]['questions'][0]['icon_class'] = None
        survey, _ = import_survey_from_zip(
            self._archive(data), organization=self.org, created_by=self.user)
        self.assertIsNotNone(survey)

    def test_missing_required_field_is_a_message_not_a_crash(self):
        """
        GIVEN an archive whose section has no name
        WHEN it is imported
        THEN a ImportError names the problem
        """
        data = self._valid_survey()
        del data['sections'][0]['name']
        with self.assertRaises(ImportError) as ctx:
            import_survey_from_zip(self._archive(data),
                                   organization=self.org, created_by=self.user)
        self.assertIn('name', str(ctx.exception))

    def test_wrongly_typed_field_is_a_message_not_a_crash(self):
        """
        GIVEN an archive where a list appears where text belongs
        WHEN it is imported
        THEN the archive is rejected with a readable error rather than a 500

        The catch-all matters more than any single field: an archive's fields
        cannot all be enumerated, so the shape errors a foreign file produces
        have to degrade to a message by default.
        """
        data = self._valid_survey()
        data['sections'][0]['questions'][0]['choices'] = {'not': 'a list'}
        try:
            import_survey_from_zip(self._archive(data),
                                   organization=self.org, created_by=self.user)
        except ImportError:
            pass  # rejected cleanly — the point of the test
        except Exception as exc:  # noqa: BLE001 - that is exactly what must not happen
            self.fail(f'a malformed archive raised {type(exc).__name__} instead of ImportError: {exc}')

    def test_import_view_shows_a_message_for_a_bad_archive(self):
        """
        GIVEN a creator uploading an archive with a null required field
        WHEN they POST it to the import view and the job runs
        THEN they are redirected, not served a 500, and the dashboard card names
             the field that failed
        """
        data = self._valid_survey(name=None)
        with _eager_import():
            response = self.client.post('/editor/import/',
                                        {'file': self._archive(data)}, follow=True)
        self.assertEqual(response.status_code, 200)
        from survey.models import SurveyImportJob
        job = SurveyImportJob.objects.get(user=self.user)
        self.assertEqual(job.status, 'failed')
        self.assertIn('name', job.error)
        dashboard = self.client.get('/editor/?dashboard=1')
        self.assertContains(dashboard, 'data-import-status="failed"')
        self.assertContains(dashboard, 'name')


class SurveyImportJobTest(TestCase):
    """Change layer-memory-diet, stage 3: the ZIP import is a tracked job on the
    worker, and the dashboard is the creator's window on it."""

    def setUp(self):
        self.org = Organization.objects.create(name="Import Job Org")
        self.user = User.objects.create_user(username='importer', password='pw12345678')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.other = User.objects.create_user(username='bystander', password='pw12345678')
        Membership.objects.create(user=self.other, organization=self.org, role='editor')
        self.client.login(username='importer', password='pw12345678')
        session = self.client.session
        session['active_org_id'] = self.org.pk
        session.save()

    def _archive(self, name='job_test_survey'):
        from io import BytesIO
        import zipfile
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('survey.json', json.dumps({
                'version': '1.0', 'exported_at': '2026-09-16T00:00:00Z', 'mode': 'structure',
                'survey': {'name': name, 'sections': [
                    {'name': 'section_1', 'code': 'S1', 'is_head': True, 'questions': []},
                ]},
                'option_groups': [],
            }))
        buf.seek(0)
        from django.core.files.uploadedfile import SimpleUploadedFile
        return SimpleUploadedFile(f'{name}.zip', buf.read(), content_type='application/zip')

    def test_post_stores_the_archive_and_enqueues_a_job(self):
        """
        GIVEN an org editor uploading an archive
        WHEN they POST to the import URL
        THEN a queued job holds the archive under a random private key, the task is
             enqueued with the job id, and the dashboard shows a polling card
        """
        from unittest.mock import patch
        from survey.models import SurveyImportJob
        with patch('survey.views.run_survey_import.delay') as delay:
            r = self.client.post('/editor/import/', {'file': self._archive()})
        self.assertEqual(r.status_code, 302)
        job = SurveyImportJob.objects.get(user=self.user)
        self.assertEqual(job.status, 'queued')
        self.assertEqual(job.original_name, 'job_test_survey.zip')
        self.assertTrue(job.file.name.startswith('import_jobs/'))
        self.assertNotIn('job_test_survey', job.file.name)
        delay.assert_called_once_with(job.pk)
        r = self.client.get('/editor/?dashboard=1')
        self.assertContains(r, 'data-import-status="queued"')
        self.assertContains(r, 'hx-trigger="every 3s"')
        job.discard_file()

    def test_task_imports_and_removes_the_archive(self):
        """
        GIVEN a queued job
        WHEN the worker runs it
        THEN the survey exists with the creator as owner, the job is done with the
             survey linked, the archive is gone, and a redelivery imports nothing twice
        """
        from unittest.mock import patch
        from survey.models import SurveyImportJob
        from survey.tasks import run_survey_import
        with patch('survey.views.run_survey_import.delay'):
            self.client.post('/editor/import/', {'file': self._archive()})
        job = SurveyImportJob.objects.get(user=self.user)
        run_survey_import(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, 'done', job.error)
        self.assertEqual(job.survey.name, 'job_test_survey')
        self.assertEqual(job.survey.organization, self.org)
        self.assertTrue(SurveyCollaborator.objects.filter(user=self.user, survey=job.survey, role='owner').exists())
        self.assertFalse(job.file)
        self.assertIsNotNone(job.finished_at)
        run_survey_import(job.pk)
        self.assertEqual(SurveyHeader.objects.filter(name='job_test_survey').count(), 1)
        r = self.client.get('/editor/?dashboard=1')
        self.assertContains(r, 'data-import-status="done"')
        self.assertNotContains(r, 'hx-trigger="every 3s"')
        self.assertContains(r, reverse('editor_survey_detail', args=[job.survey.uuid]))

    def test_invalid_archive_fails_the_job_with_the_reason(self):
        """
        GIVEN an upload that is not a ZIP archive
        WHEN the worker runs the job
        THEN the job is failed with a creator-readable reason, the file is gone,
             and the card shows the reason
        """
        from django.core.files.uploadedfile import SimpleUploadedFile
        from survey.models import SurveyImportJob
        bad = SimpleUploadedFile('broken.zip', b'not a zip', content_type='application/zip')
        with _eager_import():
            r = self.client.post('/editor/import/', {'file': bad})
        self.assertEqual(r.status_code, 302)
        job = SurveyImportJob.objects.get(user=self.user)
        self.assertEqual(job.status, 'failed')
        self.assertTrue(job.error)
        self.assertFalse(job.file)
        r = self.client.get('/editor/?dashboard=1')
        self.assertContains(r, 'data-import-status="failed"')
        self.assertContains(r, job.error)

    def test_cards_are_private_and_dismissable(self):
        """
        GIVEN a finished job of one creator
        WHEN another member of the org opens the dashboard, and the owner dismisses the card
        THEN the other member never sees it, an open job cannot be dismissed, and a
             dismissed card is gone
        """
        from survey.models import SurveyImportJob
        with _eager_import():
            self.client.post('/editor/import/', {'file': self._archive('dismiss_me')})
        job = SurveyImportJob.objects.get(user=self.user)
        other = Client()
        other.login(username='bystander', password='pw12345678')
        session = other.session
        session['active_org_id'] = self.org.pk
        session.save()
        self.assertNotContains(other.get('/editor/?dashboard=1'), 'data-import-job=')
        self.assertEqual(other.post(reverse('editor_import_job_dismiss', args=[job.pk])).status_code, 404)
        SurveyImportJob.objects.filter(pk=job.pk).update(status='running')
        self.assertEqual(self.client.post(reverse('editor_import_job_dismiss', args=[job.pk])).status_code, 400)
        SurveyImportJob.objects.filter(pk=job.pk).update(status='done')
        r = self.client.post(reverse('editor_import_job_dismiss', args=[job.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(SurveyImportJob.objects.filter(pk=job.pk).exists())
        self.assertNotContains(r, 'data-import-job=')


class SessionSourceSerializationTest(TestCase):
    """Delta of change operator-entry: the responses file carries the session source."""

    def setUp(self):
        org = Organization.objects.create(name='Source Ser Org')
        self.clerk = User.objects.create_user('ser_clerk', password='x')
        self.survey = SurveyHeader.objects.create(name='source_ser', organization=org, redirect_url='#')

    def test_session_with_source_round_trips(self):
        """
        GIVEN a paper session entered by ser_clerk
        WHEN sessions are serialized and a session is created back from the data
        THEN the data reads paper and the operator's username, and the copy is paper
        """
        from survey.serialization import create_session
        SurveySession.objects.create(survey=self.survey, source='paper', entered_by=self.clerk)
        data = serialize_sessions(self.survey)[0]
        self.assertEqual((data['source'], data['entered_by']), ('paper', 'ser_clerk'))
        copy = create_session(self.survey, data)
        self.assertEqual(copy.source, 'paper')
        self.assertIsNone(copy.entered_by)

    def test_old_responses_file_reads_online(self):
        """
        GIVEN session data without `source` (an archive from before the field) or with an unknown one
        WHEN a session is created from it
        THEN it reads `online`
        """
        from survey.serialization import create_session
        self.assertEqual(create_session(self.survey, {}).source, 'online')
        self.assertEqual(create_session(self.survey, {'source': 'fax'}).source, 'online')
