"""Distribution: share information, QR codes, tracked (campaign) links and the
embed allow-list (change api-v2-distribution, #410; epic #408).

The work is `survey/share.py`, request-free and shared with the MCP tools;
these routes check scope, role and Pro through `deps` and map `ShareError` to
the envelope.
"""
from typing import List, Literal, Optional
from uuid import UUID

from django.http import HttpResponse
from ninja import Router
from pydantic import Field

from survey import share as svc_share
from survey.permissions import SURVEY_ROLE_RANK, get_effective_survey_role

from .. import scopes
from ..errors import LIMIT_REACHED, NOT_SHAREABLE, ApiError
from . import deps
from .auth import Bearer
from .docs import errors
from .schemas import In

router = Router(tags=['Share'])

READ = Bearer(scopes.SURVEYS_READ)
WRITE = Bearer(scopes.SURVEYS_WRITE)


class TrackedLinkIn(In):
    utm_source: str = Field(min_length=1, max_length=100, description='Where the link is posted, e.g. "newsletter".')
    utm_medium: str = Field('', max_length=100, description='e.g. "email", "poster", "social".')
    utm_campaign: str = Field('', max_length=100, description='e.g. "spring-2027".')


class EmbedHostsIn(In):
    hosts: List[str] = Field(description='Sites allowed to embed the survey, e.g. ["example.org", "*.city.gov"]; '
                                         'empty = any site.')


def raise_share_error(exc):
    raise ApiError(exc.status, exc.code, exc.message, **({'fields': exc.fields} if exc.fields else {}))


def can_see_test_link(request, survey):
    role = get_effective_survey_role(request.principal.user, survey)
    return SURVEY_ROLE_RANK.get(role, -1) >= SURVEY_ROLE_RANK['editor']


@router.get('/surveys/{uuid}/share', auth=READ, openapi_extra=errors())
def share(request, uuid: UUID):
    """How to send the survey out: its link, the public results link, the embed
    snippet and allowed hosts -- once it is published (`shareable`). In testing,
    editors also get the test link with its token."""
    survey = deps.survey(request, uuid)
    return svc_share.share_info(survey, can_see_test_link=can_see_test_link(request, survey))


@router.get('/surveys/{uuid}/share/qr.{fmt}', auth=READ, openapi_extra=errors(codes=(NOT_SHAREABLE,)))
def qr(request, uuid: UUID, fmt: Literal['svg', 'png'], size: int = svc_share.QR_SIZE_DEFAULT,
       link: Optional[int] = None):
    """A QR code of the survey link (or of tracked link `link`) for posters and
    flyers. `size` is pixels per module, 1-40."""
    survey = deps.survey(request, uuid)
    try:
        url = svc_share.qr_target(survey, link)
    except svc_share.ShareError as exc:
        raise_share_error(exc)
    body, content_type = svc_share.qr_image(url, fmt, size)
    response = HttpResponse(body, content_type=content_type)
    response['Cache-Control'] = 'private, max-age=300'
    return response


@router.get('/surveys/{uuid}/tracked-links', auth=READ, openapi_extra=errors())
def tracked_links(request, uuid: UUID):
    """Campaign links -- the survey link with UTM parameters -- with how many
    responses started and completed through each."""
    return {'items': svc_share.list_links(deps.survey(request, uuid))}


@router.post('/surveys/{uuid}/tracked-links', auth=WRITE, openapi_extra=errors(codes=(LIMIT_REACHED,)))
def create_tracked_link(request, uuid: UUID, body: TrackedLinkIn):
    """Add a campaign link (editor role). At most 200 per survey."""
    survey = deps.survey(request, uuid, role='editor')
    try:
        return svc_share.create_link(deps.actor(request), survey, body.utm_source, body.utm_medium,
                                     body.utm_campaign)
    except svc_share.ShareError as exc:
        raise_share_error(exc)


@router.delete('/surveys/{uuid}/tracked-links/{link_id}', auth=WRITE, openapi_extra=errors())
def delete_tracked_link(request, uuid: UUID, link_id: int):
    """Remove a campaign link (editor role). Responses that came through it keep their source."""
    survey = deps.survey(request, uuid, role='editor')
    try:
        svc_share.delete_link(deps.actor(request), survey, link_id)
    except svc_share.ShareError as exc:
        raise_share_error(exc)
    return {'deleted': link_id}


@router.put('/surveys/{uuid}/share/embed-hosts', auth=WRITE, openapi_extra=errors(400))
def embed_hosts(request, uuid: UUID, body: EmbedHostsIn):
    """Which sites may embed the survey (editor role); an empty list lets any site."""
    survey = deps.survey(request, uuid, role='editor')
    try:
        return {'hosts': svc_share.set_embed_hosts(deps.actor(request), survey, body.hosts)}
    except svc_share.ShareError as exc:
        raise_share_error(exc)
