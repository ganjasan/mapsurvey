"""Geometry helpers for survey reports (skill survey-report): distances, hotspots, georeferencing.

    from geo import haversine_m, nearest, hotspots, georeference
"""
import math


def haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres."""
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(a))


def nearest(lat, lon, points):
    """(distance_m, item) of the nearest of `points` = [(lat, lon, item), ...]."""
    return min((haversine_m(lat, lon, la, lo), it) for la, lo, it in points)


def hotspots(pins, cell_m=120, merge_m=150, min_pins=2):
    """Group pins into ranked hotspots.

    pins: list of dicts with 'lat' and 'lon' (any other keys are kept).
    Pins fall into a cell_m grid; cells are taken largest first and merged into an existing
    hotspot whose centre is within merge_m. Returns [{'n', 'lat', 'lon', 'count', 'pins'}],
    largest first, only hotspots with at least min_pins pins.
    A single-pin survey on a housing estate worked well with 120 m cells + 150 m merge; a dense
    neighbourhood with many pins per resident with 120 m cells and no merge (merge_m=0).
    """
    if not pins:
        return []
    lat0 = sum(p['lat'] for p in pins) / len(pins)
    kx = 111320 * math.cos(math.radians(lat0))
    cells = {}
    for p in pins:
        cells.setdefault((round(p['lat'] * 111320 / cell_m), round(p['lon'] * kx / cell_m)), []).append(p)
    spots = []
    for ps in sorted(cells.values(), key=len, reverse=True):
        lat = sum(p['lat'] for p in ps) / len(ps)
        lon = sum(p['lon'] for p in ps) / len(ps)
        for s in spots:
            if haversine_m(lat, lon, s['lat'], s['lon']) < merge_m:
                s['pins'] += ps
                s['lat'] = sum(p['lat'] for p in s['pins']) / len(s['pins'])
                s['lon'] = sum(p['lon'] for p in s['pins']) / len(s['pins'])
                break
        else:
            spots.append({'lat': lat, 'lon': lon, 'pins': list(ps)})
    spots = sorted((s for s in spots if len(s['pins']) >= min_pins), key=lambda s: -len(s['pins']))
    for i, s in enumerate(spots, 1):
        s['n'], s['count'] = i, len(s['pins'])
    return spots


def _merc(lat, lon):
    return lon, math.degrees(math.log(math.tan(math.radians(45 + lat / 2))))


def georeference(pixel_points, geo_points, iterations=20):
    """Fit a customer's map image to coordinates using features both show.

    pixel_points: [(x, y)] markers found in the image (e.g. blue rings of existing bins).
    geo_points:   [(lat, lon)] the same features from the layer, any order.
    Returns (to_latlon, residuals_px): a function (x, y) -> (lat, lon) and the per-point error.
    Model: web-mercator scale + offset (no rotation), matched by nearest neighbour and refined.
    First use: 14 shared points, max residual 1 px ≈ 1.5 m.
    """
    G = [(_merc(la, lo)[0], -_merc(la, lo)[1]) for la, lo in geo_points]
    P = list(pixel_points)
    gx = [g[0] for g in G]; gy = [g[1] for g in G]; px = [p[0] for p in P]; py = [p[1] for p in P]
    s = ((max(px) - min(px)) / (max(gx) - min(gx)) + (max(py) - min(py)) / (max(gy) - min(gy))) / 2
    tx = sum(px) / len(px) - s * sum(gx) / len(gx)
    ty = sum(py) / len(py) - s * sum(gy) / len(gy)
    for _ in range(iterations):
        pairs = [(g, min(P, key=lambda p: (p[0] - (s * g[0] + tx)) ** 2 + (p[1] - (s * g[1] + ty)) ** 2)) for g in G]
        # least squares for x = s*gx + tx, y = s*gy + ty
        n = len(pairs)
        sgx = sum(g[0] for g, _ in pairs); sgy = sum(g[1] for g, _ in pairs)
        spx = sum(p[0] for _, p in pairs); spy = sum(p[1] for _, p in pairs)
        sgg = sum(g[0] ** 2 + g[1] ** 2 for g, _ in pairs); sgp = sum(g[0] * p[0] + g[1] * p[1] for g, p in pairs)
        s = (sgp - (sgx * spx + sgy * spy) / n) / (sgg - (sgx ** 2 + sgy ** 2) / n)
        tx = (spx - s * sgx) / n; ty = (spy - s * sgy) / n
    residuals = [math.hypot(p[0] - (s * g[0] + tx), p[1] - (s * g[1] + ty)) for g, p in pairs]

    def to_latlon(x, y):
        mx, my = (x - tx) / s, -(y - ty) / s
        return math.degrees(2 * math.atan(math.exp(math.radians(my))) - math.pi / 2), mx

    return to_latlon, residuals
