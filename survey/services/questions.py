"""Questions: create (top level and pop-up), edit, choices, delete, order.

Input speaks the editor's dialect -- `QuestionForm` field names plus the
modal's auxiliary keys (`choices_json`, `vs_*`, `sm_*`, `layer=answers:<code>`)
-- because that is the dialect `QuestionForm` validates and every rule below
was written for. The API translates its JSON into it (`api/v1/forms_bridge.py`)
rather than growing a second parser.
"""
import json

from django.db import models, transaction
from django.utils.html import strip_tags

from .. import other_option
from .. import product_events as pe
from ..editor_forms import QuestionForm
from ..groups import max_order as group_max_order, place_in_group
from ..html_sanitize import coerce_creator_html
from ..layers import (
    GEOMETRY_TEXT_FIELDS, backfill_question_layer, layer_lite, layer_owner,
)
from ..models import Answer, Question, QuestionTranslation, SurveyMapLayer
from ..question_types import CHOICE_TYPES, MULTI_FEATURE_TYPES, SHARED_MAP_SOURCE_TYPES, normalise_choice_extras
from ..versioning import (
    family_ids, question_snapshot, removed_answered_choices, structural_edit_message,
    structural_question_changes,
)
from . import locks
from .common import (
    UNSET, bind, check_rule, guard_answer_loss, locked_changes, parse_visibility,
    save_translations, surface_props,
)
from .errors import DeleteBlocked, StructureLocked, ValidationFailed

TRANSLATION_FIELDS = ('name', 'subtext')
FILE_TYPES = ('photo', 'audio', 'document')
SETTINGS_ON_CREATE = frozenset(MULTI_FEATURE_TYPES) | {'number', 'range', 'text', 'text_line', 'spraycan'}


class Stage:
    """Where a ValidationFailed came from, so the editor can answer each the
    way it always has (modal re-render, 422 JSON, 400)."""
    FORM = 'form'
    CHOICES = 'choices'
    SETTINGS = 'validation_settings'
    VISIBILITY = 'visibility'


def _failed(stage, fields, form=None, message=''):
    err = ValidationFailed(fields, form=form, message=message)
    err.stage = stage
    return err


# ─── Choices ─────────────────────────────────────────────────────────────────

def guard_choice_codes(question, new_choices):
    """Prevent silently rebinding a historically answered choice code.

    Cross-version analytics merges choice answers by code, so a code that
    family answers used but that is absent from the question's current set
    must never be handed to a NEW choice -- the old and new meanings would
    silently merge. Offending new entries get a fresh code above everything
    ever used in the lineage. Existing codes stay untouched (renaming an
    existing choice is a normal compatible edit).

    Every save of a choice list passes here, so this is also where the icon
    grid's optional `icon`/`group`/`color` keys are trimmed and capped.
    """
    if isinstance(new_choices, list):
        normalise_choice_extras(new_choices)
    if not isinstance(new_choices, list) or not question.code:
        return other_option.clamp_single_other(new_choices)

    old_codes = {c.get('code') for c in (question.choices or []) if isinstance(c, dict)}

    answered = set()
    lineage_selected = (
        Answer.objects
        .filter(
            question__code=question.code,
            question__input_type=question.input_type,
            question__survey_section__survey_header_id__in=family_ids(
                question.survey_section.survey_header
            ),
        )
        .exclude(selected_choices__isnull=True)
        .values_list('selected_choices', flat=True)
    )
    for selected in lineage_selected:
        answered.update(selected or [])
    if not answered:
        return other_option.clamp_single_other(new_choices)

    all_known = answered | old_codes | {
        c.get('code') for c in new_choices if isinstance(c, dict)
    }
    numeric = [c for c in all_known if isinstance(c, int)]
    next_code = (max(numeric) + 1) if numeric else 1

    for choice in new_choices:
        if not isinstance(choice, dict):
            continue
        code = choice.get('code')
        if code in answered and code not in old_codes:
            choice['code'] = next_code
            next_code += 1
    return other_option.clamp_single_other(new_choices)


def _parse_choices_json(raw, form=None):
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        raise _failed(Stage.CHOICES, {'choices': ['Choices must be valid JSON.']}, form)
    if not isinstance(value, list):
        raise _failed(Stage.CHOICES, {'choices': ['Choices must be a list.']}, form)
    return value


def _apply_choices(question, original, data, form=None):
    """Non-choice types never keep a choices list (the widget still posts
    choices_json across a type switch; stale choices used to reroute answer
    storage). The type decides, not the posted field."""
    choices_json = (data.get('choices_json') or '').strip()
    if question.input_type not in CHOICE_TYPES:
        question.choices = None
    elif question.input_type == 'thumbs':
        # Fixed 👍/👎 list; the choices editor never shows for this type.
        question.choices = question.thumbs_choices()
    elif choices_json:
        question.choices = guard_choice_codes(original, _parse_choices_json(choices_json, form))


# ─── Validation settings ─────────────────────────────────────────────────────

def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_validation_settings(input_type, data, base=None):
    """The ONE parser of `validation_settings` from the modal's `vs_*` keys.

    number/range: min/max value and outlier sigma; text: min length; polygon:
    area outlier factor; spray: max dots (empty = unlimited); file types:
    size and count limits clamped to the platform ceilings (a creator can
    lower, never raise); every multi-feature geo type: min/max features with
    min <= max. Unparseable values are ignored, as the editor always did.
    """
    from ..uploads import PLATFORM_MAX_BYTES, PLATFORM_MAX_FILES

    def raw(key):
        return (data.get(f'vs_{key}') or '').strip()

    vs = dict(base or {})
    if input_type in ('number', 'range'):
        for key in ('min_value', 'max_value', 'outlier_sigma'):
            value = _float(raw(key)) if raw(key) else None
            if value is not None:
                vs[key] = value
    elif input_type in ('text', 'text_line'):
        value = _int(raw('min_length')) if raw('min_length') else None
        if value is not None:
            vs['min_length'] = value
    elif input_type == 'polygon':
        value = _float(raw('area_outlier_factor')) if raw('area_outlier_factor') else None
        if value is not None:
            vs['area_outlier_factor'] = value
    elif input_type == 'spraycan':
        value = _int(raw('max_dots')) if raw('max_dots') else None
        if value and value > 0:
            vs['max_dots'] = value
    elif input_type in FILE_TYPES:
        value = _int(raw('max_file_mb')) if raw('max_file_mb') else None
        if value and value > 0:
            vs['max_file_bytes'] = min(value * 1024 * 1024, PLATFORM_MAX_BYTES)
        value = _int(raw('max_files')) if raw('max_files') else None
        if value and value >= 1:
            vs['max_files'] = min(value, PLATFORM_MAX_FILES)
    # Feature-count limits apply to every geo type (polygon keeps its area
    # factor above as well, hence a separate `if`).
    if input_type in MULTI_FEATURE_TYPES:
        for key, floor in (('min_features', 0), ('max_features', 1)):
            value = _int(raw(key)) if raw(key) else None
            if value is not None and value >= floor:
                vs[key] = value
        if 'min_features' in vs and 'max_features' in vs and vs['max_features'] < vs['min_features']:
            raise _failed(Stage.SETTINGS, {'max_features': [
                'Max places must be greater than or equal to min places.']},
                message='Max places must be greater than or equal to min places.')
    return vs


# ─── Shared map (Objects on the map sourced from answers) ────────────────────

def geo_questions(survey):
    """Top-level geo questions of the (canonical) survey -- the candidates for
    a layer sourced from answers (spec shared-map-layer)."""
    from ..layers import GEO_INPUT_TYPES
    owner = layer_owner(survey)
    return list(Question.objects
                .filter(survey_section__survey_header=owner, input_type__in=GEO_INPUT_TYPES,
                        parent_question_id__isnull=True)
                .select_related('survey_section')
                .order_by('survey_section_id', 'order_number', 'id'))


def label_options(question):
    """Sub-questions a `question` layer may use as the mark's label: choice
    types first (they cannot carry a name or an address), free text after."""
    if question is None:
        return []
    subs = list(Question.objects.filter(parent_question_id=question).order_by('order_number', 'id'))
    choice_like = ('choice', 'multichoice', 'rating', 'thumbs')
    ordered = [q for q in subs if q.input_type in choice_like] + [q for q in subs if q.input_type not in choice_like]
    return [{'code': q.code, 'name': q.name, 'type': q.input_type,
             'free_text': q.input_type in ('text', 'text_line')} for q in ordered]


def _resolve_layer_choice(survey, data):
    """`layer=answers:<code>` means "a layer sourced from that geo question":
    create it if missing and hand the form its id. Runs inside the caller's
    transaction, so a refused save takes the new layer with it."""
    value = data.get('layer') or ''
    if not isinstance(value, str) or not value.startswith('answers:'):
        return data
    code = value[len('answers:'):]
    question = next((q for q in geo_questions(survey) if q.code == code), None)
    if question is None:
        return data
    owner = layer_owner(survey)
    layer = owner.map_layers.defer(*GEOMETRY_TEXT_FIELDS).filter(source='question', source_question_code=code).first()
    if layer is None:
        position = (owner.map_layers.aggregate(m=models.Max('position'))['m'] or 0) + 1
        label = (data.get('sm_label_field') or '').strip()[:100]
        if label and label not in {o['code'] for o in label_options(question)}:
            label = ''
        layer = SurveyMapLayer.objects.create(
            survey=owner, name=f'Marks: {question.name}'[:100], color='#f97316', position=position,
            source='question', source_question_code=code, label_field=label,
            geojson='{"type":"FeatureCollection","features":[]}',
        )
        # Marks stored before this moment would otherwise stay invisible
        # until the next respondent submits.
        backfill_question_layer(layer)
    data = _copy(data)
    data['layer'] = str(layer.pk)
    return data


def _apply_shared_map_settings(question, data):
    """The Objects-on-the-map form is the ONE place a `question` layer's
    label and visibility settings are edited (owner decision 2026-09-05)."""
    layer = layer_lite(question) if question.input_type == 'layer_objects' else None
    if layer is None or layer.source != 'question':
        return
    from ..layers import source_question_for
    changed = []
    if 'sm_label_field' in data:
        value = (data.get('sm_label_field') or '').strip()[:100]
        if not value or value in {o['code'] for o in label_options(source_question_for(layer))}:
            layer.label_field = value
            changed.append('label_field')
    # Tallies / comments are per SUB-question (share_with_respondents); the
    # source keeps only the label field and moderation.
    if 'sm_settings' in data:   # the block was rendered: an unchecked box means False
        layer.approve_first = data.get('sm_approve_first') in ('1', 'true', 'on')
        changed.append('approve_first')
    if changed:
        layer.save(update_fields=changed + ['updated_at'])


def _copy(data):
    """A mutable copy of a QueryDict or a plain dict."""
    return data.copy() if hasattr(data, 'copy') else dict(data)


# ─── Visibility and translations ─────────────────────────────────────────────

def _visibility(visibility_rule, visibility_input, form):
    """(present, rule) from an already-built rule (the API) or the editor's
    Visibility block values; a bad block is a VISIBILITY-stage failure."""
    if visibility_rule is not UNSET:
        return True, visibility_rule
    if visibility_input is UNSET:
        return False, None
    try:
        return parse_visibility(**visibility_input)
    except ValidationFailed as err:
        raise _failed(Stage.VISIBILITY, err.fields, form, message=err.message)


def save_translations_for(question, survey, translations):
    # Same allow-list the base language goes through in QuestionForm; a
    # translated subtext is rendered |safe just the same.
    save_translations(QuestionTranslation, 'question', question, survey, translations,
                      TRANSLATION_FIELDS, rich=('subtext',))


def _emit_first_question(actor, survey, question):
    """Funnel stage, so it fires only for a survey's *first* question --
    emitting per question would count questions, not creators who got past
    the empty editor."""
    if not Question.objects.filter(survey_section__survey_header=survey).exclude(pk=question.pk).exists():
        pe.emit(pe.SURVEY_QUESTION_ADDED, actor.user_id, {'survey_id': str(survey.id), **surface_props(actor)})


def _place(question, section, group, parent=None):
    if group is not None:
        # Inside a group: last in the group, not the section.
        place_in_group(question, group)
    else:
        # Groups share the sequence (change question-groups): count them too.
        question.order_number = (group_max_order(section, parent) or 0) + 1


def _check_rule(rule, question, strict, parent=None):
    try:
        if parent is not None:
            check_rule(rule, 'subquestion', strict, parent=parent, order=question.order_number)
        else:
            check_rule(rule, 'question', strict, survey=question.survey_section.survey_header,
                       section=question.survey_section, order=question.order_number)
    except ValidationFailed as err:
        raise _failed(Stage.VISIBILITY, err.fields, message=err.message)


# ─── Create ──────────────────────────────────────────────────────────────────

def allowed_types(section):
    return {value for value, _label in QuestionForm(section=section).fields['input_type'].choices}


@transaction.atomic
def create_draft(actor, section, input_type, *, name='', subtext='', group=None):
    """The row created the moment a type is picked in the "New question" modal
    (spec survey-editor "Question rows are created on type pick")."""
    survey = section.survey_header
    locks.assert_structure_editable(survey)
    if input_type not in allowed_types(section):
        raise _failed(Stage.FORM, {'input_type': ['Unknown question type.']}, message='Unknown question type.')
    name = (name or '').strip()[:Question._meta.get_field('name').max_length]
    question = Question(survey_section=section, input_type=input_type, name=name,
                        subtext=coerce_creator_html(subtext or ''))
    _place(question, section, group)
    question.choices = question.thumbs_choices() if question.input_type == 'thumbs' else None
    question.save()
    _emit_first_question(actor, survey, question)
    return question


@transaction.atomic
def create(actor, section, data, files=None, *, parent=None, group=None,
           translations=UNSET, visibility_rule=UNSET, visibility_input=UNSET, strict=False):
    """Create a question from the modal's data (top level, or a pop-up
    sub-question of `parent`). Validated completely before the row is saved;
    a layer created from `layer=answers:<code>` goes with a refused save."""
    survey = section.survey_header
    locks.assert_structure_editable(survey)
    if parent is None:
        data = _resolve_layer_choice(survey, data)
        form = QuestionForm(data, files, section=section)
    else:
        form = QuestionForm(data, files, is_subquestion=True)
    if not form.is_valid():
        raise _failed(Stage.FORM, form.errors, form)
    question = form.save(commit=False)
    question.survey_section = section
    if parent is not None:
        question.parent_question_id = parent
    _place(question, section, group, parent)
    _apply_choices(question, question, data, form)
    present, rule = _visibility(visibility_rule, visibility_input, form)
    if present:
        _check_rule(rule, question, strict, parent=parent)
        question.visibility_rule = rule
    if parent is None and (question.input_type in FILE_TYPES or question.input_type in SETTINGS_ON_CREATE):
        # One parser for create and edit (change rest-api-v1): limits posted
        # with a create are kept instead of surviving only a later edit.
        try:
            vs = parse_validation_settings(question.input_type, data)
        except ValidationFailed as err:
            err.form = form
            raise
        if vs or question.input_type in FILE_TYPES:
            question.validation_settings = vs
    question.save()
    if parent is None:
        _apply_shared_map_settings(question, data)
        _emit_first_question(actor, survey, question)
    if translations is not UNSET:
        save_translations_for(question, survey, translations)
    return question


# ─── Edit ────────────────────────────────────────────────────────────────────

@transaction.atomic
def update(actor, question, data, files=None, *, translations=UNSET, visibility_rule=UNSET,
           visibility_input=UNSET, partial=False, strict=False):
    """Edit a question from the modal's data. On a live survey a change of
    type, layer, visibility rule or the removal of an answered option is
    structural (StructureLocked); everything else is applied in place,
    measured and re-screened."""
    survey = question.survey_section.survey_header
    locks.assert_content_editable(survey)
    _, structure_locked = locks.locks(survey)
    is_subquestion = question.parent_question_id_id is not None
    before = question_snapshot(question)
    original_choices = list(question.choices or [])
    # A layer created from "answers:<code>" is structure -- never on a live survey.
    if not structure_locked:
        data = _resolve_layer_choice(survey, data)
    form = bind(QuestionForm, data, files, instance=question, partial=partial,
                is_subquestion=is_subquestion, section=question.survey_section,
                lock_structure=structure_locked)
    if partial:
        data = {**_choices_json_of(question, original_choices), **dict(form.data.items())}
    if not form.is_valid():
        raise _failed(Stage.FORM, form.errors, form)
    q = form.save(commit=False)
    _apply_choices(q, question, data, form)
    if partial and not any(k.startswith('vs_') for k in data):
        vs = dict(q.validation_settings or {})
    else:
        try:
            vs = parse_validation_settings(q.input_type, data)
        except ValidationFailed as err:
            err.form = form
            raise
    q.validation_settings = vs
    present, rule = _visibility(visibility_rule, visibility_input, form)
    if present:
        _check_rule(rule, q, strict, parent=q.parent_question_id if is_subquestion else None)
        q.visibility_rule = rule
    if structure_locked:
        reasons = structural_question_changes(
            before, q, removed_answered_choices(q, original_choices, q.choices))
        if strict:
            reasons += locked_changes(form, data, {'input_type': 'the question type', 'layer': 'the layer'})
        if reasons:
            err = StructureLocked(structural_edit_message(reasons), reasons=reasons,
                                  draft=locks._draft(survey))
            err.form = form
            raise err
    q.save()
    _apply_shared_map_settings(q, data)
    if translations is not UNSET:
        save_translations_for(q, survey, translations)
    if structure_locked:
        pe.emit(pe.LIVE_EDIT_SAVED, actor.user_id,
                {'survey_id': str(survey.id), 'kind': 'question', **surface_props(actor)})
        locks.rescreen_if_live(survey)
    return q


def _choices_json_of(question, choices):
    """A partial update that does not name choices keeps the current list."""
    return {'choices_json': json.dumps(choices)} if choices else {}


@transaction.atomic
def set_choices(actor, question, choices, *, strict=True):
    """Replace a choice question's options. Removing an option that answers
    point at is structural on a live survey."""
    survey = question.survey_section.survey_header
    locks.assert_content_editable(survey)
    if question.input_type not in CHOICE_TYPES or question.input_type == 'thumbs':
        raise _failed(Stage.CHOICES, {'choices': ['This question type has no editable options.']})
    if not isinstance(choices, list):
        raise _failed(Stage.CHOICES, {'choices': ['Choices must be a list.']})
    original = list(question.choices or [])
    new = guard_choice_codes(question, [dict(c) if isinstance(c, dict) else c for c in choices])
    if locks.locks(survey)[1]:
        removed = removed_answered_choices(question, original, new)
        if removed:
            reasons = [f'the option “{label}” ({count} answer{"s" if count != 1 else ""})'
                       for _c, label, count in removed]
            raise StructureLocked(structural_edit_message(reasons), reasons=reasons,
                                  draft=locks._draft(survey))
    question.choices = new
    question.save(update_fields=['choices'])
    if locks.locks(survey)[1]:
        pe.emit(pe.LIVE_EDIT_SAVED, actor.user_id,
                {'survey_id': str(survey.id), 'kind': 'question', **surface_props(actor)})
        locks.rescreen_if_live(survey)
    return question


@transaction.atomic
def set_share(actor, question, share):
    """The "Others see" switch on a sub-question of an Objects question."""
    locks.assert_content_editable(question.survey_section.survey_header)
    if question.input_type not in ('thumbs', 'text', 'text_line'):
        raise ValidationFailed.single('share', 'This sub-question type has nothing to share.')
    question.share_with_respondents = bool(share)
    question.save(update_fields=['share_with_respondents'])
    return question


# ─── Delete ──────────────────────────────────────────────────────────────────

def _shared_map_source_layers(survey, question):
    from ..layers import question_layers_for
    return list(question_layers_for(survey, question.code)) \
        if question.input_type in SHARED_MAP_SOURCE_TYPES else []


def delete_blocker(survey, question):
    """The reason the question may not be deleted at all, else None.

    Shared map (spec shared-map-layer "Source geo questions are protected"):
    a geo question feeding a `question` layer that some Objects question still
    shows cannot go. Only readers in THIS header count: a draft's structure is
    the draft's to change.
    """
    readers = [q for layer in _shared_map_source_layers(survey, question)
               for q in layer.questions.filter(input_type='layer_objects', survey_section__survey_header=survey)
               .select_related('survey_section')]
    if readers:
        names = ', '.join(f'“{q.name or "(unnamed)"}” ({q.survey_section.title or q.survey_section.name})' for q in readers)
        return f'Respondents’ marks on this question are shown by {names}. Delete that question first.'
    return None


def delete_with_layers(survey, question):
    """Delete a question and the derived layers that only it kept alive."""
    source_layers = _shared_map_source_layers(survey, question)
    # An Objects question was the layer's presence on a map; when it was the
    # last one showing a `question`-sourced layer, the layer is orphaned
    # derived data -- drop it so Survey settings does not keep a "Marks" layer
    # nothing reads.
    orphan_layer = layer_lite(question) if (question.input_type == 'layer_objects' and question.layer_id
                                            and layer_lite(question).source == 'question') else None
    question.delete()
    if orphan_layer is not None and not orphan_layer.questions.exists():
        orphan_layer.delete()
    # The layer itself goes only when NO header reads it any more -- the
    # published version may still show it to live respondents.
    for layer in source_layers:
        if not layer.questions.exists():
            layer.delete()


def is_configured(question):
    """A name is not the only sign of work: a picked layer, sub-questions, a
    body typed into Subtext (for `html` the whole content). Markup carrying
    no text is not content (change fix-draft-question-body-loss)."""
    subtext_text = strip_tags(question.subtext or '').replace('\xa0', ' ').strip()
    return bool((question.name or '').strip() or question.layer_id or subtext_text
                or Question.objects.filter(parent_question_id=question).exists())


@transaction.atomic
def delete(actor, question, *, acknowledge_answer_loss=False, if_empty=False):
    """Delete a question with its sub-questions. `if_empty` (the modal's close
    handler) keeps a configured question and returns False."""
    survey = question.survey_section.survey_header
    locks.assert_structure_editable(survey)
    if if_empty and is_configured(question):
        return False
    blocked = delete_blocker(survey, question)
    if blocked:
        raise DeleteBlocked(blocked, body={'blocked': blocked})
    guard_answer_loss(survey, question.answer_count(), acknowledge_answer_loss)
    delete_with_layers(survey, question)
    return True


# ─── Order ───────────────────────────────────────────────────────────────────

@transaction.atomic
def reorder_flat(actor, survey, question_ids):
    """The legacy flat reorder: order_number = position, scoped to the survey."""
    locks.assert_structure_editable(survey)
    try:
        ids = [int(i) for i in question_ids]
    except (TypeError, ValueError):
        raise ValidationFailed.single('question_ids', 'Ids must be integers.')
    for i, qid in enumerate(ids):
        Question.objects.filter(id=qid, survey_section__survey_header=survey).update(order_number=i)


@transaction.atomic
def reorder(actor, section, parent_id, items):
    """Renumber one root (a section's top level or one pop-up) 0..N from its
    nested state `[{"g": id, "q": [ids]} | {"q": id}]` and set each
    question's group from where it sits (design D7 of question-groups).
    Rows not listed keep their relative order after the listed ones."""
    locks.assert_structure_editable(section.survey_header)
    apply_nested_order(section, parent_id, items)


def apply_nested_order(section, parent_id, items):
    """The renumbering behind `reorder`, for callers that already hold the
    lock check and the transaction (the editor's move endpoint)."""
    from ..models import QuestionGroup
    if not isinstance(items, list):
        raise ValidationFailed.single('items', 'Items must be a list.')
    q_qs = Question.objects.filter(survey_section=section)
    g_qs = QuestionGroup.objects.filter(survey_section=section)
    if parent_id is None:
        q_qs, g_qs = q_qs.filter(parent_question_id__isnull=True), g_qs.filter(parent_question__isnull=True)
    else:
        q_qs, g_qs = q_qs.filter(parent_question_id=parent_id), g_qs.filter(parent_question_id=parent_id)
    questions = {q.id: q for q in q_qs}
    groups = {g.id: g for g in g_qs}

    sequence = []          # [(kind, obj, group_or_None)]
    try:
        for item in items:
            if 'g' in item:
                group = groups[int(item['g'])]
                sequence.append(('g', group, None))
                for qid in item.get('q') or []:
                    sequence.append(('q', questions[int(qid)], group))
            else:
                sequence.append(('q', questions[int(item['q'])], None))
    except (KeyError, TypeError, ValueError):
        raise ValidationFailed.single('items', 'An id is not of this list.')
    seen = {(kind, obj.id) for kind, obj, _g in sequence}
    if len(seen) != len(sequence):
        raise ValidationFailed.single('items', 'An id is listed twice.')
    rest = sorted(
        [('q', q, q.group if q.group_id in groups else None) for q in questions.values() if ('q', q.id) not in seen]
        + [('g', g, None) for g in groups.values() if ('g', g.id) not in seen],
        key=lambda t: (t[1].order_number, t[1].id))
    for i, (kind, obj, group) in enumerate(sequence + rest):
        if kind == 'g':
            QuestionGroup.objects.filter(pk=obj.pk).update(order_number=i)
        else:
            Question.objects.filter(pk=obj.pk).update(
                order_number=i, group_id=group.pk if group else None)
