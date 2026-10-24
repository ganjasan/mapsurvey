"""Surveys: list, read, create, settings, delete, and the lifecycle -- the
`/surveys` routes of REST API v1 as tools, through the same glue and the same
services."""
from typing import Optional
from uuid import UUID

from django.db import transaction
from django.db.models import F, Q
from pydantic import Field

from survey.analytics import nonempty_sessions
from survey.models import Question, SurveyHeader, SurveySession
from survey.services import publishing as svc_publishing
from survey.services import sections as svc_sections
from survey.services import surveys as svc_surveys
from survey.versioning import canonical_of

from api import limits, scopes
from api.v1 import forms_bridge, out
from api.v1.pagination import page
from api.v1.schemas import DraftPublishIn, PublishIn, SurveyCreateIn, SurveyPatchIn
from api.v1.surveys import MapStart, draft_of, visible_surveys, workspace_for

from ..errors import confirmation_required, has_responses
from .common import actor, survey
from .registry import args_model, tool

SURVEY = (UUID, Field(description='The survey uuid (from list_surveys or create_survey).'))
CONFIRM = (bool, Field(False, description='Set to true only after the user confirmed this action in the conversation.'))

SurveyRef = args_model('SurveyRef', survey=SURVEY)


# ─── Reads ───────────────────────────────────────────────────────────────────

@tool(
    'list_surveys',
    title='List surveys',
    description=(
        'Your surveys across the workspaces whose plan includes the API, newest first. `hidden_by_plan` '
        'counts workspaces of yours on the Free plan, whose surveys are not listed.'
    ),
    scope=scopes.SURVEYS_READ, role='viewer', read_only=True, idempotent=True,
    args=args_model(
        'ListSurveysArgs',
        cursor=(Optional[str], Field(None, description='`next_cursor` of the previous page.')),
        limit=(int, Field(50, ge=1, le=200)),
    ),
)
def list_surveys(request, args):
    qs, hidden = visible_surveys(request.principal)
    items, next_cursor = page(qs, f'surveys:{request.principal.user.pk}', args.cursor, args.limit)
    return {'items': [out.survey(s) for s in items], 'next_cursor': next_cursor, 'hidden_by_plan': hidden}


@tool(
    'get_survey',
    title='Get a survey',
    description=(
        'The whole survey in one call: settings, then every section in respondent order with all of its '
        'questions (sub-questions carry `parent_id`). Ids from here are what the editing tools take.'
    ),
    scope=scopes.SURVEYS_READ, role='viewer', read_only=True, idempotent=True, args=SurveyRef,
)
def get_survey(request, args):
    obj = survey(request, args.survey)
    sections = []
    for position, section in enumerate(svc_sections.ordered(obj)):
        # Top level first (NULL parent), then the pop-ups' sub-questions.
        questions = (Question.objects.filter(survey_section=section)
                     .order_by(F('parent_question_id_id').asc(nulls_first=True), 'order_number', 'id'))
        sections.append({**out.section(section, position), 'questions': [out.question(q) for q in questions]})
    return {**out.survey_detail(obj), 'sections': sections}


# ─── Create, settings, delete ────────────────────────────────────────────────

@tool(
    'create_survey',
    title='Create a survey',
    description=(
        'A new empty survey with one section, owned by you. Name the workspace by its slug when you belong '
        'to several (get_me lists them). Add sections and questions next; the survey stays unpublished until '
        'publish_survey.'
    ),
    scope=scopes.SURVEYS_WRITE, role='workspace editor', args=args_model('CreateSurveyArgs', SurveyCreateIn),
)
def create_survey(request, args):
    p = request.principal
    organization = workspace_for(p, args.workspace)
    limits.hit(p, 'survey_create')
    start = MapStart(**args.map_start.model_dump()) if args.map_start else None
    obj = svc_surveys.create_blank(actor(request), organization, name=args.name, language=args.language,
                                   start=start, surface='mcp')
    return out.survey_detail(obj)


@tool(
    'update_survey',
    title='Update survey settings',
    description=(
        'Change the fields you name: name, languages, redirect_url ("#" for the built-in thanks page), '
        'visibility, basemaps, branding, the thanks page per language, the map start. Settings need the '
        'owner role; the thanks page the editor role.'
    ),
    scope=scopes.SURVEYS_WRITE, role='owner', idempotent=True,
    args=args_model('UpdateSurveyArgs', SurveyPatchIn, survey=SURVEY),
)
def update_survey(request, args):
    body = args.model_dump(exclude_unset=True)
    body.pop('survey')
    owner_fields = [k for k in body if k != 'thanks_html']
    obj = survey(request, args.survey, role='owner' if owner_fields else 'editor')
    act = actor(request)
    with transaction.atomic():
        settings_data = forms_bridge.survey_settings(body)
        if settings_data:
            svc_surveys.update_settings(act, obj, settings_data, partial=True)
        if 'thanks_html' in body:
            obj.refresh_from_db()
            svc_surveys.set_thanks(act, obj, body['thanks_html'] or {},
                                   languages=list((body['thanks_html'] or {}).keys()))
        if 'map_start' in body or 'use_geolocation' in body:
            start = body.get('map_start', out._map_start(obj))
            svc_surveys.set_map_position(
                act, obj, clear_position=start is None,
                lat=start and start['lat'], lng=start and start['lng'], zoom=start and start['zoom'],
                use_geolocation=body.get('use_geolocation', obj.use_geolocation))
    obj.refresh_from_db()
    return out.survey_detail(obj)


def answered_external_sessions(obj):
    """Respondents' answered sessions on the survey and all of its versions."""
    canonical = canonical_of(obj)
    versions = SurveyHeader.objects.filter(Q(pk=canonical.pk) | Q(canonical_survey=canonical))
    qs = SurveySession.objects.filter(survey__in=versions, opened_by_kind='external', is_deleted=False)
    return nonempty_sessions(qs).count()


@tool(
    'delete_survey',
    title='Delete a survey',
    description=(
        'Move a survey to the trash (the owner can restore it in the editor for 30 days). Needs `confirm: '
        'true` after the user agreed. Refused when respondents have already answered: that deletion is '
        'done in the editor, where the answers are shown first. Unpublished changes are discarded with '
        'discard_unpublished_changes instead.'
    ),
    scope=scopes.SURVEYS_DELETE, role='owner', destructive=True, confirm=True,
    args=args_model('DeleteSurveyArgs', survey=SURVEY, confirm=CONFIRM),
)
def delete_survey(request, args):
    obj = survey(request, args.survey, role='owner')
    if not obj.is_draft_copy:
        if not args.confirm:
            raise confirmation_required('Deleting a survey')
        count = answered_external_sessions(obj)
        if count:
            raise has_responses(count)
    limits.hit(request.principal, 'survey_delete')
    svc_surveys.trash(actor(request), obj)
    return {'uuid': obj.uuid, 'name': obj.name, 'deleted': True, 'restorable_in_editor_days': 30}


# ─── Lifecycle ───────────────────────────────────────────────────────────────

@tool(
    'publish_survey',
    title='Publish a survey',
    description=(
        'Make the survey live for respondents. Needs `confirm: true` after the user agreed. `review: '
        '"pending"` in the result means content screening is holding it until a human looks; '
        'translation_gaps asks you to confirm publishing with missing translations.'
    ),
    scope=scopes.SURVEYS_PUBLISH, role='owner', destructive=True, confirm=True,
    args=args_model('PublishSurveyArgs', PublishIn, survey=SURVEY, confirm=CONFIRM),
)
def publish_survey(request, args):
    obj = survey(request, args.survey, role='owner')
    if not args.confirm:
        raise confirmation_required('Publishing a survey')
    result = svc_publishing.transition(
        actor(request), obj, 'published',
        acknowledge_translation_gaps=args.acknowledge_translation_gaps,
        clear_test_data=args.clear_test_data, refuse_draft_copy=True)
    return out.survey(result.survey)


@tool(
    'close_survey',
    title='Close a survey',
    description='Stop collecting answers; the survey stays readable to its collaborators.',
    scope=scopes.SURVEYS_PUBLISH, role='owner', idempotent=True, args=SurveyRef,
)
def close_survey(request, args):
    obj = survey(request, args.survey, role='owner')
    svc_publishing.transition(actor(request), obj, 'closed', refuse_draft_copy=True)
    return out.survey(obj)


@tool(
    'start_unpublished_changes',
    title='Start unpublished changes',
    description=(
        'On a published or closed survey, structural edits (adding, deleting, reordering, changing a '
        'question type) answer draft_required. Call this to get an editable copy -- "unpublished changes" '
        '-- and edit the returned uuid; respondents keep the live survey until '
        'publish_unpublished_changes.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor', args=SurveyRef,
)
def start_unpublished_changes(request, args):
    obj = survey(request, args.survey, role='editor')
    return out.survey(svc_publishing.create_draft(actor(request), obj))


@tool(
    'publish_unpublished_changes',
    title='Publish unpublished changes',
    description=(
        'Replace the live survey with its unpublished changes as a new version. Needs `confirm: true` after '
        'the user agreed. incompatible_draft means the changes conflict with collected answers; repeat with '
        '`force: true` only if the user accepts that.'
    ),
    scope=scopes.SURVEYS_PUBLISH, role='owner', destructive=True, confirm=True,
    args=args_model('PublishChangesArgs', DraftPublishIn, survey=SURVEY, confirm=CONFIRM),
)
def publish_unpublished_changes(request, args):
    draft = draft_of(request, args.survey, 'owner')
    if not args.confirm:
        raise confirmation_required('Publishing unpublished changes')
    result = svc_publishing.publish_draft(actor(request), draft, force=args.force,
                                          acknowledge_translation_gaps=args.acknowledge_translation_gaps)
    return out.survey(result.survey)


@tool(
    'discard_unpublished_changes',
    title='Discard unpublished changes',
    description='Throw the unpublished changes away; the live survey is untouched.',
    scope=scopes.SURVEYS_WRITE, role='owner', destructive=True, args=SurveyRef,
)
def discard_unpublished_changes(request, args):
    draft = draft_of(request, args.survey, 'owner')
    live = draft.published_version
    svc_publishing.discard_draft(actor(request), draft)
    return {'discarded': draft.uuid, 'live_survey': live.uuid if live is not None else None}
