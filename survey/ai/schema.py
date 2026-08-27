"""JSON schema for the model's survey-draft output.

Marker styling (`color`, `icon`) is part of the schema because the map is the
product: an AI draft whose every marker is default-black reads as unfinished,
and the creator has no reason to know the fields exist. The icon is an ENUM of
Font Awesome 5 names we know render — a free-text field here would let the
model hallucinate classes that silently draw nothing.

Content only, on purpose: structural/positional fields (`code`, `is_head`,
`next/prev_section_name`, `order_number`) do NOT exist in this schema — the
materializer computes them from list order (design D3), which eliminates the
serialization import's silent gotchas by construction instead of detecting
them after the fact.

The schema is built per request because localized text is an object with one
property per requested language code — structured outputs require
`additionalProperties: false` everywhere, so dynamic keys are impossible and
the explicit per-language properties double as a completeness constraint the
model must satisfy.

Constraints the schema cannot express (integer-code uniqueness, ascending
range/rating codes, section count, one-geo-question policy) live in
`validator.py` — the schema keeps the shape honest, the validator keeps the
content honest.

Sub-questions are a separate, non-recursive type: structured outputs forbid
recursive schemas, and the editor UI only exposes one nesting level anyway.
"""
from typing import Dict, List

from ..editor_forms import SUBQUESTION_DISALLOWED_INPUT_TYPES
from ..serialization import VALID_INPUT_TYPES

# 'html' is a decoration block, not an answerable question; the validator
# additionally requires at least one non-html question in the draft.
# `image` is a display block the model has no business generating (it would
# need an image nobody uploaded). The file types ARE generatable — the prompt
# below teaches when a photo/audio/document question helps. If the
# FILE_UPLOAD_QUESTIONS kill switch is ever off, a generated file question
# renders as nothing for respondents (fail open) — a degraded draft, not a
# broken one.
TOP_LEVEL_INPUT_TYPES = [t for t in VALID_INPUT_TYPES if t != 'image']
SUB_QUESTION_INPUT_TYPES = [
    t for t in TOP_LEVEL_INPUT_TYPES if t not in SUBQUESTION_DISALLOWED_INPUT_TYPES
]

# Bare FA5 free-solid names; the materializer prefixes "fas fa-". Curated for
# the participatory-mapping domain — the model picks from these, never invents.
MARKER_ICONS = [
    "map-marker-alt", "tree", "leaf", "seedling", "water", "tint", "sun",
    "snowflake", "temperature-high", "car", "bicycle", "walking", "bus",
    "train", "parking", "road", "traffic-light", "exclamation-triangle",
    "heart", "home", "building", "store", "school", "hospital", "wheelchair",
    "lightbulb", "trash", "volume-up", "paw", "child", "chair", "umbrella-beach",
]


def _localized_text(languages):
    # type: (List[str]) -> Dict
    return {
        "type": "object",
        "properties": {lang: {"type": "string"} for lang in languages},
        "required": list(languages),
        "additionalProperties": False,
    }


def _choice(languages):
    # type: (List[str]) -> Dict
    return {
        "type": "object",
        "properties": {
            "code": {"type": "integer"},
            "name": _localized_text(languages),
        },
        "required": ["code", "name"],
        "additionalProperties": False,
    }


def _question(languages, input_types, with_sub_questions):
    # type: (List[str], List[str], bool) -> Dict
    properties = {
        "name": _localized_text(languages),
        "subtext": _localized_text(languages),
        "input_type": {"type": "string", "enum": list(input_types)},
        "required": {"type": "boolean"},
        "choices": {"type": "array", "items": _choice(languages)},
    }
    # Every property is listed in `required`: strict structured outputs treat
    # optional keys poorly, so "no subtext" is an empty string, not a missing
    # key, and "no choices" is an empty list.
    required = ["name", "subtext", "input_type", "required", "choices"]
    if with_sub_questions:
        # Styling is a top-level concern: sub-questions render inside the
        # feature popup and have no marker of their own.
        properties["color"] = {
            "type": "string",
            "description": "Marker/geometry colour as a 6-digit hex like #E8590C. "
                           "Empty string for non-geo questions.",
        }
        # "none" rather than "": at least one provider (Gemini) rejects an
        # empty string as an enum member.
        properties["icon"] = {"type": "string", "enum": ["none"] + MARKER_ICONS}
        required.extend(["color", "icon"])
        properties["sub_questions"] = {
            "type": "array",
            "items": _question(languages, SUB_QUESTION_INPUT_TYPES, False),
        }
        required.append("sub_questions")
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def survey_draft_schema(languages):
    # type: (List[str]) -> Dict
    """The full response schema for one generation call."""
    section = {
        "type": "object",
        "properties": {
            "title": _localized_text(languages),
            "subheading": _localized_text(languages),
            "questions": {
                "type": "array",
                "items": _question(languages, TOP_LEVEL_INPUT_TYPES, True),
            },
        },
        "required": ["title", "subheading", "questions"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "sections": {"type": "array", "items": section},
        },
        "required": ["sections"],
        "additionalProperties": False,
    }
