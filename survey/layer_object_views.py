"""The object editor: one full page per reference layer and the JSON endpoints
behind it (spec `layer-object-editor`).

Every mutation goes through `rebuild_layer`, so the derived GeoJSON the
respondent map loads can never lag the objects. Every endpoint is owner-only
and 404 under the layers kill switch; layers resolve through `layer_owner`, so
a draft copy edits the canonical survey's objects (design D-3).
"""
import csv
import io
import json
import os

from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry, GEOSException
from django.db import transaction
from django.db.models import Max, Sum
from django.http import Http404, JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST, require_http_methods

from .html_sanitize import coerce_creator_html
from .layer_assets import (
    validate_asset_upload, normalize_embed_url, AssetRejected,
    MAX_ASSET_BYTES, MAX_ASSETS_PER_OBJECT, object_card_payload,
)
from .layers import (
    layer_owner, layers_for, objects_from_features, rebuild_layer, check_object_caps,
    validate_layer_upload, LayerValidationError, explode_geometry, _clean_key,
    MAX_LAYER_BYTES, MAX_LAYERS_PER_SURVEY,
)
from .models import SurveyMapLayer, LayerObject, LayerObjectAsset, Answer
from .permissions import survey_permission_required


# ─── helpers ────────────────────────────────────────────────────────────────

def _enabled_or_404():
    if not settings.MAP_REFERENCE_LAYERS:
        raise Http404


def _layer(request, layer_id):
    _enabled_or_404()
    return get_object_or_404(SurveyMapLayer, pk=layer_id, survey=layer_owner(request.survey))


def _object(request, layer_id, key):
    layer = _layer(request, layer_id)
    return layer, get_object_or_404(LayerObject, layer=layer, key=key)


def _body(request):
    """JSON body, or the form-encoded POST as a fallback."""
    if request.content_type == 'application/json':
        try:
            return json.loads(request.body.decode('utf-8') or '{}')
        except ValueError:
            return {}
    return request.POST


def _error(message, status=400):
    return JsonResponse({'error': str(message)}, status=status)


def _next_key(layer, prefix='o'):
    n = layer.items.count() + 1
    taken = set(layer.items.values_list('key', flat=True))
    key = f'{prefix}-{n}'
    while key in taken:
        n += 1
        key = f'{prefix}-{n}'
    return key


def _geometry_from(payload):
    """A GeoJSON geometry dict (or string) → single-part GEOSGeometry, or None."""
    geometry = payload.get('geometry') if isinstance(payload, dict) else None
    if isinstance(geometry, str):
        try:
            geometry = json.loads(geometry)
        except ValueError:
            return None
    parts = explode_geometry(geometry)
    if len(parts) != 1:
        return None
    try:
        geom = GEOSGeometry(json.dumps(parts[0]), srid=4326)
    except (GEOSException, ValueError, TypeError):
        return None
    if not geom.valid and geom.geom_type != 'Point':
        return None
    return geom


def object_row(obj, cover_url=''):
    """The list-level row the editor page and its endpoints exchange."""
    counts = {}
    for asset in obj.assets.all():
        counts[asset.kind] = counts.get(asset.kind, 0) + 1
        if asset.kind == 'image' and not cover_url:
            cover_url = asset.url
    return {
        'key': obj.key,
        'title': obj.title,
        'category': obj.category,
        'cover': cover_url,
        'assets': counts,
        'has_text': bool(obj.description),
        'link': obj.link,
        'geometry_type': obj.geometry.geom_type,
        'bbox': list(obj.geometry.extent),
        'position': obj.position,
    }


def _object_detail(obj):
    data = object_card_payload(obj)
    data.update({
        'geometry': json.loads(obj.geometry.geojson),
        'properties': obj.properties or {},
        'position': obj.position,
        'assets': [
            {'id': a.pk, 'kind': a.kind, 'url': a.url, 'title': a.title,
             'content_type': a.content_type, 'size_bytes': a.size_bytes, 'position': a.position}
            for a in obj.assets.all()
        ],
    })
    return data


def _layer_summary(layer):
    return {
        'id': layer.pk, 'name': layer.name, 'color': layer.color,
        'object_count': layer.items.count(),
        'categories': sorted(c for c in layer.items.exclude(category='')
                             .values_list('category', flat=True).distinct()),
        'without_photo': layer.items.exclude(assets__kind='image').distinct().count(),
        'without_text': layer.items.filter(description='').count(),
        'published': layer.survey.status == 'published',
    }


# ─── page ───────────────────────────────────────────────────────────────────

@survey_permission_required('owner')
def layer_editor(request, survey_uuid, layer_id):
    layer = _layer(request, layer_id)
    objects = [object_row(o) for o in layer.items.prefetch_related('assets').order_by('position', 'id')]
    bound = list(layer.questions.values_list('name', flat=True)) if hasattr(layer, 'questions') else []
    return render(request, 'editor/layer_editor.html', {
        'survey': request.survey,
        'layer': layer,
        'summary': _layer_summary(layer),
        'objects_json': json.dumps(objects, ensure_ascii=False),
        'bound_questions': bound,
        'max_asset_mb': MAX_ASSET_BYTES // (1024 * 1024),
        'max_assets_per_object': MAX_ASSETS_PER_OBJECT,
    })


@survey_permission_required('owner')
@require_POST
def layer_create_empty(request, survey_uuid):
    """"New layer" on the settings card: an empty layer that opens in the editor."""
    _enabled_or_404()
    owner = layer_owner(request.survey)
    if owner.map_layers.count() >= MAX_LAYERS_PER_SURVEY:
        return _error(f'A survey can hold {MAX_LAYERS_PER_SURVEY} reference layers.')
    name = (request.POST.get('name') or 'New layer').strip()[:100]
    position = (owner.map_layers.aggregate(m=Max('position'))['m'] or 0) + 1
    layer = SurveyMapLayer.objects.create(survey=owner, name=name, geojson='', position=position)
    rebuild_layer(layer)
    return JsonResponse({'id': layer.pk, 'name': layer.name}, status=201)


# ─── objects ────────────────────────────────────────────────────────────────

@survey_permission_required('owner')
@require_http_methods(['GET', 'POST'])
def objects_collection(request, survey_uuid, layer_id):
    layer = _layer(request, layer_id)
    if request.method == 'GET':
        rows = [object_row(o) for o in layer.items.prefetch_related('assets').order_by('position', 'id')]
        return JsonResponse({'objects': rows, 'summary': _layer_summary(layer)})

    payload = _body(request)
    geom = _geometry_from(payload)
    if geom is None:
        return _error('A single Point, LineString or Polygon geometry is required.')
    try:
        check_object_caps(layer, adding=1)
    except LayerValidationError as exc:
        return _error(exc)
    key = _clean_key(payload.get('key') or '') or _next_key(layer)
    if layer.items.filter(key=key).exists():
        return _error(f'An object with key "{key}" already exists in this layer.')
    with transaction.atomic():
        obj = LayerObject.objects.create(
            layer=layer, key=key,
            title=str(payload.get('title') or '')[:255],
            category=str(payload.get('category') or '')[:100],
            geometry=geom,
            position=(layer.items.aggregate(m=Max('position'))['m'] or 0) + 1,
        )
        rebuild_layer(layer)
    return JsonResponse({'object': _object_detail(obj), 'row': object_row(obj),
                         'summary': _layer_summary(layer)}, status=201)


@survey_permission_required('owner')
@require_http_methods(['GET', 'PATCH', 'DELETE'])
def object_detail(request, survey_uuid, layer_id, key):
    layer, obj = _object(request, layer_id, key)
    if request.method == 'GET':
        return JsonResponse({'object': _object_detail(obj), 'row': object_row(obj)})

    if request.method == 'DELETE':
        with transaction.atomic():
            obj.delete()
            rebuild_layer(layer)
        return JsonResponse({'summary': _layer_summary(layer)})

    payload = _body(request)
    for field, limit in (('title', 255), ('category', 100), ('link', 500)):
        if field in payload:
            setattr(obj, field, str(payload.get(field) or '')[:limit])
    if 'description' in payload:
        obj.description = coerce_creator_html(str(payload.get('description') or ''))
    if 'properties' in payload and isinstance(payload['properties'], dict):
        obj.properties = {k: v for k, v in payload['properties'].items() if isinstance(k, str)}
    with transaction.atomic():
        obj.save()
        rebuild_layer(layer)
    return JsonResponse({'object': _object_detail(obj), 'row': object_row(obj),
                         'summary': _layer_summary(layer)})


@survey_permission_required('owner')
@require_POST
def object_geometry(request, survey_uuid, layer_id, key):
    layer, obj = _object(request, layer_id, key)
    geom = _geometry_from(_body(request))
    if geom is None:
        return _error('A single Point, LineString or Polygon geometry is required.')
    with transaction.atomic():
        obj.geometry = geom
        obj.save(update_fields=['geometry', 'updated_at'])
        rebuild_layer(layer)
    return JsonResponse({'row': object_row(obj)})


@survey_permission_required('owner')
def object_answer_count(request, survey_uuid, layer_id, key):
    """How many answers hang on this object — the delete confirmation quotes it."""
    _layer, obj = _object(request, layer_id, key)
    count = 0
    if hasattr(Answer, 'layer_object'):
        count = Answer.objects.filter(layer_object=obj).count()
    return JsonResponse({'answers': count})


@survey_permission_required('owner')
@require_POST
def objects_bulk(request, survey_uuid, layer_id):
    layer = _layer(request, layer_id)
    payload = _body(request)
    keys = payload.get('keys') or []
    if isinstance(keys, str):
        keys = [k for k in keys.split(',') if k]
    action = payload.get('action')
    qs = layer.items.filter(key__in=[str(k) for k in keys])
    with transaction.atomic():
        if action == 'set_category':
            n = qs.update(category=str(payload.get('category') or '')[:100])
        elif action == 'delete':
            n = qs.count()
            qs.delete()
        else:
            return _error('Unknown bulk action.')
        rebuild_layer(layer)
    return JsonResponse({'affected': n, 'summary': _layer_summary(layer)})


# ─── assets ─────────────────────────────────────────────────────────────────

@survey_permission_required('owner')
@require_POST
def asset_create(request, survey_uuid, layer_id, key):
    layer, obj = _object(request, layer_id, key)
    position = (obj.assets.aggregate(m=Max('position'))['m'] or 0) + 1
    embed = (request.POST.get('embed_url') or '').strip()
    if embed:
        if obj.assets.count() >= MAX_ASSETS_PER_OBJECT:
            return _error(f'An object can carry at most {MAX_ASSETS_PER_OBJECT} attachments.')
        try:
            url = normalize_embed_url(embed)
        except AssetRejected as exc:
            return _error(exc.message)
        asset = LayerObjectAsset.objects.create(
            object=obj, kind='embed', embed_url=url, position=position,
            title=(request.POST.get('title') or 'Video')[:255])
    else:
        f = request.FILES.get('file')
        if not f:
            return _error('No file.')
        try:
            kind, content_type = validate_asset_upload(obj, f)
        except AssetRejected as exc:
            return _error(exc.message)
        asset = LayerObjectAsset.objects.create(
            object=obj, kind=kind, file=f, title=(f.name or kind)[:255],
            content_type=content_type, size_bytes=f.size, position=position)
    rebuild_layer(layer)
    return JsonResponse({'asset': {'id': asset.pk, 'kind': asset.kind, 'url': asset.url,
                                   'title': asset.title, 'position': asset.position},
                         'row': object_row(obj)}, status=201)


@survey_permission_required('owner')
@require_http_methods(['PATCH', 'DELETE'])
def asset_detail(request, survey_uuid, layer_id, key, asset_id):
    layer, obj = _object(request, layer_id, key)
    asset = get_object_or_404(LayerObjectAsset, pk=asset_id, object=obj)
    if request.method == 'DELETE':
        asset.delete()
        rebuild_layer(layer)
        return JsonResponse({'row': object_row(obj)})
    payload = _body(request)
    if 'title' in payload:
        asset.title = str(payload.get('title') or '')[:255]
    asset.save()
    return JsonResponse({'asset': {'id': asset.pk, 'title': asset.title}})


@survey_permission_required('owner')
@require_POST
def assets_reorder(request, survey_uuid, layer_id, key):
    layer, obj = _object(request, layer_id, key)
    order = _body(request).get('order') or []
    if isinstance(order, str):
        order = [o for o in order.split(',') if o]
    ids = [int(i) for i in order if str(i).isdigit()]
    with transaction.atomic():
        for position, asset_id in enumerate(ids):
            LayerObjectAsset.objects.filter(pk=asset_id, object=obj).update(position=position)
        rebuild_layer(layer)
    return JsonResponse({'row': object_row(obj)})


# ─── imports ────────────────────────────────────────────────────────────────

def _mapping_from(request):
    src = _body(request)
    return {k: (src.get(f'map_{k}') or src.get(k) or '') for k in ('key', 'title', 'category', 'description', 'link')}


@survey_permission_required('owner')
@require_POST
def import_geojson(request, survey_uuid, layer_id):
    """`dry_run=1` returns the report without writing; the same request without
    it creates the objects. Mapping fields: map_key, map_title, map_category,
    map_description, map_link (property names from the file)."""
    layer = _layer(request, layer_id)
    f = request.FILES.get('file')
    if not f:
        return _error('No file.')
    if f.size > MAX_LAYER_BYTES:
        return _error(f'File is larger than {MAX_LAYER_BYTES // (1024 * 1024)} MB.')
    try:
        geojson_str, count, properties = validate_layer_upload(f.read())
    except LayerValidationError as exc:
        return _error(exc)
    try:
        check_object_caps(layer, adding=count)
    except LayerValidationError as exc:
        return _error(exc)
    features = json.loads(geojson_str)['features']
    mapping = _mapping_from(request)
    dry_run = str(request.POST.get('dry_run') or '') in ('1', 'true', 'on')
    with transaction.atomic():
        report = objects_from_features(layer, features, mapping=mapping, sanitize=coerce_creator_html)
        if dry_run:
            transaction.set_rollback(True)
        else:
            rebuild_layer(layer)
    report.update({'properties': properties, 'dry_run': dry_run, 'features': count})
    if not dry_run:
        report['summary'] = _layer_summary(layer)
    return JsonResponse(report)


def _read_csv(uploaded):
    text = uploaded.read().decode('utf-8-sig', errors='replace')
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows = [{(k or '').strip(): (v or '').strip() for k, v in row.items()} for row in reader]
    return rows, [h.strip() for h in (reader.fieldnames or [])]


def _pick(row, *names):
    lowered = {k.lower(): v for k, v in row.items()}
    for n in names:
        if n.lower() in lowered and lowered[n.lower()] != '':
            return lowered[n.lower()]
    return ''


@survey_permission_required('owner')
@require_POST
def import_csv(request, survey_uuid, layer_id):
    """Two shapes, told apart by the columns: rows with lat/lng become new point
    objects; rows without coordinates update existing objects matched by key,
    then by title. Unmatched rows are reported, never dropped silently."""
    layer = _layer(request, layer_id)
    f = request.FILES.get('file')
    if not f:
        return _error('No file.')
    rows, headers = _read_csv(f)
    if not rows:
        return _error('The CSV has no rows.')
    lower = [h.lower() for h in headers]
    has_coords = any(h in lower for h in ('lat', 'latitude')) and any(h in lower for h in ('lng', 'lon', 'longitude'))
    report = {'created': 0, 'updated': 0, 'unmatched': [], 'invalid': [], 'mode': 'coordinates' if has_coords else 'content'}

    with transaction.atomic():
        if has_coords:
            try:
                check_object_caps(layer, adding=len(rows))
            except LayerValidationError as exc:
                return _error(exc)
            taken = set(layer.items.values_list('key', flat=True))
            position = (layer.items.aggregate(m=Max('position'))['m'] or 0)
            for i, row in enumerate(rows, start=1):
                try:
                    lat = float(_pick(row, 'lat', 'latitude').replace(',', '.'))
                    lng = float(_pick(row, 'lng', 'lon', 'longitude').replace(',', '.'))
                except ValueError:
                    report['invalid'].append(i)
                    continue
                if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                    report['invalid'].append(i)
                    continue
                key = _clean_key(_pick(row, 'key', 'id')) or ''
                if not key or key in taken:
                    key = _next_key(layer) if not taken else f'o-{len(taken) + 1}'
                    while key in taken:
                        key = f'{key}-x'
                taken.add(key)
                position += 1
                LayerObject.objects.create(
                    layer=layer, key=key,
                    title=_pick(row, 'title', 'name')[:255] or key,
                    category=_pick(row, 'category', 'type')[:100],
                    description=coerce_creator_html(_pick(row, 'description', 'about', 'text')),
                    link=_pick(row, 'link', 'url')[:500],
                    geometry=GEOSGeometry(f'POINT({lng} {lat})', srid=4326),
                    position=position,
                )
                report['created'] += 1
        else:
            by_key = {o.key: o for o in layer.items.all()}
            by_title = {}
            for o in by_key.values():
                by_title.setdefault(o.title.strip().lower(), o)
            for i, row in enumerate(rows, start=1):
                obj = by_key.get(_clean_key(_pick(row, 'key', 'id'))) or by_title.get(_pick(row, 'title', 'name').strip().lower())
                if obj is None:
                    report['unmatched'].append(_pick(row, 'title', 'name', 'key', 'id') or f'row {i}')
                    continue
                changed = False
                for field, names, limit in (('category', ('category', 'type'), 100), ('link', ('link', 'url'), 500)):
                    value = _pick(row, *names)
                    if value:
                        setattr(obj, field, value[:limit])
                        changed = True
                desc = _pick(row, 'description', 'about', 'text')
                if desc:
                    obj.description = coerce_creator_html(desc)
                    changed = True
                title = _pick(row, 'title', 'name')
                if title and _pick(row, 'key', 'id'):
                    obj.title = title[:255]
                    changed = True
                if changed:
                    obj.save()
                    report['updated'] += 1
        rebuild_layer(layer)
    report['summary'] = _layer_summary(layer)
    return JsonResponse(report)


@survey_permission_required('owner')
@require_POST
def import_photos(request, survey_uuid, layer_id):
    """Many image files at once, each attached to the object whose key, then
    title, equals the filename stem (case-insensitive)."""
    layer = _layer(request, layer_id)
    files = request.FILES.getlist('files') or request.FILES.getlist('file')
    if not files:
        return _error('No files.')
    by_key = {o.key.lower(): o for o in layer.items.all()}
    by_title = {}
    for o in by_key.values():
        by_title.setdefault(o.title.strip().lower(), o)
    report = {'attached': 0, 'unmatched': [], 'rejected': []}
    with transaction.atomic():
        for f in files:
            stem = os.path.splitext(os.path.basename(f.name))[0].strip().lower()
            obj = by_key.get(stem) or by_key.get(_clean_key(stem)) or by_title.get(stem)
            if obj is None:
                report['unmatched'].append(f.name)
                continue
            try:
                kind, content_type = validate_asset_upload(obj, f)
            except AssetRejected as exc:
                report['rejected'].append(f'{f.name}: {exc.message}')
                continue
            if kind != 'image':
                report['rejected'].append(f'{f.name}: not an image')
                continue
            position = (obj.assets.aggregate(m=Max('position'))['m'] or 0) + 1
            LayerObjectAsset.objects.create(object=obj, kind='image', file=f, title=f.name[:255],
                                            content_type=content_type, size_bytes=f.size, position=position)
            report['attached'] += 1
        rebuild_layer(layer)
    report['summary'] = _layer_summary(layer)
    return JsonResponse(report)
