"""What a public surface may show of answers (change data-aggregate, ADR-001 move 2, §6.3).

Inside the workspace (Responses, the export, API and MCP) numbers are exact: every reader there
has a role and already sees raw rows. Wherever data leaves those people — the public results
page, Site results blocks, later report embeds and open-data pages — it goes through here:

- ``mask(count, k)``: a bucket greater than zero and under K shows as "<K", and its exact value
  never reaches the payload;
- ``grid(members, k)``: a public map is a grid of square cells counting DISTINCT respondents;
  a cell under K is omitted, not masked, because its location is the sensitive fact. A point
  counts in its cell, a spray cloud in every cell holding one of its dots, a line or polygon in
  every cell it touches.
"""
import math

from django.contrib.gis.gdal import CoordTransform, SpatialReference
from django.contrib.gis.geos import Polygon

_WGS84 = SpatialReference(4326)
_MERC = SpatialReference(3857)
_POINT_TYPES = ('Point', 'MultiPoint')


def mask(count, k):
    """A display dict for a public count: masked when 0 < count < k (no value leaks)."""
    k = max(1, int(k or 1))
    if 0 < count < k:
        return {'value': None, 'display': '<{}'.format(k), 'masked': True}
    return {'value': count, 'display': str(count), 'masked': False}


def grid(members, k=1, cells_across=40, min_cell_m=20.0):
    """`members`: iterable of (session_id, member_id, geometry in WGS 84), any geometry type.

    Returns {'cells': [{'bbox': (minx, miny, maxx, maxy) WGS 84, 'respondents': n,
                        'members': {member ids}}],
             'max': int, 'respondents_total': int, 'cell_m': float}.
    ``members`` per cell is for the caller's per-cell summaries; never serialise it.
    """
    to_merc = CoordTransform(_WGS84, _MERC)
    to_wgs = CoordTransform(_MERC, _WGS84)
    items = []
    sessions = set()
    minx = miny = math.inf
    maxx = maxy = -math.inf
    for session_id, member_id, geom in members:
        if geom is None or geom.empty:
            continue
        m = geom.clone()
        if m.srid is None:
            m.srid = 4326
        m.transform(to_merc)
        x0, y0, x1, y1 = m.extent
        minx, miny, maxx, maxy = min(minx, x0), min(miny, y0), max(maxx, x1), max(maxy, y1)
        sessions.add(session_id)
        items.append((session_id, member_id, m))

    if not items:
        return {'cells': [], 'max': 0, 'respondents_total': 0, 'cell_m': min_cell_m}

    longer = max(maxx - minx, maxy - miny)
    cell = max(min_cell_m, longer / float(cells_across)) if longer > 0 else min_cell_m

    def index(x, y):
        return math.floor((x - minx) / cell), math.floor((y - miny) / cell)

    per_cell = {}
    for session_id, member_id, m in items:
        keys = set()
        if m.geom_type in _POINT_TYPES:
            coords = [m.coords] if m.geom_type == 'Point' else list(m.coords)
            keys = {index(x, y) for x, y in coords}
        else:
            prepared = m.prepared
            x0, y0, x1, y1 = m.extent
            (ix0, iy0), (ix1, iy1) = index(x0, y0), index(x1, y1)
            for ix in range(ix0, ix1 + 1):
                for iy in range(iy0, iy1 + 1):
                    box = Polygon.from_bbox((minx + ix * cell, miny + iy * cell,
                                             minx + (ix + 1) * cell, miny + (iy + 1) * cell))
                    box.srid = 3857
                    if prepared.intersects(box):
                        keys.add((ix, iy))
        for key in keys:
            entry = per_cell.setdefault(key, (set(), set()))
            entry[0].add(session_id)
            entry[1].add(member_id)

    threshold = max(1, int(k or 1))
    cells = []
    for (ix, iy), (cell_sessions, cell_members) in per_cell.items():
        n = len(cell_sessions)
        if n < threshold:
            continue
        box = Polygon.from_bbox((minx + ix * cell, miny + iy * cell,
                                 minx + (ix + 1) * cell, miny + (iy + 1) * cell))
        box.srid = 3857
        box.transform(to_wgs)
        cells.append({'bbox': tuple(box.extent), 'respondents': n, 'members': cell_members})

    return {
        'cells': cells,
        'max': max((c['respondents'] for c in cells), default=0),
        'respondents_total': len(sessions),
        'cell_m': round(cell, 1),
    }
