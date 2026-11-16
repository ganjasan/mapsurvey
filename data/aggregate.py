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


# Coarser grids tried in turn (change data-grid-adaptive): 40 cells across the answers' extent
# suits a busy survey; on a small one almost every cell holds fewer than K people and the map came
# out empty (19 live /r/ pages measured on 2026-11-16: 11 would have shown nothing).
GRID_STEPS = (40, 20, 10, 5)
GRID_TARGET_SHARE = 0.6


def _project(members):
    """(items in EPSG:3857, bounds, sessions) — done once however many grids are tried."""
    to_merc = CoordTransform(_WGS84, _MERC)
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
    return items, (minx, miny, maxx, maxy), sessions


def _bin(items, bounds, sessions, k, cells_across, min_cell_m):
    to_wgs = CoordTransform(_MERC, _WGS84)
    minx, miny, maxx, maxy = bounds
    longer = max(maxx - minx, maxy - miny)
    cell = max(min_cell_m, longer / float(cells_across)) if longer > 0 else min_cell_m

    def index(x, y):
        return math.floor((x - minx) / cell), math.floor((y - miny) / cell)

    per_cell = {}
    marks = {}      # cell -> points and spray dots inside it; a line or polygon is one mark per cell
    for session_id, member_id, m in items:
        keys = set()
        if m.geom_type in _POINT_TYPES:
            coords = [m.coords] if m.geom_type == 'Point' else list(m.coords)
            for x, y in coords:
                key = index(x, y)
                keys.add(key)
                marks[key] = marks.get(key, 0) + 1
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
                        marks[(ix, iy)] = marks.get((ix, iy), 0) + 1
        for key in keys:
            entry = per_cell.setdefault(key, (set(), set()))
            entry[0].add(session_id)
            entry[1].add(member_id)

    threshold = max(1, int(k or 1))
    cells = []
    shown = set()
    for (ix, iy), (cell_sessions, cell_members) in per_cell.items():
        n = len(cell_sessions)
        if n < threshold:
            continue
        shown |= cell_sessions
        box = Polygon.from_bbox((minx + ix * cell, miny + iy * cell,
                                 minx + (ix + 1) * cell, miny + (iy + 1) * cell))
        box.srid = 3857
        box.transform(to_wgs)
        cells.append({'bbox': tuple(box.extent), 'respondents': n, 'members': cell_members,
                      'marks': marks.get((ix, iy), 0)})
    return {
        'cells': cells,
        'max': max((c['respondents'] for c in cells), default=0),
        'respondents_total': len(sessions),
        'respondents_shown': len(shown),
        'respondents_hidden': len(sessions) - len(shown),
        'cell_m': round(cell, 1),
        'cells_across': cells_across,
    }


def grid(members, k=1, cells_across=None, min_cell_m=20.0, steps=GRID_STEPS, target=GRID_TARGET_SHARE):
    """`members`: iterable of (session_id, member_id, geometry in WGS 84), any geometry type.

    Returns {'cells': [{'bbox': (minx, miny, maxx, maxy) WGS 84, 'respondents': n,
                        'members': {member ids}, 'marks': points and spray dots inside}],
             'max', 'respondents_total', 'respondents_shown', 'respondents_hidden', 'cell_m',
             'cells_across'}.
    ``members`` per cell is for the caller's per-cell summaries; never serialise it.

    `cells_across` fixes the grid; left out, the finest of `steps` that shows at least `target`
    of the respondents is used — else the one showing the most (ties: the finer). Cells under K
    are omitted either way: a coarser grid shows more people, never anyone alone.
    """
    items, bounds, sessions = _project(members)
    if not items:
        return {'cells': [], 'max': 0, 'respondents_total': 0, 'respondents_shown': 0,
                'respondents_hidden': 0, 'cell_m': min_cell_m, 'cells_across': cells_across or steps[0]}
    if cells_across:
        return _bin(items, bounds, sessions, k, cells_across, min_cell_m)
    best = None
    for across in steps:
        result = _bin(items, bounds, sessions, k, across, min_cell_m)
        if result['respondents_shown'] >= target * result['respondents_total']:
            return result
        if best is None or result['respondents_shown'] > best['respondents_shown']:
            best = result
    return best
