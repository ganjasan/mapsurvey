"""Sections: the pages of a survey."""
from uuid import UUID

from django.db import transaction
from pydantic import Field

from survey.services import sections as svc_sections
from survey.services.common import UNSET

from api import scopes
from api.v1 import forms_bridge, out
from api.v1.schemas import SectionIn, SectionOrderIn

from .common import actor, section, survey
from .registry import args_model, tool

SURVEY = (UUID, Field(description='The survey uuid.'))
SECTION = (int, Field(description='The section id (from get_survey).'))


def _apply(request, obj, body):
    """One PATCH-shaped body through the services, strict (locked fields are
    refused instead of ignored) -- the REST `_apply`, with the MCP actor."""
    act = actor(request)
    data = forms_bridge.section(body)
    translations = forms_bridge.translations(body) if 'translations' in body else UNSET
    rule = forms_bridge.visibility(body)
    if data or translations is not UNSET or rule is not UNSET:
        svc_sections.update(act, obj, data, translations=translations, visibility_rule=rule,
                            partial=True, strict=True)
    if 'map_start' in body or 'use_geolocation' in body:
        start = body.get('map_start', out._map_start(obj))
        svc_sections.set_map(
            act, obj, clear_position=start is None,
            lat=start and start['lat'], lng=start and start['lng'], zoom=start and start['zoom'],
            use_geolocation=body.get('use_geolocation', obj.use_geolocation),
            override_basemap=obj.override_basemap)


def _all(obj):
    return [out.section(s, i) for i, s in enumerate(svc_sections.ordered(obj))]


@tool(
    'create_section',
    title='Add a section',
    description=(
        'Append a section (a page) to the survey; the other fields set it at once. `layout` is "map" (the '
        'page shows the map, for geo questions), "image" (a picture beside the questions, e.g. a welcome '
        'page; the picture is uploaded in the editor, else the survey cover is shown) or "form". '
        '`panel_side` (left|right) and `panel_width` (default|third|half) place the questions on a '
        'computer screen; `content_width` (full|column) and `content_valign` (top|middle) place '
        'the content inside that panel; `keep_panel_open` keeps the questions visible while respondents '
        'place on the map (desktop, map sections). On a live survey this is a structural change: start_unpublished_changes first.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor', args=args_model('CreateSectionArgs', SectionIn, survey=SURVEY),
)
def create_section(request, args):
    obj = survey(request, args.survey, role='editor')
    body = args.model_dump(exclude_unset=True)
    body.pop('survey')
    with transaction.atomic():
        created = svc_sections.create(actor(request), obj)
        if body:
            _apply(request, created, body)
    created.refresh_from_db()
    return out.section(created)


@tool(
    'update_section',
    title='Update a section',
    description=(
        'Change the fields you name. On a live survey wording (title, subheading, next_label, translations) '
        'and the layout (layout, panel_side, panel_width, content_width, content_valign, keep_panel_open) are applied in place; the code and the '
        'visibility rule are structure (draft_required).'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor', idempotent=True,
    args=args_model('UpdateSectionArgs', SectionIn, survey=SURVEY, section_id=SECTION),
)
def update_section(request, args):
    obj = survey(request, args.survey, role='editor')
    sec = section(request, obj, args.section_id)
    body = args.model_dump(exclude_unset=True)
    body.pop('survey')
    body.pop('section_id')
    with transaction.atomic():
        _apply(request, sec, body)
    sec.refresh_from_db()
    return out.section(sec)


@tool(
    'delete_section',
    title='Delete a section',
    description=(
        'Delete a section with its questions. Answers to them go too: the first call answers answers_at_risk '
        'with the count; repeat with `acknowledge_answer_loss: true` only after the user agreed.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor', destructive=True,
    args=args_model('DeleteSectionArgs', survey=SURVEY, section_id=SECTION,
                    acknowledge_answer_loss=(bool, Field(False))),
)
def delete_section(request, args):
    obj = survey(request, args.survey, role='editor')
    sec = section(request, obj, args.section_id)
    svc_sections.delete(actor(request), sec, acknowledge_answer_loss=args.acknowledge_answer_loss)
    return {'deleted': args.section_id, 'sections': _all(obj)}


@tool(
    'reorder_sections',
    title='Reorder sections',
    description='The new order of the pages; list every section id of the survey exactly once.',
    scope=scopes.SURVEYS_WRITE, role='editor', idempotent=True,
    args=args_model('ReorderSectionsArgs', SectionOrderIn, survey=SURVEY),
)
def reorder_sections(request, args):
    obj = survey(request, args.survey, role='editor')
    svc_sections.reorder(actor(request), obj, args.section_ids, strict=True)
    return {'sections': _all(obj)}
