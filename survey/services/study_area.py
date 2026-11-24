"""The survey's study area: the ONE write path for `StudyArea` (change map-layers-study-area,
spec survey-study-area, #303).

The study area editor, the Map card, the ZIP import, REST v1 and the MCP server call these
functions. A study area belongs to the CANONICAL survey (`layer_owner`), like layers: the draft
copy and archived versions read it, nothing copies it, and changing it on a published survey is a
SAFE edit — it collects nothing, and answers already given are never re-checked.

Geometry is validated once here: GeoJSON in, made valid, polygons only, inside longitude/latitude,
simplified to at most `MAX_VERTICES` points so every respondent page and every section POST stays
cheap. Refusals are `ValidationFailed` on the `geometry` field.
"""
import json

from django.contrib.gis.geos import GEOSException, GEOSGeometry, MultiPolygon, Polygon
from django.db import transaction
from django.db.models import F
from django.utils.html import strip_tags

from ..audit import record as audit_record
from ..layers import layer_owner
from ..models import STUDY_AREA_SOURCE_CHOICES, StudyArea
from .errors import ValidationFailed

MAX_VERTICES = 2000
MAX_MESSAGE = 300
SOURCES = tuple(code for code, _label in STUDY_AREA_SOURCE_CHOICES)
GEOMETRY_MESSAGE = 'A study area is a polygon or a multipolygon in longitude/latitude.'


def get(survey):
    """The survey's study area, or None."""
    return StudyArea.objects.filter(survey=layer_owner(survey)).first()


def _polygons(geom):
    """The polygon parts of a geometry (a GeometryCollection from make_valid keeps its polygons)."""
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom)
    if geom.geom_type == 'GeometryCollection':
        out = []
        for part in geom:
            out += _polygons(part)
        return out
    return []


def vertex_count(geom):
    return sum(len(ring) for poly in _polygons(geom) for ring in poly)


def _simplified(multi):
    """`multi` with at most MAX_VERTICES points, simplified with a growing tolerance (degrees)."""
    if vertex_count(multi) <= MAX_VERTICES:
        return multi
    tolerance = 0.00001
    current = multi
    while vertex_count(current) > MAX_VERTICES and tolerance < 1:
        simple = multi.simplify(tolerance, preserve_topology=True)
        polys = _polygons(simple)
        if polys:
            current = MultiPolygon(*polys, srid=4326)
        tolerance *= 2
    return current


def clean_geometry(value):
    """GeoJSON (a dict or text) → a valid MultiPolygon in EPSG:4326, or ValidationFailed."""
    if isinstance(value, dict) and value.get('type') == 'Feature':
        value = value.get('geometry')
    if isinstance(value, dict) and value.get('type') == 'FeatureCollection':
        geoms = [f.get('geometry') for f in value.get('features') or [] if isinstance(f, dict)]
        value = {'type': 'GeometryCollection', 'geometries': [g for g in geoms if g]}
    if isinstance(value, dict):
        value = json.dumps(value)
    if not isinstance(value, str) or not value.strip():
        raise ValidationFailed.single('geometry', GEOMETRY_MESSAGE)
    try:
        geom = GEOSGeometry(value, srid=4326)
    except (GEOSException, ValueError, TypeError):
        raise ValidationFailed.single('geometry', GEOMETRY_MESSAGE)
    if geom.empty:
        raise ValidationFailed.single('geometry', GEOMETRY_MESSAGE)
    if not geom.valid:
        try:
            geom = geom.make_valid()
        except (GEOSException, AttributeError):
            raise ValidationFailed.single('geometry', GEOMETRY_MESSAGE)
    polys = [p for p in _polygons(geom) if not p.empty and p.area > 0]
    if not polys:
        raise ValidationFailed.single('geometry', GEOMETRY_MESSAGE)
    multi = MultiPolygon(*polys, srid=4326)
    x0, y0, x1, y1 = multi.extent
    if not (-180 <= x0 <= 180 and -180 <= x1 <= 180 and -90 <= y0 <= 90 and -90 <= y1 <= 90):
        raise ValidationFailed.single('geometry', 'The study area falls outside longitude/latitude ranges. '
                                                  'Upload it in WGS 84, or a file that names its coordinate system.')
    return _simplified(multi)


def clean_message(message):
    """{language: plain text} — creator text, tags stripped, trimmed."""
    if message is None:
        return {}
    if isinstance(message, str):
        message = {'': message}
    if not isinstance(message, dict):
        raise ValidationFailed.single('message', 'The message is text per language.')
    out = {}
    for lang, text in message.items():
        text = strip_tags(str(text or '')).strip()[:MAX_MESSAGE]
        if text:
            out[str(lang)[:10]] = text
    return out


def _message_for(owner, message):
    """A bare string message is the survey's primary language."""
    if '' in message:
        primary = (owner.available_languages or ['en'])[0]
        message = {**{k: v for k, v in message.items() if k}, primary: message['']}
    return message


def set_area(actor, survey, geometry, *, source='draw', place_name='', osm_ref='', fog=None,
             refuse_outside=None, message=None):
    """Create or replace the survey's study area. Flags and message left as None keep the current
    ones (defaults on a new area: fog on, answers outside allowed)."""
    owner = layer_owner(survey)
    multi = clean_geometry(geometry)
    if source not in SOURCES:
        raise ValidationFailed.single('source', 'Unknown study area source.')
    with transaction.atomic():
        area = StudyArea.objects.select_for_update().filter(survey=owner).first()
        if area is None:
            area = StudyArea(survey=owner)
        area.geometry = multi
        area.source = source
        area.place_name = (place_name or '')[:255]
        area.osm_ref = (osm_ref or '')[:40]
        if fog is not None:
            area.fog = bool(fog)
        if refuse_outside is not None:
            area.refuse_outside = bool(refuse_outside)
        if message is not None:
            area.message = _message_for(owner, clean_message(message))
        area.save()
    _audit(actor, 'study_area_set', owner, source=source, vertices=vertex_count(multi))
    _emit_set(actor, owner, area)
    return area


def update_settings(actor, survey, *, fog=None, refuse_outside=None, message=None):
    """Change the fog, the refusal rule or the message of the existing study area."""
    owner = layer_owner(survey)
    area = StudyArea.objects.filter(survey=owner).first()
    if area is None:
        raise ValidationFailed.single('geometry', 'Set the study area first.')
    fields = []
    if fog is not None:
        area.fog = bool(fog)
        fields.append('fog')
    if refuse_outside is not None:
        area.refuse_outside = bool(refuse_outside)
        fields.append('refuse_outside')
    if message is not None:
        area.message = _message_for(owner, clean_message(message))
        fields.append('message')
    if fields:
        area.save(update_fields=fields + ['updated_at'])
        _audit(actor, 'study_area_settings', owner, fields=fields)
        _emit_set(actor, owner, area)
    return area


def set_message_translation(survey, language, text):
    """The Translations tab's writer for `survey:study_area_message` (one language)."""
    owner = layer_owner(survey)
    area = StudyArea.objects.filter(survey=owner).first()
    if area is None:
        return None
    message = dict(area.message or {})
    text = strip_tags(str(text or '')).strip()[:MAX_MESSAGE]
    if text:
        message[language] = text
    else:
        message.pop(language, None)
    area.message = message
    area.save(update_fields=['message', 'updated_at'])
    return area


def clear(actor, survey):
    """Remove the study area. Returns whether there was one."""
    owner = layer_owner(survey)
    deleted, _ = StudyArea.objects.filter(survey=owner).delete()
    if deleted:
        _audit(actor, 'study_area_clear', owner)
    return bool(deleted)


def count_refused(survey, n):
    """Add `n` refused marks to the counter (the section POST)."""
    if n:
        StudyArea.objects.filter(survey=layer_owner(survey)).update(refused_marks=F('refused_marks') + n)


def area_km2(area):
    """The area's size in km², on the spheroid."""
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute('SELECT ST_Area(%s::geography) / 1000000.0', [area.geometry.ewkt])
        row = cursor.fetchone()
    return round(row[0] or 0, 2)


def message_for(area, language, fallback_languages=()):
    """The refusal message in `language`, else the first language that has one, else ''."""
    message = (area.message or {}) if area else {}
    for lang in (language, *fallback_languages):
        if lang and message.get(lang):
            return message[lang]
    return next(iter(message.values()), '')


def describe(area):
    """Plain data for the editor, the publish check, REST and MCP."""
    if area is None:
        return None
    return {
        'geometry': json.loads(area.geometry.geojson),
        'source': area.source,
        'place_name': area.place_name,
        'osm_ref': area.osm_ref,
        'fog': area.fog,
        'refuse_outside': area.refuse_outside,
        'message': dict(area.message or {}),
        'refused_marks': area.refused_marks,
        'area_km2': area_km2(area),
        'vertices': vertex_count(area.geometry),
        'bounds': list(area.geometry.extent),
    }


def _audit(actor, action, owner, **meta):
    if actor is not None:
        audit_record(actor, action, owner, **meta)


def _emit_set(actor, owner, area):
    if actor is None:
        return
    from ..product_events import STUDY_AREA_SET, emit
    emit(STUDY_AREA_SET, actor.user_id, {'survey_id': owner.pk, 'source': area.source, 'fog': area.fog,
                                         'refuse_outside': area.refuse_outside, 'surface': actor.surface})
