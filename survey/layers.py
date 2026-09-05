"""Reference overlay layers: validation, objects and the derived GeoJSON.

`validate_layer_upload` is the one gate every GeoJSON passes on the way in —
editor import, ZIP import, AI-written — so a file is always a re-serialized
parse, never raw bytes. Since `overlay-features` a layer is a container of
LayerObject rows: `objects_from_features` turns validated features into rows,
`rebuild_layer` derives the FeatureCollection the respondent map loads, and
`layers_for` resolves which survey owns the layers a page should show.
"""
import json
import re

from django.utils.text import slugify

MAX_LAYER_BYTES = 10 * 1024 * 1024
MAX_LAYER_FEATURES = 5000
MAX_LAYERS_PER_SURVEY = 10

# Properties the derived GeoJSON reserves for the list block and the popup.
# Prefixed so a GIS file's own `title` or `key` column is never clobbered.
RESERVED_PROPS = ('_key', '_title', '_category', '_has_content', '_cover')

_SINGLE_TYPES = ('Point', 'LineString', 'Polygon')
_MULTI_TYPES = {'MultiPoint': 'Point', 'MultiLineString': 'LineString', 'MultiPolygon': 'Polygon'}


def layer_owner(survey):
    """The SurveyHeader whose `map_layers` a page for `survey` should show.

    Layers are owned by the canonical survey and BORROWED by draft copies
    (`published_version` → canonical) and archived versions (`canonical_survey`
    → canonical). Copying hundreds of objects and their S3 assets into every
    draft, then merging them back on publish, is a feature with no merge
    semantics — so nothing copies, and an object edit is live everywhere."""
    return survey.canonical_survey or survey.published_version or survey


def layers_for(survey):
    """QuerySet of the layers a survey (or any of its versions) renders."""
    return layer_owner(survey).map_layers.all()


class LayerValidationError(Exception):
    """Human-readable rejection reason, safe to show in the editor."""


def _iter_coords(coords):
    """Yield (lng, lat) pairs from arbitrarily nested GeoJSON coordinates."""
    if not isinstance(coords, (list, tuple)) or not coords:
        return
    if isinstance(coords[0], (int, float)):
        if len(coords) >= 2:
            yield coords[0], coords[1]
        return
    for part in coords:
        yield from _iter_coords(part)


def _geometry_coords(geometry):
    if not isinstance(geometry, dict):
        return
    if geometry.get('type') == 'GeometryCollection':
        for g in geometry.get('geometries') or []:
            yield from _geometry_coords(g)
        return
    yield from _iter_coords(geometry.get('coordinates'))


def validate_layer_upload(data):
    """Validate raw uploaded bytes; return (geojson_str, feature_count, property_names).

    Raises LayerValidationError with a creator-facing message.
    """
    if len(data) > MAX_LAYER_BYTES:
        raise LayerValidationError(
            f"File is larger than {MAX_LAYER_BYTES // (1024 * 1024)} MB. "
            "Simplify the geometry (e.g. in QGIS or mapshaper.org) and try again.")
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise LayerValidationError("File is not UTF-8 text — expected a .geojson file.")
    try:
        parsed = json.loads(text)
    except ValueError:
        raise LayerValidationError("File is not valid JSON — expected a .geojson file.")

    if not isinstance(parsed, dict):
        raise LayerValidationError("Expected a GeoJSON object at the top level.")

    gtype = parsed.get('type')
    if gtype == 'FeatureCollection':
        features = parsed.get('features')
        if not isinstance(features, list):
            raise LayerValidationError("FeatureCollection has no 'features' array.")
    elif gtype == 'Feature':
        features = [parsed]
    elif gtype in ('Point', 'MultiPoint', 'LineString', 'MultiLineString',
                   'Polygon', 'MultiPolygon', 'GeometryCollection'):
        features = [{'type': 'Feature', 'properties': {}, 'geometry': parsed}]
    else:
        raise LayerValidationError(
            "Unrecognized GeoJSON type %r — expected a FeatureCollection." % (gtype,))

    if not features:
        raise LayerValidationError("The file contains no features.")
    if len(features) > MAX_LAYER_FEATURES:
        raise LayerValidationError(
            f"The file has {len(features)} features; the limit is {MAX_LAYER_FEATURES}.")

    properties = set()
    checked_any = False
    for f in features:
        if not isinstance(f, dict) or f.get('type') != 'Feature':
            raise LayerValidationError("Every entry in 'features' must be a Feature object.")
        props = f.get('properties')
        if isinstance(props, dict):
            properties.update(k for k in props if isinstance(k, str))
        for lng, lat in _geometry_coords(f.get('geometry')):
            checked_any = True
            if not (-180 <= lng <= 180 and -90 <= lat <= 90):
                raise LayerValidationError(
                    "Coordinates fall outside longitude/latitude ranges "
                    f"(found {lng:.1f}, {lat:.1f}). The file is probably in a projected "
                    "coordinate system — re-export it as WGS84 (EPSG:4326).")
    if not checked_any:
        raise LayerValidationError("No coordinates found in the file.")

    collection = {'type': 'FeatureCollection', 'features': features}
    geojson_str = json.dumps(collection, ensure_ascii=False, separators=(',', ':'))
    return geojson_str, len(features), sorted(properties)


def build_map_layers_metadata(survey):
    """Layer list for a map surface — config only, geometry stays behind the
    gated endpoint. Empty when the kill switch is off. Consumed by the
    respondent shell, the editor preview and the Responses tab alike."""
    from django.conf import settings as django_settings
    from django.urls import reverse
    if not django_settings.MAP_REFERENCE_LAYERS:
        return []
    return [
        {
            'id': layer.pk,
            'name': layer.name,
            'color': layer.color,
            # On a `question` layer `label_field` names a sub-question, not a
            # feature property; the title already carries it (`_title`), so no
            # permanent map label — the tally badge takes that spot.
            'label_field': '' if layer.source == 'question' else layer.label_field,
            'show_popups': layer.show_popups,
            'source': layer.source,
            'show_tallies': layer.source == 'question' and layer.show_tallies,
            # Bound to an Objects-on-the-map question: features are clickable
            # and open the object popup (card + sub-questions) instead of the
            # read-only name/description popup — spec reference-overlay-layers.
            'bound': layer.questions.filter(input_type='layer_objects').exists(),
            'url': reverse('survey_layer_geojson', kwargs={
                'survey_slug': str(survey.uuid), 'layer_id': layer.pk,
            }),
            'object_url': reverse('survey_layer_object', kwargs={
                'survey_slug': str(survey.uuid), 'layer_id': layer.pk, 'key': 'KEY',
            }),
        }
        # defer('geojson'): the 100s-of-KB geometry column loaded on every map
        # surface render fragments the worker heap into an RSS ratchet (the
        # 2026-09 "exceeded memory limits" incident); only config fields render.
        for layer in layers_for(survey).defer('geojson', 'geojson_legacy')
    ]


# ─── Objects ────────────────────────────────────────────────────────────────

def _clean_key(value):
    """Keys travel in URLs, form field names (`obj__<key>__<code>`) and CSV
    cells, so keep them to a safe charset. Slugify keeps unicode letters."""
    text = slugify(str(value), allow_unicode=True)
    return text[:100]


def derive_key(props, key_field, index, taken):
    """Object key for an imported feature: the file's key field when set and
    unused so far, else `f-<index>`. `taken` is the set of keys already assigned
    in this layer; the caller adds the result to it. Returns (key, from_field)."""
    if key_field and isinstance(props, dict):
        raw = props.get(key_field)
        if raw not in (None, ''):
            key = _clean_key(raw)
            if key:
                return key, True
    key = f'f-{index}'
    n = 1
    while key in taken:
        n += 1
        key = f'f-{index}-{n}'
    return key, False


def derive_title(props, label_field, key):
    """Title: the file's label field, then `name`/`title`-style columns, then the key."""
    if isinstance(props, dict):
        for field in (label_field, 'name', 'title', 'Name', 'NAME', 'label'):
            if field and props.get(field) not in (None, ''):
                return str(props[field])[:255]
    return key


def explode_geometry(geometry):
    """A LayerObject holds one Point/LineString/Polygon. Multi* and
    GeometryCollection split into parts; the caller suffixes their keys.
    Returns a list of geometry dicts; empty for unsupported input."""
    if not isinstance(geometry, dict):
        return []
    gtype = geometry.get('type')
    if gtype in _SINGLE_TYPES:
        return [geometry]
    if gtype in _MULTI_TYPES:
        part_type = _MULTI_TYPES[gtype]
        return [{'type': part_type, 'coordinates': c} for c in (geometry.get('coordinates') or [])]
    if gtype == 'GeometryCollection':
        parts = []
        for g in geometry.get('geometries') or []:
            parts.extend(explode_geometry(g))
        return parts
    return []


def _clean_mapping(mapping):
    mapping = mapping or {}
    return {k: (mapping.get(k) or '') for k in ('key', 'title', 'category', 'description', 'link')}


def objects_from_features(layer, features, mapping=None, sanitize=None):
    """Create LayerObject rows for validated GeoJSON features.

    `mapping` names the feature properties feeding key/title/category/
    description/link; unset entries fall back to the layer's `key_field` /
    `label_field` and the `name`-style heuristics. Returns a report:
    {'created': n, 'collisions': [key, ...], 'exploded': n, 'skipped': n}.
    A collision (a key already in the layer, or twice in the file) skips the
    feature and is reported rather than silently renumbered — the creator may
    be importing into a layer that already has answers hanging on those keys.

    `sanitize` is the creator-HTML coercer for descriptions; passed in rather
    than imported so this module stays importable from migrations."""
    from django.contrib.gis.geos import GEOSGeometry
    from survey.models import LayerObject

    m = _clean_mapping(mapping)
    key_field = m['key'] or layer.key_field
    label_field = m['title'] or layer.label_field
    taken = set(layer.items.values_list('key', flat=True))
    start_pos = (layer.items.order_by('-position').values_list('position', flat=True).first() or 0) + 1
    report = {'created': 0, 'collisions': [], 'exploded': 0, 'skipped': 0}
    rows = []
    for index, feature in enumerate(features, start=1):
        props = feature.get('properties') if isinstance(feature.get('properties'), dict) else {}
        parts = explode_geometry(feature.get('geometry'))
        if not parts:
            report['skipped'] += 1
            continue
        key, from_field = derive_key(props, key_field, index, taken)
        if from_field and key in taken:
            report['collisions'].append(key)
            continue
        if len(parts) > 1:
            report['exploded'] += 1
        for n, part in enumerate(parts, start=1):
            part_key = key if len(parts) == 1 else f'{key}-{n}'
            if part_key in taken:
                report['collisions'].append(part_key)
                continue
            taken.add(part_key)
            description = str(props.get(m['description']) or '') if m['description'] else ''
            if description and sanitize:
                description = sanitize(description)
            rows.append(LayerObject(
                layer=layer,
                key=part_key,
                title=derive_title(props, label_field, part_key),
                category=str(props.get(m['category']) or '')[:100] if m['category'] else '',
                description=description,
                link=str(props.get(m['link']) or '')[:500] if m['link'] else '',
                geometry=GEOSGeometry(json.dumps(part), srid=4326),
                position=start_pos + len(rows),
                # Reserved names are re-derived on output; storing them would
                # let a re-imported derived file shadow the object's own fields.
                properties={k: v for k, v in props.items()
                            if isinstance(k, str) and k not in RESERVED_PROPS},
            ))
    if rows:
        LayerObject.objects.bulk_create(rows, batch_size=500)
        report['created'] = len(rows)
    return report


def feature_for_object(obj, cover_url=''):
    """The derived GeoJSON feature: raw properties + the reserved fields."""
    props = dict(obj.properties or {})
    for reserved in RESERVED_PROPS:
        props.pop(reserved, None)
    props['_key'] = obj.key
    props['_title'] = obj.title
    props['_category'] = obj.category
    props['_has_content'] = bool(obj.description or obj.link or cover_url)
    props['_cover'] = cover_url
    return {
        'type': 'Feature',
        'id': obj.key,
        'properties': props,
        'geometry': json.loads(obj.geometry.geojson),
    }


def build_layer_geojson(layer):
    """FeatureCollection string for the layer, in object order."""
    from survey.models import LayerObjectAsset
    covers = {}
    for asset in (LayerObjectAsset.objects
                  .filter(object__layer=layer, kind='image')
                  .order_by('object_id', 'position', 'id')):
        covers.setdefault(asset.object_id, asset.url)
    if layer.source == 'question':
        # Creator surfaces (object editor, Responses map): every status of every
        # clean session, with the status exposed for badges. Respondents get
        # `build_question_layer_geojson` per request instead.
        features = []
        for obj in creator_objects(layer):
            feature = feature_for_object(obj)
            feature['properties']['_status'] = obj.status
            features.append(feature)
    else:
        features = [feature_for_object(obj, covers.get(obj.pk, ''))
                    for obj in layer.items.order_by('position', 'id')]
    return json.dumps({'type': 'FeatureCollection', 'features': features},
                      ensure_ascii=False, separators=(',', ':'))


def rebuild_layer(layer):
    """Recompute the derived GeoJSON and its counters; bumps `updated_at`, which
    is what the endpoint's ETag hangs on. Call after every object/asset write."""
    geojson = build_layer_geojson(layer)
    layer.geojson = geojson
    layer.feature_count = layer.items.count()
    layer.size_bytes = len(geojson.encode('utf-8'))
    layer.save(update_fields=['geojson', 'feature_count', 'size_bytes', 'updated_at'])
    return layer


def check_object_caps(layer, adding=1):
    """FD-1's caps apply to the derived layer: refuse an object that would push
    the layer past the feature count or the served-size limit."""
    count = layer.items.count()
    if count + adding > MAX_LAYER_FEATURES:
        raise LayerValidationError(
            f"This layer holds {count} objects; the limit is {MAX_LAYER_FEATURES}.")
    if layer.size_bytes > MAX_LAYER_BYTES:
        raise LayerValidationError(
            f"This layer's map data is over {MAX_LAYER_BYTES // (1024 * 1024)} MB. "
            "Simplify its geometry or split it into two layers.")


def bbox_of_collection(geojson_str):
    """(min_lng, min_lat, max_lng, max_lat) or None — used to verify the split migration."""
    try:
        parsed = json.loads(geojson_str)
    except ValueError:
        return None
    coords = [c for f in parsed.get('features') or [] for c in _geometry_coords(f.get('geometry'))]
    if not coords:
        return None
    lngs = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return (min(lngs), min(lats), max(lngs), max(lats))


# ─── Shared map: layers sourced from answers (spec shared-map-layer) ─────────
#
# A `question` layer's objects are other respondents' marks. They are
# MATERIALISED here from the geo answers on every section submit, keyed by
# session + mark index rather than by answer id, because the section POST
# deletes and re-inserts a session's answers on every submit: an answer-id key
# would recreate the object on Back → Next and drop every reaction other people
# had left on it.

import logging

_log = logging.getLogger(__name__)

GEO_INPUT_TYPES = ('point', 'line', 'polygon')
QUESTION_LAYER_KEY = 's{session}-{index}'


def source_question_for(layer, survey=None):
    """The geo question a `question` layer reads, resolved BY CODE inside
    `survey` (a version, a draft copy, or the canonical owner by default)."""
    from survey.models import Question
    if layer.source != 'question' or not layer.source_question_code:
        return None
    return (Question.objects
            .filter(survey_section__survey_header=survey or layer.survey,
                    code=layer.source_question_code,
                    input_type__in=GEO_INPUT_TYPES,
                    parent_question_id__isnull=True)
            .first())


def question_layers_for(survey, code):
    """Canonical `question` layers fed by the geo question with `code`."""
    return layer_owner(survey).map_layers.filter(source='question', source_question_code=code)


def answer_geometry(answer):
    return answer.point or answer.line or answer.polygon


def label_for_answer(answer, label_code):
    """The mark's title as OTHER respondents see it: the sub-answer named by the
    layer's `label_field` (a sub-question code here, a property name on upload
    layers). Choice-type labels come out as choice names; free text as written."""
    if not label_code:
        return ''
    from survey.models import Answer
    sub = (Answer.objects
           .filter(parent_answer_id=answer, question__code=label_code)
           .select_related('question')
           .first())
    if sub is None:
        return ''
    t = sub.question.input_type
    if t in ('text', 'text_line', 'datetime'):
        value = sub.text or ''
    elif t in ('choice', 'multichoice', 'rating', 'thumbs'):
        value = ', '.join(str(n) for n in sub.get_selected_choice_names())
    elif sub.numeric is not None:
        value = str(sub.numeric)
    else:
        value = ''
    return value[:255]


def sync_question_layer(layer, session):
    """Upsert `layer`'s objects for one session from its geo answers.

    The n-th stored feature is `s<session>-<n>`: an existing key is updated in
    place (geometry, title, source_answer) so reactions on it survive; missing
    indexes are created (`pending` on approve-first layers); keys of this
    session with no feature any more are deleted — and only then do the
    reactions on them go. Returns the number of objects present afterwards."""
    from django.db.models import Max
    from survey.models import Answer, LayerObject
    question = source_question_for(layer, session.survey)
    if question is None:
        return 0
    answers = (Answer.objects
               .filter(survey_session=session, question=question, parent_answer_id__isnull=True)
               .order_by('id'))
    existing = {o.key: o for o in layer.items.filter(source_session=session)}
    next_position = (layer.items.aggregate(m=Max('position'))['m'] or 0) + 1
    seen = []
    for index, answer in enumerate(answers, start=1):
        geometry = answer_geometry(answer)
        if geometry is None:
            continue
        key = QUESTION_LAYER_KEY.format(session=session.pk, index=index)
        seen.append(key)
        title = label_for_answer(answer, layer.label_field)
        obj = existing.get(key)
        if obj is not None:
            obj.geometry = geometry
            obj.title = title
            obj.source_answer = answer
            obj.save(update_fields=['geometry', 'title', 'source_answer', 'updated_at'])
        else:
            LayerObject.objects.create(
                layer=layer, key=key, title=title, geometry=geometry,
                source_session=session, source_answer=answer,
                status='pending' if layer.approve_first else 'visible',
                position=next_position,
            )
            next_position += 1
    layer.items.filter(source_session=session).exclude(key__in=seen).delete()
    rebuild_layer(layer)
    return len(seen)


def sync_question_layers_for_session(session, questions):
    """After a section POST: feed every `question` layer read by a geo question
    of that section. Never raises — a failed materialisation is logged and the
    next submit re-syncs; the answers themselves are already stored."""
    for question in questions:
        if question.input_type not in GEO_INPUT_TYPES:
            continue
        for layer in question_layers_for(session.survey, question.code):
            try:
                sync_question_layer(layer, session)
            except Exception:  # noqa: BLE001 — answers must never be lost to this
                _log.exception('shared map: materialisation failed for layer %s session %s',
                               layer.pk, session.pk)


def clean_session_filter(qs, prefix='source_session'):
    """The clean-session rule (public_results): not deleted, not on hold, not
    rejected. Applied to objects (via their source session) and to reactions."""
    from survey.public_results import EXCLUDED_VALIDATION_STATUSES
    return (qs.filter(**{f'{prefix}__is_deleted': False})
              .exclude(**{f'{prefix}__validation_status__in': EXCLUDED_VALIDATION_STATUSES}))


def visible_objects(layer, exclude_session_id=None):
    """What a RESPONDENT may see of a `question` layer: visible status, clean
    source session, and never their own marks."""
    qs = clean_session_filter(layer.items.filter(status='visible'))
    if exclude_session_id:
        qs = qs.exclude(source_session_id=exclude_session_id)
    return qs.order_by('position', 'id')


def creator_objects(layer):
    """What the CREATOR's surfaces show of a `question` layer: every status,
    clean sessions only (a rejected session's marks are gone everywhere)."""
    return clean_session_filter(layer.items.all()).order_by('position', 'id')


def build_question_layer_geojson(layer, exclude_session_id=None):
    """Per-request FeatureCollection for a respondent (spec shared-map-layer):
    own marks omitted, tallies attached when the layer shows them."""
    from survey.object_stats import shared_map_tallies
    tallies = shared_map_tallies(layer) if layer.show_tallies else {}
    features = []
    for obj in visible_objects(layer, exclude_session_id):
        feature = feature_for_object(obj)
        if layer.show_tallies:
            t = tallies.get(obj.key, {})
            feature['properties'].update({
                'tally_up': t.get('up', 0), 'tally_down': t.get('down', 0),
                'comment_count': t.get('comments', 0),
            })
        features.append(feature)
    return json.dumps({'type': 'FeatureCollection', 'features': features},
                      ensure_ascii=False, separators=(',', ':'))


def rebuild_question_layers_for(survey):
    """After a session's validation status / trash state changed: the creator
    surfaces read the cached GeoJSON, which must drop or restore that session's
    marks. Respondent responses are computed per request and need nothing."""
    for layer in layer_owner(survey).map_layers.filter(source='question'):
        rebuild_layer(layer)
