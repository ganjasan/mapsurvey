"""Questions of a section, their sub-questions, options and order."""
from typing import Optional
from uuid import UUID

from django.db import transaction
from pydantic import Field

from survey.models import Question
from survey.services import questions as svc_questions
from survey.services.common import UNSET

from api import scopes
from api.errors import ApiError
from api.v1 import forms_bridge, out
from api.v1.schemas import ChoicesIn, QuestionCreateIn, QuestionIn, QuestionOrderIn

from .common import actor, question, section, survey, top_questions
from .registry import args_model, tool

SURVEY = (UUID, Field(description='The survey uuid.'))
SECTION = (int, Field(description='The section id (from get_survey).'))
QUESTION = (int, Field(description='The question id (from get_survey).'))


def _body(args, *drop):
    body = args.model_dump(exclude_unset=True)
    for key in drop:
        body.pop(key, None)
    if body.get('choices') is not None:
        body['choices'] = [{k: v for k, v in c.items() if v is not None} for c in body['choices']]
    return body


@tool(
    'add_question',
    title='Add a question',
    description=(
        'Add a question at the end of a section. `input_type` picks the kind: text, text_line, number, '
        'choice, multichoice (with `choices`), range, rating, datetime, image, html (a formatted text block), '
        'and the map types point, line, polygon, spraycan. With `parent_question_id` (a geo or Objects '
        'question) it becomes a sub-question asked in that question\'s pop-up for every placed feature -- '
        'the only way to attach attributes to what respondents draw. `subtext` is help text (creator HTML, '
        'sanitised on save). On a live survey this is a structural change: start_unpublished_changes first.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor',
    args=args_model(
        'AddQuestionArgs', QuestionCreateIn, survey=SURVEY, section_id=SECTION,
        parent_question_id=(Optional[int], Field(
            None, description='Make it a sub-question of this geo / Objects question (same section).')),
    ),
)
def add_question(request, args):
    obj = survey(request, args.survey, role='editor')
    sec = section(request, obj, args.section_id)
    parent = None
    if args.parent_question_id is not None:
        parent = question(request, obj, args.parent_question_id)
        if parent.survey_section_id != sec.pk:
            raise ApiError(422, 'validation', 'The parent question is in another section.',
                           fields={'parent_question_id': ['Not in this section.']})
        if not parent.can_have_subquestions:
            raise ApiError(422, 'validation', 'This question type has no pop-up.',
                           fields={'parent_question_id': ['Only geo and Objects questions take sub-questions.']})
    body = _body(args, 'survey', 'section_id', 'parent_question_id')
    with transaction.atomic():
        created = svc_questions.create(
            actor(request), sec, forms_bridge.question(body, create=True), parent=parent,
            translations=forms_bridge.translations(body) if 'translations' in body else UNSET,
            visibility_rule=forms_bridge.visibility(body), strict=True)
    return out.question(created)


@tool(
    'update_question',
    title='Update a question',
    description=(
        'Change the fields you name. On a live survey wording, help text, translations and added options '
        'are applied in place; type, layer, visibility rule and removing an answered option are structure '
        '(draft_required). `validation_settings` replaces the whole object.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor', idempotent=True,
    args=args_model('UpdateQuestionArgs', QuestionIn, survey=SURVEY, question_id=QUESTION),
)
def update_question(request, args):
    obj = survey(request, args.survey, role='editor')
    q = question(request, obj, args.question_id)
    body = _body(args, 'survey', 'question_id')
    with transaction.atomic():
        svc_questions.update(
            actor(request), q, forms_bridge.question(body),
            translations=forms_bridge.translations(body) if 'translations' in body else UNSET,
            visibility_rule=forms_bridge.visibility(body), partial=True, strict=True)
    q.refresh_from_db()
    return out.question(q)


@tool(
    'delete_question',
    title='Delete a question',
    description=(
        'Delete a question with its sub-questions. Answers go too: the first call answers answers_at_risk '
        'with the count; repeat with `acknowledge_answer_loss: true` only after the user agreed.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor', destructive=True,
    args=args_model('DeleteQuestionArgs', survey=SURVEY, question_id=QUESTION,
                    acknowledge_answer_loss=(bool, Field(False))),
)
def delete_question(request, args):
    obj = survey(request, args.survey, role='editor')
    q = question(request, obj, args.question_id)
    section_id = q.survey_section_id
    svc_questions.delete(actor(request), q, acknowledge_answer_loss=args.acknowledge_answer_loss)
    return {'deleted': args.question_id, 'section_id': section_id}


@tool(
    'reorder_questions',
    title='Reorder questions',
    description=(
        'Renumber a section\'s top-level questions (or one pop-up\'s sub-questions, with `parent_id`). '
        '`items` are question ids in the new order; a question group is `{"g": <group id>, "q": [<ids>]}`.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor', idempotent=True,
    args=args_model('ReorderQuestionsArgs', QuestionOrderIn, survey=SURVEY, section_id=SECTION),
)
def reorder_questions(request, args):
    obj = survey(request, args.survey, role='editor')
    sec = section(request, obj, args.section_id)
    if args.parent_id is not None:
        question(request, obj, args.parent_id)
    items = [{'q': i} if isinstance(i, int) else i for i in args.items]
    svc_questions.reorder(actor(request), sec, args.parent_id, items)
    qs = Question.objects.filter(survey_section=sec, parent_question_id=args.parent_id) \
        if args.parent_id is not None else top_questions(sec)
    return {'questions': [out.question(q) for q in qs.order_by('order_number', 'id')]}


@tool(
    'set_choices',
    title='Set the options of a choice question',
    description=(
        'Replace the options of a choice / multichoice question. Keep an option\'s `code` to keep its '
        'answers; a new option gets a code never used in the survey\'s history. `name` is a string or a '
        '{language: text} map.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor', idempotent=True,
    args=args_model('SetChoicesArgs', ChoicesIn, survey=SURVEY, question_id=QUESTION),
)
def set_choices(request, args):
    obj = survey(request, args.survey, role='editor')
    q = question(request, obj, args.question_id)
    choices = [{k: v for k, v in c.items() if v is not None} for c in args.model_dump()['choices']]
    svc_questions.set_choices(actor(request), q, choices)
    q.refresh_from_db()
    return out.question(q)
