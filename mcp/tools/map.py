"""Where layers show and the study area (change map-layers-study-area). Every write goes through
`survey.services.placements` / `survey.services.study_area`, the paths the editor's Map card, the
study area editor and REST v1 take; the shapes are REST's (`api.v1.map`). All of it is reversible,
so nothing here asks for `confirm`.
"""
from typing import List
from uuid import UUID

from pydantic import Field

from survey.layers import placements_for
from survey.services import placements as svc_placements
from survey.services import study_area as svc_area

from api import scopes
from api.v1.map import PlacementIn, StudyAreaIn, StudyAreaPatchIn

from .common import actor, survey
from .registry import args_model, tool

SURVEY = (UUID, Field(description='The survey uuid (from list_surveys).'))
LAYER = (int, Field(description='A layer id from list_layers.'))


def _placements(obj):
    return {'items': [svc_placements.describe(p, obj) for p in placements_for(obj)]}


@tool(
    'place_layer',
    title='Show a layer on the map',
    description=(
        'Put a layer of the survey on its maps, or change where it shows: `scope` "all" = every section '
        'with a map, now and later (what a creator usually wants), or "sections" with `sections` = section '
        'codes ("S2", or "S2#1" for the second section with that code). A layer with no placement is on no '
        'map. Applies to a published survey at once. Needs the editor role.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor', idempotent=True,
    args=args_model('PlaceLayerArgs', PlacementIn, survey=SURVEY, layer_id=LAYER),
)
def place_layer(request, args):
    obj = survey(request, args.survey, role='editor')
    placement = svc_placements.place(actor(request), obj, args.layer_id, args.scope, args.sections)
    return svc_placements.describe(placement, obj)


@tool(
    'unplace_layer',
    title='Take a layer off the map',
    description='Take a layer off every map of the survey; it stays in the survey and in Data. Needs the editor role.',
    scope=scopes.SURVEYS_WRITE, role='editor', idempotent=True,
    args=args_model('UnplaceLayerArgs', survey=SURVEY, layer_id=LAYER),
)
def unplace_layer(request, args):
    obj = survey(request, args.survey, role='editor')
    return {'removed': svc_placements.unplace(actor(request), obj, args.layer_id)}


@tool(
    'list_placements',
    title='Where layers show',
    description='Each placed layer with its scope and sections, bottom of the map first.',
    scope=scopes.SURVEYS_READ, role='viewer', read_only=True, idempotent=True,
    args=args_model('ListPlacementsArgs', survey=SURVEY),
)
def list_placements(request, args):
    return _placements(survey(request, args.survey))


@tool(
    'reorder_placements',
    title='Reorder layers on the map',
    description='The stacking order of the placed layers: every placed layer id, bottom first. Needs the editor role.',
    scope=scopes.SURVEYS_WRITE, role='editor', idempotent=True,
    args=args_model('ReorderPlacementsArgs', survey=SURVEY, layer_ids=(List[int], Field())),
)
def reorder_placements(request, args):
    obj = survey(request, args.survey, role='editor')
    svc_placements.reorder(actor(request), obj, args.layer_ids)
    return _placements(obj)


@tool(
    'get_study_area',
    title='Get the study area',
    description=(
        'The area the survey is about: its outline (GeoJSON), where it came from, whether the map is '
        'greyed outside, whether map answers outside are refused, the message respondents then see, '
        'its size in km² — or null.'
    ),
    scope=scopes.SURVEYS_READ, role='viewer', read_only=True, idempotent=True,
    args=args_model('GetStudyAreaArgs', survey=SURVEY),
)
def get_study_area(request, args):
    obj = survey(request, args.survey)
    return {'study_area': svc_area.describe(svc_area.get(obj))}


@tool(
    'set_study_area',
    title='Set the study area',
    description=(
        'Create or replace the study area from a Polygon or MultiPolygon in WGS 84 (made valid, simplified '
        'to 2,000 points). The respondent map opens on it; `fog` greys the outside (on for a new area); '
        '`refuse_outside` refuses map answers outside it, with `message` per language. Not a layer. Applies '
        'to a published survey at once. Needs the editor role.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor', idempotent=True,
    args=args_model('SetStudyAreaArgs', StudyAreaIn, survey=SURVEY),
)
def set_study_area(request, args):
    obj = survey(request, args.survey, role='editor')
    svc_area.set_area(actor(request), obj, args.geometry, source=args.source, place_name=args.place_name or '',
                      fog=args.fog, refuse_outside=args.refuse_outside, message=args.message)
    return {'study_area': svc_area.describe(svc_area.get(obj))}


@tool(
    'update_study_area',
    title='Change the study area rules',
    description='Change the fog, the refusal of answers outside, or its message. Needs the editor role.',
    scope=scopes.SURVEYS_WRITE, role='editor', idempotent=True,
    args=args_model('UpdateStudyAreaArgs', StudyAreaPatchIn, survey=SURVEY),
)
def update_study_area(request, args):
    obj = survey(request, args.survey, role='editor')
    fields = args.model_dump(exclude_unset=True, exclude={'survey'})
    svc_area.update_settings(actor(request), obj, fog=fields.get('fog'), refuse_outside=fields.get('refuse_outside'),
                             message=fields.get('message'))
    return {'study_area': svc_area.describe(svc_area.get(obj))}


@tool(
    'clear_study_area',
    title='Remove the study area',
    description='Remove the study area: the map opens as before and nothing is refused. Needs the editor role.',
    scope=scopes.SURVEYS_WRITE, role='editor', idempotent=True,
    args=args_model('ClearStudyAreaArgs', survey=SURVEY),
)
def clear_study_area(request, args):
    obj = survey(request, args.survey, role='editor')
    return {'removed': svc_area.clear(actor(request), obj)}
