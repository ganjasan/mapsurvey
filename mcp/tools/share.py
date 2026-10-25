"""Sending a survey out: its links, a QR code shown in the chat, campaign
(tracked) links and the sites allowed to embed it (change api-v2-distribution,
#410 PR 2). Every tool calls `survey/share.py`, the functions the REST routes
call, so the URLs are the same everywhere.
"""
from typing import List, Optional
from uuid import UUID

from pydantic import Field

from survey import share as svc_share

from api import scopes
from api.v1.share import can_see_test_link, raise_share_error

from .common import actor, survey
from .registry import WithImages, args_model, tool

SURVEY = (UUID, Field(description='The survey uuid (from list_surveys).'))
SurveyRef = args_model('ShareSurveyRef', survey=SURVEY)


@tool(
    'get_share_links',
    title='Get the links to share a survey',
    description=(
        'How to send the survey out: its public link, the public results link (if that page is published), '
        'the HTML snippet to embed it in a website and the sites allowed to embed it. Only a published '
        'survey can be shared (`shareable`); otherwise `reason` says why. In testing, editors also get the '
        'test link.'
    ),
    scope=scopes.SURVEYS_READ, role='viewer', read_only=True, idempotent=True, args=SurveyRef,
)
def get_share_links(request, args):
    obj = survey(request, args.survey)
    return svc_share.share_info(obj, can_see_test_link=can_see_test_link(request, obj))


@tool(
    'get_qr_code',
    title='Get a QR code',
    description=(
        'A QR code of the survey link -- or of one tracked link -- as an image the person can save for a '
        'poster or flyer. Only for a published survey.'
    ),
    scope=scopes.SURVEYS_READ, role='viewer', read_only=True, idempotent=True,
    args=args_model(
        'QrArgs', survey=SURVEY,
        link_id=(Optional[int], Field(None, description='A tracked link id from list_tracked_links.')),
        size=(int, Field(8, ge=1, le=40, description='Pixels per module; 8 gives about 300 px.')),
    ),
)
def get_qr_code(request, args):
    obj = survey(request, args.survey)
    try:
        url = svc_share.qr_target(obj, args.link_id)
    except svc_share.ShareError as exc:
        raise_share_error(exc)
    png, mime = svc_share.qr_image(url, 'png', args.size)
    return WithImages({'url': url, 'format': 'png'}, ((png, mime),))


@tool(
    'list_tracked_links',
    title='List tracked links',
    description=(
        'Campaign links -- the survey link with UTM parameters, one per place it is posted -- with how many '
        'responses started and completed through each.'
    ),
    scope=scopes.SURVEYS_READ, role='viewer', read_only=True, idempotent=True, args=SurveyRef,
)
def list_tracked_links(request, args):
    return {'items': svc_share.list_links(survey(request, args.survey))}


@tool(
    'create_tracked_link',
    title='Create a tracked link',
    description=(
        'A campaign link for one place the survey is posted, e.g. utm_source "newsletter", utm_medium '
        '"email", utm_campaign "spring-2027". Responses through it are counted separately. Needs the editor '
        'role; at most 200 per survey.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor',
    args=args_model(
        'TrackedLinkArgs', survey=SURVEY,
        utm_source=(str, Field(min_length=1, max_length=100)),
        utm_medium=(str, Field('', max_length=100)),
        utm_campaign=(str, Field('', max_length=100)),
    ),
)
def create_tracked_link(request, args):
    obj = survey(request, args.survey, role='editor')
    try:
        return svc_share.create_link(actor(request), obj, args.utm_source, args.utm_medium, args.utm_campaign)
    except svc_share.ShareError as exc:
        raise_share_error(exc)


@tool(
    'delete_tracked_link',
    title='Delete a tracked link',
    description='Remove a campaign link. Responses that came through it keep their source. Needs the editor role.',
    scope=scopes.SURVEYS_WRITE, role='editor', idempotent=True,
    args=args_model('DeleteTrackedLinkArgs', survey=SURVEY,
                    link_id=(int, Field(description='A tracked link id from list_tracked_links.'))),
)
def delete_tracked_link(request, args):
    obj = survey(request, args.survey, role='editor')
    try:
        svc_share.delete_link(actor(request), obj, args.link_id)
    except svc_share.ShareError as exc:
        raise_share_error(exc)
    return {'deleted': args.link_id}


@tool(
    'set_embed_hosts',
    title='Set the sites allowed to embed',
    description=(
        'Which websites may show the survey in a frame, e.g. ["example.org", "*.city.gov"]. An empty list '
        'lets any site embed it. Replaces the current list. Needs the editor role.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor', idempotent=True,
    args=args_model('EmbedHostsArgs', survey=SURVEY, hosts=(List[str], Field())),
)
def set_embed_hosts(request, args):
    obj = survey(request, args.survey, role='editor')
    try:
        return {'hosts': svc_share.set_embed_hosts(actor(request), obj, args.hosts)}
    except svc_share.ShareError as exc:
        raise_share_error(exc)
