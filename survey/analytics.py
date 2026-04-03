import json
import statistics

from django.db.models import Count, Avg, Min, Max
from django.db.models.functions import TruncHour

from .models import (
    SurveySession, SurveySection, Answer, Question, SurveyEvent,
)


def _compute_histogram(values, min_val, max_val, max_bins=15):
    """Compute histogram bins for a list of numeric values."""
    import math
    if not values:
        return {'labels': [], 'counts': []}

    if min_val == max_val:
        return {'labels': [str(min_val)], 'counts': [len(values)]}

    # Sturges' rule for bin count, capped
    n_bins = min(max_bins, max(5, int(math.ceil(math.log2(len(values)) + 1))))
    bin_width = (max_val - min_val) / n_bins

    labels = []
    bins = []
    counts = [0] * n_bins
    for i in range(n_bins):
        lo = min_val + i * bin_width
        hi = lo + bin_width
        bins.append([lo, hi])
        if bin_width >= 1:
            labels.append('{:.0f}-{:.0f}'.format(lo, hi))
        else:
            labels.append('{:.1f}-{:.1f}'.format(lo, hi))

    for v in values:
        idx = int((v - min_val) / bin_width)
        if idx >= n_bins:
            idx = n_bins - 1
        counts[idx] += 1

    return {'labels': labels, 'counts': counts, 'bins': bins}


def _get_ordered_sections(survey):
    """Return sections in linked-list traversal order."""
    sections = list(SurveySection.objects.filter(survey_header=survey))
    if not sections:
        return []
    by_id = {s.id: s for s in sections}
    head = next((s for s in sections if s.is_head), None)
    if not head:
        return sections
    ordered = []
    current = head
    visited = set()
    while current and current.id not in visited:
        ordered.append(current)
        visited.add(current.id)
        current = by_id.get(current.next_section_id)
    for s in sections:
        if s.id not in visited:
            ordered.append(s)
    return ordered


def _get_last_section(survey):
    """Return the last section in linked-list order, or None."""
    ordered = _get_ordered_sections(survey)
    return ordered[-1] if ordered else None


class SurveyAnalyticsService:
    """Read-only analytics queries for a survey. No request/view knowledge."""

    def __init__(self, survey):
        self.survey = survey

    def get_overview(self):
        """Return overview stats: total sessions, completed, completion rate."""
        total = SurveySession.objects.filter(survey=self.survey).count()

        last_section = _get_last_section(self.survey)
        if last_section and total > 0:
            completed = (
                SurveySession.objects
                .filter(survey=self.survey)
                .filter(answer__question__survey_section=last_section)
                .distinct()
                .count()
            )
        else:
            completed = 0

        rate = round(completed / total * 100) if total > 0 else 0

        return {
            'total_sessions': total,
            'completed_count': completed,
            'completion_rate': rate,
        }

    def get_daily_sessions(self):
        """Return list of {date, total, completed} dicts ordered by date."""
        hourly = self.get_hourly_sessions()
        buckets = {}
        for h in hourly:
            d = h['h'][:10]
            if d not in buckets:
                buckets[d] = {'date': d, 'total': 0, 'completed': 0}
            buckets[d]['total'] += h['t']
            buckets[d]['completed'] += h['c']
        return sorted(buckets.values(), key=lambda x: x['date'])

    def get_session_hours(self):
        """Return compact list of [sid, hour_iso, completed] for timeline filtering."""
        last_section = _get_last_section(self.survey)

        sessions = (
            SurveySession.objects
            .filter(survey=self.survey)
            .values_list('id', 'start_datetime')
            .order_by('start_datetime')
        )

        completed_ids = set()
        if last_section:
            completed_ids = set(
                SurveySession.objects
                .filter(
                    survey=self.survey,
                    answer__question__survey_section=last_section,
                )
                .distinct()
                .values_list('id', flat=True)
            )

        result = []
        for sid, dt in sessions:
            if dt:
                result.append([sid, dt.strftime('%Y-%m-%dT%H'), sid in completed_ids])
        return result

    def get_hourly_sessions(self):
        """Return list of {h, t, c} dicts — hour bucket, total, completed."""
        last_section = _get_last_section(self.survey)

        hourly = (
            SurveySession.objects
            .filter(survey=self.survey)
            .annotate(hour=TruncHour('start_datetime'))
            .values('hour')
            .annotate(total=Count('id'))
            .order_by('hour')
        )

        completed_by_hour = {}
        if last_section:
            completed_hourly = (
                SurveySession.objects
                .filter(
                    survey=self.survey,
                    answer__question__survey_section=last_section,
                )
                .annotate(hour=TruncHour('start_datetime'))
                .values('hour')
                .annotate(completed=Count('id', distinct=True))
                .order_by('hour')
            )
            completed_by_hour = {
                r['hour'].isoformat(): r['completed'] for r in completed_hourly
            }

        result = []
        for row in hourly:
            h_iso = row['hour'].isoformat()
            result.append({
                'h': h_iso,
                't': row['total'],
                'c': completed_by_hour.get(h_iso, 0),
            })
        return result

    def get_geo_feature_collection(self):
        """Return GeoJSON FeatureCollection with all geo answers."""
        geo_answers = (
            Answer.objects
            .filter(
                question__survey_section__survey_header=self.survey,
                question__input_type__in=['point', 'line', 'polygon'],
            )
            .select_related('question')
        )

        features = []
        for a in geo_answers:
            geom = a.point or a.line or a.polygon
            if geom is None:
                continue
            features.append({
                'type': 'Feature',
                'geometry': json.loads(geom.geojson),
                'properties': {
                    'question': a.question.name,
                    'type': a.question.input_type,
                    'session_id': a.survey_session_id,
                },
            })

        return {
            'type': 'FeatureCollection',
            'features': features,
        }

    def _stats_choices(self, question):
        """Compute stats for choice/multichoice/rating questions."""
        answers = Answer.objects.filter(
            question=question,
        ).exclude(selected_choices__isnull=True)

        counts = {}
        for choice in (question.choices or []):
            counts[choice['code']] = 0
        for a in answers:
            for code in (a.selected_choices or []):
                counts[code] = counts.get(code, 0) + 1

        choices = question.choices or []
        choice_labels = [question.get_choice_name(c['code']) for c in choices]
        choice_counts = [counts.get(c['code'], 0) for c in choices]
        choice_codes = [c['code'] for c in choices]
        return {
            'type': 'choices',
            'choice_labels': choice_labels,
            'choice_counts': choice_counts,
            'choice_codes': choice_codes,
            'choice_labels_json': json.dumps(choice_labels, ensure_ascii=False),
            'choice_counts_json': json.dumps(choice_counts),
            'choice_codes_json': json.dumps(choice_codes),
            'total_answers': answers.count(),
        }

    def _stats_number(self, question):
        """Compute stats for number/range questions."""
        qs = Answer.objects.filter(question=question, numeric__isnull=False)
        agg = qs.aggregate(
            avg=Avg('numeric'),
            min_val=Min('numeric'),
            max_val=Max('numeric'),
            count=Count('id'),
        )
        values = list(qs.values_list('numeric', flat=True))

        result = {
            'type': 'number',
            'count': agg['count'],
            'avg': round(agg['avg'], 1) if agg['avg'] is not None else None,
            'min_val': agg['min_val'],
            'max_val': agg['max_val'],
            'median': round(statistics.median(values), 1) if values else None,
        }
        if values and agg['min_val'] is not None and agg['max_val'] is not None:
            hist = _compute_histogram(values, agg['min_val'], agg['max_val'])
            result['hist_labels_json'] = json.dumps(hist['labels'], ensure_ascii=False)
            result['hist_counts_json'] = json.dumps(hist['counts'])
            result['hist_bins_json'] = json.dumps(hist['bins'])
        return result

    def _stats_text(self, question):
        """Compute stats for text/text_line questions."""
        return {
            'type': 'text',
            'total_answers': (
                Answer.objects
                .filter(question=question, text__isnull=False)
                .exclude(text='')
                .count()
            ),
        }

    def _stats_geo(self, question):
        """Compute stats for point/line/polygon questions."""
        geo_field = question.input_type
        return {
            'type': 'geo',
            'total_answers': (
                Answer.objects
                .filter(question=question)
                .exclude(**{f'{geo_field}__isnull': True})
                .count()
            ),
        }

    def _stats_other(self, question):
        """Compute stats for unknown question types."""
        return {
            'type': 'other',
            'total_answers': Answer.objects.filter(question=question).count(),
        }

    _STAT_DISPATCH = {
        'choice': _stats_choices,
        'multichoice': _stats_choices,
        'rating': _stats_choices,
        'number': _stats_number,
        'range': _stats_number,
        'text': _stats_text,
        'text_line': _stats_text,
        'point': _stats_geo,
        'line': _stats_geo,
        'polygon': _stats_geo,
    }

    def get_question_stats(self, question):
        """Return stat dict for a single question, dispatched by input_type."""
        handler = self._STAT_DISPATCH.get(question.input_type)
        stat = {
            'question': question,
            'section': question.survey_section,
        }
        if handler is not None:
            stat.update(handler(self, question))
        else:
            stat.update(self._stats_other(question))
        return stat

    def get_all_question_stats(self):
        """Return ordered list of stat dicts for all top-level questions."""
        ordered_sections = _get_ordered_sections(self.survey)
        if not ordered_sections:
            return []

        section_order = {s.id: i for i, s in enumerate(ordered_sections)}

        questions = (
            Question.objects
            .filter(
                survey_section__survey_header=self.survey,
                parent_question_id__isnull=True,
            )
            .select_related('survey_section')
            .order_by('survey_section__id', 'order_number')
        )

        # Sort by section linked-list order, then question order
        questions = sorted(questions, key=lambda q: (
            section_order.get(q.survey_section_id, 999),
            q.order_number,
        ))

        return [self.get_question_stats(q) for q in questions]

    def get_text_answers(self, question, page=1, page_size=20, session_ids=None):
        """Return paginated text answers for a question."""
        page_size = min(max(page_size, 5), 100)

        qs = (
            Answer.objects
            .filter(question=question, text__isnull=False)
            .exclude(text='')
            .select_related('survey_session')
            .order_by('-survey_session__start_datetime')
        )
        if session_ids is not None:
            qs = qs.filter(survey_session_id__in=session_ids)
        total = qs.count()
        total_pages = max(1, (total + page_size - 1) // page_size)
        page = min(max(page, 1), total_pages)
        offset = (page - 1) * page_size
        answers = list(qs[offset:offset + page_size])

        return {
            'answers': answers,
            'page': page,
            'total_pages': total_pages,
            'total': total,
            'page_size': page_size,
        }

    def get_answer_matrix(self):
        """Return compact per-session choice + numeric data for client-side cross-filtering."""
        # Choice answers
        choice_rows = (
            Answer.objects
            .filter(
                question__survey_section__survey_header=self.survey,
                question__input_type__in=['choice', 'multichoice', 'rating'],
            )
            .exclude(selected_choices__isnull=True)
            .values(
                'survey_session_id',
                'survey_session__start_datetime',
                'question_id',
                'selected_choices',
            )
            .order_by('survey_session_id')
        )

        def ensure_session(sid, dt):
            if sid not in sessions:
                sessions[sid] = {
                    'sid': sid, 'd': str(dt.date()), 'a': {}, 'n': {},
                }
            return sessions[sid]

        sessions = {}
        for row in choice_rows:
            entry = ensure_session(row['survey_session_id'], row['survey_session__start_datetime'])
            entry['a'][str(row['question_id'])] = row['selected_choices'] or []

        # Numeric answers
        numeric_rows = (
            Answer.objects
            .filter(
                question__survey_section__survey_header=self.survey,
                question__input_type__in=['number', 'range'],
                numeric__isnull=False,
            )
            .values(
                'survey_session_id',
                'survey_session__start_datetime',
                'question_id',
                'numeric',
            )
            .order_by('survey_session_id')
        )

        for row in numeric_rows:
            entry = ensure_session(row['survey_session_id'], row['survey_session__start_datetime'])
            entry['n'][str(row['question_id'])] = row['numeric']

        return list(sessions.values())

    def format_session_answers(self, session):
        """Format all answers for a session into display rows and geo features.

        Returns (answer_rows, geo_features) where answer_rows is a list of dicts
        and geo_features is a list of GeoJSON Feature dicts.
        """
        answers = (
            Answer.objects
            .filter(survey_session=session, parent_answer_id__isnull=True)
            .select_related('question', 'question__survey_section')
            .order_by('question__survey_section__id', 'question__order_number')
        )

        answer_rows = []
        geo_features = []
        for a in answers:
            q = a.question
            if q.input_type in ('choice', 'multichoice', 'rating'):
                value = ', '.join(a.get_selected_choice_names()) or '\u2014'
            elif q.input_type in ('number', 'range'):
                value = str(a.numeric) if a.numeric is not None else '\u2014'
            elif q.input_type in ('text', 'text_line', 'datetime'):
                value = a.text or '\u2014'
            elif q.input_type in ('point', 'line', 'polygon'):
                geom = a.point or a.line or a.polygon
                if geom:
                    geo_features.append({
                        'type': 'Feature',
                        'geometry': json.loads(geom.geojson),
                        'properties': {'question': q.name, 'type': q.input_type},
                    })
                    value = q.input_type + ' feature'
                else:
                    value = '\u2014'
            else:
                value = '\u2014'

            answer_rows.append({
                'question_name': q.name,
                'section_name': q.survey_section.title or q.survey_section.name,
                'input_type': q.input_type,
                'value': value,
            })

        return answer_rows, geo_features


class PerformanceAnalyticsService:
    """Read-only performance/funnel analytics from SurveyEvent data."""

    def __init__(self, survey):
        self.survey = survey

    def _events_qs(self):
        return SurveyEvent.objects.filter(session__survey=self.survey)

    def get_event_summary(self):
        """Return top-level counts: session_starts, completions, median_load_ms."""
        qs = self._events_qs()
        starts = qs.filter(event_type='session_start').count()
        completions = qs.filter(event_type='survey_complete').count()

        load_values = list(
            qs.filter(event_type='page_load')
            .values_list('metadata', flat=True)
        )
        load_ms_values = [
            m.get('load_ms') for m in load_values
            if isinstance(m, dict) and isinstance(m.get('load_ms'), (int, float))
            and 0 < m.get('load_ms', 0) <= 120_000
        ]
        median_ms = round(statistics.median(load_ms_values)) if load_ms_values else None

        return {
            'session_starts': starts,
            'completions': completions,
            'completion_rate': round(completions / starts * 100) if starts else 0,
            'page_load_count': len(load_ms_values),
            'median_load_ms': median_ms,
        }

    def get_funnel(self):
        """Return per-section views/submits/drop_rate in linked-list order."""
        qs = self._events_qs()

        # Fetch all section_view and section_submit events
        view_events = list(
            qs.filter(event_type='section_view')
            .values_list('metadata', flat=True)
        )
        submit_events = list(
            qs.filter(event_type='section_submit')
            .values_list('metadata', flat=True)
        )

        # Count by section_name
        views_map = {}
        for m in view_events:
            name = (m or {}).get('section_name', '')
            if name:
                views_map[name] = views_map.get(name, 0) + 1

        submit_map = {}
        for m in submit_events:
            name = (m or {}).get('section_name', '')
            if name:
                submit_map[name] = submit_map.get(name, 0) + 1

        # Order by linked-list section order
        sections = _get_ordered_sections(self.survey)
        result = []
        for s in sections:
            v = views_map.get(s.name, 0)
            sub = submit_map.get(s.name, 0)
            drop_rate = round((v - sub) / v * 100) if v > 0 else 0
            result.append({
                'section_name': s.name,
                'section_title': s.title or s.name,
                'views': v,
                'submits': sub,
                'drop_rate': drop_rate,
            })
        return result

    def _session_start_metadata(self):
        """Fetch all session_start metadata dicts (cached per instance)."""
        if not hasattr(self, '_ss_meta_cache'):
            self._ss_meta_cache = list(
                self._events_qs()
                .filter(event_type='session_start')
                .values_list('metadata', flat=True)
            )
        return self._ss_meta_cache

    def get_referrer_breakdown(self):
        """Return list of {referrer_type, count} sorted descending."""
        counts = {}
        for m in self._session_start_metadata():
            ref_type = (m or {}).get('referrer_type', 'direct')
            counts[ref_type] = counts.get(ref_type, 0) + 1

        return sorted(
            [{'referrer_type': k, 'count': v} for k, v in counts.items()],
            key=lambda x: -x['count'],
        )

    def get_device_breakdown(self):
        """Return {device_types, os, browsers} — each a list of {name, count} sorted descending."""
        device_counts = {}
        os_counts = {}
        browser_counts = {}

        for m in self._session_start_metadata():
            m = m or {}
            dt = m.get('device_type', 'unknown')
            device_counts[dt] = device_counts.get(dt, 0) + 1
            os_name = m.get('os', 'unknown')
            os_counts[os_name] = os_counts.get(os_name, 0) + 1
            br = m.get('browser', 'unknown')
            browser_counts[br] = browser_counts.get(br, 0) + 1

        def _sorted_list(d):
            return sorted(
                [{'name': k, 'count': v} for k, v in d.items()],
                key=lambda x: -x['count'],
            )

        return {
            'device_types': _sorted_list(device_counts),
            'os': _sorted_list(os_counts),
            'browsers': _sorted_list(browser_counts),
        }

    def get_completion_by_referrer(self):
        """Return started/completed/rate per referrer_type."""
        # Get completed session IDs
        completed_sids = set(
            self._events_qs()
            .filter(event_type='survey_complete')
            .values_list('session_id', flat=True)
        )

        # Get all session_start events with referrer_type
        starts = list(
            self._events_qs()
            .filter(event_type='session_start')
            .values('session_id', 'metadata')
        )

        buckets = {}
        for row in starts:
            ref = (row['metadata'] or {}).get('referrer_type', 'direct')
            if ref not in buckets:
                buckets[ref] = {'started': 0, 'completed': 0}
            buckets[ref]['started'] += 1
            if row['session_id'] in completed_sids:
                buckets[ref]['completed'] += 1

        return sorted(
            [
                {
                    'referrer_type': ref,
                    'started': data['started'],
                    'completed': data['completed'],
                    'rate': round(data['completed'] / data['started'] * 100) if data['started'] else 0,
                }
                for ref, data in buckets.items()
            ],
            key=lambda x: -x['started'],
        )

    def get_page_load_stats(self):
        """Return avg page load per section."""
        events = list(
            self._events_qs()
            .filter(event_type='page_load')
            .values_list('metadata', flat=True)
        )

        by_section = {}
        for m in events:
            if not isinstance(m, dict):
                continue
            name = m.get('section_name', '')
            ms = m.get('load_ms')
            if name and isinstance(ms, (int, float)) and 0 < ms <= 120_000:
                by_section.setdefault(name, []).append(ms)

        sections = _get_ordered_sections(self.survey)
        section_order = {s.name: i for i, s in enumerate(sections)}

        result = []
        for name, values in sorted(by_section.items(), key=lambda x: section_order.get(x[0], 999)):
            result.append({
                'section_name': name,
                'avg_ms': round(sum(values) / len(values)),
                'median_ms': round(statistics.median(values)),
                'count': len(values),
            })
        return result
