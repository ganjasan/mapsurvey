"""Structure: question groups, duplicating and copying, moving a question,
versions, icon search (change api-v2-structure, #412 PR 2). Every write goes
through `survey.services.groups` / `survey.services.structure` -- the code the
editor and REST API v1 run -- and the checks REST makes on a copy's source,
the workspace role behind a whole-survey copy and the version list come from
`api.v1.structure` itself, so the two surfaces cannot drift.
"""
from typing import Literal, Optional
from uuid import UUID

from pydantic import Field

from survey.services import groups as svc_groups
from survey.services import publishing as svc_publishing
from survey.services import structure as svc_structure
from survey.services.common import UNSET

from api import scopes
from api.errors import not_found
from api.v1 import out
from api.v1.schemas import CopyQuestionIn, CopySectionIn, GroupCreateIn, GroupIn, MoveIn
from api.v1.structure import (
    duplicate, find_group, group_args, icons, source_question, source_section, versions_of,
)

from ..errors import confirmation_required
from .common import actor, question, section, survey
from .registry import args_model, tool

SURVEY = (UUID, Field(description='The survey uuid.'))
SECTION = (int, Field(description='The section id (from get_survey).'))
QUESTION = (int, Field(description='The question id (from get_survey).'))
GROUP = (int, Field(description='The group id (from get_survey or list_groups).'))
CONFIRM = (bool, Field(False, description='Set to true only after the user confirmed this action in the conversation.'))


# ─── Groups ──────────────────────────────────────────────────────────────────

@tool(
    'list_groups',
    title='List question groups',
    description=(
        'The question groups of a section -- top level first, then those inside a map question\'s pop-up '
        '(`parent_id`) -- with title, display style, visibility rule and their question ids in order.'
    ),
    scope=scopes.SURVEYS_READ, role='viewer', read_only=True, idempotent=True,
    args=args_model('ListGroupsArgs', survey=SURVEY, section_id=SECTION),
)
def list_groups(request, args):
    obj = survey(request, args.survey)
    return {'items': [out.group(g) for g in svc_groups.groups_of(section(request, obj, args.section_id))]}


@tool(
    'create_group',
    title='Group questions',
    description=(
        'A question group: a titled run of questions shown together as `plain`, `card` (default) or '
        '`collapsible`, with an optional description and one visibility rule for all of them. '
        '`question_ids` (questions of the same list -- the section\'s top level, or one pop-up with '
        '`parent_id`) move together to where the first of them was. On a published survey this needs '
        'unpublished changes (draft_required).'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor',
    args=args_model('CreateGroupArgs', GroupCreateIn, survey=SURVEY, section_id=SECTION),
)
def create_group(request, args):
    obj = survey(request, args.survey, role='editor')
    sec = section(request, obj, args.section_id)
    body = args.model_dump(exclude_unset=True, exclude={'survey', 'section_id'})
    parent = question(request, obj, body['parent_id']) if body.get('parent_id') is not None else None
    data, rule, translations = group_args(body)
    group = svc_groups.create(
        actor(request), sec, data, parent=parent,
        visibility_rule=None if rule is UNSET else rule,
        translations=None if translations is UNSET else translations,
        question_ids=body.get('question_ids'), strict=True)
    return out.group(group)


@tool(
    'update_group',
    title='Update a question group',
    description=(
        'Change a group\'s title, description, display style or translations -- these apply to a live '
        'survey at once -- or its visibility rule and `question_ids`, which are structural (draft_required '
        'on a published survey). `question_ids` is the whole membership: questions left out stay in '
        'place, ungrouped.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor', idempotent=True,
    args=args_model('UpdateGroupArgs', GroupIn, survey=SURVEY, group_id=GROUP),
)
def update_group(request, args):
    obj = survey(request, args.survey, role='editor')
    group = find_group(obj, args.group_id)
    body = args.model_dump(exclude_unset=True, exclude={'survey', 'group_id'})
    data, rule, translations = group_args(body)
    group = svc_groups.update(actor(request), group, data, visibility_rule=rule, translations=translations,
                              question_ids=body.get('question_ids'), strict=True)
    return out.group(group)


@tool(
    'delete_group',
    title='Delete a question group',
    description=(
        'Remove a group. Its questions stay where they are, ungrouped -- unless `with_questions: true`, '
        'which deletes them too and needs `confirm: true` after the user agreed; when they have answers '
        'the first call answers answers_at_risk with the count, repeat with `acknowledge_answer_loss: true`.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor', destructive=True, confirm=True,
    args=args_model('DeleteGroupArgs', survey=SURVEY, group_id=GROUP,
                    with_questions=(bool, Field(False)), acknowledge_answer_loss=(bool, Field(False)),
                    confirm=CONFIRM),
)
def delete_group(request, args):
    obj = survey(request, args.survey, role='editor')
    group = find_group(obj, args.group_id)
    if args.with_questions and not args.confirm:
        raise confirmation_required('Deleting a group with its questions')
    svc_groups.delete(actor(request), group, with_questions=args.with_questions,
                      acknowledge_answer_loss=args.acknowledge_answer_loss)
    return {'deleted': args.group_id, 'with_questions': args.with_questions}


# ─── Duplicate and copy ──────────────────────────────────────────────────────

@tool(
    'duplicate_question',
    title='Duplicate a question',
    description='A copy right after the question, in its group, with " (copy)" on the name, new codes and its sub-questions.',
    scope=scopes.SURVEYS_WRITE, role='editor',
    args=args_model('DuplicateQuestionArgs', survey=SURVEY, question_id=QUESTION),
)
def duplicate_question(request, args):
    obj = survey(request, args.survey, role='editor')
    return out.question(svc_structure.duplicate_question(actor(request), question(request, obj, args.question_id)))


@tool(
    'duplicate_section',
    title='Duplicate a section',
    description='A copy of the section with all its questions and groups, right after it, " (copy)" on the title.',
    scope=scopes.SURVEYS_WRITE, role='editor',
    args=args_model('DuplicateSectionArgs', survey=SURVEY, section_id=SECTION),
)
def duplicate_section(request, args):
    obj = survey(request, args.survey, role='editor')
    return out.section(svc_structure.duplicate_section(actor(request), section(request, obj, args.section_id)))


@tool(
    'copy_question',
    title='Copy a question from another survey',
    description=(
        'Append a copy of a question from any survey you can read (`source_question_id`) to a section of '
        'this one, with new codes and its own copy of any image. With `parent_id` it goes into that map '
        'question\'s pop-up, without the source\'s own sub-questions.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor',
    args=args_model('CopyQuestionArgs', CopyQuestionIn, survey=SURVEY, section_id=SECTION),
)
def copy_question(request, args):
    obj = survey(request, args.survey, role='editor')
    sec = section(request, obj, args.section_id)
    source = source_question(request, args.source_question_id)
    parent = question(request, obj, args.parent_id) if args.parent_id is not None else None
    return out.question(svc_structure.paste_question(actor(request), sec, source, parent=parent))


@tool(
    'copy_section',
    title='Copy a section from another survey',
    description='Append a copy of a section from any survey you can read (`source_section_id`), with its questions and groups.',
    scope=scopes.SURVEYS_WRITE, role='editor',
    args=args_model('CopySectionArgs', CopySectionIn, survey=SURVEY),
)
def copy_section(request, args):
    obj = survey(request, args.survey, role='editor')
    return out.section(svc_structure.paste_section(actor(request), obj, source_section(request, args.source_section_id)))


@tool(
    'duplicate_survey',
    title='Duplicate a survey',
    description=(
        'A new unpublished survey "<name> (copy)" in the same workspace with this one\'s sections, '
        'questions, groups, visibility rules, translations, settings and map layers -- for running it again '
        'next year or in another district. Responses, versions, campaign links, collaborators and the '
        'public results page stay behind. Needs the editor role in the workspace.'
    ),
    scope=scopes.SURVEYS_WRITE, role='workspace editor',
    args=args_model('DuplicateSurveyArgs', survey=SURVEY),
)
def duplicate_survey(request, args):
    return duplicate(request, survey(request, args.survey), actor(request))


# ─── Move ────────────────────────────────────────────────────────────────────

@tool(
    'move_question',
    title='Move a question',
    description=(
        'Move a question to another section (`section_id`), into a map question\'s pop-up (`parent_id`) or '
        'out of one (`parent_id` null), at `position` among the target list\'s items (a group counts as '
        'one; default: the end). Between sections it keeps its answers and leaves its group. Into or out '
        'of a pop-up its answers cannot follow: the first call answers answers_at_risk with the count; '
        'repeat with `acknowledge_answer_loss: true` only after the user agreed. Visibility rules the '
        'move breaks are cleared and listed in `removed_rules` -- tell the user.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor',
    args=args_model('MoveQuestionArgs', MoveIn, survey=SURVEY, question_id=QUESTION),
)
def move_question(request, args):
    obj = survey(request, args.survey, role='editor')
    q = question(request, obj, args.question_id)
    sec = section(request, obj, args.section_id) if args.section_id is not None else None
    parent = question(request, obj, args.parent_id) if args.parent_id is not None else None
    moved = svc_structure.move_question(actor(request), q, section=sec, parent=parent, position=args.position,
                                        acknowledge_answer_loss=args.acknowledge_answer_loss)
    return {'question': out.question(moved.question), 'removed_rules': moved.removed_rules}


# ─── Versions ────────────────────────────────────────────────────────────────

@tool(
    'list_versions',
    title='List versions',
    description=(
        'The survey\'s versions: the current one first, then the archived ones newest first, each with '
        'its publish date and counts of sections, questions and responses. Every publish of unpublished '
        'changes makes a new version; responses stay with the version they were given to.'
    ),
    scope=scopes.SURVEYS_READ, role='viewer', read_only=True, idempotent=True,
    args=args_model('ListVersionsArgs', survey=SURVEY),
)
def list_versions(request, args):
    return {'items': versions_of(survey(request, args.survey))}


@tool(
    'restore_version',
    title='Restore a version',
    description=(
        'Roll the questionnaire back: unpublished changes holding version `version`\'s sections and '
        'questions. Nothing respondents see changes until publish_unpublished_changes, which makes a NEW '
        'version -- history is never rewritten. Only on a published survey without unpublished changes; '
        'needs the survey owner.'
    ),
    scope=scopes.SURVEYS_WRITE, role='owner',
    args=args_model('RestoreVersionArgs', survey=SURVEY, version=(int, Field(ge=1, description='A version number from list_versions.'))),
)
def restore_version(request, args):
    obj = survey(request, args.survey, role='owner')
    draft = svc_publishing.restore_version(actor(request), obj, args.version)
    if draft is None:
        raise not_found()
    return {'unpublished_changes': draft.uuid, 'version': args.version}


# ─── Icons ───────────────────────────────────────────────────────────────────

@tool(
    'search_icons',
    title='Find a marker icon',
    description=(
        'Marker icons by meaning, best first -- use before setting a question\'s `icon_class` or a '
        'choice\'s `icon` instead of guessing a name. Every word of `q` must match the icon\'s name, label '
        'or search terms in `lang` (default: the user\'s interface language) or English. `set` narrows to '
        'maki or temaki (map symbols) or fa (Font Awesome).'
    ),
    scope=scopes.SURVEYS_READ, role='-', read_only=True, idempotent=True,
    args=args_model(
        'SearchIconsArgs',
        q=(str, Field('', max_length=200, description='What the icon should show, e.g. "bench", "bus stop", "скамейка".')),
        lang=(Optional[str], Field(None, max_length=10, description='ISO 639-1 code of the words in `q`.')),
        set=(Optional[Literal['maki', 'temaki', 'fa']], Field(None)),
        limit=(int, Field(20, ge=1, le=100)),
    ),
)
def search_icons(request, args):
    return {'items': icons(request, args.q, lang=args.lang, icon_set=args.set, limit=args.limit, surface='mcp')}
