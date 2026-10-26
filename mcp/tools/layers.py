"""Map layers: reference layers from GeoJSON, their objects, styling, order,
and moderating the marks of a shared map (change api-v2-layers, #411 PR 2).
Every write goes through `survey.services.layers`, the path the editor and
REST API v1 take; the shapes are REST's (`api.v1.layers.layer_out` /
`object_out`).
"""
import json
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field

from survey.models import LayerObject
from survey.services import layers as svc_layers

from api import scopes
from api.errors import not_found
from api.v1.layers import LayerCreateIn, LayerPatchIn, api_error, layer_out, object_out
from api.v1.pagination import page

from ..errors import confirmation_required
from .common import actor, survey
from .registry import args_model, tool

SURVEY = (UUID, Field(description='The survey uuid (from list_surveys).'))
LAYER = (int, Field(description='A layer id from list_layers.'))
KEY = (str, Field(description='An object key from list_layer_objects.'))
CONFIRM = (bool, Field(False, description='Set to true only after the user confirmed this action in the conversation.'))


def _layer(obj, layer_id):
    try:
        return svc_layers.get_layer(obj, layer_id)
    except svc_layers.LayerError:
        raise not_found()


def _object(layer, key):
    try:
        return svc_layers.get_object(layer, key)
    except svc_layers.LayerError:
        raise not_found()


def _run(fn, *a):
    try:
        return fn(*a)
    except svc_layers.LayerError as exc:
        raise api_error(exc)


@tool(
    'list_layers',
    title='List map layers',
    description=(
        'The survey\'s reference layers -- context drawn under the answers (bus stops, parks, planned '
        'sites) and shared maps of respondents\' marks -- with their style and object count.'
    ),
    scope=scopes.SURVEYS_READ, role='viewer', read_only=True, idempotent=True,
    args=args_model('ListLayersArgs', survey=SURVEY),
)
def list_layers(request, args):
    obj = survey(request, args.survey)
    return {'items': [layer_out(l, obj) for l in svc_layers.layers_qs(obj)]}


@tool(
    'create_layer',
    title='Create a map layer',
    description=(
        'A reference layer from GeoJSON you pass as `geojson` -- a FeatureCollection, a Feature or a '
        'geometry in WGS 84 longitude/latitude (not projected metres). At most 5 000 features and 10 MB; '
        'multi-part geometries become one object per part; a "name" or "title" property becomes the '
        'object title. Omit `geojson` for an empty layer to fill with create_layer_object. To ask '
        'respondents about these objects, add an "Objects on the map" question with this layer_id. Needs '
        'the survey owner; at most 10 layers.'
    ),
    scope=scopes.SURVEYS_WRITE, role='owner',
    args=args_model('CreateLayerArgs', LayerCreateIn, survey=SURVEY),
)
def create_layer(request, args):
    obj = survey(request, args.survey, role='owner')
    if args.geojson is None:
        layer = _run(svc_layers.create_empty, actor(request), obj, args.name)
        return layer_out(layer, obj)
    layer, report = _run(svc_layers.create_from_geojson, actor(request), obj,
                         json.dumps(args.geojson).encode(), args.name)
    body = layer_out(layer, obj)
    body['import'] = {k: report.get(k) for k in ('created', 'exploded', 'skipped', 'invalid_links') if k in report}
    return body


@tool(
    'update_layer',
    title='Update a map layer',
    description=(
        'Rename a layer, change its colour (#rrggbb), the property used as label or key, popups, or its '
        'style: opacity, weight, fill_opacity, radius, icon, legend, and `by` -- one rule colouring objects '
        'by one property (mode "categories" with classes [{value, color}] or "graduated"). Never changes '
        'geometry. Needs the survey owner.'
    ),
    scope=scopes.SURVEYS_WRITE, role='owner', idempotent=True,
    args=args_model('UpdateLayerArgs', LayerPatchIn, survey=SURVEY, layer_id=LAYER),
)
def update_layer(request, args):
    obj = survey(request, args.survey, role='owner')
    layer = _layer(obj, args.layer_id)
    fields = args.model_dump(exclude_unset=True, exclude={'survey', 'layer_id'})
    _run(svc_layers.update, actor(request), layer, fields)
    return layer_out(layer, obj)


@tool(
    'reorder_layers',
    title='Reorder map layers',
    description='Set the stacking order of the layers: every layer id of the survey, bottom first. Needs the survey owner.',
    scope=scopes.SURVEYS_WRITE, role='owner', idempotent=True,
    args=args_model('ReorderLayersArgs', survey=SURVEY, layer_ids=(List[int], Field())),
)
def reorder_layers(request, args):
    obj = survey(request, args.survey, role='owner')
    _run(svc_layers.reorder, actor(request), obj, args.layer_ids)
    return {'items': [layer_out(l, obj) for l in svc_layers.layers_qs(obj)]}


@tool(
    'delete_layer',
    title='Delete a map layer',
    description=(
        'Delete a layer and all its objects. Refused while a question uses it. Needs `confirm: true` after '
        'the user agreed, and the survey owner.'
    ),
    scope=scopes.SURVEYS_WRITE, role='owner', destructive=True, confirm=True,
    args=args_model('DeleteLayerArgs', survey=SURVEY, layer_id=LAYER, confirm=CONFIRM),
)
def delete_layer(request, args):
    obj = survey(request, args.survey, role='owner')
    layer = _layer(obj, args.layer_id)
    if not args.confirm:
        raise confirmation_required('Deleting a map layer')
    _run(svc_layers.delete, actor(request), layer)
    return {'deleted': args.layer_id}


@tool(
    'list_layer_objects',
    title='List layer objects',
    description='The objects of one layer -- key, title, category, description, link, geometry, properties -- paged.',
    scope=scopes.SURVEYS_READ, role='viewer', read_only=True, idempotent=True,
    args=args_model(
        'ListLayerObjectsArgs', survey=SURVEY, layer_id=LAYER,
        cursor=(Optional[str], Field(None, description='`next_cursor` of the previous page.')),
        limit=(int, Field(50, ge=1, le=200)),
    ),
)
def list_layer_objects(request, args):
    layer = _layer(survey(request, args.survey), args.layer_id)
    items, next_cursor = page(LayerObject.objects.filter(layer=layer), f'objects:{layer.pk}', args.cursor, args.limit)
    return {'items': [object_out(o) for o in items], 'next_cursor': next_cursor}


OBJECT_FIELDS = dict(
    title=(Optional[str], Field(None, max_length=255)),
    category=(Optional[str], Field(None, max_length=100)),
    description=(Optional[str], Field(None, description='Rich text shown on the object card.')),
    link=(Optional[str], Field(None, max_length=500, description='An http:// or https:// address.')),
    properties=(Optional[Dict[str, Any]], Field(None)),
)


@tool(
    'create_layer_object',
    title='Add an object to a layer',
    description=(
        'One object: a Point, LineString or Polygon `geometry` in WGS 84, with title, category, description '
        '(shown on its card), an http(s) link and properties. Not on a shared map. Needs the survey owner.'
    ),
    scope=scopes.SURVEYS_WRITE, role='owner',
    args=args_model(
        'CreateLayerObjectArgs', survey=SURVEY, layer_id=LAYER,
        geometry=(Dict[str, Any], Field()),
        key=(Optional[str], Field(None, max_length=100, description='Unique in the layer; generated when omitted.')),
        **OBJECT_FIELDS,
    ),
)
def create_layer_object(request, args):
    obj = survey(request, args.survey, role='owner')
    layer = _layer(obj, args.layer_id)
    created = _run(svc_layers.create_object, actor(request), layer,
                   args.model_dump(exclude_unset=True, exclude={'survey', 'layer_id'}))
    return object_out(created)


@tool(
    'update_layer_object',
    title='Update a layer object',
    description='Change an object\'s text, link, geometry or properties; the key stays. Needs the survey owner.',
    scope=scopes.SURVEYS_WRITE, role='owner', idempotent=True,
    args=args_model(
        'UpdateLayerObjectArgs', survey=SURVEY, layer_id=LAYER, key=KEY,
        geometry=(Optional[Dict[str, Any]], Field(None)), **OBJECT_FIELDS,
    ),
)
def update_layer_object(request, args):
    obj = survey(request, args.survey, role='owner')
    layer = _layer(obj, args.layer_id)
    target = _object(layer, args.key)
    _run(svc_layers.update_object, actor(request), layer, target,
         args.model_dump(exclude_unset=True, exclude={'survey', 'layer_id', 'key'}))
    return object_out(target)


@tool(
    'delete_layer_object',
    title='Delete a layer object',
    description='Remove one object (answers about it stay in the responses). Needs `confirm: true` and the survey owner.',
    scope=scopes.SURVEYS_WRITE, role='owner', destructive=True, confirm=True,
    args=args_model('DeleteLayerObjectArgs', survey=SURVEY, layer_id=LAYER, key=KEY, confirm=CONFIRM),
)
def delete_layer_object(request, args):
    obj = survey(request, args.survey, role='owner')
    layer = _layer(obj, args.layer_id)
    target = _object(layer, args.key)
    if not args.confirm:
        raise confirmation_required('Deleting a layer object')
    _run(svc_layers.delete_object, actor(request), layer, target)
    return {'deleted': args.key}


@tool(
    'moderate_layer_object',
    title='Moderate a mark on a shared map',
    description=(
        'On a shared map (a layer of respondents\' marks): show a mark to other respondents ("visible"), '
        'hold it ("pending") or hide it ("hidden"). Needs the editor role.'
    ),
    scope=scopes.SURVEYS_WRITE, role='editor', idempotent=True,
    args=args_model('ModerateLayerObjectArgs', survey=SURVEY, layer_id=LAYER, key=KEY,
                    status=(str, Field(description='visible, pending or hidden.'))),
)
def moderate_layer_object(request, args):
    obj = survey(request, args.survey, role='editor')
    layer = _layer(obj, args.layer_id)
    target = _object(layer, args.key)
    return object_out(_run(svc_layers.set_object_status, actor(request), layer, target, args.status))
