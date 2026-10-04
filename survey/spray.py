"""Spray clouds (spec spraycan-question): the one place that knows what a cloud
*is* beyond "a MultiPoint".

- `normalize_dots` is what the section POST stores: the respondent's dots
  snapped to a one-metre grid, duplicates dropped, order kept. A dot is an
  artefact of how the pointer moved; one dot per square metre makes the count a
  function of painted area and dwell, not of the mouse's event rate — paint
  saturates, exactly as it does in a graphics editor.
- `cloud_area_m2` / `describe` are the two numbers every read surface shows
  for a cloud (attribute table, drawer, export): how many dots, how large the
  painted extent is (convex hull).
"""
import math

from django.contrib.gis.geos import MultiPoint, Point

# Metres per degree at the equator; longitude is scaled by cos(latitude).
_M_PER_DEG_LAT = 110574.0
_M_PER_DEG_LNG = 111320.0

GRID_M = 1.0


def normalize_dots(coords, limit):
    """Finite WGS 84 pairs → list of (x, y) snapped to a GRID_M grid, first
    occurrence wins, at most `limit`. Returns None on an unusable coordinate."""
    seen = set()
    out = []
    for c in coords:
        try:
            x, y = float(c[0]), float(c[1])
        except (TypeError, ValueError, IndexError):
            return None
        if not (math.isfinite(x) and math.isfinite(y)) or not (-180 <= x <= 180 and -90 <= y <= 90):
            return None
        key = (
            math.floor(x * _M_PER_DEG_LNG * math.cos(math.radians(y)) / GRID_M),
            math.floor(y * _M_PER_DEG_LAT / GRID_M),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append((x, y))
        if len(out) >= limit:
            break
    return out


def cloud_from_dots(dots):
    return MultiPoint(*[Point(x, y, srid=4326) for x, y in dots], srid=4326)


def cloud_area_m2(geom):
    """Area of the cloud's convex hull in square metres (0 for fewer than three
    non-collinear dots). Web Mercator area corrected by cos²(lat): exact enough
    for a painted neighbourhood, and it needs no extra projection libraries."""
    if geom is None or geom.empty or len(geom) < 3:
        return 0.0
    hull = geom.convex_hull
    if hull.geom_type != 'Polygon':
        return 0.0
    lat = geom.centroid.y
    h = hull.clone()
    if h.srid is None:
        h.srid = 4326
    h.transform(3857)
    return h.area * math.cos(math.radians(lat)) ** 2


def format_area(area_m2):
    if area_m2 >= 1_000_000:
        return '{:.1f} km²'.format(area_m2 / 1_000_000)
    if area_m2 >= 10_000:
        return '{:.1f} ha'.format(area_m2 / 10_000)
    return '{} m²'.format(int(round(area_m2)))


def describe(geom):
    """'394 dots · 0.8 km²' — the attribute-table cell and the drawer line."""
    n = len(geom) if geom is not None else 0
    area = cloud_area_m2(geom)
    return '{} dots · {}'.format(n, format_area(area)) if area > 0 else '{} dots'.format(n)
