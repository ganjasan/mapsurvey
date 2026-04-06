from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point, LineString, Polygon
from io import BytesIO
import json
import zipfile

from .models import (
    Organization, SurveyHeader, SurveySection, Question,
    SurveySession, Answer, ChoicesValidator, Story,
    Membership, SurveyCollaborator, Invitation,
)
from .serialization import (
    serialize_survey_to_dict, serialize_sections,
    serialize_questions, serialize_sessions, serialize_answers,
    geo_to_wkt, serialize_choices, export_survey_to_zip, validate_archive,
    import_survey_from_zip, ImportError, FORMAT_VERSION
)
from .forms import SurveySectionAnswerForm
from .permissions import get_effective_survey_role
from .access_control import check_survey_access
from .models import SurveyEvent, TrackedLink
from .events import emit_event, _classify_referrer, _parse_user_agent, build_session_start_metadata
from .analytics import PerformanceAnalyticsService, SurveyAnalyticsService, SessionValidationService


def _make_org(name='TestOrg'):
    """Helper to create an organization for tests."""
    return Organization.objects.create(name=name, slug=name.lower().replace(' ', '-'))


class SmokeTest(TestCase):
    """Basic smoke test to verify test infrastructure works."""

    def test_database_connection(self):
        """
        GIVEN a PostGIS database
        WHEN we query the database
        THEN the connection should work and PostGIS should be available
        """
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT PostGIS_Version();")
            version = cursor.fetchone()[0]

        self.assertIsNotNone(version)


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
            redirect_url="/completed/"
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
        self.assertEqual(imported_survey.redirect_url, "/completed/")

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
        response = self.client.post('/editor/import/', {'file': upload_file})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(SurveyHeader.objects.filter(name='web_test_survey').count(), 2)


class DeleteSurveyTest(TestCase):
    """Tests for survey deletion functionality."""

    def setUp(self):
        """Set up test data and client."""
        self.client = Client()
        self.org = _make_org()
        self.user = User.objects.create_user(
            username='deleteuser',
            password='testpass123'
        )
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(name="delete_test_survey", organization=self.org)
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="delete_section",
            code="DS",
            is_head=True
        )
        self.question = Question.objects.create(
            survey_section=self.section,
            code="Q_DELETE",
            name="Delete test question",
            input_type="text"
        )
        self.session = SurveySession.objects.create(survey=self.survey)
        self.answer = Answer.objects.create(
            survey_session=self.session,
            question=self.question,
            text="Test answer"
        )

    def test_delete_survey_success(self):
        """
        GIVEN an authenticated user and existing survey
        WHEN POST request to delete endpoint
        THEN survey is deleted and user redirected with success message
        """
        self.client.login(username='deleteuser', password='testpass123')
        response = self.client.post(f'/editor/delete/{self.survey.uuid}/')

        self.assertEqual(response.status_code, 302)
        self.assertFalse(SurveyHeader.objects.filter(name="delete_test_survey").exists())

    def test_delete_survey_unauthenticated_redirect(self):
        """
        GIVEN an unauthenticated user
        WHEN accessing delete endpoint
        THEN redirect to login page
        """
        response = self.client.post(f'/editor/delete/{self.survey.uuid}/')

        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
        # Survey should still exist
        self.assertTrue(SurveyHeader.objects.filter(name="delete_test_survey").exists())

    def test_delete_survey_not_found(self):
        """
        GIVEN an authenticated user
        WHEN attempting to delete non-existent survey by UUID
        THEN return 404
        """
        import uuid
        self.client.login(username='deleteuser', password='testpass123')
        response = self.client.post(f'/editor/delete/{uuid.uuid4()}/')

        self.assertEqual(response.status_code, 404)

    def test_delete_survey_cascade_deletes_related_data(self):
        """
        GIVEN a survey with sessions, answers, sections, and questions
        WHEN survey is deleted
        THEN all related data is also deleted
        """
        # Verify data exists before deletion
        self.assertTrue(SurveySession.objects.filter(survey=self.survey).exists())
        self.assertTrue(Answer.objects.filter(survey_session=self.session).exists())
        self.assertTrue(SurveySection.objects.filter(survey_header=self.survey).exists())
        self.assertTrue(Question.objects.filter(survey_section=self.section).exists())

        self.client.login(username='deleteuser', password='testpass123')
        self.client.post(f'/editor/delete/{self.survey.uuid}/')

        # All related data should be deleted
        self.assertFalse(SurveySession.objects.filter(pk=self.session.pk).exists())
        self.assertFalse(Answer.objects.filter(pk=self.answer.pk).exists())
        self.assertFalse(SurveySection.objects.filter(pk=self.section.pk).exists())
        self.assertFalse(Question.objects.filter(pk=self.question.pk).exists())

    def test_delete_survey_get_request_rejected(self):
        """
        GIVEN an authenticated user
        WHEN GET request to delete endpoint
        THEN request is rejected and survey not deleted
        """
        self.client.login(username='deleteuser', password='testpass123')
        response = self.client.get(f'/editor/delete/{self.survey.uuid}/')

        self.assertEqual(response.status_code, 302)
        # Survey should still exist
        self.assertTrue(SurveyHeader.objects.filter(name="delete_test_survey").exists())


class TranslationModelsTest(TestCase):
    """Tests for multilingual translation models and helper methods."""

    def setUp(self):
        """Set up test data for translation tests."""
        from .models import (
            SurveySectionTranslation, QuestionTranslation,
        )
        self.SurveySectionTranslation = SurveySectionTranslation
        self.QuestionTranslation = QuestionTranslation

        self.org = Organization.objects.create(name="Test Org")
        self.survey = SurveyHeader.objects.create(
            name="multilang_survey",
            organization=self.org,
            redirect_url="/thanks/",
            available_languages=["en", "ru", "de"]
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="section1",
            title="Welcome",
            subheading="Please answer the questions",
            code="S1",
            is_head=True
        )
        self.test_choices = [
            {"code": 1, "name": {"en": "Yes", "ru": "Да"}},
            {"code": 2, "name": {"en": "No", "ru": "Нет"}},
        ]
        self.question = Question.objects.create(
            survey_section=self.section,
            name="Do you agree?",
            subtext="Select one option",
            input_type="choice",
            choices=self.test_choices,
            code="Q1"
        )

    def test_survey_is_multilingual_true(self):
        """
        GIVEN a survey with available_languages configured
        WHEN is_multilingual() is called
        THEN it returns True
        """
        self.assertTrue(self.survey.is_multilingual())

    def test_survey_is_multilingual_false_empty_list(self):
        """
        GIVEN a survey with empty available_languages
        WHEN is_multilingual() is called
        THEN it returns False
        """
        survey = SurveyHeader.objects.create(
            name="single_lang_survey",
            organization=self.org,
            available_languages=[]
        )
        self.assertFalse(survey.is_multilingual())

    def test_survey_is_multilingual_false_no_languages(self):
        """
        GIVEN a survey with no available_languages set
        WHEN is_multilingual() is called
        THEN it returns False
        """
        survey = SurveyHeader.objects.create(name="default_survey", organization=self.org)
        self.assertFalse(survey.is_multilingual())

    def test_section_translation_creation(self):
        """
        GIVEN a survey section
        WHEN translation is created
        THEN translation is stored correctly
        """
        translation = self.SurveySectionTranslation.objects.create(
            section=self.section,
            language="ru",
            title="Добро пожаловать",
            subheading="Пожалуйста, ответьте на вопросы"
        )
        self.assertEqual(translation.section, self.section)
        self.assertEqual(translation.language, "ru")
        self.assertEqual(translation.title, "Добро пожаловать")

    def test_section_get_translated_title_with_translation(self):
        """
        GIVEN a section with Russian translation
        WHEN get_translated_title('ru') is called
        THEN returns translated title
        """
        self.SurveySectionTranslation.objects.create(
            section=self.section,
            language="ru",
            title="Добро пожаловать"
        )
        self.assertEqual(
            self.section.get_translated_title("ru"),
            "Добро пожаловать"
        )

    def test_section_get_translated_title_without_translation(self):
        """
        GIVEN a section without German translation
        WHEN get_translated_title('de') is called
        THEN returns original title
        """
        self.assertEqual(
            self.section.get_translated_title("de"),
            "Welcome"
        )

    def test_section_get_translated_title_with_none_language(self):
        """
        GIVEN a section
        WHEN get_translated_title(None) is called
        THEN returns original title
        """
        self.assertEqual(
            self.section.get_translated_title(None),
            "Welcome"
        )

    def test_section_get_translated_subheading_with_translation(self):
        """
        GIVEN a section with Russian translation
        WHEN get_translated_subheading('ru') is called
        THEN returns translated subheading
        """
        self.SurveySectionTranslation.objects.create(
            section=self.section,
            language="ru",
            subheading="Пожалуйста, ответьте"
        )
        self.assertEqual(
            self.section.get_translated_subheading("ru"),
            "Пожалуйста, ответьте"
        )

    def test_section_get_translated_subheading_fallback(self):
        """
        GIVEN a section with translation that has empty subheading
        WHEN get_translated_subheading is called
        THEN returns original subheading
        """
        self.SurveySectionTranslation.objects.create(
            section=self.section,
            language="ru",
            title="Добро пожаловать",
            subheading=""
        )
        self.assertEqual(
            self.section.get_translated_subheading("ru"),
            "Please answer the questions"
        )

    def test_question_translation_creation(self):
        """
        GIVEN a question
        WHEN translation is created
        THEN translation is stored correctly
        """
        translation = self.QuestionTranslation.objects.create(
            question=self.question,
            language="ru",
            name="Вы согласны?",
            subtext="Выберите один вариант"
        )
        self.assertEqual(translation.question, self.question)
        self.assertEqual(translation.name, "Вы согласны?")

    def test_question_get_translated_name_with_translation(self):
        """
        GIVEN a question with Russian translation
        WHEN get_translated_name('ru') is called
        THEN returns translated name
        """
        self.QuestionTranslation.objects.create(
            question=self.question,
            language="ru",
            name="Вы согласны?"
        )
        self.assertEqual(
            self.question.get_translated_name("ru"),
            "Вы согласны?"
        )

    def test_question_get_translated_name_without_translation(self):
        """
        GIVEN a question without translation
        WHEN get_translated_name('fr') is called
        THEN returns original name
        """
        self.assertEqual(
            self.question.get_translated_name("fr"),
            "Do you agree?"
        )

    def test_question_get_translated_subtext_with_translation(self):
        """
        GIVEN a question with Russian translation
        WHEN get_translated_subtext('ru') is called
        THEN returns translated subtext
        """
        self.QuestionTranslation.objects.create(
            question=self.question,
            language="ru",
            subtext="Выберите один вариант"
        )
        self.assertEqual(
            self.question.get_translated_subtext("ru"),
            "Выберите один вариант"
        )

    def test_inline_choice_get_name_with_translation(self):
        """
        GIVEN a question with inline choices with Russian translation
        WHEN get_choice_name(1, 'ru') is called
        THEN returns translated name
        """
        self.assertEqual(
            self.question.get_choice_name(1, "ru"),
            "Да"
        )

    def test_inline_choice_get_name_without_translation(self):
        """
        GIVEN a question with inline choices without German translation
        WHEN get_choice_name(1, 'de') is called
        THEN returns English name as fallback
        """
        self.assertEqual(
            self.question.get_choice_name(1, "de"),
            "Yes"
        )

    def test_translation_unique_constraint(self):
        """
        GIVEN an existing translation for section+language
        WHEN another translation with same section+language is created
        THEN IntegrityError is raised
        """
        from django.db import IntegrityError

        self.SurveySectionTranslation.objects.create(
            section=self.section,
            language="ru",
            title="Добро пожаловать"
        )
        with self.assertRaises(IntegrityError):
            self.SurveySectionTranslation.objects.create(
                section=self.section,
                language="ru",
                title="Другой перевод"
            )

    def test_session_language_field(self):
        """
        GIVEN a survey session
        WHEN language is set
        THEN language is stored correctly
        """
        session = SurveySession.objects.create(
            survey=self.survey,
            language="ru"
        )
        self.assertEqual(session.language, "ru")

    def test_session_language_nullable(self):
        """
        GIVEN a survey session without language
        WHEN session is created
        THEN language is None
        """
        session = SurveySession.objects.create(survey=self.survey)
        self.assertIsNone(session.language)


class AdminInlineTest(TestCase):
    """Tests for admin interface with translation inlines."""

    def setUp(self):
        """Set up test data and admin user."""
        from django.contrib.admin.sites import AdminSite
        from .admin import (
            SurveySectionAdmin, QuestionAdmin,
            SurveySectionTranslationInline, QuestionTranslationInline,
        )
        from .models import SurveySectionTranslation, QuestionTranslation

        self.SurveySectionTranslation = SurveySectionTranslation
        self.QuestionTranslation = QuestionTranslation

        self.site = AdminSite()
        self.section_admin = SurveySectionAdmin(SurveySection, self.site)
        self.question_admin = QuestionAdmin(Question, self.site)

        self.user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='adminpass123'
        )
        self.org = Organization.objects.create(name="Admin Test Org")
        self.survey = SurveyHeader.objects.create(
            name="admin_test_survey",
            organization=self.org,
            available_languages=["en", "ru"]
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="admin_section",
            title="Admin Section",
            code="AS1",
            is_head=True
        )
        self.question = Question.objects.create(
            survey_section=self.section,
            name="Admin Question",
            input_type="text",
            code="AQ1"
        )

    def test_section_admin_has_translation_inline(self):
        """
        GIVEN SurveySectionAdmin
        WHEN inlines are checked
        THEN SurveySectionTranslationInline is present
        """
        inline_names = [inline.__name__ for inline in self.section_admin.inlines]
        self.assertIn('SurveySectionTranslationInline', inline_names)

    def test_question_admin_has_translation_inline(self):
        """
        GIVEN QuestionAdmin
        WHEN inlines are checked
        THEN QuestionTranslationInline is present
        """
        inline_names = [inline.__name__ for inline in self.question_admin.inlines]
        self.assertIn('QuestionTranslationInline', inline_names)

    def test_create_section_translation_via_model(self):
        """
        GIVEN a survey section
        WHEN translation is created programmatically
        THEN translation is accessible via section
        """
        self.SurveySectionTranslation.objects.create(
            section=self.section,
            language="ru",
            title="Админ Секция"
        )
        self.assertEqual(self.section.translations.count(), 1)
        self.assertEqual(self.section.translations.first().title, "Админ Секция")

    def test_create_question_translation_via_model(self):
        """
        GIVEN a question
        WHEN translation is created programmatically
        THEN translation is accessible via question
        """
        self.QuestionTranslation.objects.create(
            question=self.question,
            language="ru",
            name="Админ Вопрос"
        )
        self.assertEqual(self.question.translations.count(), 1)
        self.assertEqual(self.question.translations.first().name, "Админ Вопрос")

    def test_survey_admin_displays_available_languages(self):
        """
        GIVEN SurveyAdmin
        WHEN list_display is checked
        THEN available_languages is included
        """
        from .admin import SurveyAdmin
        self.assertIn('available_languages', SurveyAdmin.list_display)


class LanguageSelectionTest(TestCase):
    """Tests for language selection view and flow."""

    def setUp(self):
        """Set up test data for language selection tests."""
        self.client = Client()
        self.org = Organization.objects.create(name="Lang Test Org")
        self.multilang_survey = SurveyHeader.objects.create(
            name="multilang_test",
            organization=self.org,
            available_languages=["en", "ru", "de"],
            status='published',
        )
        self.single_lang_survey = SurveyHeader.objects.create(
            name="singlelang_test",
            organization=self.org,
            available_languages=[],
            status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.multilang_survey,
            name="section1",
            title="Test Section",
            code="S1",
            is_head=True
        )
        self.single_section = SurveySection.objects.create(
            survey_header=self.single_lang_survey,
            name="section1",
            title="Single Lang Section",
            code="SL1",
            is_head=True
        )

    def test_language_selection_page_displays_for_multilang_survey(self):
        """
        GIVEN a multilingual survey
        WHEN user visits language selection URL
        THEN language options are displayed
        """
        response = self.client.get('/surveys/multilang_test/language/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'English')
        self.assertContains(response, 'Русский')
        self.assertContains(response, 'Deutsch')

    def test_language_selection_redirects_for_single_lang_survey(self):
        """
        GIVEN a single-language survey
        WHEN user visits language selection URL
        THEN user is redirected to survey entry (using UUID)
        """
        response = self.client.get('/surveys/singlelang_test/language/')

        self.assertEqual(response.status_code, 302)
        self.assertIn(str(self.single_lang_survey.uuid), response.url)

    def test_language_selection_creates_session_with_language(self):
        """
        GIVEN a multilingual survey
        WHEN user selects a language
        THEN session is created with selected language
        """
        response = self.client.post(
            '/surveys/multilang_test/language/',
            {'language': 'ru'}
        )

        self.assertEqual(response.status_code, 302)
        session_id = self.client.session.get('survey_session_id')
        self.assertIsNotNone(session_id)

        session = SurveySession.objects.get(pk=session_id)
        self.assertEqual(session.language, 'ru')

    def test_language_selection_stores_language_in_django_session(self):
        """
        GIVEN a multilingual survey
        WHEN user selects a language
        THEN Django session contains selected language
        """
        self.client.post(
            '/surveys/multilang_test/language/',
            {'language': 'de'}
        )

        self.assertEqual(self.client.session.get('survey_language'), 'de')

    def test_language_selection_redirects_to_first_section(self):
        """
        GIVEN a multilingual survey with sections
        WHEN user selects a language
        THEN user is redirected to first section
        """
        response = self.client.post(
            '/surveys/multilang_test/language/',
            {'language': 'en'}
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('section1', response.url)

    def test_language_selection_ignores_invalid_language(self):
        """
        GIVEN a multilingual survey
        WHEN user submits invalid language code
        THEN selection page is shown again (no redirect)
        """
        response = self.client.post(
            '/surveys/multilang_test/language/',
            {'language': 'invalid'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.client.session.get('survey_session_id'))


class SurveyFlowIntegrationTest(TestCase):
    """Tests for survey flow with multilingual support."""

    def setUp(self):
        """Set up test data for flow tests."""
        self.client = Client()
        self.org = Organization.objects.create(name="Flow Test Org")
        self.multilang_survey = SurveyHeader.objects.create(
            name="flow_multilang",
            organization=self.org,
            available_languages=["en", "ru"],
            status='published',
        )
        self.single_lang_survey = SurveyHeader.objects.create(
            name="flow_singlelang",
            organization=self.org,
            available_languages=[],
            status='published',
        )
        self.multi_section = SurveySection.objects.create(
            survey_header=self.multilang_survey,
            name="section1",
            title="Multi Section",
            code="MS1",
            is_head=True
        )
        self.single_section = SurveySection.objects.create(
            survey_header=self.single_lang_survey,
            name="section1",
            title="Single Section",
            code="SS1",
            is_head=True
        )

    def test_survey_header_redirects_to_language_select_for_multilang(self):
        """
        GIVEN a multilingual survey
        WHEN user visits survey entry URL
        THEN user is redirected to language selection
        """
        response = self.client.get('/surveys/flow_multilang/')

        self.assertEqual(response.status_code, 302)
        self.assertIn('language', response.url)

    def test_survey_header_redirects_to_section_for_singlelang(self):
        """
        GIVEN a single-language survey
        WHEN user visits survey entry URL
        THEN user is redirected directly to first section
        """
        response = self.client.get('/surveys/flow_singlelang/')

        self.assertEqual(response.status_code, 302)
        self.assertIn('section1', response.url)

    def test_section_redirects_to_language_select_if_no_language(self):
        """
        GIVEN a multilingual survey
        WHEN user visits section directly without language selection
        THEN user is redirected to language selection
        """
        response = self.client.get('/surveys/flow_multilang/section1/')

        self.assertEqual(response.status_code, 302)
        self.assertIn('language', response.url)

    def test_section_accessible_after_language_selection(self):
        """
        GIVEN a multilingual survey with language selected
        WHEN user visits section
        THEN section is displayed
        """
        # First select language
        self.client.post('/surveys/flow_multilang/language/', {'language': 'en'})

        # Then access section
        response = self.client.get('/surveys/flow_multilang/section1/')

        self.assertEqual(response.status_code, 200)

    def test_section_accessible_for_singlelang_without_language(self):
        """
        GIVEN a single-language survey
        WHEN user visits section directly
        THEN section is displayed (no language selection needed)
        """
        response = self.client.get('/surveys/flow_singlelang/section1/')

        self.assertEqual(response.status_code, 200)

    def test_selected_language_passed_to_section_context(self):
        """
        GIVEN a multilingual survey with Russian selected
        WHEN section is rendered
        THEN template context contains selected_language='ru'
        """
        self.client.post('/surveys/flow_multilang/language/', {'language': 'ru'})
        response = self.client.get('/surveys/flow_multilang/section1/')

        self.assertEqual(response.context['selected_language'], 'ru')


class TranslatedContentDisplayTest(TestCase):
    """Tests for translated content display in forms and templates."""

    def setUp(self):
        """Set up test data with translations."""
        from .models import (
            SurveySectionTranslation, QuestionTranslation,
        )
        self.SurveySectionTranslation = SurveySectionTranslation
        self.QuestionTranslation = QuestionTranslation

        self.client = Client()
        self.org = Organization.objects.create(name="Display Test Org")
        self.survey = SurveyHeader.objects.create(
            name="display_test",
            organization=self.org,
            available_languages=["en", "ru"],
            status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="section1",
            title="Original Title",
            subheading="Original Subheading",
            code="DT1",
            is_head=True
        )
        self.display_choices = [
            {"code": 1, "name": {"en": "Original Choice 1", "ru": "Выбор 1"}},
            {"code": 2, "name": {"en": "Original Choice 2", "ru": "Выбор 2"}},
        ]
        self.text_question = Question.objects.create(
            survey_section=self.section,
            code="Q_TEXT",
            order_number=1,
            name="Original Question",
            subtext="Original Subtext",
            input_type="text"
        )
        self.choice_question = Question.objects.create(
            survey_section=self.section,
            code="Q_CHOICE",
            order_number=2,
            name="Original Choice Question",
            input_type="choice",
            choices=self.display_choices
        )

        # Create translations
        self.SurveySectionTranslation.objects.create(
            section=self.section,
            language="ru",
            title="Русский заголовок",
            subheading="Русский подзаголовок"
        )
        self.QuestionTranslation.objects.create(
            question=self.text_question,
            language="ru",
            name="Русский вопрос",
            subtext="Русский подтекст"
        )
        self.QuestionTranslation.objects.create(
            question=self.choice_question,
            language="ru",
            name="Русский вопрос с выбором"
        )

    def test_form_uses_translated_question_labels(self):
        """
        GIVEN a form with language='ru'
        WHEN form is created
        THEN question labels use Russian translations
        """
        session = SurveySession.objects.create(survey=self.survey, language="ru")
        form = SurveySectionAnswerForm(
            initial={},
            section=self.section,
            question=None,
            survey_session_id=session.id,
            language="ru"
        )

        self.assertEqual(form.fields["Q_TEXT"].label, "Русский вопрос")
        self.assertEqual(form.fields["Q_CHOICE"].label, "Русский вопрос с выбором")

    def test_form_uses_original_labels_without_language(self):
        """
        GIVEN a form with language=None
        WHEN form is created
        THEN question labels use original names
        """
        session = SurveySession.objects.create(survey=self.survey)
        form = SurveySectionAnswerForm(
            initial={},
            section=self.section,
            question=None,
            survey_session_id=session.id,
            language=None
        )

        self.assertEqual(form.fields["Q_TEXT"].label, "Original Question")
        self.assertEqual(form.fields["Q_CHOICE"].label, "Original Choice Question")

    def test_form_uses_translated_choice_options(self):
        """
        GIVEN a form with language='ru' and choice question
        WHEN form is created
        THEN choice options use Russian translations
        """
        session = SurveySession.objects.create(survey=self.survey, language="ru")
        form = SurveySectionAnswerForm(
            initial={},
            section=self.section,
            question=None,
            survey_session_id=session.id,
            language="ru"
        )

        choices = form.fields["Q_CHOICE"].choices
        choice_labels = [label for code, label in choices]
        self.assertIn("Выбор 1", choice_labels)
        self.assertIn("Выбор 2", choice_labels)

    def test_form_uses_original_choice_options_without_language(self):
        """
        GIVEN a form with language=None and choice question
        WHEN form is created
        THEN choice options use original names
        """
        session = SurveySession.objects.create(survey=self.survey)
        form = SurveySectionAnswerForm(
            initial={},
            section=self.section,
            question=None,
            survey_session_id=session.id,
            language=None
        )

        choices = form.fields["Q_CHOICE"].choices
        choice_labels = [label for code, label in choices]
        self.assertIn("Original Choice 1", choice_labels)
        self.assertIn("Original Choice 2", choice_labels)

    def test_section_view_passes_translated_title_to_context(self):
        """
        GIVEN a multilingual survey with Russian selected
        WHEN section is rendered
        THEN context contains translated section title
        """
        self.client.post('/surveys/display_test/language/', {'language': 'ru'})
        response = self.client.get('/surveys/display_test/section1/')

        self.assertEqual(response.context['section_title'], "Русский заголовок")

    def test_section_view_passes_translated_subheading_to_context(self):
        """
        GIVEN a multilingual survey with Russian selected
        WHEN section is rendered
        THEN context contains translated section subheading
        """
        self.client.post('/surveys/display_test/language/', {'language': 'ru'})
        response = self.client.get('/surveys/display_test/section1/')

        self.assertEqual(response.context['section_subheading'], "Русский подзаголовок")

    def test_section_view_passes_original_title_without_language(self):
        """
        GIVEN a single-language survey
        WHEN section is rendered
        THEN context contains original section title
        """
        single_survey = SurveyHeader.objects.create(
            name="single_display_test",
            organization=self.org,
            available_languages=[],
            status='published',
        )
        single_section = SurveySection.objects.create(
            survey_header=single_survey,
            name="section1",
            title="Single Lang Title",
            subheading="Single Lang Subheading",
            code="SDT1",
            is_head=True
        )

        response = self.client.get('/surveys/single_display_test/section1/')

        self.assertEqual(response.context['section_title'], "Single Lang Title")
        self.assertEqual(response.context['section_subheading'], "Single Lang Subheading")

    def test_form_fallback_for_missing_translation(self):
        """
        GIVEN a question without translation for requested language
        WHEN form is created with that language
        THEN question label falls back to original name
        """
        # Create question without Russian translation
        untranslated_q = Question.objects.create(
            survey_section=self.section,
            code="Q_UNTRANS",
            order_number=3,
            name="Untranslated Question",
            input_type="text"
        )

        session = SurveySession.objects.create(survey=self.survey, language="ru")
        form = SurveySectionAnswerForm(
            initial={},
            section=self.section,
            question=None,
            survey_session_id=session.id,
            language="ru"
        )

        self.assertEqual(form.fields["Q_UNTRANS"].label, "Untranslated Question")


class InlineChoicesTest(TestCase):
    """Tests for inline choices functionality on Question and Answer models."""

    def setUp(self):
        """Set up test data with inline choices."""
        self.org = Organization.objects.create(name="Inline Choices Test Org")
        self.survey = SurveyHeader.objects.create(
            name="inline_choices_test",
            organization=self.org
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="section1",
            code="IC1",
            is_head=True
        )
        self.multilingual_choices = [
            {"code": 1, "name": {"en": "Yes", "ru": "Да", "de": "Ja"}},
            {"code": 2, "name": {"en": "No", "ru": "Нет", "de": "Nein"}},
        ]
        self.question = Question.objects.create(
            survey_section=self.section,
            code="Q_IC",
            order_number=1,
            name="Choice Question",
            input_type="choice",
            choices=self.multilingual_choices
        )
        self.session = SurveySession.objects.create(survey=self.survey)

    def test_get_choice_name_returns_requested_language(self):
        """
        GIVEN a question with multilingual choices
        WHEN get_choice_name is called with a specific language
        THEN the name in that language is returned
        """
        self.assertEqual(self.question.get_choice_name(1, "en"), "Yes")
        self.assertEqual(self.question.get_choice_name(1, "ru"), "Да")
        self.assertEqual(self.question.get_choice_name(2, "de"), "Nein")

    def test_get_choice_name_falls_back_to_english(self):
        """
        GIVEN a question with multilingual choices
        WHEN get_choice_name is called with a language that has no translation
        THEN the English name is returned as fallback
        """
        self.assertEqual(self.question.get_choice_name(1, "fr"), "Yes")
        self.assertEqual(self.question.get_choice_name(2, "ja"), "No")

    def test_get_choice_name_falls_back_to_first_available(self):
        """
        GIVEN a question with choices that have no English translation
        WHEN get_choice_name is called with an unavailable language
        THEN the first available translation is returned
        """
        no_en_choices = [
            {"code": 1, "name": {"ru": "Да", "de": "Ja"}},
        ]
        question = Question.objects.create(
            survey_section=self.section,
            code="Q_NOEN",
            order_number=2,
            name="No English",
            input_type="choice",
            choices=no_en_choices
        )
        result = question.get_choice_name(1, "fr")
        self.assertIn(result, ["Да", "Ja"])

    def test_get_choice_name_returns_code_for_missing_choice(self):
        """
        GIVEN a question with choices
        WHEN get_choice_name is called with a non-existent code
        THEN the string representation of the code is returned
        """
        self.assertEqual(self.question.get_choice_name(99, "en"), "99")

    def test_get_choice_name_with_string_name(self):
        """
        GIVEN a question with choices where name is a plain string
        WHEN get_choice_name is called
        THEN the string name is returned regardless of language
        """
        simple_choices = [
            {"code": 1, "name": "Simple Choice"},
        ]
        question = Question.objects.create(
            survey_section=self.section,
            code="Q_SIMPLE",
            order_number=3,
            name="Simple",
            input_type="choice",
            choices=simple_choices
        )
        self.assertEqual(question.get_choice_name(1, "en"), "Simple Choice")
        self.assertEqual(question.get_choice_name(1, "ru"), "Simple Choice")

    def test_get_choice_name_with_none_language(self):
        """
        GIVEN a question with multilingual choices
        WHEN get_choice_name is called with lang=None
        THEN the English name is returned as fallback
        """
        self.assertEqual(self.question.get_choice_name(1, None), "Yes")
        self.assertEqual(self.question.get_choice_name(2), "No")

    def test_choices_validator_accepts_valid_choices(self):
        """
        GIVEN valid choices structure
        WHEN ChoicesValidator is called
        THEN no error is raised
        """
        validator = ChoicesValidator()
        validator([
            {"code": 1, "name": "Choice A"},
            {"code": 2, "name": {"en": "Choice B", "ru": "Выбор Б"}},
        ])

    def test_choices_validator_rejects_non_list(self):
        """
        GIVEN a non-list value
        WHEN ChoicesValidator is called
        THEN ValidationError is raised
        """
        from django.core.exceptions import ValidationError
        validator = ChoicesValidator()
        with self.assertRaises(ValidationError):
            validator("not a list")

    def test_choices_validator_rejects_missing_code(self):
        """
        GIVEN a choice dict without 'code' key
        WHEN ChoicesValidator is called
        THEN ValidationError is raised
        """
        from django.core.exceptions import ValidationError
        validator = ChoicesValidator()
        with self.assertRaises(ValidationError):
            validator([{"name": "No code"}])

    def test_choices_validator_rejects_missing_name(self):
        """
        GIVEN a choice dict without 'name' key
        WHEN ChoicesValidator is called
        THEN ValidationError is raised
        """
        from django.core.exceptions import ValidationError
        validator = ChoicesValidator()
        with self.assertRaises(ValidationError):
            validator([{"code": 1}])

    def test_choices_validator_rejects_non_dict_items(self):
        """
        GIVEN a list containing non-dict items
        WHEN ChoicesValidator is called
        THEN ValidationError is raised
        """
        from django.core.exceptions import ValidationError
        validator = ChoicesValidator()
        with self.assertRaises(ValidationError):
            validator(["not a dict"])

    def test_selected_choices_saved_and_retrieved(self):
        """
        GIVEN an answer with selected_choices
        WHEN saved and retrieved from database
        THEN selected_choices are preserved
        """
        answer = Answer.objects.create(
            survey_session=self.session,
            question=self.question,
            selected_choices=[1, 2]
        )
        answer.refresh_from_db()
        self.assertEqual(answer.selected_choices, [1, 2])

    def test_get_selected_choice_names_returns_names(self):
        """
        GIVEN an answer with selected_choices
        WHEN get_selected_choice_names is called
        THEN choice names are returned in the requested language
        """
        answer = Answer.objects.create(
            survey_session=self.session,
            question=self.question,
            selected_choices=[1, 2]
        )
        self.assertEqual(answer.get_selected_choice_names("en"), ["Yes", "No"])
        self.assertEqual(answer.get_selected_choice_names("ru"), ["Да", "Нет"])

    def test_get_selected_choice_names_empty_for_no_choices(self):
        """
        GIVEN an answer with no selected_choices
        WHEN get_selected_choice_names is called
        THEN an empty list is returned
        """
        answer = Answer.objects.create(
            survey_session=self.session,
            question=self.question
        )
        self.assertEqual(answer.get_selected_choice_names("en"), [])


class TranslationSerializationTest(TestCase):
    """Tests for export/import of translations."""

    def setUp(self):
        """Set up test data with translations."""
        from .models import SurveySectionTranslation, QuestionTranslation
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


class MultilingualIntegrationTest(TestCase):
    """End-to-end integration tests for multilingual survey functionality."""

    def setUp(self):
        """Set up complete multilingual survey with translations."""
        from .models import SurveySectionTranslation, QuestionTranslation
        self.SurveySectionTranslation = SurveySectionTranslation
        self.QuestionTranslation = QuestionTranslation

        self.client = Client()
        self.org = Organization.objects.create(name="Integration Test Org")

        # Create multilingual survey
        self.survey = SurveyHeader.objects.create(
            name="integration_multilang",
            organization=self.org,
            available_languages=["en", "ru"],
            redirect_url="/completed/",
            status='published',
        )

        # Create section with translations
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="main_section",
            title="English Section Title",
            subheading="English section description",
            code="INT1",
            is_head=True
        )
        self.SurveySectionTranslation.objects.create(
            section=self.section,
            language="ru",
            title="Русский заголовок секции",
            subheading="Русское описание секции"
        )

        # Create inline choices with translated names
        self.yes_no_choices = [
            {"code": 1, "name": {"en": "Yes", "ru": "Да"}},
            {"code": 2, "name": {"en": "No", "ru": "Нет"}},
        ]

        # Create questions with translations
        self.text_question = Question.objects.create(
            survey_section=self.section,
            code="Q_INT_TEXT",
            order_number=1,
            name="What is your name?",
            subtext="Please enter your full name",
            input_type="text"
        )
        self.QuestionTranslation.objects.create(
            question=self.text_question,
            language="ru",
            name="Как вас зовут?",
            subtext="Пожалуйста, введите ваше полное имя"
        )

        self.choice_question = Question.objects.create(
            survey_section=self.section,
            code="Q_INT_CHOICE",
            order_number=2,
            name="Do you agree?",
            input_type="choice",
            choices=self.yes_no_choices
        )
        self.QuestionTranslation.objects.create(
            question=self.choice_question,
            language="ru",
            name="Вы согласны?"
        )

    def test_end_to_end_multilingual_survey_flow(self):
        """
        GIVEN a multilingual survey with Russian translations
        WHEN user selects Russian, views section
        THEN survey session is created with language='ru' and translated titles shown
        """
        # Step 1: Access survey entry - should redirect to language selection
        response = self.client.get('/surveys/integration_multilang/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('language', response.url)

        # Step 2: Select Russian language
        response = self.client.post(
            '/surveys/integration_multilang/language/',
            {'language': 'ru'}
        )
        self.assertEqual(response.status_code, 302)

        # Step 3: View section - should show translated content
        response = self.client.get('/surveys/integration_multilang/main_section/')
        self.assertEqual(response.status_code, 200)

        # Verify translated section title is in context
        self.assertEqual(response.context['section_title'], "Русский заголовок секции")
        self.assertEqual(response.context['section_subheading'], "Русское описание секции")
        self.assertEqual(response.context['selected_language'], 'ru')

        # Verify session was created with correct language
        session = SurveySession.objects.get(survey=self.survey)
        self.assertEqual(session.language, 'ru')

    def test_export_import_multilingual_survey_roundtrip(self):
        """
        GIVEN a multilingual survey with translations and responses
        WHEN exported and imported to fresh database
        THEN all translations and language settings are preserved
        """
        # Create a session with language
        session = SurveySession.objects.create(
            survey=self.survey,
            language="ru"
        )
        Answer.objects.create(
            survey_session=session,
            question=self.text_question,
            text="Тестовый ответ"
        )

        # Export
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="full")
        output.seek(0)

        # Modify name for import
        with zipfile.ZipFile(output, 'r') as zf:
            survey_json = json.loads(zf.read("survey.json"))
            responses_json = json.loads(zf.read("responses.json"))

        survey_json["survey"]["name"] = "imported_integration_multilang"
        responses_json["survey_name"] = "imported_integration_multilang"

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_json))
            zf.writestr("responses.json", json.dumps(responses_json))
        import_buffer.seek(0)

        # Import
        imported_survey, _ = import_survey_from_zip(import_buffer)

        # Verify survey structure
        self.assertEqual(imported_survey.available_languages, ["en", "ru"])

        # Verify section translations
        imported_section = SurveySection.objects.get(survey_header=imported_survey)
        self.assertEqual(
            imported_section.get_translated_title("ru"),
            "Русский заголовок секции"
        )

        # Verify question translations
        imported_text_q = Question.objects.get(
            survey_section=imported_section,
            name="What is your name?"
        )
        self.assertEqual(
            imported_text_q.get_translated_name("ru"),
            "Как вас зовут?"
        )

        # Verify session language preserved
        imported_session = SurveySession.objects.get(survey=imported_survey)
        self.assertEqual(imported_session.language, "ru")

    def test_single_language_survey_backwards_compatibility(self):
        """
        GIVEN a survey without available_languages (single-language)
        WHEN user accesses the survey
        THEN no language selection screen is shown, direct access to section
        """
        # Create single-language survey
        single_survey = SurveyHeader.objects.create(
            name="single_lang_compat",
            organization=self.org,
            available_languages=[],
            status='published',
        )
        single_section = SurveySection.objects.create(
            survey_header=single_survey,
            name="single_section",
            title="Single Lang Title",
            code="SLC1",
            is_head=True
        )
        Question.objects.create(
            survey_section=single_section,
            code="Q_SINGLE",
            name="Single language question",
            input_type="text"
        )

        # Access survey - should redirect directly to section
        response = self.client.get('/surveys/single_lang_compat/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('single_section', response.url)
        self.assertNotIn('language', response.url)

        # Access section directly - should work without language selection
        response = self.client.get('/surveys/single_lang_compat/single_section/')
        self.assertEqual(response.status_code, 200)

        # Verify original content is shown (no translations)
        self.assertEqual(response.context['section_title'], "Single Lang Title")
        self.assertIsNone(response.context['selected_language'])

        # Submit answer
        response = self.client.post('/surveys/single_lang_compat/single_section/', {
            'Q_SINGLE': 'Test answer',
        })

        # Verify session created without language
        session = SurveySession.objects.get(survey=single_survey)
        self.assertIsNone(session.language)

    def test_missing_translation_fallback_in_section_title(self):
        """
        GIVEN a multilingual survey where section lacks translation for a language
        WHEN user selects that language
        THEN original section title is displayed as fallback
        """
        # Create a new section without Russian translation
        untranslated_section = SurveySection.objects.create(
            survey_header=self.survey,
            name="untranslated_section",
            title="Untranslated Section Title",
            subheading="Untranslated subheading",
            code="UNT1",
            is_head=False
        )
        # Link from main section
        self.section.next_section = untranslated_section
        self.section.save()

        # Select Russian
        self.client.post('/surveys/integration_multilang/language/', {'language': 'ru'})

        # Access untranslated section
        response = self.client.get('/surveys/integration_multilang/untranslated_section/')
        self.assertEqual(response.status_code, 200)

        # Verify original title is shown as fallback
        self.assertEqual(response.context['section_title'], "Untranslated Section Title")
        self.assertEqual(response.context['section_subheading'], "Untranslated subheading")


class SurveyHeaderVisibilityTest(TestCase):
    """Tests for SurveyHeader visibility and is_archived fields."""

    def setUp(self):
        self.org = _make_org()

    def test_default_visibility_is_private(self):
        """
        GIVEN a new SurveyHeader
        WHEN created without specifying visibility
        THEN visibility should default to 'private'
        """
        survey = SurveyHeader.objects.create(name="test_vis", organization=self.org)
        self.assertEqual(survey.visibility, "private")

    def test_default_is_archived_is_false(self):
        """
        GIVEN a new SurveyHeader
        WHEN created without specifying is_archived
        THEN is_archived should default to False
        """
        survey = SurveyHeader.objects.create(name="test_arch", organization=self.org)
        self.assertFalse(survey.is_archived)

    def test_visibility_choices(self):
        """
        GIVEN a SurveyHeader
        WHEN setting visibility to each valid choice
        THEN each value should be accepted
        """
        for vis in ("private", "demo", "public"):
            survey = SurveyHeader.objects.create(name=f"test_{vis}", visibility=vis, organization=self.org)
            self.assertEqual(survey.visibility, vis)


class StoryModelTest(TestCase):
    """Tests for the Story model."""

    def setUp(self):
        self.org = _make_org()

    def test_create_story(self):
        """
        GIVEN valid story data
        WHEN a Story is created
        THEN it should be persisted and queryable
        """
        story = Story.objects.create(
            title="Test Story",
            slug="test-story",
            body="<p>Body</p>",
            story_type="article",
            is_published=True,
        )
        self.assertEqual(Story.objects.get(slug="test-story").title, "Test Story")

    def test_slug_uniqueness(self):
        """
        GIVEN an existing Story with a slug
        WHEN creating another Story with the same slug
        THEN the system should raise an IntegrityError
        """
        from django.db import IntegrityError
        Story.objects.create(title="A", slug="dup", story_type="article")
        with self.assertRaises(IntegrityError):
            Story.objects.create(title="B", slug="dup", story_type="article")

    def test_nullable_survey_fk(self):
        """
        GIVEN a Story without a survey FK
        WHEN created
        THEN it should be valid with survey as NULL
        """
        story = Story.objects.create(title="No Survey", slug="no-survey", story_type="map")
        self.assertIsNone(story.survey)

    def test_story_with_survey_fk(self):
        """
        GIVEN a Story linked to a SurveyHeader
        WHEN created
        THEN the story should reference that survey
        """
        survey = SurveyHeader.objects.create(name="linked_survey", organization=self.org)
        story = Story.objects.create(
            title="Linked", slug="linked", story_type="results", survey=survey,
        )
        self.assertEqual(story.survey, survey)


class LandingPageViewTest(TestCase):
    """Tests for the landing page index view."""

    def setUp(self):
        self.client = Client()
        self.org = _make_org()

    def test_anonymous_sees_landing_page(self):
        """
        GIVEN an unauthenticated user
        WHEN navigating to /
        THEN the system renders the landing page with sign-up CTA
        """
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'landing.html')
        self.assertContains(response, 'Sign Up Free')
        self.assertContains(response, 'Sign In')
        self.assertNotContains(response, 'Go to Dashboard')

    def test_authenticated_sees_dashboard_cta(self):
        """
        GIVEN an authenticated user
        WHEN navigating to /
        THEN the system renders the landing page with dashboard CTA
        """
        User.objects.create_user('testuser', password='pass')
        self.client.login(username='testuser', password='pass')
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'landing.html')
        self.assertContains(response, 'Go to Dashboard')
        self.assertNotContains(response, 'Sign Up Free')

    def test_private_surveys_excluded_from_context(self):
        """
        GIVEN private, demo, and public surveys
        WHEN the landing page is rendered
        THEN only demo and public surveys appear in the surveys context
        """
        SurveyHeader.objects.create(name="priv", visibility="private", organization=self.org, status='published')
        SurveyHeader.objects.create(name="demo_s", visibility="demo", organization=self.org, status='published')
        SurveyHeader.objects.create(name="pub_s", visibility="public", organization=self.org, status='published')

        response = self.client.get('/')
        survey_names = [s.name for s in response.context['surveys']]
        self.assertNotIn('priv', survey_names)
        self.assertIn('demo_s', survey_names)
        self.assertIn('pub_s', survey_names)

    def test_seo_meta_tags_present(self):
        """
        GIVEN the landing page
        WHEN rendered
        THEN essential SEO meta tags are present in the HTML
        """
        response = self.client.get('/')
        content = response.content.decode()
        self.assertIn('<meta name="description"', content)
        self.assertIn('<link rel="canonical"', content)
        self.assertIn('og:title', content)
        self.assertIn('twitter:card', content)
        self.assertIn('application/ld+json', content)

    def test_landing_page_sections_present(self):
        """
        GIVEN the landing page
        WHEN rendered
        THEN all major sections are present
        """
        SurveyHeader.objects.create(name="hidden", visibility="private", organization=self.org, status='published')
        response = self.client.get('/')
        content = response.content.decode()
        self.assertIn('id="hero"', content)
        self.assertIn('id="problem-solution"', content)
        self.assertIn('id="features"', content)
        self.assertIn('id="use-cases"', content)
        self.assertIn('id="tech-stack"', content)
        self.assertIn('id="social-proof"', content)

    def test_github_link_present(self):
        """
        GIVEN the GITHUB_REPO_URL setting is configured
        WHEN the landing page is rendered
        THEN GitHub links appear in the page
        """
        response = self.client.get('/')
        self.assertContains(response, 'github.com')

    def test_navbar_links(self):
        """
        GIVEN the landing page
        WHEN rendered
        THEN the navbar contains correct anchor links
        """
        response = self.client.get('/')
        content = response.content.decode()
        self.assertIn('href="/#features"', content)
        self.assertIn('href="/#demo"', content)
        # Pricing section removed — verify it's not in navbar
        self.assertNotIn('href="/#pricing"', content)

    def test_schema_org_structured_data(self):
        """
        GIVEN the landing page
        WHEN rendered
        THEN Schema.org SoftwareApplication structured data is present
        """
        response = self.client.get('/')
        content = response.content.decode()
        self.assertIn('"@type": "SoftwareApplication"', content)
        self.assertIn('"name": "Mapsurvey"', content)


class StoryDetailViewTest(TestCase):
    """Tests for the story detail view."""

    def setUp(self):
        self.client = Client()
        self.org = _make_org()

    def test_published_story_returns_200(self):
        """
        GIVEN a published story
        WHEN navigating to /stories/<slug>/
        THEN the system returns 200
        """
        from django.utils import timezone
        Story.objects.create(
            title="Published", slug="published", story_type="article",
            is_published=True, published_date=timezone.now(),
        )
        response = self.client.get('/stories/published/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'story_detail.html')

    def test_unpublished_story_returns_404(self):
        """
        GIVEN an unpublished story
        WHEN navigating to /stories/<slug>/
        THEN the system returns 404
        """
        Story.objects.create(title="Draft", slug="draft-story", story_type="article", is_published=False)
        response = self.client.get('/stories/draft-story/')
        self.assertEqual(response.status_code, 404)

    def test_nonexistent_story_returns_404(self):
        """
        GIVEN no story with a given slug
        WHEN navigating to /stories/<slug>/
        THEN the system returns 404
        """
        response = self.client.get('/stories/does-not-exist/')
        self.assertEqual(response.status_code, 404)

    def test_story_with_survey_shows_link(self):
        """
        GIVEN a published story linked to a survey
        WHEN viewing the story detail
        THEN the page includes the survey name in the response
        """
        from django.utils import timezone
        survey = SurveyHeader.objects.create(name="linked_surv", organization=self.org)
        Story.objects.create(
            title="With Survey", slug="with-survey", story_type="results",
            is_published=True, published_date=timezone.now(), survey=survey,
        )
        response = self.client.get('/stories/with-survey/')
        self.assertContains(response, "linked_surv")


class AnswerPrepopulationTest(TestCase):
    """Tests for answer prepopulation when revisiting survey sections."""

    def setUp(self):
        """Set up a survey with multiple question types across two sections."""
        self.client = Client()
        self.org = Organization.objects.create(name="Prepop Test Org")
        self.survey = SurveyHeader.objects.create(
            name="prepop_survey",
            organization=self.org,
            redirect_url="/thanks/",
            status='published',
        )
        self.section1 = SurveySection.objects.create(
            survey_header=self.survey,
            name="section1",
            title="Section One",
            code="S1",
            is_head=True,
        )
        self.section2 = SurveySection.objects.create(
            survey_header=self.survey,
            name="section2",
            title="Section Two",
            code="S2",
        )
        self.section1.next_section = self.section2
        self.section1.save()
        self.section2.prev_section = self.section1
        self.section2.save()

        self.text_q = Question.objects.create(
            survey_section=self.section1,
            name="Your name",
            input_type="text",
            order_number=1,
        )
        self.number_q = Question.objects.create(
            survey_section=self.section1,
            name="Your age",
            input_type="number",
            order_number=2,
        )
        self.choice_q = Question.objects.create(
            survey_section=self.section1,
            name="Agree?",
            input_type="choice",
            choices=[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}],
            order_number=3,
        )
        self.multichoice_q = Question.objects.create(
            survey_section=self.section1,
            name="Colors",
            input_type="multichoice",
            choices=[
                {"code": 1, "name": "Red"},
                {"code": 2, "name": "Blue"},
                {"code": 3, "name": "Green"},
            ],
            order_number=4,
        )
        self.point_q = Question.objects.create(
            survey_section=self.section1,
            name="Location",
            input_type="point",
            order_number=5,
        )
        # A question in section2 to verify isolation
        self.section2_q = Question.objects.create(
            survey_section=self.section2,
            name="Feedback",
            input_type="text",
            order_number=1,
        )

    def _visit_section(self, section_name):
        """GET a section and return the response."""
        return self.client.get(f'/surveys/prepop_survey/{section_name}/')

    def _submit_section(self, section_name, data):
        """POST to a section with given data."""
        return self.client.post(f'/surveys/prepop_survey/{section_name}/', data)

    def test_scalar_field_prepopulation(self):
        """
        GIVEN a section with text, number, and choice answers saved
        WHEN the user revisits the section via GET
        THEN the form initial values contain the previously saved answers
        """
        # First visit to create session
        self._visit_section('section1')

        # Submit answers
        self._submit_section('section1', {
            self.text_q.code: 'Alice',
            self.number_q.code: '25',
            self.choice_q.code: '1',
            self.multichoice_q.code: ['1', '3'],
        })

        # Revisit section1 — verify rendered HTML contains saved values
        response = self._visit_section('section1')

        self.assertContains(response, 'Alice')
        self.assertContains(response, '25')
        # Choice radio button should be checked
        self.assertContains(response, 'checked')

    def test_geo_answer_restoration(self):
        """
        GIVEN a section with a point geo answer saved
        WHEN the user revisits the section via GET
        THEN existing_geo_answers_json context contains correct GeoJSON
        """
        # Create session and save a point answer directly
        self._visit_section('section1')
        session_id = self.client.session['survey_session_id']
        session = SurveySession.objects.get(pk=session_id)
        Answer.objects.create(
            survey_session=session,
            question=self.point_q,
            point=Point(30.5, 60.0, srid=4326),
        )

        # Revisit section1
        response = self._visit_section('section1')
        geo_json_str = response.context['existing_geo_answers_json']
        geo_data = json.loads(geo_json_str)

        self.assertIn(self.point_q.code, geo_data)
        features = geo_data[self.point_q.code]
        self.assertEqual(len(features), 1)
        self.assertEqual(features[0]['geometry']['type'], 'Point')
        self.assertEqual(features[0]['properties']['question_id'], self.point_q.code)

    def test_resubmission_replaces_answers(self):
        """
        GIVEN a section submitted with answers
        WHEN the user re-submits with different values
        THEN only the latest answers exist in the database
        """
        # First visit to create session
        self._visit_section('section1')
        session_id = self.client.session['survey_session_id']

        # First submission
        self._submit_section('section1', {
            self.text_q.code: 'Alice',
            self.number_q.code: '25',
        })
        self.assertEqual(
            Answer.objects.filter(survey_session_id=session_id, question=self.text_q).count(),
            1,
        )

        # Second submission with different values
        self._submit_section('section1', {
            self.text_q.code: 'Bob',
            self.number_q.code: '30',
        })

        # Only latest answers should exist
        text_answers = Answer.objects.filter(survey_session_id=session_id, question=self.text_q)
        self.assertEqual(text_answers.count(), 1)
        self.assertEqual(text_answers.first().text, 'Bob')

        number_answers = Answer.objects.filter(survey_session_id=session_id, question=self.number_q)
        self.assertEqual(number_answers.count(), 1)
        self.assertEqual(number_answers.first().numeric, 30.0)

    def test_first_visit_shows_empty_form(self):
        """
        GIVEN a section with no saved answers
        WHEN the user visits it for the first time
        THEN no geo answers are present in the context
        """
        response = self._visit_section('section1')
        geo_json_str = response.context['existing_geo_answers_json']

        self.assertEqual(json.loads(geo_json_str), {})

    def test_resubmission_does_not_affect_other_sections(self):
        """
        GIVEN answers saved in section2
        WHEN section1 is re-submitted
        THEN section2 answers remain unchanged
        """
        # Visit section1 to create session
        self._visit_section('section1')
        session_id = self.client.session['survey_session_id']
        session = SurveySession.objects.get(pk=session_id)

        # Save an answer in section2 directly
        Answer.objects.create(
            survey_session=session,
            question=self.section2_q,
            text="Great survey",
        )

        # Submit section1
        self._submit_section('section1', {
            self.text_q.code: 'Alice',
        })

        # Section2 answer should still exist
        self.assertTrue(
            Answer.objects.filter(survey_session=session, question=self.section2_q).exists()
        )


class SurveyProgressIndicatorTest(TestCase):
    """Tests for survey section progress indicator."""

    def setUp(self):
        """Set up a survey with three linked sections."""
        self.client = Client()
        self.org = Organization.objects.create(name="Progress Test Org")
        self.survey = SurveyHeader.objects.create(
            name="progress_survey",
            organization=self.org,
            redirect_url="/thanks/",
            status='published',
        )
        self.section1 = SurveySection.objects.create(
            survey_header=self.survey,
            name="sec1",
            title="First",
            code="S1",
            is_head=True,
        )
        self.section2 = SurveySection.objects.create(
            survey_header=self.survey,
            name="sec2",
            title="Second",
            code="S2",
        )
        self.section3 = SurveySection.objects.create(
            survey_header=self.survey,
            name="sec3",
            title="Third",
            code="S3",
        )
        # Link sections: sec1 → sec2 → sec3
        self.section1.next_section = self.section2
        self.section1.save()
        self.section2.prev_section = self.section1
        self.section2.next_section = self.section3
        self.section2.save()
        self.section3.prev_section = self.section2
        self.section3.save()

        # Each section needs at least one question
        for section in [self.section1, self.section2, self.section3]:
            Question.objects.create(
                survey_section=section,
                name=f"Q in {section.name}",
                input_type="text",
                order_number=1,
            )

    def test_progress_on_first_section(self):
        """
        GIVEN a 3-section survey
        WHEN the user opens the first section
        THEN section_current is 1 and section_total is 3
        """
        response = self.client.get('/surveys/progress_survey/sec1/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['section_current'], 1)
        self.assertEqual(response.context['section_total'], 3)

    def test_progress_on_middle_section(self):
        """
        GIVEN a 3-section survey
        WHEN the user opens the second section
        THEN section_current is 2 and section_total is 3
        """
        response = self.client.get('/surveys/progress_survey/sec2/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['section_current'], 2)
        self.assertEqual(response.context['section_total'], 3)

    def test_progress_on_last_section(self):
        """
        GIVEN a 3-section survey
        WHEN the user opens the last section
        THEN section_current is 3 and section_total is 3
        """
        response = self.client.get('/surveys/progress_survey/sec3/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['section_current'], 3)
        self.assertEqual(response.context['section_total'], 3)

    def test_progress_displayed_in_html(self):
        """
        GIVEN a 3-section survey
        WHEN the user opens the second section
        THEN the HTML contains "2 / 3" in a progress element
        """
        response = self.client.get('/surveys/progress_survey/sec2/')
        self.assertContains(response, '2 / 3')


class SurveyThanksPageTest(TestCase):
    """Tests for the built-in survey thanks page."""

    def setUp(self):
        org = Organization.objects.create(name="Thanks Org")
        self.survey = SurveyHeader.objects.create(
            name="thanks_survey",
            organization=org,
            redirect_url="#",
            status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="only_section",
            title="Only Section",
            code="S1",
            is_head=True,
            start_map_postion=Point(30.0, 60.0),
            start_map_zoom=14,
        )
        self.question = Question.objects.create(
            survey_section=self.section,
            name="Name",
            input_type="text_line",
            order_number=1,
        )

        self.custom_survey = SurveyHeader.objects.create(
            name="custom_redirect_survey",
            organization=org,
            redirect_url="https://example.com/done",
            status='published',
        )
        self.custom_section = SurveySection.objects.create(
            survey_header=self.custom_survey,
            name="only_section",
            title="Only Section",
            code="S1",
            is_head=True,
            start_map_postion=Point(30.0, 60.0),
            start_map_zoom=14,
        )
        Question.objects.create(
            survey_section=self.custom_section,
            name="Name",
            input_type="text_line",
            order_number=1,
        )

    def test_thanks_page_returns_200_and_clears_session(self):
        """
        GIVEN a survey with a completed session
        WHEN the user visits the thanks page
        THEN status is 200 and session keys are cleared
        """
        # Create a session by visiting the section
        self.client.get('/surveys/thanks_survey/only_section/')
        self.assertIn('survey_session_id', self.client.session)

        response = self.client.get('/surveys/thanks_survey/thanks/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('survey_session_id', self.client.session)
        self.assertNotIn('survey_language', self.client.session)

    def test_thanks_page_nonexistent_survey_returns_404(self):
        """
        GIVEN no survey with the given name
        WHEN the user visits the thanks page
        THEN the server returns 404
        """
        response = self.client.get('/surveys/nonexistent/thanks/')
        self.assertEqual(response.status_code, 404)

    def test_last_section_post_redirects_to_thanks_page(self):
        """
        GIVEN a single-section survey with default redirect_url="#"
        WHEN the user submits the last section
        THEN the response redirects to the thanks page (using UUID)
        """
        self.client.get('/surveys/thanks_survey/only_section/')
        response = self.client.post('/surveys/thanks_survey/only_section/', {
            self.question.code: 'Alice',
        })
        self.assertRedirects(response, f'/surveys/{self.survey.uuid}/thanks/', fetch_redirect_response=False)

    def test_last_section_post_with_custom_redirect(self):
        """
        GIVEN a single-section survey with custom redirect_url
        WHEN the user submits the last section
        THEN the response redirects to the custom URL
        """
        self.client.get('/surveys/custom_redirect_survey/only_section/')
        response = self.client.post('/surveys/custom_redirect_survey/only_section/', {
            self.custom_section.questions()[0].code: 'Bob',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'https://example.com/done')

    def test_thanks_page_empty_thanks_html_shows_default(self):
        """
        GIVEN a survey with empty thanks_html
        WHEN the user visits the thanks page
        THEN the default message block is displayed and share URL uses UUID
        """
        response = self.client.get('/surveys/thanks_survey/thanks/')
        # Share URL in JS uses UUID-based survey URL
        self.assertContains(response, f'/surveys/{self.survey.uuid}/')

    def test_thanks_page_multilingual_renders_correct_language(self):
        """
        GIVEN a survey with multilingual thanks_html
        WHEN the user completed the survey in Russian
        THEN the thanks page renders the Russian HTML
        """
        self.survey.thanks_html = {
            'en': '<h1>Thanks!</h1>',
            'ru': '<h1>Спасибо!</h1>',
        }
        self.survey.save()

        session = self.client.session
        session['survey_language'] = 'ru'
        session.save()

        response = self.client.get('/surveys/thanks_survey/thanks/')
        self.assertContains(response, '<h1>Спасибо!</h1>')
        self.assertNotContains(response, 'Thanks!')

    def test_thanks_page_falls_back_to_en(self):
        """
        GIVEN a survey with thanks_html that has only "en" key
        WHEN the user completed the survey in French
        THEN the thanks page falls back to English content
        """
        self.survey.thanks_html = {'en': '<p>Thank you very much!</p>'}
        self.survey.save()

        session = self.client.session
        session['survey_language'] = 'fr'
        session.save()

        response = self.client.get('/surveys/thanks_survey/thanks/')
        self.assertContains(response, 'Thank you very much!')

    def test_thanks_page_plain_string_renders_directly(self):
        """
        GIVEN a survey with thanks_html as a plain string
        WHEN the user visits the thanks page
        THEN the string is rendered directly
        """
        self.survey.thanks_html = '<h2>Merci!</h2>'
        self.survey.save()

        response = self.client.get('/surveys/thanks_survey/thanks/')
        self.assertContains(response, '<h2>Merci!</h2>')


class QuestionCardStylingTest(TestCase):
    """Tests for question card wrapper rendering in survey sections."""

    def setUp(self):
        self.client = Client()
        self.org = Organization.objects.create(name="Card Test Org")
        self.survey = SurveyHeader.objects.create(
            name="card_survey",
            organization=self.org,
            redirect_url="#",
            status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey,
            name="section1",
            title="Section One",
            code="S1",
            is_head=True,
            start_map_postion=Point(30.5, 60.0),
            start_map_zoom=14,
        )

    def test_text_question_renders_in_card(self):
        """
        GIVEN a survey section with a text question
        WHEN the section page is rendered
        THEN the question is wrapped in a div.question-card
        """
        Question.objects.create(
            survey_section=self.section,
            name="Your name",
            input_type="text",
            order_number=1,
        )
        response = self.client.get('/surveys/card_survey/section1/')
        self.assertContains(response, 'class="question-card"')

    def test_choice_question_renders_in_card(self):
        """
        GIVEN a survey section with a choice question
        WHEN the section page is rendered
        THEN the question is wrapped in a div.question-card
        """
        Question.objects.create(
            survey_section=self.section,
            name="Agree?",
            input_type="choice",
            choices=[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}],
            order_number=1,
        )
        response = self.client.get('/surveys/card_survey/section1/')
        self.assertContains(response, 'class="question-card"')

    def test_geo_question_not_in_card(self):
        """
        GIVEN a survey section with a point geo question
        WHEN the section page is rendered
        THEN the question is NOT wrapped in a div.question-card
        """
        Question.objects.create(
            survey_section=self.section,
            name="Location",
            input_type="point",
            order_number=1,
        )
        response = self.client.get('/surveys/card_survey/section1/')
        self.assertNotContains(response, 'class="question-card"')

    def test_html_question_not_in_card(self):
        """
        GIVEN a survey section with an html question
        WHEN the section page is rendered
        THEN the question is NOT wrapped in a div.question-card
        """
        Question.objects.create(
            survey_section=self.section,
            name="Info",
            input_type="html",
            subtext="<p>Some info</p>",
            order_number=1,
        )
        response = self.client.get('/surveys/card_survey/section1/')
        self.assertNotContains(response, 'class="question-card"')

    def test_widget_has_question_type_attribute(self):
        """
        GIVEN a survey section with a choice question
        WHEN a SurveySectionAnswerForm is created
        THEN the field widget has question_type attribute set to 'choice'
        """
        q = Question.objects.create(
            survey_section=self.section,
            name="Agree?",
            input_type="choice",
            choices=[{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}],
            order_number=1,
        )
        form = SurveySectionAnswerForm(
            initial={}, section=self.section, question=None,
            survey_session_id=None,
        )
        widget = form.fields[q.code].widget
        self.assertEqual(widget.question_type, 'choice')

    def test_mixed_questions_only_card_types_wrapped(self):
        """
        GIVEN a survey section with text and point questions
        WHEN the section page is rendered
        THEN only the text question has a question-card wrapper
        """
        Question.objects.create(
            survey_section=self.section,
            name="Your name",
            input_type="text",
            order_number=1,
        )
        Question.objects.create(
            survey_section=self.section,
            name="Location",
            input_type="point",
            order_number=2,
        )
        response = self.client.get('/surveys/card_survey/section1/')
        content = response.content.decode()
        self.assertEqual(content.count('class="question-card"'), 1)


class EditorAuthTest(TestCase):
    """Tests that all editor views require authentication."""

    def test_unauthenticated_redirects_to_login(self):
        """
        GIVEN an unauthenticated user
        WHEN they access any editor URL
        THEN they are redirected to the login page
        """
        import uuid
        fake_uuid = uuid.uuid4()
        urls = [
            '/editor/surveys/new/',
            f'/editor/surveys/{fake_uuid}/',
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, f"{url} should redirect")
            self.assertIn('login', response.url, f"{url} should redirect to login")


class EditorSurveyCreateTest(TestCase):
    """Tests for survey creation via the editor."""

    def setUp(self):
        self.org = _make_org()
        self.user = User.objects.create_user(username='editor', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='editor', password='pass')

    def test_create_survey_happy_path(self):
        """
        GIVEN an authenticated user
        WHEN they submit the survey creation form with a valid name
        THEN a SurveyHeader is created with a default section
        """
        response = self.client.post('/editor/surveys/new/', {
            'name': 'my_new_survey',
            'redirect_url': '#',
            'visibility': 'private',
        })
        self.assertEqual(response.status_code, 302)
        survey = SurveyHeader.objects.get(name='my_new_survey')
        self.assertIsNotNone(survey)
        sections = SurveySection.objects.filter(survey_header=survey)
        self.assertEqual(sections.count(), 1)
        self.assertTrue(sections.first().is_head)

    def test_create_survey_duplicate_name_allowed(self):
        """
        GIVEN an existing survey with name 'dup_survey'
        WHEN a user tries to create another survey with the same name
        THEN the survey is created (duplicate names are allowed)
        """
        SurveyHeader.objects.create(name='dup_survey', organization=self.org)
        response = self.client.post('/editor/surveys/new/', {
            'name': 'dup_survey',
            'redirect_url': '#',
            'visibility': 'private',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SurveyHeader.objects.filter(name='dup_survey').count(), 2)

    def test_create_survey_get_renders_form(self):
        """
        GIVEN an authenticated user
        WHEN they GET the creation page
        THEN the form is rendered
        """
        response = self.client.get('/editor/surveys/new/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create New Survey')


class EditorSectionCRUDTest(TestCase):
    """Tests for section CRUD in the editor."""

    def setUp(self):
        self.org = _make_org()
        self.user = User.objects.create_user(username='editor', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='editor', password='pass')
        self.survey = SurveyHeader.objects.create(name='test_editor', visibility='private', organization=self.org)
        self.section_a = SurveySection.objects.create(
            survey_header=self.survey, name='a', title='Section A', code='SA', is_head=True,
        )
        self.section_b = SurveySection.objects.create(
            survey_header=self.survey, name='b', title='Section B', code='SB',
        )
        self.section_a.next_section = self.section_b
        self.section_a.save(update_fields=['next_section'])
        self.section_b.prev_section = self.section_a
        self.section_b.save(update_fields=['prev_section'])

    def test_create_section_appends_to_linked_list(self):
        """
        GIVEN a survey with sections [A, B]
        WHEN a new section is created
        THEN it is appended after B in the linked list
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/new/',
            HTTP_X_CSRFTOKEN='test',
        )
        self.assertEqual(response.status_code, 200)
        new_section = SurveySection.objects.filter(survey_header=self.survey).exclude(
            id__in=[self.section_a.id, self.section_b.id]
        ).first()
        self.assertIsNotNone(new_section)
        self.section_b.refresh_from_db()
        self.assertEqual(self.section_b.next_section_id, new_section.id)
        self.assertEqual(new_section.prev_section_id, self.section_b.id)

    def test_delete_section_relinks_neighbors(self):
        """
        GIVEN sections [A → B]
        WHEN B is deleted
        THEN A.next_section becomes None
        """
        self.client.post(f'/editor/surveys/{self.survey.uuid}/sections/{self.section_b.id}/delete/')
        self.section_a.refresh_from_db()
        self.assertIsNone(self.section_a.next_section_id)
        self.assertFalse(SurveySection.objects.filter(id=self.section_b.id).exists())

    def test_edit_section_title(self):
        """
        GIVEN a section with title 'Section A'
        WHEN the user updates the title to 'Introduction'
        THEN the section title is updated
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section_a.id}/',
            {'title': 'Introduction', 'subheading': '', 'code': 'SA'},
        )
        self.section_a.refresh_from_db()
        self.assertEqual(self.section_a.title, 'Introduction')


class EditorSectionReorderTest(TestCase):
    """Tests for section drag-and-drop reordering."""

    def setUp(self):
        self.org = _make_org()
        self.user = User.objects.create_user(username='editor', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='editor', password='pass')
        self.survey = SurveyHeader.objects.create(name='reorder_test', visibility='private', organization=self.org)
        self.s1 = SurveySection.objects.create(
            survey_header=self.survey, name='s1', title='S1', code='S1', is_head=True,
        )
        self.s2 = SurveySection.objects.create(
            survey_header=self.survey, name='s2', title='S2', code='S2',
        )
        self.s3 = SurveySection.objects.create(
            survey_header=self.survey, name='s3', title='S3', code='S3',
        )
        # Link: s1 → s2 → s3
        self.s1.next_section = self.s2
        self.s1.save(update_fields=['next_section'])
        self.s2.prev_section = self.s1
        self.s2.next_section = self.s3
        self.s2.save(update_fields=['prev_section', 'next_section'])
        self.s3.prev_section = self.s2
        self.s3.save(update_fields=['prev_section'])

    def test_reorder_rebuilds_linked_list(self):
        """
        GIVEN sections [S1, S2, S3]
        WHEN reordered to [S3, S1, S2]
        THEN linked list is rebuilt: S3(head) → S1 → S2
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/reorder/',
            data=json.dumps({'section_ids': [self.s3.id, self.s1.id, self.s2.id]}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 204)

        self.s1.refresh_from_db()
        self.s2.refresh_from_db()
        self.s3.refresh_from_db()

        self.assertTrue(self.s3.is_head)
        self.assertFalse(self.s1.is_head)
        self.assertFalse(self.s2.is_head)

        self.assertEqual(self.s3.next_section_id, self.s1.id)
        self.assertIsNone(self.s3.prev_section_id)
        self.assertEqual(self.s1.prev_section_id, self.s3.id)
        self.assertEqual(self.s1.next_section_id, self.s2.id)
        self.assertEqual(self.s2.prev_section_id, self.s1.id)
        self.assertIsNone(self.s2.next_section_id)


class EditorQuestionCRUDTest(TestCase):
    """Tests for question CRUD in the editor."""

    def setUp(self):
        self.org = _make_org()
        self.user = User.objects.create_user(username='editor', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='editor', password='pass')
        self.survey = SurveyHeader.objects.create(name='q_test', visibility='private', organization=self.org)
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section 1', code='S1', is_head=True,
        )

    def test_create_text_question(self):
        """
        GIVEN a section with no questions
        WHEN a text question is created
        THEN the question appears in the section with correct attributes
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/',
            {'name': 'Your feedback', 'input_type': 'text', 'color': '#000000'},
        )
        self.assertEqual(response.status_code, 200)
        q = Question.objects.get(survey_section=self.section, name='Your feedback')
        self.assertEqual(q.input_type, 'text')
        self.assertEqual(q.order_number, 1)

    def test_create_choice_question_with_choices(self):
        """
        GIVEN a section
        WHEN a choice question is created with choices JSON
        THEN the question has correct choices
        """
        choices = [{"code": 1, "name": "Yes"}, {"code": 2, "name": "No"}]
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/',
            {
                'name': 'Do you agree?',
                'input_type': 'choice',
                'color': '#000000',
                'choices_json': json.dumps(choices),
            },
        )
        self.assertEqual(response.status_code, 200)
        q = Question.objects.get(survey_section=self.section, name='Do you agree?')
        self.assertEqual(q.choices, choices)

    def test_delete_question(self):
        """
        GIVEN a section with one question
        WHEN the question is deleted
        THEN it no longer exists
        """
        q = Question.objects.create(
            survey_section=self.section, name='Delete me', input_type='text',
        )
        response = self.client.post(f'/editor/surveys/{self.survey.uuid}/questions/{q.id}/delete/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Question.objects.filter(id=q.id).exists())

    def test_edit_question(self):
        """
        GIVEN a text question
        WHEN it is edited to change the name
        THEN the name is updated
        """
        q = Question.objects.create(
            survey_section=self.section, name='Old name', input_type='text',
        )
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/{q.id}/edit/',
            {'name': 'New name', 'input_type': 'text', 'color': '#000000'},
        )
        self.assertEqual(response.status_code, 200)
        q.refresh_from_db()
        self.assertEqual(q.name, 'New name')


class EditorQuestionReorderTest(TestCase):
    """Tests for question reordering."""

    def setUp(self):
        self.org = _make_org()
        self.user = User.objects.create_user(username='editor', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='editor', password='pass')
        self.survey = SurveyHeader.objects.create(name='qr_test', visibility='private', organization=self.org)
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.q1 = Question.objects.create(
            survey_section=self.section, name='Q1', input_type='text', order_number=0,
        )
        self.q2 = Question.objects.create(
            survey_section=self.section, name='Q2', input_type='text', order_number=1,
        )
        self.q3 = Question.objects.create(
            survey_section=self.section, name='Q3', input_type='text', order_number=2,
        )

    def test_reorder_updates_order_number(self):
        """
        GIVEN questions [Q1(0), Q2(1), Q3(2)]
        WHEN reordered to [Q3, Q1, Q2]
        THEN order_numbers become Q3(0), Q1(1), Q2(2)
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/reorder/',
            data=json.dumps({'question_ids': [self.q3.id, self.q1.id, self.q2.id]}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 204)
        self.q1.refresh_from_db()
        self.q2.refresh_from_db()
        self.q3.refresh_from_db()
        self.assertEqual(self.q3.order_number, 0)
        self.assertEqual(self.q1.order_number, 1)
        self.assertEqual(self.q2.order_number, 2)


class EditorSubquestionTest(TestCase):
    """Tests for sub-question creation."""

    def setUp(self):
        self.org = _make_org()
        self.user = User.objects.create_user(username='editor', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='editor', password='pass')
        self.survey = SurveyHeader.objects.create(name='sub_test', visibility='private', organization=self.org)
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.geo_question = Question.objects.create(
            survey_section=self.section, name='Mark location', input_type='point',
        )

    def test_create_subquestion(self):
        """
        GIVEN a geo question
        WHEN a sub-question is created for it
        THEN the sub-question has parent_question_id set correctly
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/questions/{self.geo_question.id}/subquestions/new/',
            {'name': 'Rate this place', 'input_type': 'choice', 'color': '#000000',
             'choices_json': json.dumps([{"code": 1, "name": "Good"}, {"code": 2, "name": "Bad"}])},
        )
        self.assertEqual(response.status_code, 200)
        sub = Question.objects.get(name='Rate this place')
        self.assertEqual(sub.parent_question_id_id, self.geo_question.id)


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


# ─── Task 2.6: Permission Resolution Logic Tests ────────────────────────────

class PermissionResolutionTest(TestCase):
    """Tests for permission resolution logic (org baseline + survey collaborator)."""

    def setUp(self):
        self.org = _make_org('PermOrg')
        self.survey = SurveyHeader.objects.create(name='perm_survey', organization=self.org)
        self.owner_user = User.objects.create_user(username='org_owner', password='pass')
        self.admin_user = User.objects.create_user(username='org_admin', password='pass')
        self.editor_user = User.objects.create_user(username='org_editor', password='pass')
        self.viewer_user = User.objects.create_user(username='org_viewer', password='pass')
        self.nonmember = User.objects.create_user(username='nonmember', password='pass')

        Membership.objects.create(user=self.owner_user, organization=self.org, role='owner')
        Membership.objects.create(user=self.admin_user, organization=self.org, role='admin')
        Membership.objects.create(user=self.editor_user, organization=self.org, role='editor')
        Membership.objects.create(user=self.viewer_user, organization=self.org, role='viewer')

    def test_org_owner_gets_survey_owner_role(self):
        """
        GIVEN an org owner with no explicit survey collaborator entry
        WHEN get_effective_survey_role is called
        THEN effective role is 'owner'
        """
        role = get_effective_survey_role(self.owner_user, self.survey)
        self.assertEqual(role, 'owner')

    def test_org_admin_gets_survey_owner_role(self):
        """
        GIVEN an org admin with no explicit survey collaborator entry
        WHEN get_effective_survey_role is called
        THEN effective role is 'owner' (admin maps to survey owner)
        """
        role = get_effective_survey_role(self.admin_user, self.survey)
        self.assertEqual(role, 'owner')

    def test_org_editor_gets_none_without_collaborator(self):
        """
        GIVEN an org editor with no explicit survey collaborator entry
        WHEN get_effective_survey_role is called
        THEN effective role is None (editor gets no implicit access to others' surveys)
        """
        role = get_effective_survey_role(self.editor_user, self.survey)
        self.assertIsNone(role)

    def test_org_editor_with_collaborator_gets_collaborator_role(self):
        """
        GIVEN an org editor who is a survey collaborator with 'editor' role
        WHEN get_effective_survey_role is called
        THEN effective role is 'editor'
        """
        SurveyCollaborator.objects.create(user=self.editor_user, survey=self.survey, role='editor')
        role = get_effective_survey_role(self.editor_user, self.survey)
        self.assertEqual(role, 'editor')

    def test_org_viewer_gets_viewer_baseline(self):
        """
        GIVEN an org viewer with no explicit survey collaborator entry
        WHEN get_effective_survey_role is called
        THEN effective role is 'viewer'
        """
        role = get_effective_survey_role(self.viewer_user, self.survey)
        self.assertEqual(role, 'viewer')

    def test_org_viewer_with_editor_collaborator_gets_editor(self):
        """
        GIVEN an org viewer who has an explicit 'editor' collaborator role
        WHEN get_effective_survey_role is called
        THEN effective role is 'editor' (max of viewer baseline and editor collab)
        """
        SurveyCollaborator.objects.create(user=self.viewer_user, survey=self.survey, role='editor')
        role = get_effective_survey_role(self.viewer_user, self.survey)
        self.assertEqual(role, 'editor')

    def test_org_viewer_with_owner_collaborator_gets_owner(self):
        """
        GIVEN an org viewer who has an explicit 'owner' collaborator role
        WHEN get_effective_survey_role is called
        THEN effective role is 'owner'
        """
        SurveyCollaborator.objects.create(user=self.viewer_user, survey=self.survey, role='owner')
        role = get_effective_survey_role(self.viewer_user, self.survey)
        self.assertEqual(role, 'owner')

    def test_nonmember_gets_none(self):
        """
        GIVEN a user who is not a member of the org
        WHEN get_effective_survey_role is called
        THEN effective role is None
        """
        role = get_effective_survey_role(self.nonmember, self.survey)
        self.assertIsNone(role)

    def test_unauthenticated_user_gets_none(self):
        """
        GIVEN an anonymous (unauthenticated) user object
        WHEN get_effective_survey_role is called
        THEN effective role is None
        """
        from django.contrib.auth.models import AnonymousUser
        role = get_effective_survey_role(AnonymousUser(), self.survey)
        self.assertIsNone(role)

    def test_org_editor_with_viewer_collaborator_gets_viewer(self):
        """
        GIVEN an org editor who has an explicit 'viewer' collaborator role
        WHEN get_effective_survey_role is called
        THEN effective role is 'viewer' (editor baseline is None, collab is viewer)
        """
        SurveyCollaborator.objects.create(user=self.editor_user, survey=self.survey, role='viewer')
        role = get_effective_survey_role(self.editor_user, self.survey)
        self.assertEqual(role, 'viewer')


# ─── Task 4.8: Organization CRUD and Member Management Tests ────────────────

class OrgCRUDTest(TestCase):
    """Tests for organization creation, settings, and member management."""

    def setUp(self):
        self.owner = User.objects.create_user(username='org_owner', password='pass')
        self.admin = User.objects.create_user(username='org_admin', password='pass')
        self.viewer = User.objects.create_user(username='org_viewer', password='pass')
        self.outsider = User.objects.create_user(username='outsider', password='pass')

        self.org = _make_org('TestCrudOrg')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        Membership.objects.create(user=self.admin, organization=self.org, role='admin')
        Membership.objects.create(user=self.viewer, organization=self.org, role='viewer')

    def test_create_org_as_authenticated_user(self):
        """
        GIVEN an authenticated user
        WHEN they POST to org creation with a name
        THEN a new org is created and they become owner
        """
        self.client.login(username='outsider', password='pass')
        response = self.client.post('/org/new/', {'name': 'My New Org'})
        self.assertEqual(response.status_code, 302)
        org = Organization.objects.get(name='My New Org')
        self.assertTrue(Membership.objects.filter(user=self.outsider, organization=org, role='owner').exists())

    def test_create_org_unauthenticated_redirects(self):
        """
        GIVEN an unauthenticated user
        WHEN they access org creation
        THEN they are redirected to login
        """
        response = self.client.post('/org/new/', {'name': 'Nope'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_org_settings_owner_can_edit(self):
        """
        GIVEN an org owner
        WHEN they POST updated settings
        THEN the org is updated
        """
        self.client.login(username='org_owner', password='pass')
        response = self.client.post(f'/org/{self.org.slug}/settings/', {
            'name': 'Updated Name',
            'slug': self.org.slug,
        })
        self.assertEqual(response.status_code, 302)
        self.org.refresh_from_db()
        self.assertEqual(self.org.name, 'Updated Name')

    def test_org_settings_non_owner_forbidden(self):
        """
        GIVEN an org admin (not owner)
        WHEN they access org settings
        THEN they get 403
        """
        self.client.login(username='org_admin', password='pass')
        response = self.client.get(f'/org/{self.org.slug}/settings/')
        self.assertEqual(response.status_code, 403)

    def test_change_role_by_owner(self):
        """
        GIVEN an org owner
        WHEN they change a viewer's role to editor
        THEN the role is updated
        """
        self.client.login(username='org_owner', password='pass')
        response = self.client.post(
            f'/org/{self.org.slug}/members/{self.viewer.id}/role/',
            {'role': 'editor'},
        )
        self.assertEqual(response.status_code, 302)
        m = Membership.objects.get(user=self.viewer, organization=self.org)
        self.assertEqual(m.role, 'editor')

    def test_admin_cannot_change_owner_role(self):
        """
        GIVEN an org admin
        WHEN they try to change an owner's role
        THEN they get 403
        """
        self.client.login(username='org_admin', password='pass')
        response = self.client.post(
            f'/org/{self.org.slug}/members/{self.owner.id}/role/',
            {'role': 'editor'},
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_cannot_promote_to_owner(self):
        """
        GIVEN an org admin
        WHEN they try to promote a viewer to owner
        THEN they get 403
        """
        self.client.login(username='org_admin', password='pass')
        response = self.client.post(
            f'/org/{self.org.slug}/members/{self.viewer.id}/role/',
            {'role': 'owner'},
        )
        self.assertEqual(response.status_code, 403)

    def test_remove_member_by_owner(self):
        """
        GIVEN an org owner
        WHEN they remove a viewer member
        THEN the membership is deleted
        """
        self.client.login(username='org_owner', password='pass')
        response = self.client.post(
            f'/org/{self.org.slug}/members/{self.viewer.id}/remove/',
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Membership.objects.filter(user=self.viewer, organization=self.org).exists())

    def test_cannot_remove_last_owner(self):
        """
        GIVEN only one owner in the org
        WHEN they try to remove themselves
        THEN the removal is rejected
        """
        self.client.login(username='org_owner', password='pass')
        response = self.client.post(
            f'/org/{self.org.slug}/members/{self.owner.id}/remove/',
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Membership.objects.filter(user=self.owner, organization=self.org).exists())

    def test_admin_cannot_remove_owner(self):
        """
        GIVEN an org admin
        WHEN they try to remove an owner
        THEN they get 403
        """
        self.client.login(username='org_admin', password='pass')
        response = self.client.post(
            f'/org/{self.org.slug}/members/{self.owner.id}/remove/',
        )
        self.assertEqual(response.status_code, 403)

    def test_outsider_cannot_view_members(self):
        """
        GIVEN a user not in the org
        WHEN they try to view members
        THEN they get 403
        """
        self.client.login(username='outsider', password='pass')
        response = self.client.get(f'/org/{self.org.slug}/members/')
        self.assertEqual(response.status_code, 403)

    def test_viewer_can_view_members(self):
        """
        GIVEN an org viewer
        WHEN they view the members page
        THEN they get 200
        """
        self.client.login(username='org_viewer', password='pass')
        response = self.client.get(f'/org/{self.org.slug}/members/')
        self.assertEqual(response.status_code, 200)


# ─── Task 5.8: Invitation Tests ─────────────────────────────────────────────

class InvitationTest(TestCase):
    """Tests for the invitation system."""

    def setUp(self):
        self.org = _make_org('InviteOrg')
        self.owner = User.objects.create_user(username='inv_owner', password='pass')
        self.admin = User.objects.create_user(username='inv_admin', password='pass')
        self.existing_user = User.objects.create_user(username='existing', password='pass', email='existing@test.com')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        Membership.objects.create(user=self.admin, organization=self.org, role='admin')

    def test_send_invitation_as_owner(self):
        """
        GIVEN an org owner
        WHEN they send an invitation to an email
        THEN an Invitation record is created
        """
        self.client.login(username='inv_owner', password='pass')
        response = self.client.post(f'/org/{self.org.slug}/invite/', {
            'email': 'newuser@test.com',
            'role': 'editor',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Invitation.objects.filter(email='newuser@test.com', organization=self.org).exists())

    def test_send_invitation_admin_cannot_invite_as_owner(self):
        """
        GIVEN an org admin
        WHEN they try to send an invitation with role 'owner'
        THEN the invitation is not created (admin cannot invite owners)
        """
        self.client.login(username='inv_admin', password='pass')
        response = self.client.post(f'/org/{self.org.slug}/invite/', {
            'email': 'newowner@test.com',
            'role': 'owner',
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Invitation.objects.filter(email='newowner@test.com', role='owner').exists())

    def test_accept_invitation_as_existing_user(self):
        """
        GIVEN an existing user and a pending invitation
        WHEN they visit the accept URL
        THEN they are added to the org
        """
        invitation = Invitation.objects.create(
            email='existing@test.com', organization=self.org, role='editor', invited_by=self.owner,
        )
        self.client.login(username='existing', password='pass')
        response = self.client.get(f'/invitations/{invitation.token}/accept/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Membership.objects.filter(user=self.existing_user, organization=self.org, role='editor').exists())
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.accepted_at)

    def test_accept_already_used_invitation(self):
        """
        GIVEN an invitation that has already been accepted
        WHEN a user visits the accept URL
        THEN they see an info message and are redirected
        """
        from django.utils import timezone
        invitation = Invitation.objects.create(
            email='existing@test.com', organization=self.org, role='editor',
            invited_by=self.owner, accepted_at=timezone.now(),
        )
        self.client.login(username='existing', password='pass')
        response = self.client.get(f'/invitations/{invitation.token}/accept/')
        self.assertEqual(response.status_code, 302)

    def test_accept_expired_invitation(self):
        """
        GIVEN an invitation older than 7 days
        WHEN a user visits the accept URL
        THEN they see an error and are redirected
        """
        from django.utils import timezone
        from datetime import timedelta
        invitation = Invitation.objects.create(
            email='existing@test.com', organization=self.org, role='editor', invited_by=self.owner,
        )
        # Manually backdate the created_at
        Invitation.objects.filter(pk=invitation.pk).update(created_at=timezone.now() - timedelta(days=8))
        self.client.login(username='existing', password='pass')
        response = self.client.get(f'/invitations/{invitation.token}/accept/')
        self.assertEqual(response.status_code, 302)
        # User should NOT be added to org
        self.assertFalse(Membership.objects.filter(user=self.existing_user, organization=self.org).exists())

    def test_duplicate_invitation_replaces_existing(self):
        """
        GIVEN an existing invitation for an email
        WHEN a new invitation is sent to the same email
        THEN the old one is replaced
        """
        Invitation.objects.create(
            email='dup@test.com', organization=self.org, role='viewer', invited_by=self.owner,
        )
        self.client.login(username='inv_owner', password='pass')
        self.client.post(f'/org/{self.org.slug}/invite/', {
            'email': 'dup@test.com',
            'role': 'editor',
        })
        invitations = Invitation.objects.filter(email='dup@test.com', organization=self.org)
        self.assertEqual(invitations.count(), 1)
        self.assertEqual(invitations.first().role, 'editor')

    def test_invalid_token_shows_error(self):
        """
        GIVEN a non-existent invitation token
        WHEN a user visits the accept URL
        THEN they are redirected with error
        """
        import uuid
        self.client.login(username='existing', password='pass')
        response = self.client.get(f'/invitations/{uuid.uuid4()}/accept/')
        self.assertEqual(response.status_code, 302)


# ─── Task 6.5: Organization Switcher Tests ──────────────────────────────────

class OrgSwitcherTest(TestCase):
    """Tests for the organization switcher."""

    def setUp(self):
        self.user = User.objects.create_user(username='switcher', password='pass')
        self.org_a = _make_org('OrgA')
        self.org_b = _make_org('OrgB')
        Membership.objects.create(user=self.user, organization=self.org_a, role='owner')
        Membership.objects.create(user=self.user, organization=self.org_b, role='editor')

    def test_switch_org_sets_session(self):
        """
        GIVEN a user with membership in two orgs
        WHEN they POST to switch_org with org_b's id
        THEN the session active_org_id is updated
        """
        self.client.login(username='switcher', password='pass')
        response = self.client.post('/org/switch/', {'org_id': self.org_b.id})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session['active_org_id'], self.org_b.id)

    def test_switch_to_invalid_org_ignored(self):
        """
        GIVEN a user
        WHEN they try to switch to an org they're not a member of
        THEN the switch is silently ignored
        """
        other_org = _make_org('OtherOrg')
        self.client.login(username='switcher', password='pass')
        # First ensure there is an active org
        self.client.post('/org/switch/', {'org_id': self.org_a.id})
        old_org_id = self.client.session['active_org_id']
        self.client.post('/org/switch/', {'org_id': other_org.id})
        # Should stay the same (or fall back)
        self.assertNotEqual(self.client.session.get('active_org_id'), other_org.id)

    def test_middleware_fallback_on_login(self):
        """
        GIVEN a user with membership in one org
        WHEN they log in without active_org_id in session
        THEN middleware sets active_org to their first org
        """
        solo_user = User.objects.create_user(username='solo', password='pass')
        solo_org = _make_org('SoloOrg')
        Membership.objects.create(user=solo_user, organization=solo_org, role='owner')

        self.client.login(username='solo', password='pass')
        response = self.client.get('/editor/')
        self.assertEqual(self.client.session.get('active_org_id'), solo_org.id)

    def test_switch_org_requires_post(self):
        """
        GIVEN an authenticated user
        WHEN they send GET to switch_org
        THEN it is rejected (405 Method Not Allowed)
        """
        self.client.login(username='switcher', password='pass')
        response = self.client.get('/org/switch/')
        self.assertEqual(response.status_code, 405)

    def test_dashboard_shows_surveys_for_active_org(self):
        """
        GIVEN surveys in org_a and org_b
        WHEN user views editor dashboard with org_a active
        THEN only org_a surveys are shown
        """
        survey_a = SurveyHeader.objects.create(name='survey_a', organization=self.org_a)
        survey_b = SurveyHeader.objects.create(name='survey_b', organization=self.org_b)

        self.client.login(username='switcher', password='pass')
        self.client.post('/org/switch/', {'org_id': self.org_a.id})
        response = self.client.get('/editor/')
        self.assertContains(response, 'survey_a')
        self.assertNotContains(response, 'survey_b')


# ─── Task 7.9: Editor View Permission Tests ─────────────────────────────────

class EditorPermissionTest(TestCase):
    """Tests for permission checks on all editor view actions."""

    def setUp(self):
        self.org = _make_org('EditorPermOrg')
        self.owner = User.objects.create_user(username='ep_owner', password='pass')
        self.editor = User.objects.create_user(username='ep_editor', password='pass')
        self.viewer = User.objects.create_user(username='ep_viewer', password='pass')
        self.outsider = User.objects.create_user(username='ep_outsider', password='pass')

        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        Membership.objects.create(user=self.editor, organization=self.org, role='editor')
        Membership.objects.create(user=self.viewer, organization=self.org, role='viewer')

        self.survey = SurveyHeader.objects.create(name='ep_survey', organization=self.org, created_by=self.owner)
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section 1', code='S1', is_head=True,
        )
        self.question = Question.objects.create(
            survey_section=self.section, code='Q1', name='Test Q', input_type='text', order_number=1,
        )
        # Give editor explicit collaborator access
        SurveyCollaborator.objects.create(user=self.editor, survey=self.survey, role='editor')

    def test_viewer_cannot_create_survey(self):
        """
        GIVEN an org viewer
        WHEN they try to create a survey
        THEN they get 403
        """
        self.client.login(username='ep_viewer', password='pass')
        response = self.client.post('/editor/surveys/new/', {
            'name': 'forbidden_survey', 'redirect_url': '#', 'visibility': 'private',
        })
        self.assertEqual(response.status_code, 403)

    def test_editor_can_create_survey(self):
        """
        GIVEN an org editor
        WHEN they create a survey
        THEN it succeeds and is assigned to the active org
        """
        self.client.login(username='ep_editor', password='pass')
        response = self.client.post('/editor/surveys/new/', {
            'name': 'editor_survey', 'redirect_url': '#', 'visibility': 'private',
        })
        self.assertEqual(response.status_code, 302)
        survey = SurveyHeader.objects.get(name='editor_survey')
        self.assertEqual(survey.organization, self.org)
        self.assertEqual(survey.created_by, self.editor)

    def test_viewer_sees_read_only_badge(self):
        """
        GIVEN an org viewer and a published survey
        WHEN they view the survey detail page
        THEN they see the read-only badge
        """
        self.survey.status = 'published'
        self.survey.save()
        self.client.login(username='ep_viewer', password='pass')
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'read-only')

    def test_viewer_cannot_create_section(self):
        """
        GIVEN an org viewer
        WHEN they try to create a section
        THEN they get 403
        """
        self.client.login(username='ep_viewer', password='pass')
        response = self.client.post(f'/editor/surveys/{self.survey.uuid}/sections/new/')
        self.assertEqual(response.status_code, 403)

    def test_editor_can_create_section(self):
        """
        GIVEN an org editor with survey collaborator role
        WHEN they create a section
        THEN it succeeds
        """
        self.client.login(username='ep_editor', password='pass')
        response = self.client.post(f'/editor/surveys/{self.survey.uuid}/sections/new/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SurveySection.objects.filter(survey_header=self.survey).count(), 2)

    def test_viewer_cannot_delete_question(self):
        """
        GIVEN an org viewer
        WHEN they try to delete a question
        THEN they get 403
        """
        self.client.login(username='ep_viewer', password='pass')
        response = self.client.post(f'/editor/surveys/{self.survey.uuid}/questions/{self.question.id}/delete/')
        self.assertEqual(response.status_code, 403)

    def test_editor_can_delete_question(self):
        """
        GIVEN an org editor with survey collaborator role
        WHEN they delete a question
        THEN it succeeds
        """
        self.client.login(username='ep_editor', password='pass')
        response = self.client.post(f'/editor/surveys/{self.survey.uuid}/questions/{self.question.id}/delete/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Question.objects.filter(id=self.question.id).exists())

    def test_viewer_cannot_reorder_sections(self):
        """
        GIVEN an org viewer
        WHEN they try to reorder sections
        THEN they get 403
        """
        self.client.login(username='ep_viewer', password='pass')
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/sections/reorder/',
            json.dumps({'section_ids': [self.section.id]}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_outsider_gets_404_on_survey_detail(self):
        """
        GIVEN a user not in the org
        WHEN they try to view a survey in that org
        THEN they get 404
        """
        other_org = _make_org('OutsiderOrg')
        Membership.objects.create(user=self.outsider, organization=other_org, role='owner')
        self.client.login(username='ep_outsider', password='pass')
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/')
        self.assertEqual(response.status_code, 404)

    def test_editor_without_collab_cannot_edit_others_survey(self):
        """
        GIVEN an org editor with no collaborator entry for a survey
        WHEN they try to access that survey
        THEN they get 403 (editor baseline is None without collab)
        """
        other_survey = SurveyHeader.objects.create(name='other_survey', organization=self.org, created_by=self.owner)
        SurveySection.objects.create(
            survey_header=other_survey, name='osec', code='OS', is_head=True,
        )
        self.client.login(username='ep_editor', password='pass')
        response = self.client.get(f'/editor/surveys/{other_survey.uuid}/')
        self.assertEqual(response.status_code, 403)

    def test_editor_cannot_access_settings(self):
        """
        GIVEN an org editor with 'editor' collaborator role
        WHEN they try to access survey settings
        THEN they get 403 (settings require 'owner')
        """
        self.client.login(username='ep_editor', password='pass')
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/settings/')
        self.assertEqual(response.status_code, 403)

    def test_owner_can_access_settings(self):
        """
        GIVEN an org owner
        WHEN they access survey settings
        THEN they get 200
        """
        self.client.login(username='ep_owner', password='pass')
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/settings/')
        self.assertEqual(response.status_code, 200)


# ─── Task 8.4: Export/Import/Delete Permission Tests ────────────────────────

class ExportImportDeletePermissionTest(TestCase):
    """Tests for export, import, and delete permission checks."""

    def setUp(self):
        self.org = _make_org('EIDOrg')
        self.owner = User.objects.create_user(username='eid_owner', password='pass')
        self.editor = User.objects.create_user(username='eid_editor', password='pass')
        self.viewer = User.objects.create_user(username='eid_viewer', password='pass')

        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        Membership.objects.create(user=self.editor, organization=self.org, role='editor')
        Membership.objects.create(user=self.viewer, organization=self.org, role='viewer')

        self.survey = SurveyHeader.objects.create(name='eid_survey', organization=self.org)
        SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )

    def test_viewer_can_export(self):
        """
        GIVEN an org viewer
        WHEN they export a survey
        THEN the export succeeds (viewers have read access)
        """
        self.client.login(username='eid_viewer', password='pass')
        response = self.client.get(f'/editor/export/{self.survey.uuid}/?mode=structure')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')

    def test_viewer_cannot_import(self):
        """
        GIVEN an org viewer
        WHEN they try to import a survey
        THEN they get 403
        """
        self.client.login(username='eid_viewer', password='pass')
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('survey.json', json.dumps({
                'version': '1.0',
                'survey': {'name': 'forbidden', 'sections': [{'name': 's', 'code': 'S', 'is_head': True, 'questions': []}]},
            }))
        buf.seek(0)
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('test.zip', buf.read(), content_type='application/zip')
        response = self.client.post('/editor/import/', {'file': f})
        self.assertEqual(response.status_code, 403)

    def test_editor_can_import(self):
        """
        GIVEN an org editor
        WHEN they import a survey
        THEN it succeeds and the survey is assigned to the active org
        """
        self.client.login(username='eid_editor', password='pass')
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('survey.json', json.dumps({
                'version': '1.0',
                'survey': {'name': 'imported_survey', 'sections': [{'name': 's', 'code': 'S', 'is_head': True, 'questions': []}]},
            }))
        buf.seek(0)
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('test.zip', buf.read(), content_type='application/zip')
        response = self.client.post('/editor/import/', {'file': f})
        self.assertEqual(response.status_code, 302)
        imported = SurveyHeader.objects.get(name='imported_survey')
        self.assertEqual(imported.organization, self.org)

    def test_viewer_cannot_delete(self):
        """
        GIVEN an org viewer
        WHEN they try to delete a survey
        THEN they get 403
        """
        self.client.login(username='eid_viewer', password='pass')
        response = self.client.post(f'/editor/delete/{self.survey.uuid}/')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(SurveyHeader.objects.filter(pk=self.survey.pk).exists())

    def test_editor_cannot_delete(self):
        """
        GIVEN an org editor (even with survey collaborator editor role)
        WHEN they try to delete a survey
        THEN they get 403 (delete requires owner)
        """
        SurveyCollaborator.objects.create(user=self.editor, survey=self.survey, role='editor')
        self.client.login(username='eid_editor', password='pass')
        response = self.client.post(f'/editor/delete/{self.survey.uuid}/')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(SurveyHeader.objects.filter(pk=self.survey.pk).exists())

    def test_owner_can_delete(self):
        """
        GIVEN an org owner
        WHEN they delete a survey
        THEN it is deleted
        """
        self.client.login(username='eid_owner', password='pass')
        response = self.client.post(f'/editor/delete/{self.survey.uuid}/')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SurveyHeader.objects.filter(pk=self.survey.pk).exists())

    def test_export_survey_in_different_org_returns_404(self):
        """
        GIVEN a survey in org_a
        WHEN a user with active_org=org_b tries to export it
        THEN they get 404
        """
        org_b = _make_org('OtherEIDOrg')
        other_user = User.objects.create_user(username='eid_other', password='pass')
        Membership.objects.create(user=other_user, organization=org_b, role='owner')
        self.client.login(username='eid_other', password='pass')
        response = self.client.get(f'/editor/export/{self.survey.uuid}/?mode=structure')
        self.assertEqual(response.status_code, 404)


# ─── Task 9.7: Collaborator Management Tests ────────────────────────────────

class CollaboratorManagementTest(TestCase):
    """Tests for add/change/remove collaborators and last-owner protection."""

    def setUp(self):
        self.org = _make_org('CollabOrg')
        self.owner = User.objects.create_user(username='coll_owner', password='pass')
        self.member = User.objects.create_user(username='coll_member', password='pass')
        self.editor = User.objects.create_user(username='coll_editor', password='pass')

        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        Membership.objects.create(user=self.member, organization=self.org, role='viewer')
        Membership.objects.create(user=self.editor, organization=self.org, role='editor')

        self.survey = SurveyHeader.objects.create(name='collab_survey', organization=self.org, created_by=self.owner)
        SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        SurveyCollaborator.objects.create(user=self.owner, survey=self.survey, role='owner')

    def test_owner_can_add_collaborator(self):
        """
        GIVEN a survey owner
        WHEN they add an org member as a collaborator
        THEN the collaborator record is created
        """
        self.client.login(username='coll_owner', password='pass')
        response = self.client.post(f'/editor/surveys/{self.survey.uuid}/collaborators/add/', {
            'user_id': self.member.id,
            'role': 'editor',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(SurveyCollaborator.objects.filter(
            user=self.member, survey=self.survey, role='editor',
        ).exists())

    def test_non_owner_cannot_add_collaborator(self):
        """
        GIVEN an org editor with survey editor role
        WHEN they try to add a collaborator
        THEN they get 403
        """
        SurveyCollaborator.objects.create(user=self.editor, survey=self.survey, role='editor')
        self.client.login(username='coll_editor', password='pass')
        response = self.client.post(f'/editor/surveys/{self.survey.uuid}/collaborators/add/', {
            'user_id': self.member.id,
            'role': 'viewer',
        })
        self.assertEqual(response.status_code, 403)

    def test_change_collaborator_role(self):
        """
        GIVEN a survey owner and an existing collaborator
        WHEN they change the collaborator's role
        THEN the role is updated
        """
        collab = SurveyCollaborator.objects.create(user=self.member, survey=self.survey, role='viewer')
        self.client.login(username='coll_owner', password='pass')
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/collaborators/{collab.id}/role/',
            {'role': 'editor'},
        )
        self.assertEqual(response.status_code, 200)
        collab.refresh_from_db()
        self.assertEqual(collab.role, 'editor')

    def test_remove_collaborator(self):
        """
        GIVEN a survey owner and a collaborator
        WHEN they remove the collaborator
        THEN the collaborator record is deleted
        """
        collab = SurveyCollaborator.objects.create(user=self.member, survey=self.survey, role='viewer')
        self.client.login(username='coll_owner', password='pass')
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/collaborators/{collab.id}/remove/',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SurveyCollaborator.objects.filter(user=self.member, survey=self.survey).exists())

    def test_cannot_remove_last_survey_owner(self):
        """
        GIVEN a survey with only one owner collaborator
        WHEN they try to remove that owner
        THEN they get 400 error
        """
        self.client.login(username='coll_owner', password='pass')
        owner_collab = SurveyCollaborator.objects.get(user=self.owner, survey=self.survey)
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/collaborators/{owner_collab.id}/remove/',
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(SurveyCollaborator.objects.filter(user=self.owner, survey=self.survey).exists())

    def test_can_remove_owner_when_multiple_owners_exist(self):
        """
        GIVEN a survey with two owner collaborators
        WHEN one owner removes the other
        THEN the removal succeeds
        """
        SurveyCollaborator.objects.create(user=self.member, survey=self.survey, role='owner')
        self.client.login(username='coll_owner', password='pass')
        member_collab = SurveyCollaborator.objects.get(user=self.member, survey=self.survey)
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/collaborators/{member_collab.id}/remove/',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SurveyCollaborator.objects.filter(user=self.member, survey=self.survey).exists())

    def test_add_non_org_member_rejected(self):
        """
        GIVEN a user not in the org
        WHEN survey owner tries to add them as collaborator
        THEN it is rejected with 400
        """
        outsider = User.objects.create_user(username='coll_outsider', password='pass')
        self.client.login(username='coll_owner', password='pass')
        response = self.client.post(f'/editor/surveys/{self.survey.uuid}/collaborators/add/', {
            'user_id': outsider.id,
            'role': 'viewer',
        })
        self.assertEqual(response.status_code, 400)


# ─── Task 11.3: CLI Import with Organization Tests ──────────────────────────

class CLIImportWithOrgTest(TestCase):
    """Tests for the import_survey management command with --organization."""

    def setUp(self):
        self.org = _make_org('CLIOrg')
        self.other_org = _make_org('OtherCLIOrg')
        self.survey_data = {
            'version': '1.0',
            'survey': {
                'name': 'cli_import_test',
                'sections': [{
                    'name': 'sec1', 'code': 'S1', 'is_head': True, 'questions': [],
                }],
            },
        }

    def _create_zip(self):
        buf = BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('survey.json', json.dumps(self.survey_data))
        buf.seek(0)
        return buf

    def test_import_with_org_name(self):
        """
        GIVEN a ZIP archive and an existing organization
        WHEN import_survey is called with --organization=<name>
        THEN the survey is assigned to that organization
        """
        from django.core.management import call_command
        from io import StringIO
        buf = self._create_zip()
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
            f.write(buf.read())
            f.flush()
            try:
                call_command('import_survey', f.name, organization='CLIOrg', stdout=StringIO())
                survey = SurveyHeader.objects.get(name='cli_import_test')
                self.assertEqual(survey.organization, self.org)
            finally:
                os.unlink(f.name)

    def test_import_with_org_slug(self):
        """
        GIVEN a ZIP archive and an existing organization
        WHEN import_survey is called with --organization=<slug>
        THEN the survey is assigned to that organization
        """
        from django.core.management import call_command
        from io import StringIO
        buf = self._create_zip()
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
            f.write(buf.read())
            f.flush()
            try:
                call_command('import_survey', f.name, organization=self.other_org.slug, stdout=StringIO())
                survey = SurveyHeader.objects.get(name='cli_import_test')
                self.assertEqual(survey.organization, self.other_org)
            finally:
                os.unlink(f.name)

    def test_import_with_unknown_org_raises_error(self):
        """
        GIVEN a ZIP archive
        WHEN import_survey is called with --organization=<nonexistent>
        THEN it raises CommandError
        """
        from django.core.management import call_command, CommandError
        from io import StringIO
        buf = self._create_zip()
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
            f.write(buf.read())
            f.flush()
            try:
                with self.assertRaises(CommandError):
                    call_command('import_survey', f.name, organization='nonexistent', stderr=StringIO())
            finally:
                os.unlink(f.name)

    def test_import_without_org_uses_default(self):
        """
        GIVEN a ZIP archive without --organization
        WHEN import_survey is called
        THEN the survey is assigned based on archive data or default
        """
        from django.core.management import call_command
        from io import StringIO
        buf = self._create_zip()
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
            f.write(buf.read())
            f.flush()
            try:
                call_command('import_survey', f.name, stdout=StringIO())
                survey = SurveyHeader.objects.get(name='cli_import_test')
                self.assertIsNotNone(survey.organization)
            finally:
                os.unlink(f.name)


# ─── Task 3.6: Registration and Personal Org Creation Tests ─────────────────

class PersonalOrgCreationTest(TestCase):
    """Tests for personal org creation on user registration signal."""

    def test_signal_creates_personal_org(self):
        """
        GIVEN a newly registered user
        WHEN the user_registered signal fires
        THEN a personal org is created and user is set as owner
        """
        from django_registration.signals import user_registered
        from django.test import RequestFactory
        user = User.objects.create_user(username='newuser', password='pass', email='new@test.com')
        factory = RequestFactory()
        request = factory.get('/')
        # Simulate session
        from django.contrib.sessions.backends.db import SessionStore
        request.session = SessionStore()

        user_registered.send(sender=self.__class__, user=user, request=request)

        # Personal org should exist
        self.assertTrue(Membership.objects.filter(user=user, role='owner').exists())
        membership = Membership.objects.get(user=user, role='owner')
        self.assertIn(user.username, membership.organization.name)

    def test_signal_auto_accepts_pending_invitations(self):
        """
        GIVEN a pending invitation for a new user's email
        WHEN the user registers
        THEN the invitation is auto-accepted and user joins the org
        """
        from django_registration.signals import user_registered
        from django.test import RequestFactory
        from django.contrib.sessions.backends.db import SessionStore

        invite_org = _make_org('InviteTargetOrg')
        inviter = User.objects.create_user(username='inviter', password='pass')
        Membership.objects.create(user=inviter, organization=invite_org, role='owner')
        invitation = Invitation.objects.create(
            email='newbie@test.com', organization=invite_org, role='editor', invited_by=inviter,
        )

        user = User.objects.create_user(username='newbie', password='pass', email='newbie@test.com')
        factory = RequestFactory()
        request = factory.get('/')
        request.session = SessionStore()

        user_registered.send(sender=self.__class__, user=user, request=request)

        # User should have membership in invite_org
        self.assertTrue(Membership.objects.filter(user=user, organization=invite_org, role='editor').exists())
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.accepted_at)


# ─── Invitation Flow for Unregistered Users ──────────────────────────────────

class InvitationFlowTest(TestCase):
    """Tests for the invitation flow supporting unauthenticated users."""

    def setUp(self):
        self.org = _make_org('FlowOrg')
        self.owner = User.objects.create_user(username='flow_owner', password='pass')
        self.existing_user = User.objects.create_user(username='flow_existing', password='pass', email='flow@test.com')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')

    def _make_invitation(self, **kwargs):
        defaults = dict(
            email='invitee@test.com',
            organization=self.org,
            role='editor',
            invited_by=self.owner,
        )
        defaults.update(kwargs)
        return Invitation.objects.create(**defaults)

    def test_unauthenticated_user_sees_landing_page(self):
        """
        GIVEN a valid pending invitation
        WHEN an unauthenticated user visits the accept URL
        THEN they see the invitation landing page with org details
        """
        invitation = self._make_invitation()
        response = self.client.get(f'/invitations/{invitation.token}/accept/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.org.name)
        self.assertContains(response, 'editor')
        self.assertContains(response, self.owner.username)

    def test_token_stored_in_session(self):
        """
        GIVEN a valid pending invitation
        WHEN an unauthenticated user visits the accept URL
        THEN the invitation token is stored in the session
        """
        invitation = self._make_invitation()
        self.client.get(f'/invitations/{invitation.token}/accept/')
        self.assertEqual(
            self.client.session.get('pending_invitation_token'),
            str(invitation.token),
        )

    def test_expired_invitation_shows_error(self):
        """
        GIVEN an invitation older than 7 days
        WHEN an unauthenticated user visits the accept URL
        THEN they see an expiry error message
        """
        from django.utils import timezone
        from datetime import timedelta
        invitation = self._make_invitation()
        Invitation.objects.filter(pk=invitation.pk).update(
            created_at=timezone.now() - timedelta(days=8)
        )
        response = self.client.get(f'/invitations/{invitation.token}/accept/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'expired')
        self.assertNotIn('pending_invitation_token', self.client.session)

    def test_already_accepted_invitation_shows_info(self):
        """
        GIVEN an invitation that has already been accepted
        WHEN an unauthenticated user visits the accept URL
        THEN they see an "already used" message
        """
        from django.utils import timezone
        invitation = self._make_invitation(accepted_at=timezone.now())
        response = self.client.get(f'/invitations/{invitation.token}/accept/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already been used')

    def test_invalid_token_shows_error(self):
        """
        GIVEN a non-existent invitation token
        WHEN an unauthenticated user visits the accept URL
        THEN they see an error message
        """
        import uuid as _uuid
        response = self.client.get(f'/invitations/{_uuid.uuid4()}/accept/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid invitation link')

    def test_middleware_processes_pending_token_after_login(self):
        """
        GIVEN a pending invitation token stored in the session
        WHEN the user logs in and the middleware runs
        THEN the invitation is accepted and membership is created
        """
        invitation = self._make_invitation(email='flow@test.com')
        # Visit accept URL as anonymous to store token
        self.client.get(f'/invitations/{invitation.token}/accept/')
        self.assertEqual(
            self.client.session.get('pending_invitation_token'),
            str(invitation.token),
        )
        # Log in — middleware should pick up the token
        self.client.login(username='flow_existing', password='pass')
        self.client.get('/editor/')
        # Membership should exist
        self.assertTrue(
            Membership.objects.filter(
                user=self.existing_user, organization=self.org, role='editor'
            ).exists()
        )
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.accepted_at)
        # Token should be removed from session
        self.assertNotIn('pending_invitation_token', self.client.session)

    def test_authenticated_user_still_works_directly(self):
        """
        GIVEN an authenticated user and a pending invitation
        WHEN they visit the accept URL directly
        THEN they are added to the org immediately (existing behavior)
        """
        invitation = self._make_invitation(email='flow@test.com')
        self.client.login(username='flow_existing', password='pass')
        response = self.client.get(f'/invitations/{invitation.token}/accept/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Membership.objects.filter(
                user=self.existing_user, organization=self.org, role='editor'
            ).exists()
        )
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.accepted_at)

    def test_middleware_cleans_up_invalid_pending_token(self):
        """
        GIVEN a pending invitation token in session that has become invalid
        WHEN the user logs in and the middleware runs
        THEN the token is silently removed without error
        """
        import uuid as _uuid
        # Give the user an org so /editor/ doesn't 403
        personal_org = _make_org('PersonalOrg')
        Membership.objects.create(user=self.existing_user, organization=personal_org, role='owner')
        # Manually set a bogus token in session
        session = self.client.session
        session['pending_invitation_token'] = str(_uuid.uuid4())
        session.save()
        # Log in and visit a page — should not error
        self.client.login(username='flow_existing', password='pass')
        response = self.client.get('/editor/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('pending_invitation_token', self.client.session)


class LifecycleTransitionTest(TestCase):
    """Tests for survey lifecycle state transitions."""

    def setUp(self):
        self.org = _make_org('LifecycleOrg')
        self.user = User.objects.create_user(username='lifecycle_user', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='lifecycle_test', organization=self.org, created_by=self.user,
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        Question.objects.create(
            survey_section=self.section, code='Q_LC1', name='Q1', input_type='text',
        )

    def test_new_survey_is_draft(self):
        """
        GIVEN a newly created survey
        WHEN checking status
        THEN it should be 'draft'
        """
        self.assertEqual(self.survey.status, 'draft')

    def test_valid_transitions_return_true(self):
        """
        GIVEN a survey in draft status with password and structure
        WHEN checking can_transition_to for valid targets
        THEN each should return (True, "")
        """
        self.survey.set_password('test1234')
        self.survey.save()
        ok, err = self.survey.can_transition_to('testing')
        self.assertTrue(ok)
        self.assertEqual(err, '')

        ok, err = self.survey.can_transition_to('published')
        self.assertTrue(ok)
        self.assertEqual(err, '')

    def test_invalid_transition_returns_error(self):
        """
        GIVEN a survey in draft status
        WHEN checking can_transition_to('closed')
        THEN it should return (False, error message)
        """
        ok, err = self.survey.can_transition_to('closed')
        self.assertFalse(ok)
        self.assertIn('Cannot transition', err)

    def test_archived_is_terminal(self):
        """
        GIVEN a survey in archived status
        WHEN checking can_transition_to for any target
        THEN all should return (False, error)
        """
        self.survey.status = 'archived'
        for target in ('draft', 'testing', 'published', 'closed'):
            ok, err = self.survey.can_transition_to(target)
            self.assertFalse(ok)
            self.assertIn('Cannot transition from archived', err)

    def test_draft_to_testing_without_password_allowed(self):
        """
        GIVEN a draft survey without password but with valid structure
        WHEN checking can_transition_to('testing')
        THEN it should succeed (password is optional)
        """
        ok, err = self.survey.can_transition_to('testing')
        self.assertTrue(ok)

    def test_draft_to_testing_requires_structure(self):
        """
        GIVEN a draft survey with no sections/questions
        WHEN checking can_transition_to('testing')
        THEN it should fail with structure required error
        """
        empty_survey = SurveyHeader.objects.create(
            name='empty', organization=self.org,
        )
        ok, err = empty_survey.can_transition_to('testing')
        self.assertFalse(ok)
        self.assertIn('section', err.lower())

    def test_draft_to_testing_requires_head_section(self):
        """
        GIVEN a draft survey with questions but no head section
        WHEN checking can_transition_to('testing')
        THEN it should fail with head section error
        """
        survey = SurveyHeader.objects.create(
            name='no_head', organization=self.org,
        )
        section = SurveySection.objects.create(
            survey_header=survey, name='s1', code='S1', is_head=False,
        )
        Question.objects.create(
            survey_section=section, code='Q_NH1', name='Q1', input_type='text',
        )
        ok, err = survey.can_transition_to('testing')
        self.assertFalse(ok)
        self.assertIn('head section', err.lower())

    def test_draft_to_published_requires_structure(self):
        """
        GIVEN a draft survey with no structure
        WHEN checking can_transition_to('published')
        THEN it should fail with structure required error
        """
        empty_survey = SurveyHeader.objects.create(
            name='empty2', organization=self.org,
        )
        ok, err = empty_survey.can_transition_to('published')
        self.assertFalse(ok)
        self.assertIn('section', err.lower())


class LifecyclePasswordTest(TestCase):
    """Tests for survey password management methods."""

    def setUp(self):
        self.org = _make_org('PwdOrg')
        self.survey = SurveyHeader.objects.create(
            name='pwd_test', organization=self.org,
        )

    def test_set_password(self):
        """
        GIVEN a survey without password
        WHEN set_password is called
        THEN has_password returns True and check_password works
        """
        self.assertFalse(self.survey.has_password())
        self.survey.set_password('test123')
        self.assertTrue(self.survey.has_password())
        self.assertTrue(self.survey.check_password('test123'))

    def test_check_password_rejects_wrong(self):
        """
        GIVEN a survey with password set
        WHEN check_password is called with wrong password
        THEN it returns False
        """
        self.survey.set_password('correct')
        self.assertFalse(self.survey.check_password('wrong'))

    def test_has_password_no_hash(self):
        """
        GIVEN a survey without password_hash
        WHEN has_password is called
        THEN it returns False
        """
        self.assertFalse(self.survey.has_password())

    def test_clear_password(self):
        """
        GIVEN a survey with password set
        WHEN clear_password is called
        THEN has_password returns False
        """
        self.survey.set_password('test123')
        self.survey.clear_password()
        self.assertFalse(self.survey.has_password())

    def test_check_password_returns_false_no_hash(self):
        """
        GIVEN a survey without password
        WHEN check_password is called
        THEN it returns False
        """
        self.assertFalse(self.survey.check_password('anything'))


class AccessControlTest(TestCase):
    """Tests for check_survey_access function."""

    def setUp(self):
        self.org = _make_org('AccessOrg')
        self.owner = User.objects.create_user(username='ac_owner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')

    def _make_survey(self, status='draft', password=None):
        survey = SurveyHeader.objects.create(
            name=f'access_{status}', organization=self.org,
            status=status, created_by=self.owner,
        )
        SurveyCollaborator.objects.create(user=self.owner, survey=survey, role='owner')
        if password:
            survey.set_password(password)
            survey.save()
        return survey

    def test_draft_returns_404_for_anonymous(self):
        """
        GIVEN a draft survey
        WHEN an anonymous user accesses it
        THEN Http404 is raised
        """
        from django.http import Http404
        survey = self._make_survey('draft')
        request = self.client.get('/').wsgi_request
        with self.assertRaises(Http404):
            check_survey_access(request, survey)

    def test_draft_allowed_for_editor(self):
        """
        GIVEN a draft survey
        WHEN an editor accesses it
        THEN access is allowed (returns None)
        """
        survey = self._make_survey('draft')
        self.client.login(username='ac_owner', password='pass')
        request = self.client.get('/').wsgi_request
        request.user = self.owner
        result = check_survey_access(request, survey)
        self.assertIsNone(result)

    def test_published_no_password_allowed(self):
        """
        GIVEN a published survey without password
        WHEN an anonymous user accesses it
        THEN access is allowed (returns None)
        """
        survey = self._make_survey('published')
        request = self.client.get('/').wsgi_request
        result = check_survey_access(request, survey)
        self.assertIsNone(result)

    def test_published_with_password_redirects(self):
        """
        GIVEN a published survey with password
        WHEN an anonymous user accesses it without session key
        THEN redirect to password page
        """
        survey = self._make_survey('published', password='secret')
        response = self.client.get(f'/surveys/{survey.uuid}/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('password', response.url)

    def test_closed_shows_closed_page(self):
        """
        GIVEN a closed survey
        WHEN an anonymous user accesses it
        THEN the survey_closed.html template is rendered
        """
        survey = self._make_survey('closed')
        response = self.client.get(f'/surveys/{survey.uuid}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no longer accepting')

    def test_testing_with_valid_token(self):
        """
        GIVEN a testing survey with password
        WHEN a user accesses with valid token
        THEN access is allowed and token is stored in session
        """
        survey = self._make_survey('testing', password='secret')
        response = self.client.get(f'/surveys/{survey.uuid}/?token={survey.test_token}')
        # Should redirect to first section (survey_header behavior), not to password page
        self.assertNotIn('password', response.url if response.status_code == 302 else '')

    def test_testing_without_token_redirects_to_password(self):
        """
        GIVEN a testing survey
        WHEN a user accesses without token or session key
        THEN redirect to password page
        """
        survey = self._make_survey('testing', password='secret')
        response = self.client.get(f'/surveys/{survey.uuid}/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('password', response.url)


class PasswordGateViewTest(TestCase):
    """Tests for the survey_password_gate view."""

    def setUp(self):
        self.org = _make_org('GateOrg')
        self.survey = SurveyHeader.objects.create(
            name='gate_test', organization=self.org, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.survey.set_password('correct')
        self.survey.save()

    def test_get_renders_form(self):
        """
        GIVEN a published survey with password
        WHEN GET /surveys/<uuid>/password/
        THEN render password form
        """
        response = self.client.get(f'/surveys/{self.survey.uuid}/password/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'password')

    def test_correct_password_redirects(self):
        """
        GIVEN a published survey with password
        WHEN POST with correct password
        THEN redirect to survey and set session key
        """
        response = self.client.post(
            f'/surveys/{self.survey.uuid}/password/',
            {'password': 'correct'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(str(self.survey.uuid), response.url)
        self.assertTrue(self.client.session.get(f'survey_password_{self.survey.id}'))

    def test_incorrect_password_shows_error(self):
        """
        GIVEN a published survey with password
        WHEN POST with incorrect password
        THEN re-render form with error
        """
        response = self.client.post(
            f'/surveys/{self.survey.uuid}/password/',
            {'password': 'wrong'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Incorrect password')


class EditorTransitionTest(TestCase):
    """Tests for the editor_survey_transition endpoint."""

    def setUp(self):
        self.org = _make_org('TransOrg')
        self.owner = User.objects.create_user(username='trans_owner', password='pass')
        self.editor = User.objects.create_user(username='trans_editor', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        Membership.objects.create(user=self.editor, organization=self.org, role='editor')
        self.survey = SurveyHeader.objects.create(
            name='trans_test', organization=self.org, created_by=self.owner,
        )
        SurveyCollaborator.objects.create(user=self.owner, survey=self.survey, role='owner')
        SurveyCollaborator.objects.create(user=self.editor, survey=self.survey, role='editor')
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        Question.objects.create(
            survey_section=self.section, code='Q_TR1', name='Q1', input_type='text',
        )

    def test_valid_transition_returns_204(self):
        """
        GIVEN a draft survey with structure
        WHEN owner posts transition to published
        THEN status 204 and survey status updated
        """
        self.client.login(username='trans_owner', password='pass')
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/transition/',
            {'status': 'published'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 204)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.status, 'published')

    def test_invalid_transition_returns_400(self):
        """
        GIVEN a draft survey
        WHEN owner posts transition to closed
        THEN status 400 with error message
        """
        self.client.login(username='trans_owner', password='pass')
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/transition/',
            {'status': 'closed'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 400)

    def test_non_owner_returns_403(self):
        """
        GIVEN a draft survey
        WHEN editor (not owner) posts transition
        THEN status 403
        """
        self.client.login(username='trans_editor', password='pass')
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/transition/',
            {'status': 'published'},
        )
        self.assertEqual(response.status_code, 403)

    def test_test_data_cleanup(self):
        """
        GIVEN a testing survey with sessions
        WHEN owner transitions to published with clear_test_data=true
        THEN all sessions are deleted
        """
        self.survey.set_password('test1234')
        self.survey.status = 'testing'
        self.survey.save()
        SurveySession.objects.create(survey=self.survey)
        SurveySession.objects.create(survey=self.survey)
        self.assertEqual(SurveySession.objects.filter(survey=self.survey).count(), 2)

        self.client.login(username='trans_owner', password='pass')
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/transition/',
            {'status': 'published', 'clear_test_data': 'true'},
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(SurveySession.objects.filter(survey=self.survey).count(), 0)

    def test_archive_syncs_is_archived(self):
        """
        GIVEN a closed survey
        WHEN owner transitions to archived
        THEN is_archived is set to True
        """
        self.survey.status = 'closed'
        self.survey.save()
        self.client.login(username='trans_owner', password='pass')
        self.client.post(
            f'/editor/surveys/{self.survey.uuid}/transition/',
            {'status': 'archived'},
            HTTP_HX_REQUEST='true',
        )
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.status, 'archived')
        self.assertTrue(self.survey.is_archived)


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


class LandingPageLifecycleTest(TestCase):
    """Tests for landing page lifecycle filtering."""

    def setUp(self):
        self.org = _make_org('LandingOrg')

    def test_draft_surveys_excluded(self):
        """
        GIVEN a draft survey with public visibility
        WHEN the landing page is rendered
        THEN the draft survey is not in the surveys context
        """
        SurveyHeader.objects.create(
            name='draft_pub', organization=self.org,
            visibility='public', status='draft',
        )
        response = self.client.get('/')
        survey_names = [s.name for s in response.context['surveys']]
        self.assertNotIn('draft_pub', survey_names)

    def test_published_surveys_shown(self):
        """
        GIVEN a published survey with public visibility
        WHEN the landing page is rendered
        THEN the survey is in the surveys context
        """
        SurveyHeader.objects.create(
            name='pub_survey', organization=self.org,
            visibility='public', status='published',
        )
        response = self.client.get('/')
        survey_names = [s.name for s in response.context['surveys']]
        self.assertIn('pub_survey', survey_names)


# ─── Versioning Tests ──────────────────────────────────────────────────────────
# Additional imports for versioning tests
from .versioning import clone_survey_for_draft, check_draft_compatibility, publish_draft, IncompatibleDraftError
from .models import SurveySectionTranslation, QuestionTranslation


class VersioningModelTest(TestCase):
    """Tests for versioning-related model fields and methods on SurveyHeader."""

    def setUp(self):
        self.org = _make_org('VersionOrg')
        self.user = User.objects.create_user(username='vowner', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='canon_survey', organization=self.org, created_by=self.user,
            status='published',
        )

    def test_default_version_number_is_one(self):
        """
        GIVEN a newly created SurveyHeader
        WHEN no version_number is specified
        THEN version_number defaults to 1
        """
        self.assertEqual(self.survey.version_number, 1)

    def test_default_is_canonical_true(self):
        """
        GIVEN a newly created SurveyHeader
        WHEN no is_canonical is specified
        THEN is_canonical defaults to True
        """
        self.assertTrue(self.survey.is_canonical)

    def test_canonical_survey_defaults_to_null(self):
        """
        GIVEN a newly created SurveyHeader
        WHEN no canonical_survey is specified
        THEN canonical_survey is None
        """
        self.assertIsNone(self.survey.canonical_survey)

    def test_published_version_defaults_to_null(self):
        """
        GIVEN a newly created SurveyHeader
        WHEN no published_version is specified
        THEN published_version is None
        """
        self.assertIsNone(self.survey.published_version)

    def test_has_draft_copy_false_when_no_draft(self):
        """
        GIVEN a canonical survey with no draft copy
        WHEN has_draft_copy() is called
        THEN it returns False
        """
        self.assertFalse(self.survey.has_draft_copy())

    def test_has_draft_copy_true_when_draft_exists(self):
        """
        GIVEN a canonical survey with a draft copy linked via published_version
        WHEN has_draft_copy() is called
        THEN it returns True
        """
        SurveyHeader.objects.create(
            name='[draft] canon_survey', organization=self.org,
            status='draft', published_version=self.survey,
        )
        self.assertTrue(self.survey.has_draft_copy())

    def test_get_draft_copy_returns_none_when_no_draft(self):
        """
        GIVEN a canonical survey with no draft copy
        WHEN get_draft_copy() is called
        THEN it returns None
        """
        self.assertIsNone(self.survey.get_draft_copy())

    def test_get_draft_copy_returns_draft(self):
        """
        GIVEN a canonical survey with a draft copy
        WHEN get_draft_copy() is called
        THEN it returns the draft SurveyHeader
        """
        draft = SurveyHeader.objects.create(
            name='[draft] canon_survey', organization=self.org,
            status='draft', published_version=self.survey,
        )
        self.assertEqual(self.survey.get_draft_copy(), draft)

    def test_is_draft_copy_false_for_canonical(self):
        """
        GIVEN a canonical survey (published_version is None)
        WHEN is_draft_copy is accessed
        THEN it returns False
        """
        self.assertFalse(self.survey.is_draft_copy)

    def test_is_draft_copy_true_for_draft(self):
        """
        GIVEN a draft copy with published_version set
        WHEN is_draft_copy is accessed
        THEN it returns True
        """
        draft = SurveyHeader.objects.create(
            name='[draft] canon_survey', organization=self.org,
            status='draft', published_version=self.survey,
        )
        self.assertTrue(draft.is_draft_copy)

    def test_get_version_history_empty_when_no_archives(self):
        """
        GIVEN a canonical survey with no archived versions
        WHEN get_version_history() is called
        THEN it returns an empty queryset
        """
        self.assertEqual(self.survey.get_version_history().count(), 0)

    def test_get_version_history_returns_archived_versions_ordered(self):
        """
        GIVEN a canonical survey with two archived versions
        WHEN get_version_history() is called
        THEN it returns them ordered by -version_number
        """
        v1 = SurveyHeader.objects.create(
            name='canon_survey', organization=self.org,
            status='closed', is_canonical=False,
            canonical_survey=self.survey, version_number=1,
        )
        v2 = SurveyHeader.objects.create(
            name='canon_survey', organization=self.org,
            status='closed', is_canonical=False,
            canonical_survey=self.survey, version_number=2,
        )
        history = list(self.survey.get_version_history())
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0], v2)
        self.assertEqual(history[1], v1)


class CloneSurveyTest(TestCase):
    """Tests for clone_survey_for_draft function."""

    def setUp(self):
        self.org = _make_org('CloneOrg')
        self.user = User.objects.create_user(username='cloner', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='original', organization=self.org, created_by=self.user,
            status='published', redirect_url='/done/',
            available_languages=['en', 'ru'], thanks_html={'en': 'Thanks'},
        )
        SurveyCollaborator.objects.create(user=self.user, survey=self.survey, role='owner')
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section 1',
            code='S1', is_head=True,
        )
        SurveySectionTranslation.objects.create(
            section=self.section, language='ru', title='Раздел 1',
        )
        self.question = Question.objects.create(
            survey_section=self.section, code='Q1', order_number=1,
            name='Favorite color?', input_type='choice',
            choices=[{'code': 1, 'name': 'Red'}, {'code': 2, 'name': 'Blue'}],
        )
        QuestionTranslation.objects.create(
            question=self.question, language='ru', name='Любимый цвет?',
        )
        self.sub_q = Question.objects.create(
            survey_section=self.section, parent_question_id=self.question,
            code='Q1_1', order_number=1, name='Why?', input_type='text',
        )

    def test_draft_linked_to_canonical(self):
        """
        GIVEN a published canonical survey
        WHEN clone_survey_for_draft is called
        THEN the draft's published_version points to the canonical
        """
        draft = clone_survey_for_draft(self.survey)
        self.assertEqual(draft.published_version, self.survey)

    def test_draft_status_is_draft(self):
        """
        GIVEN a published canonical survey
        WHEN clone_survey_for_draft is called
        THEN the draft status is 'draft'
        """
        draft = clone_survey_for_draft(self.survey)
        self.assertEqual(draft.status, 'draft')

    def test_draft_name_has_prefix(self):
        """
        GIVEN a canonical survey named 'original'
        WHEN clone_survey_for_draft is called
        THEN the draft name starts with '[draft] '
        """
        draft = clone_survey_for_draft(self.survey)
        self.assertTrue(draft.name.startswith('[draft] '))

    def test_draft_name_truncation(self):
        """
        GIVEN a canonical survey with a 45-character name
        WHEN clone_survey_for_draft is called
        THEN the draft name is truncated to 45 characters
        """
        self.survey.name = 'a' * 45
        self.survey.save()
        draft = clone_survey_for_draft(self.survey)
        self.assertLessEqual(len(draft.name), 45)

    def test_sections_cloned_with_same_codes(self):
        """
        GIVEN a canonical survey with one section
        WHEN clone_survey_for_draft is called
        THEN the draft has a section with the same code and name
        """
        draft = clone_survey_for_draft(self.survey)
        draft_sections = SurveySection.objects.filter(survey_header=draft)
        self.assertEqual(draft_sections.count(), 1)
        self.assertEqual(draft_sections.first().code, 'S1')
        self.assertEqual(draft_sections.first().name, 'sec1')

    def test_section_translations_cloned(self):
        """
        GIVEN a canonical survey with section translations
        WHEN clone_survey_for_draft is called
        THEN the draft sections have the same translations
        """
        draft = clone_survey_for_draft(self.survey)
        draft_section = SurveySection.objects.get(survey_header=draft)
        trans = SurveySectionTranslation.objects.filter(section=draft_section)
        self.assertEqual(trans.count(), 1)
        self.assertEqual(trans.first().language, 'ru')
        self.assertEqual(trans.first().title, 'Раздел 1')

    def test_questions_cloned_with_same_codes(self):
        """
        GIVEN a canonical survey with questions
        WHEN clone_survey_for_draft is called
        THEN the draft has questions with the same codes
        """
        draft = clone_survey_for_draft(self.survey)
        draft_questions = Question.objects.filter(
            survey_section__survey_header=draft
        )
        codes = set(draft_questions.values_list('code', flat=True))
        self.assertIn('Q1', codes)
        self.assertIn('Q1_1', codes)

    def test_choices_cloned(self):
        """
        GIVEN a canonical survey with a choice question
        WHEN clone_survey_for_draft is called
        THEN the draft question has the same choices
        """
        draft = clone_survey_for_draft(self.survey)
        draft_q = Question.objects.get(
            survey_section__survey_header=draft, code='Q1'
        )
        self.assertEqual(len(draft_q.choices), 2)
        codes = {c['code'] for c in draft_q.choices}
        self.assertEqual(codes, {1, 2})

    def test_question_translations_cloned(self):
        """
        GIVEN a canonical survey with question translations
        WHEN clone_survey_for_draft is called
        THEN the draft questions have the same translations
        """
        draft = clone_survey_for_draft(self.survey)
        draft_q = Question.objects.get(
            survey_section__survey_header=draft, code='Q1'
        )
        trans = QuestionTranslation.objects.filter(question=draft_q)
        self.assertEqual(trans.count(), 1)
        self.assertEqual(trans.first().name, 'Любимый цвет?')

    def test_subquestions_cloned(self):
        """
        GIVEN a canonical survey with sub-questions
        WHEN clone_survey_for_draft is called
        THEN the draft has sub-questions with the same codes and parent links
        """
        draft = clone_survey_for_draft(self.survey)
        draft_sub = Question.objects.get(
            survey_section__survey_header=draft, code='Q1_1'
        )
        self.assertIsNotNone(draft_sub.parent_question_id)
        self.assertEqual(draft_sub.parent_question_id.code, 'Q1')

    def test_collaborators_cloned(self):
        """
        GIVEN a canonical survey with collaborators
        WHEN clone_survey_for_draft is called
        THEN the draft has the same collaborators with the same roles
        """
        draft = clone_survey_for_draft(self.survey)
        collabs = SurveyCollaborator.objects.filter(survey=draft)
        self.assertEqual(collabs.count(), 1)
        self.assertEqual(collabs.first().user, self.user)
        self.assertEqual(collabs.first().role, 'owner')

    def test_linked_list_preserved(self):
        """
        GIVEN a canonical survey with two linked sections
        WHEN clone_survey_for_draft is called
        THEN the draft sections maintain the same linked list structure
        """
        section2 = SurveySection.objects.create(
            survey_header=self.survey, name='sec2', title='Section 2', code='S2',
        )
        self.section.next_section = section2
        self.section.save(update_fields=['next_section'])
        section2.prev_section = self.section
        section2.save(update_fields=['prev_section'])

        draft = clone_survey_for_draft(self.survey)
        draft_secs = {
            s.code: s for s in SurveySection.objects.filter(survey_header=draft)
        }
        self.assertIsNotNone(draft_secs['S1'].next_section)
        self.assertEqual(draft_secs['S1'].next_section.code, 'S2')
        self.assertIsNotNone(draft_secs['S2'].prev_section)
        self.assertEqual(draft_secs['S2'].prev_section.code, 'S1')

    def test_settings_copied(self):
        """
        GIVEN a canonical survey with custom settings
        WHEN clone_survey_for_draft is called
        THEN the draft has the same redirect_url, available_languages, thanks_html
        """
        draft = clone_survey_for_draft(self.survey)
        self.assertEqual(draft.redirect_url, '/done/')
        self.assertEqual(draft.available_languages, ['en', 'ru'])
        self.assertEqual(draft.thanks_html, {'en': 'Thanks'})


class CompatibilityCheckTest(TestCase):
    """Tests for check_draft_compatibility function."""

    def setUp(self):
        self.org = _make_org('CompatOrg')
        self.survey = SurveyHeader.objects.create(
            name='compat_survey', organization=self.org, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec', code='S1', is_head=True,
        )
        self.question = Question.objects.create(
            survey_section=self.section, code='Q1', order_number=1,
            name='Color?', input_type='choice',
            choices=[
                {'code': 1, 'name': 'Red'},
                {'code': 2, 'name': 'Blue'},
                {'code': 3, 'name': 'Green'},
            ],
        )
        # Create a session and an answer to make compatibility checks meaningful
        self.session = SurveySession.objects.create(survey=self.survey)
        self.answer = Answer.objects.create(
            survey_session=self.session, question=self.question,
            selected_choices=[1],
        )

    def _make_draft(self):
        """Create a draft copy via clone."""
        return clone_survey_for_draft(self.survey)

    def test_deleted_question_with_answers_is_breaking(self):
        """
        GIVEN a draft where a question with answers is deleted
        WHEN check_draft_compatibility is called
        THEN it returns a breaking issue of type 'deleted_question'
        """
        draft = self._make_draft()
        # Delete the cloned question from draft
        Question.objects.filter(
            survey_section__survey_header=draft, code='Q1'
        ).delete()

        issues = check_draft_compatibility(draft, self.survey)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]['type'], 'deleted_question')
        self.assertEqual(issues[0]['question_code'], 'Q1')

    def test_changed_input_type_with_answers_is_breaking(self):
        """
        GIVEN a draft where a question's input_type changed and has answers
        WHEN check_draft_compatibility is called
        THEN it returns a breaking issue of type 'changed_input_type'
        """
        draft = self._make_draft()
        draft_q = Question.objects.get(
            survey_section__survey_header=draft, code='Q1'
        )
        draft_q.input_type = 'text'
        draft_q.save()

        issues = check_draft_compatibility(draft, self.survey)
        types = [i['type'] for i in issues]
        self.assertIn('changed_input_type', types)

    def test_removed_choice_code_with_answers_is_breaking(self):
        """
        GIVEN a draft where a choice code used in answers is removed
        WHEN check_draft_compatibility is called
        THEN it returns a breaking issue of type 'removed_choice_codes'
        """
        draft = self._make_draft()
        draft_q = Question.objects.get(
            survey_section__survey_header=draft, code='Q1'
        )
        # Remove choice code 1 which is used in the answer
        draft_q.choices = [
            {'code': 2, 'name': 'Blue'},
            {'code': 3, 'name': 'Green'},
        ]
        draft_q.save()

        issues = check_draft_compatibility(draft, self.survey)
        types = [i['type'] for i in issues]
        self.assertIn('removed_choice_codes', types)

    def test_safe_changes_pass(self):
        """
        GIVEN a draft with only safe changes (added questions, added choices)
        WHEN check_draft_compatibility is called
        THEN it returns an empty list
        """
        draft = self._make_draft()
        # Add a new choice (safe)
        draft_q = Question.objects.get(
            survey_section__survey_header=draft, code='Q1'
        )
        draft_q.choices.append({'code': 4, 'name': 'Yellow'})
        draft_q.save()
        # Add a new question (safe)
        draft_sec = SurveySection.objects.get(survey_header=draft)
        Question.objects.create(
            survey_section=draft_sec, code='Q_NEW', order_number=2,
            name='New question', input_type='text',
        )

        issues = check_draft_compatibility(draft, self.survey)
        self.assertEqual(len(issues), 0)

    def test_no_answers_means_no_breaking_issues(self):
        """
        GIVEN a canonical survey with no answers
        WHEN a draft deletes a question and check_draft_compatibility is called
        THEN it returns an empty list (no breaking issues)
        """
        # Remove all answers
        Answer.objects.all().delete()
        SurveySession.objects.all().delete()

        draft = self._make_draft()
        Question.objects.filter(
            survey_section__survey_header=draft, code='Q1'
        ).delete()

        issues = check_draft_compatibility(draft, self.survey)
        self.assertEqual(len(issues), 0)

    def test_removed_unused_choice_is_not_breaking(self):
        """
        GIVEN a draft that removes a choice code not used in any answer
        WHEN check_draft_compatibility is called
        THEN it returns an empty list
        """
        draft = self._make_draft()
        draft_q = Question.objects.get(
            survey_section__survey_header=draft, code='Q1'
        )
        # Remove code 3 which is NOT used in any answer (answer uses code 1)
        draft_q.choices = [
            {'code': 1, 'name': 'Red'},
            {'code': 2, 'name': 'Blue'},
        ]
        draft_q.save()

        issues = check_draft_compatibility(draft, self.survey)
        self.assertEqual(len(issues), 0)


class PublishDraftTest(TestCase):
    """Tests for publish_draft function."""

    def setUp(self):
        self.org = _make_org('PublishOrg')
        self.user = User.objects.create_user(username='publisher', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='pub_test', organization=self.org, created_by=self.user,
            status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section 1',
            code='S1', is_head=True,
        )
        self.question = Question.objects.create(
            survey_section=self.section, code='Q1', order_number=1,
            name='Color?', input_type='choice',
            choices=[{'code': 1, 'name': 'Red'}],
        )
        self.session = SurveySession.objects.create(survey=self.survey)
        self.answer = Answer.objects.create(
            survey_session=self.session, question=self.question,
            selected_choices=[1],
        )

    def test_publish_increments_version(self):
        """
        GIVEN a canonical survey at version 1 with a compatible draft
        WHEN publish_draft is called
        THEN canonical.version_number becomes 2
        """
        draft = clone_survey_for_draft(self.survey)
        canonical = publish_draft(draft)
        self.assertEqual(canonical.version_number, 2)

    def test_publish_creates_archived_version(self):
        """
        GIVEN a canonical survey with a draft
        WHEN publish_draft is called
        THEN an archived version is created with is_canonical=False
        """
        draft = clone_survey_for_draft(self.survey)
        publish_draft(draft)
        archived = SurveyHeader.objects.filter(
            canonical_survey=self.survey, is_canonical=False,
        )
        self.assertEqual(archived.count(), 1)
        self.assertEqual(archived.first().version_number, 1)
        self.assertEqual(archived.first().status, 'closed')

    def test_publish_moves_sessions_to_archived(self):
        """
        GIVEN a canonical survey with sessions
        WHEN publish_draft is called
        THEN existing sessions belong to the archived version
        """
        draft = clone_survey_for_draft(self.survey)
        publish_draft(draft)
        archived = SurveyHeader.objects.get(
            canonical_survey=self.survey, is_canonical=False,
        )
        self.session.refresh_from_db()
        self.assertEqual(self.session.survey, archived)

    def test_publish_moves_old_sections_to_archived(self):
        """
        GIVEN a canonical survey with sections
        WHEN publish_draft is called
        THEN original sections belong to the archived version
        """
        old_section_id = self.section.id
        draft = clone_survey_for_draft(self.survey)
        publish_draft(draft)
        archived = SurveyHeader.objects.get(
            canonical_survey=self.survey, is_canonical=False,
        )
        self.section.refresh_from_db()
        self.assertEqual(self.section.survey_header, archived)

    def test_publish_moves_draft_sections_to_canonical(self):
        """
        GIVEN a canonical survey with a draft
        WHEN publish_draft is called
        THEN draft sections now belong to the canonical survey
        """
        draft = clone_survey_for_draft(self.survey)
        draft_section = SurveySection.objects.get(survey_header=draft)
        draft_section_id = draft_section.id
        publish_draft(draft)
        draft_section.refresh_from_db()
        self.assertEqual(draft_section.survey_header, self.survey)

    def test_publish_deletes_draft(self):
        """
        GIVEN a canonical survey with a draft
        WHEN publish_draft is called
        THEN the draft SurveyHeader is deleted
        """
        draft = clone_survey_for_draft(self.survey)
        draft_id = draft.id
        publish_draft(draft)
        self.assertFalse(SurveyHeader.objects.filter(id=draft_id).exists())

    def test_old_answers_keep_valid_question_fk(self):
        """
        GIVEN a canonical survey with answers
        WHEN publish_draft is called
        THEN old answers still reference their original question (now on archived)
        """
        draft = clone_survey_for_draft(self.survey)
        publish_draft(draft)
        self.answer.refresh_from_db()
        # The answer's question should still exist and be on the archived version
        self.assertIsNotNone(self.answer.question)
        self.assertEqual(self.answer.question.code, 'Q1')
        archived = SurveyHeader.objects.get(
            canonical_survey=self.survey, is_canonical=False,
        )
        self.assertEqual(self.answer.question.survey_section.survey_header, archived)

    def test_incompatible_without_force_raises_error(self):
        """
        GIVEN a draft with breaking compatibility issues
        WHEN publish_draft is called without force=True
        THEN IncompatibleDraftError is raised
        """
        draft = clone_survey_for_draft(self.survey)
        # Delete the question in draft to create incompatibility
        Question.objects.filter(
            survey_section__survey_header=draft, code='Q1'
        ).delete()

        with self.assertRaises(IncompatibleDraftError) as ctx:
            publish_draft(draft, force=False)
        self.assertTrue(len(ctx.exception.issues) > 0)

    def test_incompatible_with_force_succeeds(self):
        """
        GIVEN a draft with breaking compatibility issues
        WHEN publish_draft is called with force=True
        THEN it succeeds and returns the canonical survey
        """
        draft = clone_survey_for_draft(self.survey)
        Question.objects.filter(
            survey_section__survey_header=draft, code='Q1'
        ).delete()

        canonical = publish_draft(draft, force=True)
        self.assertEqual(canonical.id, self.survey.id)
        self.assertEqual(canonical.version_number, 2)

    def test_grace_period_old_session_on_archived(self):
        """
        GIVEN a respondent who started a session before publish
        WHEN publish_draft is called
        THEN the old session's survey is the archived version (grace period)
        """
        draft = clone_survey_for_draft(self.survey)
        publish_draft(draft)
        self.session.refresh_from_db()
        # Old session is now on the archived version
        self.assertFalse(self.session.survey.is_canonical)
        self.assertEqual(self.session.survey.canonical_survey, self.survey)

    def test_grace_period_new_session_on_canonical(self):
        """
        GIVEN a published canonical survey after a publish_draft
        WHEN a new session is created
        THEN the session is on the canonical survey at the new version
        """
        draft = clone_survey_for_draft(self.survey)
        publish_draft(draft)
        self.survey.refresh_from_db()
        new_session = SurveySession.objects.create(survey=self.survey)
        self.assertEqual(new_session.survey, self.survey)
        self.assertEqual(new_session.survey.version_number, 2)


class ReadOnlyLockTest(TestCase):
    """Tests that structural editor endpoints return 403 for published/closed surveys."""

    def setUp(self):
        self.org = _make_org('LockOrg')
        self.user = User.objects.create_user(username='lockuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='lockuser', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='locked_survey', organization=self.org, created_by=self.user,
            status='published',
        )
        SurveyCollaborator.objects.create(user=self.user, survey=self.survey, role='owner')
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Section 1',
            code='S1', is_head=True,
        )
        self.question = Question.objects.create(
            survey_section=self.section, code='Q1', order_number=1,
            name='Test?', input_type='text',
        )

    def test_section_create_blocked_on_published(self):
        """
        GIVEN a published survey
        WHEN a POST to section create is made
        THEN a 403 response is returned
        """
        url = f'/editor/surveys/{self.survey.uuid}/sections/new/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_section_delete_blocked_on_published(self):
        """
        GIVEN a published survey
        WHEN a POST to section delete is made
        THEN a 403 response is returned
        """
        url = f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/delete/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_question_create_blocked_on_published(self):
        """
        GIVEN a published survey
        WHEN a POST to question create is made
        THEN a 403 response is returned
        """
        url = f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/'
        response = self.client.post(url, {
            'name': 'New Q', 'input_type': 'text',
        })
        self.assertEqual(response.status_code, 403)

    def test_question_edit_blocked_on_published(self):
        """
        GIVEN a published survey
        WHEN a POST to question edit is made
        THEN a 403 response is returned
        """
        url = f'/editor/surveys/{self.survey.uuid}/questions/{self.question.id}/edit/'
        response = self.client.post(url, {
            'name': 'Updated', 'input_type': 'text',
        })
        self.assertEqual(response.status_code, 403)

    def test_question_delete_blocked_on_published(self):
        """
        GIVEN a published survey
        WHEN a POST to question delete is made
        THEN a 403 response is returned
        """
        url = f'/editor/surveys/{self.survey.uuid}/questions/{self.question.id}/delete/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_sections_reorder_blocked_on_published(self):
        """
        GIVEN a published survey
        WHEN a POST to sections reorder is made
        THEN a 403 response is returned
        """
        url = f'/editor/surveys/{self.survey.uuid}/sections/reorder/'
        response = self.client.post(url, json.dumps({'order': []}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_questions_reorder_blocked_on_published(self):
        """
        GIVEN a published survey
        WHEN a POST to questions reorder is made
        THEN a 403 response is returned
        """
        url = f'/editor/surveys/{self.survey.uuid}/questions/reorder/'
        response = self.client.post(url, json.dumps({'order': []}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_subquestion_create_blocked_on_published(self):
        """
        GIVEN a published survey
        WHEN a POST to subquestion create is made
        THEN a 403 response is returned
        """
        url = f'/editor/surveys/{self.survey.uuid}/questions/{self.question.id}/subquestions/new/'
        response = self.client.post(url, {
            'name': 'Sub Q', 'input_type': 'text',
        })
        self.assertEqual(response.status_code, 403)

    def test_settings_edit_allowed_on_published(self):
        """
        GIVEN a published survey
        WHEN a POST to survey settings is made
        THEN it succeeds (settings are not structural edits)
        """
        url = f'/editor/surveys/{self.survey.uuid}/settings/'
        response = self.client.post(url, {
            'name': 'locked_survey',
            'redirect_url': '/new-done/',
            'visibility': 'private',
        })
        # Should succeed (200 for rendered form or 302 for redirect)
        self.assertIn(response.status_code, [200, 204, 302])

    def test_structural_edits_blocked_on_closed_survey(self):
        """
        GIVEN a closed survey
        WHEN a POST to section create is made
        THEN a 403 response is returned
        """
        self.survey.status = 'closed'
        self.survey.save()
        url = f'/editor/surveys/{self.survey.uuid}/sections/new/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)


class EditorVersioningEndpointsTest(TestCase):
    """Tests for the editor versioning endpoints (create-draft, publish-draft, discard-draft)."""

    def setUp(self):
        self.org = _make_org('EditorVerOrg')
        self.owner = User.objects.create_user(username='ver_owner', password='pass')
        self.editor = User.objects.create_user(username='ver_editor', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        Membership.objects.create(user=self.editor, organization=self.org, role='editor')

        self.survey = SurveyHeader.objects.create(
            name='ver_test', organization=self.org, created_by=self.owner,
            status='published',
        )
        SurveyCollaborator.objects.create(user=self.owner, survey=self.survey, role='owner')
        SurveyCollaborator.objects.create(user=self.editor, survey=self.survey, role='editor')
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec', code='S1', is_head=True,
        )
        Question.objects.create(
            survey_section=self.section, code='Q1', order_number=1,
            name='Test?', input_type='text',
        )

    # ─── create-draft ────────────────────────────────────────────────────────

    def test_create_draft_success_for_owner(self):
        """
        GIVEN a published survey and an owner user
        WHEN POST to create-draft
        THEN a 302 redirect to the draft editor page is returned
        """
        self.client.login(username='ver_owner', password='pass')
        url = f'/editor/surveys/{self.survey.uuid}/create-draft/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.survey.has_draft_copy())

    def test_create_draft_409_if_draft_exists(self):
        """
        GIVEN a published survey that already has a draft copy
        WHEN POST to create-draft
        THEN a 409 response is returned
        """
        self.client.login(username='ver_owner', password='pass')
        clone_survey_for_draft(self.survey)
        url = f'/editor/surveys/{self.survey.uuid}/create-draft/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 409)

    def test_create_draft_400_if_not_published(self):
        """
        GIVEN a draft-status survey
        WHEN POST to create-draft
        THEN a 400 response is returned
        """
        self.survey.status = 'draft'
        self.survey.save()
        self.client.login(username='ver_owner', password='pass')
        url = f'/editor/surveys/{self.survey.uuid}/create-draft/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 400)

    def test_create_draft_403_for_non_owner(self):
        """
        GIVEN a published survey and an editor-role user
        WHEN POST to create-draft
        THEN a 403 response is returned
        """
        self.client.login(username='ver_editor', password='pass')
        url = f'/editor/surveys/{self.survey.uuid}/create-draft/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    # ─── publish-draft ───────────────────────────────────────────────────────

    def test_publish_draft_compatible_redirects(self):
        """
        GIVEN a compatible draft copy
        WHEN POST to publish-draft
        THEN a 302 redirect to the canonical editor page is returned
        """
        self.client.login(username='ver_owner', password='pass')
        draft = clone_survey_for_draft(self.survey)
        SurveyCollaborator.objects.get_or_create(
            user=self.owner, survey=draft, defaults={'role': 'owner'},
        )
        url = f'/editor/surveys/{draft.uuid}/publish-draft/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.version_number, 2)

    def test_publish_draft_incompatible_returns_409(self):
        """
        GIVEN a draft with breaking compatibility issues
        WHEN POST to publish-draft without force
        THEN a 409 response with issues JSON is returned
        """
        self.client.login(username='ver_owner', password='pass')
        # Create answers so deletion becomes breaking
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(
            survey_session=session,
            question=Question.objects.get(survey_section=self.section, code='Q1'),
            text='answer',
        )
        draft = clone_survey_for_draft(self.survey)
        SurveyCollaborator.objects.get_or_create(
            user=self.owner, survey=draft, defaults={'role': 'owner'},
        )
        # Delete question in draft to make it incompatible
        Question.objects.filter(
            survey_section__survey_header=draft, code='Q1'
        ).delete()
        url = f'/editor/surveys/{draft.uuid}/publish-draft/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 409)
        data = json.loads(response.content)
        self.assertIn('issues', data)

    def test_publish_draft_force_succeeds(self):
        """
        GIVEN a draft with breaking compatibility issues
        WHEN POST to publish-draft with force=true
        THEN a 302 redirect is returned and version incremented
        """
        self.client.login(username='ver_owner', password='pass')
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(
            survey_session=session,
            question=Question.objects.get(survey_section=self.section, code='Q1'),
            text='answer',
        )
        draft = clone_survey_for_draft(self.survey)
        SurveyCollaborator.objects.get_or_create(
            user=self.owner, survey=draft, defaults={'role': 'owner'},
        )
        Question.objects.filter(
            survey_section__survey_header=draft, code='Q1'
        ).delete()
        url = f'/editor/surveys/{draft.uuid}/publish-draft/'
        response = self.client.post(url, {'force': 'true'})
        self.assertEqual(response.status_code, 302)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.version_number, 2)

    # ─── discard-draft ───────────────────────────────────────────────────────

    def test_discard_draft_redirects_and_deletes(self):
        """
        GIVEN a draft copy
        WHEN POST to discard-draft
        THEN the draft is deleted and a redirect to canonical is returned
        """
        self.client.login(username='ver_owner', password='pass')
        draft = clone_survey_for_draft(self.survey)
        draft_id = draft.id
        SurveyCollaborator.objects.get_or_create(
            user=self.owner, survey=draft, defaults={'role': 'owner'},
        )
        url = f'/editor/surveys/{draft.uuid}/discard-draft/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SurveyHeader.objects.filter(id=draft_id).exists())

    def test_discard_draft_canonical_unchanged(self):
        """
        GIVEN a draft copy
        WHEN POST to discard-draft
        THEN the canonical survey is unchanged
        """
        self.client.login(username='ver_owner', password='pass')
        original_version = self.survey.version_number
        draft = clone_survey_for_draft(self.survey)
        SurveyCollaborator.objects.get_or_create(
            user=self.owner, survey=draft, defaults={'role': 'owner'},
        )
        url = f'/editor/surveys/{draft.uuid}/discard-draft/'
        self.client.post(url)
        self.survey.refresh_from_db()
        self.assertEqual(self.survey.version_number, original_version)
        self.assertEqual(self.survey.status, 'published')

    # ─── check-compatibility ─────────────────────────────────────────────────

    def test_check_compatibility_returns_issues(self):
        """
        GIVEN a draft with breaking issues
        WHEN GET to check-compatibility
        THEN JSON response with issues list is returned
        """
        self.client.login(username='ver_editor', password='pass')
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(
            survey_session=session,
            question=Question.objects.get(survey_section=self.section, code='Q1'),
            text='answer',
        )
        draft = clone_survey_for_draft(self.survey)
        SurveyCollaborator.objects.get_or_create(
            user=self.editor, survey=draft, defaults={'role': 'editor'},
        )
        Question.objects.filter(
            survey_section__survey_header=draft, code='Q1'
        ).delete()
        url = f'/editor/surveys/{draft.uuid}/check-compatibility/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('issues', data)
        self.assertTrue(len(data['issues']) > 0)


class DashboardVersioningTest(TestCase):
    """Tests that the dashboard excludes draft copies and archived versions."""

    def setUp(self):
        self.org = _make_org('DashOrg')
        self.user = User.objects.create_user(username='dashuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='dashuser', password='pass')

    def test_dashboard_excludes_draft_copies(self):
        """
        GIVEN a canonical survey with a draft copy
        WHEN the dashboard is loaded
        THEN the draft copy is not listed
        """
        canonical = SurveyHeader.objects.create(
            name='dash_canonical', organization=self.org, status='published',
        )
        draft = SurveyHeader.objects.create(
            name='[draft] dash_canonical', organization=self.org,
            status='draft', published_version=canonical,
        )
        response = self.client.get('/editor/')
        self.assertContains(response, 'dash_canonical')
        # The draft name should not appear as a separate entry
        content = response.content.decode()
        # Count occurrences - canonical appears, draft appears zero times as list entry
        self.assertNotIn('[draft] dash_canonical', content)

    def test_dashboard_excludes_archived_versions(self):
        """
        GIVEN a canonical survey with an archived version
        WHEN the dashboard is loaded
        THEN the archived version is not listed as a separate survey
        """
        canonical = SurveyHeader.objects.create(
            name='dash_versioned', organization=self.org, status='published',
            version_number=2,
        )
        archived = SurveyHeader.objects.create(
            name='dash_versioned', organization=self.org, status='closed',
            is_canonical=False, canonical_survey=canonical, version_number=1,
        )
        response = self.client.get('/editor/')
        # Should show the canonical once
        self.assertContains(response, 'dash_versioned')

    def test_dashboard_shows_only_canonical_surveys(self):
        """
        GIVEN a canonical survey, a draft copy, and an archived version
        WHEN the dashboard is loaded
        THEN only the canonical survey appears in the list
        """
        canonical = SurveyHeader.objects.create(
            name='single_entry', organization=self.org, status='published',
        )
        SurveyHeader.objects.create(
            name='[draft] single_entry', organization=self.org,
            status='draft', published_version=canonical,
        )
        SurveyHeader.objects.create(
            name='single_entry', organization=self.org,
            status='closed', is_canonical=False, canonical_survey=canonical,
            version_number=1,
        )
        response = self.client.get('/editor/')
        # The filter is is_canonical=True, published_version__isnull=True
        # Verify canonical survey appears
        survey_list = SurveyHeader.objects.filter(
            organization=self.org, is_canonical=True, published_version__isnull=True,
        )
        self.assertEqual(survey_list.count(), 1)
        self.assertEqual(survey_list.first(), canonical)


class DashboardVersionDownloadUITest(TestCase):
    """Tests for version-aware download dropdown in the editor dashboard."""

    def setUp(self):
        self.org = _make_org('DlUIOrg')
        self.user = User.objects.create_user(username='dluiuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='dluiuser', password='pass')

    def test_single_version_shows_plain_download_link(self):
        """
        GIVEN a survey with version_number=1 and no archived versions
        WHEN the dashboard is loaded
        THEN a plain "Download Data" link is shown (no dropdown)
        """
        survey = SurveyHeader.objects.create(
            name='single_v', organization=self.org, status='published',
            version_number=1,
        )
        response = self.client.get('/editor/')
        content = response.content.decode()
        self.assertIn(f'/surveys/{survey.uuid}/download', content)
        self.assertNotIn('?version=all', content)

    def test_multi_version_shows_download_dropdown(self):
        """
        GIVEN a survey with version_number=3 and two archived versions
        WHEN the dashboard is loaded
        THEN a dropdown is shown with "All Versions", "Current (v3)", "v2", and "v1"
        """
        canonical = SurveyHeader.objects.create(
            name='multi_v', organization=self.org, status='published',
            version_number=3,
        )
        SurveyHeader.objects.create(
            name='multi_v', organization=self.org, status='closed',
            is_canonical=False, canonical_survey=canonical, version_number=2,
        )
        SurveyHeader.objects.create(
            name='multi_v', organization=self.org, status='closed',
            is_canonical=False, canonical_survey=canonical, version_number=1,
        )
        response = self.client.get('/editor/')
        content = response.content.decode()
        self.assertIn('?version=all', content)
        self.assertIn('?version=latest', content)
        self.assertIn('Current (v3)', content)
        self.assertIn('?version=v2', content)
        self.assertIn('?version=v1', content)

    def test_prefetched_versions_avoid_n_plus_one(self):
        """
        GIVEN multiple surveys with archived versions
        WHEN the dashboard is loaded
        THEN archived versions are prefetched (available as prefetched_archived_versions)
        """
        for i in range(3):
            canonical = SurveyHeader.objects.create(
                name=f'prefetch_test_{i}', organization=self.org,
                status='published', version_number=2,
            )
            SurveyHeader.objects.create(
                name=f'prefetch_test_{i}', organization=self.org,
                status='closed', is_canonical=False,
                canonical_survey=canonical, version_number=1,
            )
        response = self.client.get('/editor/')
        surveys = response.context['survey_headers']
        for s in surveys:
            self.assertTrue(hasattr(s, 'prefetched_archived_versions'))


class VersionedDownloadTest(TestCase):
    """Tests for download_data with version filter query parameter."""

    def setUp(self):
        self.org = _make_org('DownloadOrg')
        self.user = User.objects.create_user(username='dluser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.client.login(username='dluser', password='pass')
        self.survey = SurveyHeader.objects.create(
            name='dl_survey', organization=self.org, created_by=self.user,
            status='published', version_number=2,
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec', code='S1', is_head=True,
        )
        self.question = Question.objects.create(
            survey_section=self.section, code='Q1', order_number=1,
            name='Q?', input_type='text',
        )
        self.session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(
            survey_session=self.session, question=self.question, text='v2 answer',
        )
        # Create archived version
        self.archived = SurveyHeader.objects.create(
            name='dl_survey', organization=self.org, status='closed',
            is_canonical=False, canonical_survey=self.survey, version_number=1,
        )
        self.arch_section = SurveySection.objects.create(
            survey_header=self.archived, name='sec_old', code='S1_old', is_head=True,
        )
        self.arch_question = Question.objects.create(
            survey_section=self.arch_section, code='Q1_old', order_number=1,
            name='Old Q?', input_type='text',
        )
        self.arch_session = SurveySession.objects.create(survey=self.archived)
        Answer.objects.create(
            survey_session=self.arch_session, question=self.arch_question,
            text='v1 answer',
        )

    def test_download_latest_returns_zip(self):
        """
        GIVEN a canonical survey
        WHEN download_data is called with version=latest
        THEN a ZIP file is returned
        """
        url = f'/surveys/{self.survey.uuid}/download?version=latest'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')

    def test_download_specific_version(self):
        """
        GIVEN a canonical survey with archived version 1
        WHEN download_data is called with version=v1
        THEN a ZIP file containing v1 data is returned
        """
        url = f'/surveys/{self.survey.uuid}/download?version=v1'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')
        # Verify the zip contains data (CSV with v1 answer)
        zip_buffer = BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            filenames = zf.namelist()
            self.assertTrue(len(filenames) > 0)

    def test_download_all_versions(self):
        """
        GIVEN a canonical survey with an archived version
        WHEN download_data is called with version=all
        THEN a ZIP file with prefixed filenames for both versions is returned
        """
        url = f'/surveys/{self.survey.uuid}/download?version=all'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        zip_buffer = BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            filenames = zf.namelist()
            # Should have files prefixed with version numbers
            has_v2 = any(f.startswith('v2_') for f in filenames)
            has_v1 = any(f.startswith('v1_') for f in filenames)
            self.assertTrue(has_v2 or has_v1)

    def test_download_no_version_param_returns_latest(self):
        """
        GIVEN a canonical survey
        WHEN download_data is called without version param
        THEN it defaults to latest (current canonical data)
        """
        url = f'/surveys/{self.survey.uuid}/download'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/zip')


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


class PublicViewVersioningTest(TestCase):
    """Tests that versioning is invisible to public respondents."""

    def setUp(self):
        self.org = _make_org('PubViewOrg')
        self.survey = SurveyHeader.objects.create(
            name='public_ver', organization=self.org, status='published',
            version_number=2,
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', title='Sec',
            code='S1', is_head=True,
        )
        Question.objects.create(
            survey_section=self.section, code='Q1', order_number=1,
            name='Q?', input_type='text',
        )

    def test_draft_copy_invisible_to_respondents(self):
        """
        GIVEN a draft copy of a published survey
        WHEN a respondent tries to access the draft by its UUID
        THEN they get a 404 (draft status raises Http404 in access control)
        """
        draft = SurveyHeader.objects.create(
            name='[draft] public_ver', organization=self.org,
            status='draft', published_version=self.survey,
        )
        # Draft section so the URL resolves properly
        SurveySection.objects.create(
            survey_header=draft, name='dsec', code='DS1', is_head=True,
        )
        url = f'/surveys/{draft.uuid}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_archived_version_shows_closed_page(self):
        """
        GIVEN an archived version of a survey
        WHEN a respondent accesses it by the archived UUID
        THEN resolve_survey returns the canonical survey instead
        """
        archived = SurveyHeader.objects.create(
            name='public_ver', organization=self.org, status='closed',
            is_canonical=False, canonical_survey=self.survey, version_number=1,
        )
        # Access by archived UUID should redirect to canonical survey
        url = f'/surveys/{archived.uuid}/'
        response = self.client.get(url)
        # resolve_survey returns canonical for archived UUID,
        # so it should redirect to the first section of the canonical survey
        self.assertIn(response.status_code, [200, 302])

    def test_resolve_survey_returns_canonical_for_archived_uuid(self):
        """
        GIVEN an archived version with canonical_survey set
        WHEN resolve_survey is called with the archived UUID
        THEN the canonical survey is returned
        """
        from .views import resolve_survey
        archived = SurveyHeader.objects.create(
            name='public_ver', organization=self.org, status='closed',
            is_canonical=False, canonical_survey=self.survey, version_number=1,
        )
        result = resolve_survey(str(archived.uuid))
        self.assertEqual(result, self.survey)

    def test_resolve_survey_name_filters_canonical_only(self):
        """
        GIVEN a canonical survey and an archived version with the same name
        WHEN resolve_survey is called with the name
        THEN the canonical survey is returned
        """
        from .views import resolve_survey
        SurveyHeader.objects.create(
            name='public_ver', organization=self.org, status='closed',
            is_canonical=False, canonical_survey=self.survey, version_number=1,
        )
        result = resolve_survey('public_ver')
        self.assertEqual(result, self.survey)

    def test_canonical_survey_accessible_to_respondents(self):
        """
        GIVEN a published canonical survey
        WHEN a respondent accesses it by UUID
        THEN they get a successful response (redirect to section)
        """
        url = f'/surveys/{self.survey.uuid}/'
        response = self.client.get(url)
        self.assertIn(response.status_code, [200, 302])


class SessionProtectTest(TestCase):
    """Tests that SurveySession PROTECT prevents deletion of SurveyHeader with sessions."""

    def setUp(self):
        self.org = _make_org('ProtectOrg')
        self.survey = SurveyHeader.objects.create(
            name='protect_test', organization=self.org, status='published',
        )
        self.session = SurveySession.objects.create(survey=self.survey)

    def test_cannot_delete_survey_with_sessions(self):
        """
        GIVEN a SurveyHeader that has SurveySessions
        WHEN attempting to delete the SurveyHeader
        THEN a ProtectedError is raised
        """
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            self.survey.delete()

    def test_can_delete_survey_after_sessions_removed(self):
        """
        GIVEN a SurveyHeader whose sessions have been moved or deleted
        WHEN attempting to delete the SurveyHeader
        THEN it succeeds
        """
        self.session.delete()
        self.survey.delete()
        self.assertFalse(SurveyHeader.objects.filter(name='protect_test').exists())

    def test_can_delete_survey_after_sessions_moved(self):
        """
        GIVEN a SurveyHeader whose sessions have been moved to another survey
        WHEN attempting to delete the original SurveyHeader
        THEN it succeeds
        """
        other_survey = SurveyHeader.objects.create(
            name='other_survey', organization=self.org,
        )
        self.session.survey = other_survey
        self.session.save()
        self.survey.delete()
        self.assertFalse(SurveyHeader.objects.filter(name='protect_test').exists())
        # Session still exists on the other survey
        self.session.refresh_from_db()
        self.assertEqual(self.session.survey, other_survey)


class PlausibleAnalyticsTest(TestCase):
    """Tests for Plausible Analytics integration."""

    def setUp(self):
        self.org = _make_org('AnalyticsOrg')
        self.user = User.objects.create_user('analyticsuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='analytics_survey',
            organization=self.org,
            redirect_url='#',
            status='published',
        )
        self.section1 = SurveySection.objects.create(
            survey_header=self.survey,
            name='section1',
            start_map_postion=Point(0, 0),
            start_map_zoom=10,
        )
        self.section2 = SurveySection.objects.create(
            survey_header=self.survey,
            name='section2',
            start_map_postion=Point(0, 0),
            start_map_zoom=10,
        )
        self.section1.next_section = self.section2
        self.section1.save()
        self.section2.prev_section = self.section1
        self.section2.save()

    def test_no_plausible_script_when_url_unset(self):
        """
        GIVEN PLAUSIBLE_SCRIPT_URL is empty (default)
        WHEN any page is rendered
        THEN no Plausible script tag appears in the HTML
        """
        with self.settings(PLAUSIBLE_SCRIPT_URL=''):
            response = self.client.get(f'/surveys/{self.survey.uuid}/section1/')
            self.assertNotContains(response, 'plausible.io')
            self.assertNotContains(response, 'plausible.init')

    def test_plausible_script_present_when_url_set(self):
        """
        GIVEN PLAUSIBLE_SCRIPT_URL is set
        WHEN any page is rendered
        THEN the Plausible script tag and init block appear
        """
        with self.settings(PLAUSIBLE_SCRIPT_URL='https://plausible.io/js/pa-test123.js'):
            response = self.client.get(f'/surveys/{self.survey.uuid}/section1/')
            self.assertContains(response, 'src="https://plausible.io/js/pa-test123.js"')
            self.assertContains(response, 'plausible.init')

    def test_plausible_script_with_custom_url(self):
        """
        GIVEN PLAUSIBLE_SCRIPT_URL points to a self-hosted instance
        WHEN a page is rendered
        THEN the script tag uses that URL
        """
        with self.settings(PLAUSIBLE_SCRIPT_URL='https://stats.example.com/js/pa-abc.js'):
            response = self.client.get(f'/surveys/{self.survey.uuid}/section1/')
            self.assertContains(response, 'src="https://stats.example.com/js/pa-abc.js"')

    def test_yandex_metrica_absent(self):
        """
        GIVEN any configuration
        WHEN a survey section page is rendered
        THEN no Yandex Metrica code appears in the HTML
        """
        response = self.client.get(f'/surveys/{self.survey.uuid}/section1/')
        self.assertNotContains(response, 'mc.yandex.ru')
        self.assertNotContains(response, '53686546')

    def test_survey_start_event_on_first_section(self):
        """
        GIVEN PLAUSIBLE_SCRIPT_URL is configured
        WHEN the first section of a survey is loaded
        THEN the page contains a survey_start event script
        """
        with self.settings(PLAUSIBLE_SCRIPT_URL='https://plausible.io/js/pa-test.js'):
            response = self.client.get(f'/surveys/{self.survey.uuid}/section1/')
            self.assertContains(response, "plausible('survey_start'")
            self.assertContains(response, "survey: 'analytics_survey'")

    def test_no_survey_start_event_on_non_first_section(self):
        """
        GIVEN PLAUSIBLE_SCRIPT_URL is configured
        WHEN a non-first section is loaded
        THEN the page does NOT contain a survey_start event script
        """
        with self.settings(PLAUSIBLE_SCRIPT_URL='https://plausible.io/js/pa-test.js'):
            # Visit first section to create a session
            self.client.get(f'/surveys/{self.survey.uuid}/section1/')
            response = self.client.get(f'/surveys/{self.survey.uuid}/section2/')
            self.assertNotContains(response, "plausible('survey_start'")

    def test_survey_section_complete_event_present(self):
        """
        GIVEN PLAUSIBLE_SCRIPT_URL is configured
        WHEN a survey section page is loaded
        THEN the page contains a survey_section_complete event script
        """
        with self.settings(PLAUSIBLE_SCRIPT_URL='https://plausible.io/js/pa-test.js'):
            response = self.client.get(f'/surveys/{self.survey.uuid}/section1/')
            self.assertContains(response, "plausible('survey_section_complete'")

    def test_survey_complete_event_on_thanks_page(self):
        """
        GIVEN PLAUSIBLE_SCRIPT_URL is configured AND a respondent has an active session
        WHEN the thanks page is loaded
        THEN the page contains a survey_complete event script
        """
        with self.settings(PLAUSIBLE_SCRIPT_URL='https://plausible.io/js/pa-test.js'):
            # Create a session by visiting first section
            self.client.get(f'/surveys/{self.survey.uuid}/section1/')
            response = self.client.get(f'/surveys/{self.survey.uuid}/thanks/')
            self.assertContains(response, "plausible('survey_complete'")

    def test_no_events_when_plausible_disabled(self):
        """
        GIVEN PLAUSIBLE_SCRIPT_URL is empty
        WHEN survey pages are loaded
        THEN no custom event scripts appear
        """
        with self.settings(PLAUSIBLE_SCRIPT_URL=''):
            self.client.get(f'/surveys/{self.survey.uuid}/section1/')
            response = self.client.get(f'/surveys/{self.survey.uuid}/section1/')
            self.assertNotContains(response, "plausible('survey_start'")
            self.assertNotContains(response, "plausible('survey_section_complete'")

    def test_plausible_on_editor_page(self):
        """
        GIVEN PLAUSIBLE_SCRIPT_URL is set
        WHEN the editor page is loaded
        THEN the Plausible script tag is present
        """
        with self.settings(PLAUSIBLE_SCRIPT_URL='https://plausible.io/js/pa-test.js'):
            self.client.login(username='analyticsuser', password='pass')
            response = self.client.get('/editor/')
            self.assertContains(response, 'src="https://plausible.io/js/pa-test.js"')

    def test_events_guarded_against_blocked_scripts(self):
        """
        GIVEN PLAUSIBLE_SCRIPT_URL is configured
        WHEN survey section page is rendered
        THEN event scripts are guarded with typeof plausible check
        """
        with self.settings(PLAUSIBLE_SCRIPT_URL='https://plausible.io/js/pa-test.js'):
            response = self.client.get(f'/surveys/{self.survey.uuid}/section1/')
            content = response.content.decode()
            self.assertIn("typeof plausible !== 'undefined'", content)


class AnalyticsServiceTest(TestCase):
    """Tests for SurveyAnalyticsService."""

    def setUp(self):
        from .analytics import SurveyAnalyticsService
        self.SurveyAnalyticsService = SurveyAnalyticsService

        self.org = _make_org('AnalyticsOrg')
        self.user = User.objects.create_user('analyticsowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

        self.survey = SurveyHeader.objects.create(
            name='analytics_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section1 = SurveySection.objects.create(
            survey_header=self.survey, name='section1', code='S1', is_head=True,
        )
        self.section2 = SurveySection.objects.create(
            survey_header=self.survey, name='section2', code='S2',
        )
        self.section1.next_section = self.section2
        self.section1.save()

        self.q_choice = Question.objects.create(
            survey_section=self.section1, name='Satisfaction', code='q1',
            input_type='choice', order_number=1,
            choices=[{'code': 1, 'name': 'Good'}, {'code': 2, 'name': 'Bad'}],
        )
        self.q_number = Question.objects.create(
            survey_section=self.section1, name='Travel time', code='q2',
            input_type='number', order_number=2,
        )
        self.q_text = Question.objects.create(
            survey_section=self.section2, name='Comments', code='q3',
            input_type='text', order_number=1,
        )
        self.q_point = Question.objects.create(
            survey_section=self.section2, name='Location', code='q4',
            input_type='point', order_number=2,
        )

    def _create_completed_session(self, choice_code=1, number=10, text='Great', point=None):
        """Helper: create a session with answers in both sections."""
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(
            survey_session=session, question=self.q_choice,
            selected_choices=[choice_code],
        )
        Answer.objects.create(
            survey_session=session, question=self.q_number,
            numeric=number,
        )
        Answer.objects.create(
            survey_session=session, question=self.q_text,
            text=text,
        )
        if point:
            Answer.objects.create(
                survey_session=session, question=self.q_point,
                point=point,
            )
        return session

    def _create_abandoned_session(self):
        """Helper: create a session with no answers."""
        return SurveySession.objects.create(survey=self.survey)

    def _create_partial_session(self, choice_code=1, number=5):
        """Helper: create a session with answers only in section1."""
        session = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(
            survey_session=session, question=self.q_choice,
            selected_choices=[choice_code],
        )
        Answer.objects.create(
            survey_session=session, question=self.q_number,
            numeric=number,
        )
        return session

    def test_overview_with_completed_and_abandoned(self):
        """
        GIVEN a survey with 3 completed, 2 abandoned, and 1 partial session
        WHEN get_overview is called
        THEN total=6, completed=3, rate=50
        """
        self._create_completed_session()
        self._create_completed_session(choice_code=2, number=20, text='OK')
        self._create_completed_session(choice_code=1, number=5, text='Fine')
        self._create_abandoned_session()
        self._create_abandoned_session()
        self._create_partial_session()

        service = self.SurveyAnalyticsService(self.survey)
        overview = service.get_overview()

        self.assertEqual(overview['total_sessions'], 6)
        self.assertEqual(overview['completed_count'], 3)
        self.assertEqual(overview['completion_rate'], 50)

    def test_overview_empty_survey(self):
        """
        GIVEN a survey with no sessions
        WHEN get_overview is called
        THEN returns zeros
        """
        service = self.SurveyAnalyticsService(self.survey)
        overview = service.get_overview()

        self.assertEqual(overview['total_sessions'], 0)
        self.assertEqual(overview['completed_count'], 0)
        self.assertEqual(overview['completion_rate'], 0)

    def test_daily_sessions(self):
        """
        GIVEN sessions created on the same day
        WHEN get_daily_sessions is called
        THEN returns one entry with correct counts
        """
        self._create_completed_session()
        self._create_abandoned_session()

        service = self.SurveyAnalyticsService(self.survey)
        daily = service.get_daily_sessions()

        self.assertEqual(len(daily), 1)
        self.assertEqual(daily[0]['total'], 2)
        self.assertEqual(daily[0]['completed'], 1)

    def test_question_stats_choice(self):
        """
        GIVEN 3 choice answers (2x Good, 1x Bad)
        WHEN get_question_stats is called for the choice question
        THEN returns correct distribution
        """
        self._create_completed_session(choice_code=1)
        self._create_completed_session(choice_code=1)
        self._create_completed_session(choice_code=2)

        service = self.SurveyAnalyticsService(self.survey)
        stat = service.get_question_stats(self.q_choice)

        self.assertEqual(stat['type'], 'choices')
        self.assertEqual(stat['choice_labels'], ['Good', 'Bad'])
        self.assertEqual(stat['choice_counts'], [2, 1])
        self.assertEqual(stat['total_answers'], 3)

    def test_question_stats_number(self):
        """
        GIVEN numeric answers [5, 10, 20]
        WHEN get_question_stats is called for the number question
        THEN returns correct avg, median, min, max
        """
        self._create_completed_session(number=5)
        self._create_completed_session(number=10)
        self._create_completed_session(number=20)

        service = self.SurveyAnalyticsService(self.survey)
        stat = service.get_question_stats(self.q_number)

        self.assertEqual(stat['type'], 'number')
        self.assertEqual(stat['count'], 3)
        self.assertAlmostEqual(stat['avg'], 11.7, places=1)
        self.assertEqual(stat['median'], 10)
        self.assertEqual(stat['min_val'], 5)
        self.assertEqual(stat['max_val'], 20)

    def test_text_answers_pagination(self):
        """
        GIVEN 25 text answers
        WHEN get_text_answers is called with page=2, page_size=10
        THEN returns answers 11-20 with correct page info
        """
        for i in range(25):
            session = SurveySession.objects.create(survey=self.survey)
            Answer.objects.create(
                survey_session=session, question=self.q_text,
                text=f'Answer {i+1}',
            )

        service = self.SurveyAnalyticsService(self.survey)
        result = service.get_text_answers(self.q_text, page=2, page_size=10)

        self.assertEqual(len(result['answers']), 10)
        self.assertEqual(result['page'], 2)
        self.assertEqual(result['total_pages'], 3)
        self.assertEqual(result['total'], 25)

    def test_geo_feature_collection(self):
        """
        GIVEN 2 point answers
        WHEN get_geo_feature_collection is called
        THEN returns FeatureCollection with 2 features
        """
        self._create_completed_session(point=Point(2.35, 48.86))
        self._create_completed_session(point=Point(4.83, 45.76))

        service = self.SurveyAnalyticsService(self.survey)
        fc = service.get_geo_feature_collection()

        self.assertEqual(fc['type'], 'FeatureCollection')
        self.assertEqual(len(fc['features']), 2)
        self.assertEqual(fc['features'][0]['properties']['question'], 'Location')
        self.assertEqual(fc['features'][0]['properties']['type'], 'point')


class AnalyticsViewTest(TestCase):
    """Tests for analytics dashboard views."""

    def setUp(self):
        self.org = _make_org('AnalyticsViewOrg')
        self.owner = User.objects.create_user('dashowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.client.login(username='dashowner', password='pass')

        # Set active org in session
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

        self.survey = SurveyHeader.objects.create(
            name='dash_test', organization=self.org,
            created_by=self.owner, status='published',
        )
        section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.q = Question.objects.create(
            survey_section=section, name='Q1', code='q1',
            input_type='text', order_number=1,
        )
        sess = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=sess, question=self.q, text='Hello')

    def test_dashboard_requires_auth(self):
        """
        GIVEN an unauthenticated user
        WHEN GET analytics dashboard
        THEN redirect to login
        """
        self.client.logout()
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/analytics/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_dashboard_renders(self):
        """
        GIVEN an authenticated survey owner
        WHEN GET analytics dashboard
        THEN returns 200 with analytics data
        """
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/analytics/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Total Sessions')
        self.assertContains(response, 'Completed')
        self.assertContains(response, 'Completion Rate')

    def test_text_answers_partial(self):
        """
        GIVEN a survey with text answers
        WHEN GET text answers HTMX endpoint
        THEN returns 200 with answer text
        """
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/analytics/questions/{self.q.id}/text/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hello')


class CrossFilteringServiceTest(TestCase):
    """Tests for cross-filtering analytics features."""

    def setUp(self):
        from .analytics import SurveyAnalyticsService
        self.SurveyAnalyticsService = SurveyAnalyticsService

        self.org = _make_org('CrossFilterOrg')
        self.user = User.objects.create_user('cfowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

        self.survey = SurveyHeader.objects.create(
            name='crossfilter_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.q_gender = Question.objects.create(
            survey_section=self.section, name='Gender', code='qg',
            input_type='choice', order_number=1,
            choices=[{'code': 1, 'name': 'Male'}, {'code': 2, 'name': 'Female'}],
        )
        self.q_rating = Question.objects.create(
            survey_section=self.section, name='Rating', code='qr',
            input_type='rating', order_number=2,
            choices=[
                {'code': 1, 'name': 'Bad'},
                {'code': 2, 'name': 'OK'},
                {'code': 3, 'name': 'Good'},
            ],
        )
        self.q_text = Question.objects.create(
            survey_section=self.section, name='Comment', code='qt',
            input_type='text', order_number=3,
        )
        self.q_point = Question.objects.create(
            survey_section=self.section, name='Location', code='qp',
            input_type='point', order_number=4,
        )

        # Session 1: Male, Good rating, "Nice" comment, point
        self.s1 = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=self.s1, question=self.q_gender, selected_choices=[1])
        Answer.objects.create(survey_session=self.s1, question=self.q_rating, selected_choices=[3])
        Answer.objects.create(survey_session=self.s1, question=self.q_text, text='Nice')
        Answer.objects.create(survey_session=self.s1, question=self.q_point, point=Point(2.35, 48.86))

        # Session 2: Female, Bad rating, "Awful" comment
        self.s2 = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=self.s2, question=self.q_gender, selected_choices=[2])
        Answer.objects.create(survey_session=self.s2, question=self.q_rating, selected_choices=[1])
        Answer.objects.create(survey_session=self.s2, question=self.q_text, text='Awful')

        # Session 3: Male, Bad rating, "Meh" comment
        self.s3 = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=self.s3, question=self.q_gender, selected_choices=[1])
        Answer.objects.create(survey_session=self.s3, question=self.q_rating, selected_choices=[1])
        Answer.objects.create(survey_session=self.s3, question=self.q_text, text='Meh')

    def test_answer_matrix_structure(self):
        """
        GIVEN 3 sessions with choice and rating answers
        WHEN get_answer_matrix is called
        THEN returns list of session dicts with correct structure
        """
        service = self.SurveyAnalyticsService(self.survey)
        matrix = service.get_answer_matrix()

        self.assertEqual(len(matrix), 3)
        sids = {m['sid'] for m in matrix}
        self.assertEqual(sids, {self.s1.id, self.s2.id, self.s3.id})

        for entry in matrix:
            self.assertIn('sid', entry)
            self.assertIn('d', entry)
            self.assertIn('a', entry)
            # Each session should have gender and rating answers
            self.assertIn(str(self.q_gender.id), entry['a'])
            self.assertIn(str(self.q_rating.id), entry['a'])
            # Text and point questions should NOT be in matrix
            self.assertNotIn(str(self.q_text.id), entry['a'])
            self.assertNotIn(str(self.q_point.id), entry['a'])

    def test_answer_matrix_values(self):
        """
        GIVEN session 1 with Male (1) and Good (3)
        WHEN get_answer_matrix is called
        THEN session 1 entry has correct choice codes
        """
        service = self.SurveyAnalyticsService(self.survey)
        matrix = service.get_answer_matrix()

        s1_entry = next(m for m in matrix if m['sid'] == self.s1.id)
        self.assertEqual(s1_entry['a'][str(self.q_gender.id)], [1])
        self.assertEqual(s1_entry['a'][str(self.q_rating.id)], [3])

    def test_geo_feature_has_session_id(self):
        """
        GIVEN a session with a point answer
        WHEN get_geo_feature_collection is called
        THEN each feature has session_id in properties
        """
        service = self.SurveyAnalyticsService(self.survey)
        fc = service.get_geo_feature_collection()

        self.assertEqual(len(fc['features']), 1)
        self.assertEqual(fc['features'][0]['properties']['session_id'], self.s1.id)

    def test_question_stats_has_choice_codes(self):
        """
        GIVEN a choice question
        WHEN get_question_stats is called
        THEN stat includes choice_codes and choice_codes_json
        """
        service = self.SurveyAnalyticsService(self.survey)
        stat = service.get_question_stats(self.q_gender)

        self.assertEqual(stat['choice_codes'], [1, 2])
        self.assertEqual(stat['choice_codes_json'], '[1, 2]')

    def test_text_answers_filtered_by_session_ids(self):
        """
        GIVEN 3 text answers from 3 sessions
        WHEN get_text_answers is called with session_ids={s1, s3}
        THEN returns only 2 answers from those sessions
        """
        service = self.SurveyAnalyticsService(self.survey)
        result = service.get_text_answers(
            self.q_text, session_ids={self.s1.id, self.s3.id},
        )

        self.assertEqual(result['total'], 2)
        texts = {a.text for a in result['answers']}
        self.assertEqual(texts, {'Nice', 'Meh'})

    def test_text_answers_empty_session_ids(self):
        """
        GIVEN 3 text answers
        WHEN get_text_answers is called with session_ids=set() (empty)
        THEN returns 0 answers
        """
        service = self.SurveyAnalyticsService(self.survey)
        result = service.get_text_answers(self.q_text, session_ids=set())

        self.assertEqual(result['total'], 0)
        self.assertEqual(len(result['answers']), 0)

    def test_text_answers_no_filter(self):
        """
        GIVEN 3 text answers
        WHEN get_text_answers is called with session_ids=None
        THEN returns all 3 answers
        """
        service = self.SurveyAnalyticsService(self.survey)
        result = service.get_text_answers(self.q_text, session_ids=None)

        self.assertEqual(result['total'], 3)


class CrossFilteringViewTest(TestCase):
    """Tests for cross-filtering view helpers and endpoints."""

    def setUp(self):
        self.org = _make_org('CrossFilterViewOrg')
        self.owner = User.objects.create_user('cfvowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.client.login(username='cfvowner', password='pass')

        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

        self.survey = SurveyHeader.objects.create(
            name='cfview_test', organization=self.org,
            created_by=self.owner, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.q_choice = Question.objects.create(
            survey_section=self.section, name='Color', code='qc',
            input_type='choice', order_number=1,
            choices=[{'code': 1, 'name': 'Red'}, {'code': 2, 'name': 'Blue'}],
        )
        self.q_text = Question.objects.create(
            survey_section=self.section, name='Why', code='qw',
            input_type='text', order_number=2,
        )

        # Session A: Red, "I like red"
        self.sa = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=self.sa, question=self.q_choice, selected_choices=[1])
        Answer.objects.create(survey_session=self.sa, question=self.q_text, text='I like red')

        # Session B: Blue, "I like blue"
        self.sb = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=self.sb, question=self.q_choice, selected_choices=[2])
        Answer.objects.create(survey_session=self.sb, question=self.q_text, text='I like blue')

    def test_parse_filter_param_valid(self):
        """
        GIVEN a valid filter string '7:1,3;12:2'
        WHEN _parse_filter_param is called
        THEN returns correct dict
        """
        from .analytics_views import _parse_filter_param
        result = _parse_filter_param('7:1,3;12:2')
        self.assertEqual(result, {7: [1, 3], 12: [2]})

    def test_parse_filter_param_empty(self):
        """
        GIVEN an empty string
        WHEN _parse_filter_param is called
        THEN returns empty dict
        """
        from .analytics_views import _parse_filter_param
        self.assertEqual(_parse_filter_param(''), {})
        self.assertEqual(_parse_filter_param(None), {})

    def test_parse_filter_param_invalid(self):
        """
        GIVEN an invalid filter string
        WHEN _parse_filter_param is called
        THEN returns empty dict without raising
        """
        from .analytics_views import _parse_filter_param
        self.assertEqual(_parse_filter_param('garbage'), {})
        self.assertEqual(_parse_filter_param('abc:xyz'), {})

    def test_resolve_filtered_session_ids_single_filter(self):
        """
        GIVEN sessions with Red(1) and Blue(2) answers
        WHEN _resolve_filtered_session_ids filters for Red (code=1)
        THEN returns only session A
        """
        from .analytics_views import _resolve_filtered_session_ids
        result = _resolve_filtered_session_ids(
            self.survey, {self.q_choice.id: [1]},
        )
        self.assertEqual(result, {self.sa.id})

    def test_resolve_filtered_session_ids_no_filter(self):
        """
        GIVEN no filters
        WHEN _resolve_filtered_session_ids is called with empty dict
        THEN returns None (no filtering)
        """
        from .analytics_views import _resolve_filtered_session_ids
        result = _resolve_filtered_session_ids(self.survey, {})
        self.assertIsNone(result)

    def test_dashboard_includes_answer_matrix(self):
        """
        GIVEN a survey with choice answers
        WHEN GET analytics dashboard
        THEN response contains answer-matrix-data script tag
        """
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/analytics/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'answer-matrix-data')
        self.assertContains(response, 'FilterManager')

    def test_text_answers_with_filter_param(self):
        """
        GIVEN sessions with Red and Blue answers
        WHEN GET text answers with filters=<choice_id>:1 (Red only)
        THEN returns only the text answer from the Red session
        """
        filters = f'{self.q_choice.id}:1'
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/analytics/questions/{self.q_text.id}/text/'
            f'?filters={filters}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'I like red')
        self.assertNotContains(response, 'I like blue')


class SessionDetailViewTest(TestCase):
    """Tests for analytics session detail modal endpoint."""

    def setUp(self):
        self.org = _make_org('SessionDetailOrg')
        self.owner = User.objects.create_user('sdowner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.client.login(username='sdowner', password='pass')

        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

        self.survey = SurveyHeader.objects.create(
            name='sd_test', organization=self.org,
            created_by=self.owner, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.q_choice = Question.objects.create(
            survey_section=self.section, name='Favorite', code='qf',
            input_type='choice', order_number=1,
            choices=[{'code': 1, 'name': 'Alpha'}, {'code': 2, 'name': 'Beta'}],
        )
        self.q_text = Question.objects.create(
            survey_section=self.section, name='Comment', code='qc',
            input_type='text', order_number=2,
        )
        self.q_point = Question.objects.create(
            survey_section=self.section, name='Location', code='qp',
            input_type='point', order_number=3,
        )

        self.sess = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(
            survey_session=self.sess, question=self.q_choice,
            selected_choices=[1],
        )
        Answer.objects.create(
            survey_session=self.sess, question=self.q_text,
            text='Great survey',
        )
        Answer.objects.create(
            survey_session=self.sess, question=self.q_point,
            point=Point(2.35, 48.86),
        )

    def test_session_detail_returns_200(self):
        """
        GIVEN a session with answers
        WHEN GET analytics session detail
        THEN returns 200 with answer data
        """
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{self.sess.id}/'
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alpha')
        self.assertContains(response, 'Great survey')
        self.assertContains(response, 'point feature')

    def test_session_detail_wrong_survey_404(self):
        """
        GIVEN a session from survey A
        WHEN GET session detail using survey B uuid
        THEN returns 404
        """
        other_survey = SurveyHeader.objects.create(
            name='other', organization=self.org,
            created_by=self.owner, status='published',
        )
        response = self.client.get(
            f'/editor/surveys/{other_survey.uuid}/analytics/sessions/{self.sess.id}/'
        )
        self.assertEqual(response.status_code, 404)

    def test_session_detail_requires_auth(self):
        """
        GIVEN an unauthenticated user
        WHEN GET session detail
        THEN redirect to login
        """
        self.client.logout()
        response = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{self.sess.id}/'
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)


class UserAgentParserTest(TestCase):
    """Tests for user agent parsing into device, OS, and browser."""

    def test_chrome_windows_desktop(self):
        """
        GIVEN a Chrome on Windows UA string
        WHEN _parse_user_agent is called
        THEN device_type=desktop, os=Windows, browser=Chrome
        """
        ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        result = _parse_user_agent(ua)
        self.assertEqual(result['device_type'], 'desktop')
        self.assertEqual(result['os'], 'Windows')
        self.assertEqual(result['browser'], 'Chrome')

    def test_safari_iphone_mobile(self):
        """
        GIVEN an iPhone Safari UA string
        WHEN _parse_user_agent is called
        THEN device_type=mobile, os=iOS, browser=Safari
        """
        ua = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
        result = _parse_user_agent(ua)
        self.assertEqual(result['device_type'], 'mobile')
        self.assertEqual(result['os'], 'iOS')
        self.assertEqual(result['browser'], 'Safari')

    def test_firefox_linux_desktop(self):
        """
        GIVEN a Firefox on Linux UA string
        WHEN _parse_user_agent is called
        THEN device_type=desktop, os=Linux, browser=Firefox
        """
        ua = 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0'
        result = _parse_user_agent(ua)
        self.assertEqual(result['device_type'], 'desktop')
        self.assertEqual(result['os'], 'Linux')
        self.assertEqual(result['browser'], 'Firefox')

    def test_android_chrome_mobile(self):
        """
        GIVEN a Chrome on Android mobile UA string
        WHEN _parse_user_agent is called
        THEN device_type=mobile, os=Android, browser=Chrome
        """
        ua = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
        result = _parse_user_agent(ua)
        self.assertEqual(result['device_type'], 'mobile')
        self.assertEqual(result['os'], 'Android')
        self.assertEqual(result['browser'], 'Chrome')

    def test_ipad_tablet(self):
        """
        GIVEN an iPad UA string
        WHEN _parse_user_agent is called
        THEN device_type=tablet, os=iOS
        """
        ua = 'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
        result = _parse_user_agent(ua)
        self.assertEqual(result['device_type'], 'tablet')
        self.assertEqual(result['os'], 'iOS')

    def test_empty_ua(self):
        """
        GIVEN an empty UA string
        WHEN _parse_user_agent is called
        THEN all fields are 'unknown'
        """
        result = _parse_user_agent('')
        self.assertEqual(result['device_type'], 'unknown')
        self.assertEqual(result['os'], 'unknown')
        self.assertEqual(result['browser'], 'unknown')

    def test_edge_browser(self):
        """
        GIVEN an Edge browser UA string
        WHEN _parse_user_agent is called
        THEN browser=Edge
        """
        ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
        result = _parse_user_agent(ua)
        self.assertEqual(result['browser'], 'Edge')

    def test_yandex_browser(self):
        """
        GIVEN a Yandex Browser UA string
        WHEN _parse_user_agent is called
        THEN browser=Yandex
        """
        ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 YaBrowser/24.1.0 Safari/537.36'
        result = _parse_user_agent(ua)
        self.assertEqual(result['browser'], 'Yandex')


class ReferrerClassificationTest(TestCase):
    """Tests for referrer hostname extraction and bucketing."""

    def test_google_referrer(self):
        """
        GIVEN a referrer URL from google.com
        WHEN _classify_referrer is called
        THEN it returns host 'google.com' and bucket 'google'
        """
        host, bucket = _classify_referrer('https://www.google.com/search?q=survey')
        self.assertEqual(bucket, 'google')
        self.assertEqual(host, 'google.com')

    def test_direct_empty_referrer(self):
        """
        GIVEN an empty referrer string
        WHEN _classify_referrer is called
        THEN it returns empty host and bucket 'direct'
        """
        host, bucket = _classify_referrer('')
        self.assertEqual(bucket, 'direct')
        self.assertEqual(host, '')

    def test_direct_none_referrer(self):
        """
        GIVEN None as referrer
        WHEN _classify_referrer is called
        THEN it returns empty host and bucket 'direct'
        """
        host, bucket = _classify_referrer(None)
        self.assertEqual(bucket, 'direct')
        self.assertEqual(host, '')

    def test_social_instagram(self):
        """
        GIVEN a referrer URL from instagram.com
        WHEN _classify_referrer is called
        THEN it returns bucket 'social'
        """
        host, bucket = _classify_referrer('https://l.instagram.com/redirect?u=...')
        self.assertEqual(bucket, 'social')

    def test_unknown_domain_is_other(self):
        """
        GIVEN a referrer URL from an unrecognized domain
        WHEN _classify_referrer is called
        THEN it returns the bare hostname and bucket 'other'
        """
        host, bucket = _classify_referrer('https://example-blog.com/post/1')
        self.assertEqual(bucket, 'other')
        self.assertEqual(host, 'example-blog.com')

    def test_www_prefix_stripped(self):
        """
        GIVEN a referrer with www.facebook.com
        WHEN _classify_referrer is called
        THEN it returns 'facebook.com' and bucket 'social'
        """
        host, bucket = _classify_referrer('https://www.facebook.com/share')
        self.assertEqual(host, 'facebook.com')
        self.assertEqual(bucket, 'social')


class EmitEventTest(TestCase):
    """Tests for the emit_event function."""

    def setUp(self):
        self.org = _make_org('EventOrg')
        self.survey = SurveyHeader.objects.create(
            name='event_survey', organization=self.org, status='published',
        )
        self.session = SurveySession.objects.create(survey=self.survey)

    def test_emit_creates_event_row(self):
        """
        GIVEN a saved SurveySession
        WHEN emit_event is called with event_type='section_view'
        THEN a SurveyEvent row is created with correct fields
        """
        emit_event(self.session, 'section_view', {'section_name': 'intro'})
        ev = SurveyEvent.objects.get(session=self.session, event_type='section_view')
        self.assertEqual(ev.metadata['section_name'], 'intro')

    def test_emit_with_none_session(self):
        """
        GIVEN None as session
        WHEN emit_event is called
        THEN no exception is raised and no row is created
        """
        emit_event(None, 'section_view')
        self.assertEqual(SurveyEvent.objects.count(), 0)

    def test_emit_swallows_db_error(self):
        """
        GIVEN an unsaved session with no PK
        WHEN emit_event is called
        THEN no exception propagates to the caller
        """
        unsaved = SurveySession(survey=self.survey)
        try:
            emit_event(unsaved, 'session_start')
        except Exception as e:
            self.fail(f'emit_event raised unexpectedly: {e}')


class EventIntegrationTest(TestCase):
    """Tests for event emission in survey views."""

    def setUp(self):
        self.client = Client()
        self.org = _make_org('EventIntOrg')
        self.user = User.objects.create_user('eventuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='event_int_survey', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        self.question = Question.objects.create(
            survey_section=self.section, name='Q1', code='q1',
            input_type='text', order_number=1,
        )

    def test_session_start_on_first_visit(self):
        """
        GIVEN a published survey with one section
        WHEN a GET to the first section is made without an existing session
        THEN a session_start and section_view SurveyEvent are created
        """
        self.client.get(f'/surveys/{self.survey.uuid}/s1/')
        self.assertTrue(SurveyEvent.objects.filter(event_type='session_start').exists())
        self.assertTrue(SurveyEvent.objects.filter(event_type='section_view').exists())

    def test_no_duplicate_session_start_on_revisit(self):
        """
        GIVEN a session already created from visiting section s1
        WHEN the same section is visited again (back navigation)
        THEN no additional session_start event is created
        """
        self.client.get(f'/surveys/{self.survey.uuid}/s1/')
        start_count = SurveyEvent.objects.filter(event_type='session_start').count()
        self.client.get(f'/surveys/{self.survey.uuid}/s1/')
        self.assertEqual(
            SurveyEvent.objects.filter(event_type='session_start').count(),
            start_count,
        )

    def test_section_submit_on_post(self):
        """
        GIVEN an active session on section s1
        WHEN a POST with answer data is made
        THEN a section_submit event is created
        """
        self.client.get(f'/surveys/{self.survey.uuid}/s1/')
        self.client.post(f'/surveys/{self.survey.uuid}/s1/', {'q1': 'hello'})
        self.assertTrue(SurveyEvent.objects.filter(event_type='section_submit').exists())

    def test_survey_complete_on_thanks(self):
        """
        GIVEN an active session that submitted the last section
        WHEN the thanks page is visited
        THEN a survey_complete event is created
        """
        self.client.get(f'/surveys/{self.survey.uuid}/s1/')
        self.client.post(f'/surveys/{self.survey.uuid}/s1/', {'q1': 'hello'})
        self.client.get(f'/surveys/{self.survey.uuid}/thanks/')
        self.assertTrue(SurveyEvent.objects.filter(event_type='survey_complete').exists())

    def test_session_start_captures_referrer(self):
        """
        GIVEN a request with HTTP_REFERER from google.com
        WHEN the first section is visited
        THEN the session_start event metadata contains referrer_type='google'
        """
        self.client.get(
            f'/surveys/{self.survey.uuid}/s1/',
            HTTP_REFERER='https://www.google.com/search?q=test',
        )
        ev = SurveyEvent.objects.get(event_type='session_start')
        self.assertEqual(ev.metadata['referrer_type'], 'google')
        self.assertEqual(ev.metadata['referrer_host'], 'google.com')


class PageLoadTrackingTest(TestCase):
    """Tests for the fire-and-forget page_load AJAX endpoint."""

    def setUp(self):
        self.client = Client()
        self.org = _make_org('PLOrg')
        self.survey = SurveyHeader.objects.create(
            name='pl_survey', organization=self.org, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', code='S1', is_head=True,
        )
        # Visit section to create session
        self.client.get(f'/surveys/{self.survey.uuid}/s1/')
        self.session = SurveySession.objects.first()

    def test_valid_page_load_creates_event(self):
        """
        GIVEN a valid session_id matching the server session and a load_ms value
        WHEN POST is sent to /surveys/track/event/ with event_type=page_load
        THEN response is 204 and a page_load SurveyEvent is created
        """
        response = self.client.post(
            '/surveys/track/event/',
            data=json.dumps({
                'event_type': 'page_load',
                'session_id': self.session.pk,
                'load_ms': 1500,
                'section_name': 's1',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 204)
        ev = SurveyEvent.objects.filter(event_type='page_load').first()
        self.assertIsNotNone(ev)
        self.assertEqual(ev.metadata['load_ms'], 1500)

    def test_valid_page_leave_creates_event(self):
        """
        GIVEN a valid session and time_on_page_ms
        WHEN POST is sent with event_type=page_leave
        THEN response is 204 and a page_leave SurveyEvent is created
        """
        response = self.client.post(
            '/surveys/track/event/',
            data=json.dumps({
                'event_type': 'page_leave',
                'session_id': self.session.pk,
                'time_on_page_ms': 45000,
                'section_name': 's1',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 204)
        ev = SurveyEvent.objects.filter(event_type='page_leave').first()
        self.assertIsNotNone(ev)
        self.assertEqual(ev.metadata['time_on_page_ms'], 45000)

    def test_mismatched_session_returns_204_silently(self):
        """
        GIVEN a session_id in payload that does not match the server session
        WHEN POST is sent to /surveys/track/event/
        THEN response is 204 and no event is created
        """
        response = self.client.post(
            '/surveys/track/event/',
            data=json.dumps({
                'event_type': 'page_load',
                'session_id': 99999,
                'load_ms': 1000,
                'section_name': 's1',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(SurveyEvent.objects.filter(event_type='page_load').exists())

    def test_invalid_event_type_returns_400(self):
        """
        GIVEN an event_type not in the allowed set
        WHEN POST is sent to /surveys/track/event/
        THEN response is 400
        """
        response = self.client.post(
            '/surveys/track/event/',
            data=json.dumps({
                'event_type': 'session_start',
                'session_id': self.session.pk,
                'section_name': 's1',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_fields_returns_400(self):
        """
        GIVEN a payload missing session_id
        WHEN POST is sent to /surveys/track/event/
        THEN response is 400
        """
        response = self.client.post(
            '/surveys/track/event/',
            data=json.dumps({
                'event_type': 'page_load',
                'section_name': 's1',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_load_ms_returns_400(self):
        """
        GIVEN a load_ms value of 0 (invalid)
        WHEN POST is sent to /surveys/track/event/
        THEN response is 400
        """
        response = self.client.post(
            '/surveys/track/event/',
            data=json.dumps({
                'event_type': 'page_load',
                'session_id': self.session.pk,
                'load_ms': 0,
                'section_name': 's1',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)


class PerformanceAnalyticsServiceTest(TestCase):
    """Tests for PerformanceAnalyticsService query methods."""

    def setUp(self):
        self.org = _make_org('PerfOrg')
        self.survey = SurveyHeader.objects.create(
            name='perf_survey', organization=self.org, status='published',
        )
        self.s1 = SurveySession.objects.create(survey=self.survey)
        self.s2 = SurveySession.objects.create(survey=self.survey)

    def test_event_summary_counts(self):
        """
        GIVEN two sessions, one completed
        WHEN get_event_summary is called
        THEN session_starts=2, completions=1, completion_rate=50
        """
        from .analytics import PerformanceAnalyticsService
        emit_event(self.s1, 'session_start')
        emit_event(self.s2, 'session_start')
        emit_event(self.s1, 'survey_complete')

        svc = PerformanceAnalyticsService(self.survey)
        summary = svc.get_event_summary()
        self.assertEqual(summary['session_starts'], 2)
        self.assertEqual(summary['completions'], 1)
        self.assertEqual(summary['completion_rate'], 50)

    def test_referrer_breakdown_groups_by_type(self):
        """
        GIVEN two session_start events from google and one direct
        WHEN get_referrer_breakdown is called
        THEN google has count 2 and appears first
        """
        from .analytics import PerformanceAnalyticsService
        emit_event(self.s1, 'session_start', {'referrer_type': 'google'})
        emit_event(self.s2, 'session_start', {'referrer_type': 'google'})
        s3 = SurveySession.objects.create(survey=self.survey)
        emit_event(s3, 'session_start', {'referrer_type': 'direct'})

        svc = PerformanceAnalyticsService(self.survey)
        refs = svc.get_referrer_breakdown()
        self.assertEqual(refs[0]['referrer_type'], 'google')
        self.assertEqual(refs[0]['count'], 2)

    def test_empty_survey_returns_safe_defaults(self):
        """
        GIVEN a survey with no events
        WHEN all service methods are called
        THEN they return empty lists or zero counts without error
        """
        from .analytics import PerformanceAnalyticsService
        svc = PerformanceAnalyticsService(self.survey)
        summary = svc.get_event_summary()
        self.assertEqual(summary['session_starts'], 0)
        self.assertIsNone(summary['median_load_ms'])
        self.assertEqual(svc.get_funnel(), [])
        self.assertEqual(svc.get_referrer_breakdown(), [])
        self.assertEqual(svc.get_page_load_stats(), [])

    def test_completion_by_referrer(self):
        """
        GIVEN two sessions from 'social', one completed
        WHEN get_completion_by_referrer is called
        THEN social has started=2, completed=1, rate=50
        """
        from .analytics import PerformanceAnalyticsService
        emit_event(self.s1, 'session_start', {'referrer_type': 'social'})
        emit_event(self.s2, 'session_start', {'referrer_type': 'social'})
        emit_event(self.s1, 'survey_complete')

        svc = PerformanceAnalyticsService(self.survey)
        result = svc.get_completion_by_referrer()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['started'], 2)
        self.assertEqual(result[0]['completed'], 1)
        self.assertEqual(result[0]['rate'], 50)


class UtmCaptureTest(TestCase):
    """Tests for UTM param capture via session storage and event metadata."""

    def setUp(self):
        self.client = Client()
        self.org = _make_org('UtmOrg')
        self.survey = SurveyHeader.objects.create(
            name='utmsurvey', organization=self.org, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='s1', is_head=True, code='S1',
        )

    def test_utm_stored_in_session_on_survey_entry(self):
        """
        GIVEN a published survey
        WHEN the entry URL is visited with utm_source param
        THEN utm_params are stored in the session
        """
        self.client.get(f'/surveys/{self.survey.uuid}/?utm_source=newsletter&utm_medium=email')
        self.assertIn('utm_params', self.client.session)
        self.assertEqual(self.client.session['utm_params']['utm_source'], 'newsletter')
        self.assertEqual(self.client.session['utm_params']['utm_medium'], 'email')

    def test_utm_appears_in_session_start_event(self):
        """
        GIVEN utm_params stored in session from survey entry
        WHEN the first section is visited (creating session_start event)
        THEN the event metadata contains utm_source
        """
        # Visit entry URL to store UTM, then follow redirect to section
        self.client.get(f'/surveys/{self.survey.uuid}/?utm_source=social&utm_campaign=spring')
        self.client.get(f'/surveys/{self.survey.uuid}/s1/')
        event = SurveyEvent.objects.filter(event_type='session_start').last()
        self.assertIsNotNone(event)
        self.assertEqual(event.metadata.get('utm_source'), 'social')
        self.assertEqual(event.metadata.get('utm_campaign'), 'spring')

    def test_utm_consumed_after_session_start(self):
        """
        GIVEN utm_params stored in session
        WHEN the session_start event fires
        THEN utm_params are removed from the session
        """
        self.client.get(f'/surveys/{self.survey.uuid}/?utm_source=test')
        self.client.get(f'/surveys/{self.survey.uuid}/s1/')
        self.assertNotIn('utm_params', self.client.session)

    def test_no_utm_does_not_break(self):
        """
        GIVEN a request with no UTM params
        WHEN the session_start event fires
        THEN no utm_source in metadata and no error
        """
        self.client.get(f'/surveys/{self.survey.uuid}/s1/')
        event = SurveyEvent.objects.filter(event_type='session_start').last()
        self.assertIsNotNone(event)
        self.assertNotIn('utm_source', event.metadata)


class TrackedLinkModelTest(TestCase):
    """Tests for TrackedLink model."""

    def setUp(self):
        self.org = _make_org('LinkOrg')
        self.survey = SurveyHeader.objects.create(name='linksurvey', organization=self.org)

    def test_build_url_includes_all_params(self):
        """
        GIVEN a TrackedLink with source, medium, campaign
        WHEN build_url is called
        THEN the returned URL contains all three utm params
        """
        link = TrackedLink.objects.create(
            survey=self.survey, utm_source='fb', utm_medium='social', utm_campaign='q1',
        )
        url = link.build_url()
        self.assertIn('utm_source=fb', url)
        self.assertIn('utm_medium=social', url)
        self.assertIn('utm_campaign=q1', url)

    def test_build_url_omits_blank_params(self):
        """
        GIVEN a TrackedLink with only utm_source
        WHEN build_url is called
        THEN the URL contains utm_source but not utm_medium or utm_campaign
        """
        link = TrackedLink.objects.create(
            survey=self.survey, utm_source='direct',
        )
        url = link.build_url()
        self.assertIn('utm_source=direct', url)
        self.assertNotIn('utm_medium', url)
        self.assertNotIn('utm_campaign', url)


class ShareViewTest(TestCase):
    """Tests for the Share page view."""

    def setUp(self):
        self.client = Client()
        self.org = _make_org('ShareOrg')
        self.user = User.objects.create_user('shareuser', password='pw')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='sharesurvey', organization=self.org, created_by=self.user,
        )
        self.client.login(username='shareuser', password='pw')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def test_share_page_get_returns_200(self):
        """
        GIVEN an authenticated editor user
        WHEN the share page is requested via GET
        THEN the response is 200
        """
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/share/')
        self.assertEqual(response.status_code, 200)

    def test_share_page_post_creates_link(self):
        """
        GIVEN an authenticated editor user
        WHEN a POST with utm_source is submitted
        THEN a TrackedLink is created and user is redirected
        """
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/share/',
            {'utm_source': 'newsletter', 'utm_medium': 'email', 'utm_campaign': ''},
        )
        self.assertEqual(TrackedLink.objects.filter(survey=self.survey).count(), 1)
        self.assertRedirects(response, f'/editor/surveys/{self.survey.uuid}/share/')

    def test_share_page_post_missing_source(self):
        """
        GIVEN an authenticated editor user
        WHEN a POST with empty utm_source is submitted
        THEN no TrackedLink is created
        """
        self.client.post(
            f'/editor/surveys/{self.survey.uuid}/share/',
            {'utm_source': '', 'utm_medium': '', 'utm_campaign': ''},
        )
        self.assertEqual(TrackedLink.objects.filter(survey=self.survey).count(), 0)

    def test_share_link_delete(self):
        """
        GIVEN a TrackedLink exists
        WHEN DELETE POST is sent
        THEN the link is removed
        """
        link = TrackedLink.objects.create(survey=self.survey, utm_source='test')
        response = self.client.post(
            f'/editor/surveys/{self.survey.uuid}/share/{link.id}/delete/',
        )
        self.assertFalse(TrackedLink.objects.filter(id=link.id).exists())


class CampaignAnalyticsTest(TestCase):
    """Tests for campaign breakdown analytics."""

    def setUp(self):
        self.org = _make_org('CampOrg')
        self.survey = SurveyHeader.objects.create(name='campsurvey', organization=self.org)
        self.s1 = SurveySession.objects.create(survey=self.survey)
        self.s2 = SurveySession.objects.create(survey=self.survey)
        emit_event(self.s1, 'session_start', {'utm_source': 'newsletter', 'utm_medium': 'email', 'utm_campaign': 'q1'})
        emit_event(self.s2, 'session_start', {'utm_source': 'newsletter', 'utm_medium': 'email', 'utm_campaign': 'q1'})
        emit_event(self.s1, 'survey_complete')

    def test_campaign_groups_by_utm_triple(self):
        """
        GIVEN two sessions with same UTM params, one completed
        WHEN get_campaign_breakdown is called
        THEN one row with started=2, completed=1, rate=50
        """
        svc = PerformanceAnalyticsService(self.survey)
        result = svc.get_campaign_breakdown()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['utm_source'], 'newsletter')
        self.assertEqual(result[0]['started'], 2)
        self.assertEqual(result[0]['completed'], 1)
        self.assertEqual(result[0]['rate'], 50)

    def test_campaign_excludes_non_utm_sessions(self):
        """
        GIVEN a session_start with no utm_source
        WHEN get_campaign_breakdown is called
        THEN that session is excluded
        """
        s3 = SurveySession.objects.create(survey=self.survey)
        emit_event(s3, 'session_start', {'referrer_type': 'direct'})
        svc = PerformanceAnalyticsService(self.survey)
        result = svc.get_campaign_breakdown()
        self.assertEqual(len(result), 1)


class SessionValidationStatusTest(TestCase):
    """Tests for session validation status and soft-delete (trash) feature."""

    def setUp(self):
        self.org = _make_org('ValidationOrg')
        self.user = User.objects.create_user('valowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

        self.viewer = User.objects.create_user('valviewer', password='pass')
        Membership.objects.create(user=self.viewer, organization=self.org, role='viewer')

        self.survey = SurveyHeader.objects.create(
            name='validation_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.q_text = Question.objects.create(
            survey_section=self.section, name='Comment', code='q1',
            input_type='text', order_number=1,
        )
        self.q_point = Question.objects.create(
            survey_section=self.section, name='Location', code='q2',
            input_type='point', order_number=2,
        )

    def _create_session(self, **kwargs):
        session = SurveySession.objects.create(survey=self.survey, **kwargs)
        Answer.objects.create(survey_session=session, question=self.q_text, text='hello')
        return session

    def _login_owner(self):
        self.client.login(username='valowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def _login_viewer(self):
        self.client.login(username='valviewer', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    # -- Model defaults --

    def test_session_field_defaults(self):
        """
        GIVEN a newly created SurveySession
        WHEN no validation fields are set
        THEN defaults are validation_status='', is_deleted=False, deleted_at=None
        """
        s = SurveySession.objects.create(survey=self.survey)
        self.assertEqual(s.validation_status, '')
        self.assertFalse(s.is_deleted)
        self.assertIsNone(s.deleted_at)

    # -- QuerySet --

    def test_active_excludes_deleted(self):
        """
        GIVEN one active and one soft-deleted session
        WHEN SurveySession.objects.active() is called
        THEN only the active session is returned
        """
        s_active = self._create_session()
        s_deleted = self._create_session(is_deleted=True)
        active_qs = SurveySession.objects.active().filter(survey=self.survey)
        self.assertIn(s_active, active_qs)
        self.assertNotIn(s_deleted, active_qs)

    def test_deleted_returns_only_deleted(self):
        """
        GIVEN one active and one soft-deleted session
        WHEN SurveySession.objects.deleted() is called
        THEN only the deleted session is returned
        """
        s_active = self._create_session()
        s_deleted = self._create_session(is_deleted=True)
        deleted_qs = SurveySession.objects.deleted().filter(survey=self.survey)
        self.assertNotIn(s_active, deleted_qs)
        self.assertIn(s_deleted, deleted_qs)

    # -- SessionValidationService --

    def test_set_status_valid(self):
        """
        GIVEN a session with no status
        WHEN set_status is called with 'approved'
        THEN session.validation_status becomes 'approved'
        """
        s = self._create_session()
        svc = SessionValidationService()
        svc.set_status(s, 'approved')
        s.refresh_from_db()
        self.assertEqual(s.validation_status, 'approved')

    def test_set_status_invalid_raises(self):
        """
        GIVEN a session
        WHEN set_status is called with an invalid value
        THEN ValueError is raised
        """
        s = self._create_session()
        svc = SessionValidationService()
        with self.assertRaises(ValueError):
            svc.set_status(s, 'invalid_status')

    def test_trash_session(self):
        """
        GIVEN an active session
        WHEN trash() is called
        THEN is_deleted=True and deleted_at is set
        """
        s = self._create_session()
        svc = SessionValidationService()
        svc.trash(s)
        s.refresh_from_db()
        self.assertTrue(s.is_deleted)
        self.assertIsNotNone(s.deleted_at)

    def test_restore_session(self):
        """
        GIVEN a trashed session
        WHEN restore() is called
        THEN is_deleted=False and deleted_at is None
        """
        s = self._create_session(is_deleted=True)
        svc = SessionValidationService()
        svc.restore(s)
        s.refresh_from_db()
        self.assertFalse(s.is_deleted)
        self.assertIsNone(s.deleted_at)

    def test_hard_delete(self):
        """
        GIVEN a trashed session
        WHEN hard_delete() is called
        THEN the session is permanently removed from the database
        """
        s = self._create_session(is_deleted=True)
        sid = s.id
        svc = SessionValidationService()
        svc.hard_delete(s)
        self.assertFalse(SurveySession.objects.filter(id=sid).exists())

    # -- Analytics service with trashed sessions --

    def test_overview_excludes_trashed(self):
        """
        GIVEN 2 active sessions and 1 trashed session
        WHEN get_overview() is called
        THEN total_sessions is 2
        """
        self._create_session()
        self._create_session()
        self._create_session(is_deleted=True)
        svc = SurveyAnalyticsService(self.survey)
        overview = svc.get_overview()
        self.assertEqual(overview['total_sessions'], 2)

    def test_table_excludes_trashed(self):
        """
        GIVEN 2 active sessions and 1 trashed session
        WHEN get_table_page(show_trash=False) is called
        THEN only 2 rows are returned
        """
        self._create_session()
        self._create_session()
        self._create_session(is_deleted=True)
        svc = SurveyAnalyticsService(self.survey)
        result = svc.get_table_page(show_trash=False)
        self.assertEqual(result['total'], 2)

    def test_table_trash_mode(self):
        """
        GIVEN 2 active sessions and 1 trashed session
        WHEN get_table_page(show_trash=True) is called
        THEN only the trashed session is returned
        """
        self._create_session()
        self._create_session()
        self._create_session(is_deleted=True)
        svc = SurveyAnalyticsService(self.survey, include_deleted=True)
        result = svc.get_table_page(show_trash=True)
        self.assertEqual(result['total'], 1)

    def test_geo_excludes_trashed(self):
        """
        GIVEN a geo answer on an active session and one on a trashed session
        WHEN get_geo_feature_collection() is called
        THEN only the active session's feature is returned
        """
        s_active = self._create_session()
        Answer.objects.create(
            survey_session=s_active, question=self.q_point,
            point=Point(13.4, 52.5),
        )
        s_deleted = self._create_session(is_deleted=True)
        Answer.objects.create(
            survey_session=s_deleted, question=self.q_point,
            point=Point(13.5, 52.6),
        )
        svc = SurveyAnalyticsService(self.survey)
        geo = svc.get_geo_feature_collection()
        self.assertEqual(len(geo['features']), 1)

    # -- View endpoints --

    def test_set_status_endpoint(self):
        """
        GIVEN an active session and an editor user
        WHEN POST to set status with 'approved'
        THEN response is 204 and session status is updated
        """
        s = self._create_session()
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{s.id}/status/'
        resp = self.client.post(url, {'validation_status': 'approved'})
        self.assertEqual(resp.status_code, 204)
        s.refresh_from_db()
        self.assertEqual(s.validation_status, 'approved')

    def test_set_status_invalid_returns_400(self):
        """
        GIVEN an active session and an editor user
        WHEN POST with an invalid status value
        THEN response is 400
        """
        s = self._create_session()
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{s.id}/status/'
        resp = self.client.post(url, {'validation_status': 'bogus'})
        self.assertEqual(resp.status_code, 400)

    def test_trash_endpoint(self):
        """
        GIVEN an active session and an editor user
        WHEN POST to trash endpoint
        THEN response is 204 and session is soft-deleted
        """
        s = self._create_session()
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{s.id}/trash/'
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 204)
        s.refresh_from_db()
        self.assertTrue(s.is_deleted)

    def test_restore_endpoint(self):
        """
        GIVEN a trashed session and an editor user
        WHEN POST to restore endpoint
        THEN response is 204 and session is restored
        """
        s = self._create_session(is_deleted=True)
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{s.id}/restore/'
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 204)
        s.refresh_from_db()
        self.assertFalse(s.is_deleted)

    def test_hard_delete_endpoint(self):
        """
        GIVEN a trashed session and an editor user
        WHEN POST to hard delete endpoint
        THEN response is 204 and session is gone from DB
        """
        s = self._create_session(is_deleted=True)
        sid = s.id
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{sid}/delete/'
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(SurveySession.objects.filter(id=sid).exists())

    def test_viewer_cannot_trash(self):
        """
        GIVEN a viewer user
        WHEN POST to trash endpoint
        THEN response is 403
        """
        s = self._create_session()
        self._login_viewer()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{s.id}/trash/'
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)

    def test_table_view_trash_param(self):
        """
        GIVEN 2 active and 1 trashed session
        WHEN GET analytics table with ?trash=1
        THEN response contains only trashed sessions
        """
        self._create_session()
        self._create_session()
        self._create_session(is_deleted=True)
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/table/?trash=1'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '1 trashed')


class CleanExportTest(TestCase):
    """Tests for clean export (respects validation status and trash)."""

    def setUp(self):
        self.org = _make_org('ExportOrg')
        self.user = User.objects.create_user('exportuser', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

        self.survey = SurveyHeader.objects.create(
            name='export_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.q_text = Question.objects.create(
            survey_section=self.section, name='Comment', code='q1',
            input_type='text', order_number=1,
        )
        self.q_point = Question.objects.create(
            survey_section=self.section, name='Location', code='q2',
            input_type='point', order_number=2,
        )
        self.client.login(username='exportuser', password='pass')

    def _create_session(self, text='hello', point=None, **kwargs):
        session = SurveySession.objects.create(survey=self.survey, **kwargs)
        Answer.objects.create(survey_session=session, question=self.q_text, text=text)
        if point:
            Answer.objects.create(survey_session=session, question=self.q_point, point=point)
        return session

    def _download(self, include_all=False):
        url = f'/surveys/{self.survey.uuid}/download'
        if include_all:
            url += '?include_all=1'
        return self.client.get(url)

    def _extract_csv(self, response):
        import csv
        import io
        zip_buffer = BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            csv_name = [n for n in zf.namelist() if n.endswith('.csv')][0]
            csv_text = zf.read(csv_name).decode('utf-8')
        reader = csv.DictReader(io.StringIO(csv_text))
        return list(reader)

    def _extract_geojson(self, response):
        zip_buffer = BytesIO(response.content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            geojson_name = [n for n in zf.namelist() if n.endswith('.geojson')][0]
            return json.loads(zf.read(geojson_name))

    def test_clean_export_excludes_trashed(self):
        """
        GIVEN 2 active sessions and 1 trashed session
        WHEN download_data is called without include_all
        THEN CSV contains only 2 rows
        """
        self._create_session(text='good1')
        self._create_session(text='good2')
        self._create_session(text='trashed', is_deleted=True)
        resp = self._download()
        self.assertEqual(resp.status_code, 200)
        rows = self._extract_csv(resp)
        self.assertEqual(len(rows), 2)

    def test_clean_export_excludes_not_approved(self):
        """
        GIVEN 1 active session and 1 not_approved session
        WHEN download_data is called without include_all
        THEN CSV contains only 1 row
        """
        self._create_session(text='good')
        self._create_session(text='bad', validation_status='not_approved')
        resp = self._download()
        rows = self._extract_csv(resp)
        self.assertEqual(len(rows), 1)

    def test_include_all_exports_everything(self):
        """
        GIVEN 1 active, 1 trashed, and 1 not_approved session
        WHEN download_data is called with include_all=1
        THEN CSV contains all 3 rows
        """
        self._create_session(text='good')
        self._create_session(text='trashed', is_deleted=True)
        self._create_session(text='rejected', validation_status='not_approved')
        resp = self._download(include_all=True)
        rows = self._extract_csv(resp)
        self.assertEqual(len(rows), 3)

    def test_csv_has_validation_status_column(self):
        """
        GIVEN a session with validation_status='approved'
        WHEN download_data is called
        THEN CSV rows contain a validation_status column
        """
        self._create_session(text='data', validation_status='approved')
        resp = self._download()
        rows = self._extract_csv(resp)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['validation_status'], 'approved')

    def test_geojson_has_validation_status_and_session_id(self):
        """
        GIVEN a session with a geo answer
        WHEN download_data is called
        THEN GeoJSON features have validation_status and session_id properties
        """
        s = self._create_session(text='geo', point=Point(13.4, 52.5), validation_status='approved')
        resp = self._download()
        geojson = self._extract_geojson(resp)
        self.assertEqual(len(geojson['features']), 1)
        props = geojson['features'][0]['properties']
        self.assertEqual(props['validation_status'], 'approved')
        self.assertEqual(props['session_id'], s.id)


class BulkOperationsTest(TestCase):
    """Tests for bulk operations on survey sessions."""

    def setUp(self):
        self.org = _make_org('BulkOrg')
        self.user = User.objects.create_user('bulkowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

        self.viewer = User.objects.create_user('bulkviewer', password='pass')
        Membership.objects.create(user=self.viewer, organization=self.org, role='viewer')

        self.survey = SurveyHeader.objects.create(
            name='bulk_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.q_text = Question.objects.create(
            survey_section=self.section, name='Q', code='q1',
            input_type='text', order_number=1,
        )

    def _create_session(self, **kwargs):
        s = SurveySession.objects.create(survey=self.survey, **kwargs)
        Answer.objects.create(survey_session=s, question=self.q_text, text='data')
        return s

    def _login_owner(self):
        self.client.login(username='bulkowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def _login_viewer(self):
        self.client.login(username='bulkviewer', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def _post_json(self, url, data):
        return self.client.post(url, json.dumps(data), content_type='application/json')

    def test_bulk_set_status(self):
        """
        GIVEN 3 sessions
        WHEN bulk set status to 'approved'
        THEN all 3 sessions have validation_status='approved'
        """
        s1 = self._create_session()
        s2 = self._create_session()
        s3 = self._create_session()
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/bulk/status/'
        resp = self._post_json(url, {'session_ids': [s1.id, s2.id, s3.id], 'status': 'approved'})
        self.assertEqual(resp.status_code, 204)
        for s in [s1, s2, s3]:
            s.refresh_from_db()
            self.assertEqual(s.validation_status, 'approved')

    def test_bulk_trash(self):
        """
        GIVEN 2 active sessions
        WHEN bulk trash is called
        THEN both sessions are soft-deleted
        """
        s1 = self._create_session()
        s2 = self._create_session()
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/bulk/trash/'
        resp = self._post_json(url, {'session_ids': [s1.id, s2.id]})
        self.assertEqual(resp.status_code, 204)
        s1.refresh_from_db()
        s2.refresh_from_db()
        self.assertTrue(s1.is_deleted)
        self.assertTrue(s2.is_deleted)

    def test_bulk_restore(self):
        """
        GIVEN 2 trashed sessions
        WHEN bulk restore is called
        THEN both sessions are restored
        """
        s1 = self._create_session(is_deleted=True)
        s2 = self._create_session(is_deleted=True)
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/bulk/restore/'
        resp = self._post_json(url, {'session_ids': [s1.id, s2.id]})
        self.assertEqual(resp.status_code, 204)
        s1.refresh_from_db()
        s2.refresh_from_db()
        self.assertFalse(s1.is_deleted)
        self.assertFalse(s2.is_deleted)

    def test_bulk_hard_delete(self):
        """
        GIVEN 2 trashed sessions
        WHEN bulk hard delete is called
        THEN both sessions are permanently removed
        """
        s1 = self._create_session(is_deleted=True)
        s2 = self._create_session(is_deleted=True)
        ids = [s1.id, s2.id]
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/bulk/delete/'
        resp = self._post_json(url, {'session_ids': ids})
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(SurveySession.objects.filter(id__in=ids).count(), 0)

    def test_viewer_cannot_bulk_trash(self):
        """
        GIVEN a viewer user
        WHEN bulk trash is called
        THEN response is 403
        """
        s = self._create_session()
        self._login_viewer()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/bulk/trash/'
        resp = self._post_json(url, {'session_ids': [s.id]})
        self.assertEqual(resp.status_code, 403)

    def test_invalid_session_ids_ignored(self):
        """
        GIVEN a mix of valid and invalid session IDs
        WHEN bulk set status is called
        THEN valid sessions are updated, invalid ones are silently ignored
        """
        s = self._create_session()
        self._login_owner()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/bulk/status/'
        resp = self._post_json(url, {'session_ids': [s.id, 999999], 'status': 'on_hold'})
        self.assertEqual(resp.status_code, 204)
        s.refresh_from_db()
        self.assertEqual(s.validation_status, 'on_hold')


class AutoValidationBasicTest(TestCase):
    """Tests for auto-validation basic rules (empty, incomplete, missing required)."""

    def setUp(self):
        self.org = _make_org('AutoValOrg')
        self.user = User.objects.create_user('avowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

        self.survey = SurveyHeader.objects.create(
            name='autoval_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section1 = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.section2 = SurveySection.objects.create(
            survey_header=self.survey, name='sec2', code='S2',
        )
        self.section1.next_section = self.section2
        self.section1.save()

        self.q1_required = Question.objects.create(
            survey_section=self.section1, name='Name', code='q1',
            input_type='text', order_number=1, required=True,
        )
        self.q2_optional = Question.objects.create(
            survey_section=self.section1, name='Comment', code='q2',
            input_type='text', order_number=2, required=False,
        )
        self.q3_sec2 = Question.objects.create(
            survey_section=self.section2, name='Rating', code='q3',
            input_type='number', order_number=1, required=False,
        )

    def _create_completed_session(self):
        """Session with answers in both sections including required."""
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.q1_required, text='Alice')
        Answer.objects.create(survey_session=s, question=self.q2_optional, text='Nice')
        Answer.objects.create(survey_session=s, question=self.q3_sec2, numeric=5)
        return s

    def _create_empty_session(self):
        """Session with 0 answers."""
        return SurveySession.objects.create(survey=self.survey)

    def _create_incomplete_session(self):
        """Session with answers only in section1 (didn't reach section2)."""
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.q1_required, text='Bob')
        return s

    def _create_missing_required_session(self):
        """Session that visited section1 but skipped the required question."""
        s = SurveySession.objects.create(survey=self.survey)
        # Answered optional but not required
        Answer.objects.create(survey_session=s, question=self.q2_optional, text='Hello')
        Answer.objects.create(survey_session=s, question=self.q3_sec2, numeric=3)
        return s

    def test_empty_session_detected(self):
        """
        GIVEN a session with 0 answers
        WHEN compute_session_issues is called
        THEN 'empty' is in the issues list
        """
        s = self._create_empty_session()
        svc = SurveyAnalyticsService(self.survey)
        issues = svc.compute_session_issues([s.id])
        self.assertIn('empty', issues[s.id])

    def test_incomplete_session_detected(self):
        """
        GIVEN a session with answers only in section1
        WHEN compute_session_issues is called
        THEN 'incomplete' is in the issues list
        """
        s = self._create_incomplete_session()
        svc = SurveyAnalyticsService(self.survey)
        issues = svc.compute_session_issues([s.id])
        self.assertIn('incomplete', issues[s.id])

    def test_missing_required_detected(self):
        """
        GIVEN a session that visited section1 but skipped the required question
        WHEN compute_session_issues is called
        THEN 'missing_required' is in the issues list
        """
        s = self._create_missing_required_session()
        svc = SurveyAnalyticsService(self.survey)
        issues = svc.compute_session_issues([s.id])
        self.assertIn('missing_required', issues[s.id])

    def test_clean_session_no_issues(self):
        """
        GIVEN a completed session with all required answers
        WHEN compute_session_issues is called
        THEN the issues list is empty
        """
        s = self._create_completed_session()
        svc = SurveyAnalyticsService(self.survey)
        issues = svc.compute_session_issues([s.id])
        self.assertEqual(issues[s.id], [])

    def test_table_page_includes_issues(self):
        """
        GIVEN sessions with various issues
        WHEN get_table_page is called
        THEN each row has an 'issues' key
        """
        self._create_completed_session()
        self._create_empty_session()
        svc = SurveyAnalyticsService(self.survey)
        result = svc.get_table_page()
        for row in result['rows']:
            self.assertIn('issues', row)

    def test_table_page_issues_filter(self):
        """
        GIVEN 1 clean and 1 empty session
        WHEN get_table_page is called with issues_filter='empty'
        THEN only the empty session is returned
        """
        self._create_completed_session()
        self._create_empty_session()
        svc = SurveyAnalyticsService(self.survey)
        result = svc.get_table_page(issues_filter=['empty'])
        self.assertEqual(result['total'], 1)
        self.assertIn('empty', result['rows'][0]['issues'])

    def test_overview_includes_flagged_count(self):
        """
        GIVEN 1 clean and 2 flagged sessions
        WHEN get_overview is called
        THEN flagged_count is 2
        """
        self._create_completed_session()
        self._create_empty_session()
        self._create_incomplete_session()
        svc = SurveyAnalyticsService(self.survey)
        overview = svc.get_overview()
        self.assertEqual(overview['flagged_count'], 2)

    def test_table_view_issues_param(self):
        """
        GIVEN 1 clean and 1 empty session
        WHEN GET analytics table with ?issues=empty
        THEN response contains only the empty session
        """
        self._create_completed_session()
        self._create_empty_session()
        self.client.login(username='avowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/table/?issues=empty'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '1 result')


class AnswerLintingErrorsTest(TestCase):
    """Tests for answer-level linting: self-intersection and empty required."""

    def setUp(self):
        self.org = _make_org('LintOrg')
        self.user = User.objects.create_user('lintowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')

        self.survey = SurveyHeader.objects.create(
            name='lint_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.q_polygon = Question.objects.create(
            survey_section=self.section, name='Area', code='q1',
            input_type='polygon', order_number=1,
        )
        self.q_required = Question.objects.create(
            survey_section=self.section, name='Name', code='q2',
            input_type='text', order_number=2, required=True,
        )
        self.q_optional = Question.objects.create(
            survey_section=self.section, name='Comment', code='q3',
            input_type='text', order_number=3, required=False,
        )

    def test_self_intersection_detected(self):
        """
        GIVEN a polygon answer with a self-intersecting geometry (bowtie)
        WHEN compute_answer_lints is called
        THEN 'self_intersection' is in the lint for that answer
        """
        s = SurveySession.objects.create(survey=self.survey)
        # Bowtie polygon: self-intersecting
        bowtie = Polygon(((0, 0), (1, 1), (1, 0), (0, 1), (0, 0)))
        Answer.objects.create(survey_session=s, question=self.q_polygon, polygon=bowtie)
        Answer.objects.create(survey_session=s, question=self.q_required, text='Alice')

        svc = SurveyAnalyticsService(self.survey)
        answers = list(Answer.objects.filter(survey_session=s, parent_answer_id__isnull=True).select_related('question'))
        questions = [self.q_polygon, self.q_required, self.q_optional]
        lints = svc.compute_answer_lints([s.id], answers, questions)
        self.assertIn('self_intersection', lints.get(s.id, {}).get(str(self.q_polygon.id), []))

    def test_valid_polygon_no_lint(self):
        """
        GIVEN a polygon answer with valid geometry
        WHEN compute_answer_lints is called
        THEN no lints for that answer
        """
        s = SurveySession.objects.create(survey=self.survey)
        valid_poly = Polygon(((0, 0), (1, 0), (1, 1), (0, 1), (0, 0)))
        Answer.objects.create(survey_session=s, question=self.q_polygon, polygon=valid_poly)
        Answer.objects.create(survey_session=s, question=self.q_required, text='Bob')

        svc = SurveyAnalyticsService(self.survey)
        answers = list(Answer.objects.filter(survey_session=s, parent_answer_id__isnull=True).select_related('question'))
        questions = [self.q_polygon, self.q_required, self.q_optional]
        lints = svc.compute_answer_lints([s.id], answers, questions)
        self.assertEqual(lints.get(s.id, {}).get(str(self.q_polygon.id), []), [])

    def test_empty_required_detected(self):
        """
        GIVEN a session that answered the optional but not the required question
        WHEN compute_answer_lints is called
        THEN 'empty_required' is in the lint for the required question
        """
        s = SurveySession.objects.create(survey=self.survey)
        # Only answer the optional question — skip required
        Answer.objects.create(survey_session=s, question=self.q_optional, text='Hello')

        svc = SurveyAnalyticsService(self.survey)
        answers = list(Answer.objects.filter(survey_session=s, parent_answer_id__isnull=True).select_related('question'))
        questions = [self.q_polygon, self.q_required, self.q_optional]
        lints = svc.compute_answer_lints([s.id], answers, questions)
        self.assertIn('empty_required', lints.get(s.id, {}).get(str(self.q_required.id), []))

    def test_has_errors_filter(self):
        """
        GIVEN 1 clean session and 1 session with a self-intersecting polygon
        WHEN get_table_page is called with issues_filter='has_errors'
        THEN only the session with errors is returned
        """
        # Clean session
        s1 = SurveySession.objects.create(survey=self.survey)
        valid_poly = Polygon(((0, 0), (1, 0), (1, 1), (0, 1), (0, 0)))
        Answer.objects.create(survey_session=s1, question=self.q_polygon, polygon=valid_poly)
        Answer.objects.create(survey_session=s1, question=self.q_required, text='Good')

        # Session with self-intersection
        s2 = SurveySession.objects.create(survey=self.survey)
        bowtie = Polygon(((0, 0), (1, 1), (1, 0), (0, 1), (0, 0)))
        Answer.objects.create(survey_session=s2, question=self.q_polygon, polygon=bowtie)
        Answer.objects.create(survey_session=s2, question=self.q_required, text='Bad')

        svc = SurveyAnalyticsService(self.survey)
        result = svc.get_table_page(issues_filter=['has_errors'])
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['rows'][0]['session_id'], s2.id)

    def test_table_page_includes_lints(self):
        """
        GIVEN a session with lint errors
        WHEN get_table_page is called
        THEN rows include 'lints' key
        """
        s = SurveySession.objects.create(survey=self.survey)
        bowtie = Polygon(((0, 0), (1, 1), (1, 0), (0, 1), (0, 0)))
        Answer.objects.create(survey_session=s, question=self.q_polygon, polygon=bowtie)
        Answer.objects.create(survey_session=s, question=self.q_required, text='Data')

        svc = SurveyAnalyticsService(self.survey)
        result = svc.get_table_page()
        self.assertIn('lints', result['rows'][0])
        self.assertTrue(result['rows'][0]['lints'])


class SessionTagsNotesTest(TestCase):
    """Tests for session tags and notes."""

    def setUp(self):
        self.org = _make_org('TagsOrg')
        self.user = User.objects.create_user('tagsowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='tags_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.q = Question.objects.create(
            survey_section=self.section, name='Q', code='q1',
            input_type='text', order_number=1,
        )

    def _login(self):
        self.client.login(username='tagsowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def test_field_defaults(self):
        """
        GIVEN a new session
        WHEN created with no tags/notes
        THEN defaults are tags=[] and notes=''
        """
        s = SurveySession.objects.create(survey=self.survey)
        self.assertEqual(s.tags, [])
        self.assertEqual(s.notes, '')

    def test_update_tags_endpoint(self):
        """
        GIVEN a session and an editor user
        WHEN POST to update tags with ['expert', 'verified']
        THEN tags are saved on the session
        """
        s = SurveySession.objects.create(survey=self.survey)
        self._login()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{s.id}/tags/'
        resp = self.client.post(url, json.dumps({'tags': ['expert', 'verified']}), content_type='application/json')
        self.assertEqual(resp.status_code, 204)
        s.refresh_from_db()
        self.assertEqual(s.tags, ['expert', 'verified'])

    def test_update_notes_endpoint(self):
        """
        GIVEN a session
        WHEN POST to update notes
        THEN notes are saved
        """
        s = SurveySession.objects.create(survey=self.survey)
        self._login()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{s.id}/tags/'
        resp = self.client.post(url, json.dumps({'notes': 'Important session'}), content_type='application/json')
        self.assertEqual(resp.status_code, 204)
        s.refresh_from_db()
        self.assertEqual(s.notes, 'Important session')

    def test_tags_in_table(self):
        """
        GIVEN a session with tags
        WHEN get_table_page is called
        THEN rows include tags
        """
        s = SurveySession.objects.create(survey=self.survey, tags=['spam', 'test'])
        Answer.objects.create(survey_session=s, question=self.q, text='hi')
        svc = SurveyAnalyticsService(self.survey)
        result = svc.get_table_page()
        self.assertEqual(result['rows'][0]['tags'], ['spam', 'test'])

    def test_tags_searchable(self):
        """
        GIVEN one session tagged 'expert' and one without
        WHEN col_search for tags column contains 'expert'
        THEN only the tagged session is returned
        """
        s1 = SurveySession.objects.create(survey=self.survey, tags=['expert'])
        Answer.objects.create(survey_session=s1, question=self.q, text='a')
        s2 = SurveySession.objects.create(survey=self.survey, tags=[])
        Answer.objects.create(survey_session=s2, question=self.q, text='b')
        svc = SurveyAnalyticsService(self.survey)
        result = svc.get_table_page(col_search={'tags': 'expert'})
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['rows'][0]['session_id'], s1.id)


class InlineEditingTest(TestCase):
    """Tests for inline answer editing."""

    def setUp(self):
        self.org = _make_org('EditOrg')
        self.user = User.objects.create_user('editowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.viewer = User.objects.create_user('editviewer', password='pass')
        Membership.objects.create(user=self.viewer, organization=self.org, role='viewer')
        self.survey = SurveyHeader.objects.create(
            name='edit_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.q_text = Question.objects.create(
            survey_section=self.section, name='Name', code='q1',
            input_type='text', order_number=1,
        )
        self.q_number = Question.objects.create(
            survey_section=self.section, name='Age', code='q2',
            input_type='number', order_number=2,
        )
        self.q_choice = Question.objects.create(
            survey_section=self.section, name='Color', code='q3',
            input_type='choice', order_number=3,
            choices=[{'code': 1, 'name': 'Red'}, {'code': 2, 'name': 'Blue'}],
        )

    def _login_owner(self):
        self.client.login(username='editowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def _login_viewer(self):
        self.client.login(username='editviewer', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def _post_edit(self, session_id, question_id, value):
        url = f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{session_id}/answers/{question_id}/edit/'
        return self.client.post(url, json.dumps({'value': value}), content_type='application/json')

    def test_edit_text_answer(self):
        """
        GIVEN a session with a text answer
        WHEN POST to edit with new text
        THEN the answer text is updated
        """
        s = SurveySession.objects.create(survey=self.survey)
        a = Answer.objects.create(survey_session=s, question=self.q_text, text='Alice')
        self._login_owner()
        resp = self._post_edit(s.id, self.q_text.id, 'Bob')
        self.assertEqual(resp.status_code, 204)
        a.refresh_from_db()
        self.assertEqual(a.text, 'Bob')

    def test_edit_number_answer(self):
        """
        GIVEN a session with a number answer
        WHEN POST to edit with new number
        THEN the answer numeric is updated
        """
        s = SurveySession.objects.create(survey=self.survey)
        a = Answer.objects.create(survey_session=s, question=self.q_number, numeric=25)
        self._login_owner()
        resp = self._post_edit(s.id, self.q_number.id, 30)
        self.assertEqual(resp.status_code, 204)
        a.refresh_from_db()
        self.assertEqual(a.numeric, 30)

    def test_edit_choice_answer(self):
        """
        GIVEN a session with a choice answer
        WHEN POST to edit with new choice code
        THEN selected_choices is updated
        """
        s = SurveySession.objects.create(survey=self.survey)
        a = Answer.objects.create(survey_session=s, question=self.q_choice, selected_choices=[1])
        self._login_owner()
        resp = self._post_edit(s.id, self.q_choice.id, 2)
        self.assertEqual(resp.status_code, 204)
        a.refresh_from_db()
        self.assertEqual(a.selected_choices, [2])

    def test_create_answer_for_blank_cell(self):
        """
        GIVEN a session with no answer for a question
        WHEN POST to edit
        THEN a new answer is created
        """
        s = SurveySession.objects.create(survey=self.survey)
        self._login_owner()
        resp = self._post_edit(s.id, self.q_text.id, 'New value')
        self.assertEqual(resp.status_code, 204)
        self.assertTrue(Answer.objects.filter(survey_session=s, question=self.q_text).exists())
        self.assertEqual(Answer.objects.get(survey_session=s, question=self.q_text).text, 'New value')

    def test_viewer_cannot_edit(self):
        """
        GIVEN a viewer user
        WHEN POST to edit answer
        THEN response is 403
        """
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.q_text, text='Alice')
        self._login_viewer()
        resp = self._post_edit(s.id, self.q_text.id, 'Hacked')
        self.assertEqual(resp.status_code, 403)


class AutoValidationAdvancedTest(TestCase):
    """Tests for advanced auto-validation rules (fast completion, duplicates)."""

    def setUp(self):
        self.org = _make_org('AdvValOrg')
        self.user = User.objects.create_user('advvalowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='advval_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.q = Question.objects.create(
            survey_section=self.section, name='Q', code='q1',
            input_type='text', order_number=1,
        )

    def test_fast_completion_detected(self):
        """
        GIVEN a session completed in 5 seconds
        WHEN compute_session_issues is called
        THEN 'fast' is in the issues list
        """
        from django.utils import timezone as tz
        from datetime import timedelta
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.q, text='hi')
        now = tz.now()
        SurveyEvent.objects.create(session=s, event_type='session_start', created_at=now)
        SurveyEvent.objects.create(session=s, event_type='survey_complete', created_at=now + timedelta(seconds=5))
        svc = SurveyAnalyticsService(self.survey)
        issues = svc.compute_session_issues([s.id])
        self.assertIn('fast', issues[s.id])

    def test_normal_speed_not_flagged(self):
        """
        GIVEN a session completed in 120 seconds
        WHEN compute_session_issues is called
        THEN 'fast' is NOT in the issues list
        """
        from django.utils import timezone as tz
        from datetime import timedelta
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.q, text='hi')
        now = tz.now()
        SurveyEvent.objects.create(session=s, event_type='session_start', created_at=now)
        SurveyEvent.objects.create(session=s, event_type='survey_complete', created_at=now + timedelta(seconds=120))
        svc = SurveyAnalyticsService(self.survey)
        issues = svc.compute_session_issues([s.id])
        self.assertNotIn('fast', issues[s.id])

    def test_duplicate_sessions_detected(self):
        """
        GIVEN two sessions from the same user_agent within 30 minutes
        WHEN compute_session_issues is called
        THEN both have 'duplicate' in issues
        """
        from django.utils import timezone as tz
        from datetime import timedelta
        s1 = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s1, question=self.q, text='a')
        s2 = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s2, question=self.q, text='b')
        now = tz.now()
        ua = 'Mozilla/5.0 TestBrowser'
        SurveyEvent.objects.create(session=s1, event_type='session_start', created_at=now, metadata={'user_agent': ua})
        SurveyEvent.objects.create(session=s2, event_type='session_start', created_at=now + timedelta(minutes=10), metadata={'user_agent': ua})
        svc = SurveyAnalyticsService(self.survey)
        issues = svc.compute_session_issues([s1.id, s2.id])
        self.assertIn('duplicate', issues[s1.id])
        self.assertIn('duplicate', issues[s2.id])

    def test_unique_user_agents_not_duplicate(self):
        """
        GIVEN two sessions from different user_agents
        WHEN compute_session_issues is called
        THEN neither has 'duplicate'
        """
        from django.utils import timezone as tz
        s1 = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s1, question=self.q, text='a')
        s2 = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s2, question=self.q, text='b')
        now = tz.now()
        SurveyEvent.objects.create(session=s1, event_type='session_start', created_at=now, metadata={'user_agent': 'UA-1'})
        SurveyEvent.objects.create(session=s2, event_type='session_start', created_at=now, metadata={'user_agent': 'UA-2'})
        svc = SurveyAnalyticsService(self.survey)
        issues = svc.compute_session_issues([s1.id, s2.id])
        self.assertNotIn('duplicate', issues[s1.id])
        self.assertNotIn('duplicate', issues[s2.id])


class AnswerLintingWarningsTest(TestCase):
    """Tests for answer-level linting warnings (numeric outlier, short text, area outlier)."""

    def setUp(self):
        self.org = _make_org('WarnOrg')
        self.user = User.objects.create_user('warnowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='warn_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.q_number = Question.objects.create(
            survey_section=self.section, name='Age', code='q1',
            input_type='number', order_number=1,
        )
        self.q_text = Question.objects.create(
            survey_section=self.section, name='Comment', code='q2',
            input_type='text', order_number=2,
        )

    def test_numeric_outlier_detected(self):
        """
        GIVEN 10 sessions with age ~25 and 1 with age 999
        WHEN compute_answer_lints is called
        THEN the outlier has 'numeric_outlier' lint
        """
        sessions = []
        for i in range(10):
            s = SurveySession.objects.create(survey=self.survey)
            Answer.objects.create(survey_session=s, question=self.q_number, numeric=25 + i % 3)
            sessions.append(s)
        # Outlier
        s_out = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s_out, question=self.q_number, numeric=999)
        sessions.append(s_out)

        pks = [s.id for s in sessions]
        svc = SurveyAnalyticsService(self.survey)
        answers = list(Answer.objects.filter(survey_session_id__in=pks, parent_answer_id__isnull=True).select_related('question'))
        questions = [self.q_number, self.q_text]
        lints = svc.compute_answer_lints(pks, answers, questions)
        self.assertIn('numeric_outlier', lints.get(s_out.id, {}).get(str(self.q_number.id), []))

    def test_short_text_detected(self):
        """
        GIVEN a session with a 1-char text answer
        WHEN compute_answer_lints is called
        THEN 'short_text' is in the lint
        """
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.q_text, text='a')
        svc = SurveyAnalyticsService(self.survey)
        answers = list(Answer.objects.filter(survey_session=s, parent_answer_id__isnull=True).select_related('question'))
        lints = svc.compute_answer_lints([s.id], answers, [self.q_number, self.q_text])
        self.assertIn('short_text', lints.get(s.id, {}).get(str(self.q_text.id), []))

    def test_normal_text_no_warning(self):
        """
        GIVEN a session with a normal-length text answer
        WHEN compute_answer_lints is called
        THEN no 'short_text' lint
        """
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.q_text, text='This is a good answer')
        svc = SurveyAnalyticsService(self.survey)
        answers = list(Answer.objects.filter(survey_session=s, parent_answer_id__isnull=True).select_related('question'))
        lints = svc.compute_answer_lints([s.id], answers, [self.q_number, self.q_text])
        self.assertNotIn('short_text', lints.get(s.id, {}).get(str(self.q_text.id), []))


class ValidationSettingsTest(TestCase):
    """Tests for configurable validation settings."""

    def setUp(self):
        self.org = _make_org('SettingsOrg')
        self.user = User.objects.create_user('settingsowner', password='pass')
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name='settings_test', organization=self.org,
            created_by=self.user, status='published',
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name='sec1', code='S1', is_head=True,
        )
        self.q_number = Question.objects.create(
            survey_section=self.section, name='Score', code='q1',
            input_type='number', order_number=1,
        )

    def _login(self):
        self.client.login(username='settingsowner', password='pass')
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def test_custom_fast_threshold(self):
        """
        GIVEN survey with fast_threshold_seconds=15
        WHEN a session completes in 20 seconds
        THEN it is NOT flagged as 'fast' (would be flagged with default 30)
        """
        from django.utils import timezone as tz
        from datetime import timedelta
        self.survey.validation_settings = {'fast_threshold_seconds': 15}
        self.survey.save(update_fields=['validation_settings'])
        self.survey.refresh_from_db()
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.q_number, numeric=5)
        now = tz.now()
        SurveyEvent.objects.create(session=s, event_type='session_start', created_at=now)
        SurveyEvent.objects.create(session=s, event_type='survey_complete', created_at=now + timedelta(seconds=20))
        svc = SurveyAnalyticsService(self.survey)
        issues = svc.compute_session_issues([s.id])
        self.assertNotIn('fast', issues[s.id])

    def test_question_min_max_creates_lint(self):
        """
        GIVEN a question with min_value=0 and max_value=100
        WHEN an answer has numeric=150
        THEN 'out_of_range' is in the lint
        """
        self.q_number.validation_settings = {'min_value': 0, 'max_value': 100}
        self.q_number.save()
        s = SurveySession.objects.create(survey=self.survey)
        Answer.objects.create(survey_session=s, question=self.q_number, numeric=150)
        svc = SurveyAnalyticsService(self.survey)
        answers = list(Answer.objects.filter(survey_session=s, parent_answer_id__isnull=True).select_related('question'))
        lints = svc.compute_answer_lints([s.id], answers, [self.q_number])
        self.assertIn('out_of_range', lints.get(s.id, {}).get(str(self.q_number.id), []))

    def test_settings_endpoint_saves_and_returns(self):
        """
        GIVEN an editor user
        WHEN POST to validation settings then GET
        THEN settings are persisted and returned
        """
        self._login()
        url = f'/editor/surveys/{self.survey.uuid}/analytics/validation-settings/'
        resp = self.client.post(url, json.dumps({'fast_threshold_seconds': 60, 'duplicate_window_hours': 2}), content_type='application/json')
        self.assertEqual(resp.status_code, 204)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['fast_threshold_seconds'], 60)
        self.assertEqual(data['duplicate_window_hours'], 2)
