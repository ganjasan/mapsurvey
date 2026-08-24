from django import template

register = template.Library()

STATUS_BADGE_CLASSES = {
    'draft': 'secondary',
    'testing': 'warning',
    'published': 'success',
    'closed': 'info',
    'archived': 'dark',
}


@register.filter
def status_badge_class(status):
    return STATUS_BADGE_CLASSES.get(status, 'secondary')


@register.filter
def question_missing_langs(question, survey):
    """Non-primary languages this question lacks translations for."""
    from ..translation_gaps import question_missing_languages
    return question_missing_languages(question, survey)


@register.filter
def section_missing_langs(section, survey):
    """Non-primary languages this section lacks translations for."""
    from ..translation_gaps import section_missing_languages
    return section_missing_languages(section, survey)


@register.filter
def language_name(code):
    """Human-readable language name for a survey-content language code.

    Backed by Django's locale registry rather than duplicating the 75-entry
    list in language_picker.html; the six picker codes Django's registry lacks
    are supplemented, and anything else falls back to the upper-cased code so
    the label never renders empty.
    """
    from django.utils.translation import get_language_info
    extra = {'am': 'Amharic', 'gu': 'Gujarati', 'lo': 'Lao',
             'si': 'Sinhala', 'tl': 'Filipino', 'zh': 'Chinese'}
    if code in extra:
        return extra[code]
    try:
        return get_language_info(code)['name']
    except (KeyError, TypeError):
        return (code or '').upper()


@register.filter
def cover_gradient(name):
    """Generate a deterministic gradient CSS from a string."""
    import hashlib
    h = int(hashlib.md5((name or '').encode()).hexdigest(), 16) % 360
    return f'linear-gradient(135deg, hsl({h}, 55%, 50%), hsl({(h + 40) % 360}, 45%, 40%))'


LINT_DESCRIPTIONS = {
    'self_intersection': 'Polygon has self-intersecting geometry',
    'empty_required': 'Required question was not answered',
    'out_of_range': 'Value is outside the allowed min/max range',
    'numeric_outlier': 'Value is a statistical outlier (>3σ from mean)',
    'short_text': 'Text answer is suspiciously short',
    'area_outlier': 'Polygon area is much larger or smaller than typical',
}


@register.filter
def lint_tooltip(lint_list):
    """Convert a list of lint codes to human-readable tooltip text."""
    if not lint_list:
        return ''
    return '; '.join(LINT_DESCRIPTIONS.get(code, code) for code in lint_list)


@register.filter
def input_type_label(question):
    """Presentation label for a question's type.

    The model's choice labels are storage-era names ("HTML"); the type picker
    overrides some of them for creators ("Formatted Text"). Every creator-facing
    surface must show the picker's name, or the same block gets two names.
    """
    from survey.question_types import PICKER_TYPES
    meta = PICKER_TYPES.get(question.input_type) or {}
    return meta.get('label') or question.get_input_type_display()


@register.filter
def section_next_label(section, language=None):
    """The creator's custom forward-button label for a section, translated.

    Empty/None means "use the default Next/Finish" — the template decides which.
    """
    return section.get_translated_next_label(language) or ''
