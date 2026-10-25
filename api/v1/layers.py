"""Reference layers and their objects -- writes (change api-v2-layers, #411;
epic #408). Reads stay in `data.py` (`GET …/layers`, `…/geojson`).

Every write goes through `survey.services.layers`, the path the editor's layer
card and object editor take; these routes check scope, role and Pro and map
`LayerError` to the envelope. Layer and object writes need the survey's
`owner` role, as in the editor; moderating a shared-map mark needs `editor`.
"""
import json
from typing import Any, Dict, List, Optional
from uuid import UUID

from ninja import File, Form, Router
from ninja.files import UploadedFile
from pydantic import Field

from survey.layers import legend_for, normalize_style
from survey.models import LayerObject
from survey.services import layers as svc_layers

from .. import scopes
from ..errors import CONFLICT, LIMIT_REACHED, NOT_FOUND, VALIDATION, ApiError, not_found
from . import deps, out
from .auth import Bearer
from .docs import errors, list_errors
from .pagination import page
from .schemas import In, LayerOut

router = Router(tags=['Layers'])

READ = Bearer(scopes.SURVEYS_READ)
WRITE = Bearer(scopes.SURVEYS_WRITE)

STATUS_OF = {svc_layers.VALIDATION: 422, svc_layers.LIMIT_REACHED: 409, svc_layers.CONFLICT: 409,
             svc_layers.NOT_FOUND: 404}
CODE_OF = {svc_layers.VALIDATION: VALIDATION, svc_layers.LIMIT_REACHED: LIMIT_REACHED,
           svc_layers.CONFLICT: CONFLICT, svc_layers.NOT_FOUND: NOT_FOUND}


def api_error(exc):
    extra = {'fields': {exc.field: [exc.message]}} if exc.field else {}
    return ApiError(STATUS_OF.get(exc.code, 409), CODE_OF.get(exc.code, CONFLICT), exc.message, **extra)


# ─── schemas ─────────────────────────────────────────────────────────────────

class LayerCreateIn(In):
    name: Optional[str] = Field(None, max_length=100)
    geojson: Optional[Dict[str, Any]] = Field(
        None, description='A FeatureCollection, a Feature or a bare geometry in WGS 84 (lng, lat). At most '
                          '10 MB and 5 000 features; multi-part geometries become one object per part. Omit '
                          'for an empty layer.')


class LayerPatchIn(In):
    name: Optional[str] = Field(None, max_length=100)
    color: Optional[str] = Field(None, description='#rrggbb')
    label_field: Optional[str] = Field(None, description='A property shown as the object title on the map.')
    key_field: Optional[str] = None
    show_popups: Optional[bool] = None
    style: Optional[Dict[str, Any]] = Field(
        None, description='opacity, weight, fill_opacity, radius, icon, legend, and `by` — one rule on one '
                          'property (categories or graduated classes). Normalised on save.')


class LayerOrderIn(In):
    layer_ids: List[int] = Field(description='Every layer id of the survey, in the new order.')


class ObjectIn(In):
    key: Optional[str] = Field(None, max_length=100, description='Unique in the layer; generated when omitted.')
    title: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, description='Rich text; sanitised like every creator text.')
    link: Optional[str] = Field(None, max_length=500, description='An http:// or https:// address.')
    geometry: Optional[Dict[str, Any]] = Field(None, description='One Point, LineString or Polygon (WGS 84).')
    properties: Optional[Dict[str, Any]] = None


class ObjectCreateIn(ObjectIn):
    geometry: Dict[str, Any]


class ObjectStatusIn(In):
    status: str = Field(description='visible, pending or hidden.')


# ─── output ──────────────────────────────────────────────────────────────────

def layer_out(layer, survey):
    data = out.layer(layer, survey)
    data.update({
        'label_field': layer.label_field, 'key_field': layer.key_field, 'show_popups': layer.show_popups,
        'style': normalize_style(layer.style, layer.color), 'legend': legend_for(layer),
        'source_question_code': layer.source_question_code or None,
        'live': svc_layers.is_live(survey),
    })
    return data


def object_out(obj):
    return {
        'key': obj.key, 'title': obj.title, 'category': obj.category, 'description': obj.description,
        'link': obj.link, 'geometry': json.loads(obj.geometry.geojson) if obj.geometry else None,
        'properties': obj.properties or {}, 'position': obj.position,
        'status': obj.status,
    }


def _layer(request, survey, layer_id):
    try:
        return svc_layers.get_layer(survey, layer_id)
    except svc_layers.LayerError:
        raise not_found()


def _object(layer, key):
    try:
        return svc_layers.get_object(layer, key)
    except svc_layers.LayerError:
        raise not_found()


def _create(request, survey, data, name, filename=None):
    try:
        layer, report = svc_layers.create_from_geojson(deps.actor(request), survey, data, name=name,
                                                       filename=filename)
    except svc_layers.LayerError as exc:
        raise api_error(exc)
    body = layer_out(layer, survey)
    body['import'] = {k: report.get(k) for k in ('created', 'exploded', 'skipped', 'invalid_links') if k in report}
    if report.get('collisions'):
        body['import']['collisions'] = report['collisions'][:50]
    return body


# ─── layers ──────────────────────────────────────────────────────────────────

@router.get('/surveys/{uuid}/layers', response=List[LayerOut], auth=READ, openapi_extra=errors())
def list_layers(request, uuid: UUID):
    """The survey's reference layers, metadata only; fetch geometry from `geojson_url`."""
    survey = deps.survey(request, uuid)
    return [out.layer(layer, survey) for layer in deps.layers_list(survey)]


@router.post('/surveys/{uuid}/layers', auth=WRITE, response={201: dict},
             openapi_extra=errors(codes=(LIMIT_REACHED,)))
def create_layer(request, uuid: UUID, body: LayerCreateIn):
    """A layer from GeoJSON in the body (or an empty one). Owner role; at most 10 layers per survey."""
    survey = deps.survey(request, uuid, role='owner')
    if body.geojson is None:
        try:
            layer = svc_layers.create_empty(deps.actor(request), survey, body.name)
        except svc_layers.LayerError as exc:
            raise api_error(exc)
        return 201, layer_out(layer, survey)
    return 201, _create(request, survey, json.dumps(body.geojson).encode(), body.name)


@router.post('/surveys/{uuid}/layers/upload', auth=WRITE, response={201: dict},
             openapi_extra=errors(codes=(LIMIT_REACHED,)))
def upload_layer(request, uuid: UUID, file: UploadedFile = File(...), name: Optional[str] = Form(None)):
    """A layer from a GeoJSON file (multipart). Owner role."""
    survey = deps.survey(request, uuid, role='owner')
    if file.size and file.size > svc_layers.MAX_LAYER_BYTES:
        raise ApiError(422, VALIDATION, 'File is larger than 10 MB.', fields={'file': ['too large']})
    return 201, _create(request, survey, file.read(), name, filename=file.name)


@router.put('/surveys/{uuid}/layers/order', auth=WRITE, openapi_extra=errors())
def reorder_layers(request, uuid: UUID, body: LayerOrderIn):
    """Set the layers' order (map stacking and the Layers panel). Owner role."""
    survey = deps.survey(request, uuid, role='owner')
    try:
        svc_layers.reorder(deps.actor(request), survey, body.layer_ids)
    except svc_layers.LayerError as exc:
        raise api_error(exc)
    return {'items': [layer_out(l, survey) for l in svc_layers.layers_qs(survey)]}


@router.patch('/surveys/{uuid}/layers/{layer_id}', auth=WRITE, openapi_extra=errors())
def update_layer(request, uuid: UUID, layer_id: int, body: LayerPatchIn):
    """Name, color, label/key field, popups and style -- never geometry. Owner role."""
    survey = deps.survey(request, uuid, role='owner')
    layer = _layer(request, survey, layer_id)
    try:
        svc_layers.update(deps.actor(request), layer, body.model_dump(exclude_unset=True))
    except svc_layers.LayerError as exc:
        raise api_error(exc)
    return layer_out(layer, survey)


@router.delete('/surveys/{uuid}/layers/{layer_id}', auth=WRITE, openapi_extra=errors(codes=(CONFLICT,)))
def delete_layer(request, uuid: UUID, layer_id: int):
    """Delete a layer and its objects -- refused while a question uses it. Owner role."""
    survey = deps.survey(request, uuid, role='owner')
    layer = _layer(request, survey, layer_id)
    try:
        svc_layers.delete(deps.actor(request), layer)
    except svc_layers.LayerError as exc:
        raise api_error(exc)
    return {'deleted': layer_id}


# ─── objects ─────────────────────────────────────────────────────────────────

@router.get('/surveys/{uuid}/layers/{layer_id}/objects', auth=READ, openapi_extra=list_errors())
def list_objects(request, uuid: UUID, layer_id: int, cursor: Optional[str] = None, limit: int = 100):
    """The layer's objects with geometry and properties, paged."""
    survey = deps.survey(request, uuid)
    layer = _layer(request, survey, layer_id)
    items, next_cursor = page(LayerObject.objects.filter(layer=layer), f'objects:{layer.pk}', cursor, limit)
    return {'items': [object_out(o) for o in items], 'next_cursor': next_cursor}


@router.post('/surveys/{uuid}/layers/{layer_id}/objects', auth=WRITE, response={201: dict},
             openapi_extra=errors(codes=(CONFLICT, LIMIT_REACHED)))
def create_object(request, uuid: UUID, layer_id: int, body: ObjectCreateIn):
    """Add an object. Owner role; not on a shared-map layer."""
    survey = deps.survey(request, uuid, role='owner')
    layer = _layer(request, survey, layer_id)
    try:
        obj = svc_layers.create_object(deps.actor(request), layer, body.model_dump(exclude_unset=True))
    except svc_layers.LayerError as exc:
        raise api_error(exc)
    return 201, object_out(obj)


@router.get('/surveys/{uuid}/layers/{layer_id}/objects/{key}', auth=READ, openapi_extra=errors())
def get_object(request, uuid: UUID, layer_id: int, key: str):
    survey = deps.survey(request, uuid)
    return object_out(_object(_layer(request, survey, layer_id), key))


@router.patch('/surveys/{uuid}/layers/{layer_id}/objects/{key}', auth=WRITE, openapi_extra=errors(codes=(CONFLICT,)))
def update_object(request, uuid: UUID, layer_id: int, key: str, body: ObjectIn):
    """Change an object's text, link, geometry or properties. The key cannot change. Owner role."""
    survey = deps.survey(request, uuid, role='owner')
    layer = _layer(request, survey, layer_id)
    obj = _object(layer, key)
    fields = body.model_dump(exclude_unset=True)
    fields.pop('key', None)
    try:
        svc_layers.update_object(deps.actor(request), layer, obj, fields)
    except svc_layers.LayerError as exc:
        raise api_error(exc)
    return object_out(obj)


@router.delete('/surveys/{uuid}/layers/{layer_id}/objects/{key}', auth=WRITE, openapi_extra=errors(codes=(CONFLICT,)))
def delete_object(request, uuid: UUID, layer_id: int, key: str):
    survey = deps.survey(request, uuid, role='owner')
    layer = _layer(request, survey, layer_id)
    try:
        svc_layers.delete_object(deps.actor(request), layer, _object(layer, key))
    except svc_layers.LayerError as exc:
        raise api_error(exc)
    return {'deleted': key}


@router.patch('/surveys/{uuid}/layers/{layer_id}/objects/{key}/status', auth=WRITE,
              openapi_extra=errors(codes=(CONFLICT,)))
def object_status(request, uuid: UUID, layer_id: int, key: str, body: ObjectStatusIn):
    """Moderate a mark on a shared map: visible, pending or hidden. Editor role."""
    survey = deps.survey(request, uuid, role='editor')
    layer = _layer(request, survey, layer_id)
    try:
        obj = svc_layers.set_object_status(deps.actor(request), layer, _object(layer, key), body.status)
    except svc_layers.LayerError as exc:
        raise api_error(exc)
    return object_out(obj)
