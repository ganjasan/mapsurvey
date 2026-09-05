"""Per-object aggregates for Objects-on-the-map questions (spec object-answers).

One computation shared by the response ZIP (results GeoJSON), the Responses tab
(per-object table and map badges) and the public results page (masked by k),
so "31 answers · 4.2★ · 👍 24/7" is the same number on every surface.
"""
from collections import defaultdict

from django.db.models import Q

from .models import Answer, Question


def sub_questions_of(question):
    return list(Question.objects.filter(parent_question_id=question).order_by('order_number', 'id'))


def object_aggregates(question, session_ids=None, excluded_session_ids=None, include_text=False):
    """{object_key: {'key', 'title', 'answers', 'subs': {code: {...}}}} for one
    `layer_objects` question.

    `answers` counts distinct sessions with at least one stored value about the
    object. Per sub-question: rating/range/number → mean+count; thumbs → up/down;
    choice/multichoice → per-code counts; text → count (and the values only when
    `include_text`, which the public page never passes)."""
    if question.input_type != 'layer_objects' or not question.layer_id:
        return {}
    subs = sub_questions_of(question)
    by_code = {q.code: q for q in subs}
    qs = (Answer.objects
          .filter(question__in=subs, layer_object__isnull=False)
          .exclude(survey_session__is_deleted=True)
          .select_related('layer_object', 'question'))
    if session_ids is not None:
        qs = qs.filter(survey_session_id__in=session_ids)
    if excluded_session_ids:
        qs = qs.exclude(survey_session_id__in=excluded_session_ids)

    out = {}
    for obj in question.layer.items.order_by('position', 'id'):
        out[obj.key] = {
            'key': obj.key, 'title': obj.title or obj.key, 'category': obj.category,
            'answers': 0, '_sessions': set(),
            'subs': {q.code: _empty(q) for q in subs},
        }
    for a in qs:
        entry = out.get(a.layer_object.key)
        if entry is None:
            continue
        entry['_sessions'].add(a.survey_session_id)
        sub = entry['subs'][a.question.code]
        q = by_code[a.question.code]
        _accumulate(sub, q, a, include_text)
    for entry in out.values():
        entry['answers'] = len(entry.pop('_sessions'))
        for sub in entry['subs'].values():
            _finish(sub)
    return out


def _empty(q):
    base = {'code': q.code, 'name': q.name, 'type': q.input_type, 'count': 0}
    if q.input_type in ('rating', 'range', 'number'):
        base.update({'sum': 0.0, 'mean': None})
    elif q.input_type == 'thumbs':
        base.update({'up': 0, 'down': 0})
    elif q.input_type in ('choice', 'multichoice'):
        base.update({'counts': {str(c['code']): 0 for c in (q.choices or [])},
                     'labels': {str(c['code']): q.get_choice_name(c['code']) for c in (q.choices or [])}})
    elif q.input_type in ('text', 'text_line'):
        base.update({'values': []})
    return base


def _accumulate(sub, q, a, include_text):
    t = q.input_type
    if t == 'rating':
        codes = a.selected_choices or []
        if codes:
            sub['count'] += 1
            sub['sum'] += float(codes[0])
    elif t in ('range', 'number'):
        if a.numeric is not None:
            sub['count'] += 1
            sub['sum'] += float(a.numeric)
    elif t == 'thumbs':
        codes = a.selected_choices or []
        if codes:
            sub['count'] += 1
            if int(codes[0]) == 1:
                sub['up'] += 1
            else:
                sub['down'] += 1
    elif t in ('choice', 'multichoice'):
        codes = a.selected_choices or []
        if codes:
            sub['count'] += 1
            for c in codes:
                sub['counts'][str(c)] = sub['counts'].get(str(c), 0) + 1
    elif t in ('text', 'text_line'):
        if a.text:
            sub['count'] += 1
            if include_text:
                sub['values'].append(a.text)
    else:
        if a.text or a.numeric is not None or a.selected_choices:
            sub['count'] += 1


def _finish(sub):
    if 'sum' in sub:
        sub['mean'] = round(sub['sum'] / sub['count'], 2) if sub['count'] else None
        sub.pop('sum', None)


def headline(entry):
    """Short badge text for a map feature: "31 · 4.2★ · 👍 24/7"."""
    parts = [str(entry['answers'])]
    for sub in entry['subs'].values():
        if sub['type'] == 'rating' and sub.get('mean') is not None:
            parts.append('%s★' % sub['mean'])
        elif sub['type'] == 'thumbs' and sub['count']:
            parts.append('👍 %s/%s' % (sub['up'], sub['down']))
    return ' · '.join(parts)


def flat_properties(entry):
    """GeoJSON-friendly properties for one object's aggregates (no text values)."""
    props = {'answers': entry['answers']}
    for sub in entry['subs'].values():
        prefix = sub['code']
        props['%s_count' % prefix] = sub['count']
        if sub['type'] in ('rating', 'range', 'number'):
            props['%s_mean' % prefix] = sub.get('mean')
        elif sub['type'] == 'thumbs':
            props['%s_up' % prefix] = sub['up']
            props['%s_down' % prefix] = sub['down']
        elif sub['type'] in ('choice', 'multichoice'):
            for code, n in sub['counts'].items():
                props['%s_%s' % (prefix, code)] = n
    return props


def layer_object_stats(layer, excluded_session_ids=None):
    """{key: {'answers', 'headline', 'sessions': [...]}} over every question
    bound to the layer — what the Responses map badges and click-to-filter use."""
    stats = {}
    for question in layer.questions.filter(input_type='layer_objects'):
        aggregates = object_aggregates(question, excluded_session_ids=excluded_session_ids)
        sessions = defaultdict(set)
        rows = (Answer.objects
                .filter(question__parent_question_id=question, layer_object__isnull=False)
                .exclude(survey_session__is_deleted=True))
        if excluded_session_ids:
            rows = rows.exclude(survey_session_id__in=excluded_session_ids)
        for key, sid in rows.values_list('layer_object__key', 'survey_session_id'):
            sessions[key].add(sid)
        for key, entry in aggregates.items():
            if not entry['answers']:
                continue
            stats[key] = {'answers': entry['answers'], 'headline': headline(entry),
                          'sessions': sorted(sessions.get(key, ()))}
    return stats


def shared_map_tallies(layer):
    """{object_key: {'up', 'down', 'comments'}} for a `question` layer — what
    respondents see next to other people's marks (spec shared-map-layer).
    Counts 👍/👎 sub-answers and non-hidden text sub-answers of every question
    bound to the layer, over clean sessions only."""
    from .public_results import EXCLUDED_VALIDATION_STATUSES
    rows = (Answer.objects
            .filter(layer_object__layer=layer,
                    question__parent_question_id__layer=layer,
                    question__parent_question_id__input_type='layer_objects',
                    question__input_type__in=('thumbs', 'text', 'text_line'),
                    hidden=False,
                    survey_session__is_deleted=False)
            .exclude(survey_session__validation_status__in=EXCLUDED_VALIDATION_STATUSES)
            .values_list('layer_object__key', 'question__input_type', 'selected_choices', 'text'))
    out = defaultdict(lambda: {'up': 0, 'down': 0, 'comments': 0})
    for key, input_type, codes, text in rows:
        if input_type == 'thumbs':
            if codes:
                out[key]['up' if int(codes[0]) == 1 else 'down'] += 1
        elif text:
            out[key]['comments'] += 1
    return dict(out)


def shared_map_comments(obj, limit=10):
    """Newest non-hidden comments on one mark, as plain strings, no author."""
    from .public_results import EXCLUDED_VALIDATION_STATUSES
    rows = (Answer.objects
            .filter(layer_object=obj, hidden=False,
                    question__input_type__in=('text', 'text_line'),
                    question__parent_question_id__input_type='layer_objects',
                    survey_session__is_deleted=False)
            .exclude(survey_session__validation_status__in=EXCLUDED_VALIDATION_STATUSES)
            .exclude(text__isnull=True).exclude(text='')
            .order_by('-id')
            .values_list('text', flat=True)[:limit])
    return list(rows)
