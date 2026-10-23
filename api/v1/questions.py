"""Questions of a section, their sub-questions, options and order."""
from typing import List
from uuid import UUID

from django.db import transaction
from ninja import Router, Status

from survey.models import Question
from survey.services import questions as svc_questions
from survey.services.common import UNSET

from .. import scopes
from . import deps, forms_bridge, out
from .auth import Bearer
from .docs import errors
from .schemas import ChoicesIn, QuestionCreateIn, QuestionIn, QuestionOrderIn, QuestionOut

router = Router(tags=['Questions'])

READ = Bearer(scopes.SURVEYS_READ)
WRITE = Bearer(scopes.SURVEYS_WRITE)


def _body(payload):
    body = payload.dict(exclude_unset=True)
    if body.get('choices') is not None:
        body['choices'] = [{k: v for k, v in c.items() if v is not None} for c in body['choices']]
    return body


def _create(request, section, payload, parent=None):
    body = _body(payload)
    return svc_questions.create(
        deps.actor(request), section, forms_bridge.question(body, create=True), parent=parent,
        translations=forms_bridge.translations(body) if 'translations' in body else UNSET,
        visibility_rule=forms_bridge.visibility(body), strict=True)


@router.get('/surveys/{uuid}/sections/{section_id}/questions', response=List[QuestionOut], auth=READ,
            openapi_extra=errors())
def list_questions(request, uuid: UUID, section_id: int):
    """Top-level questions of a section in order; each lists its sub-question ids."""
    survey = deps.survey(request, uuid)
    section = deps.section(request, survey, section_id)
    return [out.question(q) for q in deps.top_questions(section).order_by('order_number', 'id')]


@router.post('/surveys/{uuid}/sections/{section_id}/questions', response={201: QuestionOut}, auth=WRITE,
             openapi_extra=errors(409))
def create_question(request, uuid: UUID, section_id: int, payload: QuestionCreateIn):
    """Add a question at the end of the section."""
    survey = deps.survey(request, uuid, role='editor')
    section = deps.section(request, survey, section_id)
    return Status(201, out.question(_create(request, section, payload)))


@router.put('/surveys/{uuid}/sections/{section_id}/questions/order', response=List[QuestionOut], auth=WRITE,
            openapi_extra=errors(409))
def order_questions(request, uuid: UUID, section_id: int, payload: QuestionOrderIn):
    """Renumber the section's top level (or one pop-up, with `parent_id`).
    Items are question ids, or `{"g": <group id>, "q": [<ids>]}` for a group."""
    survey = deps.survey(request, uuid, role='editor')
    section = deps.section(request, survey, section_id)
    if payload.parent_id is not None:
        deps.question(request, survey, payload.parent_id)
    items = [{'q': i} if isinstance(i, int) else i for i in payload.items]
    svc_questions.reorder(deps.actor(request), section, payload.parent_id, items)
    qs = Question.objects.filter(survey_section=section, parent_question_id=payload.parent_id) \
        if payload.parent_id is not None else deps.top_questions(section)
    return [out.question(q) for q in qs.order_by('order_number', 'id')]


@router.get('/surveys/{uuid}/questions/{question_id}', response=QuestionOut, auth=READ, openapi_extra=errors())
def get_question(request, uuid: UUID, question_id: int):
    survey = deps.survey(request, uuid)
    return out.question(deps.question(request, survey, question_id))


@router.patch('/surveys/{uuid}/questions/{question_id}', response=QuestionOut, auth=WRITE,
              openapi_extra=errors(409))
def patch_question(request, uuid: UUID, question_id: int, payload: QuestionIn):
    """Change the fields the body names. On a live survey wording, help text,
    translations and added options are applied in place; type, layer,
    visibility rule and removing an answered option are structure
    (`409 draft_required`). `validation_settings` replaces the whole object."""
    survey = deps.survey(request, uuid, role='editor')
    question = deps.question(request, survey, question_id)
    body = _body(payload)
    with transaction.atomic():
        svc_questions.update(
            deps.actor(request), question, forms_bridge.question(body),
            translations=forms_bridge.translations(body) if 'translations' in body else UNSET,
            visibility_rule=forms_bridge.visibility(body), partial=True, strict=True)
    question.refresh_from_db()
    return out.question(question)


@router.delete('/surveys/{uuid}/questions/{question_id}', response={204: None}, auth=WRITE,
               openapi_extra=errors(409, codes=('answers_at_risk', 'delete_blocked')))
def delete_question(request, uuid: UUID, question_id: int, acknowledge_answer_loss: bool = False):
    """Delete a question with its sub-questions; see `acknowledge_answer_loss`
    on section delete."""
    survey = deps.survey(request, uuid, role='editor')
    question = deps.question(request, survey, question_id)
    svc_questions.delete(deps.actor(request), question, acknowledge_answer_loss=acknowledge_answer_loss)
    return Status(204, None)


@router.put('/surveys/{uuid}/questions/{question_id}/choices', response=QuestionOut, auth=WRITE,
            openapi_extra=errors(409))
def put_choices(request, uuid: UUID, question_id: int, payload: ChoicesIn):
    """Replace the options of a choice question. Keep an option's `code` to
    keep its answers; a new option gets a code never used in the survey's
    history."""
    survey = deps.survey(request, uuid, role='editor')
    question = deps.question(request, survey, question_id)
    choices = [{k: v for k, v in c.items() if v is not None} for c in payload.dict()['choices']]
    svc_questions.set_choices(deps.actor(request), question, choices)
    question.refresh_from_db()
    return out.question(question)


@router.post('/surveys/{uuid}/questions/{question_id}/subquestions', response={201: QuestionOut}, auth=WRITE,
             openapi_extra=errors(409))
def create_subquestion(request, uuid: UUID, question_id: int, payload: QuestionCreateIn):
    """Ask something about each feature placed on a geo question, or each
    object of an Objects question: the sub-question appears in its pop-up."""
    survey = deps.survey(request, uuid, role='editor')
    parent = deps.question(request, survey, question_id)
    if not parent.can_have_subquestions:
        from ..errors import ApiError
        raise ApiError(422, 'validation', 'This question type has no pop-up.',
                       fields={'question_id': ['Only geo and Objects questions take sub-questions.']})
    with transaction.atomic():
        question = _create(request, parent.survey_section, payload, parent=parent)
    return Status(201, out.question(question))

