"""Copying and moving structure (change api-v2-structure, #412): duplicate a
question, a section or a whole survey, paste from another survey, move a
question anywhere in its survey.

The editor's endpoints and REST API v1 both call this. Every operation is
structural (a live survey answers `StructureLocked`), runs in one transaction
and leaves an audit row. A copy into another survey owns its files
(`cloning.copy_file`); files copied for an operation that then fails are
deleted again.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field

from django.conf import settings
from django.db import transaction

from .. import cloning
from .. import product_events as pe
from ..audit import record as audit_record
from ..editor_forms import SUBQUESTION_DISALLOWED_INPUT_TYPES
from ..groups import max_order as group_max_order, shift_down
from ..models import Answer, Question, QuestionGroup, SurveyCollaborator, SurveySection
from . import locks
from .common import guard_answer_loss
from .errors import LimitReached, ValidationFailed
from .groups import bucket_items
from .questions import apply_nested_order

DUPLICATE_ASSET_BYTES_MAX = 200 * 1024 * 1024
POPUP_REFUSED = 'This kind of question cannot go into a pop-up.'


@dataclass
class Moved:
    question: Question
    removed_rules: list = field(default_factory=list)


@contextmanager
def _owned_files():
    """A list to collect the names `copy_file` stores; they are deleted when
    the block raises, so a refused or failed copy leaves no orphans."""
    created = []
    try:
        yield created
    except BaseException:
        for storage, name in created:
            try:
                storage.delete(name)
            except Exception:  # noqa: BLE001
                pass
        raise


def _survey(obj):
    return obj.survey_header if isinstance(obj, SurveySection) else obj.survey_section.survey_header


# ─── Duplicate within a survey ───────────────────────────────────────────────

@transaction.atomic
def duplicate_question(actor, source):
    """A copy right after `source`, in its group and its pop-up, with fresh
    codes, " (copy)" on the name and its sub-questions."""
    survey = _survey(source)
    locks.assert_structure_editable(survey)
    parent = source.parent_question_id
    shift_down(source.survey_section, parent, source.order_number)
    copy = cloning.clone_question(source, target_section=source.survey_section, parent=parent,
                                  regenerate_code=True, name_suffix=' (copy)', copy_sub_questions=True)
    copy.order_number = source.order_number + 1
    copy.group_id = source.group_id
    copy.save(update_fields=['order_number', 'group'])
    audit_record(actor, 'question_duplicate', survey, question_id=copy.pk, source_question_id=source.pk)
    return copy


@transaction.atomic
def duplicate_section(actor, source):
    """A copy spliced right after `source`, " (copy)" on the title."""
    survey = source.survey_header
    locks.assert_structure_editable(survey)
    copy = cloning.clone_section(source, target_survey=survey, insert_after=source, name_suffix=' (copy)')
    audit_record(actor, 'section_duplicate', survey, section_id=copy.pk, source_section_id=source.pk)
    return copy


# ─── Paste from any readable survey ─────────────────────────────────────────

def paste_question(actor, target_section, source, *, parent=None):
    """A copy of `source` (from any survey the caller may read) appended to
    `target_section`, or to the pop-up of `parent` -- then without the
    source's own sub-questions. Lands last and ungrouped."""
    survey = target_section.survey_header
    locks.assert_structure_editable(survey)
    if parent is not None:
        if parent.survey_section_id != target_section.id or not parent.can_have_subquestions:
            raise ValidationFailed.single('parent_id', 'That question has no pop-up.')
        if source.input_type in SUBQUESTION_DISALLOWED_INPUT_TYPES:
            raise ValidationFailed.single('source_question_id', POPUP_REFUSED)
    with _owned_files() as created, transaction.atomic():
        last = group_max_order(target_section, parent)
        copy = cloning.clone_question(source, target_section=target_section, parent=parent,
                                      regenerate_code=True, name_suffix=None,
                                      copy_sub_questions=parent is None, created_files=created)
        copy.order_number = (last or 0) + 1
        copy.save(update_fields=['order_number'])
        audit_record(actor, 'question_paste', survey, question_id=copy.pk, source_question_id=source.pk,
                     source_survey_uuid=str(_survey(source).uuid))
    return copy


def paste_section(actor, target_survey, source):
    """A copy of `source` appended at the end of `target_survey`."""
    locks.assert_structure_editable(target_survey)
    with _owned_files() as created, transaction.atomic():
        copy = cloning.clone_section(source, target_survey=target_survey, insert_after=None,
                                     name_suffix=None, created_files=created)
        audit_record(actor, 'section_paste', target_survey, section_id=copy.pk, source_section_id=source.pk,
                     source_survey_uuid=str(source.survey_header.uuid))
    return copy


# ─── Move ────────────────────────────────────────────────────────────────────

def _insert(items, question_id, position):
    items = list(items)
    index = len(items) if position is None else max(0, min(int(position), len(items)))
    items.insert(index, {'q': question_id})
    return items


def _rule_broken(host, survey):
    from ..templatetags.question_utils import visibility_info
    info = visibility_info(host, survey)
    return bool(info and info.get('broken'))


def _drop_broken_rules(survey, code, own=None):
    """Clear the rules a move broke and return their hosts' labels: rules
    naming the moved `code` anywhere in the survey, and `own` -- the moved
    question's rule, which may now name a controller below it."""
    if not getattr(settings, 'CONDITIONAL_VISIBILITY', False):
        return []
    hosts = [own] if own is not None and isinstance(own.visibility_rule, dict) else []
    hosts += list(SurveySection.objects.filter(survey_header=survey, visibility_rule__question_code=code))
    hosts += list(Question.objects.filter(survey_section__survey_header=survey,
                                          visibility_rule__question_code=code))
    hosts += list(QuestionGroup.objects.filter(survey_section__survey_header=survey,
                                               visibility_rule__question_code=code))
    removed = []
    for host in hosts:
        if _rule_broken(host, survey):
            host.visibility_rule = None
            host.save(update_fields=['visibility_rule'])
            removed.append(getattr(host, 'name', None) or getattr(host, 'title', None)
                           or getattr(host, 'code', ''))
    return removed


@transaction.atomic
def move_question(actor, question, *, section=None, parent=None, items=None, position=None,
                  acknowledge_answer_loss=False):
    """Move `question` to `section` (default: its own) at the top level, or into
    the pop-up of `parent` (which then names the section).

    `items` is the target list's whole nested order with the question in it
    (the editor's drag); without it the question goes to `position` among the
    target list's items (a group counts as one), at the end by default.

    A change of level (section <-> pop-up) cannot carry answers -- one per
    respondent against one per mark -- so they are deleted behind the
    answer-loss acknowledgement, as are the question's own rule and group.
    A move between sections at the same level keeps everything but the group.
    Rules the move breaks are cleared and named in `removed_rules`."""
    survey = _survey(question)
    locks.assert_structure_editable(survey)
    if parent is not None:
        section = parent.survey_section
    target_section = section or question.survey_section
    if target_section.survey_header_id != survey.id:
        raise ValidationFailed.single('section_id', 'Not a section of this survey.')
    old_section, old_parent_id = question.survey_section, question.parent_question_id_id
    target_parent_id = parent.pk if parent is not None else None

    if parent is not None:
        if parent.pk == question.pk or parent.parent_question_id_id is not None \
                or not parent.can_have_subquestions:
            raise ValidationFailed.single('parent_id', 'That question has no pop-up.')
        if question.input_type in SUBQUESTION_DISALLOWED_INPUT_TYPES \
                or Question.objects.filter(parent_question_id=question).exists():
            raise ValidationFailed.single('parent_id', POPUP_REFUSED)

    level_change = (old_parent_id is None) != (target_parent_id is None) or \
        (old_parent_id is not None and old_parent_id != target_parent_id)
    if level_change:
        count = question.answer_count()
        guard_answer_loss(survey, count, acknowledge_answer_loss)
        if count:
            Answer.objects.filter(question_id__in=question.descendant_question_ids()).delete()

    own_rule_label = None
    question.group = None
    if level_change:
        if isinstance(question.visibility_rule, dict):
            own_rule_label = question.name or question.code
        question.visibility_rule = None
        if parent is None or parent.input_type != 'layer_objects':
            question.share_with_respondents = False
    question.parent_question_id = parent
    if target_section.pk != old_section.pk:
        question.survey_section = target_section
        descendants = [i for i in question.descendant_question_ids() if i != question.pk]
        Question.objects.filter(pk__in=descendants).update(survey_section=target_section)
        QuestionGroup.objects.filter(parent_question=question).update(survey_section=target_section)
    question.save(update_fields=['parent_question_id', 'group', 'visibility_rule',
                                 'share_with_respondents', 'survey_section'])

    if items is None:
        items = _insert(bucket_items(target_section, target_parent_id, exclude=[question.pk]),
                        question.pk, position)
    apply_nested_order(target_section, target_parent_id, items)
    if (old_section.pk, old_parent_id) != (target_section.pk, target_parent_id):
        apply_nested_order(old_section, old_parent_id, [])

    question.refresh_from_db()
    removed = _drop_broken_rules(survey, question.code, own=None if level_change else question)
    if own_rule_label:
        removed.insert(0, own_rule_label)
    audit_record(actor, 'question_move', survey, question_id=question.pk,
                 from_section_id=old_section.pk, to_section_id=target_section.pk,
                 from_parent_id=old_parent_id, to_parent_id=target_parent_id)
    return Moved(question, removed)


# ─── Whole survey ────────────────────────────────────────────────────────────

def duplicate_survey(actor, source):
    """A new independent draft survey in the same workspace: structure, groups,
    rules, translations, settings and copies of the layers, owned by the actor.
    Rights (workspace role, Pro, limits) are the caller's to check."""
    if cloning.asset_bytes(source) > DUPLICATE_ASSET_BYTES_MAX:
        raise LimitReached('This survey holds more than 200 MB of layer attachments; '
                           'copy it through a ZIP export and import instead.')
    with _owned_files() as created, transaction.atomic():
        copy = cloning.clone_survey(source, created_by=actor.user, created_files=created)
        SurveyCollaborator.objects.create(user=actor.user, survey=copy, role='owner')
        audit_record(actor, 'survey_duplicate', copy, source_survey_uuid=str(source.uuid))
    # A copy is a new survey for the funnel; `surface` says how it was made and
    # `via` where the creator asked for it.
    pe.emit(pe.SURVEY_CREATED, actor.user_id, {
        'survey_id': str(copy.id), 'creation_method': pe.CREATION_MANUAL,
        'surface': 'duplicate', 'via': actor.surface, 'map_source': '',
    })
    return copy
