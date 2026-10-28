"""Pieces every service module shares: the "leave it alone" marker, binding
the editor's forms to plain data, visibility rules, translations and the
answer-loss guard."""
from django.conf import settings

from ..html_sanitize import coerce_creator_html
from ..models import SurveyHeader
from .errors import AnswersAtRisk, ValidationFailed


class _Unset:
    def __repr__(self):
        return 'UNSET'

    def __bool__(self):
        return False


# An argument left at UNSET means "do not touch this"; None means "clear it".
UNSET = _Unset()


# ─── Forms as validators ─────────────────────────────────────────────────────

def form_data_from_instance(form):
    """The data an UNBOUND form would post back unchanged: each field's initial
    value in the shape `value_from_datadict` reads (a checkbox that is off is
    absent, a multi-value field is a list)."""
    from django import forms as dj_forms
    data = {}
    for name, field in form.fields.items():
        if field.disabled:
            continue
        value = form[name].value()
        widget = field.widget
        if isinstance(widget, dj_forms.CheckboxInput):
            if value:
                data[name] = 'on'
            continue
        if isinstance(widget, dj_forms.ClearableFileInput) or isinstance(field, dj_forms.FileField):
            continue
        if value is None:
            continue
        if isinstance(widget, dj_forms.widgets.ChoiceWidget):
            if widget.allow_multiple_selected:
                data[name] = [str(v) for v in (value or [])]
            else:
                data[name] = str(value)
            continue
        if isinstance(value, (list, tuple)):
            data[name] = [str(v) for v in value]
            continue
        formatted = widget.format_value(value)
        data[name] = '' if formatted is None else formatted
    return data


def bind(form_class, data, files=None, *, instance=None, partial=False, **kwargs):
    """Bind `form_class` to `data`. With `partial`, fields `data` does not name
    keep the instance's current values -- the PATCH semantics the API needs on
    top of forms written for full posts."""
    if partial and instance is not None:
        base = form_data_from_instance(form_class(instance=instance, **kwargs))
        base.update(data)
        data = base
    return form_class(data, files, instance=instance, **kwargs)


def locked_changes(form, data, labels):
    """Reasons a strict caller's `data` tries to change a field the form
    locks on a live survey (`disabled`). The editor relies on "the stored
    value wins whatever is posted"; a programmatic client is told instead."""
    reasons = []
    for name, label in labels.items():
        field = form.fields.get(name)
        if field is None or not field.disabled or name not in data:
            continue
        current = form.initial.get(name)
        current = getattr(current, 'pk', current)
        if str(data.get(name) or '') != str(current if current is not None else ''):
            reasons.append(label)
    return reasons


def validate(form):
    """Raise ValidationFailed carrying the form unless it is valid."""
    if not form.is_valid():
        raise ValidationFailed(form.errors, form=form)
    return form


# ─── Visibility rules ────────────────────────────────────────────────────────

def parse_visibility(mode, question_code='', match='any_of', choice_codes=()):
    """The editor's Visibility block, as values: (present, rule) or
    ValidationFailed. `mode` None = the block was not posted (kill switch off,
    stale form) -- leave the stored rule untouched. Mode 'always' clears the
    rule; 'conditional' needs a controller and, for match 'any_of', at least
    one option code; match 'answered' (#339) needs no codes."""
    if not getattr(settings, 'CONDITIONAL_VISIBILITY', False):
        return False, None
    if mode is None:
        return False, None
    if mode != 'conditional':
        return True, None
    code = (question_code or '').strip()
    if (match or 'any_of') == 'answered':
        if not code:
            raise ValidationFailed.single('visibility', 'Pick a controlling question.')
        return True, {'question_code': code, 'answered': True}
    codes = []
    for raw in choice_codes or ():
        try:
            codes.append(int(raw))
        except (TypeError, ValueError):
            continue
    if not code or not codes:
        raise ValidationFailed.single(
            'visibility', 'Pick a controlling question and at least one of its answers.')
    return True, {'question_code': code, 'choice_codes': codes}


def check_rule(rule, host_kind, strict, **where):
    """Strict callers (the API) get the reason a rule would be broken as a
    ValidationFailed on `visibility_rule`; the editor keeps fail-open."""
    if not strict or rule is None:
        return
    from ..visibility import validate_rule
    reason = validate_rule(rule, host_kind, **where)
    if reason:
        raise ValidationFailed.single('visibility_rule', reason)


# ─── Translations ────────────────────────────────────────────────────────────

def translation_languages(survey):
    """Languages that carry translation rows: everything after the primary.

    The first entry of available_languages is the survey's primary language;
    its content lives in base model fields only. Iterating this instead of the
    full list is also what makes stale translation_<primary>_* keys (old open
    forms) a no-op instead of a resurrected duplicate row.
    """
    return (survey.available_languages or [])[1:]


def save_translations(model, owner_field, owner, survey, translations, fields, rich=(), caps=None,
                      record_all=()):
    """Write one translation row per non-primary language from
    `translations = {lang: {field: value}}`.

    A language whose values are all blank loses its row. A language missing
    from `translations` is left alone, so a partial update (the API) touches
    only what it names; the editor passes every language, as its form posts
    every language. Rich-text fields pass `coerce_creator_html`.

    The source hash (change translation-table) is recorded for every field
    whose value changed, and for the fields in `record_all` whatever their
    value — a save from the Translations tab is a review of the text as it is.
    """
    from .. import translation_table
    caps = caps or {}
    prefix = None
    for lang in translation_languages(survey):
        if lang not in translations:
            continue
        values = translations[lang] or {}
        cleaned = {}
        for field in fields:
            raw = values.get(field) or ''
            value = coerce_creator_html(raw).strip() if field in rich else str(raw).strip()
            if field in caps:
                value = value[:caps[field]]
            cleaned[field] = value
        existing = model.objects.filter(**{owner_field: owner, 'language': lang}).first()
        if any(cleaned.values()):
            model.objects.update_or_create(
                **{owner_field: owner, 'language': lang},
                defaults={k: (v or None) for k, v in cleaned.items()},
            )
        else:
            model.objects.filter(**{owner_field: owner, 'language': lang}).delete()
        changed = [
            f for f in fields
            if f in record_all or cleaned[f] != ((getattr(existing, f, None) or '') if existing else '')
        ]
        if changed:
            if prefix is None:
                prefix = translation_table.prefix_for(owner_field, owner)
            translation_table.record_hashes(survey, lang, [
                (f'{prefix}:{f}', getattr(owner, f, None) or '',
                 translation_table.RICH if f in rich else translation_table.PLAIN, cleaned[f])
                for f in changed
            ])


def translations_from_post(post, survey, fields):
    """`{lang: {field: value}}` from the editor's `translation_<lang>_<field>` keys."""
    return {
        lang: {field: post.get(f'translation_{lang}_{field}', '') for field in fields}
        for lang in translation_languages(survey)
    }


# ─── Answer loss ─────────────────────────────────────────────────────────────

def survey_is_unversioned(survey):
    """True when this survey has no archived versions to fall back on.

    Publishing moves the previous structure and its sessions onto an archived
    header rather than deleting them, so a survey that has been published keeps
    its earlier answers. One that never has does not -- there is nowhere for
    them to go.
    """
    if survey.is_draft_copy:
        return False
    return survey.version_number == 1 and not SurveyHeader.objects.filter(
        canonical_survey=survey, is_canonical=False,
    ).exists()


def guard_answer_loss(survey, answer_count, acknowledged):
    """Raise AnswersAtRisk unless the caller acknowledged losing `answer_count`
    answers. Counted in the same request that deletes, never earlier: a number
    that goes stale teaches the author to disbelieve it."""
    if answer_count and not acknowledged:
        raise AnswersAtRisk(answer_count, explain_versioning=survey_is_unversioned(survey))


def surface_props(actor):
    """Product events from the editor keep their old properties; every other
    surface is named, so API and MCP use can be told apart."""
    return {} if actor.surface == 'editor' else {'surface': actor.surface}
