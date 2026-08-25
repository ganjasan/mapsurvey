"""Reference overlay layers: upload validation.

One helper used by the editor upload endpoint AND ZIP import, so every GeoJSON
that becomes a SurveyMapLayer — interactive, archived or AI-written — passes the
same checks and is stored as a re-serialized parse, never the raw upload bytes.
"""
import json

MAX_LAYER_BYTES = 10 * 1024 * 1024
MAX_LAYER_FEATURES = 5000
MAX_LAYERS_PER_SURVEY = 5


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
