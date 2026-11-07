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

BUILDINGS_ON = {'fill': '#ffffff', 'outline': '#a6a6a6'}
PLACE_NAMES_RANGE = (6, 16)
DEFAULT_SETTINGS = {
    'poi': False, 'paths': False, 'shields': False, 'relief': False, 'regions': False,
    'land': '#ffffff', 'park': '#dcefd2', 'water': '#cfe2f2', 'boundary': '#9a9a9a',
    'buildings': dict(BUILDINGS_ON),
    'roads': dict(ROAD_PRESETS['medium']),
    'labels': {'major': '#333333', 'minor': '#777777', 'halo': '#ffffff', 'halo_width': 1.5, 'bold_roads': False},
    'place_names_maxzoom': 10,
    'greyscale': False,
}


def road_preset_of(roads):
    """The preset name a `roads` triple matches, else 'medium'."""
    for name, triple in ROAD_PRESETS.items():
        if roads == triple:
            return name
    return 'medium'


def form_values(settings):
    """Flat values the editor renders and the browser edits, from a settings document."""
    settings = dict(DEFAULT_SETTINGS, **(settings or {}))
    labels = dict(DEFAULT_SETTINGS['labels'], **(settings.get('labels') or {}))
    return {
        **{key: settings.get(key) is not False for key, _l, _h in REMOVALS},
        'buildings': settings.get('buildings') is not False,
        'land': settings.get('land', '#ffffff'),
        'park': settings.get('park', '#dcefd2'),
        'water': settings.get('water', '#cfe2f2'),
        'boundary': settings.get('boundary', '#9a9a9a'),
        'roads': road_preset_of(settings.get('roads')),
        'labels_major': labels.get('major', '#333333'),
        'labels_minor': labels.get('minor', '#777777'),
        'bold_roads': bool(labels.get('bold_roads')),
        'place_names_maxzoom': int(settings.get('place_names_maxzoom', 10)),
        'greyscale': bool(settings.get('greyscale')),
    }


def clean_settings(raw):
    """(settings document, errors) from the editor's flat values. Unknown keys are
    ignored; a bad colour is an error; enumerations and ranges are enforced."""
    raw = raw or {}
    errors = {}
    settings = {}

    def truthy(value):
        return value in (True, 'true', 'on', '1', 1)

    for key, _label, _help in REMOVALS:
        settings[key] = truthy(raw.get(key, False))
    settings['buildings'] = dict(BUILDINGS_ON) if truthy(raw.get('buildings', True)) else False
    for role in ('land', 'park', 'water', 'boundary', 'labels_major', 'labels_minor'):
        value = str(raw.get(role, '') or '').strip().lower()
        if not HEX.match(value):
            errors[role] = str(_('Use a colour like #dcefd2.'))
            continue
        if role.startswith('labels_'):
            settings.setdefault('labels', dict(DEFAULT_SETTINGS['labels']))[role[len('labels_'):]] = value
        else:
            settings[role] = value
    settings.setdefault('labels', dict(DEFAULT_SETTINGS['labels']))['bold_roads'] = truthy(raw.get('bold_roads', False))
    preset = str(raw.get('roads', 'medium') or 'medium')
    settings['roads'] = dict(ROAD_PRESETS.get(preset, ROAD_PRESETS['medium']))
    try:
        zoom = int(raw.get('place_names_maxzoom', 10))
    except (TypeError, ValueError):
        zoom = 10
    low, high = PLACE_NAMES_RANGE
    settings['place_names_maxzoom'] = max(low, min(high, zoom))
    if truthy(raw.get('greyscale', False)):
        settings['greyscale'] = True
    # Absent means "leave the base as it is" to the generator: a removal that is kept,
    # regular street names and colour mode need no key, so Paper A's document round-trips.
    if not settings['labels'].get('bold_roads'):
        settings['labels'].pop('bold_roads', None)
    for key, _label, _help in REMOVALS:
        if settings[key] is True:
            settings.pop(key)
    return settings, errors


def controls_for_template():
    """What the template and the browser render: the control list with its labels and options."""
    return {
        'removals': [{'key': k, 'label': str(l), 'help': str(h)} for k, l, h in REMOVALS],
        'palettes': [{'key': k, 'label': str(l), 'swatches': s} for k, (l, s) in PALETTES.items()],
        'roads': [{'key': k, 'label': str(ROAD_LABELS[k]), 'triple': t} for k, t in ROAD_PRESETS.items()],
        'place_names_range': PLACE_NAMES_RANGE,
    }
