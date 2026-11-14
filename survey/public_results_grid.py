"""Server-side density grid for public spray-cloud blocks (spec spraycan-density-views).

Kept for its callers; the grid itself is `data.aggregate.grid` (change data-aggregate), which
every public map now uses — spray clouds, points, lines and polygons alike.
"""
from data.aggregate import grid


def spray_grid(clouds, k=1, cells_across=40, min_cell_m=20.0):
    """`clouds`: iterable of (session_id, MultiPoint in WGS 84).

    Returns {'cells': [{'bbox': (minx, miny, maxx, maxy) in WGS 84, 'respondents': n}],
             'max': int, 'respondents_total': int, 'cell_m': float}.
    """
    out = grid(((sid, i, geom) for i, (sid, geom) in enumerate(clouds)),
               k=k, cells_across=cells_across, min_cell_m=min_cell_m)
    out['cells'] = [{'bbox': c['bbox'], 'respondents': c['respondents']} for c in out['cells']]
    return out
