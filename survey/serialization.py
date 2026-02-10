"""
Survey import/export serialization module.

Provides functions for exporting surveys to ZIP archives and importing them back.
Supports three modes: structure, data, full.
"""
import json
import zipfile
import os
from datetime import datetime
from io import BytesIO
from typing import IO, Dict, List, Optional, Tuple, Any

from django.conf import settings
from django.contrib.gis.geos import Point, LineString, Polygon, GEOSGeometry
from django.core.files.base import ContentFile
from django.db import transaction

from .models import (
    Organization, SurveyHeader, SurveySection, Question,
    SurveySession, Answer,
    INPUT_TYPE_CHOICES, SurveySectionTranslation,
    QuestionTranslation,
)

# Format version for compatibility checking
FORMAT_VERSION = "1.0"

# Valid export modes
EXPORT_MODES = ("structure", "data", "full")

# Valid input types for validation
VALID_INPUT_TYPES = [choice[0] for choice in INPUT_TYPE_CHOICES]


class ImportError(Exception):
    """Raised when import validation or processing fails."""
    pass


class ExportError(Exception):
    """Raised when export processing fails."""
    pass


# =============================================================================
# EXPORT - Structure Serialization
# =============================================================================

def serialize_survey_to_dict(survey: SurveyHeader) -> Dict[str, Any]:
    """Convert survey header to JSON-serializable dict."""
    return {
        "name": survey.name,
        "organization": survey.organization.name if survey.organization else None,
        "redirect_url": survey.redirect_url,
        "available_languages": survey.available_languages or [],
        "sections": serialize_sections(survey),
    }


def serialize_sections(survey: SurveyHeader) -> List[Dict[str, Any]]:
    """Serialize all sections with geo WKT and questions."""
    sections = SurveySection.objects.filter(survey_header=survey)
    result = []

    for section in sections:
        result.append({
            "name": section.name,
            "title": section.title,
            "subheading": section.subheading,
            "code": section.code,
            "is_head": section.is_head,
            "start_map_position": section.start_map_postion.wkt if section.start_map_postion else None,
            "start_map_zoom": section.start_map_zoom,
            "next_section_name": section.next_section.name if section.next_section else None,
            "prev_section_name": section.prev_section.name if section.prev_section else None,
            "translations": [
                {"language": t.language, "title": t.title, "subheading": t.subheading}
                for t in section.translations.all()
            ],
            "questions": serialize_questions(section),
        })

    return result


def _serialize_question(question: Question) -> Dict[str, Any]:
    """Serialize a single question."""
    data = {
        "code": question.code,
        "order_number": question.order_number,
        "name": question.name,
        "subtext": question.subtext,
        "input_type": question.input_type,
        "choices": question.choices,
        "required": question.required,
        "color": question.color,
        "icon_class": question.icon_class,
        "image": question.image.name if question.image else None,
        "translations": [
            {"language": t.language, "name": t.name, "subtext": t.subtext}
            for t in question.translations.all()
        ],
        "sub_questions": [
            _serialize_question(sub_q)
            for sub_q in question.subQuestions()
        ],
    }
    return data


def serialize_questions(section: SurveySection) -> List[Dict[str, Any]]:
    """Serialize questions with nested sub_questions."""
    return [
        _serialize_question(question)
        for question in section.questions()
    ]


def collect_structure_images(survey: SurveyHeader) -> List[Tuple[str, str]]:
    """
    Gather all question images for export.
    Returns list of (archive_path, filesystem_path) tuples.
    """
    images = []

    for question in survey.questions():
        if question.image and question.image.name:
            original_name = os.path.basename(question.image.name)
            archive_path = f"images/structure/{question.code}_{original_name}"
            filesystem_path = question.image.path
            if os.path.exists(filesystem_path):
                images.append((archive_path, filesystem_path))

    return images


# =============================================================================
# EXPORT - Data Serialization
# =============================================================================

def serialize_sessions(survey: SurveyHeader) -> List[Dict[str, Any]]:
    """Serialize all survey sessions with their answers."""
    sessions = []

    for session in survey.sessions():
        sessions.append({
            "start_datetime": session.start_datetime.isoformat() if session.start_datetime else None,
            "end_datetime": session.end_datetime.isoformat() if session.end_datetime else None,
            "language": session.language,
            "answers": serialize_answers(session),
        })

    return sessions


def _serialize_answer(answer: Answer) -> Dict[str, Any]:
    """Serialize a single answer."""
    data = {
        "question_code": answer.question.code,
        "numeric": answer.numeric,
        "text": answer.text,
        "yn": answer.yn,
        "point": geo_to_wkt(answer.point),
        "line": geo_to_wkt(answer.line),
        "polygon": geo_to_wkt(answer.polygon),
        "choices": serialize_choices(answer),
        "sub_answers": [
            _serialize_answer(sub_a)
            for sub_a in Answer.objects.filter(parent_answer_id=answer)
        ],
    }
    return data


def serialize_answers(session: SurveySession) -> List[Dict[str, Any]]:
    """Serialize answers with nested sub_answers."""
    return [
        _serialize_answer(answer)
        for answer in session.answers()
    ]


def geo_to_wkt(geo_field) -> Optional[str]:
    """Convert geo field (point/line/polygon) to WKT string."""
    if geo_field is None:
        return None
    return geo_field.wkt


def serialize_choices(answer: Answer) -> List[str]:
    """Serialize selected choices to list of choice names."""
    return answer.get_selected_choice_names()


def collect_upload_images(survey: SurveyHeader) -> List[Tuple[str, str]]:
    """
    Gather all user-uploaded answer images for export.
    Returns list of (archive_path, filesystem_path) tuples.

    Note: Currently Answer model has no ImageField, so this returns empty.
    Kept for future extension if user uploads are added.
    """
    # Answer model currently doesn't have image uploads
    # If added in future, iterate through answers and collect files
    return []


# =============================================================================
# EXPORT - ZIP Creation
# =============================================================================

def export_survey_to_zip(
    survey: SurveyHeader,
    output: IO[bytes],
    mode: str = "structure"
) -> List[str]:
    """
    Export survey to ZIP archive.

    Args:
        survey: The survey to export
        output: File-like object to write ZIP to
        mode: One of 'structure', 'data', 'full'

    Returns:
        List of warnings generated during export
    """
    if mode not in EXPORT_MODES:
        raise ExportError(f"Invalid export mode '{mode}'. Must be one of: {', '.join(EXPORT_MODES)}")

    warnings = []

    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Export structure (survey.json + structure images)
        if mode in ("structure", "full"):
            survey_data = {
                "version": FORMAT_VERSION,
                "exported_at": datetime.utcnow().isoformat() + "Z",
                "mode": mode,
                "survey": serialize_survey_to_dict(survey),
            }
            zf.writestr("survey.json", json.dumps(survey_data, indent=2, ensure_ascii=False))

            # Add structure images
            images = collect_structure_images(survey)
            if images:
                warnings.append(
                    f"Survey contains {len(images)} image(s). "
                    "Media files are included in the archive."
                )
            for archive_path, filesystem_path in images:
                zf.write(filesystem_path, archive_path)

        # Export data (responses.json + upload images)
        if mode in ("data", "full"):
            responses_data = {
                "version": FORMAT_VERSION,
                "exported_at": datetime.utcnow().isoformat() + "Z",
                "survey_name": survey.name,
                "sessions": serialize_sessions(survey),
            }
            zf.writestr("responses.json", json.dumps(responses_data, indent=2, ensure_ascii=False))

            # Add upload images (currently empty, for future extension)
            for archive_path, filesystem_path in collect_upload_images(survey):
                zf.write(filesystem_path, archive_path)

    return warnings


# =============================================================================
# IMPORT - Validation
# =============================================================================

def validate_archive(zip_file: zipfile.ZipFile) -> Dict[str, Any]:
    """
    Validate archive structure, version, and required files.

    Returns parsed survey.json and/or responses.json content.
    Raises ImportError if validation fails.
    """
    result = {
        "has_structure": False,
        "has_data": False,
        "survey_data": None,
        "responses_data": None,
        "mode": None,
    }

    names = zip_file.namelist()

    # Check for survey.json
    if "survey.json" in names:
        try:
            content = zip_file.read("survey.json").decode("utf-8")
            data = json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ImportError(f"Invalid survey.json: {e}")

        # Validate version
        version = data.get("version")
        if version != FORMAT_VERSION:
            raise ImportError(
                f"Unsupported format version '{version}'. Supported: {FORMAT_VERSION}"
            )

        # Validate required fields
        if "survey" not in data:
            raise ImportError("Missing 'survey' field in survey.json")
        if "name" not in data["survey"]:
            raise ImportError("Missing 'survey.name' field in survey.json")

        result["has_structure"] = True
        result["survey_data"] = data
        result["mode"] = data.get("mode", "structure")

    # Check for responses.json
    if "responses.json" in names:
        try:
            content = zip_file.read("responses.json").decode("utf-8")
            data = json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ImportError(f"Invalid responses.json: {e}")

        # Validate version
        version = data.get("version")
        if version != FORMAT_VERSION:
            raise ImportError(
                f"Unsupported format version '{version}' in responses.json. Supported: {FORMAT_VERSION}"
            )

        result["has_data"] = True
        result["responses_data"] = data
        if not result["mode"]:
            result["mode"] = "data"

    # Must have at least one
    if not result["has_structure"] and not result["has_data"]:
        raise ImportError("Archive must contain survey.json and/or responses.json")

    return result


# =============================================================================
# IMPORT - Structure
# =============================================================================

def import_structure_from_archive(
    zip_file: zipfile.ZipFile,
    data: Dict[str, Any]
) -> Tuple[SurveyHeader, Dict[str, str], List[str]]:
    """
    Import survey structure from archive.

    Args:
        zip_file: The ZIP archive
        data: Parsed survey.json content

    Returns:
        Tuple of (created_survey, code_remap_table, warnings)
    """
    warnings = []
    code_remap = {}

    survey_data = data["survey"]
    legacy_option_groups = data.get("option_groups", [])

    # Create organization
    org = get_or_create_organization(survey_data.get("organization"))

    # Create survey header
    survey = create_survey_header(survey_data, org)

    # Create sections
    sections_data = survey_data.get("sections", [])
    sections = create_sections(survey, sections_data)

    # Create questions for each section
    for section_data in sections_data:
        section = sections.get(section_data["name"])
        if section:
            questions_data = section_data.get("questions", [])
            create_questions(section, questions_data, legacy_option_groups, code_remap)

    # Resolve section links
    link_warnings = resolve_section_links(sections, sections_data)
    warnings.extend(link_warnings)

    # Extract images
    image_warnings = extract_structure_images(zip_file, survey, code_remap)
    warnings.extend(image_warnings)

    return survey, code_remap, warnings


def get_or_create_organization(name: Optional[str]) -> Optional[Organization]:
    """Get existing organization by name or create new one."""
    if not name:
        return None
    org, _ = Organization.objects.get_or_create(name=name)
    return org


def convert_legacy_option_group_to_choices(
    option_group_name: str,
    legacy_option_groups: List[Dict[str, Any]]
) -> Optional[List[Dict[str, Any]]]:
    """Convert legacy option_groups format to inline choices."""
    for group in legacy_option_groups:
        if group["name"] == option_group_name:
            choices = []
            for idx, choice_data in enumerate(group.get("choices", []), start=1):
                code = choice_data.get("code", idx)
                # Build name dict with translations
                names = {"en": choice_data["name"]}
                for trans in choice_data.get("translations", []):
                    names[trans["language"]] = trans["name"]
                choices.append({"code": code, "name": names})
            return choices
    return None


def create_survey_header(
    survey_data: Dict[str, Any],
    organization: Optional[Organization]
) -> SurveyHeader:
    """Create SurveyHeader from data."""
    name = survey_data["name"]

    # Check if survey already exists
    if SurveyHeader.objects.filter(name=name).exists():
        raise ImportError(
            f"Survey '{name}' already exists. Delete it first or use a different name."
        )

    return SurveyHeader.objects.create(
        name=name[:45],
        organization=organization,
        redirect_url=survey_data.get("redirect_url", "#")[:250],
        available_languages=survey_data.get("available_languages", []),
    )


def create_sections(
    survey: SurveyHeader,
    sections_data: List[Dict[str, Any]]
) -> Dict[str, SurveySection]:
    """Create sections without next/prev links, returns name->object mapping."""
    result = {}

    for section_data in sections_data:
        # Parse geo point
        start_map_position = None
        wkt = section_data.get("start_map_position")
        if wkt:
            try:
                start_map_position = GEOSGeometry(wkt)
            except Exception as e:
                raise ImportError(
                    f"Invalid WKT for section '{section_data['name']}': {e}"
                )

        section = SurveySection.objects.create(
            survey_header=survey,
            name=section_data["name"][:45],
            title=section_data.get("title", "")[:256] if section_data.get("title") else None,
            subheading=section_data.get("subheading"),
            code=section_data.get("code", "")[:8],
            is_head=section_data.get("is_head", False),
            start_map_postion=start_map_position or Point(30.317, 59.945),
            start_map_zoom=section_data.get("start_map_zoom") or 12,
            # next_section and prev_section are resolved later
        )

        # Create section translations
        for trans_data in section_data.get("translations", []):
            SurveySectionTranslation.objects.create(
                section=section,
                language=trans_data["language"],
                title=trans_data.get("title"),
                subheading=trans_data.get("subheading"),
            )

        result[section.name] = section

    return result


def _generate_unique_code(original_code: str) -> str:
    """Generate a new unique question code."""
    import random
    while True:
        new_code = f"Q_{str(random.random())[2:12]}"
        if not Question.objects.filter(code=new_code).exists():
            return new_code


def _create_question(
    section: SurveySection,
    question_data: Dict[str, Any],
    legacy_option_groups: List[Dict[str, Any]],
    code_remap: Dict[str, str],
    parent: Optional[Question] = None
) -> Question:
    """Create a single question, handling code collisions."""
    original_code = question_data["code"]

    # Check for code collision
    if Question.objects.filter(code=original_code).exists():
        new_code = _generate_unique_code(original_code)
        code_remap[original_code] = new_code
        code = new_code
    else:
        code = original_code

    # Validate input_type
    input_type = question_data.get("input_type", "text")
    if input_type not in VALID_INPUT_TYPES:
        raise ImportError(
            f"Invalid input_type '{input_type}' for question '{original_code}'"
        )

    # Resolve choices: inline format or legacy option_group_name
    choices = question_data.get("choices")
    if choices is None:
        # Try legacy format
        og_name = question_data.get("option_group_name")
        if og_name:
            choices = convert_legacy_option_group_to_choices(og_name, legacy_option_groups)
            if choices is None:
                raise ImportError(
                    f"Question '{original_code}': option_group_name '{og_name}' not found in option_groups"
                )

    # Validate choices required for certain input types
    requires_choices = {"choice", "multichoice", "range", "rating"}
    if input_type in requires_choices and not choices:
        raise ImportError(
            f"Question '{original_code}': input_type '{input_type}' requires choices"
        )

    question = Question.objects.create(
        survey_section=section,
        parent_question_id=parent,
        code=code[:50],
        order_number=question_data.get("order_number", 0),
        name=question_data.get("name", "")[:512] if question_data.get("name") else None,
        subtext=question_data.get("subtext", "")[:512] if question_data.get("subtext") else None,
        input_type=input_type[:80],
        choices=choices,
        required=question_data.get("required", False),
        color=question_data.get("color", "#000000")[:7],
        icon_class=question_data.get("icon_class", "")[:80] if question_data.get("icon_class") else None,
        # image is handled separately during extraction
    )

    # Create question translations
    for trans_data in question_data.get("translations", []):
        QuestionTranslation.objects.create(
            question=question,
            language=trans_data["language"],
            name=trans_data.get("name"),
            subtext=trans_data.get("subtext"),
        )

    # Create sub-questions recursively
    for sub_q_data in question_data.get("sub_questions", []):
        _create_question(section, sub_q_data, legacy_option_groups, code_remap, parent=question)

    return question


def create_questions(
    section: SurveySection,
    questions_data: List[Dict[str, Any]],
    legacy_option_groups: List[Dict[str, Any]],
    code_remap: Dict[str, str]
) -> None:
    """Create questions with hierarchy, updating code_remap for collisions."""
    for question_data in questions_data:
        _create_question(section, question_data, legacy_option_groups, code_remap)


def resolve_section_links(
    sections: Dict[str, SurveySection],
    sections_data: List[Dict[str, Any]]
) -> List[str]:
    """Resolve next/prev section links by name, returns warnings."""
    warnings = []

    for section_data in sections_data:
        section_name = section_data["name"]
        section = sections.get(section_name)
        if not section:
            continue

        # Resolve next_section
        next_name = section_data.get("next_section_name")
        if next_name:
            if next_name in sections:
                section.next_section = sections[next_name]
            else:
                warnings.append(
                    f"Section '{section_name}': next_section '{next_name}' not found, set to null"
                )

        # Resolve prev_section
        prev_name = section_data.get("prev_section_name")
        if prev_name:
            if prev_name in sections:
                section.prev_section = sections[prev_name]
            else:
                warnings.append(
                    f"Section '{section_name}': prev_section '{prev_name}' not found, set to null"
                )

        section.save()

    return warnings


def extract_structure_images(
    zip_file: zipfile.ZipFile,
    survey: SurveyHeader,
    code_remap: Dict[str, str]
) -> List[str]:
    """Extract question images to MEDIA_ROOT, returns warnings."""
    warnings = []

    # Get all files in images/structure/
    image_files = [
        name for name in zip_file.namelist()
        if name.startswith("images/structure/") and not name.endswith("/")
    ]

    for image_path in image_files:
        # Parse filename: <question_code>_<original_name>
        filename = os.path.basename(image_path)
        parts = filename.split("_", 1)
        if len(parts) != 2:
            warnings.append(f"Invalid image filename format: {filename}")
            continue

        original_code, original_name = parts

        # Apply code remapping
        actual_code = code_remap.get(original_code, original_code)

        # Find the question
        try:
            question = Question.objects.get(
                code=actual_code,
                survey_section__survey_header=survey
            )
        except Question.DoesNotExist:
            warnings.append(
                f"Image '{filename}' not found in archive for question '{original_code}'"
            )
            continue

        # Extract and save image
        try:
            image_data = zip_file.read(image_path)
            # Save to question's image field
            question.image.save(original_name, ContentFile(image_data), save=True)
        except Exception as e:
            warnings.append(f"Failed to extract image '{filename}': {e}")

    return warnings


# =============================================================================
# IMPORT - Data
# =============================================================================

def import_responses_from_archive(
    zip_file: zipfile.ZipFile,
    survey: SurveyHeader,
    code_remap: Dict[str, str],
    data: Dict[str, Any]
) -> List[str]:
    """
    Import responses (sessions and answers) from archive.

    Args:
        zip_file: The ZIP archive
        survey: The target survey (existing or just created)
        code_remap: Question code remapping table
        data: Parsed responses.json content

    Returns:
        List of warnings generated during import
    """
    warnings = []

    sessions_data = data.get("sessions", [])

    for session_data in sessions_data:
        session = create_session(survey, session_data)

        for answer_data in session_data.get("answers", []):
            _, answer_warnings = create_answer(session, answer_data, code_remap)
            warnings.extend(answer_warnings)

    # Extract uploaded images (currently a stub)
    upload_warnings = extract_upload_images(zip_file, survey)
    warnings.extend(upload_warnings)

    return warnings


def create_session(
    survey: SurveyHeader,
    session_data: Dict[str, Any]
) -> SurveySession:
    """Create SurveySession from data."""
    from dateutil.parser import parse as parse_datetime

    start_dt = None
    if session_data.get("start_datetime"):
        start_dt = parse_datetime(session_data["start_datetime"])

    end_dt = None
    if session_data.get("end_datetime"):
        end_dt = parse_datetime(session_data["end_datetime"])

    return SurveySession.objects.create(
        survey=survey,
        start_datetime=start_dt or datetime.now(),
        end_datetime=end_dt,
        language=session_data.get("language"),
    )


def create_answer(
    session: SurveySession,
    answer_data: Dict[str, Any],
    code_remap: Dict[str, str],
    parent_answer: Optional[Answer] = None
) -> Tuple[Optional[Answer], List[str]]:
    """
    Create Answer from data with geo parsing and choice linking.
    Returns (answer, warnings). Answer may be None if question not found.
    """
    warnings = []

    original_code = answer_data["question_code"]
    actual_code = code_remap.get(original_code, original_code)

    # Find the question
    try:
        question = Question.objects.get(
            code=actual_code,
            survey_section__survey_header=session.survey
        )
    except Question.DoesNotExist:
        warnings.append(
            f"Answer references unknown question '{original_code}', skipped"
        )
        return None, warnings

    # Create answer
    answer = Answer.objects.create(
        survey_session=session,
        question=question,
        parent_answer_id=parent_answer,
        numeric=answer_data.get("numeric"),
        text=answer_data.get("text"),
        yn=answer_data.get("yn"),
        point=wkt_to_geo(answer_data.get("point"), "point"),
        line=wkt_to_geo(answer_data.get("line"), "line"),
        polygon=wkt_to_geo(answer_data.get("polygon"), "polygon"),
    )

    # Link choices by name -> code
    choice_names = answer_data.get("choices", [])
    choice_warnings = link_choices(answer, choice_names, question)
    warnings.extend(choice_warnings)

    # Create sub-answers recursively
    for sub_answer_data in answer_data.get("sub_answers", []):
        _, sub_warnings = create_answer(session, sub_answer_data, code_remap, answer)
        warnings.extend(sub_warnings)

    return answer, warnings


def wkt_to_geo(wkt: Optional[str], field_type: str) -> Optional[GEOSGeometry]:
    """Parse WKT string to geo field (point/line/polygon)."""
    if not wkt:
        return None
    try:
        return GEOSGeometry(wkt)
    except Exception:
        return None


def link_choices(
    answer: Answer,
    choice_names: List[str],
    question: Question
) -> List[str]:
    """Convert choice names to codes and store in answer.selected_choices."""
    warnings = []

    if not question.choices or not choice_names:
        return warnings

    # Build a name->code lookup from Question.choices
    name_to_code = {}
    for choice in question.choices:
        names = choice["name"]
        if isinstance(names, dict):
            for lang_name in names.values():
                name_to_code[lang_name] = choice["code"]
        else:
            name_to_code[names] = choice["code"]

    codes = []
    for name in choice_names:
        if name in name_to_code:
            codes.append(name_to_code[name])
        else:
            warnings.append(
                f"Choice '{name}' not found for question '{answer.question.code}', skipped"
            )

    if codes:
        answer.selected_choices = codes
        answer.save(update_fields=['selected_choices'])

    return warnings


def extract_upload_images(
    zip_file: zipfile.ZipFile,
    survey: SurveyHeader
) -> List[str]:
    """Extract user-uploaded images to MEDIA_ROOT, returns warnings."""
    # Currently Answer model has no image uploads
    # Stub for future extension
    return []


# =============================================================================
# MAIN IMPORT FUNCTION
# =============================================================================

def import_survey_from_zip(
    input_file: IO[bytes],
    mode: Optional[str] = None
) -> Tuple[Optional[SurveyHeader], List[str]]:
    """
    Import survey from ZIP archive.

    Args:
        input_file: File-like object containing ZIP data
        mode: Override mode detection (None = auto-detect from archive)

    Returns:
        Tuple of (created_survey_or_none, warnings)

    Raises:
        ImportError: If validation fails or survey already exists
    """
    warnings = []
    survey = None
    code_remap = {}

    try:
        with zipfile.ZipFile(input_file, 'r') as zf:
            # Validate archive
            archive_info = validate_archive(zf)

            has_structure = archive_info["has_structure"]
            has_data = archive_info["has_data"]
            survey_data = archive_info["survey_data"]
            responses_data = archive_info["responses_data"]

            # Data-only import requires existing survey
            if has_data and not has_structure:
                survey_name = responses_data.get("survey_name")
                if not survey_name:
                    raise ImportError("Data-only archive missing 'survey_name' field")

                try:
                    survey = SurveyHeader.objects.get(name=survey_name)
                except SurveyHeader.DoesNotExist:
                    raise ImportError(
                        f"Data-only import requires existing survey '{survey_name}'"
                    )

            # Import structure (in transaction)
            if has_structure:
                with transaction.atomic():
                    survey, code_remap, struct_warnings = import_structure_from_archive(
                        zf, survey_data
                    )
                    warnings.extend(struct_warnings)

            # Import data (in transaction)
            if has_data and survey:
                with transaction.atomic():
                    data_warnings = import_responses_from_archive(
                        zf, survey, code_remap, responses_data
                    )
                    warnings.extend(data_warnings)

    except zipfile.BadZipFile:
        raise ImportError("Invalid ZIP archive")

    return survey, warnings
