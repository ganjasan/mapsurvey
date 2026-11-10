"""Aggregates of budget questions (change budget-question, spec budget-question
"One aggregate for every read surface").

Responses, public results and the export call these and compute nothing of
their own. Answers are matched by question CODE across the survey family
(versions copy question rows), and the caller decides which sessions count —
public results pass its clean-session ids, Responses its filtered ones.

Split: per item the mean share of each respondent's OWN total (an answer keeps
the total it was given against, so a later change of the budget does not skew
old shares), mean and median amount, and how many gave it nothing. Projects:
per item the share of respondents who picked it, plus `fits` — items by
descending support while their costs fit the budget. Place items: per item the
mean and total count and the share of the budget spent on it.
"""
from statistics import median

from survey import budget
from survey.models import Answer
from survey.question_types import GEO_TYPES


def _answers(question, session_ids, answers=None):
    if answers is not None:
        return answers.filter(parent_answer_id__isnull=True)
    qs = Answer.objects.filter(question__code=question.code,
                               question__survey_section__survey_header__in=_family(question),
                               parent_answer_id__isnull=True)
    if session_ids is not None:
        qs = qs.filter(survey_session_id__in=session_ids)
    return qs


def _family(question):
    from survey.versioning import canonical_of, family_ids
    return family_ids(canonical_of(question.survey_section.survey_header))


def aggregate(question, session_ids=None, language=None, answers=None):
    """The mode's aggregate for one budget question, as a plain dict:
    `{mode, total, total_label, respondents, items: [...], ...}`.

    `answers` (a queryset of this question's answers, already scoped — what
    Responses passes from its lineage and filters) replaces the code-based
    family lookup and `session_ids`."""
    settings = budget.settings_of(question)
    if settings is None:
        return None
    items = budget.items_of(question, language)
    if settings['mode'] == budget.MODE_SPLIT:
        return _split(question, settings, items, session_ids, answers)
    return _projects(question, settings, items, session_ids, answers)


def _base(question, settings, respondents):
    return {
        'mode': settings['mode'],
        'total': settings['total'],
        'total_label': budget.format_amount(settings['total'], settings),
        'respondents': respondents,
        'settings': settings,
    }


def _split(question, settings, items, session_ids, answers=None):
    rows = [a.allocation for a in _answers(question, session_ids, answers).exclude(allocation__isnull=True)]
    n = len(rows)
    out = _base(question, settings, n)
    entries = []
    for item in items:
        amounts, shares = [], []
        for alloc in rows:
            own_total = budget._num(alloc.get('total')) or settings['total']
            amount = budget._num((alloc.get('items') or {}).get(item['code'])) or 0
            amounts.append(amount)
            shares.append(amount / own_total if own_total else 0)
        given = sum(1 for a in amounts if a > 0)
        mean_amount = sum(amounts) / n if n else 0
        entries.append({
            'code': item['code'], 'name': item['name'], 'color': item.get('color') or '',
            'n': given,
            'mean_share': sum(shares) / n if n else 0,
            'mean_amount': mean_amount,
            'mean_amount_label': budget.format_amount(round(mean_amount, 2), settings),
            'median_amount': median(amounts) if amounts else 0,
            'zero_share': (n - given) / n if n else 0,
        })
    out['items'] = entries
    return out


def _projects(question, settings, items, session_ids, answers=None):
    rows = [a.allocation for a in _answers(question, session_ids, answers).exclude(allocation__isnull=True)]
    n = len(rows)
    out = _base(question, settings, n)
    entries = []
    for item in items:
        picked = sum(1 for alloc in rows if item['code'] in (alloc.get('items') or {}))
        entries.append({
            'code': item['code'], 'name': item['name'], 'color': item.get('color') or '',
            'cost': item['cost'],
            'cost_label': budget.format_amount(item['cost'], settings) if item['cost'] is not None else '',
            'n': picked,
            'pick_share': picked / n if n else 0,
        })
    out['items'] = entries
    out['fits'] = fitting_set(entries, settings['total'])
    spent = [budget.spent(alloc) for alloc in rows]
    out['mean_spent'] = sum(spent) / n if n else 0
    out['mean_spent_label'] = budget.format_amount(round(out['mean_spent'], 2), settings)
    out['mean_picked'] = sum(len(alloc.get('items') or {}) for alloc in rows) / n if n else 0
    return out


def fitting_set(entries, total):
    """Codes of the items that fit the budget, taken by descending support
    (ties keep the creator's order); an item that does not fit is skipped and
    the next cheaper one may still fit."""
    ranked = sorted((e for e in entries if e.get('cost') is not None and e['n'] > 0),
                    key=lambda e: -e['pick_share'])
    left, fits = total, []
    for entry in ranked:
        if entry['cost'] <= left:
            fits.append(entry['code'])
            left -= entry['cost']
    return fits


def group_aggregate(group, answers_by_question=None, session_ids=None):
    """A budget group's result (change budget-question): per priced member the
    number of marks, the measure they add up to (count, metres or m²), what
    they cost, and the share of everything spent; plus respondents and the
    mean spend. `answers_by_question` maps member question id to a scoped
    queryset of its top-level answers (Responses); without it the family of
    the canonical survey is read, limited to `session_ids`."""
    settings = budget.group_settings(group)
    if settings is None:
        return None
    members = [q for q in group.members() if q.input_type in GEO_TYPES]
    entries, sessions, spend_total = [], set(), 0.0
    per_member = []
    for q in members:
        price = budget.price_of(q)
        if answers_by_question is not None:
            rows = answers_by_question.get(q.id)
            if rows is None:
                rows = Answer.objects.none()
        else:
            rows = _answers(q, session_ids)
        rows = rows.filter(parent_answer_id__isnull=True)
        count, measure, cost, placers = 0, 0.0, 0.0, set()
        for a in rows:
            geom = a.geometry
            if geom is None:
                continue
            count += 1
            placers.add(a.survey_session_id)
            if price:
                measure += budget.measure(geom, price['per'])
                cost += budget.feature_cost(price, geom)
        sessions |= placers
        spend_total += cost
        per_member.append((q, price, count, measure, cost, placers))
    n = len(sessions)
    for q, price, count, measure, cost, placers in per_member:
        entries.append({
            'code': q.code, 'name': q.name, 'input_type': q.input_type,
            'color': q.color if q.color and q.color != '#000000' else '',
            'price': price,
            'price_label': budget.format_price(price, settings) if price else '',
            'n': len(placers),
            'count': count,
            'measure': round(measure, 1),
            'measure_label': _measure_label(price, count, measure),
            'cost': cost,
            'cost_label': budget.format_amount(round(cost, 2), settings),
            'budget_share': cost / spend_total if spend_total else 0,
        })
    return {
        'mode': 'group',
        'total': settings['total'],
        'total_label': budget.format_amount(settings['total'], settings),
        'respondents': n,
        'settings': settings,
        'items': entries,
        'mean_spent': spend_total / n if n else 0,
        'mean_spent_label': budget.format_amount(round(spend_total / n, 2) if n else 0, settings),
    }


def _measure_label(price, count, measure):
    if not price or price['per'] == budget.PER_FEATURE:
        return f'×{count}'
    if price['per'] == budget.PER_LENGTH:
        return f'{measure:,.0f} m'
    return f'{measure:,.0f} m²'


def masked(aggregate_dict, k):
    """The aggregate with every item behind fewer than `k` respondents masked
    (public results, spec public-results-page "Budget block")."""
    if aggregate_dict is None:
        return None
    for entry in aggregate_dict['items']:
        entry['masked'] = 0 < entry['n'] < k
        if entry['masked']:
            for key in ('mean_share', 'mean_amount', 'median_amount', 'zero_share', 'pick_share',
                        'total_count', 'mean_count', 'budget_share'):
                if key in entry:
                    entry[key] = None
            entry['mean_amount_label'] = ''
    if 'fits' in aggregate_dict:
        hidden = {e['code'] for e in aggregate_dict['items'] if e.get('masked')}
        aggregate_dict['fits'] = [c for c in aggregate_dict['fits'] if c not in hidden]
    return aggregate_dict
