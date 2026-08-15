"""Structural gate between model output and the database.

Pure function, no I/O — every rule is checkable from the blob alone, which
makes the whole quality contract unit-testable without a provider or a
database.

This exists because a hallucinated survey does not fail loudly: the
serialization import accepts a great deal (see design D5), so a draft with
zero answerable questions, or a rating scale whose codes do not ascend, would
import cleanly and only reveal itself when respondents met it. Nothing
reaches the DB until this returns an empty list.
"""
import re

from .schema import MARKER_ICONS, SUB_QUESTION_INPUT_TYPES, TOP_LEVEL_INPUT_TYPES

GEO_INPUT_TYPES = ('point', 'line', 'polygon')
CHOICE_REQUIRED_INPUT_TYPES = ('choice', 'multichoice', 'range', 'rating')
ORDERED_CODE_INPUT_TYPES = ('range', 'rating')
MIN_SECTIONS = 2
MAX_SECTIONS = 4
MAX_SUB_QUESTIONS = 2
HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


def _check_localized(value, languages, label, errors):
    """Every localized field must carry exactly the requested language keys.

    Missing a language is not a soft fallback here: the platform silently
    falls back to the primary language at render time, so an incomplete
    translation would ship as a survey that looks multilingual and is not.
    """
    if not isinstance(value, dict):
        errors.append("%s: expected an object keyed by language code" % label)
        return
    missing = [lang for lang in languages if lang not in value]
    extra = [key for key in value if key not in languages]
    if missing:
        errors.append("%s: missing translations for %s" % (label, ", ".join(missing)))
    if extra:
        errors.append("%s: unexpected languages %s" % (label, ", ".join(extra)))


def _check_choices(question, label, errors):
    input_type = question.get('input_type')
    choices = question.get('choices') or []
    if input_type in CHOICE_REQUIRED_INPUT_TYPES:
        if not choices:
            errors.append("%s: input_type '%s' requires choices" % (label, input_type))
            return
    elif choices:
        errors.append("%s: input_type '%s' must not have choices" % (label, input_type))
        return

    codes = []
    for index, choice in enumerate(choices):
        code = choice.get('code')
        # Codes drive range/rating min-max and cross-version answer merging;
        # a string code silently breaks both.
        if not isinstance(code, int) or isinstance(code, bool):
            errors.append("%s: choice %d has a non-integer code %r" % (label, index + 1, code))
            continue
        codes.append(code)
    if len(set(codes)) != len(codes):
        errors.append("%s: choice codes must be unique" % label)
    if input_type in ORDERED_CODE_INPUT_TYPES and codes != sorted(codes):
        errors.append("%s: '%s' choice codes must ascend (they define the scale)" % (label, input_type))


def _check_question(question, languages, label, errors, allowed_types, is_sub):
    input_type = question.get('input_type')
    if input_type not in allowed_types:
        errors.append("%s: invalid input_type %r" % (label, input_type))
    _check_localized(question.get('name'), languages, "%s name" % label, errors)
    if question.get('subtext'):
        _check_localized(question.get('subtext'), languages, "%s subtext" % label, errors)
    _check_choices(question, label, errors)
    for index, choice in enumerate(question.get('choices') or []):
        _check_localized(choice.get('name'), languages, "%s choice %d" % (label, index + 1), errors)

    sub_questions = question.get('sub_questions') or []
    if is_sub:
        if sub_questions:
            errors.append("%s: sub-questions may not have their own sub-questions" % label)
        return

    # Marker styling: a geo question must be visibly styled — an unstyled black
    # marker is the "looks unfinished" tell of a generated survey. Non-geo
    # questions carry empty style fields.
    color = question.get('color') or ''
    icon = question.get('icon') or ''
    if icon == 'none':
        icon = ''
    if input_type in GEO_INPUT_TYPES:
        if not HEX_COLOR_RE.match(color):
            errors.append(
                "%s: geo question needs a 6-digit hex color like #E8590C, got %r"
                % (label, color)
            )
        if input_type == 'point' and not icon:
            errors.append("%s: a point question needs a marker icon" % label)
    if icon and icon not in MARKER_ICONS:
        errors.append("%s: unknown icon %r" % (label, icon))
    if color and not HEX_COLOR_RE.match(color):
        errors.append("%s: color must be a 6-digit hex like #2F9E44, got %r" % (label, color))
    if input_type in GEO_INPUT_TYPES and len(sub_questions) > MAX_SUB_QUESTIONS:
        errors.append(
            "%s: a geo question may have at most %d sub-questions" % (label, MAX_SUB_QUESTIONS)
        )
    for index, sub in enumerate(sub_questions):
        _check_question(
            sub, languages, "%s sub-question %d" % (label, index + 1), errors,
            SUB_QUESTION_INPUT_TYPES, True,
        )


def validate_blob(blob, requested_languages):
    """Return a list of human-readable problems; empty means the draft is usable.

    The messages are fed back to the model verbatim on the single retry, so
    they are written to be actionable by the model as well as by a developer
    reading the event log.
    """
    errors = []
    languages = list(requested_languages)
    if not languages:
        return ["no content languages were requested"]

    if not isinstance(blob, dict):
        return ["model output is not an object"]
    sections = blob.get('sections')
    if not isinstance(sections, list) or not sections:
        return ["model output has no sections"]
    if not MIN_SECTIONS <= len(sections) <= MAX_SECTIONS:
        errors.append(
            "expected between %d and %d sections, got %d"
            % (MIN_SECTIONS, MAX_SECTIONS, len(sections))
        )

    answerable = 0
    geo_questions = 0
    for section_index, section in enumerate(sections):
        section_label = "section %d" % (section_index + 1)
        if not isinstance(section, dict):
            errors.append("%s: expected an object" % section_label)
            continue
        _check_localized(section.get('title'), languages, "%s title" % section_label, errors)
        if section.get('subheading'):
            _check_localized(
                section.get('subheading'), languages, "%s subheading" % section_label, errors,
            )
        questions = section.get('questions')
        if not isinstance(questions, list) or not questions:
            errors.append("%s: has no questions" % section_label)
            continue
        for question_index, question in enumerate(questions):
            label = "%s question %d" % (section_label, question_index + 1)
            if not isinstance(question, dict):
                errors.append("%s: expected an object" % label)
                continue
            _check_question(
                question, languages, label, errors, TOP_LEVEL_INPUT_TYPES, False,
            )
            input_type = question.get('input_type')
            if input_type != 'html':
                answerable += 1
            if input_type in GEO_INPUT_TYPES:
                geo_questions += 1
            for sub in question.get('sub_questions') or []:
                if sub.get('input_type') != 'html':
                    answerable += 1

    # A draft of nothing but html blocks imports fine and collects nothing —
    # the exact "looks done but is empty" failure this gate exists for.
    if not answerable:
        errors.append("the draft has no answerable questions")
    if geo_questions > 1:
        errors.append(
            "expected at most one top-level geo question, got %d" % geo_questions
        )
    return errors
