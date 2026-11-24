"""Where layers show and the study area (change map-layers-study-area, specs map-layer-placement and
survey-study-area "… writable through every surface").

Every write goes through `survey.services.placements` and `survey.services.study_area`, the paths
the editor's Map card and study area editor take; a refusal is the service's `ValidationFailed`,
answered 422 by the API's one error envelope. Both are safe edits: applied in place on a published
survey, never unpublished changes. Writes need the `editor` role.
"""
from typing import Any, Dict, List, Optional
from uuid import UUID

from ninja import Router
from pydantic import Field

from survey.services import placements as svc_placements
from survey.services import study_area as svc_area

from .. import scopes
from . import deps
from .auth import Bearer
from .docs import errors
from .schemas import In

router = Router(tags=['Map'])

READ = Bearer(scopes.SURVEYS_READ)
WRITE = Bearer(scopes.SURVEYS_WRITE)


class PlacementIn(In):
    scope: str = Field('all', description='`all` — every section with a map, now and later — or `sections`.')
    sections: List[str] = Field(default_factory=list, description='`sections` scope: section references, '
                                '`<code>` or `<code>#<n>` (the n-th section of that code, from 0).')


class PlacementOrderIn(In):
    layer_ids: List[int] = Field(description='Every placed layer id, bottom of the map first.')


class StudyAreaIn(In):
    geometry: Dict[str, Any] = Field(description='A Polygon or MultiPolygon in WGS 84 (a Feature is accepted); '
                                     'made valid and simplified to 2,000 points.')
    source: str = Field('draw', description='place, upload, layer or draw.')
    place_name: Optional[str] = Field(None, max_length=255)
    fog: Optional[bool] = Field(None, description='Grey out the map outside (on for a new area).')
    refuse_outside: Optional[bool] = Field(None, description='Refuse map answers outside the area.')
    message: Optional[Dict[str, str]] = Field(None, description='The refusal message per language code.')


class StudyAreaPatchIn(In):
    fog: Optional[bool] = None
    refuse_outside: Optional[bool] = None
    message: Optional[Dict[str, str]] = Field(None, description='The refusal message per language code.')


def _placements(survey):
    from survey.layers import placements_for
    return {'items': [svc_placements.describe(p, survey) for p in placements_for(survey)]}


@router.get('/surveys/{uuid}/placements', auth=READ, openapi_extra=errors())
def list_placements(request, uuid: UUID):
    """Where each layer shows, bottom of the map first. A layer with no placement is on no map."""
    return _placements(deps.survey(request, uuid))


@router.put('/surveys/{uuid}/placements/order', auth=WRITE, openapi_extra=errors())
def reorder_placements(request, uuid: UUID, body: PlacementOrderIn):
    """The stacking order of the placed layers. Editor role."""
    survey = deps.survey(request, uuid, role='editor')
    svc_placements.reorder(deps.actor(request), survey, body.layer_ids)
    return _placements(survey)


@router.put('/surveys/{uuid}/layers/{layer_id}/placement', auth=WRITE, openapi_extra=errors())
def place_layer(request, uuid: UUID, layer_id: int, body: PlacementIn):
    """Put a layer the survey uses on its maps, or change where it shows. Editor role."""
    survey = deps.survey(request, uuid, role='editor')
    placement = svc_placements.place(deps.actor(request), survey, layer_id, body.scope, body.sections)
    return svc_placements.describe(placement, survey)


@router.delete('/surveys/{uuid}/layers/{layer_id}/placement', auth=WRITE, openapi_extra=errors())
def unplace_layer(request, uuid: UUID, layer_id: int):
    """Take a layer off every map of the survey; it stays linked. Editor role."""
    survey = deps.survey(request, uuid, role='editor')
    return {'removed': svc_placements.unplace(deps.actor(request), survey, layer_id)}


@router.get('/surveys/{uuid}/study-area', auth=READ, openapi_extra=errors())
def get_study_area(request, uuid: UUID):
    """The survey's study area (geometry, source, fog, refusal rule, message, size), or null."""
    survey = deps.survey(request, uuid)
    return {'study_area': svc_area.describe(svc_area.get(survey))}


@router.put('/surveys/{uuid}/study-area', auth=WRITE, openapi_extra=errors())
def set_study_area(request, uuid: UUID, body: StudyAreaIn):
    """Create or replace the study area. Editor role."""
    survey = deps.survey(request, uuid, role='editor')
    svc_area.set_area(deps.actor(request), survey, body.geometry, source=body.source,
                      place_name=body.place_name or '', fog=body.fog, refuse_outside=body.refuse_outside,
                      message=body.message)
    return {'study_area': svc_area.describe(svc_area.get(survey))}


@router.patch('/surveys/{uuid}/study-area', auth=WRITE, openapi_extra=errors())
def update_study_area(request, uuid: UUID, body: StudyAreaPatchIn):
    """Change the fog, the refusal rule or the message. Editor role."""
    survey = deps.survey(request, uuid, role='editor')
    fields = body.model_dump(exclude_unset=True)
    svc_area.update_settings(deps.actor(request), survey, fog=fields.get('fog'),
                             refuse_outside=fields.get('refuse_outside'), message=fields.get('message'))
    return {'study_area': svc_area.describe(svc_area.get(survey))}


@router.delete('/surveys/{uuid}/study-area', auth=WRITE, openapi_extra=errors())
def clear_study_area(request, uuid: UUID):
    """Remove the study area. Editor role."""
    survey = deps.survey(request, uuid, role='editor')
    return {'removed': svc_area.clear(deps.actor(request), survey)}
