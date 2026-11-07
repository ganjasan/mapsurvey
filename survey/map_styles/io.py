"""A map style as a portable file (change map-styles-import-export, #544; vision FE-6).

The document is the generator's settings with a name and a base, nothing more: no Mapbox
id, no uuid, no workspace, so the same file means the same thing in any library and, later,
in the shared catalogue or an API payload. Import normalises the settings through the
editor's control schema (`controls.clean_settings(controls.form_values(...))`), so a file
can never widen what the editor allows — a hand-added `layers` key is dropped, a bad colour
is an error the page names.
"""
import json
from datetime import timezone as dt_timezone

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from ..models import MAP_STYLE_BASE_STREETS, MapStyle
from . import controls

FORMAT = 'mapsurvey-map-style'
VERSION = 1
MAX_BYTES = 64 * 1024
SUPPORTED_BASES = (MAP_STYLE_BASE_STREETS,)
NAME_MAX = 120


def export_document(style, version=None):
    """The file for `style` (its latest ready version unless `version` is given)."""
    version = version or style.latest_ready() or style.latest()
    doc = {
        'format': FORMAT,
        'version': VERSION,
        'name': style.name,
        'base': style.base or MAP_STYLE_BASE_STREETS,
        'settings': dict(version.settings) if version else {},
        'exported_at': timezone.now().astimezone(dt_timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }
    if style.is_preset:
        doc['preset'] = style.key
    doc['settings'].pop('name', None)
    doc['settings'].pop('base', None)
    return doc


def export_bytes(style, version=None):
    return (json.dumps(export_document(style, version), indent=2, sort_keys=True, ensure_ascii=False) + '\n').encode('utf-8')


def parse_document(data):
    """(name, base, settings, errors) from the bytes of an uploaded file. `errors` is a list
    of messages; when it is non-empty the other values are None."""
    errors = []
    if data is None or len(data) == 0:
        return None, None, None, [str(_('Choose a file.'))]
    if len(data) > MAX_BYTES:
        return None, None, None, [str(_('The file is larger than a map style can be (64 KB).'))]
    try:
        doc = json.loads(data.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        return None, None, None, [str(_('This file is not a Mapsurvey map style.'))]
    if not isinstance(doc, dict) or doc.get('format') != FORMAT:
        return None, None, None, [str(_('This file is not a Mapsurvey map style.'))]
    try:
        version = int(doc.get('version', 0))
    except (TypeError, ValueError):
        version = 0
    if version < 1:
        return None, None, None, [str(_('This file is not a Mapsurvey map style.'))]
    if version > VERSION:
        return None, None, None, [str(_('This map style needs a newer Mapsurvey.'))]
    name = str(doc.get('name') or '').strip()[:NAME_MAX]
    if not name:
        errors.append(str(_('The map style has no name.')))
    base = str(doc.get('base') or MAP_STYLE_BASE_STREETS)
    if base not in SUPPORTED_BASES:
        errors.append(str(_('Base map "%(base)s" is not supported here.') % {'base': base}))
    raw_settings = doc.get('settings')
    if not isinstance(raw_settings, dict):
        errors.append(str(_('The map style has no settings.')))
        raw_settings = {}
    settings, field_errors = controls.clean_settings(controls.form_values(raw_settings))
    for field, message in field_errors.items():
        errors.append(f'{field}: {message}')
    if errors:
        return None, None, None, errors
    return name, base, settings, []


def unique_name(org, name):
    """`name`, else `name (2)`, `name (3)`… against the workspace's live styles."""
    taken = set(MapStyle.objects.filter(organization=org, archived_at__isnull=True).values_list('name', flat=True))
    if name not in taken:
        return name
    n = 2
    while True:
        suffix = f' ({n})'
        candidate = name[:NAME_MAX - len(suffix)] + suffix
        if candidate not in taken:
            return candidate
        n += 1
