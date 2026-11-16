"""Analysis views: what a view computes (change data-analysis-views, #692; epic #712).

Four kinds beside the saved filters of `data.dataviews`:

- ``engagement`` (a `responses` dataset): opened → answered → finished, and the three per period;
- ``crosstab`` (a `responses` dataset): two choice-type questions, distinct respondents per pair;
- ``coverage`` (an `answers` dataset of lines or areas): per cell, the respondents whose shape
  reaches it and their share of everyone who drew;
- ``density`` (an `answers` dataset of points or spray): per cell, the marks inside it.

Everything here counts `SessionScope.public` sessions and leaves through `data.aggregate`: a count
under K is masked, a cell under K is omitted. There is no unmasked variant — a view is something a
report, a Site or an API client shows to people outside the workspace. Reports render these
results and compute nothing themselves (Reports Vision BO-4).
"""
from collections import defaultdict

from data.aggregate import grid, mask
from data.scope import SessionScope

CROSSTAB_TYPES = ('choice', 'multichoice', 'rating', 'thumbs')
COVERAGE_TYPES = ('line', 'polygon')
DENSITY_TYPES = ('point', 'spraycan')

# A series longer than this many buckets moves to the next coarser period.
MAX_DAYS = 45
MAX_WEEKS = 53

WITHHELD = {'value': None, 'display': '—', 'masked': True}


# ── engagement ────────────────────────────────────────────────────────────────

def _period(first, last):
    span = (last - first).days + 1
    if span <= MAX_DAYS:
        return 'day'
    if span <= MAX_WEEKS * 7:
        return 'week'
    return 'month'


def _bucket_start(day, period):
    from datetime import timedelta
    if period == 'week':
        return day - timedelta(days=day.weekday())
    if period == 'month':
        return day.replace(day=1)
    return day


def engagement(survey, k):
    """Opened → answered → finished for a canonical survey, whole and per period.

    ``opened``: clean sessions (not trashed, not moderated out); ``answered``: those with an answer
    — the number every public surface calls "responses"; ``finished``: those with no required
    question left unanswered (`completed_session_filter`). Periods are days up to 45 days of
    collection, weeks up to a year, months beyond, by the day a session started."""
    from django.utils import timezone
    scope = SessionScope.for_family(survey)
    answered_ids = set(scope.replace(nonempty=True).sessions().values_list('id', flat=True))
    finished_ids = set(scope.replace(completed=True).sessions().values_list('id', flat=True))
    rows = list(scope.sessions().exclude(start_datetime__isnull=True).values_list('id', 'start_datetime'))
    undated = scope.sessions().filter(start_datetime__isnull=True).count()

    totals = {'opened': len(rows) + undated, 'answered': len(answered_ids), 'finished': len(finished_ids)}
    out = {
        'kind': 'engagement', 'k': k,
        'steps': [{'key': key, **mask(totals[key], k)} for key in ('opened', 'answered', 'finished')],
        'period': None, 'first': None, 'last': None, 'series': [],
    }
    if not rows:
        return out
    days = [(sid, timezone.localtime(start).date()) for sid, start in rows]
    first, last = min(d for _s, d in days), max(d for _s, d in days)
    period = _period(first, last)
    buckets = defaultdict(lambda: {'opened': 0, 'answered': 0, 'finished': 0})
    for sid, day in days:
        b = buckets[_bucket_start(day, period)]
        b['opened'] += 1
        if sid in answered_ids:
            b['answered'] += 1
        if sid in finished_ids:
            b['finished'] += 1
    out.update(period=period, first=first.isoformat(), last=last.isoformat())
    out['series'] = [{'start': start.isoformat(),
                      **{key: mask(b[key], k) for key in ('opened', 'answered', 'finished')}}
                     for start, b in sorted(buckets.items())]
    return out


# ── cross-tab ─────────────────────────────────────────────────────────────────

def choices_of(question):
    """[(code, raw choice)] a choice-type question lays out."""
    choices = question.choices
    if not choices and question.input_type == 'thumbs':
        choices = question.thumbs_choices()
    if not choices and question.input_type == 'rating':
        choices = question.star_choices()
    return [c['code'] for c in (choices or [])]


def _label(question, code, lang):
    if question.input_type == 'rating' and not question.choices:
        return str(code)
    return str(question.get_choice_name(code, lang))


def _selections(survey, question, scope):
    """{session id: {choice codes}} of a question's lineage (same code and type across versions)."""
    from survey.models import Answer
    from survey.versioning import family_ids
    out = defaultdict(set)
    rows = (Answer.objects
            .filter(question__code=question.code, question__input_type=question.input_type,
                    question__parent_question_id__isnull=True,
                    question__survey_section__survey_header_id__in=family_ids(survey))
            .filter(scope.q('survey_session'))
            .values_list('survey_session_id', 'selected_choices'))
    for session_id, selected in rows:
        out[session_id].update(selected or [])
    return out


def _withhold_margins(cells, totals_by_row, totals_by_column, k):
    """Row and column totals as display dicts. A total under K is masked like any count; the total
    of a line holding a masked cell is withheld, because the total minus the cells shown would
    give that cell away (one masked cell) or pin several down (two cells adding up to 2)."""
    rows = [dict(WITHHELD) if any(c['masked'] for c in cells[r]) else mask(total, k)
            for r, total in enumerate(totals_by_row)]
    columns = [dict(WITHHELD) if any(row[c]['masked'] for row in cells) else mask(total, k)
               for c, total in enumerate(totals_by_column)]
    return rows, columns


def crosstab(survey, rows_question, columns_question, k, lang='en'):
    """Distinct respondents per (row choice, column choice) among those who answered both
    questions. A multiple-choice answer counts in every choice it holds, so a line of such a
    question may add up to more than its total."""
    scope = SessionScope.public(survey)
    by_row = _selections(survey, rows_question, scope)
    by_column = _selections(survey, columns_question, scope)
    both = [s for s in by_row if s in by_column and by_row[s] and by_column[s]]
    row_codes, column_codes = choices_of(rows_question), choices_of(columns_question)
    row_index = {code: i for i, code in enumerate(row_codes)}
    column_index = {code: i for i, code in enumerate(column_codes)}
    counts = [[0] * len(column_codes) for _r in row_codes]
    row_totals, column_totals = [0] * len(row_codes), [0] * len(column_codes)
    for session_id in both:
        rs = [row_index[c] for c in by_row[session_id] if c in row_index]
        cs = [column_index[c] for c in by_column[session_id] if c in column_index]
        for r in rs:
            row_totals[r] += 1
        for c in cs:
            column_totals[c] += 1
        for r in rs:
            for c in cs:
                counts[r][c] += 1
    cells = [[mask(n, k) for n in line] for line in counts]
    shown_rows, shown_columns = _withhold_margins(cells, row_totals, column_totals, k)
    masked_cells = sum(1 for line in cells for c in line if c['masked'])

    def describe(question):
        return {'code': question.code, 'name': question.name, 'type': question.input_type,
                'multiple': question.input_type == 'multichoice'}

    return {
        'kind': 'crosstab', 'k': k,
        'rows': {**describe(rows_question),
                 'items': [{'code': code, 'label': _label(rows_question, code, lang), 'total': shown_rows[i]}
                           for i, code in enumerate(row_codes)]},
        'columns': {**describe(columns_question),
                    'items': [{'code': code, 'label': _label(columns_question, code, lang),
                               'total': shown_columns[i]} for i, code in enumerate(column_codes)]},
        'cells': cells,
        # The grand total goes with them: it and the other lines' totals would return a
        # withheld total, and that one its masked cell.
        'respondents': dict(WITHHELD) if masked_cells else mask(len(both), k),
        'masked_cells': masked_cells,
    }


# ── coverage and density ──────────────────────────────────────────────────────

def cells(survey, question_code, k, kind='grid'):
    """A FeatureCollection dict of grid cells over one geo question's answers.

    Every kind is the same grid (`data.aggregate.grid`: the finest that shows most respondents,
    cells under K omitted); the kind decides what a cell says:
    ``grid`` — `respondents`; ``coverage`` — `respondents` and their `share` of everyone who drew;
    ``density`` — `marks` (points or spray dots inside) and `respondents`."""
    from data.features import question_features
    result = grid(question_features(survey, question_code, scope=SessionScope.public(survey)), k=k)
    total = result['respondents_total']
    features = []
    for cell in result['cells']:
        x0, y0, x1, y1 = cell['bbox']
        props = {'respondents': cell['respondents']}
        if kind == 'coverage':
            props['share'] = round(cell['respondents'] / total, 3) if total else 0
        elif kind == 'density':
            props['marks'] = cell['marks']
        features.append({'type': 'Feature', 'properties': props,
                         'geometry': {'type': 'Polygon',
                                      'coordinates': [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}})
    out = {'type': 'FeatureCollection', 'kind': kind, 'k': k,
           'respondents_total': total, 'respondents_hidden': result['respondents_hidden'],
           'cell_m': result['cell_m'], 'max': result['max'], 'features': features}
    if kind == 'density':
        out['max_marks'] = max((c['marks'] for c in result['cells']), default=0)
    return out
