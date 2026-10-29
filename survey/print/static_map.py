"""The section map as an image (spec printable-form, design D3/D4).

Basemap from the Mapbox Static Images API behind the existing token, the
survey's reference layers drawn on top with Pillow, a scale bar; no headless
browser, no tile stitching. Everything degrades: no token, a Mapbox error or a
timeout prints an empty frame with a grid and the layers alone, and the view
still answers the PDF.

Zoom: the respondent map is Leaflet over 256-px tiles; the Static Images API
works in 512-px style zoom, one level lower for the same scale. `FrameSpec.zoom`
is the respondent's (Leaflet) zoom; `style_zoom` converts.
"""
import hashlib
import json
import logging
import math
from dataclasses import dataclass, field

import requests
from django.conf import settings
from django.core.cache import cache
from PIL import Image, ImageDraw, ImageFont

from survey.layers import GEOMETRY_TEXT_FIELDS, layer_owner, match_class, normalize_style

log = logging.getLogger(__name__)

# Logical size of a frame in @1x pixels (the API caps at 1280×1280); the PDF
# scales the @2x image into its millimetre frame.
FRAME_W, FRAME_H = 900, 550
SCALE = 2
STATIC_TIMEOUT = 5
CACHE_TTL = 24 * 3600
MAX_FEATURES = 20_000
WORLD_ZOOM = 1

BASEMAP_STYLES = {
    'streets': 'mapbox/streets-v12',
    'topo': 'mapbox/outdoors-v12',
    # The respondent's satellite is Esri imagery, which has no static endpoint;
    # satellite-streets is the nearest look and carries street names, which
    # paper needs more than a screen does.
    'satellite': 'mapbox/satellite-streets-v12',
}
ATTRIBUTION = '© Mapbox © OpenStreetMap'


@dataclass
class FrameSpec:
    lat: float
    lng: float
    zoom: int                 # Leaflet zoom (256-px tiles)
    basemap: str | None       # key of BASEMAP_STYLES, or None when no basemap can be fetched
    section_code: str = ''
    width: int = FRAME_W
    height: int = FRAME_H
    note: str = ''            # why the position is a fallback, for the legend

    @property
    def style_zoom(self):
        return max(0, self.zoom - 1)

    @property
    def bounds(self):
        return bounds_of(self.lat, self.lng, self.zoom, self.width, self.height)


@dataclass
class FrameImage:
    image: Image.Image
    spec: FrameSpec
    basemap_ok: bool
    drawn_features: int = 0
    truncated_layers: list = field(default_factory=list)


# ── geometry ───────────────────────────────────────────────────────────────

def _world_size(zoom):
    return 256 * (2 ** zoom)


def project(lng, lat, zoom):
    """WGS84 → world pixel (x, y) at a Leaflet zoom."""
    size = _world_size(zoom)
    lat = max(-85.05112878, min(85.05112878, lat))
    x = (lng + 180.0) / 360.0 * size
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * size
    return x, y


def unproject(x, y, zoom):
    size = _world_size(zoom)
    lng = x / size * 360.0 - 180.0
    n = math.pi - 2.0 * math.pi * y / size
    lat = math.degrees(math.atan(math.sinh(n)))
    return lng, lat


def bounds_of(lat, lng, zoom, width=FRAME_W, height=FRAME_H):
    """[w, s, e, n] shown by a frame of `width`×`height` logical pixels."""
    cx, cy = project(lng, lat, zoom)
    w, n = unproject(cx - width / 2, cy - height / 2, zoom)
    e, s = unproject(cx + width / 2, cy + height / 2, zoom)
    return [round(w, 6), round(s, 6), round(e, 6), round(n, 6)]


def metres_per_pixel(lat, zoom):
    return 156543.03392 * math.cos(math.radians(lat)) / (2 ** zoom)


SCALE_STEPS = (10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000)


def scale_bar(lat, zoom, max_px=180):
    """(length_px, label) of the longest round-number scale bar that fits in `max_px`."""
    mpp = metres_per_pixel(lat, zoom)
    px, metres = max_px, max_px * mpp
    for step in SCALE_STEPS:
        if step / mpp > max_px:
            break
        px, metres = step / mpp, step
    label = f'{metres / 1000:g} km' if metres >= 1000 else f'{metres:g} m'
    return int(px), label


# ── where the frame is ─────────────────────────────────────────────────────

def _layer_bounds(survey):
    """Union bbox of the survey's reference layers, or None. Reads the geometry
    text — only on the fallback path, when neither the section nor the survey
    has a start position."""
    from survey.layers import bbox_of_collection, layers_for
    boxes = []
    for layer in layers_for(survey).defer(None):
        box = bbox_of_collection(layer.geojson or '')
        if box and len(box) == 4:
            boxes.append(box)
    if not boxes:
        return None
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


def _zoom_for_bounds(bbox, width=FRAME_W, height=FRAME_H):
    w, s, e, n = bbox
    for zoom in range(18, 0, -1):
        x0, y0 = project(w, n, zoom)
        x1, y1 = project(e, s, zoom)
        if (x1 - x0) <= width * 0.9 and (y1 - y0) <= height * 0.9:
            return zoom
    return WORLD_ZOOM


def _basemap_key(section, survey):
    name = section.override_basemap or survey.default_basemap
    if not name:
        enabled = survey.basemaps or []
        name = enabled[0] if enabled else 'streets'
    return name if name in BASEMAP_STYLES else 'streets'


def resolve_frame(section, survey):
    """Centre, zoom and basemap of a section's printed map: the section's start
    position, else the survey's, else the bounds of the reference layers, else
    the world (with a note for the legend)."""
    basemap = _basemap_key(section, survey)
    code = section.code or ''
    if section.start_map_postion:
        zoom = section.start_map_zoom if section.start_map_zoom is not None else (
            survey.start_map_zoom if survey.start_map_zoom is not None else 12)
        return FrameSpec(section.start_map_postion.y, section.start_map_postion.x, int(zoom), basemap, code)
    if survey.start_map_postion:
        zoom = survey.start_map_zoom if survey.start_map_zoom is not None else 12
        return FrameSpec(survey.start_map_postion.y, survey.start_map_postion.x, int(zoom), basemap, code)
    bbox = _layer_bounds(survey)
    if bbox:
        lat = (bbox[1] + bbox[3]) / 2
        lng = (bbox[0] + bbox[2]) / 2
        return FrameSpec(lat, lng, _zoom_for_bounds(bbox), basemap, code, note='layers')
    return FrameSpec(0.0, 0.0, WORLD_ZOOM, basemap, code, note='world')


# ── basemap ────────────────────────────────────────────────────────────────

def basemap_style(name):
    return BASEMAP_STYLES.get(name, BASEMAP_STYLES['streets'])


def _cache_key(style, lat, lng, zoom, width, height):
    raw = f'{style}|{lat:.6f}|{lng:.6f}|{zoom}|{width}x{height}@{SCALE}'
    return 'print:basemap:' + hashlib.sha1(raw.encode()).hexdigest()


def fetch_basemap(spec):
    """The basemap PNG as a Pillow image, or None on any failure (no token,
    HTTP error, timeout, unreadable body). Successes are cached for a day."""
    token = getattr(settings, 'MAPBOX_ACCESS_TOKEN', '') or ''
    if not token or spec.basemap is None:
        return None
    style = basemap_style(spec.basemap)
    key = _cache_key(style, spec.lat, spec.lng, spec.style_zoom, spec.width, spec.height)
    cached = cache.get(key)
    if cached is None:
        url = (f'https://api.mapbox.com/styles/v1/{style}/static/'
               f'{spec.lng:.6f},{spec.lat:.6f},{spec.style_zoom}/{spec.width}x{spec.height}@{SCALE}x')
        try:
            response = requests.get(url, params={'access_token': token, 'attribution': 'false', 'logo': 'false'},
                                    timeout=STATIC_TIMEOUT)
            if response.status_code != 200 or not response.content:
                log.warning('print: static map %s for %s', response.status_code, style)
                return None
            cached = response.content
        except requests.RequestException as exc:
            log.warning('print: static map failed: %s', exc)
            return None
        cache.set(key, cached, CACHE_TTL)
    try:
        import io
        return Image.open(io.BytesIO(cached)).convert('RGB')
    except Exception:  # noqa: BLE001 — a corrupt body is a missing basemap, not a 500
        log.warning('print: static map body unreadable')
        return None


# ── layers ─────────────────────────────────────────────────────────────────

def _hex(color, alpha=255):
    color = (color or '#2c7be5').lstrip('#')
    if len(color) == 3:
        color = ''.join(c * 2 for c in color)
    try:
        r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    except ValueError:
        r, g, b = 44, 123, 229
    return (r, g, b, alpha)


def _feature_style(props, style, base_color):
    """Colour, weight, radius, opacities for one feature: rule class → simplestyle
    in the file → base (mirrors styleFor() in ref_layer_factory.html)."""
    rule = style.get('by')
    color, weight, radius = base_color, style['weight'], style['radius']
    opacity, fill_opacity = style['opacity'], style['fill_opacity']
    if rule:
        cls = match_class(rule, props.get(rule['field']))
        src = cls or rule['other']
        color, weight, radius = src['color'], src['weight'], src['radius']
        if cls is None:
            opacity = rule['other']['opacity']
    else:
        color = props.get('marker-color') or props.get('stroke') or props.get('fill') or base_color
    return color, weight, radius, opacity, fill_opacity


def _rings(geometry):
    """(kind, [rings or paths or points]) for one GeoJSON geometry, Multi* flattened."""
    t = geometry.get('type')
    c = geometry.get('coordinates')
    if t == 'Point':
        return 'point', [c]
    if t == 'MultiPoint':
        return 'point', list(c)
    if t == 'LineString':
        return 'line', [c]
    if t == 'MultiLineString':
        return 'line', list(c)
    if t == 'Polygon':
        return 'polygon', [c]
    if t == 'MultiPolygon':
        return 'polygon', list(c)
    return None, []


def _font(size):
    try:
        from survey.print import FONT_DIR
        import os
        return ImageFont.truetype(os.path.join(FONT_DIR, 'DejaVuSans.ttf'), size)
    except Exception:  # noqa: BLE001
        return ImageFont.load_default()


def draw_layers(image, survey, spec):
    """Draw the survey's reference layers onto `image` (an @2x frame). Returns
    (features drawn, [layer names cut at MAX_FEATURES]). Reads the geometry
    text once per layer and keeps nothing on the instance (layer memory rules)."""
    from survey.layers import layers_for
    width, height = image.size
    cx, cy = project(spec.lng, spec.lat, spec.zoom)
    ox = cx - spec.width / 2
    oy = cy - spec.height / 2
    overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _font(11 * SCALE)
    drawn, truncated = 0, []

    def to_px(lng, lat):
        x, y = project(lng, lat, spec.zoom)
        return ((x - ox) * SCALE, (y - oy) * SCALE)

    def visible(points):
        return any(-50 <= x <= width + 50 and -50 <= y <= height + 50 for x, y in points)

    for layer in layers_for(survey).defer(None).order_by('position', 'id'):
        try:
            collection = json.loads(layer.geojson or '{}')
        except (TypeError, ValueError):
            continue
        features = collection.get('features') or []
        if len(features) > MAX_FEATURES:
            truncated.append(layer.name)
            features = features[:MAX_FEATURES]
        style = normalize_style(layer.style, layer.color)
        labels = []
        for feature in features:
            geometry = feature.get('geometry') or {}
            props = feature.get('properties') or {}
            kind, parts = _rings(geometry)
            if kind is None:
                continue
            color, weight, radius, opacity, fill_opacity = _feature_style(props, style, layer.color)
            stroke = _hex(color, int(255 * opacity))
            fill = _hex(color, int(255 * fill_opacity))
            w = max(1, int(weight * SCALE))
            anchor = None
            if kind == 'point':
                for lng, lat in parts:
                    x, y = to_px(lng, lat)
                    if not visible([(x, y)]):
                        continue
                    r = radius * SCALE
                    draw.ellipse([x - r, y - r, x + r, y + r], fill=_hex(color, 230), outline=(255, 255, 255, 255), width=SCALE)
                    anchor = (x + r + 2, y - r)
                    drawn += 1
            elif kind == 'line':
                for path in parts:
                    pts = [to_px(p[0], p[1]) for p in path if len(p) >= 2]
                    if len(pts) < 2 or not visible(pts):
                        continue
                    draw.line(pts, fill=stroke, width=w, joint='curve')
                    anchor = pts[len(pts) // 2]
                    drawn += 1
            else:
                for polygon in parts:
                    if not polygon:
                        continue
                    outer = [to_px(p[0], p[1]) for p in polygon[0] if len(p) >= 2]
                    if len(outer) < 3 or not visible(outer):
                        continue
                    draw.polygon(outer, fill=fill)
                    for hole in polygon[1:]:
                        pts = [to_px(p[0], p[1]) for p in hole if len(p) >= 2]
                        if len(pts) >= 3:
                            draw.polygon(pts, fill=(0, 0, 0, 0))
                    draw.line(outer + [outer[0]], fill=stroke, width=w, joint='curve')
                    anchor = (sum(p[0] for p in outer) / len(outer), sum(p[1] for p in outer) / len(outer))
                    drawn += 1
            label = props.get(layer.label_field) if layer.label_field else None
            if anchor is not None and label not in (None, ''):
                labels.append((anchor, str(label)[:40]))
        for (x, y), text in labels:
            box = draw.textbbox((x, y), text, font=font)
            draw.rectangle([box[0] - 2, box[1] - 1, box[2] + 2, box[3] + 1], fill=(255, 255, 255, 200))
            draw.text((x, y), text, fill=(20, 20, 20, 255), font=font)
    image.paste(Image.alpha_composite(image.convert('RGBA'), overlay).convert('RGB'))
    return drawn, truncated


def draw_grid(image, step_px=None):
    """A light grid on an empty frame, for the respondent to place a mark by eye."""
    draw = ImageDraw.Draw(image)
    step = step_px or int(10 / 25.4 * 150 * SCALE / 2)   # ≈ 10 mm at the print size
    w, h = image.size
    for x in range(0, w, step):
        draw.line([(x, 0), (x, h)], fill=(215, 215, 215), width=1)
    for y in range(0, h, step):
        draw.line([(0, y), (w, y)], fill=(215, 215, 215), width=1)


def draw_scale_bar(image, spec):
    px, label = scale_bar(spec.lat, spec.zoom, max_px=spec.width // 5)
    px *= SCALE
    draw = ImageDraw.Draw(image)
    w, h = image.size
    x0, y0 = 16 * SCALE, h - 16 * SCALE
    draw.rectangle([x0 - 6, y0 - 14 * SCALE, x0 + px + 6, y0 + 6], fill=(255, 255, 255))
    draw.line([(x0, y0), (x0 + px, y0)], fill=(0, 0, 0), width=2 * SCALE)
    draw.line([(x0, y0 - 5 * SCALE), (x0, y0)], fill=(0, 0, 0), width=2 * SCALE)
    draw.line([(x0 + px, y0 - 5 * SCALE), (x0 + px, y0)], fill=(0, 0, 0), width=2 * SCALE)
    draw.text((x0 + 4, y0 - 13 * SCALE), label, fill=(0, 0, 0), font=_font(9 * SCALE))


def render_frame(section, survey, unavailable_text='Map unavailable — attach a printed map here'):
    """The frame image of a section: basemap (or the grid) + layers + scale bar."""
    spec = resolve_frame(section, survey)
    base = fetch_basemap(spec)
    ok = base is not None
    if base is None or base.size != (spec.width * SCALE, spec.height * SCALE):
        if base is not None:
            base = base.resize((spec.width * SCALE, spec.height * SCALE))
        else:
            base = Image.new('RGB', (spec.width * SCALE, spec.height * SCALE), (255, 255, 255))
            draw_grid(base)
    drawn, truncated = (0, [])
    if spec.note != 'world':
        try:
            drawn, truncated = draw_layers(base, survey, spec)
        except Exception:  # noqa: BLE001 — a bad layer must not cost the form
            log.exception('print: drawing layers failed for survey %s', survey.pk)
    if not ok:
        draw = ImageDraw.Draw(base)
        font = _font(14 * SCALE)
        box = draw.textbbox((0, 0), unavailable_text, font=font)
        tw, th = box[2] - box[0], box[3] - box[1]
        x = (base.width - tw) // 2
        y = (base.height - th) // 2
        draw.rectangle([x - 12, y - 8, x + tw + 12, y + th + 8], fill=(255, 255, 255), outline=(120, 120, 120))
        draw.text((x, y), unavailable_text, fill=(60, 60, 60), font=font)
    if spec.note != 'world':
        draw_scale_bar(base, spec)
    return FrameImage(base, spec, ok, drawn, truncated)
