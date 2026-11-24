"""A study area from a place name (change map-layers-study-area, design D8).

The study area editor asks OpenStreetMap's Nominatim for boundaries — server-side, from the editor
only, never from a respondent page. Photon (the Wizard's geocoder, `survey/ai/geocode.py`) answers
with a point, so it cannot give an outline; Nominatim's `polygon_geojson` does.

What a candidate becomes depends on the geometry OpenStreetMap holds (owner, 2026-11-24):
- a polygon or multipolygon is the boundary as it is;
- a line (a street, a river, a rail line) becomes a corridor — the line buffered by the width the
  creator picks (50 / 100 / 200 m, default 100 m), rebuilt from the cache when the width changes;
- a point becomes a rectangle around it: its bounding box when that is more than 100 m across,
  otherwise 500 × 500 m; it is labelled as having no boundary in OpenStreetMap.

Nominatim's usage policy: an identifying User-Agent, at most one request a second, no bulk use.
Answers are cached for 30 days by query (and each result by its OSM reference), the whole app
waits its turn on a one-second lock, and each user is rate-limited by the view.
"""
import hashlib
import json
import logging
import math
import time

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

USER_AGENT = 'Mapsurvey/1.0 (+https://mapsurvey.org)'
TIMEOUT_SECONDS = 8
CACHE_SECONDS = 30 * 24 * 3600
MAX_CANDIDATES = 5
CORRIDOR_WIDTHS = (50, 100, 200)
DEFAULT_WIDTH = 100
POINT_SQUARE_M = 500
POINT_MIN_BBOX_M = 100
METRES_PER_DEGREE = 111320.0


class LookupUnavailable(Exception):
    """Nominatim did not answer usefully; the editor offers upload and drawing instead."""


def _url():
    return getattr(settings, 'NOMINATIM_URL', 'https://nominatim.openstreetmap.org').rstrip('/')


def _key(prefix, value):
    return f'study_area:{prefix}:' + hashlib.sha1(value.encode('utf-8')).hexdigest()


def _wait_turn():
    """One Nominatim request a second for the whole app (cache.add is atomic)."""
    for _attempt in range(3):
        if cache.add('study_area:nominatim:turn', 1, timeout=1):
            return
        time.sleep(0.4)


def _fetch(query, language):
    _wait_turn()
    try:
        response = requests.get(f'{_url()}/search', params={
            'q': query, 'format': 'jsonv2', 'polygon_geojson': 1, 'polygon_threshold': 0.0005,
            'limit': MAX_CANDIDATES, 'dedupe': 1,
        }, headers={'User-Agent': USER_AGENT, 'Accept-Language': language or 'en'}, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        logger.info('study area lookup %r failed: %s', query, type(exc).__name__)
        raise LookupUnavailable()
    if response.status_code != 200:
        logger.info('study area lookup %r: HTTP %s', query, response.status_code)
        raise LookupUnavailable()
    try:
        data = response.json()
    except ValueError:
        raise LookupUnavailable()
    return data if isinstance(data, list) else []


def _kind(geometry):
    gtype = (geometry or {}).get('type')
    if gtype in ('Polygon', 'MultiPolygon'):
        return 'polygon'
    if gtype in ('LineString', 'MultiLineString'):
        return 'line'
    return 'point'


def _osm_ref(raw):
    osm_type = str(raw.get('osm_type') or '')[:1].upper()
    return f'{osm_type}{raw.get("osm_id")}' if osm_type and raw.get('osm_id') else ''


def _bbox(raw):
    """[west, south, east, north] from Nominatim's [south, north, west, east] strings."""
    try:
        south, north, west, east = (float(v) for v in raw.get('boundingbox') or [])
    except (TypeError, ValueError):
        return None
    return [west, south, east, north]


def _span_m(bbox):
    west, south, east, north = bbox
    lat = math.radians((south + north) / 2)
    return max((east - west) * METRES_PER_DEGREE * math.cos(lat), (north - south) * METRES_PER_DEGREE)


def _square(lng, lat, metres):
    dlat = metres / 2 / METRES_PER_DEGREE
    dlng = metres / 2 / (METRES_PER_DEGREE * max(math.cos(math.radians(lat)), 0.01))
    return {'type': 'Polygon', 'coordinates': [[[lng - dlng, lat - dlat], [lng + dlng, lat - dlat],
                                                [lng + dlng, lat + dlat], [lng - dlng, lat + dlat],
                                                [lng - dlng, lat - dlat]]]}


def _rectangle(raw):
    bbox = _bbox(raw)
    if bbox and _span_m(bbox) > POINT_MIN_BBOX_M:
        west, south, east, north = bbox
        return {'type': 'Polygon', 'coordinates': [[[west, south], [east, south], [east, north],
                                                    [west, north], [west, south]]]}
    return _square(float(raw.get('lon') or 0), float(raw.get('lat') or 0), POINT_SQUARE_M)


def corridor(line, width_m):
    """The line buffered by `width_m` metres either side, on the spheroid, as GeoJSON."""
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ST_AsGeoJSON(ST_Buffer(ST_GeomFromGeoJSON(%s)::geography, %s, 'endcap=round join=round quad_segs=3')::geometry, 7)",
            [json.dumps(line), float(width_m)])
        row = cursor.fetchone()
    return json.loads(row[0]) if row and row[0] else None


def _line_length_m(line):
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute('SELECT ST_Length(ST_GeomFromGeoJSON(%s)::geography)', [json.dumps(line)])
        row = cursor.fetchone()
    return float(row[0] or 0)


def outline(raw, width_m=DEFAULT_WIDTH):
    """The polygon a candidate becomes (see the module docstring)."""
    geometry = raw.get('geojson') or {}
    kind = _kind(geometry)
    if kind == 'polygon':
        return geometry
    if kind == 'line':
        return corridor(geometry, width_m if width_m in CORRIDOR_WIDTHS else DEFAULT_WIDTH)
    return _rectangle(raw)


def _candidate(raw):
    geometry = raw.get('geojson') or {}
    kind = _kind(geometry)
    item = {
        'osm_ref': _osm_ref(raw),
        'name': raw.get('display_name') or raw.get('name') or '',
        'type': (raw.get('addresstype') or raw.get('type') or raw.get('category') or '').replace('_', ' '),
        'kind': kind,
        'bbox': _bbox(raw),
    }
    if kind == 'line':
        item['short_segment'] = _line_length_m(geometry) < 300
    return item


def search(query, language='en'):
    """Up to five candidates for a place name: [{osm_ref, name, type, kind, bbox, short_segment?}].
    Raises LookupUnavailable when Nominatim cannot be reached."""
    query = (query or '').strip()[:200]
    if not query:
        return []
    key = _key('q', f'{language}|{query.lower()}')
    results = cache.get(key)
    if results is None:
        results = _fetch(query, language)
        cache.set(key, results, CACHE_SECONDS)
    out = []
    for raw in results[:MAX_CANDIDATES]:
        ref = _osm_ref(raw)
        if ref:
            cache.set(_key('osm', ref), raw, CACHE_SECONDS)
        out.append(_candidate(raw))
    return out


def candidate_outline(osm_ref, width_m=DEFAULT_WIDTH):
    """The polygon for a candidate a search returned (from the cache), or None when it expired."""
    raw = cache.get(_key('osm', str(osm_ref or '')))
    if raw is None:
        return None
    return {'geometry': outline(raw, width_m), 'name': raw.get('display_name') or '',
            'kind': _kind(raw.get('geojson') or {})}
