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
    GEOMETRY_TEXT_FIELDS, MAX_LAYER_BYTES, MAX_LAYER_FEATURES, MAX_LAYERS_PER_SURVEY, LayerValidationError,
    _clean_key, _geometry_coords, check_object_caps, clean_object_link, explode_geometry, layer_owner,
    layers_for, normalize_style, objects_from_features, rebuild_layer, validate_layer_upload,
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
    """The survey's layers, geometry text deferred: the datasets it links and the shared-map layers
    it owns (change map-layers-study-area: layers live in Data, the survey reaches them through
    its links). A survey edits the style and objects of a layer it uses; Data shows the edit on
    every place that links it."""
    return layers_for(survey).order_by('position', 'id')


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


def _audit(actor, action, layer, survey=None, **meta):
    if actor is not None:
        audit_record(actor, action, survey or layer.survey, layer_id=layer.pk, **meta)


# ─── layers ──────────────────────────────────────────────────────────────────

def _assert_room(owner):
    if layers_for(owner).count() >= MAX_LAYERS_PER_SURVEY:
        raise LayerError(LIMIT_REACHED, f'A survey can hold {MAX_LAYERS_PER_SURVEY} reference layers.')


def _next_position(owner):
    return (layers_for(owner).aggregate(m=Max('position'))['m'] or 0) + 1


# Files the Data import reads (GDAL / csv). A GeoJSON in WGS 84 keeps the direct parser, so its
# properties stay JSON values exactly as before; a projected GeoJSON and every other format go
# through the Data reader, which reprojects (spec reference-overlay-layers, design D4).
DATA_READER_EXTS = ('.gpkg', '.zip', '.kml', '.csv')
GEOJSON_EXTS = ('', '.geojson', '.json')


def new_layer(actor, owner, name, fields=None, position=None, **values):
    """A new uploaded or drawn layer of `owner`: a workspace dataset the survey links (layers
    live in Data). The dataset row comes first — the rebuild reads its field dictionary. A survey
    without a workspace keeps the layer itself (there is no Data to put it in). The ZIP import
    calls it too, with the archive's position and cleaned config."""
    position = _next_position(owner) if position is None else position
    if owner.organization_id is None:
        return SurveyMapLayer.objects.create(survey=owner, name=name, geojson='', position=position, **values)
    from data.models import Dataset, DatasetLink
    layer = SurveyMapLayer.objects.create(survey=None, organization_id=owner.organization_id, name=name,
                                          geojson='', position=position, **values)
    dataset = Dataset.objects.create(organization_id=owner.organization_id, kind=Dataset.KIND_LAYER, layer=layer,
                                     name=name[:200], privacy_class=Dataset.PRIVACY_PUBLIC, fields=fields or [])
    DatasetLink.objects.create(dataset=dataset, survey=owner, created_by=getattr(actor, 'user', None))
    return layer


def _read_with_data_reader(data, filename):
    """(features, profile) of a file the Data import reads, reprojected to WGS 84."""
    import shutil
    import tempfile
    from data.imports import ImportRefused, open_source
    ext = os.path.splitext(filename or '')[1].lower() or '.geojson'
    workdir = tempfile.mkdtemp(prefix='layer-upload-')
    try:
        path = os.path.join(workdir, 'upload' + ext)
        with open(path, 'wb') as fh:
            fh.write(data)
        try:
            source = open_source(path, 'upload' + ext)
            profile = source.profile()
            located = profile['count'] - profile['no_location']
            if located == 0:
                raise ImportRefused('No feature of the file has a location.')
            if located > MAX_LAYER_FEATURES:
                raise ImportRefused(f'The file has {located} features; the limit is {MAX_LAYER_FEATURES}.')
            features = list(source.features())
        except ImportRefused as exc:
            raise LayerError(VALIDATION, str(exc), 'geojson')
        except Exception:  # noqa: BLE001 — GDAL raises plain errors on a broken file
            raise LayerError(VALIDATION, 'This file could not be read. Upload a GeoPackage, a zipped shapefile, '
                                         'KML, GeoJSON or a CSV with coordinate columns.', 'geojson')
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    for feature in features:
        for lng, lat in _geometry_coords(feature.get('geometry')):
            if not (-180 <= lng <= 180 and -90 <= lat <= 90):
                raise LayerError(VALIDATION, 'The file has no coordinate system and its coordinates are not '
                                             'longitude/latitude. Re-export it with its coordinate system '
                                             '(or as WGS84, EPSG:4326).', 'geojson')
    return features, profile


def _converted_from(crs):
    """The coordinate system a file was converted from, '' when it was already WGS 84."""
    crs = crs or ''
    if crs in ('EPSG:4326', 'unknown') or crs.startswith('none'):
        return ''
    return crs


def create_from_upload(actor, survey, data, name=None, filename=None):
    """A layer from an uploaded file (or a serialised GeoJSON body): GeoJSON, GeoPackage, zipped
    shapefile, KML or CSV with coordinate columns, reprojected to WGS 84 when the file says it is
    in another coordinate system. It becomes a workspace dataset linked to the survey and placed
    on every map section, now and later (spec map-layer-placement). Refuses a full survey, an
    oversized file and anything the readers refuse, before writing a row. Returns (layer, report);
    `report['crs']` names the coordinate system the file was converted from ('' when none)."""
    owner = layer_owner(survey)
    _assert_room(owner)
    if len(data) > MAX_LAYER_BYTES:
        raise LayerError(VALIDATION, f'File is larger than {MAX_LAYER_BYTES // (1024 * 1024)} MB.', 'geojson')
    ext = os.path.splitext(filename or '')[1].lower()
    fields, converted = [], ''
    if ext in DATA_READER_EXTS:
        features, profile = _read_with_data_reader(data, filename)
        fields, converted = profile['fields'], _converted_from(profile['crs'])
    elif ext in GEOJSON_EXTS:
        try:
            features, _properties, _dropped_z = validate_layer_upload(data)
        except LayerValidationError as exc:
            if 'projected coordinate system' not in str(exc):
                raise LayerError(VALIDATION, exc, 'geojson')
            # A GeoJSON in State Plane, UTM… — the Data reader honours its `crs` member.
            features, profile = _read_with_data_reader(data, 'upload.geojson')
            converted = _converted_from(profile['crs'])
    else:
        raise LayerError(VALIDATION, 'Upload a GeoJSON, a GeoPackage (.gpkg), a zipped shapefile (.zip), KML or '
                                     'a CSV with coordinate columns.', 'geojson')
    name = (name or (os.path.splitext(filename)[0] if filename else '') or 'Layer').strip()[:100] or 'Layer'
    # Atomic: an exception while building objects used to leave an empty layer
    # counting against the cap (one such orphan reached production).
    with transaction.atomic():
        layer = new_layer(actor, owner, name, fields=fields)
        report = objects_from_features(layer, features, sanitize=coerce_creator_html)
        rebuild_layer(layer)
        from . import placements
        placements.place(actor, owner, layer.pk, automatic=True)
    report = dict(report, crs=converted)
    _audit(actor, 'layer_create', layer, survey=owner, name=layer.name, objects=report.get('created', 0))
    _layer_added(actor, owner, 'upload')
    return layer, report


# The name every caller used before other formats were accepted.
create_from_geojson = create_from_upload


def _layer_added(actor, owner, source):
    if actor is not None:
        from ..product_events import LAYER_ADDED, emit
        emit(LAYER_ADDED, actor.user_id, {'survey_id': owner.pk, 'source': source, 'surface': actor.surface})


def create_empty(actor, survey, name=None):
    """A layer to draw on: a workspace dataset linked to the survey and placed on every map."""
    owner = layer_owner(survey)
    _assert_room(owner)
    with transaction.atomic():
        layer = new_layer(actor, owner, ((name or '').strip() or 'New layer')[:100])
        rebuild_layer(layer)
        from . import placements
        placements.place(actor, owner, layer.pk, automatic=True)
    _audit(actor, 'layer_create', layer, survey=owner, name=layer.name, objects=0)
    _layer_added(actor, owner, 'draw')
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


def _family(owner):
    from django.db.models import Q
    from ..models import SurveyHeader
    return SurveyHeader.objects.filter(Q(pk=owner.pk) | Q(canonical_survey=owner) | Q(published_version=owner))


def delete(actor, layer, survey=None):
    """Remove a layer from a survey. A layer the survey owns (a shared map, or a survey without a
    workspace) is deleted; a dataset it links is unlinked, taken off its maps and stays in Data
    (spec reference-overlay-layers "Remove from this survey"). Refused while a question of the
    survey asks about it."""
    from ..models import LayerPlacement, Question
    owner = layer_owner(survey) if survey is not None else layer.survey
    if owner is None:
        raise LayerError(CONFLICT, 'Delete a workspace dataset from its page in Data.')
    bound = list(Question.objects.filter(layer=layer, survey_section__survey_header__in=_family(owner))
                 .values_list('name', flat=True))
    if bound:
        names = ', '.join(f'“{n}”' for n in bound if n) or 'a question'
        raise LayerError(CONFLICT, f'This layer is used by {names}. Change that question\'s layer or delete it first.')
    layer_id, name = layer.pk, layer.name
    with transaction.atomic():
        LayerPlacement.objects.filter(survey=owner, layer_id=layer_id).delete()
        if layer.survey_id == owner.pk:
            layer.delete()
            action = 'layer_delete'
        else:
            from data.models import DatasetLink
            DatasetLink.objects.filter(survey=owner, dataset__layer_id=layer_id).delete()
            action = 'layer_unlink'
    if actor is not None:
        audit_record(actor, action, owner, layer_id=layer_id, name=name)


def reorder(actor, survey, layer_ids):
    """The order of the survey's layers: their placements' stacking order on the maps and the
    layers' own position (the list order in Survey settings, REST and MCP)."""
    from ..models import LayerPlacement
    owner = layer_owner(survey)
    current = list(layers_for(owner).values_list('pk', flat=True))
    if sorted(current) != sorted(layer_ids) or len(set(layer_ids)) != len(layer_ids):
        raise LayerError(VALIDATION, 'Give every layer of the survey exactly once.', 'layer_ids')
    with transaction.atomic():
        for position, pk in enumerate(layer_ids, start=1):
            SurveyMapLayer.objects.filter(pk=pk).update(position=position)
            LayerPlacement.objects.filter(survey=owner, layer_id=pk).update(position=position)
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
        new = {k: v for k, v in fields['properties'].items() if isinstance(k, str)}
        # A writer that never saw the private fields (REST/MCP) cannot erase them (data-metadata).
        from data.fields import hidden_names, merge_private
        obj.properties = merge_private(obj.properties if obj.pk else {}, new, hidden_names(obj.layer_id))


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
