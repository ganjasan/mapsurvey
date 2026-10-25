"""Reference layers and their objects: the ONE write path (change api-v2-layers,
#411). The editor's layer card, the object editor and REST API v1 all call it;
none of them writes `SurveyMapLayer` or `LayerObject` directly.

Everything a write must do lives here: the canonical owner (`layer_owner`),
the caps, the per-layer lock, `rebuild_layer` after every object change, the
style normaliser, the link rule, the shared-map read-only rule, and an audit
row. Geometry text is never loaded to change metadata (layer memory rules).

Refusals are `LayerError(code, message, field)`: the editor answers 400 with
the message as it always did, the API maps the code to its envelope.
"""
import json
import os
import re
from contextlib import contextmanager

from django.contrib.gis.geos import GEOSException, GEOSGeometry
from django.db import transaction
from django.db.models import Max

from ..audit import record as audit_record
from ..html_sanitize import coerce_creator_html
from ..layers import (
    GEOMETRY_TEXT_FIELDS, MAX_LAYER_BYTES, MAX_LAYERS_PER_SURVEY, LayerValidationError, _clean_key,
    check_object_caps, clean_object_link, explode_geometry, layer_owner, normalize_style,
    objects_from_features, rebuild_layer, validate_layer_upload,
)
from ..models import LayerObject, SurveyMapLayer

VALIDATION = 'validation'
LIMIT_REACHED = 'limit_reached'
CONFLICT = 'conflict'
NOT_FOUND = 'not_found'

COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')
GEOMETRY_MESSAGE = 'A single Point, LineString or Polygon geometry is required.'
READ_ONLY_MESSAGE = "This layer's objects are respondents' marks; edit the answers instead."
OBJECT_STATUSES = ('visible', 'pending', 'hidden')


class LayerError(Exception):
    def __init__(self, code, message, field=None):
        super().__init__(message)
        self.code, self.message, self.field = code, str(message), field


# ─── lookups ─────────────────────────────────────────────────────────────────

def layers_qs(survey):
    """The survey's layers, geometry text deferred, in map order."""
    return SurveyMapLayer.objects.defer(*GEOMETRY_TEXT_FIELDS).filter(survey=layer_owner(survey))


def get_layer(survey, layer_id):
    layer = layers_qs(survey).filter(pk=layer_id).first()
    if layer is None:
        raise LayerError(NOT_FOUND, 'No such layer on this survey.')
    return layer


def get_object(layer, key):
    obj = LayerObject.objects.filter(layer=layer, key=key).first()
    if obj is None:
        raise LayerError(NOT_FOUND, 'No such object in this layer.')
    return obj


def is_live(survey):
    return layer_owner(survey).status == 'published'


@contextmanager
def layer_write(layer):
    """Serialise writers of one layer for the whole read-modify-rebuild (key
    allocation, caps and the derived GeoJSON each read what the next writes).
    `.only('pk')`: the lock wants the row, never its 10 MB text."""
    with transaction.atomic():
        SurveyMapLayer.objects.select_for_update().only('pk').get(pk=layer.pk)
        yield


def _writable(layer):
    if layer.source == 'question':
        raise LayerError(CONFLICT, READ_ONLY_MESSAGE)


def _audit(actor, action, layer, **meta):
    if actor is not None:
        audit_record(actor, action, layer.survey, layer_id=layer.pk, **meta)


# ─── layers ──────────────────────────────────────────────────────────────────

def _assert_room(owner):
    if owner.map_layers.count() >= MAX_LAYERS_PER_SURVEY:
        raise LayerError(LIMIT_REACHED, f'A survey can hold {MAX_LAYERS_PER_SURVEY} reference layers.')


def _next_position(owner):
    return (owner.map_layers.aggregate(m=Max('position'))['m'] or 0) + 1


def create_from_geojson(actor, survey, data, name=None, filename=None):
    """A layer from GeoJSON bytes (an upload or a serialised JSON body), its
    features turned into objects. Refuses a full survey, an oversized file and
    anything `validate_layer_upload` refuses, before writing a row."""
    owner = layer_owner(survey)
    _assert_room(owner)
    if len(data) > MAX_LAYER_BYTES:
        raise LayerError(VALIDATION, f'File is larger than {MAX_LAYER_BYTES // (1024 * 1024)} MB.', 'geojson')
    try:
        features, _properties, _dropped_z = validate_layer_upload(data)
    except LayerValidationError as exc:
        raise LayerError(VALIDATION, exc, 'geojson')
    name = (name or (os.path.splitext(filename)[0] if filename else '') or 'Layer').strip()[:100] or 'Layer'
    # Atomic: an exception while building objects used to leave an empty layer
    # counting against the cap (one such orphan reached production).
    with transaction.atomic():
        layer = SurveyMapLayer.objects.create(survey=owner, name=name, geojson='', position=_next_position(owner))
        report = objects_from_features(layer, features, sanitize=coerce_creator_html)
        rebuild_layer(layer)
    _audit(actor, 'layer_create', layer, name=layer.name, objects=report.get('created', 0))
    return layer, report


def create_empty(actor, survey, name=None):
    owner = layer_owner(survey)
    _assert_room(owner)
    layer = SurveyMapLayer.objects.create(survey=owner, name=((name or '').strip() or 'New layer')[:100],
                                          geojson='', position=_next_position(owner))
    rebuild_layer(layer)
    _audit(actor, 'layer_create', layer, name=layer.name, objects=0)
    return layer


def update(actor, layer, fields):
    """Presentation only, never geometry. `fields` may hold name, color,
    label_field, key_field, show_popups, style (a dict, normalised here). A
    shared-map layer takes name, color and a style without a rule."""
    if 'style' in fields:
        raw = fields['style']
        if not isinstance(raw, dict):
            raise LayerError(VALIDATION, 'Style must be JSON.', 'style')
        color = fields.get('color') or layer.color
        try:
            style = normalize_style(raw, color if COLOR_RE.match(color or '') else layer.color)
        except LayerValidationError as exc:
            raise LayerError(VALIDATION, exc, 'style')
        if layer.source == 'question':
            style['by'] = None
        layer.style = style
    name = (fields.get('name') or '').strip()
    if name:
        layer.name = name[:100]
    color = (fields.get('color') or '').strip()
    if color:
        if not COLOR_RE.match(color):
            raise LayerError(VALIDATION, 'Color must be #RRGGBB.', 'color')
        layer.color = color
    if layer.source != 'question':
        # A field name must exist in the layer, or labels silently vanish.
        known = list(layer.property_names or [])
        for field in ('label_field', 'key_field'):
            if field in fields:
                value = (fields.get(field) or '').strip()[:100]
                if value and value not in known:
                    raise LayerError(VALIDATION, f'"{value}" is not a property of this layer.', field)
                setattr(layer, field, value)
        if 'show_popups' in fields:
            layer.show_popups = bool(fields['show_popups'])
    # geojson_gz is deferred: update_fields keeps save() from touching it.
    layer.save(update_fields=['name', 'color', 'label_field', 'key_field', 'show_popups', 'style', 'updated_at'])
    _audit(actor, 'layer_update', layer, fields=sorted(k for k in fields if k in (
        'name', 'color', 'label_field', 'key_field', 'show_popups', 'style')))
    return layer


def bound_question_names(layer):
    return list(layer.questions.values_list('name', flat=True))


def delete(actor, layer):
    bound = bound_question_names(layer)
    if bound:
        names = ', '.join(f'“{n}”' for n in bound if n) or 'a question'
        raise LayerError(CONFLICT, f'This layer is used by {names}. Change that question\'s layer or delete it first.')
    layer_id, name, survey = layer.pk, layer.name, layer.survey
    layer.delete()
    if actor is not None:
        audit_record(actor, 'layer_delete', survey, layer_id=layer_id, name=name)


def reorder(actor, survey, layer_ids):
    owner = layer_owner(survey)
    current = list(owner.map_layers.values_list('pk', flat=True))
    if sorted(current) != sorted(layer_ids) or len(set(layer_ids)) != len(layer_ids):
        raise LayerError(VALIDATION, 'Give every layer of the survey exactly once.', 'layer_ids')
    with transaction.atomic():
        for position, pk in enumerate(layer_ids, start=1):
            SurveyMapLayer.objects.filter(pk=pk).update(position=position)
    if actor is not None:
        audit_record(actor, 'layer_reorder', owner, layer_ids=list(layer_ids))


# ─── objects ─────────────────────────────────────────────────────────────────

def geometry_from(value):
    """A GeoJSON geometry (dict or string) → one-part GEOS geometry, else None."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    parts = explode_geometry(value)
    if len(parts) != 1:
        return None
    try:
        geom = GEOSGeometry(json.dumps(parts[0]), srid=4326)
    except (GEOSException, ValueError, TypeError):
        return None
    if not geom.valid and geom.geom_type != 'Point':
        return None
    return geom


def next_key(layer, prefix='o'):
    taken = set(layer.items.values_list('key', flat=True))
    n = len(taken) + 1
    key = f'{prefix}-{n}'
    while key in taken:
        n += 1
        key = f'{prefix}-{n}'
    return key


def _apply_object_fields(obj, fields):
    if 'link' in fields:
        try:
            obj.link = clean_object_link(fields.get('link'))
        except LayerValidationError as exc:
            raise LayerError(VALIDATION, exc, 'link')
    if 'title' in fields:
        obj.title = str(fields.get('title') or '')[:255]
    if 'category' in fields:
        obj.category = str(fields.get('category') or '')[:100]
    if 'description' in fields:
        obj.description = coerce_creator_html(str(fields.get('description') or ''))
    if 'properties' in fields and isinstance(fields['properties'], dict):
        obj.properties = {k: v for k, v in fields['properties'].items() if isinstance(k, str)}


def create_object(actor, layer, fields):
    """`fields`: geometry (required), key, title, category, description, link,
    properties. Caps, key allocation, insert and rebuild under the layer lock."""
    _writable(layer)
    geom = geometry_from(fields.get('geometry'))
    if geom is None:
        raise LayerError(VALIDATION, GEOMETRY_MESSAGE, 'geometry')
    obj = LayerObject(layer=layer, geometry=geom)
    _apply_object_fields(obj, fields)   # link refusal before anything is written
    with layer_write(layer):
        try:
            check_object_caps(layer, adding=1)
        except LayerValidationError as exc:
            raise LayerError(LIMIT_REACHED, exc)
        key = _clean_key(fields.get('key') or '') or next_key(layer)
        if layer.items.filter(key=key).exists():
            raise LayerError(CONFLICT, f'An object with key "{key}" already exists in this layer.', 'key')
        obj.key = key
        obj.position = (layer.items.aggregate(m=Max('position'))['m'] or 0) + 1
        obj.save()
        rebuild_layer(layer)
    _audit(actor, 'layer_object_create', layer, key=obj.key)
    return obj


def update_object(actor, layer, obj, fields):
    _writable(layer)
    _apply_object_fields(obj, fields)
    if 'geometry' in fields:
        geom = geometry_from(fields.get('geometry'))
        if geom is None:
            raise LayerError(VALIDATION, GEOMETRY_MESSAGE, 'geometry')
        obj.geometry = geom
    with layer_write(layer):
        obj.save()
        rebuild_layer(layer)
    _audit(actor, 'layer_object_update', layer, key=obj.key,
           fields=sorted(k for k in fields if k in ('title', 'category', 'description', 'link', 'properties',
                                                    'geometry')))
    return obj


def delete_object(actor, layer, obj):
    _writable(layer)
    key = obj.key
    with layer_write(layer):
        obj.delete()
        rebuild_layer(layer)
    _audit(actor, 'layer_object_delete', layer, key=key)


def set_object_status(actor, layer, obj, status):
    """Moderate a mark on a shared map (`visible`, `pending`, `hidden`)."""
    if layer.source != 'question':
        raise LayerError(CONFLICT, 'Only marks on a shared map have a status.')
    if status not in OBJECT_STATUSES:
        raise LayerError(VALIDATION, 'Status must be visible, pending or hidden.', 'status')
    obj.status = status
    obj.save(update_fields=['status', 'updated_at'])
    rebuild_layer(layer)
    _audit(actor, 'layer_object_status', layer, key=obj.key, status=status)
    return obj
