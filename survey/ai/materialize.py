"""Turn a validated draft into real survey rows.

Two rules shape this module.

1. Structural fields are computed here, never taken from the model. Section
   codes, `is_head`, the next/prev linked list, question codes and
   `order_number` all follow from list order. The serialization import treats
   a missing `is_head` or a dangling `next_section_name` as a warning, not an
   error, so a survey would import "successfully" and then be unable to
   publish or unable to navigate. Generating them ourselves makes those
   states unreachable.

2. Everything is written through `import_survey_from_zip`. That path is the
   one place in the codebase that knows how to build the full object graph,
   it is already covered by the import test suite, and it wraps the work in a
   transaction. Re-implementing it here would mean re-implementing its
   validation too.
"""
import io
import json
import zipfile

from django.contrib.gis.geos import Point

from ..models import question_code_generator
from ..serialization import FORMAT_VERSION, import_survey_from_zip


def _translations(languages, keys):
    """Convert {lang: text} dicts into the import format's translation rows.

    `keys` maps the import field name to the localized dict, e.g.
    {'title': {...}, 'subheading': {...}} — every requested language gets a
    row, including the primary one, matching what the editor writes when a
    creator adds translations by hand.
    """
    rows = []
    for language in languages:
        row = {"language": language}
        for field, values in keys.items():
            row[field] = (values or {}).get(language) or None
        rows.append(row)
    return rows


def _question_dict(question, languages, primary, order_number):
    localized_name = question.get('name') or {}
    localized_subtext = question.get('subtext') or {}
    icon = question.get('icon') or ''
    if icon == 'none':
        icon = ''
    data = {
        "code": question_code_generator(),
        "order_number": order_number,
        "name": localized_name.get(primary) or '',
        "subtext": localized_subtext.get(primary) or None,
        "input_type": question.get('input_type'),
        "choices": question.get('choices') or None,
        "required": bool(question.get('required')),
        # The model emits a bare curated icon name; the FA prefix is ours so a
        # hallucinated "fab"/"far" variant can never reach the widget.
        "color": question.get('color') or '#000000',
        "icon_class": ('fas fa-%s' % icon) if icon else None,
        "translations": _translations(
            languages, {"name": localized_name, "subtext": localized_subtext},
        ),
        "sub_questions": [
            _question_dict(sub, languages, primary, index + 1)
            for index, sub in enumerate(question.get('sub_questions') or [])
        ],
    }
    return data


def build_envelope(blob, header_overrides, languages):
    """Compose the `survey.json` payload the import path consumes."""
    primary = languages[0]
    sections = blob.get('sections') or []
    section_names = ["section_%d" % (index + 1) for index in range(len(sections))]

    section_dicts = []
    for index, section in enumerate(sections):
        localized_title = section.get('title') or {}
        localized_subheading = section.get('subheading') or {}
        section_dicts.append({
            "name": section_names[index],
            "title": localized_title.get(primary) or '',
            "subheading": localized_subheading.get(primary) or None,
            "code": "S%d" % (index + 1),
            # Exactly one head, always the first section: the survey cannot
            # leave draft status without it.
            "is_head": index == 0,
            "next_section_name": section_names[index + 1] if index + 1 < len(sections) else None,
            "prev_section_name": section_names[index - 1] if index > 0 else None,
            "translations": _translations(
                languages,
                {"title": localized_title, "subheading": localized_subheading},
            ),
            "questions": [
                _question_dict(question, languages, primary, q_index + 1)
                for q_index, question in enumerate(section.get('questions') or [])
            ],
        })

    survey = dict(header_overrides)
    survey["available_languages"] = languages
    survey["sections"] = section_dicts
    return {"version": FORMAT_VERSION, "survey": survey}


def header_overrides_from_form(name, languages, map_lat, map_lng, map_zoom, default_basemap):
    """Header fields come from the creator's form, never from the model.

    The map position is what the creator framed on the Leaflet picker — the
    same hidden fields the manual create path reads.
    """
    overrides = {
        "name": name,
        "available_languages": list(languages),
        "status": "draft",
    }
    if map_lat and map_lng:
        overrides["start_map_position"] = Point(float(map_lng), float(map_lat)).wkt
    if map_zoom:
        overrides["start_map_zoom"] = int(map_zoom)
    if default_basemap:
        overrides["default_basemap"] = default_basemap
    return overrides


def materialize_draft(blob, header_overrides, languages, organization, created_by):
    """Create the survey graph; returns (survey, warnings).

    Raises `serialization.ImportError` if the import path rejects the payload
    — a backstop that should never fire, since the validator runs first.
    """
    envelope = build_envelope(blob, header_overrides, languages)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            'survey.json', json.dumps(envelope, indent=2, ensure_ascii=False),
        )
    buffer.seek(0)
    return import_survey_from_zip(
        buffer, organization=organization, created_by=created_by,
    )
