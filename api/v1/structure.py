"""Structure beyond single edits (change api-v2-structure, #412): question
groups, duplicating and copying, moving a question, versions, icon search.

Every write goes through `survey/services/groups.py` and
`survey/services/structure.py`, the same code the editor runs, and is
structural on a live survey (`409 draft_required`) except a group's wording.
"""
from typing import List, Optional
from uuid import UUID

from ninja import Router, Status

from survey import icon_search
from survey.analytics import nonempty_sessions
from survey.models import AuditLog, Membership, Question, QuestionGroup, SurveyHeader, SurveySection, SurveySession
from survey.permissions import ORG_ROLE_RANK
from survey.services import groups as svc_groups
from survey.services import publishing as svc_publishing
from survey.services import structure as svc_structure
from survey.services.common import UNSET
from survey.services.sections import ordered

from .. import limits, scopes
from ..errors import FORBIDDEN_ROLE, LIMIT_REACHED, TRANSITION_REFUSED, CONFLICT, ApiError, not_found
from . import deps, forms_bridge, out
from .auth import Bearer
from .docs import errors
from .schemas import (
    CopyQuestionIn, CopySectionIn, DuplicateSurveyOut, GroupCreateIn, GroupIn, GroupOut, IconOut, MoveIn, MoveOut,
    QuestionOut, RestoreOut, SectionOut, VersionOut,
)

router = Router(tags=['Structure'])

READ = Bearer(scopes.SURVEYS_READ)
WRITE = Bearer(scopes.SURVEYS_WRITE)


# ─── Groups ──────────────────────────────────────────────────────────────────

def find_group(survey, group_id):
    obj = QuestionGroup.objects.select_related('survey_section', 'parent_question').filter(
        pk=group_id, survey_section__survey_header=survey).first()
    if obj is None:
        raise not_found()
    return obj


def group_args(body):
    data = {k: ('' if body[k] is None else body[k]) for k in ('title', 'description', 'display_style') if k in body}
    translations = forms_bridge.translations(body) if 'translations' in body else UNSET
    return data, forms_bridge.visibility(body), translations


@router.get('/surveys/{uuid}/sections/{section_id}/groups', response=List[GroupOut], auth=READ,
            openapi_extra=errors())
def list_groups(request, uuid: UUID, section_id: int):
    """The section's question groups -- top level first, then each pop-up's -- in order."""
    survey = deps.survey(request, uuid)
    section = deps.section(request, survey, section_id)
    return [out.group(g) for g in svc_groups.groups_of(section)]


@router.post('/surveys/{uuid}/sections/{section_id}/groups', response={201: GroupOut}, auth=WRITE,
             openapi_extra=errors(409))
def create_group(request, uuid: UUID, section_id: int, payload: GroupCreateIn):
    """A group at the end of the section (or of a pop-up with `parent_id`); `question_ids` fills it."""
    survey = deps.survey(request, uuid, role='editor')
    section = deps.section(request, survey, section_id)
    body = payload.dict(exclude_unset=True)
    parent = None
    if body.get('parent_id') is not None:
        parent = deps.question(request, survey, body['parent_id'])
    data, rule, translations = group_args(body)
    group = svc_groups.create(
        deps.actor(request), section, data, parent=parent,
        visibility_rule=None if rule is UNSET else rule,
        translations=None if translations is UNSET else translations,
        question_ids=body.get('question_ids'), strict=True)
    return Status(201, out.group(group))


@router.get('/surveys/{uuid}/groups/{group_id}', response=GroupOut, auth=READ, openapi_extra=errors())
def get_group(request, uuid: UUID, group_id: int):
    return out.group(find_group(deps.survey(request, uuid), group_id))


@router.patch('/surveys/{uuid}/groups/{group_id}', response=GroupOut, auth=WRITE, openapi_extra=errors(409))
def update_group(request, uuid: UUID, group_id: int, payload: GroupIn):
    """Wording and style apply to a live survey in place; the rule and `question_ids` are structure."""
    survey = deps.survey(request, uuid, role='editor')
    group = find_group(survey, group_id)
    body = payload.dict(exclude_unset=True)
    data, rule, translations = group_args(body)
    group = svc_groups.update(deps.actor(request), group, data, visibility_rule=rule, translations=translations,
                              question_ids=body.get('question_ids'), strict=True)
    return out.group(group)


@router.delete('/surveys/{uuid}/groups/{group_id}', response={204: None}, auth=WRITE,
               openapi_extra=errors(409, codes=('answers_at_risk', 'delete_blocked')))
def delete_group(request, uuid: UUID, group_id: int, with_questions: bool = False,
                 acknowledge_answer_loss: bool = False):
    """Delete the group; its questions stay in place, ungrouped, unless `with_questions`."""
    survey = deps.survey(request, uuid, role='editor')
    svc_groups.delete(deps.actor(request), find_group(survey, group_id), with_questions=with_questions,
                      acknowledge_answer_loss=acknowledge_answer_loss)
    return Status(204, None)


# ─── Duplicate and copy ──────────────────────────────────────────────────────

@router.post('/surveys/{uuid}/questions/{question_id}/duplicate', response={201: QuestionOut}, auth=WRITE,
             openapi_extra=errors(409))
def duplicate_question(request, uuid: UUID, question_id: int):
    """A copy right after the question, in its group, with " (copy)" on the name and its sub-questions."""
    survey = deps.survey(request, uuid, role='editor')
    source = deps.question(request, survey, question_id)
    return Status(201, out.question(svc_structure.duplicate_question(deps.actor(request), source)))


@router.post('/surveys/{uuid}/sections/{section_id}/duplicate', response={201: SectionOut}, auth=WRITE,
             openapi_extra=errors(409))
def duplicate_section(request, uuid: UUID, section_id: int):
    """A copy of the section with all its questions, right after it, " (copy)" on the title."""
    survey = deps.survey(request, uuid, role='editor')
    source = deps.section(request, survey, section_id)
    return Status(201, out.section(svc_structure.duplicate_section(deps.actor(request), source)))


def source_question(request, question_id):
    """The question a copy is made from: any survey the caller can read over
    the API (404 for one they cannot see, pro_required on a Free workspace)."""
    source = Question.objects.select_related('survey_section__survey_header').filter(pk=question_id).first()
    if source is None:
        raise not_found()
    deps.survey(request, source.survey_section.survey_header.uuid)
    return source


def source_section(request, section_id):
    source = SurveySection.objects.select_related('survey_header').filter(pk=section_id).first()
    if source is None:
        raise not_found()
    deps.survey(request, source.survey_header.uuid)
    return source


@router.post('/surveys/{uuid}/sections/{section_id}/questions/copy', response={201: QuestionOut}, auth=WRITE,
             openapi_extra=errors(409))
def copy_question(request, uuid: UUID, section_id: int, payload: CopyQuestionIn):
    """Append a copy of a question from any survey you can read (new codes, its own files)."""
    survey = deps.survey(request, uuid, role='editor')
    section = deps.section(request, survey, section_id)
    source = source_question(request, payload.source_question_id)
    parent = deps.question(request, survey, payload.parent_id) if payload.parent_id is not None else None
    copy = svc_structure.paste_question(deps.actor(request), section, source, parent=parent)
    return Status(201, out.question(copy))


@router.post('/surveys/{uuid}/sections/copy', response={201: SectionOut}, auth=WRITE, openapi_extra=errors(409))
def copy_section(request, uuid: UUID, payload: CopySectionIn):
    """Append a copy of a section from any survey you can read."""
    survey = deps.survey(request, uuid, role='editor')
    source = source_section(request, payload.source_section_id)
    return Status(201, out.section(svc_structure.paste_section(deps.actor(request), survey, source)))


# ─── Move ────────────────────────────────────────────────────────────────────

@router.post('/surveys/{uuid}/questions/{question_id}/move', response=MoveOut, auth=WRITE,
             openapi_extra=errors(409, codes=('answers_at_risk',)))
def move_question(request, uuid: UUID, question_id: int, payload: MoveIn):
    """Move a question to another section, into a pop-up or out of one, to `position`.

    Between sections it keeps its answers and leaves its group. Into or out of a
    pop-up its answers cannot follow (one per respondent against one per mark):
    `409 answers_at_risk` until `acknowledge_answer_loss`. Rules the move breaks
    are cleared and named in `removed_rules`."""
    survey = deps.survey(request, uuid, role='editor')
    question = deps.question(request, survey, question_id)
    section = deps.section(request, survey, payload.section_id) if payload.section_id is not None else None
    parent = deps.question(request, survey, payload.parent_id) if payload.parent_id is not None else None
    moved = svc_structure.move_question(
        deps.actor(request), question, section=section, parent=parent, position=payload.position,
        acknowledge_answer_loss=payload.acknowledge_answer_loss)
    return {'question': out.question(moved.question), 'removed_rules': moved.removed_rules}


# ─── Whole survey ────────────────────────────────────────────────────────────

@router.post('/surveys/{uuid}/duplicate', response={201: DuplicateSurveyOut}, auth=WRITE,
             openapi_extra=errors(409, codes=(LIMIT_REACHED,)))
def duplicate_survey(request, uuid: UUID):
    """A new draft survey in the same workspace with this one's sections, questions, groups, rules,
    translations, settings and map layers -- no responses, versions, links or public results page."""
    return Status(201, duplicate(request, deps.survey(request, uuid), deps.actor(request)))


def duplicate(request, source, actor):
    """The copy and its counts, after the checks every surface makes: the
    workspace role that creates surveys and the `survey_create` limit."""
    p = request.principal
    membership = Membership.objects.filter(user=p.user, organization=source.organization).first()
    if membership is None or ORG_ROLE_RANK.get(membership.role, -1) < ORG_ROLE_RANK['editor']:
        raise ApiError(403, FORBIDDEN_ROLE, 'Creating surveys needs the editor role in the workspace.',
                       role='editor')
    limits.hit(p, 'survey_create')
    copy = svc_structure.duplicate_survey(actor, source)
    return {
        **out.survey(copy),
        'sections': len(list(ordered(copy))),
        'questions': Question.objects.filter(survey_section__survey_header=copy).count(),
        'layers': copy.map_layers.count(),
    }


# ─── Versions ────────────────────────────────────────────────────────────────

def _published_at(canonical):
    """{version number: first publish time} from the audit log -- the status
    says nothing about when (lesson: publish dates live in AuditLog)."""
    when = {}
    rows = AuditLog.objects.filter(
        survey_uuid=canonical.uuid, action__in=('status_transition', 'draft_publish'),
    ).order_by('created_at').values_list('action', 'metadata', 'created_at')
    for action, meta, created in rows:
        meta = meta or {}
        if action == 'draft_publish' and meta.get('version'):
            when.setdefault(int(meta['version']), created)
        elif action == 'status_transition' and meta.get('new_status') == 'published':
            when.setdefault(1, created)
    return when


def _version(header, current, published):
    return {
        'version': header.version_number,
        'current': current,
        'status': header.status,
        'published_at': published.get(header.version_number),
        'sections': SurveySection.objects.filter(survey_header=header).count(),
        'questions': Question.objects.filter(survey_section__survey_header=header).count(),
        'responses': nonempty_sessions(SurveySession.objects.filter(survey=header)).count(),
    }


@router.get('/surveys/{uuid}/versions', response=List[VersionOut], auth=READ, openapi_extra=errors())
def list_versions(request, uuid: UUID):
    """The current survey, then its archived versions newest first; each publish makes a version."""
    return versions_of(deps.survey(request, uuid))


def versions_of(survey):
    canonical = survey.published_version or survey
    published = _published_at(canonical)
    archived = SurveyHeader.objects.filter(canonical_survey=canonical, is_canonical=False).order_by(
        '-version_number')
    return [_version(canonical, True, published)] + [_version(h, False, published) for h in archived]


@router.post('/surveys/{uuid}/versions/{version}/restore', response={201: RestoreOut}, auth=WRITE,
             openapi_extra=errors(409, codes=(TRANSITION_REFUSED, CONFLICT)))
def restore_version(request, uuid: UUID, version: int):
    """Unpublished changes holding version `version`'s questionnaire. The live survey is unchanged until
    you publish them, which makes a NEW version; history is never rewritten."""
    survey = deps.survey(request, uuid, role='owner')
    draft = svc_publishing.restore_version(deps.actor(request), survey, version)
    if draft is None:
        raise not_found()
    return Status(201, {'unpublished_changes': draft.uuid, 'version': version})


# ─── Icons ───────────────────────────────────────────────────────────────────

@router.get('/icons', response=List[IconOut], auth=READ, openapi_extra=errors())
def search_icons(request, q: str = '', lang: Optional[str] = None, set: Optional[str] = None, limit: int = 20):
    """Marker icons by meaning, best first: every word must match the icon's name, label or search
    terms in `lang` (default: your interface language) or English. `set` narrows to maki, temaki or fa.
    Every value is accepted as `icon_class`."""
    return icons(request, q, lang=lang, icon_set=set, limit=limit, surface='api')


def icons(request, q, *, lang=None, icon_set=None, limit=20, surface):
    if icon_set is not None and icon_set not in icon_search.SETS:
        raise ApiError(422, 'validation', 'Unknown icon set.', fields={'set': ['One of maki, temaki, fa.']})
    lang = lang or icon_search.ui_language(request.principal.user)
    hits = icon_search.search(q, lang=lang, sets=[icon_set] if icon_set else None, limit=limit)
    if (q or '').strip() and not hits:
        icon_search.report_miss(request.principal.user, q, lang, surface=surface)
    return hits

