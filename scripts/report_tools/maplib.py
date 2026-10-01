"""Render Leaflet map specs to exact-size images with headless Chromium.

A spec is plain JSON: base ('sat' | 'osm' | 'sat-muted' | 'none'), bounds or center+zoom, size, and
a list of layers drawn in order:
  {'kind': 'geojson', 'data': FC, 'style': {...}, 'styleBy': {'prop': 'n', 'stops': [[min, color, opacity], ...]}}
  {'kind': 'heat', 'points': [[lat, lon, w]], 'color': '#C0622B', 'radius': 24, 'blur': 18, 'max': 5}
  {'kind': 'lines', 'data': FC, 'color': '#0FA58E', 'weight': 3, 'opacity': .35}
  {'kind': 'badges', 'items': [{'lat', 'lon', 'label', 'size', 'color'}]}      numbered circles
  {'kind': 'labels', 'items': [{'lat', 'lon', 'text', 'anchor'}]}               place names
  {'kind': 'dots', 'items': [[lat, lon]], 'color', 'radius'}
  {'kind': 'scale'}                                                             metric scale bar
Tiles: Mapbox satellite (token from the repo .env, used only to render images here — never shipped
in a deliverable) and OpenStreetMap.
"""
import functools
import http.server
import json
import socketserver
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RENDER = Path.cwd() / 'render'   # scratch pages next to wherever the report is built
RENDER.mkdir(exist_ok=True)
import os
def _token():
    if os.environ.get('MAPBOX_ACCESS_TOKEN'):
        return os.environ['MAPBOX_ACCESS_TOKEN']
    env = HERE.parents[1] / '.env'   # repo root .env; the token renders images here and never ships
    for line in env.read_text().splitlines() if env.exists() else []:
        if line.startswith('MAPBOX_ACCESS_TOKEN='):
            return line.split('=', 1)[1].strip()
    return ''
TOKEN = _token()

PAGE = r"""<!DOCTYPE html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@500;600;700&display=swap" rel="stylesheet">
<style>
html,body{margin:0;background:#fff;font-family:'Instrument Sans',Arial,sans-serif}
#map{width:__W__px;height:__H__px;background:#e9e6df}
.leaflet-control-attribution{font-size:10px;background:rgba(255,255,255,.75)!important}
.muted .leaflet-tile-pane{filter:saturate(.35) brightness(1.08) contrast(.9)}
.dim .leaflet-tile-pane{filter:saturate(.2) brightness(.78) contrast(.95)}
.badge{display:flex;align-items:center;justify-content:center;border-radius:50%;color:#fff;font-weight:700;
  border:2.5px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.45);box-sizing:border-box}
.plabel{font-weight:600;font-size:13px;color:#1B2A4A;white-space:nowrap;
  text-shadow:0 0 3px #fff,0 0 3px #fff,0 0 4px #fff,0 0 5px #fff}
.plabel.dark{color:#fff;text-shadow:0 0 3px #000,0 0 4px #000,0 0 6px rgba(0,0,0,.8)}
.leaflet-control-scale-line{font-size:11px;border-color:#1B2A4A}
</style></head><body><div id="map"></div><script>
const S = __SPEC__;
const map = L.map('map', {zoomControl:false, attributionControl:true, zoomSnap:0.25, fadeAnimation:false});
const TOKEN = '__TOKEN__';
const base = S.base || 'sat';
if (base.startsWith('sat')) {
  L.tileLayer('https://api.mapbox.com/v4/mapbox.satellite/{z}/{x}/{y}@2x.jpg90?access_token=' + TOKEN,
    {maxZoom:21, maxNativeZoom:19, tileSize:256, attribution:'Imagery © Mapbox, © Maxar · © OpenStreetMap contributors'}).addTo(map);
} else if (base.startsWith('osm')) {
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom:21, maxNativeZoom:19, attribution:'© OpenStreetMap contributors'}).addTo(map);
}
if (base.endsWith('-muted')) document.getElementById('map').classList.add('muted');
if (base.endsWith('-dim')) document.getElementById('map').classList.add('dim');
function pick(stops, v){ let s = stops[0]; for (const t of stops) if (v >= t[0]) s = t; return s; }
for (const ly of S.layers || []) {
  if (ly.kind === 'geojson') {
    L.geoJSON(ly.data, {interactive:false, style: f => {
      const st = Object.assign({}, ly.style || {});
      if (ly.styleBy) { const s = pick(ly.styleBy.stops, f.properties[ly.styleBy.prop]); st.fillColor = s[1]; st.color = s[1]; st.fillOpacity = s[2]; }
      return st; },
      pointToLayer: (f, latlng) => L.circleMarker(latlng, Object.assign({radius:5}, ly.style || {}))}).addTo(map);
  } else if (ly.kind === 'heat') {
    const c = ly.color;
    L.heatLayer(ly.points, {radius: ly.radius || 24, blur: ly.blur || 18, maxZoom: 18, minOpacity: ly.minOpacity || 0.15, max: ly.max || 4,
      gradient: ly.gradient || {0.15: c + '00', 0.45: c + '99', 0.8: c + 'DD', 1: c}}).addTo(map);
  } else if (ly.kind === 'lines') {
    L.geoJSON(ly.data, {interactive:false, style: {color: ly.color, weight: ly.weight || 3, opacity: ly.opacity || .4, lineCap:'round', lineJoin:'round'}}).addTo(map);
  } else if (ly.kind === 'dots') {
    for (const p of ly.items) L.circleMarker(p, {radius: ly.radius || 4, color:'#fff', weight:1.2, fillColor: ly.color, fillOpacity: ly.opacity || .9, interactive:false}).addTo(map);
  } else if (ly.kind === 'badges') {
    for (const b of ly.items) {
      const s = b.size || 28;
      L.marker([b.lat, b.lon], {interactive:false, icon: L.divIcon({className:'', iconSize:[s, s], iconAnchor:[s/2, s/2],
        html:`<div class="badge" style="width:${s}px;height:${s}px;background:${b.color};font-size:${Math.round(s*.48)}px">${b.label}</div>`})}).addTo(map);
    }
  } else if (ly.kind === 'labels') {
    for (const b of ly.items) {
      const a = b.anchor || 'c';
      const tx = a === 'l' ? '0' : a === 'r' ? '-100%' : '-50%';
      L.marker([b.lat, b.lon], {interactive:false, icon: L.divIcon({className:'', iconSize:[0,0],
        html:`<div class="plabel ${b.dark ? 'dark' : ''}" style="transform:translate(${tx},-50%);font-size:${b.size || 13}px">${b.text}</div>`})}).addTo(map);
    }
  } else if (ly.kind === 'image') {
    L.imageOverlay(ly.url, ly.bounds, {opacity: ly.opacity || 1, interactive:false}).addTo(map);
  } else if (ly.kind === 'scale') {
    L.control.scale({imperial:false, position: ly.position || 'bottomleft', maxWidth: 120}).addTo(map);
  }
}
if (S.bounds) map.fitBounds(S.bounds, {padding: S.padding || [20, 20]}); else map.setView(S.center, S.zoom);
if (S.zoom && S.bounds) map.setZoom(S.zoom);
let pending = 0; map.eachLayer(l => { if (l instanceof L.TileLayer) { pending++; l.on('load', () => pending--); } });
window.tilesDone = () => pending <= 0;
</script></body></html>"""


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@functools.lru_cache(maxsize=1)
def _server():
    httpd = socketserver.TCPServer(('127.0.0.1', 0), functools.partial(_Quiet, directory=str(RENDER)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd.server_address[1]


def render_many(jobs, scale=2):
    """jobs = [(spec, out_path)]. One browser for all of them."""
    from playwright.sync_api import sync_playwright
    port = _server()
    with sync_playwright() as p:
        b = p.chromium.launch()
        for spec, out in jobs:
            w, h = spec.get('size', (1000, 700))
            ctx = b.new_context(viewport={'width': w + 20, 'height': h + 20}, device_scale_factor=scale,
                                user_agent='Mozilla/5.0 (X11; Linux x86_64) mapsurvey-report/1.0')
            page = ctx.new_page()
            name = Path(out).stem + '.html'
            (RENDER / name).write_text(PAGE.replace('__W__', str(w)).replace('__H__', str(h)).replace('__TOKEN__', TOKEN)
                                       .replace('__SPEC__', json.dumps(spec)), encoding='utf-8')
            page.goto(f'http://127.0.0.1:{port}/{name}', wait_until='networkidle')
            try:
                page.wait_for_function('window.tilesDone && window.tilesDone()', timeout=20000)
            except Exception:
                print('  tiles timeout', out)
            time.sleep(0.8)
            out = Path(out)
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.suffix == '.jpg':
                page.locator('#map').screenshot(path=str(out), type='jpeg', quality=88)
            else:
                page.locator('#map').screenshot(path=str(out))
            ctx.close()
        b.close()


def render(spec, out, scale=2):
    render_many([(spec, out)], scale)
