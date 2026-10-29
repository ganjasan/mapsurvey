"""/surveys: list, create, read, settings, delete, and the lifecycle."""
from typing import Optional
from uuid import UUID

from django.db import transaction
from django.db.models import Q
from ninja import Router, Status

from survey.models import Membership, SurveyHeader
from survey.permissions import ORG_ROLE_RANK
from survey.services import publishing as svc_publishing
from survey.services import surveys as svc_surveys

from .. import gates, limits, scopes
from ..errors import NOT_FOUND, FORBIDDEN_ROLE, ApiError, not_found
from . import deps, forms_bridge, out
from .auth import Bearer
from .docs import errors, list_errors
from .pagination import page
from .schemas import (
    DraftPublishIn, PublishIn, SurveyCreateIn, SurveyDetailOut, SurveyList, SurveyOut, SurveyPatchIn,
)

router = Router(tags=['Surveys'])

READ = Bearer(scopes.SURVEYS_READ)
WRITE = Bearer(scopes.SURVEYS_WRITE)
PUBLISH = Bearer(scopes.SURVEYS_PUBLISH)
DELETE = Bearer(scopes.SURVEYS_DELETE)


def _visible_surveys(principal):
    """Canonical, untrashed surveys in the caller's Pro workspaces that the
    caller has a role on -- the same rule `get_effective_survey_role` applies:
    org owner/admin/viewer see every survey, an org editor only the ones they
    collaborate on."""
    allowed, hidden = gates.pro_organizations(principal)
    memberships = {m.organization_id: m.role for m in Membership.objects.filter(
        user=principal.user, organization__in=allowed)}
    broad = [org_id for org_id, role in memberships.items() if role in ('owner', 'admin', 'viewer')]
    qs = (SurveyHeader.objects
          .filter(organization_id__in=list(memberships), deleted_at__isnull=True,
                  published_version__isnull=True, canonical_survey__isnull=True)
          .filter(Q(organization_id__in=broad) | Q(collaborators__user=principal.user))
          .select_related('organization', 'published_version')
          .distinct())
    return qs, hidden


@router.get('/surveys', response=SurveyList, auth=READ, openapi_extra=list_errors())
def list_surveys(request, cursor: Optional[str] = None, limit: int = 50):
    """Your surveys across the workspaces whose plan includes the API, newest first."""
    qs, hidden = _visible_surveys(request.principal)
    items, next_cursor = page(qs, f'surveys:{request.principal.user.pk}', cursor, limit)
    return {'items': [out.survey(s) for s in items], 'next_cursor': next_cursor, 'hidden_by_plan': hidden}


def _workspace(principal, slug):
    """The workspace a new survey goes into: the one named, else the token's
    binding, else the caller's only membership."""
    memberships = Membership.objects.filter(user=principal.user).select_related('organization')
    if principal.organization is not None:
        memberships = memberships.filter(organization=principal.organization)
    if slug:
        memberships = memberships.filter(organization__slug=slug)
    memberships = list(memberships)
    if not memberships:
        raise not_found() if slug else ApiError(
            422, 'validation', 'Name a workspace.', fields={'workspace': ['You belong to no workspace.']})
    if len(memberships) > 1:
        raise ApiError(422, 'validation', 'Name a workspace.',
                       fields={'workspace': ['You belong to several workspaces; name one by its slug.']})
    membership = memberships[0]
    if ORG_ROLE_RANK.get(membership.role, -1) < ORG_ROLE_RANK['editor']:
        raise ApiError(403, FORBIDDEN_ROLE, 'Creating surveys needs the editor role in the workspace.',
                       role='editor')
    gates.require_pro_api(principal, membership.organization)
    return membership.organization


class _Start:
    def __init__(self, lat, lng, zoom):
        self.lat, self.lng, self.zoom, self.source = lat, lng, zoom, 'api'


@router.post('/surveys', response={201: SurveyDetailOut}, auth=WRITE, openapi_extra=errors(409))
def create_survey(request, payload: SurveyCreateIn):
    """A new empty survey with one section, owned by you."""
    p = request.principal
    organization = _workspace(p, payload.workspace)
    limits.hit(p, 'survey_create')
    start = _Start(**payload.map_start.dict()) if payload.map_start else None
    survey = svc_surveys.create_blank(deps.actor(request), organization, name=payload.name,
                                      language=payload.language, start=start, surface='api')
    return Status(201, out.survey_detail(survey))


@router.get('/surveys/{uuid}', response=SurveyDetailOut, auth=READ, openapi_extra=errors())
def get_survey(request, uuid: UUID):
    return out.survey_detail(deps.survey(request, uuid))


SETTINGS_FIELDS = ('name', 'redirect_url', 'languages', 'visibility', 'basemaps', 'default_basemap',
                   'show_branding')


@router.patch('/surveys/{uuid}', response=SurveyDetailOut, auth=WRITE, openapi_extra=errors(409))
def patch_survey(request, uuid: UUID, payload: SurveyPatchIn):
    """Settings, the thanks page and the map start. Settings and the map need
    the owner role, like the editor; the thanks page the editor role."""
    body = payload.dict(exclude_unset=True)
    owner_fields = [k for k in body if k != 'thanks_html']
    survey = deps.survey(request, uuid, role='owner' if owner_fields else 'editor')
    actor = deps.actor(request)
    with transaction.atomic():
        settings_data = forms_bridge.survey_settings(body)
        if settings_data:
            svc_surveys.update_settings(actor, survey, settings_data, partial=True)
        if 'thanks_html' in body:
            survey.refresh_from_db()
            svc_surveys.set_thanks(actor, survey, body['thanks_html'] or {},
                                   languages=list((body['thanks_html'] or {}).keys()))
        if 'map_start' in body or 'use_geolocation' in body:
            start = body.get('map_start', out._map_start(survey))
            svc_surveys.set_map_position(
                actor, survey, clear_position=start is None,
                lat=start and start['lat'], lng=start and start['lng'], zoom=start and start['zoom'],
                use_geolocation=body.get('use_geolocation', survey.use_geolocation))
    survey.refresh_from_db()
    return out.survey_detail(survey)


@router.delete('/surveys/{uuid}', response={204: None}, auth=DELETE, openapi_extra=errors())
def delete_survey(request, uuid: UUID):
    """Move the survey to the trash; it can be restored in the editor for 30 days."""
    survey = deps.survey(request, uuid, role='owner')
    limits.hit(request.principal, 'survey_delete')
    svc_surveys.trash(deps.actor(request), survey)
    return Status(204, None)


@router.post('/surveys/{uuid}/publish', response=SurveyOut, auth=PUBLISH,
             openapi_extra=errors(409, codes=('translation_gaps', 'transition_refused', 'email_unconfirmed', 'conflict')))
def publish_survey(request, uuid: UUID, payload: PublishIn = None):
    """Publish. `review: "pending"` means content screening is holding the
    survey: respondents see an unavailable page until it is reviewed."""
    payload = payload or PublishIn()
    survey = deps.survey(request, uuid, role='owner')
    result = svc_publishing.transition(
        deps.actor(request), survey, 'published',
        acknowledge_translation_gaps=payload.acknowledge_translation_gaps,
        clear_test_data=payload.clear_test_data, refuse_draft_copy=True)
    return out.survey(result.survey)


@router.post('/surveys/{uuid}/close', response=SurveyOut, auth=PUBLISH,
             openapi_extra=errors(409, codes=('transition_refused', 'conflict')))
def close_survey(request, uuid: UUID):
    """Stop collecting answers; the survey stays readable to you."""
    survey = deps.survey(request, uuid, role='owner')
    svc_publishing.transition(deps.actor(request), survey, 'closed', refuse_draft_copy=True)
    return out.survey(survey)


@router.post('/surveys/{uuid}/draft', response={201: SurveyOut}, auth=WRITE,
             openapi_extra=errors(409, codes=('transition_refused', 'conflict')))
def create_draft(request, uuid: UUID):
    """Start unpublished changes on a published or closed survey. Edit the
    returned uuid; respondents keep the live survey until you publish them."""
    survey = deps.survey(request, uuid, role='editor')
    draft = svc_publishing.create_draft(deps.actor(request), survey)
    return Status(201, out.survey(draft))


def _draft_of(request, uuid, role):
    survey = deps.survey(request, uuid, role=role)
    draft = survey if survey.is_draft_copy else survey.get_draft_copy()
    if draft is None:
        raise ApiError(404, NOT_FOUND, 'This survey has no unpublished changes.')
    return draft


@router.post('/surveys/{uuid}/draft/publish', response=SurveyOut, auth=PUBLISH,
             openapi_extra=errors(409, codes=('translation_gaps', 'incompatible_draft', 'email_unconfirmed', 'conflict')))
def publish_draft(request, uuid: UUID, payload: DraftPublishIn = None):
    """Publish the unpublished changes as a new version of the live survey."""
    payload = payload or DraftPublishIn()
    draft = _draft_of(request, uuid, 'owner')
    result = svc_publishing.publish_draft(
        deps.actor(request), draft, force=payload.force,
        acknowledge_translation_gaps=payload.acknowledge_translation_gaps)
    return out.survey(result.survey)


@router.delete('/surveys/{uuid}/draft', response={204: None}, auth=WRITE, openapi_extra=errors())
def discard_draft(request, uuid: UUID):
    """Throw the unpublished changes away; the live survey is untouched."""
    draft = _draft_of(request, uuid, 'owner')
    svc_publishing.discard_draft(deps.actor(request), draft)
    return Status(204, None)


# Public names for the MCP server (change mcp-server, #306), which runs the
# same glue over the same services with its own actor surface.
visible_surveys = _visible_surveys
workspace_for = _workspace
MapStart = _Start
draft_of = _draft_of

