#!/usr/bin/env python3
"""Turn a settings document into a Mapbox GL style and publish it to the Mapsurvey account.

Usage:
    python scripts/mapbox_style_publish.py scripts/map_styles/paper_a.json
    python scripts/mapbox_style_publish.py scripts/map_styles/paper_a.json --dry-run --out /tmp/a.json
    python scripts/mapbox_style_publish.py scripts/map_styles/paper_a.json --base-file survey/tests/fixtures/mapbox_streets_v12.json

Change map-styles-rendering-path (#541, epic #545). Paper A and Paper B were built by hand
over `streets-v12` on 2026-11-06; this is that work as code, so a style is a settings
document rather than a thing that lives in Mapbox Studio. `apply_settings` is pure (no
network, no Django); every call to Mapbox goes through `MapboxStylesClient`, which tests
replace. The token is `MAPBOX_STYLES_TOKEN` from the environment or the repo's `.env`
(a secret token with styles:read, styles:write, styles:list) — never the public one, and
nothing here is ever rendered into a page.

A style is named after its settings' `name`; a second run with the same name updates the
existing style (`PATCH`) instead of creating another, so re-running after a settings edit
is the way to change a published style. The settings are kept in the style's `metadata`
under `mapsurvey:settings`, which is how a hosted style can be traced back to its source.

Settings keys (every key optional; absent = leave the base as it is):

    name                  style name in the account (required to publish)
    base                  base style id, default "mapbox/streets-v12"
    poi                   false removes POI, transit, airport and address labels
    paths                 false removes footpaths, steps, pedestrian areas, crosswalks
    shields               false removes route shields, one-way arrows, intersections
    relief                false removes hillshade, bathymetry, ferries, aerialways
    regions               false removes first-level admin boundaries (states, Länder)
    land                  background colour
    park                  colour for parks, grass, cemeteries, pitches, wood and scrub
    water                 colour for water bodies and waterways
    buildings             {"fill", "outline", "minzoom"} or false to remove buildings
    roads                 {"fill", "minor_low_zoom", "casing"}; minor roads use
                          minor_low_zoom below zoom 14 and fill from 14
    boundary              colour of national boundaries
    labels                {"major", "minor", "halo", "halo_width", "bold_roads"}
    place_names_maxzoom   last zoom at which city/state/continent names show
    greyscale             true turns every colour into a grey blended on white
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

DEFAULT_BASE = 'mapbox/streets-v12'
GENERATOR = 'mapbox_style_publish/1'
API = 'https://api.mapbox.com'

# ── layer groups of streets-v12 that a setting removes ────────────────────────

POI_LAYERS = (
    'poi-label', 'transit-label', 'airport-label', 'natural-point-label',
    'ferry-aerialway-label', 'golf-hole-label', 'building-entrance',
    'building-number-label', 'block-number-label',
)
PATH_LAYERS = (
    'road-path', 'road-path-bg', 'road-pedestrian', 'road-pedestrian-case',
    'road-pedestrian-polygon-fill', 'road-pedestrian-polygon-pattern', 'road-polygon',
    'road-steps', 'road-steps-bg',
    'bridge-path', 'bridge-path-bg', 'bridge-pedestrian', 'bridge-pedestrian-case',
    'bridge-steps', 'bridge-steps-bg',
    'tunnel-path', 'tunnel-pedestrian', 'tunnel-steps',
    'path-pedestrian-label', 'crosswalks', 'golf-hole-line', 'pitch-outline',
    'land-structure-line', 'land-structure-polygon',
)
SHIELD_LAYERS = (
    'road-oneway-arrow-blue', 'road-oneway-arrow-white',
    'bridge-oneway-arrow-blue', 'bridge-oneway-arrow-white',
    'tunnel-oneway-arrow-blue', 'tunnel-oneway-arrow-white',
    'road-exit-shield', 'road-number-shield', 'road-intersection',
    'turning-feature', 'turning-feature-outline', 'level-crossing', 'road-construction',
)
RELIEF_LAYERS = ('hillshade', 'water-depth', 'aerialway', 'ferry', 'ferry-auto')
REGION_LAYERS = ('admin-1-boundary', 'admin-1-boundary-bg')
BUILDING_LAYERS = ('building', 'building-underground')

REMOVALS = {
    'poi': POI_LAYERS,
    'paths': PATH_LAYERS,
    'shields': SHIELD_LAYERS,
    'relief': RELIEF_LAYERS,
    'regions': REGION_LAYERS,
}

# ── layers a colour setting paints ────────────────────────────────────────────

PARK_CLASSES = ['park', 'grass', 'cemetery', 'pitch', 'wood', 'scrub']
WATER_LAYERS = {
    'water': 'fill-color', 'water-shadow': 'fill-color',
    'waterway': 'line-color', 'waterway-shadow': 'line-color',
}
BOUNDARY_LAYERS = ('admin-0-boundary-bg', 'admin-0-boundary', 'admin-0-boundary-disputed')
MAJOR_LABELS = ('road-label', 'settlement-major-label', 'state-label', 'country-label', 'continent-label')
MINOR_LABELS = ('waterway-label', 'natural-line-label', 'water-line-label', 'water-point-label',
                'settlement-subdivision-label', 'settlement-minor-label')
PLACE_NAME_LAYERS = ('settlement-minor-label', 'settlement-major-label', 'state-label', 'continent-label')
ICONLESS_LABELS = ('settlement-minor-label', 'settlement-major-label', 'country-label')
MINOR_ROAD_KINDS = ('minor', 'minor-link', 'street', 'street-low', 'construction')
ROAD_PREFIXES = ('road-', 'bridge-', 'tunnel-')

# Top-level keys of a fetched style that a POST/PATCH must not carry.
READ_ONLY_KEYS = ('id', 'owner', 'created', 'modified', 'visibility', 'protected', 'draft')


# ── pure transformation ───────────────────────────────────────────────────────

def apply_settings(base, settings):
    """Return a new style: `base` with `settings` applied. Pure; `base` is not changed."""
    style = copy.deepcopy(base)
    for key in READ_ONLY_KEYS:
        style.pop(key, None)
    settings = dict(settings or {})

    drop = set()
    for key, layer_ids in REMOVALS.items():
        if settings.get(key) is False:
            drop.update(layer_ids)
    if settings.get('buildings') is False:
        drop.update(BUILDING_LAYERS)
    style['layers'] = [layer for layer in style['layers'] if layer['id'] not in drop]
    by_id = {layer['id']: layer for layer in style['layers']}

    if 'land' in settings:
        _paint(by_id, 'land', 'background-color', settings['land'])
    if 'park' in settings:
        park = settings['park']
        _paint(by_id, 'landcover', 'fill-color', park)
        _paint(by_id, 'landcover', 'fill-opacity', 1)
        _paint(by_id, 'national-park', 'fill-color', park)
        _paint(by_id, 'national-park', 'fill-opacity', 1)
        _paint(by_id, 'landuse', 'fill-color',
               ['match', ['get', 'class'], PARK_CLASSES, park, settings.get('land', '#ffffff')])
        _paint(by_id, 'landuse', 'fill-opacity', 1)
    if 'water' in settings:
        for layer_id, prop in WATER_LAYERS.items():
            _paint(by_id, layer_id, prop, settings['water'])
    buildings = settings.get('buildings')
    if isinstance(buildings, dict):
        for layer_id in BUILDING_LAYERS:
            if 'fill' in buildings:
                _paint(by_id, layer_id, 'fill-color', buildings['fill'])
                _paint(by_id, layer_id, 'fill-opacity', 1)
            if 'outline' in buildings:
                _paint(by_id, layer_id, 'fill-outline-color', buildings['outline'])
            if 'minzoom' in buildings and layer_id in by_id:
                by_id[layer_id]['minzoom'] = buildings['minzoom']
    roads = settings.get('roads')
    if isinstance(roads, dict):
        _paint_roads(style['layers'], roads)
    if 'boundary' in settings:
        for layer_id in BOUNDARY_LAYERS:
            _paint(by_id, layer_id, 'line-color', settings['boundary'])
    labels = settings.get('labels')
    if isinstance(labels, dict):
        _paint_labels(by_id, labels)
    if 'place_names_maxzoom' in settings:
        for layer_id in PLACE_NAME_LAYERS:
            if layer_id in by_id:
                by_id[layer_id]['maxzoom'] = settings['place_names_maxzoom']
    if settings.get('greyscale'):
        style['layers'] = greyscale(style['layers'])

    if settings.get('name'):
        style['name'] = settings['name']
    metadata = dict(style.get('metadata') or {})
    metadata['mapsurvey:generator'] = GENERATOR
    metadata['mapsurvey:settings'] = settings
    style['metadata'] = metadata
    return style


def _paint(by_id, layer_id, prop, value):
    layer = by_id.get(layer_id)
    if layer is not None:
        layer.setdefault('paint', {})[prop] = value


def _road_kind(layer):
    """'casing' | 'minor' | 'major' | None for a line layer of the road source-layer."""
    if layer.get('type') != 'line' or layer.get('source-layer') != 'road':
        return None
    layer_id = layer['id']
    if not layer_id.startswith(ROAD_PREFIXES):
        return None
    if layer_id.endswith('-case') or '-rail' in layer_id:
        return 'casing'
    rest = layer_id.split('-', 1)[1]
    return 'minor' if rest in MINOR_ROAD_KINDS else 'major'


def _paint_roads(layers, roads):
    fill = roads.get('fill')
    low = roads.get('minor_low_zoom', fill)
    casing = roads.get('casing')
    for layer in layers:
        kind = _road_kind(layer)
        if kind == 'casing' and casing is not None:
            layer.setdefault('paint', {})['line-color'] = casing
        elif kind == 'minor' and fill is not None:
            layer.setdefault('paint', {})['line-color'] = ['step', ['zoom'], low, 14, fill]
        elif kind == 'major' and fill is not None:
            layer.setdefault('paint', {})['line-color'] = fill


def _paint_labels(by_id, labels):
    halo = labels.get('halo')
    halo_width = labels.get('halo_width')
    for group, key in ((MAJOR_LABELS, 'major'), (MINOR_LABELS, 'minor')):
        for layer_id in group:
            layer = by_id.get(layer_id)
            if layer is None:
                continue
            paint = layer.setdefault('paint', {})
            if key in labels:
                paint['text-color'] = labels[key]
            if halo is not None:
                paint['text-halo-color'] = halo
            if halo_width is not None:
                paint['text-halo-width'] = halo_width
    for layer_id in ICONLESS_LABELS:
        layer = by_id.get(layer_id)
        if layer is not None and 'layout' in layer:
            layer['layout'].pop('icon-image', None)
    if labels.get('bold_roads') and 'road-label' in by_id:
        layout = by_id['road-label'].setdefault('layout', {})
        layout['text-font'] = [_bold(font) for font in layout.get('text-font', ['DIN Pro Regular'])]


def _bold(font):
    return re.sub(r'\b(Regular|Medium)$', 'Bold', font) if not font.endswith('Bold') else font


# ── greyscale ─────────────────────────────────────────────────────────────────

COLOR_PROPS = ('fill-color', 'line-color', 'text-color', 'background-color', 'fill-outline-color',
               'text-halo-color', 'icon-color', 'icon-halo-color', 'circle-color',
               'circle-stroke-color', 'fill-extrusion-color', 'hillshade-shadow-color',
               'hillshade-highlight-color', 'hillshade-accent-color', 'line-gradient')
_HEX = re.compile(r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$')
_FUNC = re.compile(r'^(hsla?|rgba?)\(([^)]*)\)$')


def greyscale(layers):
    """Every colour in a paint colour property becomes a grey hex, alpha blended on white."""
    out = copy.deepcopy(layers)
    for layer in out:
        paint = layer.get('paint') or {}
        for prop in COLOR_PROPS:
            if prop in paint:
                paint[prop] = _grey_value(paint[prop])
    return out


def _grey_value(value):
    if isinstance(value, str):
        rgba = parse_color(value)
        return to_grey_hex(*rgba) if rgba else value
    if isinstance(value, list):
        return [_grey_value(item) for item in value]
    if isinstance(value, dict) and 'stops' in value:  # legacy function syntax
        return dict(value, stops=[[z, _grey_value(c)] for z, c in value['stops']])
    return value


def parse_color(text):
    """(r, g, b, a) in 0..255 / 0..1 for #hex, rgb(), rgba(), hsl(), hsla(); None otherwise."""
    text = text.strip()
    match = _HEX.match(text)
    if match:
        digits = match.group(1)
        if len(digits) == 3:
            digits = ''.join(d * 2 for d in digits)
        r, g, b = (int(digits[i:i + 2], 16) for i in (0, 2, 4))
        a = int(digits[6:8], 16) / 255 if len(digits) == 8 else 1.0
        return r, g, b, a
    match = _FUNC.match(text)
    if not match:
        return None
    kind, body = match.groups()
    parts = [p.strip() for p in body.replace('/', ',').split(',') if p.strip()]
    if len(parts) not in (3, 4):
        return None
    a = _number(parts[3]) if len(parts) == 4 else 1.0
    if a is None:
        return None
    if kind.startswith('rgb'):
        rgb = [_number(p) for p in parts[:3]]
        if any(c is None for c in rgb):
            return None
        return (*[int(round(c)) for c in rgb], a)
    h, s, lum = (_number(parts[0]), _number(parts[1]), _number(parts[2]))
    if None in (h, s, lum):
        return None
    return (*_hsl_to_rgb(h, s / 100, lum / 100), a)


def _number(text):
    text = text.strip().rstrip('%')
    try:
        return float(text)
    except ValueError:
        return None


def _hsl_to_rgb(h, s, lum):
    c = (1 - abs(2 * lum - 1)) * s
    hp = (h % 360) / 60
    x = c * (1 - abs(hp % 2 - 1))
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)][int(hp) % 6]
    m = lum - c / 2
    return tuple(int(round((v + m) * 255)) for v in (r, g, b))


def to_grey_hex(r, g, b, a=1.0):
    """Luminance grey, alpha blended onto white, as #rrggbb."""
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    grey = int(round(lum * a + 255 * (1 - a)))
    grey = max(0, min(255, grey))
    return '#%02x%02x%02x' % (grey, grey, grey)


# ── Mapbox Styles API ─────────────────────────────────────────────────────────

class MapboxStylesClient:
    """The one place this script talks to Mapbox. Tests replace it with a fake of the same shape."""

    def __init__(self, token, account, api=API):
        if not token:
            raise SystemExit('MAPBOX_STYLES_TOKEN is not set (a secret token with styles:read, '
                             'styles:write, styles:list); put it in the environment or in .env')
        self.token = token
        self.account = account
        self.api = api

    def _url(self, path, **query):
        query['access_token'] = self.token
        return f'{self.api}{path}?{urllib.parse.urlencode(query)}'

    def _request(self, method, path, body=None, **query):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self._url(path, **query), data=data, method=method,
                                     headers={'Content-Type': 'application/json'} if data else {})
        try:
            with urllib.request.urlopen(req) as response:
                text = response.read().decode()
                return json.loads(text) if text else None, dict(response.headers)
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors='replace')[:500]
            raise SystemExit(f'{method} {path}: HTTP {error.code} {detail}') from None

    def get_style(self, style_id):
        """`mapbox/streets-v12` or `<account>/<id>`; the fetched style, read-only keys included."""
        style, _ = self._request('GET', f'/styles/v1/{style_id}')
        return style

    def list_styles(self):
        styles, _ = self._request('GET', f'/styles/v1/{self.account}', limit=100)
        return styles or []

    def find_by_name(self, name):
        ids = [entry['id'] for entry in self.list_styles() if entry.get('name') == name]
        if len(ids) > 1:
            raise SystemExit(f'{len(ids)} styles in {self.account} are named {name!r} ({", ".join(ids)}); '
                             'delete the extras or rename the settings before publishing')
        return ids[0] if ids else None

    def create(self, style):
        created, headers = self._request('POST', f'/styles/v1/{self.account}', body=style)
        return created, headers

    def update(self, style_id, style):
        updated, headers = self._request('PATCH', f'/styles/v1/{self.account}/{style_id}', body=style)
        return updated, headers

    def delete(self, style_id):
        self._request('DELETE', f'/styles/v1/{self.account}/{style_id}')

    def static_url(self, style_id, lng, lat, zoom, width=600, height=400, fresh=True):
        query = {'access_token': self.token}
        if fresh:
            query['fresh'] = 'true'
        return (f'{self.api}/styles/v1/{self.account}/{style_id}/static/'
                f'{lng},{lat},{zoom}/{width}x{height}@2x?{urllib.parse.urlencode(query)}')


def publish(settings, client, base=None):
    """Create or update the style named in `settings`. Returns (style_id, 'created'|'updated')."""
    name = settings.get('name')
    if not name:
        raise SystemExit('settings need a "name" to publish')
    if base is None:
        base = client.get_style(settings.get('base', DEFAULT_BASE))
    style = apply_settings(base, settings)
    existing = client.find_by_name(name)
    if existing:
        client.update(existing, style)
        return existing, 'updated'
    created, _ = client.create(style)
    return created['id'], 'created'


# ── command line ──────────────────────────────────────────────────────────────

def load_token():
    token = os.environ.get('MAPBOX_STYLES_TOKEN', '')
    if token:
        return token
    try:
        from dotenv import dotenv_values
    except ImportError:  # pragma: no cover
        return ''
    return dotenv_values(os.path.join(REPO, '.env')).get('MAPBOX_STYLES_TOKEN', '') or ''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('settings', help='settings JSON file')
    parser.add_argument('--account', default=os.environ.get('MAPBOX_ACCOUNT', 'artemkonuchov'))
    parser.add_argument('--base-file', help='use this style JSON as the base instead of fetching it')
    parser.add_argument('--dry-run', action='store_true', help='build the style, publish nothing')
    parser.add_argument('--out', help='write the built style JSON here')
    parser.add_argument('--check', default='12.57,55.68,13',
                        help='lng,lat,zoom of the Static Images check frame printed after publishing')
    args = parser.parse_args(argv)

    with open(args.settings) as handle:
        settings = json.load(handle)
    base = None
    if args.base_file:
        with open(args.base_file) as handle:
            base = json.load(handle)

    if args.dry_run:
        if base is None:
            client = MapboxStylesClient(load_token(), args.account)
            base = client.get_style(settings.get('base', DEFAULT_BASE))
        style = apply_settings(base, settings)
        _write(style, args.out)
        print(f'dry run: {len(style["layers"])} layers, nothing published')
        return 0

    client = MapboxStylesClient(load_token(), args.account)
    style_id, action = publish(settings, client, base=base)
    if args.out:
        _write(apply_settings(base or client.get_style(settings.get('base', DEFAULT_BASE)), settings), args.out)
    lng, lat, zoom = args.check.split(',')
    print(f'{action}: {args.account}/{style_id}')
    print(f'check frame: {client.static_url(style_id, lng, lat, zoom)}')
    return 0


def _write(style, path):
    if path:
        with open(path, 'w') as handle:
            json.dump(style, handle, indent=1, sort_keys=True)
    else:
        json.dump(style, sys.stdout, indent=1, sort_keys=True)
        sys.stdout.write('\n')


if __name__ == '__main__':
    sys.exit(main())
