"""Saved views over datasets (change data-views, #672).

A view of a LAYER dataset keeps the objects matching its conditions, with only its fields; a view of
an ANSWERS dataset (privacy `aggregated`) is a grid of counts of distinct respondents, cells under K
omitted, through `data.aggregate` — the dataset's privacy class decides which, never the creator.
Conditions and fields name public fields only. Every surface that shows a view (the survey's layer
GeoJSON and object card, a Site map block) reads it through here.
"""
import hashlib
import json
import re

from django.utils.translation import gettext as _

from data.models import Dataset, DatasetView

OPS = ('eq', 'in', 'gt', 'lt')
_HEX = re.compile(r'^#[0-9a-fA-F]{6}$')
CACHE_SECONDS = 300


def kind_for(dataset):
    if dataset.kind == Dataset.KIND_LAYER and dataset.layer_id and dataset.layer.source != 'question':
        return DatasetView.KIND_OBJECTS
    if dataset.kind == Dataset.KIND_ANSWERS:
        return DatasetView.KIND_GRID
    return None


def public_fields(dataset):
    """{name: label} of the dataset's public fields (the dictionary, or the layer's names)."""
    from data.fields import dictionary
    return {f['name']: f['label'] for f in dictionary(dataset) if not f['private']}


def clean(dataset, raw):
    """(values, errors) for a view posted as {'name', 'color', 'field_n', 'op_n', 'value_n', 'fields'}."""
    errors = {}
    kind = kind_for(dataset)
    if kind is None:
        return {}, {'kind': _('Views are made of layers and of map answers.')}
    name = str(raw.get('name') or '').strip()[:120]
    if not name:
        errors['name'] = _('Give the view a name.')
    color = str(raw.get('color') or '').strip()
    color = color.lower() if _HEX.match(color) else ''
    conditions, fields = [], []
    if kind == DatasetView.KIND_OBJECTS:
        known = public_fields(dataset)
        for i in range(5):
            field = str(raw.get(f'field_{i}') or '').strip()
            if not field:
                continue
            op = raw.get(f'op_{i}') if raw.get(f'op_{i}') in OPS else 'eq'
            value = str(raw.get(f'value_{i}') or '').strip()[:200]
            if field not in known:
                errors['conditions'] = _('A condition can only use a public field of this dataset.')
                continue
            if op == 'in':
                conditions.append({'field': field, 'op': op, 'values': [v.strip() for v in value.split(',') if v.strip()]})
            else:
                if op in ('gt', 'lt') and _number(value) is None:
                    errors['conditions'] = _('“Greater than” and “less than” need a number.')
                    continue
                conditions.append({'field': field, 'op': op, 'value': value})
        chosen = raw.getlist('fields') if hasattr(raw, 'getlist') else raw.get('fields') or []
        if any(f not in known for f in chosen):
            errors['fields'] = _('A view can only keep public fields of this dataset.')
        fields = [f for f in chosen if f in known]
        if set(fields) == set(known):
            fields = []
    return {'name': name, 'kind': kind, 'color': color, 'conditions': conditions, 'fields': fields}, errors


def _number(value):
    try:
        return float(str(value).replace(',', '.'))
    except (TypeError, ValueError):
        return None


def matches(view, props):
    """Whether an object's properties satisfy every condition of the view."""
    props = props if isinstance(props, dict) else {}
    for c in view.conditions or []:
        have = props.get(c.get('field'))
        if c.get('op') == 'in':
            if str(have) not in {str(v) for v in c.get('values') or []}:
                return False
        elif c.get('op') in ('gt', 'lt'):
            a, b = _number(have), _number(c.get('value'))
            if a is None or b is None or (a <= b if c['op'] == 'gt' else a >= b):
                return False
        else:
            want = c.get('value')
            if str(have) != str(want) and not (_number(have) is not None and _number(have) == _number(want)):
                return False
    return True


def kept_names(view):
    """Field names a view keeps: its chosen fields, else every public field."""
    known = set(public_fields(view.dataset))
    return (set(view.fields) & known) if view.fields else known


def object_keys(view):
    """Keys of the layer objects the view shows (for the object card)."""
    return {row['key'] for row in view.dataset.layer.items.values('key', 'properties').iterator(chunk_size=500)
            if matches(view, row['properties'])}


def objects_geojson(view):
    """The view's FeatureCollection text: matching objects, kept fields only. Cached per view,
    layer rebuild and view edit; built one feature at a time like the layer cache."""
    from django.core.cache import cache
    from survey.layers import _OBJECT_ROW_FIELDS, _feature_json
    layer = view.dataset.layer
    key = 'dataview:%s:%s:%s' % (view.pk, layer.updated_at.timestamp(), view.updated_at.timestamp())
    try:
        hit = cache.get(key)
    except Exception:  # noqa: BLE001 — a cache outage costs a rebuild, never the page
        hit = None
    if hit is not None:
        return hit
    keep = kept_names(view)
    parts = []
    for row in layer.items.order_by('position', 'id').values(*_OBJECT_ROW_FIELDS).iterator(chunk_size=500):
        if not matches(view, row['properties']):
            continue
        props = row['properties'] if isinstance(row['properties'], dict) else {}
        hidden = frozenset(k for k in props if k not in keep)
        parts.append(_feature_json(row, '', None, hidden))
    body = '{"type":"FeatureCollection","features":[' + ','.join(parts) + ']}'
    try:
        cache.set(key, body, CACHE_SECONDS)
    except Exception:  # noqa: BLE001
        pass
    return body


def _k_for(survey):
    from survey.models import PublicResultsPage
    page = PublicResultsPage.objects.filter(survey=survey).only('k_anonymity_threshold').first()
    k = page.k_anonymity_threshold if page is not None else \
        PublicResultsPage._meta.get_field('k_anonymity_threshold').default
    return max(1, k or 1)


def grid_geojson(view):
    """A grid view's FeatureCollection: one polygon per cell with its count of distinct respondents;
    cells under K are omitted by `data.aggregate.grid`. No mark ever leaves."""
    from data.aggregate import grid
    from data.features import question_features
    from data.scope import SessionScope
    ds = view.dataset
    survey = ds.survey
    k = _k_for(survey)
    cells = grid(question_features(survey, ds.question_code, scope=SessionScope.public(survey)), k=k)
    features = []
    for cell in cells['cells']:
        x0, y0, x1, y1 = cell['bbox']
        features.append({'type': 'Feature', 'properties': {'respondents': cell['respondents']},
                         'geometry': {'type': 'Polygon',
                                      'coordinates': [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}})
    return json.dumps({'type': 'FeatureCollection', 'k': k, 'features': features}, separators=(',', ':'))


def geojson_response(request, view):
    """The view's collection as a response, with an ETag on its content."""
    from django.http import HttpResponse
    body = grid_geojson(view) if view.kind == DatasetView.KIND_GRID else objects_geojson(view)
    etag = '"view-%s-%s"' % (view.pk, hashlib.md5(body.encode('utf-8')).hexdigest()[:16])
    if request.headers.get('If-None-Match') == etag:
        response = HttpResponse(status=304)
    else:
        response = HttpResponse(body, content_type='application/geo+json')
    response['ETag'] = etag
    response['Cache-Control'] = 'private, max-age=60'
    return response
