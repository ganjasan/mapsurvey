"""Question groups: create, edit, delete (change api-v2-structure, #412).

The editor's group endpoints and REST API v1 both call this; neither writes
`QuestionGroup` directly. Locks follow the live-survey split of change
question-groups: title, description, display style and translations are
content and apply to a live survey in place; creating, deleting, membership
and the group's visibility rule are structure.

Membership is never set here field by field. It is a position in the one
continuous order of a bucket (a section's top level or one pop-up), so every
change of it goes through `questions.apply_nested_order`.
"""
from django.db import transaction

from .. import product_events as pe
from ..audit import record as audit_record
from ..editor_forms import QuestionGroupForm
from ..groups import next_order
from ..models import Answer, Question, QuestionGroup, QuestionGroupTranslation
from . import locks
from .common import UNSET, bind, check_rule, guard_answer_loss, save_translations, surface_props, validate
from .errors import DeleteBlocked, StructureLocked, ValidationFailed
from .questions import apply_nested_order, delete_blocker, delete_with_layers

TRANSLATION_FIELDS = ('title', 'description')
TRANSLATION_CAPS = {'title': 512}
DEFAULTS = {'title': '', 'description': '', 'display_style': 'card'}


def groups_of(section):
    """Every group of a section, top level and pop-ups, in order."""
    return QuestionGroup.objects.filter(survey_section=section).order_by(
        'parent_question_id', 'order_number', 'id')


def _check_parent(section, parent):
    if parent is None:
        return
    if parent.survey_section_id != section.id or parent.parent_question_id_id is not None:
        raise ValidationFailed.single('parent_id', 'Not a top-level question of this section.')
    if not parent.can_have_subquestions:
        raise ValidationFailed.single('parent_id', 'This question has no pop-up.')


def _check_group_rule(rule, group, strict):
    if group.parent_question_id:
        check_rule(rule, 'subquestion', strict, parent=group.parent_question, order=group.order_number)
    else:
        check_rule(rule, 'group', strict, survey=group.survey_section.survey_header,
                   section=group.survey_section, order=group.order_number)


def save_translations_for(group, survey, translations, record_all=()):
    save_translations(QuestionGroupTranslation, 'group', group, survey, translations,
                      TRANSLATION_FIELDS, rich=('description',), caps=TRANSLATION_CAPS,
                      record_all=record_all)


def bucket_items(section, parent_id, *, exclude=()):
    """The nested order of one bucket as `apply_nested_order` reads it:
    `[{"g": id, "q": [ids]} | {"q": id}]`, questions in `exclude` left out."""
    questions = Question.objects.filter(survey_section=section)
    groups = QuestionGroup.objects.filter(survey_section=section)
    if parent_id is None:
        questions = questions.filter(parent_question_id__isnull=True)
        groups = groups.filter(parent_question__isnull=True)
    else:
        questions = questions.filter(parent_question_id=parent_id)
        groups = groups.filter(parent_question_id=parent_id)
    group_ids = set(groups.values_list('id', flat=True))
    members = {}
    slots = []
    for q in questions.exclude(pk__in=list(exclude)).order_by('order_number', 'id'):
        if q.group_id in group_ids:
            members.setdefault(q.group_id, []).append(q.id)
        else:
            slots.append((q.order_number, 1, q.id, {'q': q.id}))
    for g in groups:
        slots.append((g.order_number, 0, g.id, {'g': g.id, 'q': members.get(g.id, [])}))
    return [item for *_key, item in sorted(slots, key=lambda s: s[:3])]


def _with_members(items, group_id, question_ids):
    """`items` with `question_ids` taken out of wherever they sit and placed,
    in the given order, as the members of `group_id` at the place of the
    first of them."""
    wanted = [int(i) for i in question_ids]
    taken = set(wanted)
    out, placed = [], False
    for item in items:
        if 'g' in item and item['g'] == group_id:
            # The list is the whole membership: former members it leaves out
            # stay where they are, ungrouped.
            if not placed and (any(q in taken for q in item['q']) or not taken):
                out.append({'g': group_id, 'q': wanted})
                placed = True
            out.extend({'q': q} for q in item['q'] if q not in taken)
            continue
        if 'g' in item:
            hit = any(q in taken for q in item['q'])
            if hit and not placed:
                out.append({'g': group_id, 'q': wanted})
                placed = True
            out.append({'g': item['g'], 'q': [q for q in item['q'] if q not in taken]})
        elif item['q'] in taken:
            if not placed:
                out.append({'g': group_id, 'q': wanted})
                placed = True
        else:
            out.append(item)
    if not placed:
        out.append({'g': group_id, 'q': wanted})
    return out


def set_members(group, question_ids):
    """Make `question_ids` the group's members, contiguous at the place of the
    first of them. Every id must be a question of the group's bucket."""
    parent_id = group.parent_question_id
    bucket = set(Question.objects.filter(
        survey_section=group.survey_section,
        **({'parent_question_id': parent_id} if parent_id else {'parent_question_id__isnull': True}),
    ).values_list('id', flat=True))
    try:
        ids = [int(i) for i in question_ids]
    except (TypeError, ValueError):
        raise ValidationFailed.single('question_ids', 'Ids must be integers.')
    if len(set(ids)) != len(ids):
        raise ValidationFailed.single('question_ids', 'An id is listed twice.')
    foreign = [i for i in ids if i not in bucket]
    if foreign:
        raise ValidationFailed.single(
            'question_ids', 'Not a question of this list: ' + ', '.join(str(i) for i in foreign))
    items = _with_members(bucket_items(group.survey_section, parent_id), group.id, ids)
    apply_nested_order(group.survey_section, parent_id, items)


def _audit(actor, action, group, **meta):
    audit_record(actor, action, group.survey_section.survey_header,
                 group_id=group.pk, group_code=group.code, **meta)


@transaction.atomic
def create(actor, section, data=None, *, parent=None, visibility_rule=None, translations=None,
           question_ids=None, strict=False):
    """A new group at the end of a section's top level or of one pop-up;
    with `question_ids`, those questions become its members."""
    survey = section.survey_header
    locks.assert_structure_editable(survey)
    _check_parent(section, parent)
    group = QuestionGroup(survey_section=section, parent_question=parent,
                          order_number=next_order(section, parent))
    form = validate(bind(QuestionGroupForm, {**DEFAULTS, **(data or {})}, instance=group))
    group = form.save(commit=False)
    _check_group_rule(visibility_rule, group, strict)
    group.visibility_rule = visibility_rule
    group.save()
    if translations:
        save_translations_for(group, survey, translations)
    if question_ids:
        set_members(group, question_ids)
        group.refresh_from_db()
    _audit(actor, 'group_create', group, parent_id=parent.pk if parent else None)
    return group


@transaction.atomic
def update(actor, group, data=None, *, visibility_rule=UNSET, translations=UNSET, question_ids=None,
           strict=False):
    """Content edits (title, description, style, translations) apply to a live
    survey in place; the rule and the members are structure."""
    survey = group.survey_section.survey_header
    locks.assert_content_editable(survey)
    _, structure_locked = locks.locks(survey)
    changes_rule = visibility_rule is not UNSET and visibility_rule != group.visibility_rule
    audience_before = group.audience
    form = validate(bind(QuestionGroupForm, data or {}, instance=group, partial=True))
    changes_audience = form.cleaned_data.get('audience', audience_before) != audience_before
    reasons = ((['visibility rule'] if changes_rule else []) + (['the audience'] if changes_audience else [])
               + (['members'] if question_ids is not None else []))
    if structure_locked and reasons:
        group.audience = audience_before  # the bound form already wrote it onto the instance
        raise StructureLocked(locks.STRUCTURE_LOCKED_MESSAGE, reasons=reasons, draft=locks._draft(survey))
    group = form.save(commit=False)
    if changes_rule:
        _check_group_rule(visibility_rule, group, strict)
        group.visibility_rule = visibility_rule
    group.save()
    if translations is not UNSET:
        save_translations_for(group, survey, translations)
    if question_ids is not None:
        set_members(group, question_ids)
        group.refresh_from_db()
    if structure_locked:
        pe.emit(pe.LIVE_EDIT_SAVED, actor.user_id, {'survey_id': str(survey.id), 'kind': 'group',
                                                     **surface_props(actor)})
        locks.rescreen_if_live(survey)
    _audit(actor, 'group_update', group)
    return group


@transaction.atomic
def delete(actor, group, *, with_questions=False, acknowledge_answer_loss=False):
    """Delete the group. Its questions stay in place, ungrouped, unless
    `with_questions`, which deletes them behind the answer-loss guard."""
    survey = group.survey_section.survey_header
    locks.assert_structure_editable(survey)
    members = list(group.members())
    deleted = 0
    if with_questions and members:
        for member in members:
            blocked = delete_blocker(survey, member)
            if blocked:
                raise DeleteBlocked(blocked, body={'blocked': blocked})
        ids = [i for member in members for i in member.descendant_question_ids()]
        guard_answer_loss(survey, Answer.objects.filter(question_id__in=ids).count(), acknowledge_answer_loss)
        for member in members:
            delete_with_layers(survey, member)
        deleted = len(members)
    _audit(actor, 'group_delete', group, with_questions=bool(with_questions), deleted_questions=deleted)
    group.delete()
