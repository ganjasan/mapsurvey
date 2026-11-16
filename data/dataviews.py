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


def kinds_for(dataset):
    """The view kinds a dataset allows, the default first (change data-analysis-views): what the
    dataset holds decides, never the creator. () = no views."""
    from data.analysis import COVERAGE_TYPES, DENSITY_TYPES
    V = DatasetView
    if dataset.kind == Dataset.KIND_LAYER and dataset.layer_id and dataset.layer.source != 'question':
        return (V.KIND_OBJECTS,)
    if dataset.kind == Dataset.KIND_ANSWERS:
        from data.questions import question_of
        question = question_of(dataset.survey, dataset.question_code)
        input_type = question.input_type if question is not None else ''
        if input_type in COVERAGE_TYPES:
            return (V.KIND_GRID, V.KIND_COVERAGE)
        if input_type in DENSITY_TYPES:
            return (V.KIND_GRID, V.KIND_DENSITY)
        return (V.KIND_GRID,)
    if dataset.kind == Dataset.KIND_RESPONSES:
        return (V.KIND_ENGAGEMENT, V.KIND_CROSSTAB, V.KIND_RESPONSES)
    return ()


def kind_for(dataset):
    """The dataset's default view kind, or None."""
    kinds = kinds_for(dataset)
    return kinds[0] if kinds else None


def kind_labels(kinds):
    labels = dict(DatasetView.KIND_CHOICES)
    return [(k, labels[k]) for k in kinds]


def crosstab_questions(dataset):
    """The questions a cross-tab of a responses dataset may name, in survey order."""
    from data.analysis import CROSSTAB_TYPES
    from data.questions import top_level_questions
    return top_level_questions(dataset.survey, CROSSTAB_TYPES)


def _clean_crosstab(dataset, config, errors):
    from data.analysis import CROSSTAB_TYPES
    from data.questions import questions_of
    config = config if isinstance(config, dict) else {}
    rows, columns = str(config.get('rows') or '').strip(), str(config.get('columns') or '').strip()
    if not rows or not columns:
        errors['config'] = _('A cross-tab needs two questions: one for the rows, one for the columns.')
        return {}
    if rows == columns:
        errors['config'] = _('Pick two different questions.')
        return {}
    found = questions_of(dataset.survey, [rows, columns])
    for code in (rows, columns):
        q = found.get(code)
        if q is None or q.parent_question_id_id is not None or q.input_type not in CROSSTAB_TYPES:
            errors['config'] = _('“%(code)s” is not a choice, rating or thumbs question of this survey.') % {'code': code}
            return {}
    return {'rows': rows, 'columns': columns}


def public_fields(dataset):
    """{name: label} of the dataset's public fields (the dictionary, or the layer's names)."""
    from data.fields import dictionary
    return {f['name']: f['label'] for f in dictionary(dataset) if not f['private']}


def clean(dataset, raw):
    """(values, errors) for a view posted as {'name', 'color', 'field_n', 'op_n', 'value_n', 'fields'}."""
    errors = {}
    kinds = kinds_for(dataset)
    if not kinds:
        return {}, {'kind': _('Views are made of layers, of map answers and of responses.')}
    kind = str(raw.get('kind') or '').strip() or kinds[0]
    if kind not in kinds:
        return {}, {'kind': _('This dataset takes these views: %(kinds)s.')
                    % {'kinds': ', '.join(str(label) for _k, label in kind_labels(kinds))}}
    config = {}
    if kind == DatasetView.KIND_CROSSTAB:
        config = _clean_crosstab(dataset, raw.get('config'), errors)
    elif kind == DatasetView.KIND_RESPONSES:
        from data.responses_views import clean_config
        config = clean_config(raw.get('config'))
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
    return {'name': name, 'kind': kind, 'color': color, 'conditions': conditions, 'fields': fields,
            'config': config}, errors


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
    from reports.render import k_for_survey
    return k_for_survey(survey)


def grid_geojson(view):
    """A grid view's FeatureCollection: one polygon per cell with its count of distinct respondents;
    cells under K are omitted by `data.aggregate.grid`. No mark ever leaves."""
    return json.dumps(cells(view), separators=(',', ':'))


def cells(view):
    """A cell view's FeatureCollection as a dict — `grid`, `coverage` or `density`
    (`data.analysis.cells`), with the K it used."""
    from data.analysis import cells as _cells
    ds = view.dataset
    return _cells(ds.survey, ds.question_code, _k_for(ds.survey), kind=view.kind)


def result(view, lang='en'):
    """What a computed view yields, as a dict: the cells of a grid / coverage / density view, the
    steps and series of an engagement view, the table of a cross-tab. Masked for every reader
    (design decision 6). None for a saved filter (objects, responses)."""
    from data import analysis
    ds = view.dataset
    if view.kind in DatasetView.CELL_KINDS:
        return cells(view)
    k = _k_for(ds.survey)
    if view.kind == DatasetView.KIND_ENGAGEMENT:
        return analysis.engagement(ds.survey, k)
    if view.kind == DatasetView.KIND_CROSSTAB:
        from data.questions import questions_of
        config = view.config or {}
        found = questions_of(ds.survey, [config.get('rows'), config.get('columns')])
        rows, columns = found.get(config.get('rows')), found.get(config.get('columns'))
        if rows is None or columns is None:
            return {'kind': 'crosstab', 'k': k, 'missing': [c for c in (config.get('rows'), config.get('columns'))
                                                           if c not in found]}
        return analysis.crosstab(ds.survey, rows, columns, k, lang=lang)
    return None


def geojson_response(request, view):
    """The view's collection as a response, with an ETag on its content."""
    from django.http import HttpResponse
    body = grid_geojson(view) if view.kind in DatasetView.CELL_KINDS else objects_geojson(view)
    etag = '"view-%s-%s"' % (view.pk, hashlib.md5(body.encode('utf-8')).hexdigest()[:16])
    if request.headers.get('If-None-Match') == etag:
        response = HttpResponse(status=304)
    else:
        response = HttpResponse(body, content_type='application/geo+json')
    response['ETag'] = etag
    response['Cache-Control'] = 'private, max-age=60'
    return response
