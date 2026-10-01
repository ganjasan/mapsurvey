"""Build Leaflet heat-map pages for a customer story (skill customer-story). Data section is per story."""
import base64
import csv
import gzip
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'maps'
OUT.mkdir(exist_ok=True)

TEMPLATE = """<!DOCTYPE html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
<style>html,body{margin:0;background:#fff}#map{width:1000px;height:760px}.leaflet-control-attribution{font-size:11px}</style>
</head><body><div id="map"></div><script>
const DATA = __DATA__;
const map = L.map('map', {zoomControl:false, attributionControl:true});
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom:19, attribution:'&copy; OpenStreetMap contributors'}).addTo(map);
for (const g of DATA.geojson || []) L.geoJSON(g.data, {style: g.style, interactive:false}).addTo(map);
for (const h of DATA.heat) L.heatLayer(h.points, {radius:h.radius||22, blur:h.blur||18, maxZoom:17, minOpacity:0.2, max:h.max||1, gradient:h.gradient}).addTo(map);
map.fitBounds(DATA.bounds, {padding:[30,30]});
if (DATA.zoom) map.setZoom(DATA.zoom);
window.__ready = true;
</script></body></html>"""


def mono(color):
    return {0.2: color + '00', 0.5: color + '80', 1: color}


def write(name, data):
    (OUT / f'{name}.html').write_text(TEMPLATE.replace('__DATA__', json.dumps(data)), encoding='utf-8')


# --- Remington -------------------------------------------------------------
rows = list(csv.DictReader((HERE / 'data' / 'remington_points.csv').open()))
cats = {
    'Q_5571512833': ('#1B6FB8', 'value or protect'),
    'Q_5914671305': ('#0FA58E', 'improve'),
    'Q_0394330883': ('#C0622B', 'difficult or unsafe'),
}
layers = {}
for r in rows:
    if r['code'] in cats:
        layers.setdefault(r['code'], []).append([float(r['lat']), float(r['lon']), 1])
gria = []
for r in csv.DictReader((HERE / 'data' / 'gria_layers.csv').open()):
    gj = json.loads(gzip.decompress(base64.b64decode(r['gz'])).decode())
    style = {'color': r['color'], 'weight': 2.5 if 'Boundary' in r['name'] else 1, 'fill': 'Boundary' not in r['name'],
             'fillOpacity': 0.18, 'dashArray': '6 4' if 'Boundary' in r['name'] else None}
    gria.append({'data': gj, 'style': style})
def flat(x):
    return [x] if isinstance(x[0], (int, float)) else [c for y in x for c in flat(y)]
coords = [c for g in gria if g['style']['dashArray'] for f in g['data']['features'] for c in flat(f['geometry']['coordinates'])]
lats = [c[1] for c in coords]; lons = [c[0] for c in coords]
for code, (color, label) in cats.items():
    write(f'remington-{label.split()[0]}', {
        'heat': [{'points': layers[code], 'gradient': mono(color), 'radius': 22, 'blur': 18, 'max': 5}],
        'geojson': gria, 'bounds': [[min(lats), min(lons)], [max(lats), max(lons)]]})
write('remington-all', {
    'heat': [{'points': layers[c], 'gradient': mono(cats[c][0]), 'radius': 22, 'blur': 18, 'max': 5} for c in cats],
    'geojson': gria, 'bounds': [[min(lats), min(lons)], [max(lats), max(lons)]]})
print('remington', {cats[c][1]: len(layers[c]) for c in cats})

# --- Pszów -----------------------------------------------------------------
rows = list(csv.DictReader((HERE / 'data' / 'pszow_geo.csv').open()))
pts, lines, polys = [], [], []
for r in rows:
    g = json.loads(r['geom'])
    if g['type'] == 'Point':
        pts.append([g['coordinates'][1], g['coordinates'][0], 1])
    elif g['type'] == 'LineString':
        lines.append({'type': 'Feature', 'geometry': g, 'properties': {}})
    elif g['type'] == 'Polygon':
        polys.append({'type': 'Feature', 'geometry': g, 'properties': {}})
allc = [c for r in rows for c in ([json.loads(r['geom'])['coordinates']] if json.loads(r['geom'])['type'] == 'Point' else
        (json.loads(r['geom'])['coordinates'] if json.loads(r['geom'])['type'] == 'LineString' else json.loads(r['geom'])['coordinates'][0]))]
lats = [c[1] for c in allc]; lons = [c[0] for c in allc]
# clip the bounds to the 2nd..98th percentile so one stray mark does not zoom the map out
lats.sort(); lons.sort(); k = int(len(lats) * 0.02)
bounds = [[lats[k], lons[k]], [lats[-1 - k], lons[-1 - k]]]
write('pszow-points', {'heat': [{'points': pts, 'gradient': mono('#C0622B'), 'radius': 24, 'blur': 20, 'max': 6}],
                       'geojson': [], 'bounds': [[50.0392, 18.3965], [50.0414, 18.3995]], 'zoom': 18})
write('pszow-all', {
    'heat': [{'points': pts, 'gradient': mono('#C0622B'), 'radius': 18, 'blur': 15, 'max': 4}],
    'geojson': [
        {'data': {'type': 'FeatureCollection', 'features': polys}, 'style': {'color': '#1B6FB8', 'weight': 1, 'opacity': 0.35, 'fillOpacity': 0.06}},
        {'data': {'type': 'FeatureCollection', 'features': lines}, 'style': {'color': '#0FA58E', 'weight': 2, 'opacity': 0.35}},
    ], 'bounds': bounds, 'zoom': 17})
print('pszow', len(pts), 'points', len(lines), 'lines', len(polys), 'polygons')

# --- plain "the place" maps for covers ---------------------------------------
gb = [c for g in gria if g['style']['dashArray'] for f in g['data']['features'] for c in flat(f['geometry']['coordinates'])]
write('remington-place', {'heat': [], 'geojson': gria, 'bounds': [[min(c[1] for c in gb), min(c[0] for c in gb)], [max(c[1] for c in gb), max(c[0] for c in gb)]]})
write('pszow-place', {'heat': [], 'geojson': [], 'bounds': [[50.0385, 18.3950], [50.0420, 18.4010]], 'zoom': 17})
