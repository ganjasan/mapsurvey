"""The numbers behind a block, as CSV (change reports-embed, #708).

A chart pasted into slides as a picture loses its numbers; this gives them back. The CSV is made
from the block's PAYLOAD — what the page shows — never from answers, so it obeys the same masking:
a group the page hides reads "<K" here and its value is nowhere in the file; a map's rows are its
cells, or its marks only when the author chose to show marks.
"""
import csv
import io

from django.utils.text import slugify

DATA_BLOCK_TYPES = ('chart', 'map', 'crosstab', 'engagement', 'compare', 'numbers', 'budget', 'objects')


def _cell(value):
    """A CSV cell; a text that a spreadsheet would run as a formula is apostrophe-guarded."""
    if value is None:
        return ''
    text = str(value)
    return "'" + text if text[:1] in ('=', '+', '-', '@') and not _is_number(text) else text


def _is_number(text):
    try:
        float(text)
        return True
    except ValueError:
        return False


def rows_of(payload):
    """[[cell]] with a header row, or None for a block that holds no numbers."""
    kind = payload.get('block_type')
    if kind == 'chart' and payload.get('data_type') == 'choices':
        return [['option', 'answers']] + [[i['label'], i['display']] for i in payload.get('items') or []]
    if kind == 'chart' and payload.get('data_type') == 'number':
        rows = [['range', 'answers']] + [list(pair) for pair in zip(payload.get('hist_labels') or [],
                                                                    payload.get('hist_counts') or [])]
        return rows + [['average', payload.get('avg')], ['median', payload.get('median')],
                       ['minimum', payload.get('min_val')], ['maximum', payload.get('max_val')]]
    if kind == 'crosstab':
        data = payload.get('data') or {}
        columns = (data.get('columns') or {}).get('items') or []
        rows = [[(data.get('rows') or {}).get('name', '')] + [c['label'] for c in columns] + ['total']]
        for line in payload.get('table') or []:
            rows.append([line['item']['label']] + [c['display'] for c in line['cells']]
                        + [line['item']['total']['display']])
        rows.append(['total'] + [c['total']['display'] for c in columns]
                    + [(data.get('respondents') or {}).get('display', '')])
        return rows
    if kind == 'compare':
        rounds = payload.get('rounds') or []
        head = ['']
        for r in rounds:
            head += [r['name'], '%s %%' % r['name']]
        rows = [head, ['people who answered'] + [x for r in rounds for x in (r['n'], '')]]
        for line in payload.get('rows') or []:
            rows.append([line['label']] + [x for c in line['cells']
                                           for x in (c['display'], '' if c['share'] is None else c['share'])])
        return rows
    if kind == 'engagement':
        data = payload.get('data') or {}
        rows = [['from', 'opened', 'answered', 'finished']]
        rows += [[p['start'], p['opened']['display'], p['answered']['display'], p['finished']['display']]
                 for p in data.get('series') or []]
        return rows + [['total'] + [s['display'] for s in data.get('steps') or []]]
    if kind == 'numbers':
        return [['value', 'label']] + [[i.get('value', ''), i.get('label', '')] for i in payload.get('items') or []]
    if kind == 'map' and payload.get('data_type') == 'marks':
        rows = [['geometry', 'longitude', 'latitude']]
        for feature in (payload.get('marks') or {}).get('features') or []:
            geometry = feature.get('geometry') or {}
            point = _first_point(geometry.get('coordinates'))
            rows.append([geometry.get('type', ''), point[0], point[1]])
        return rows
    if kind == 'map':
        rows = [['west', 'south', 'east', 'north', 'respondents']]
        for feature in (payload.get('cells') or {}).get('features') or []:
            ring = (feature.get('geometry') or {}).get('coordinates', [[]])[0]
            xs, ys = [p[0] for p in ring], [p[1] for p in ring]
            if xs:
                rows.append([round(min(xs), 6), round(min(ys), 6), round(max(xs), 6), round(max(ys), 6),
                             (feature.get('properties') or {}).get('respondents', '')])
        return rows
    if kind == 'budget' and payload.get('budget'):
        return [['item', 'share']] + [[r['name'], '<%s' % payload.get('k') if r['masked'] else '%s%%' % r['percent']]
                                      for r in payload['budget']['rows']]
    if kind == 'objects':
        return [['object', 'answers']] + [[r['title'] or r['key'], r['answers']['display']]
                                          for r in payload.get('rows') or []]
    return None


def _first_point(coords):
    while coords and isinstance(coords[0], (list, tuple)):
        coords = coords[0]
    return (coords[0], coords[1]) if coords and len(coords) >= 2 else ('', '')


def file_stem(payload, index=None):
    stem = slugify(payload.get('title') or payload.get('block_type') or 'block')[:60] or 'block'
    return '%02d-%s' % (index, stem) if index is not None else stem


def block_csv(payload):
    """(file name, text) of a block's numbers, or None when it has none."""
    rows = rows_of(payload)
    if rows is None:
        return None
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for row in rows:
        writer.writerow([_cell(value) for value in row])
    return file_stem(payload) + '.csv', buffer.getvalue()
