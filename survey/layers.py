"""Reference overlay layers: validation, objects and the derived GeoJSON.

`validate_layer_upload` is the one gate every GeoJSON passes on the way in —
editor import, ZIP import, AI-written — so a file is always a re-serialized
parse, never raw bytes. Since `overlay-features` a layer is a container of
LayerObject rows: `objects_from_features` turns validated features into rows,
`rebuild_layer` derives the FeatureCollection the respondent map loads, and
`layers_for` resolves which survey owns the layers a page should show.
"""
import json
import re

from django.utils.text import slugify

MAX_LAYER_BYTES = 10 * 1024 * 1024
MAX_LAYER_FEATURES = 5000
MAX_LAYERS_PER_SURVEY = 10

# Properties the derived GeoJSON reserves for the list block and the popup.
# Prefixed so a GIS file's own `title` or `key` column is never clobbered.
RESERVED_PROPS = ('_key', '_title', '_category', '_has_content', '_cover')

_SINGLE_TYPES = ('Point', 'LineString', 'Polygon')
_MULTI_TYPES = {'MultiPoint': 'Point', 'MultiLineString': 'LineString', 'MultiPolygon': 'Polygon'}


def layer_owner(survey):
    """The SurveyHeader whose `map_layers` a page for `survey` should show.

    Layers are owned by the canonical survey and BORROWED by draft copies
    (`published_version` → canonical) and archived versions (`canonical_survey`
    → canonical). Copying hundreds of objects and their S3 assets into every
    draft, then merging them back on publish, is a feature with no merge
    semantics — so nothing copies, and an object edit is live everywhere."""
    return survey.canonical_survey or survey.published_version or survey


def layers_for(survey):
    """QuerySet of the layers a survey (or any of its versions) renders."""
    return layer_owner(survey).map_layers.all()


class LayerValidationError(Exception):
    """Human-readable rejection reason, safe to show in the editor."""


def _iter_coords(coords):
    """Yield (lng, lat) pairs from arbitrarily nested GeoJSON coordinates."""
    if not isinstance(coords, (list, tuple)) or not coords:
        return
    if isinstance(coords[0], (int, float)):
        if len(coords) >= 2:
            yield coords[0], coords[1]
        return
    for part in coords:
        yield from _iter_coords(part)


def _geometry_coords(geometry):
    if not isinstance(geometry, dict):
        return
    if geometry.get('type') == 'GeometryCollection':
        for g in geometry.get('geometries') or []:
            yield from _geometry_coords(g)
        return
    yield from _iter_coords(geometry.get('coordinates'))


def validate_layer_upload(data):
    """Validate raw uploaded bytes; return (geojson_str, feature_count, property_names).

    Raises LayerValidationError with a creator-facing message.
    """
    if len(data) > MAX_LAYER_BYTES:
        raise LayerValidationError(
            f"File is larger than {MAX_LAYER_BYTES // (1024 * 1024)} MB. "
            "Simplify the geometry (e.g. in QGIS or mapshaper.org) and try again.")
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise LayerValidationError("File is not UTF-8 text — expected a .geojson file.")
    try:
        parsed = json.loads(text)
    except ValueError:
        raise LayerValidationError("File is not valid JSON — expected a .geojson file.")

    if not isinstance(parsed, dict):
        raise LayerValidationError("Expected a GeoJSON object at the top level.")

    gtype = parsed.get('type')
    if gtype == 'FeatureCollection':
        features = parsed.get('features')
        if not isinstance(features, list):
            raise LayerValidationError("FeatureCollection has no 'features' array.")
    elif gtype == 'Feature':
        features = [parsed]
    elif gtype in ('Point', 'MultiPoint', 'LineString', 'MultiLineString',
                   'Polygon', 'MultiPolygon', 'GeometryCollection'):
        features = [{'type': 'Feature', 'properties': {}, 'geometry': parsed}]
    else:
        raise LayerValidationError(
            "Unrecognized GeoJSON type %r — expected a FeatureCollection." % (gtype,))

    if not features:
        raise LayerValidationError("The file contains no features.")
    if len(features) > MAX_LAYER_FEATURES:
        raise LayerValidationError(
            f"The file has {len(features)} features; the limit is {MAX_LAYER_FEATURES}.")

    properties = set()
    checked_any = False
    for f in features:
        if not isinstance(f, dict) or f.get('type') != 'Feature':
            raise LayerValidationError("Every entry in 'features' must be a Feature object.")
        props = f.get('properties')
        if isinstance(props, dict):
            properties.update(k for k in props if isinstance(k, str))
        for lng, lat in _geometry_coords(f.get('geometry')):
            checked_any = True
            if not (-180 <= lng <= 180 and -90 <= lat <= 90):
                raise LayerValidationError(
                    "Coordinates fall outside longitude/latitude ranges "
                    f"(found {lng:.1f}, {lat:.1f}). The file is probably in a projected "
                    "coordinate system — re-export it as WGS84 (EPSG:4326).")
    if not checked_any:
        raise LayerValidationError("No coordinates found in the file.")

    collection = {'type': 'FeatureCollection', 'features': features}
    geojson_str = json.dumps(collection, ensure_ascii=False, separators=(',', ':'))
    return geojson_str, len(features), sorted(properties)


def build_map_layers_metadata(survey):
    """Layer list for a map surface — config only, geometry stays behind the
    gated endpoint. Empty when the kill switch is off. Consumed by the
    respondent shell, the editor preview and the Responses tab alike."""
    from django.conf import settings as django_settings
    from django.urls import reverse
    if not django_settings.MAP_REFERENCE_LAYERS:
        return []
    return [
        {
            'id': layer.pk,
            'name': layer.name,
            'color': layer.color,
            'label_field': layer.label_field,
            'show_popups': layer.show_popups,
            'url': reverse('survey_layer_geojson', kwargs={
                'survey_slug': str(survey.uuid), 'layer_id': layer.pk,
            }),
        }
        # defer('geojson'): the 100s-of-KB geometry column loaded on every map
        # surface render fragments the worker heap into an RSS ratchet (the
        # 2026-09 "exceeded memory limits" incident); only config fields render.
        for layer in layers_for(survey).defer('geojson', 'geojson_legacy')
    ]


# ─── Objects ────────────────────────────────────────────────────────────────

def _clean_key(value):
    """Keys travel in URLs, form field names (`obj__<key>__<code>`) and CSV
    cells, so keep them to a safe charset. Slugify keeps unicode letters."""
    text = slugify(str(value), allow_unicode=True)
    return text[:100]


def derive_key(props, key_field, index, taken):
    """Object key for an imported feature: the file's key field when set and
    unused so far, else `f-<index>`. `taken` is the set of keys already assigned
    in this layer; the caller adds the result to it. Returns (key, from_field)."""
    if key_field and isinstance(props, dict):
        raw = props.get(key_field)
        if raw not in (None, ''):
            key = _clean_key(raw)
            if key:
                return key, True
    key = f'f-{index}'
    n = 1
    while key in taken:
        n += 1
        key = f'f-{index}-{n}'
    return key, False


def derive_title(props, label_field, key):
    """Title: the file's label field, then `name`/`title`-style columns, then the key."""
    if isinstance(props, dict):
        for field in (label_field, 'name', 'title', 'Name', 'NAME', 'label'):
            if field and props.get(field) not in (None, ''):
                return str(props[field])[:255]
    return key


def explode_geometry(geometry):
    """A LayerObject holds one Point/LineString/Polygon. Multi* and
    GeometryCollection split into parts; the caller suffixes their keys.
    Returns a list of geometry dicts; empty for unsupported input."""
    if not isinstance(geometry, dict):
        return []
    gtype = geometry.get('type')
    if gtype in _SINGLE_TYPES:
        return [geometry]
    if gtype in _MULTI_TYPES:
        part_type = _MULTI_TYPES[gtype]
        return [{'type': part_type, 'coordinates': c} for c in (geometry.get('coordinates') or [])]
    if gtype == 'GeometryCollection':
        parts = []
        for g in geometry.get('geometries') or []:
            parts.extend(explode_geometry(g))
        return parts
    return []


def _clean_mapping(mapping):
    mapping = mapping or {}
    return {k: (mapping.get(k) or '') for k in ('key', 'title', 'category', 'description', 'link')}


def objects_from_features(layer, features, mapping=None, sanitize=None):
    """Create LayerObject rows for validated GeoJSON features.

    `mapping` names the feature properties feeding key/title/category/
    description/link; unset entries fall back to the layer's `key_field` /
    `label_field` and the `name`-style heuristics. Returns a report:
    {'created': n, 'collisions': [key, ...], 'exploded': n, 'skipped': n}.
    A collision (a key already in the layer, or twice in the file) skips the
    feature and is reported rather than silently renumbered — the creator may
    be importing into a layer that already has answers hanging on those keys.

    `sanitize` is the creator-HTML coercer for descriptions; passed in rather
    than imported so this module stays importable from migrations."""
    from django.contrib.gis.geos import GEOSGeometry
    from survey.models import LayerObject

    m = _clean_mapping(mapping)
    key_field = m['key'] or layer.key_field
    label_field = m['title'] or layer.label_field
    taken = set(layer.items.values_list('key', flat=True))
    start_pos = (layer.items.order_by('-position').values_list('position', flat=True).first() or 0) + 1
    report = {'created': 0, 'collisions': [], 'exploded': 0, 'skipped': 0}
    rows = []
    for index, feature in enumerate(features, start=1):
        props = feature.get('properties') if isinstance(feature.get('properties'), dict) else {}
        parts = explode_geometry(feature.get('geometry'))
        if not parts:
            report['skipped'] += 1
            continue
        key, from_field = derive_key(props, key_field, index, taken)
        if from_field and key in taken:
            report['collisions'].append(key)
            continue
        if len(parts) > 1:
            report['exploded'] += 1
        for n, part in enumerate(parts, start=1):
            part_key = key if len(parts) == 1 else f'{key}-{n}'
            if part_key in taken:
                report['collisions'].append(part_key)
                continue
            taken.add(part_key)
            description = str(props.get(m['description']) or '') if m['description'] else ''
            if description and sanitize:
                description = sanitize(description)
            rows.append(LayerObject(
                layer=layer,
                key=part_key,
                title=derive_title(props, label_field, part_key),
                category=str(props.get(m['category']) or '')[:100] if m['category'] else '',
                description=description,
                link=str(props.get(m['link']) or '')[:500] if m['link'] else '',
                geometry=GEOSGeometry(json.dumps(part), srid=4326),
                position=start_pos + len(rows),
                # Reserved names are re-derived on output; storing them would
                # let a re-imported derived file shadow the object's own fields.
                properties={k: v for k, v in props.items()
                            if isinstance(k, str) and k not in RESERVED_PROPS},
            ))
    if rows:
        LayerObject.objects.bulk_create(rows, batch_size=500)
        report['created'] = len(rows)
    return report


def feature_for_object(obj, cover_url=''):
    """The derived GeoJSON feature: raw properties + the reserved fields."""
    props = dict(obj.properties or {})
    for reserved in RESERVED_PROPS:
        props.pop(reserved, None)
    props['_key'] = obj.key
    props['_title'] = obj.title
    props['_category'] = obj.category
    props['_has_content'] = bool(obj.description or obj.link or cover_url)
    props['_cover'] = cover_url
    return {
        'type': 'Feature',
        'id': obj.key,
        'properties': props,
        'geometry': json.loads(obj.geometry.geojson),
    }


def build_layer_geojson(layer):
    """FeatureCollection string for the layer, in object order."""
    from survey.models import LayerObjectAsset
    covers = {}
    for asset in (LayerObjectAsset.objects
                  .filter(object__layer=layer, kind='image')
                  .order_by('object_id', 'position', 'id')):
        covers.setdefault(asset.object_id, asset.url)
    features = [feature_for_object(obj, covers.get(obj.pk, ''))
                for obj in layer.items.order_by('position', 'id')]
    return json.dumps({'type': 'FeatureCollection', 'features': features},
                      ensure_ascii=False, separators=(',', ':'))


def rebuild_layer(layer):
    """Recompute the derived GeoJSON and its counters; bumps `updated_at`, which
    is what the endpoint's ETag hangs on. Call after every object/asset write."""
    geojson = build_layer_geojson(layer)
    layer.geojson = geojson
    layer.feature_count = layer.items.count()
    layer.size_bytes = len(geojson.encode('utf-8'))
    layer.save(update_fields=['geojson', 'feature_count', 'size_bytes', 'updated_at'])
    return layer


def check_object_caps(layer, adding=1):
    """FD-1's caps apply to the derived layer: refuse an object that would push
    the layer past the feature count or the served-size limit."""
    count = layer.items.count()
    if count + adding > MAX_LAYER_FEATURES:
        raise LayerValidationError(
            f"This layer holds {count} objects; the limit is {MAX_LAYER_FEATURES}.")
    if layer.size_bytes > MAX_LAYER_BYTES:
        raise LayerValidationError(
            f"This layer's map data is over {MAX_LAYER_BYTES // (1024 * 1024)} MB. "
            "Simplify its geometry or split it into two layers.")


def bbox_of_collection(geojson_str):
    """(min_lng, min_lat, max_lng, max_lat) or None — used to verify the split migration."""
    try:
        parsed = json.loads(geojson_str)
    except ValueError:
        return None
    coords = [c for f in parsed.get('features') or [] for c in _geometry_coords(f.get('geometry'))]
    if not coords:
        return None
    lngs = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return (min(lngs), min(lats), max(lngs), max(lats))
