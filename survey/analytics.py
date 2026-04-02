import json
import statistics

from django.db.models import Count, Avg, Min, Max
from django.db.models.functions import TruncDate

from .models import (
    SurveySession, SurveySection, Answer, Question,
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


def _get_last_section(survey):
    """Return the last section in linked-list order, or None."""
    sections = list(SurveySection.objects.filter(survey_header=survey))
    if not sections:
        return None

    by_id = {s.id: s for s in sections}
    head = None
    for s in sections:
        if s.is_head:
            head = s
            break
    if head is None:
        return sections[-1]

    current = head
    visited = set()
    last = head
    while current and current.id not in visited:
        last = current
        visited.add(current.id)
        current = by_id.get(current.next_section_id)
    return last


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
        from django.db.models.functions import TruncHour
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

    def get_question_stats(self, question):
        """Return stat dict for a single question, dispatched by input_type."""
        stat = {
            'question': question,
            'section': question.survey_section,
        }

        if question.input_type in ('choice', 'multichoice', 'rating'):
            answers = Answer.objects.filter(
                question=question,
            ).exclude(selected_choices__isnull=True)

            counts = {}
            for choice in (question.choices or []):
                counts[choice['code']] = 0
            for a in answers:
                for code in (a.selected_choices or []):
                    counts[code] = counts.get(code, 0) + 1

            stat['type'] = 'choices'
            stat['choice_labels'] = [
                question.get_choice_name(c['code'])
                for c in (question.choices or [])
            ]
            stat['choice_counts'] = [
                counts.get(c['code'], 0)
                for c in (question.choices or [])
            ]
            stat['choice_codes'] = [c['code'] for c in (question.choices or [])]
            stat['choice_labels_json'] = json.dumps(stat['choice_labels'], ensure_ascii=False)
            stat['choice_counts_json'] = json.dumps(stat['choice_counts'])
            stat['choice_codes_json'] = json.dumps(stat['choice_codes'])
            stat['total_answers'] = answers.count()

        elif question.input_type in ('number', 'range'):
            qs = Answer.objects.filter(question=question, numeric__isnull=False)
            agg = qs.aggregate(
                avg=Avg('numeric'),
                min_val=Min('numeric'),
                max_val=Max('numeric'),
                count=Count('id'),
            )
            values = list(qs.values_list('numeric', flat=True))

            stat['type'] = 'number'
            stat['count'] = agg['count']
            stat['avg'] = round(agg['avg'], 1) if agg['avg'] is not None else None
            stat['min_val'] = agg['min_val']
            stat['max_val'] = agg['max_val']
            stat['median'] = round(statistics.median(values), 1) if values else None

            # Histogram bins
            if values and agg['min_val'] is not None and agg['max_val'] is not None:
                hist = _compute_histogram(values, agg['min_val'], agg['max_val'])
                stat['hist_labels_json'] = json.dumps(hist['labels'], ensure_ascii=False)
                stat['hist_counts_json'] = json.dumps(hist['counts'])
                stat['hist_bins_json'] = json.dumps(hist['bins'])

        elif question.input_type in ('text', 'text_line'):
            stat['type'] = 'text'
            stat['total_answers'] = (
                Answer.objects
                .filter(question=question, text__isnull=False)
                .exclude(text='')
                .count()
            )

        elif question.input_type in ('point', 'line', 'polygon'):
            geo_field = question.input_type
            stat['type'] = 'geo'
            stat['total_answers'] = (
                Answer.objects
                .filter(question=question)
                .exclude(**{f'{geo_field}__isnull': True})
                .count()
            )

        else:
            stat['type'] = 'other'
            stat['total_answers'] = Answer.objects.filter(question=question).count()

        return stat

    def get_all_question_stats(self):
        """Return ordered list of stat dicts for all top-level questions."""
        # Get sections in linked-list order
        sections = list(SurveySection.objects.filter(survey_header=self.survey))
        if not sections:
            return []

        by_id = {s.id: s for s in sections}
        head = next((s for s in sections if s.is_head), None)

        if head:
            ordered_sections = []
            current = head
            visited = set()
            while current and current.id not in visited:
                ordered_sections.append(current)
                visited.add(current.id)
                current = by_id.get(current.next_section_id)
            for s in sections:
                if s.id not in visited:
                    ordered_sections.append(s)
        else:
            ordered_sections = sections

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

        sessions = {}
        for row in choice_rows:
            sid = row['survey_session_id']
            if sid not in sessions:
                sessions[sid] = {
                    'sid': sid,
                    'd': str(row['survey_session__start_datetime'].date()),
                    'a': {},
                    'n': {},
                }
            qid = str(row['question_id'])
            sessions[sid]['a'][qid] = row['selected_choices'] or []

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
            sid = row['survey_session_id']
            if sid not in sessions:
                sessions[sid] = {
                    'sid': sid,
                    'd': str(row['survey_session__start_datetime'].date()),
                    'a': {},
                    'n': {},
                }
            qid = str(row['question_id'])
            sessions[sid]['n'][qid] = row['numeric']

        return list(sessions.values())
