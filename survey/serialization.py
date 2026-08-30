"""
Survey import/export serialization module.

Provides functions for exporting surveys to ZIP archives and importing them back.
Supports three modes: structure, data, full.
"""
import json
import logging
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
    QuestionTranslation, default_basemaps, SurveyMapLayer,
)
from .html_sanitize import coerce_creator_html

logger = logging.getLogger(__name__)
from .question_types import CHOICE_TYPES

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
        "thanks_html": survey.thanks_html or {},
        "status": survey.status,
        "has_password": survey.has_password(),
        "version": survey.version_number,
        "basemaps": survey.basemaps or [],
        "default_basemap": survey.default_basemap,
        "start_map_position": survey.start_map_postion.wkt if survey.start_map_postion else None,
        "start_map_zoom": survey.start_map_zoom,
        "use_geolocation": survey.use_geolocation,
        "show_branding": survey.show_branding,
        "style_settings": survey.style_settings or {},
        "layers": serialize_layers(survey),
        "sections": serialize_sections(survey),
    }


def serialize_layers(survey: SurveyHeader) -> List[Dict[str, Any]]:
    """Reference-layer config, ordered. Geometry travels as separate archive
    entries (see collect_layer_files); sections reference layers by their index
    here, not by database id, so an import can remap them."""
    return [
        {
            "name": layer.name,
            "color": layer.color,
            "label_field": layer.label_field,
            "key_field": layer.key_field,
            "show_popups": layer.show_popups,
        }
        for layer in survey.map_layers.all()
    ]


def collect_layer_files(survey: SurveyHeader) -> List[Tuple[str, str]]:
    """(archive_path, geojson_text) per layer.

    Text, not a filesystem path: layers live in the database precisely so they
    are not public objects in the media bucket."""
    return [
        (f"layers/{index}.geojson", layer.geojson)
        for index, layer in enumerate(survey.map_layers.all())
    ]


def serialize_sections(survey: SurveyHeader) -> List[Dict[str, Any]]:
    """Serialize all sections with geo WKT and questions."""
    sections = SurveySection.objects.filter(survey_header=survey)
    result = []
    # Layer ids mean nothing in another database; export the position within
    # the exported `layers` array instead.
    layer_index = {layer.pk: i for i, layer in enumerate(survey.map_layers.all())}

    for section in sections:
        result.append({
            "name": section.name,
            "title": section.title,
            "subheading": section.subheading,
            "code": section.code,
            "is_head": section.is_head,
            "layout": section.layout,
            "next_label": section.next_label,
            "start_map_position": section.start_map_postion.wkt if section.start_map_postion else None,
            "start_map_zoom": section.start_map_zoom,
            "use_geolocation": section.use_geolocation,
            "override_basemap": section.override_basemap,
            "hidden_layers": sorted(
                layer_index[i] for i in (section.hidden_layers or [])
                if i in layer_index
            ),
            "next_section_name": section.next_section.name if section.next_section else None,
            "prev_section_name": section.prev_section.name if section.prev_section else None,
            "visibility_rule": section.visibility_rule,
            "translations": [
                {"language": t.language, "title": t.title, "subheading": t.subheading,
                 "next_label": t.next_label}
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
        "visibility_rule": question.visibility_rule,
        "color": question.color,
        "icon_class": question.icon_class,
        "display_style": question.display_style,
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


def collect_structure_images(survey: SurveyHeader) -> Tuple[List[Tuple[str, bytes]], List[str]]:
    """Gather all question images for export.

    Returns (images, warnings) where images is a list of (archive_path, data).

    Bytes, not a filesystem path. `question.image.path` raises
    `NotImplementedError: This backend doesn't support absolute paths` on any
    remote storage backend, so once media moved to S3 (2026-08-27) the structure
    export died for every survey that has a question image. Reading through the
    storage API works on both local disk and S3.

    An image the backend cannot open is skipped with a warning: one missing file
    must not cost the creator the whole archive.
    """
    images = []
    warnings = []

    for question in survey.questions():
        if question.image and question.image.name:
            original_name = os.path.basename(question.image.name)
            archive_path = f"images/structure/{question.code}_{original_name}"
            try:
                with question.image.open('rb') as fh:
                    images.append((archive_path, fh.read()))
            except Exception:
                warnings.append(
                    f"Image for question '{question.code}' could not be read "
                    f"({question.image.name}); it is not in the archive."
                )

    return images, warnings


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
            "validation_status": session.validation_status,
            "is_deleted": session.is_deleted,
            "tags": session.tags or [],
            "notes": session.notes or '',
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
            images, image_warnings = collect_structure_images(survey)
            if images:
                warnings.append(
                    f"Survey contains {len(images)} image(s). "
                    "Media files are included in the archive."
                )
            warnings.extend(image_warnings)
            for archive_path, data in images:
                zf.writestr(archive_path, data)

            # Reference layers: geometry written straight from the row
            for archive_path, geojson_text in collect_layer_files(survey):
                zf.writestr(archive_path, geojson_text)

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

def _archive_text(data: Dict[str, Any], key: str, default: str = "", limit: Optional[int] = None) -> str:
    """A text field out of an archive, treating an explicit null like a missing key.

    `data.get(key, default)[:limit]` reads as safe and is not: `.get`'s default
    only fires when the key is ABSENT, so a survey.json carrying
    `"redirect_url": null` hands back None and the slice raises
    `TypeError: 'NoneType' object is not subscriptable` -- a 500 on the import
    page for a creator whose only mistake was a hand-edited or foreign archive.
    That is what happened on 2026-08-23.

    An archive is content from outside this installation, so every field it
    supplies is read through here rather than trusted to be a string.
    """
    value = data.get(key)
    if value is None:
        value = default
    if not isinstance(value, str):
        value = str(value)
    return value[:limit] if limit else value


def _required_text(data: Dict[str, Any], key: str, what: str, limit: Optional[int] = None) -> str:
    """A field the import cannot invent a default for. Raises ImportError, which
    the view renders as a message, rather than letting a KeyError become a 500."""
    value = data.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ImportError(f"{what} is missing its '{key}' field")
    if not isinstance(value, str):
        value = str(value)
    return value[:limit] if limit else value


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

def _apply_visibility_rules(
    sections: Dict[str, SurveySection],
    sections_data: List[Dict[str, Any]],
    code_remap: Dict[str, str],
) -> List[str]:
    """Attach exported visibility rules to imported sections and questions.

    The controlling question is referenced by its exported code; ``code_remap``
    translates codes that collided on import. A rule whose controller or every
    referenced option code cannot be resolved is dropped with a warning — never
    imported broken, never fatal to the import.
    """
    warnings = []
    controllers = {}
    for section in sections.values():
        for question in Question.objects.filter(
            survey_section=section, parent_question_id__isnull=True
        ):
            controllers[question.code] = question

    def resolve(rule, host_label):
        if not isinstance(rule, dict):
            return None
        code = code_remap.get(rule.get("question_code"), rule.get("question_code"))
        controller = controllers.get(code)
        if controller is None:
            warnings.append(
                f"Dropped visibility rule on {host_label}: controlling question not found"
            )
            return None
        defined = {c.get("code") for c in (controller.choices or []) if isinstance(c, dict)}
        codes = [c for c in (rule.get("choice_codes") or []) if c in defined]
        if not codes:
            warnings.append(
                f"Dropped visibility rule on {host_label}: no referenced answer option exists"
            )
            return None
        return {"question_code": code, "choice_codes": codes}

    for section_data in sections_data:
        section = sections.get(section_data["name"])
        if section is None:
            continue
        section_rule = resolve(
            section_data.get("visibility_rule"), f"section '{section.name}'"
        )
        if section_rule:
            section.visibility_rule = section_rule
            section.save(update_fields=["visibility_rule"])
        for question_data in section_data.get("questions", []):
            rule = question_data.get("visibility_rule")
            if not isinstance(rule, dict):
                continue
            q_code = code_remap.get(question_data["code"], question_data["code"])
            question = controllers.get(q_code)
            if question is None:
                continue
            resolved = resolve(rule, f"question '{question.name or q_code}'")
            if resolved:
                question.visibility_rule = resolved
                question.save(update_fields=["visibility_rule"])
    return warnings


def import_structure_from_archive(
    zip_file: zipfile.ZipFile,
    data: Dict[str, Any],
    organization: Optional[Organization] = None,
    created_by=None,
) -> Tuple[SurveyHeader, Dict[str, str], List[str]]:
    """
    Import survey structure from archive.

    Args:
        zip_file: The ZIP archive
        data: Parsed survey.json content
        organization: Override organization (from active org context)
        created_by: User who initiated the import

    Returns:
        Tuple of (created_survey, code_remap_table, warnings)
    """
    warnings = []
    code_remap = {}

    survey_data = data["survey"]
    legacy_option_groups = data.get("option_groups", [])

    # Use provided organization or fall back to archive data
    if organization is None:
        org = get_or_create_organization(survey_data.get("organization"))
    else:
        org = organization

    # Create survey header
    survey = create_survey_header(survey_data, org, created_by=created_by)

    # Create reference layers before sections: a section's hidden_layers holds
    # indexes into the exported layers array and needs the new ids to remap.
    layer_ids, layer_warnings = extract_layers(zip_file, survey, survey_data.get("layers") or [])
    warnings.extend(layer_warnings)

    # Create sections
    sections_data = survey_data.get("sections", [])
    sections = create_sections(survey, sections_data, layer_ids)

    # Create questions for each section
    for section_data in sections_data:
        section = sections.get(section_data["name"])
        if section:
            questions_data = section_data.get("questions", [])
            create_questions(section, questions_data, legacy_option_groups, code_remap)

    # Apply visibility rules once every question exists (a rule's controller is
    # earlier in survey order, but a post-pass is immune to creation order and
    # lets an unresolvable rule become one report line instead of a half-rule).
    rule_warnings = _apply_visibility_rules(sections, sections_data, code_remap)
    warnings.extend(rule_warnings)

    # Resolve section links
    link_warnings = resolve_section_links(sections, sections_data)
    warnings.extend(link_warnings)

    # Extract images
    image_warnings = extract_structure_images(zip_file, survey, code_remap)
    warnings.extend(image_warnings)

    return survey, code_remap, warnings


def get_or_create_organization(name: Optional[str]) -> Organization:
    """Get existing organization by name or create new one.

    If name is None/empty, creates or gets a default 'Imported' organization.
    """
    if not name:
        name = 'Imported'
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
    organization: Optional[Organization],
    created_by=None,
) -> SurveyHeader:
    """Create SurveyHeader from data.

    Reads status from data (defaults to 'draft').
    Never imports password_hash or test_token for security.
    """
    name = _required_text(survey_data, "name", "The survey", limit=45)

    return SurveyHeader.objects.create(
        name=name,
        organization=organization,
        created_by=created_by,
        redirect_url=_archive_text(survey_data, "redirect_url", "#", 250),
        available_languages=survey_data.get("available_languages", []),
        thanks_html=survey_data.get("thanks_html", {}),
        status=survey_data.get("status", "draft"),
        version_number=survey_data.get("version", 1),
        basemaps=survey_data.get("basemaps", default_basemaps()),
        default_basemap=survey_data.get("default_basemap"),
        start_map_postion=GEOSGeometry(survey_data["start_map_position"]) if survey_data.get("start_map_position") else None,
        start_map_zoom=survey_data.get("start_map_zoom"),
        use_geolocation=survey_data.get("use_geolocation", False),
        show_branding=survey_data.get("show_branding", True),
        style_settings=_clean_style_settings(survey_data.get("style_settings")),
        is_canonical=True,
    )


def _clean_style_settings(value):
    """Keep only known style keys with valid values; anything else is dropped."""
    import re as re_module
    if not isinstance(value, dict):
        return {}
    cleaned = {}
    if value.get("rating_display_style") in ("scale_strip", "list_pips"):
        cleaned["rating_display_style"] = value["rating_display_style"]
    accent = value.get("accent_color")
    if isinstance(accent, str) and re_module.fullmatch(r"#[0-9a-fA-F]{6}", accent):
        cleaned["accent_color"] = accent
    return cleaned


def create_sections(
    survey: SurveyHeader,
    sections_data: List[Dict[str, Any]],
    layer_ids: Optional[List[int]] = None,
) -> Dict[str, SurveySection]:
    """Create sections without next/prev links, returns name->object mapping.

    layer_ids maps an exported layer's position to the id it got on import; an
    index with no id (a layer that failed to import) simply drops out, leaving
    that layer visible rather than referencing a row that does not exist.
    """
    layer_ids = layer_ids or []
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
            name=_required_text(section_data, "name", "A section", limit=45),
            title=_archive_text(section_data, "title", "", 256) or None,
            subheading=_import_rich_text(section_data.get("subheading")),
            code=_archive_text(section_data, "code", "", 8),
            is_head=section_data.get("is_head", False),
            layout=section_data.get("layout") if section_data.get("layout") in ("map", "form") else "map",
            next_label=(section_data.get("next_label") or None) and str(section_data.get("next_label"))[:30],
            start_map_postion=start_map_position,
            start_map_zoom=section_data.get("start_map_zoom"),
            use_geolocation=section_data.get("use_geolocation", False),
            override_basemap=section_data.get("override_basemap"),
            hidden_layers=[
                layer_ids[i] for i in (section_data.get("hidden_layers") or [])
                if isinstance(i, int) and 0 <= i < len(layer_ids) and layer_ids[i] is not None
            ],
            # next_section and prev_section are resolved later
        )

        # Create section translations
        for trans_data in section_data.get("translations", []):
            SurveySectionTranslation.objects.create(
                section=section,
                language=trans_data["language"],
                title=trans_data.get("title"),
                subheading=_import_rich_text(trans_data.get("subheading")),
                next_label=(trans_data.get("next_label") or None) and str(trans_data.get("next_label"))[:30],
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


def _import_rich_text(raw: Optional[str]) -> Optional[str]:
    """Creator rich text from an imported ZIP, ready to store.

    Subtext and subheading render `|safe`, and a ZIP is content from outside this
    installation — including archives exported before these fields held markup,
    whose plain text has to be escaped rather than sanitized.
    """
    if not raw:
        return None
    return coerce_creator_html(raw) or None


def _create_question(
    section: SurveySection,
    question_data: Dict[str, Any],
    legacy_option_groups: List[Dict[str, Any]],
    code_remap: Dict[str, str],
    parent: Optional[Question] = None
) -> Question:
    """Create a single question, handling code collisions."""
    original_code = _required_text(question_data, "code", "A question")

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
    # A non-choice type must not import a choices list: a poisoned export
    # (geo question with leftover choices) would otherwise recreate the state
    # the editor and migration 0060 clean up.
    if input_type not in CHOICE_TYPES:
        choices = None

    display_style = question_data.get("display_style")
    allowed_styles = (
        ("default", "dropdown") if input_type == "choice"
        else ("default", "scale_strip", "list_pips")
    )
    if display_style not in allowed_styles:
        display_style = "default"

    question = Question.objects.create(
        survey_section=section,
        parent_question_id=parent,
        code=code[:50],
        order_number=question_data.get("order_number", 0),
        name=question_data.get("name", "")[:512] if question_data.get("name") else None,
        # Not truncated: for a Formatted Text block the subtext is the block's
        # whole body. Sanitized for that type because it renders |safe, and an
        # imported ZIP is content from outside this installation.
        subtext=_import_rich_text(question_data.get("subtext")),
        input_type=input_type[:80],
        choices=choices,
        required=question_data.get("required", False),
        color=_archive_text(question_data, "color", "#000000", 7),
        icon_class=_archive_text(question_data, "icon_class", "", 80) or None,
        display_style=display_style,
        # image is handled separately during extraction
    )

    # Create question translations
    for trans_data in question_data.get("translations", []):
        QuestionTranslation.objects.create(
            question=question,
            language=trans_data["language"],
            name=trans_data.get("name"),
            subtext=_import_rich_text(trans_data.get("subtext")),
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


def _clean_layer_config(cfg: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Whitelist a layer's config from an archive — same posture as
    _clean_style_settings: unknown keys dropped, bad values replaced."""
    import re as re_module
    name = cfg.get("name")
    name = str(name)[:100] if isinstance(name, str) and name.strip() else f"Layer {index + 1}"
    color = cfg.get("color")
    if not (isinstance(color, str) and re_module.fullmatch(r"#[0-9a-fA-F]{6}", color)):
        color = "#2c7be5"
    out = {"name": name, "color": color, "show_popups": bool(cfg.get("show_popups"))}
    for field in ("label_field", "key_field"):
        value = cfg.get(field)
        out[field] = str(value)[:100] if isinstance(value, str) else ""
    return out


def extract_layers(
    zip_file: zipfile.ZipFile,
    survey: SurveyHeader,
    layers_data: List[Dict[str, Any]],
) -> Tuple[List[Optional[int]], List[str]]:
    """Recreate reference layers from the archive.

    Geometry goes through the same validation as an interactive upload, so a
    hand-edited or AI-written archive cannot store something the editor would
    have refused. A missing or invalid entry is a warning that skips one layer,
    never a failed import — the survey itself is still worth having.
    """
    from .layers import validate_layer_upload, LayerValidationError, MAX_LAYERS_PER_SURVEY

    ids: List[Optional[int]] = []
    warnings: List[str] = []
    if not isinstance(layers_data, list):
        return ids, warnings

    for index, cfg in enumerate(layers_data):
        if len(ids) >= MAX_LAYERS_PER_SURVEY:
            warnings.append(
                f"Archive holds more than {MAX_LAYERS_PER_SURVEY} reference layers; the rest were skipped."
            )
            break
        if not isinstance(cfg, dict):
            ids.append(None)
            continue
        clean = _clean_layer_config(cfg, index)
        archive_path = f"layers/{index}.geojson"
        try:
            raw = zip_file.read(archive_path)
        except KeyError:
            ids.append(None)
            warnings.append(f"Reference layer '{clean['name']}' is missing '{archive_path}' — layer skipped.")
            continue
        try:
            geojson_str, count, _ = validate_layer_upload(raw)
        except LayerValidationError as exc:
            ids.append(None)
            warnings.append(f"Reference layer '{clean['name']}' was skipped: {exc}")
            continue
        layer = SurveyMapLayer.objects.create(
            survey=survey, geojson=geojson_str, feature_count=count,
            size_bytes=len(geojson_str.encode("utf-8")), position=index, **clean,
        )
        ids.append(layer.pk)

    return ids, warnings


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
    mode: Optional[str] = None,
    organization: Optional[Organization] = None,
    created_by=None,
) -> Tuple[Optional[SurveyHeader], List[str]]:
    """
    Import survey from ZIP archive.

    Args:
        input_file: File-like object containing ZIP data
        mode: Override mode detection (None = auto-detect from archive)
        organization: Override organization (from active org context)
        created_by: User who initiated the import

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

                matches = SurveyHeader.objects.filter(name=survey_name)
                count = matches.count()
                if count == 0:
                    raise ImportError(
                        f"Data-only import requires existing survey '{survey_name}'"
                    )
                if count > 1:
                    raise ImportError(
                        f"Multiple surveys found with name '{survey_name}'. "
                        f"Data-only import requires an unambiguous match."
                    )
                survey = matches.first()

            # Warn if exported survey had password protection
            if has_structure and survey_data.get("survey", {}).get("has_password"):
                warnings.append(
                    "Survey had password protection in export. "
                    "Password not imported for security — set new password in editor."
                )

            # Import structure (in transaction)
            if has_structure:
                with transaction.atomic():
                    survey, code_remap, struct_warnings = import_structure_from_archive(
                        zf, survey_data,
                        organization=organization,
                        created_by=created_by,
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
    except ImportError:
        raise
    except (TypeError, KeyError, IndexError, AttributeError, ValueError) as exc:
        # An archive is data from outside this installation, and its fields
        # cannot all be enumerated -- a hand-edited or foreign survey.json can
        # null out or retype anything. The shape errors that produces are the
        # creator's file being wrong, not our logic, and they must not surface
        # as a 500 on the import page. Logged so a genuine bug hiding in here
        # still leaves a trail in the request log.
        logger.exception("Malformed survey archive rejected during import")
        raise ImportError(
            f"The archive could not be read: {type(exc).__name__}: {exc}. "
            "It may be edited, truncated, or produced by a different tool."
        )

    return survey, warnings
