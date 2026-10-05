"""Server-side density grid for public spray-cloud blocks (spec spraycan-density-views).

Pure function over (session_id, MultiPoint) pairs: no model access, so it is
unit-testable without a page. Cells are squares in Web Mercator (EPSG:3857);
the count per cell is the number of DISTINCT sessions with at least one dot in
it, and cells below `k` are left out of the result entirely.
"""
import math

from django.contrib.gis.gdal import CoordTransform, SpatialReference

_WGS84 = SpatialReference(4326)
_MERC = SpatialReference(3857)


def spray_grid(clouds, k=1, cells_across=40, min_cell_m=20.0):
    """`clouds`: iterable of (session_id, MultiPoint in WGS 84).

    Returns {'cells': [{'bbox': (minx, miny, maxx, maxy) in WGS 84, 'respondents': n}],
             'max': int, 'respondents_total': int, 'cell_m': float}.
    """
    to_merc = CoordTransform(_WGS84, _MERC)
    to_wgs = CoordTransform(_MERC, _WGS84)
    sessions = set()
    merc_clouds = []
    minx = miny = math.inf
    maxx = maxy = -math.inf
    for session_id, geom in clouds:
        if geom is None or geom.empty:
            continue
        m = geom.clone()
        if m.srid is None:
            m.srid = 4326
        m.transform(to_merc)
        coords = list(m.coords)
        if not coords:
            continue
        sessions.add(session_id)
        merc_clouds.append((session_id, coords))
        for x, y in coords:
            minx, miny, maxx, maxy = min(minx, x), min(miny, y), max(maxx, x), max(maxy, y)

    if not merc_clouds:
        return {'cells': [], 'max': 0, 'respondents_total': 0, 'cell_m': min_cell_m}

    longer = max(maxx - minx, maxy - miny)
    cell = max(min_cell_m, longer / float(cells_across)) if longer > 0 else min_cell_m

    per_cell = {}
    for session_id, coords in merc_clouds:
        seen = set()
        for x, y in coords:
            key = (math.floor((x - minx) / cell), math.floor((y - miny) / cell))
            if key in seen:
                continue
            seen.add(key)
            per_cell.setdefault(key, set()).add(session_id)

    threshold = max(1, int(k or 1))
    cells = []
    for (ix, iy), ids in per_cell.items():
        n = len(ids)
        if n < threshold:
            continue
        x0, y0 = minx + ix * cell, miny + iy * cell
        from django.contrib.gis.geos import Polygon
        box = Polygon.from_bbox((x0, y0, x0 + cell, y0 + cell))
        box.srid = 3857
        box.transform(to_wgs)
        cells.append({'bbox': tuple(box.extent), 'respondents': n})

    return {
        'cells': cells,
        'max': max((c['respondents'] for c in cells), default=0),
        'respondents_total': len(sessions),
        'cell_m': round(cell, 1),
    }
