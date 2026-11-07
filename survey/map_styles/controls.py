"""The guided controls of the style editor (change map-styles-editor, #543; vision FE-3).

One schema the template, the browser and the save view share: `CONTROLS` lists every
control a creator gets — a removal toggle, a colour role with six swatches and a hex
field, a road preset, the place-name zoom limit, greyscale — and `clean_settings` turns
a posted document into the generator's settings (`survey/map_styles/generator.py`),
dropping what the schema does not know. Nothing here lets a creator name a layer, a
font or a sprite: the vision's bounded editor, not Mapbox Studio.
"""
import re
from django.utils.translation import gettext_lazy as _

HEX = re.compile(r'^#[0-9a-fA-F]{6}$')

# key, label, help — a `False` value removes the generator's layer group.
REMOVALS = (
    ('poi', _('Place icons and names'), _('Shops, stations, parks by name — the clutter a paper map does without.')),
    ('paths', _('Footpaths and steps'), _('Pedestrian ways, stairs, crossings and park paths.')),
    ('shields', _('Route shields and arrows'), _('Road numbers, one-way arrows, junction marks.')),
    ('relief', _('Relief and ferries'), _('Hillshade, sea depth, ferry and cable-car lines.')),
    ('regions', _('Regional boundaries'), _('States, provinces, Länder. National borders always show.')),
)

# role → (label, swatches); the first swatch is the preset's default.
PALETTES = {
    'land': (_('Land'), ['#ffffff', '#faf8f4', '#f4f4f2', '#eeeeee', '#e6e6e6', '#dcdcdc']),
    'park': (_('Parks and green'), ['#dcefd2', '#cfe6b8', '#e5f1dc', '#c8dfb8', '#e9e9e9', '#f1f1f1']),
    'water': (_('Water'), ['#cfe2f2', '#2f8f86', '#9fc6e3', '#bfdff0', '#d6d6d6', '#eaeaea']),
    'boundary': (_('National borders'), ['#9a9a9a', '#6e6e6e', '#4a4a4a', '#b5b5b5', '#8a6d8f', '#c48a8a']),
    'labels_major': (_('Street and city names'), ['#333333', '#111111', '#555555', '#2b3a55', '#000000', '#444444']),
    'labels_minor': (_('Water and district names'), ['#777777', '#555555', '#999999', '#5b6b8a', '#666666', '#8a8a8a']),
}

# Road look presets → the generator's `roads` triple.
ROAD_PRESETS = {
    'light': {'fill': '#ffffff', 'minor_low_zoom': '#e8e8e8', 'casing': '#c8c8c8'},
    'medium': {'fill': '#ffffff', 'minor_low_zoom': '#bdbdbd', 'casing': '#8f8f8f'},   # Paper A
    'strong': {'fill': '#ffffff', 'minor_low_zoom': '#ffffff', 'casing': '#3a3a3a'},    # Paper B-like
}
ROAD_LABELS = {'light': _('Light'), 'medium': _('Medium'), 'strong': _('Strong')}

# Every control has a "leave the base as it is" state (change map-styles-editor-fidelity):
# a colour left empty, roads "as base", place names "no limit", buildings at the base's zoom.
# The editor shows a style exactly as its settings document says — Streets' document is
# empty, so a Streets copy shows Streets — and saving an untouched style changes nothing.
ROAD_BASE = 'base'
ROAD_CUSTOM = 'custom'   # a triple no preset matches (Paper B, an import): kept as it is
ROAD_BASE_SAMPLE = {'fill': '#ffffff', 'casing': '#cfd3dc'}   # what the "as base" swatch draws
PLACE_NAMES_RANGE = (6, 17)
PLACE_NAMES_NO_LIMIT = 17
BUILDINGS_ZOOM_RANGE = (13, 17)
BUILDINGS_BASE_ZOOM = 15   # streets-v12 draws buildings from zoom 15
LABEL_HALO = {'halo': '#ffffff', 'halo_width': 1.5}
COLOUR_ROLES = ('land', 'park', 'water', 'boundary', 'labels_major', 'labels_minor')


# Where each colour role reads its base colour: the first layer the generator paints for it
# that the base has, and the class to pick inside a `match` (owner, 2026-11-07: show the
# colour the base really uses, never an abstract "As base").
BASE_COLOUR_SOURCES = {
    'land': (('land', 'background-color', None),),
    'park': (('landuse', 'fill-color', 'park'), ('landcover', 'fill-color', 'grass'),
             ('national-park', 'fill-color', None)),
    'water': (('water', 'fill-color', None),),
    'boundary': (('admin-0-boundary', 'line-color', None),),
    'labels_major': (('settlement-major-label', 'text-color', None), ('road-label', 'text-color', None)),
    'labels_minor': (('settlement-subdivision-label', 'text-color', None), ('water-point-label', 'text-color', None)),
}


def _sample(expr, cls):
    """One colour string out of a paint value: a literal; the last (street-zoom) stop of an
    `interpolate`/`step`; the `cls` arm of a `match`, else its default. None otherwise."""
    if isinstance(expr, str):
        return expr
    if not isinstance(expr, list) or not expr:
        return None
    op = expr[0]
    if op == 'interpolate' and len(expr) >= 5:
        return _sample(expr[-1], cls)
    if op == 'step' and len(expr) >= 3:
        return _sample(expr[-1], cls)
    if op == 'match' and len(expr) >= 4:
        arms = expr[2:-1]
        for label, value in zip(arms[::2], arms[1::2]):
            labels = label if isinstance(label, list) else [label]
            if cls is not None and cls in labels:
                return _sample(value, cls)
        return _sample(expr[-1], cls)
    return None


def base_colours(base_style):
    """role → '#rrggbb' the base style draws it with (alpha blended onto white); roles the
    base does not answer are left out."""
    from survey.map_styles.generator import parse_color
    layers = {layer.get('id'): layer for layer in (base_style or {}).get('layers', [])}
    out = {}
    for role, sources in BASE_COLOUR_SOURCES.items():
        for layer_id, prop, cls in sources:
            value = _sample((layers.get(layer_id) or {}).get('paint', {}).get(prop), cls)
            rgba = parse_color(value) if isinstance(value, str) else None
            if rgba:
                r, g, b, a = rgba
                out[role] = '#%02x%02x%02x' % tuple(int(round(c * a + 255 * (1 - a))) for c in (r, g, b))
                break
    return out


def road_preset_of(roads):
    """The preset a `roads` triple matches; no triple = the base's roads, any other = custom."""
    if not roads:
        return ROAD_BASE
    for name, triple in ROAD_PRESETS.items():
        if roads == triple:
            return name
    return ROAD_CUSTOM


def form_values(settings):
    """Flat values the editor renders and the browser edits — exactly what `settings` says,
    with '' / "base" / "no limit" where it leaves the base alone."""
    settings = settings or {}
    labels = settings.get('labels') or {}
    buildings = settings.get('buildings')
    buildings = buildings if isinstance(buildings, dict) else {}
    return {
        **{key: settings.get(key) is not False for key, _l, _h in REMOVALS},
        'buildings': settings.get('buildings') is not False,
        'buildings_minzoom': int(buildings.get('minzoom', BUILDINGS_BASE_ZOOM)),
        'buildings_fill': buildings.get('fill', ''),
        'buildings_outline': buildings.get('outline', ''),
        'land': settings.get('land', ''),
        'park': settings.get('park', ''),
        'water': settings.get('water', ''),
        'boundary': settings.get('boundary', ''),
        'roads': road_preset_of(settings.get('roads')),
        'roads_custom': settings.get('roads') if road_preset_of(settings.get('roads')) == ROAD_CUSTOM else {},
        'labels_major': labels.get('major', ''),
        'labels_minor': labels.get('minor', ''),
        'bold_roads': bool(labels.get('bold_roads')),
        'place_names_maxzoom': int(settings.get('place_names_maxzoom', PLACE_NAMES_NO_LIMIT)),
        'greyscale': bool(settings.get('greyscale')),
    }


def clean_settings(raw):
    """(settings document, errors) from the editor's flat values. Unknown keys are
    ignored; a bad colour is an error; enumerations and ranges are enforced; a control
    left in its base state adds no key, so the generator leaves the base as it is."""
    raw = raw or {}
    errors = {}
    settings = {}

    def truthy(value):
        return value in (True, 'true', 'on', '1', 1)

    def colour(key):
        value = str(raw.get(key, '') or '').strip().lower()
        if not value:
            return ''
        if not HEX.match(value):
            errors[key] = str(_('Use a colour like #dcefd2.'))
            return ''
        return value

    for key, _label, _help in REMOVALS:
        if not truthy(raw.get(key, True)):
            settings[key] = False

    if not truthy(raw.get('buildings', True)):
        settings['buildings'] = False
    else:
        buildings = {}
        for part in ('fill', 'outline'):
            value = colour(f'buildings_{part}')
            if value:
                buildings[part] = value
        try:
            minzoom = int(raw.get('buildings_minzoom', BUILDINGS_BASE_ZOOM))
        except (TypeError, ValueError):
            minzoom = BUILDINGS_BASE_ZOOM
        low, high = BUILDINGS_ZOOM_RANGE
        minzoom = max(low, min(high, minzoom))
        if minzoom != BUILDINGS_BASE_ZOOM:
            buildings['minzoom'] = minzoom
        if buildings:
            settings['buildings'] = buildings

    for role in ('land', 'park', 'water', 'boundary'):
        value = colour(role)
        if value:
            settings[role] = value

    labels = {}
    for role in ('labels_major', 'labels_minor'):
        value = colour(role)
        if value:
            labels[role[len('labels_'):]] = value
    if labels:
        labels.update(LABEL_HALO)
    if truthy(raw.get('bold_roads', False)):
        labels['bold_roads'] = True
    if labels:
        settings['labels'] = labels

    preset = str(raw.get('roads', ROAD_BASE) or ROAD_BASE)
    if preset in ROAD_PRESETS:
        settings['roads'] = dict(ROAD_PRESETS[preset])
    elif preset == ROAD_CUSTOM:
        custom = raw.get('roads_custom') if isinstance(raw.get('roads_custom'), dict) else {}
        triple = {k: str(custom.get(k, '')).lower() for k in ('fill', 'minor_low_zoom', 'casing')}
        if all(HEX.match(v) for v in triple.values()):
            settings['roads'] = triple

    try:
        zoom = int(raw.get('place_names_maxzoom', PLACE_NAMES_NO_LIMIT))
    except (TypeError, ValueError):
        zoom = PLACE_NAMES_NO_LIMIT
    low, high = PLACE_NAMES_RANGE
    zoom = max(low, min(high, zoom))
    if zoom != PLACE_NAMES_NO_LIMIT:
        settings['place_names_maxzoom'] = zoom

    if truthy(raw.get('greyscale', False)):
        settings['greyscale'] = True
    return settings, errors


def controls_for_template():
    """What the template and the browser render: the control list with its labels and options."""
    roads = [{'key': ROAD_BASE, 'label': str(_('As base')), 'triple': ROAD_BASE_SAMPLE}]
    roads += [{'key': k, 'label': str(ROAD_LABELS[k]), 'triple': t} for k, t in ROAD_PRESETS.items()]
    return {
        'removals': [{'key': k, 'label': str(l), 'help': str(h)} for k, l, h in REMOVALS],
        'palettes': [{'key': k, 'label': str(l), 'swatches': s} for k, (l, s) in PALETTES.items()],
        'roads': roads,
        'place_names_range': PLACE_NAMES_RANGE,
        'place_names_no_limit': PLACE_NAMES_NO_LIMIT,
        'buildings_zoom_range': BUILDINGS_ZOOM_RANGE,
    }
