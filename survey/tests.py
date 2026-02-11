from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point, LineString, Polygon
from io import BytesIO
import json
import zipfile

from .models import (
    Organization, SurveyHeader, SurveySection, Question,
    SurveySession, Answer, ChoicesValidator, Story,
)
from .serialization import (
    serialize_survey_to_dict, serialize_sections,
    serialize_questions, serialize_sessions, serialize_answers,
    geo_to_wkt, serialize_choices, export_survey_to_zip, validate_archive,
    import_survey_from_zip, ImportError, FORMAT_VERSION
)
from .forms import SurveySectionAnswerForm


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
        self.survey = SurveyHeader.objects.create(name="data_test_survey")
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
        self.survey = SurveyHeader.objects.create(name="zip_test_survey")
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
        self.survey = SurveyHeader.objects.create(name="cli_test_survey")
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

    def test_import_command_survey_exists(self):
        """
        GIVEN a ZIP archive with survey name that already exists
        WHEN import_survey command is called
        THEN it raises CommandError
        """
        import tempfile
        from django.core.management import call_command
        from django.core.management.base import CommandError

        # Export existing survey
        output = BytesIO()
        export_survey_to_zip(self.survey, output, mode="structure")
        output.seek(0)

        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as f:
            import_path = f.name

        try:
            with open(import_path, 'wb') as f:
                f.write(output.read())

            with self.assertRaises(CommandError) as context:
                call_command('import_survey', import_path)
            self.assertIn("already exists", str(context.exception))
        finally:
            import os
            os.unlink(import_path)


class RoundTripTest(TestCase):
    """Tests for export/import round-trip integrity."""

    def test_roundtrip_structure_only(self):
        """
        GIVEN a complete survey with sections and questions
        WHEN exported and imported with mode=structure
        THEN the imported survey matches the original structure
        """
        # Create original survey
        org = Organization.objects.create(name="RoundTrip Org")
        survey = SurveyHeader.objects.create(
            name="roundtrip_survey",
            organization=org,
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
        self.assertEqual(imported_survey.organization.name, "RoundTrip Org")
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
        survey = SurveyHeader.objects.create(name="full_roundtrip")
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
        survey = SurveyHeader.objects.create(name="geo_roundtrip")
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
        self.survey = SurveyHeader.objects.create(name="existing_survey")
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

    def test_survey_already_exists(self):
        """
        GIVEN a survey already exists with the same name
        WHEN import_survey_from_zip is called
        THEN it raises ImportError
        """
        SurveyHeader.objects.create(name="duplicate_survey")

        survey_data = {
            "version": FORMAT_VERSION,
            "survey": {"name": "duplicate_survey"},
            "option_groups": []
        }

        import_buffer = BytesIO()
        with zipfile.ZipFile(import_buffer, 'w') as zf:
            zf.writestr("survey.json", json.dumps(survey_data))
        import_buffer.seek(0)

        with self.assertRaises(ImportError) as context:
            import_survey_from_zip(import_buffer)
        self.assertIn("already exists", str(context.exception))

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
        survey = SurveyHeader.objects.create(name="missing_ref_survey")
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
        survey = SurveyHeader.objects.create(name="missing_choice_survey")
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

    def test_code_collision_generates_new_code(self):
        """
        GIVEN an existing question with same code as in archive
        WHEN import_survey_from_zip is called
        THEN it generates a new unique code for the imported question
        """
        # Create existing question with code that will collide
        existing_survey = SurveyHeader.objects.create(name="existing")
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
        existing_survey = SurveyHeader.objects.create(name="existing2")
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
        existing_survey = SurveyHeader.objects.create(name="existing3")
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
        existing_survey = SurveyHeader.objects.create(name="existing4")
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
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.survey = SurveyHeader.objects.create(name="web_test_survey")
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
        response = self.client.get('/editor/export/web_test_survey/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_export_authenticated_structure_mode(self):
        """
        GIVEN an authenticated user
        WHEN accessing export URL with mode=structure
        THEN download ZIP file with survey.json
        """
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get('/editor/export/web_test_survey/?mode=structure')

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
        response = self.client.get('/editor/export/web_test_survey/?mode=data')

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
        response = self.client.get('/editor/export/web_test_survey/?mode=full')

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
        response = self.client.get('/editor/export/web_test_survey/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('structure.zip', response['Content-Disposition'])

    def test_export_survey_not_found(self):
        """
        GIVEN an authenticated user
        WHEN accessing export URL for non-existent survey
        THEN redirect with error message
        """
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get('/editor/export/nonexistent_survey/')

        self.assertEqual(response.status_code, 302)

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

    def test_import_survey_already_exists(self):
        """
        GIVEN an authenticated user and archive with existing survey name
        WHEN posting to import URL
        THEN redirect with error message
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


class DeleteSurveyTest(TestCase):
    """Tests for survey deletion functionality."""

    def setUp(self):
        """Set up test data and client."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='deleteuser',
            password='testpass123'
        )
        self.survey = SurveyHeader.objects.create(name="delete_test_survey")
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
        response = self.client.post('/editor/delete/delete_test_survey/')

        self.assertEqual(response.status_code, 302)
        self.assertFalse(SurveyHeader.objects.filter(name="delete_test_survey").exists())

    def test_delete_survey_unauthenticated_redirect(self):
        """
        GIVEN an unauthenticated user
        WHEN accessing delete endpoint
        THEN redirect to login page
        """
        response = self.client.post('/editor/delete/delete_test_survey/')

        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)
        # Survey should still exist
        self.assertTrue(SurveyHeader.objects.filter(name="delete_test_survey").exists())

    def test_delete_survey_not_found(self):
        """
        GIVEN an authenticated user
        WHEN attempting to delete non-existent survey
        THEN redirect with error message
        """
        self.client.login(username='deleteuser', password='testpass123')
        response = self.client.post('/editor/delete/nonexistent_survey/')

        self.assertEqual(response.status_code, 302)

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
        self.client.post('/editor/delete/delete_test_survey/')

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
        response = self.client.get('/editor/delete/delete_test_survey/')

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
            available_languages=[]
        )
        self.assertFalse(survey.is_multilingual())

    def test_survey_is_multilingual_false_no_languages(self):
        """
        GIVEN a survey with no available_languages set
        WHEN is_multilingual() is called
        THEN it returns False
        """
        survey = SurveyHeader.objects.create(name="default_survey")
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
            available_languages=["en", "ru", "de"]
        )
        self.single_lang_survey = SurveyHeader.objects.create(
            name="singlelang_test",
            organization=self.org,
            available_languages=[]
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
        THEN user is redirected to survey entry
        """
        response = self.client.get('/surveys/singlelang_test/language/')

        self.assertEqual(response.status_code, 302)
        self.assertIn('singlelang_test', response.url)

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
            available_languages=["en", "ru"]
        )
        self.single_lang_survey = SurveyHeader.objects.create(
            name="flow_singlelang",
            organization=self.org,
            available_languages=[]
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
            available_languages=["en", "ru"]
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
            available_languages=[]
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
            redirect_url="/completed/"
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
            available_languages=[]
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

    def test_default_visibility_is_private(self):
        """
        GIVEN a new SurveyHeader
        WHEN created without specifying visibility
        THEN visibility should default to 'private'
        """
        org = Organization.objects.create(name="TestOrg")
        survey = SurveyHeader.objects.create(name="test_vis", organization=org)
        self.assertEqual(survey.visibility, "private")

    def test_default_is_archived_is_false(self):
        """
        GIVEN a new SurveyHeader
        WHEN created without specifying is_archived
        THEN is_archived should default to False
        """
        survey = SurveyHeader.objects.create(name="test_arch")
        self.assertFalse(survey.is_archived)

    def test_visibility_choices(self):
        """
        GIVEN a SurveyHeader
        WHEN setting visibility to each valid choice
        THEN each value should be accepted
        """
        for vis in ("private", "demo", "public"):
            survey = SurveyHeader.objects.create(name=f"test_{vis}", visibility=vis)
            self.assertEqual(survey.visibility, vis)


class StoryModelTest(TestCase):
    """Tests for the Story model."""

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
        survey = SurveyHeader.objects.create(name="linked_survey")
        story = Story.objects.create(
            title="Linked", slug="linked", story_type="results", survey=survey,
        )
        self.assertEqual(story.survey, survey)


class LandingPageViewTest(TestCase):
    """Tests for the landing page index view."""

    def setUp(self):
        self.client = Client()
        self.org = Organization.objects.create(name="TestOrg")

    def test_anonymous_sees_landing_page(self):
        """
        GIVEN an unauthenticated user
        WHEN navigating to /
        THEN the system renders the landing page (not a redirect)
        """
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'landing.html')

    def test_authenticated_sees_landing_page(self):
        """
        GIVEN an authenticated user
        WHEN navigating to /
        THEN the system renders the landing page (not a redirect)
        """
        User.objects.create_user('testuser', password='pass')
        self.client.login(username='testuser', password='pass')
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'landing.html')

    def test_only_visible_surveys_shown(self):
        """
        GIVEN surveys with different visibility settings
        WHEN the landing page is rendered
        THEN only demo and public surveys appear in context
        """
        SurveyHeader.objects.create(name="priv", visibility="private", organization=self.org)
        SurveyHeader.objects.create(name="demo_s", visibility="demo", organization=self.org)
        SurveyHeader.objects.create(name="pub_s", visibility="public", organization=self.org)

        response = self.client.get('/')
        survey_names = [s.name for s in response.context['surveys']]
        self.assertNotIn("priv", survey_names)
        self.assertIn("demo_s", survey_names)
        self.assertIn("pub_s", survey_names)

    def test_survey_ordering_demo_active_archived(self):
        """
        GIVEN demo, active public, and archived surveys
        WHEN the landing page is rendered
        THEN surveys are ordered: demo first, active public, then archived
        """
        SurveyHeader.objects.create(name="archived_s", visibility="public", is_archived=True, organization=self.org)
        SurveyHeader.objects.create(name="active_s", visibility="public", organization=self.org)
        SurveyHeader.objects.create(name="demo_s2", visibility="demo", organization=self.org)

        response = self.client.get('/')
        names = [s.name for s in response.context['surveys']]
        self.assertEqual(names[0], "demo_s2")
        self.assertEqual(names[1], "active_s")
        self.assertEqual(names[2], "archived_s")

    def test_no_surveys_section_when_all_private(self):
        """
        GIVEN all surveys have visibility 'private'
        WHEN the landing page is rendered
        THEN no surveys appear in context
        """
        SurveyHeader.objects.create(name="hidden", visibility="private")
        response = self.client.get('/')
        self.assertEqual(len(response.context['surveys']), 0)

    def test_no_stories_when_none_published(self):
        """
        GIVEN no published stories
        WHEN the landing page is rendered
        THEN stories context is empty
        """
        Story.objects.create(title="Draft", slug="draft", story_type="article", is_published=False)
        response = self.client.get('/')
        self.assertEqual(len(response.context['stories']), 0)


class StoryDetailViewTest(TestCase):
    """Tests for the story detail view."""

    def setUp(self):
        self.client = Client()

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
        survey = SurveyHeader.objects.create(name="linked_surv")
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
