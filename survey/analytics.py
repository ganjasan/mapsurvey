import json
import statistics

from django.db.models import Count, Avg, Min, Max
from django.db.models.functions import TruncHour

from django.utils import timezone

from .models import (
    SurveyHeader, SurveySession, SurveySection, Answer, Question, SurveyEvent,
    VALIDATION_STATUS_CHOICES,
)
from .versioning import canonical_of, family_ids, lineage_map


def resolve_version_scope(survey, version):
    """Resolve a version filter value to a set of SurveyHeader ids.

    version: 'all' (default) → the whole family; 'vN' / 'N' → that single
    version's header. Unknown values fall back to 'all'.
    """
    canonical = canonical_of(survey)
    if version and version != 'all':
        try:
            num = int(str(version).lstrip('v'))
        except (TypeError, ValueError):
            num = None
        if num is not None:
            if num == canonical.version_number:
                return {canonical.id}
            match = SurveyHeader.objects.filter(
                canonical_survey=canonical, version_number=num,
            ).values_list('id', flat=True).first()
            if match is not None:
                return {match}
    return family_ids(canonical)


def version_choices(survey):
    """Return [{'value': 'all'|'vN', 'label': ...}] for the version filter UI.

    Returns an empty list for single-version surveys (no filter to show).
    """
    canonical = canonical_of(survey)
    versions = list(
        SurveyHeader.objects
        .filter(canonical_survey=canonical)
        .order_by('-version_number')
        .values_list('version_number', flat=True)
    )
    if not versions:
        return []
    choices = [{'value': 'all', 'label': 'All versions'}]
    for num in [canonical.version_number] + versions:
        choices.append({'value': f'v{num}', 'label': f'v{num}'})
    return choices


def _compute_histogram(values, min_val, max_val, max_bins=15):
    """Compute histogram bins for a list of numeric values."""
    import math
    if not values:
        return {'labels': [], 'counts': [], 'bins': []}

    if min_val == max_val:
        return {
            'labels': [str(min_val)],
            'counts': [len(values)],
            'bins': [[min_val, min_val]],
        }

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
    """Read-only analytics queries for a survey. No request/view knowledge.

    Version scope: publish_draft() moves old sessions (and their question
    objects) onto an archived header, so all reads run over a *scope* of
    version headers — the whole family by default, or a single version when
    the creator filters. Questions aggregate by lineage (code, input_type).
    """

    def __init__(self, survey, include_deleted=False, version='all'):
        self.survey = survey
        self.version = version
        self.scope_ids = resolve_version_scope(survey, version)
        if include_deleted:
            self.base_qs = SurveySession.objects.filter(survey_id__in=self.scope_ids)
        else:
            self.base_qs = SurveySession.objects.active().filter(survey_id__in=self.scope_ids)

    # ── Version-scope helpers ──────────────────────────────────────

    @property
    def _scope_surveys(self):
        """SurveyHeaders in scope (canonical first)."""
        if not hasattr(self, '_scope_surveys_cache'):
            headers = list(SurveyHeader.objects.filter(id__in=self.scope_ids))
            headers.sort(key=lambda h: (not h.is_canonical, -h.version_number))
            self._scope_surveys_cache = headers
        return self._scope_surveys_cache

    @property
    def _lineages(self):
        """Family lineage map (built once per instance)."""
        if not hasattr(self, '_lineages_cache'):
            self._lineages_cache = lineage_map(self.survey)
        return self._lineages_cache

    def _lineage_ids(self, question):
        """All question ids aggregating with `question`, limited to scope.

        Falls back to [question.id] for questions outside any lineage
        (defensive — e.g. sub-questions passed directly).
        """
        entry = self._lineages.get((question.code, question.input_type))
        if not entry:
            return [question.id]
        # Scope-limited: an archived lineage under a single-version filter
        # may legitimately resolve to no questions (→ zero answers).
        return [
            q.id for q in entry['questions']
            if q.survey_section.survey_header_id in self.scope_ids
        ]

    def _rep_question_by_qid(self):
        """Map every scoped question id → its lineage representative Question.

        The representative is the canonical version's question when the
        lineage is current, else the newest archived question — the object
        the stats/table/charts/layers key on.
        """
        if not hasattr(self, '_rep_by_qid_cache'):
            mapping = {}
            for entry in self._lineages.values():
                rep = entry['current'] or entry['questions'][0]
                for q in entry['questions']:
                    if q.survey_section.survey_header_id in self.scope_ids:
                        mapping[q.id] = rep
            self._rep_by_qid_cache = mapping
        return self._rep_by_qid_cache

    def _last_section_ids(self):
        """Ids of every scoped version's last section (completion targets)."""
        ids = set()
        for header in self._scope_surveys:
            last = _get_last_section(header)
            if last:
                ids.add(last.id)
        return ids

    def _completed_filter_qs(self, qs):
        """Sessions from qs that answered their version's last section."""
        last_ids = self._last_section_ids()
        if not last_ids:
            return qs.none()
        return qs.filter(answer__question__survey_section_id__in=last_ids).distinct()

    def get_overview(self):
        """Return overview stats: total sessions, completed, completion rate."""
        total = self.base_qs.count()

        if total > 0:
            completed = self._completed_filter_qs(self.base_qs).count()
        else:
            completed = 0

        rate = round(completed / total * 100) if total > 0 else 0

        # Count flagged sessions
        flagged_count = 0
        if total > 0:
            all_pks = list(self.base_qs.values_list('id', flat=True))
            issues = self.compute_session_issues(all_pks)
            flagged_count = sum(1 for v in issues.values() if v)

        return {
            'total_sessions': total,
            'completed_count': completed,
            'completion_rate': rate,
            'flagged_count': flagged_count,
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
        sessions = (
            self.base_qs
            .values_list('id', 'start_datetime')
            .order_by('start_datetime')
        )

        completed_ids = set(
            self._completed_filter_qs(self.base_qs).values_list('id', flat=True)
        )

        result = []
        for sid, dt in sessions:
            if dt:
                result.append([sid, dt.strftime('%Y-%m-%dT%H'), sid in completed_ids])
        return result

    def get_hourly_sessions(self):
        """Return list of {h, t, c} dicts — hour bucket, total, completed."""
        hourly = (
            self.base_qs
            .annotate(hour=TruncHour('start_datetime'))
            .values('hour')
            .annotate(total=Count('id'))
            .order_by('hour')
        )

        completed_by_hour = {}
        last_ids = self._last_section_ids()
        if last_ids:
            completed_hourly = (
                self.base_qs
                .filter(answer__question__survey_section_id__in=last_ids)
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
        """Return GeoJSON FeatureCollection with all geo answers in scope."""
        geo_answers = (
            Answer.objects
            .filter(
                question__survey_section__survey_header_id__in=self.scope_ids,
                question__input_type__in=['point', 'line', 'polygon'],
                survey_session__is_deleted=False,
            )
            .select_related('question')
        )

        # Key features on the lineage representative so one logical question
        # renders as one layer even when its objects differ across versions.
        rep_by_qid = self._rep_question_by_qid()

        features = []
        for a in geo_answers:
            geom = a.point or a.line or a.polygon
            if geom is None:
                continue
            rep = rep_by_qid.get(a.question_id, a.question)
            features.append({
                'type': 'Feature',
                'geometry': json.loads(geom.geojson),
                'properties': {
                    'question': rep.name,
                    'type': rep.input_type,
                    'session_id': a.survey_session_id,
                },
            })

        return {
            'type': 'FeatureCollection',
            'features': features,
        }

    def _historic_choice_name(self, question, code):
        """Resolve a removed code's label from older lineage questions."""
        entry = self._lineages.get((question.code, question.input_type))
        for q in (entry['questions'] if entry else []):
            for c in (q.choices or []):
                if c['code'] == code:
                    return q.get_choice_name(code)
        return str(code)

    def _stats_choices(self, question):
        """Compute stats for choice/multichoice/rating questions.

        Aggregates over the whole lineage. Codes answered historically but
        absent from the current choice set are appended as flagged
        "no longer offered" buckets — never silently merged or dropped.
        """
        answers = Answer.objects.filter(
            question_id__in=self._lineage_ids(question),
            survey_session__is_deleted=False,
        ).exclude(selected_choices__isnull=True)

        counts = {}
        for choice in (question.choices or []):
            counts[choice['code']] = 0
        for a in answers:
            for code in (a.selected_choices or []):
                counts[code] = counts.get(code, 0) + 1

        choices = question.choices or []
        current_codes = [c['code'] for c in choices]
        choice_labels = [question.get_choice_name(c['code']) for c in choices]
        choice_counts = [counts.get(c['code'], 0) for c in choices]
        choice_codes = list(current_codes)

        # Historically answered codes no longer offered in the current version
        removed = sorted(set(counts) - set(current_codes), key=str)
        for code in removed:
            choice_labels.append(
                f'{self._historic_choice_name(question, code)} (no longer offered)'
            )
            choice_counts.append(counts[code])
            choice_codes.append(code)

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
        """Compute stats for number/range questions (lineage-wide)."""
        qs = Answer.objects.filter(
            question_id__in=self._lineage_ids(question),
            numeric__isnull=False, survey_session__is_deleted=False,
        )
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
        """Compute stats for text/text_line questions (lineage-wide)."""
        return {
            'type': 'text',
            'total_answers': (
                Answer.objects
                .filter(question_id__in=self._lineage_ids(question),
                        text__isnull=False, survey_session__is_deleted=False)
                .exclude(text='')
                .count()
            ),
        }

    def _stats_geo(self, question):
        """Compute stats for point/line/polygon questions (lineage-wide)."""
        geo_field = question.input_type
        return {
            'type': 'geo',
            'total_answers': (
                Answer.objects
                .filter(question_id__in=self._lineage_ids(question),
                        survey_session__is_deleted=False)
                .exclude(**{f'{geo_field}__isnull': True})
                .count()
            ),
        }

    def _stats_other(self, question):
        """Compute stats for unknown question types (lineage-wide)."""
        return {
            'type': 'other',
            'total_answers': Answer.objects.filter(
                question_id__in=self._lineage_ids(question),
                survey_session__is_deleted=False,
            ).count(),
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
        entry = self._lineages.get((question.code, question.input_type))
        stat = {
            'question': question,
            'section': question.survey_section,
            'archived': bool(entry) and entry['current'] is None,
            'versions': entry['versions'] if entry else '',
        }
        if handler is not None:
            stat.update(handler(self, question))
        else:
            stat.update(self._stats_other(question))
        return stat

    def _stats_language(self):
        """Build a choices-style stat for the session language (multilingual surveys only)."""
        langs = list(
            SurveySession.objects.filter(survey_id__in=self.scope_ids, is_deleted=False)
            .values_list('language', flat=True)
        )
        counts = {}
        for lang in langs:
            lang = lang or '—'
            counts[lang] = counts.get(lang, 0) + 1

        labels = sorted(counts.keys())
        codes = labels  # use lang code as "choice code"

        # Build a lightweight duck-typed object for template compatibility
        class _LangQuestion:
            id = '_language'
            name = 'Language'
            input_type = 'choice'
        class _LangSection:
            title = 'Survey'
            name = 'survey'

        return {
            'question': _LangQuestion(),
            'section': _LangSection(),
            'type': 'choices',
            'choice_labels': labels,
            'choice_counts': [counts[l] for l in labels],
            'choice_codes': codes,
            'choice_labels_json': json.dumps(labels, ensure_ascii=False),
            'choice_counts_json': json.dumps([counts[l] for l in labels]),
            'choice_codes_json': json.dumps(codes),
            'total_answers': len(langs),
        }

    def get_all_question_stats(self):
        """Return ordered list of stat dicts for all top-level lineages.

        Current-structure questions first (canonical section order), then
        archived lineages (questions with answers that no longer exist in
        the canonical version) so history is visible, never hidden.
        """
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

        stats = [
            self.get_question_stats(q) for q in questions
            if q.input_type not in ('point', 'line', 'polygon')
        ]

        # Archived lineages: represented by their newest question object.
        # Only shown when they actually have answers in scope (_lineage_ids
        # is scope-limited, so an out-of-scope lineage yields 0 answers).
        for entry in self._lineages.values():
            if entry['current'] is not None:
                continue
            rep = entry['questions'][0]
            if rep.parent_question_id is not None:
                continue
            if rep.input_type in ('point', 'line', 'polygon', 'html', 'image'):
                continue
            stat = self.get_question_stats(rep)
            if stat.get('total_answers'):
                stats.append(stat)

        # Add language chart for multilingual surveys
        if self.survey.is_multilingual():
            stats.insert(0, self._stats_language())

        return stats

    def get_text_answers(self, question, page=1, page_size=20, session_ids=None):
        """Return paginated text answers for a question."""
        page_size = min(max(page_size, 5), 100)

        qs = (
            Answer.objects
            .filter(question_id__in=self._lineage_ids(question),
                    text__isnull=False, survey_session__is_deleted=False)
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
        """Return compact per-session choice + numeric data for client-side cross-filtering.

        Question keys are lineage-representative ids so charts (which key on
        the representative) cross-filter across versions transparently.
        """
        rep_by_qid = self._rep_question_by_qid()

        def rep_key(qid):
            rep = rep_by_qid.get(qid)
            return str(rep.id if rep else qid)

        # Choice answers
        choice_rows = (
            Answer.objects
            .filter(
                question__survey_section__survey_header_id__in=self.scope_ids,
                question__input_type__in=['choice', 'multichoice', 'rating'],
                survey_session__is_deleted=False,
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
            entry['a'][rep_key(row['question_id'])] = row['selected_choices'] or []

        # Numeric answers
        numeric_rows = (
            Answer.objects
            .filter(
                question__survey_section__survey_header_id__in=self.scope_ids,
                question__input_type__in=['number', 'range'],
                numeric__isnull=False,
                survey_session__is_deleted=False,
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
            entry['n'][rep_key(row['question_id'])] = row['numeric']

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
                'question_id': q.id,
                'question_name': q.name,
                'section_name': q.survey_section.title or q.survey_section.name,
                'input_type': q.input_type,
                'value': value,
                'editable': q.input_type in ('text', 'text_line', 'number', 'range', 'choice', 'multichoice', 'rating', 'datetime'),
            })

        return answer_rows, geo_features

    # ── Auto-validation ────────────────────────────────────────────

    def compute_session_issues(self, session_pks):
        """Compute validation issues for sessions. Returns {sid: [issue_list]}.

        Rules:
        - 'empty': session has 0 top-level answers
        - 'incomplete': session has no answer in the last section
        - 'missing_required': session visited a section but skipped a required question in it
        """
        if not session_pks:
            return {}

        issues = {sid: [] for sid in session_pks}

        # Rule 1: Empty sessions (0 top-level answers)
        answer_counts = dict(
            Answer.objects
            .filter(survey_session_id__in=session_pks, parent_answer_id__isnull=True)
            .values('survey_session_id')
            .annotate(cnt=Count('id'))
            .values_list('survey_session_id', 'cnt')
        )
        empty_sids = {sid for sid in session_pks if answer_counts.get(sid, 0) == 0}
        for sid in empty_sids:
            issues[sid].append('empty')

        # Rule 2: Incomplete sessions (no answer in their version's last section)
        last_ids = self._last_section_ids()
        if last_ids:
            completed_sids = set(
                Answer.objects
                .filter(
                    survey_session_id__in=session_pks,
                    parent_answer_id__isnull=True,
                    question__survey_section_id__in=last_ids,
                )
                .values_list('survey_session_id', flat=True)
                .distinct()
            )
            for sid in session_pks:
                if sid not in completed_sids and sid not in empty_sids:
                    issues[sid].append('incomplete')

        # Rule 3: Missing required questions in visited sections.
        # Spanning the scope keeps this version-correct automatically:
        # sections are version-specific objects, so a v2 session's visited
        # sections only ever match v2's required sets.
        required_questions = list(
            Question.objects
            .filter(
                survey_section__survey_header_id__in=self.scope_ids,
                required=True,
                parent_question_id__isnull=True,
            )
            .values_list('id', 'survey_section_id')
        )
        if required_questions:
            # Build {section_id: set(required_question_ids)}
            required_by_section = {}
            for qid, sec_id in required_questions:
                required_by_section.setdefault(sec_id, set()).add(qid)

            # Get all (session_id, question_id) pairs for answered questions
            answered_pairs = set(
                Answer.objects
                .filter(
                    survey_session_id__in=session_pks,
                    parent_answer_id__isnull=True,
                    question__survey_section__survey_header_id__in=self.scope_ids,
                )
                .values_list('survey_session_id', 'question_id')
            )

            # Build {session_id: set(answered_question_ids)} and visited sections
            answered_by_session = {}
            visited_sections_by_session = {}
            for sid, qid in answered_pairs:
                answered_by_session.setdefault(sid, set()).add(qid)

            # Determine visited sections from answered questions
            question_to_section = {qid: sec_id for qid, sec_id in
                Question.objects
                .filter(survey_section__survey_header_id__in=self.scope_ids, parent_question_id__isnull=True)
                .values_list('id', 'survey_section_id')
            }
            for sid, qid in answered_pairs:
                sec_id = question_to_section.get(qid)
                if sec_id:
                    visited_sections_by_session.setdefault(sid, set()).add(sec_id)

            # Check each session
            for sid in session_pks:
                if sid in empty_sids:
                    continue
                visited = visited_sections_by_session.get(sid, set())
                answered = answered_by_session.get(sid, set())
                for sec_id in visited:
                    required_qs = required_by_section.get(sec_id, set())
                    if not required_qs.issubset(answered):
                        issues[sid].append('missing_required')
                        break

        # Rule 4: Fast completion (session_start to survey_complete < 30 seconds)
        start_events = dict(
            SurveyEvent.objects
            .filter(session_id__in=session_pks, event_type='session_start')
            .values_list('session_id', 'created_at')
        )
        complete_events = dict(
            SurveyEvent.objects
            .filter(session_id__in=session_pks, event_type='survey_complete')
            .values_list('session_id', 'created_at')
        )
        for sid in session_pks:
            start_at = start_events.get(sid)
            complete_at = complete_events.get(sid)
            if start_at and complete_at:
                duration = (complete_at - start_at).total_seconds()
                fast_threshold = (self.survey.validation_settings or {}).get('fast_threshold_seconds', 30)
                if duration < fast_threshold:
                    issues[sid].append('fast')

        # Rule 5: Duplicate sessions (same user_agent within 1 hour)
        ua_events = list(
            SurveyEvent.objects
            .filter(session_id__in=session_pks, event_type='session_start')
            .exclude(metadata__user_agent='')
            .values_list('session_id', 'created_at', 'metadata')
        )
        # Group by user_agent
        ua_groups = {}
        for sid, created_at, metadata in ua_events:
            ua = (metadata or {}).get('user_agent', '')
            if ua:
                ua_groups.setdefault(ua, []).append((sid, created_at))
        # Flag sessions where same UA appears within 1 hour
        dup_window = (self.survey.validation_settings or {}).get('duplicate_window_hours', 1) * 3600
        for ua, entries in ua_groups.items():
            if len(entries) < 2:
                continue
            entries.sort(key=lambda x: x[1])
            for i in range(1, len(entries)):
                prev_sid, prev_t = entries[i - 1]
                cur_sid, cur_t = entries[i]
                if (cur_t - prev_t).total_seconds() < dup_window:
                    if 'duplicate' not in issues.get(cur_sid, []):
                        issues[cur_sid].append('duplicate')
                    if 'duplicate' not in issues.get(prev_sid, []):
                        issues[prev_sid].append('duplicate')

        return issues

    def compute_answer_lints(self, session_pks, answers_iter, questions):
        """Compute per-answer lints. Returns {sid: {str(qid): [lint_types]}}.

        Errors (red):
        - 'self_intersection': polygon with invalid geometry
        - 'empty_required': required question with no answer in visited section

        Warnings (yellow):
        - 'numeric_outlier': numeric value > mean ± 3σ
        - 'short_text': text answer < 3 chars
        - 'area_outlier': polygon area > median × 10 or < median / 10
        """
        lint_map = {}  # {session_id: {str(question_id): [lints]}}

        # Collect data for warnings during answer iteration
        numeric_values = {}  # {question_id: [(session_id, value)]}
        text_answers = []    # [(session_id, question_id, text)]
        polygon_areas = {}   # {question_id: [(session_id, area)]}

        # Rule 1: Self-intersection + collect data
        for a in answers_iter:
            q = a.question
            if q.input_type == 'polygon' and a.polygon:
                try:
                    if not a.polygon.valid:
                        lint_map.setdefault(a.survey_session_id, {})\
                            .setdefault(str(a.question_id), []).append('self_intersection')
                    area = a.polygon.area
                    if area > 0:
                        polygon_areas.setdefault(q.id, []).append((a.survey_session_id, area))
                except Exception:
                    pass
            if q.input_type in ('number', 'range') and a.numeric is not None:
                numeric_values.setdefault(q.id, []).append((a.survey_session_id, float(a.numeric)))
            if q.input_type in ('text', 'text_line') and a.text:
                text_answers.append((a.survey_session_id, q.id, a.text))

        # Rule 2: Empty required — required questions without answer
        required_questions = [q for q in questions if q.required]
        if required_questions and session_pks:
            required_by_section = {}
            for q in required_questions:
                required_by_section.setdefault(q.survey_section_id, set()).add(q.id)

            # Get (session_id, question_id) for all answered questions
            answered_pairs = set(
                Answer.objects
                .filter(
                    survey_session_id__in=session_pks,
                    parent_answer_id__isnull=True,
                    question__survey_section__survey_header_id__in=self.scope_ids,
                )
                .values_list('survey_session_id', 'question_id')
            )

            # Determine visited sections per session
            question_to_section = {q.id: q.survey_section_id for q in questions}
            for q in required_questions:
                question_to_section[q.id] = q.survey_section_id

            visited_sections = {}  # {sid: set(section_ids)}
            for sid, qid in answered_pairs:
                sec_id = question_to_section.get(qid)
                if sec_id:
                    visited_sections.setdefault(sid, set()).add(sec_id)

            answered_by_session = {}
            for sid, qid in answered_pairs:
                answered_by_session.setdefault(sid, set()).add(qid)

            # Flag missing required answers
            for sid in session_pks:
                visited = visited_sections.get(sid, set())
                answered = answered_by_session.get(sid, set())
                for sec_id in visited:
                    for req_qid in required_by_section.get(sec_id, set()):
                        if req_qid not in answered:
                            lint_map.setdefault(sid, {})\
                                .setdefault(str(req_qid), []).append('empty_required')

        # Build question settings lookup
        q_settings = {q.id: (q.validation_settings or {}) for q in questions}

        # Warning: numeric outlier (> mean ± Nσ) + min/max validation
        for qid, values in numeric_values.items():
            qs = q_settings.get(qid, {})
            min_val = qs.get('min_value')
            max_val = qs.get('max_value')
            # min/max as errors
            if min_val is not None or max_val is not None:
                for sid, val in values:
                    if min_val is not None and val < min_val:
                        lint_map.setdefault(sid, {})\
                            .setdefault(str(qid), []).append('out_of_range')
                    elif max_val is not None and val > max_val:
                        lint_map.setdefault(sid, {})\
                            .setdefault(str(qid), []).append('out_of_range')
            # σ outlier as warning
            sigma = qs.get('outlier_sigma', 3)
            if len(values) >= 3 and sigma > 0:
                nums = [v for _, v in values]
                mean = sum(nums) / len(nums)
                std = (sum((x - mean) ** 2 for x in nums) / len(nums)) ** 0.5
                if std > 0:
                    for sid, val in values:
                        if abs(val - mean) > sigma * std:
                            lint_map.setdefault(sid, {})\
                                .setdefault(str(qid), []).append('numeric_outlier')

        # Warning: short text (< min_length chars)
        text_q_settings = {q.id: (q.validation_settings or {}) for q in questions if q.input_type in ('text', 'text_line')}
        for sid, qid, text in text_answers:
            min_len = text_q_settings.get(qid, {}).get('min_length', 3)
            if len(text.strip()) < min_len:
                lint_map.setdefault(sid, {})\
                    .setdefault(str(qid), []).append('short_text')

        # Warning: polygon area outlier (> median × factor or < median / factor)
        for qid, values in polygon_areas.items():
            if len(values) < 3:
                continue
            factor = q_settings.get(qid, {}).get('area_outlier_factor', 10)
            areas = sorted([a for _, a in values])
            median_area = areas[len(areas) // 2]
            if median_area == 0:
                continue
            for sid, area in values:
                if area > median_area * factor or area < median_area / factor:
                    lint_map.setdefault(sid, {})\
                        .setdefault(str(qid), []).append('area_outlier')

        return lint_map

    # ── Attribute table ─────────────────────────────────────────────

    def _get_ordered_questions(self):
        """Return flat list of top-level lineage representatives.

        Canonical questions in section-linked-list order first, then archived
        lineage representatives (questions removed from the current version
        but answered historically) so their columns stay visible.
        """
        ordered_sections = _get_ordered_sections(self.survey)
        section_order = {s.id: i for i, s in enumerate(ordered_sections)}

        questions = list(
            Question.objects
            .filter(
                survey_section__survey_header=self.survey,
                parent_question_id__isnull=True,
            )
            .exclude(input_type__in=('html', 'image'))
            .select_related('survey_section')
        )

        questions.sort(key=lambda q: (
            section_order.get(q.survey_section_id, 999),
            q.order_number,
        ))

        for entry in self._lineages.values():
            if entry['current'] is not None:
                continue
            rep = entry['questions'][0]
            if rep.parent_question_id is not None:
                continue
            if rep.input_type in ('html', 'image'):
                continue
            if self._lineage_ids(rep):  # has questions in scope
                questions.append(rep)

        return questions

    @staticmethod
    def _format_cell(answer):
        """Format a single Answer to a display string for the attribute table."""
        q = answer.question
        if q.input_type in ('choice', 'multichoice', 'rating'):
            names = answer.get_selected_choice_names()
            return ', '.join(names) if names else '—'
        elif q.input_type in ('number', 'range'):
            return str(answer.numeric) if answer.numeric is not None else '—'
        elif q.input_type in ('text', 'text_line', 'datetime'):
            return answer.text or '—'
        elif q.input_type == 'point' and answer.point:
            try:
                return '{:.2f}, {:.2f}'.format(answer.point.y, answer.point.x)
            except Exception:
                return 'point'
        elif q.input_type == 'line' and answer.line:
            try:
                return '{} vertices'.format(len(answer.line.coords))
            except Exception:
                return 'line'
        elif q.input_type == 'polygon' and answer.polygon:
            try:
                return '{} vertices'.format(len(answer.polygon.exterior.coords) - 1)
            except Exception:
                return 'polygon'
        return '—'

    def get_table_page(self, page=1, page_size=50, session_ids=None,
                       sort_col=None, sort_dir='asc', col_search=None,
                       show_trash=False, issues_filter=None, col_filters=None):
        """Return one page of session rows with formatted answer values.

        Args:
            page: 1-based page number
            page_size: rows per page
            session_ids: set of session PKs to include (from FilterManager), or None for all
            sort_col: 'id', 'start_datetime', 'language', or str(question_id)
            sort_dir: 'asc' or 'desc'
            col_search: dict {col_key: search_string} for per-column text filter
            show_trash: if True, show only trashed sessions

        Returns:
            dict with columns, rows, page, total_pages, total, page_size, sort_col, sort_dir
        """
        col_search = col_search or {}
        if not sort_col:
            sort_col = 'start_datetime'

        questions = self._get_ordered_questions()
        # Fetch answers for every lineage member in scope, not just the reps
        rep_by_qid = self._rep_question_by_qid()
        question_ids = sorted({
            qid for q in questions for qid in self._lineage_ids(q)
        })

        multi_version = len(self.scope_ids) > 1 or self.version == 'all'
        version_label_by_survey = {
            h.id: f'v{h.version_number}' for h in self._scope_surveys
        }

        # Build columns list
        system_cols = [
            {'key': 'id', 'label': '#', 'input_type': None},
            {'key': 'validation_status', 'label': 'Status', 'input_type': None},
            {'key': 'issues', 'label': 'Issues', 'input_type': None},
            {'key': 'tags', 'label': 'Tags', 'input_type': None},
            {'key': 'start_datetime', 'label': 'Start time', 'input_type': None},
            {'key': 'language', 'label': 'Language', 'input_type': None},
        ]
        if multi_version:
            system_cols.append({'key': 'version', 'label': 'Version', 'input_type': None})

        def _col_label(q):
            entry = self._lineages.get((q.code, q.input_type))
            if entry and entry['current'] is None:
                return f"{q.name or ''} ({entry['versions']})"
            return q.name or ''

        question_cols = [
            {
                'key': str(q.id), 'label': _col_label(q), 'input_type': q.input_type,
                'choices_json': json.dumps(q.choices or [], ensure_ascii=False) if q.input_type in ('choice', 'multichoice', 'rating') else '',
            }
            for q in questions
        ]
        columns = system_cols + question_cols

        # Base session queryset
        if show_trash:
            qs = SurveySession.objects.deleted().filter(survey_id__in=self.scope_ids)
        else:
            qs = self.base_qs
        if session_ids is not None:
            qs = qs.filter(pk__in=session_ids)

        # Fetch all matching sessions + their answers in bulk
        all_sessions = list(qs.order_by('-start_datetime'))

        # Bulk fetch answers for all sessions
        session_pks = [s.id for s in all_sessions]
        answer_qs = (
            Answer.objects
            .filter(
                survey_session_id__in=session_pks,
                parent_answer_id__isnull=True,
                question_id__in=question_ids,
            )
            .select_related('question')
        ) if session_pks else Answer.objects.none()

        # Materialize answers for pivot + lint
        all_answers = list(answer_qs)

        def rep_key(qid):
            rep = rep_by_qid.get(qid)
            return str(rep.id if rep else qid)

        # Pivot: {session_id: {rep_question_key: formatted_value}} — cells key
        # on the lineage representative so one column spans all versions.
        cell_map = {}
        for a in all_answers:
            if a.survey_session_id not in cell_map:
                cell_map[a.survey_session_id] = {}
            cell_map[a.survey_session_id][rep_key(a.question_id)] = self._format_cell(a)

        # Compute session issues and answer lints. Lints run against the full
        # per-version question set (required/validation rules are evaluated
        # against each session's own version), then remap to rep keys so
        # badges attach to the merged columns.
        session_issues = self.compute_session_issues(session_pks) if session_pks else {}
        lint_map = {}
        if session_pks:
            lint_questions = list(
                Question.objects
                .filter(
                    survey_section__survey_header_id__in=self.scope_ids,
                    parent_question_id__isnull=True,
                )
                .exclude(input_type__in=('html', 'image'))
                .select_related('survey_section')
            )
            raw_lints = self.compute_answer_lints(session_pks, all_answers, lint_questions)
            for sid, per_q in raw_lints.items():
                remapped = {}
                for qid_str, lints in per_q.items():
                    key = rep_key(int(qid_str))
                    remapped.setdefault(key, []).extend(lints)
                lint_map[sid] = remapped

        # Build rows
        rows = []
        for s in all_sessions:
            cells = cell_map.get(s.id, {})
            lints = lint_map.get(s.id, {})
            row = {
                'session_id': s.id,
                'id': s.id,
                'validation_status': s.validation_status,
                'is_deleted': s.is_deleted,
                'issues': session_issues.get(s.id, []),
                'lints': lints,
                'tags': s.tags or [],
                'notes': s.notes or '',
                'start_datetime': s.start_datetime,
                'language': s.language or '—',
                'version': version_label_by_survey.get(s.survey_id, ''),
                'cells': cells,
            }
            rows.append(row)

        _WARNING_TYPES = {'numeric_outlier', 'short_text', 'area_outlier'}
        _ERROR_TYPES = {'self_intersection', 'empty_required', 'out_of_range'}

        # Compute anomaly counts (before filtering)
        anomaly_counts = {}
        for r in rows:
            for issue in r['issues']:
                anomaly_counts[issue] = anomaly_counts.get(issue, 0) + 1
            for lint_list in r['lints'].values():
                for lint in lint_list:
                    anomaly_counts[lint] = anomaly_counts.get(lint, 0) + 1

        # Issues filter (issues_filter is a list of filter keys, or None)
        if issues_filter:
            filter_set = set(issues_filter)

            def _row_matches_filters(r, fset):
                for f in fset:
                    if f == 'has_errors':
                        if any(_ERROR_TYPES & set(ls) for ls in r['lints'].values()):
                            return True
                    elif f == 'has_warnings':
                        if any(_WARNING_TYPES & set(ls) for ls in r['lints'].values()):
                            return True
                    elif f == 'has_any_violation':
                        if r['issues'] or r['lints']:
                            return True
                    elif f in r['issues']:
                        return True
                    elif any(f in ls for ls in r['lints'].values()):
                        return True
                return False

            rows = [r for r in rows if _row_matches_filters(r, filter_set)]

        # Per-column search filter (legacy text search)
        if col_search:
            def matches_search(row):
                for col_key, search_str in col_search.items():
                    search_lower = search_str.lower()
                    if col_key in ('id', 'validation_status', 'issues', 'tags', 'start_datetime', 'language', 'version'):
                        val = str(row.get(col_key, ''))
                    else:
                        val = row['cells'].get(col_key, '—')
                    if search_lower not in val.lower():
                        return False
                return True
            rows = [r for r in rows if matches_search(r)]

        # Normalize cell value to string for filter matching
        def _normalize_val(v):
            if isinstance(v, list):
                return [str(item) if item else '' for item in v]
            return str(v) if v and v != '—' else ''

        # Compute unique values per column BEFORE col_filters (for dropdowns)
        unique_values = {}
        _VALUE_SYSTEM_COLS = {'validation_status', 'language', 'issues', 'tags', 'version'}
        for col in system_cols:
            if col['key'] not in _VALUE_SYSTEM_COLS:
                continue
            vals = set()
            for r in rows:
                v = r.get(col['key'], '')
                if isinstance(v, list):
                    for item in v:
                        vals.add(str(item) if item else '')
                else:
                    vals.add(str(v) if v else '')
            unique_values[col['key']] = sorted(vals)
        for col in question_cols:
            if col['input_type'] in ('choice', 'multichoice', 'rating'):
                vals = set()
                for r in rows:
                    v = r['cells'].get(col['key'], '—')
                    vals.add(v if v != '—' else '')
                unique_values[col['key']] = sorted(vals)

        # Typed column filters
        col_filters = col_filters or {}
        if col_filters:
            def _get_cell_val(row, col_key):
                if col_key in ('id', 'validation_status', 'issues', 'tags', 'start_datetime', 'language', 'version'):
                    return row.get(col_key, '')
                return row['cells'].get(col_key, '—')

            def matches_col_filters(row):
                for col_key, filt in col_filters.items():
                    ftype = filt.get('type')
                    if ftype == 'values':
                        allowed = set(filt.get('values', []))
                        val = _get_cell_val(row, col_key)
                        # Normalize: empty → '' to match unique_values convention
                        if isinstance(val, list):
                            normalized = set(str(v) if v else '' for v in val)
                            if not val:
                                normalized = {''}
                            if not (normalized & allowed):
                                return False
                        else:
                            normalized = str(val) if val and val != '—' else ''
                            if normalized not in allowed:
                                return False
                    elif ftype == 'range':
                        val = _get_cell_val(row, col_key)
                        try:
                            num = float(val) if not isinstance(val, (int, float)) else val
                        except (ValueError, TypeError):
                            return False
                        fmin = filt.get('min')
                        fmax = filt.get('max')
                        if fmin is not None and num < float(fmin):
                            return False
                        if fmax is not None and num > float(fmax):
                            return False
                    elif ftype == 'date_range':
                        val = row.get(col_key)
                        if val is None:
                            return False
                        val_str = val.strftime('%Y-%m-%d') if hasattr(val, 'strftime') else str(val)[:10]
                        if filt.get('min') and val_str < filt['min']:
                            return False
                        if filt.get('max') and val_str > filt['max']:
                            return False
                    elif ftype == 'text':
                        val = str(_get_cell_val(row, col_key))
                        if filt.get('query', '').lower() not in val.lower():
                            return False
                return True
            rows = [r for r in rows if matches_col_filters(r)]

        # Sort
        reverse = (sort_dir == 'desc')
        if sort_col == 'issues':
            rows.sort(key=lambda r: len(r.get('issues', [])), reverse=reverse)
        elif sort_col == 'tags':
            rows.sort(key=lambda r: len(r.get('tags', [])), reverse=reverse)
        elif sort_col in ('id', 'validation_status', 'start_datetime', 'language', 'version'):
            rows.sort(key=lambda r: (r.get(sort_col) is None, r.get(sort_col, '')), reverse=reverse)
        else:
            # Sort by question column value
            rows.sort(
                key=lambda r: (r['cells'].get(sort_col, '—') == '—', r['cells'].get(sort_col, '')),
                reverse=reverse,
            )

        # Paginate
        total = len(rows)
        total_pages = max(1, (total + page_size - 1) // page_size)
        page = min(max(page, 1), total_pages)
        offset = (page - 1) * page_size
        page_rows = rows[offset:offset + page_size]

        return {
            'columns': columns,
            'rows': page_rows,
            'page': page,
            'total_pages': total_pages,
            'total': total,
            'page_size': page_size,
            'sort_col': sort_col,
            'sort_dir': sort_dir,
            'col_search': col_search,
            'anomaly_counts': anomaly_counts,
            'unique_values': unique_values,
        }


class SessionValidationService:
    """Encapsulates all mutable operations on session validation state."""

    VALID_STATUSES = {s[0] for s in VALIDATION_STATUS_CHOICES}

    def set_status(self, session, status):
        """Set validation_status on a session. Raises ValueError for invalid status."""
        if status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid validation status: {status!r}")
        session.validation_status = status
        session.save(update_fields=['validation_status'])

    def trash(self, session):
        """Soft-delete a session (move to trash)."""
        session.is_deleted = True
        session.deleted_at = timezone.now()
        session.save(update_fields=['is_deleted', 'deleted_at'])

    def restore(self, session):
        """Restore a trashed session."""
        session.is_deleted = False
        session.deleted_at = None
        session.save(update_fields=['is_deleted', 'deleted_at'])

    def hard_delete(self, session):
        """Permanently delete a trashed session and all its answers."""
        session.delete()


class PerformanceAnalyticsService:
    """Read-only performance/funnel analytics from SurveyEvent data."""

    def __init__(self, survey, version='all'):
        self.survey = survey
        self.scope_ids = resolve_version_scope(survey, version)

    def _events_qs(self):
        return SurveyEvent.objects.filter(session__survey_id__in=self.scope_ids)

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

    def get_language_breakdown(self):
        """Return list of {language, count} sorted descending."""
        from .models import SurveySession
        counts = {}
        for lang in SurveySession.objects.filter(survey_id__in=self.scope_ids).values_list('language', flat=True):
            lang = lang or '—'
            counts[lang] = counts.get(lang, 0) + 1
        return sorted(
            [{'language': k, 'count': v} for k, v in counts.items()],
            key=lambda x: -x['count'],
        )

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

    def get_time_on_section(self):
        """Return avg/median time spent per section from page_leave events."""
        events = list(
            self._events_qs()
            .filter(event_type='page_leave')
            .values_list('metadata', flat=True)
        )

        by_section = {}
        for m in events:
            if not isinstance(m, dict):
                continue
            name = m.get('section_name', '')
            ms = m.get('time_on_page_ms')
            if name and isinstance(ms, (int, float)) and 0 < ms <= 3_600_000:
                by_section.setdefault(name, []).append(ms)

        sections = _get_ordered_sections(self.survey)
        section_order = {s.name: i for i, s in enumerate(sections)}

        result = []
        for name, values in sorted(by_section.items(), key=lambda x: section_order.get(x[0], 999)):
            avg_s = round(sum(values) / len(values) / 1000)
            median_s = round(statistics.median(values) / 1000)
            result.append({
                'section_name': name,
                'avg_seconds': avg_s,
                'median_seconds': median_s,
                'count': len(values),
            })
        return result

    def get_campaign_breakdown(self):
        """Return started/completed/rate per UTM source+medium+campaign triple."""
        completed_sids = set(
            self._events_qs()
            .filter(event_type='survey_complete')
            .values_list('session_id', flat=True)
        )

        starts = list(
            self._events_qs()
            .filter(event_type='session_start')
            .values('session_id', 'metadata')
        )

        buckets = {}
        for row in starts:
            m = row['metadata'] or {}
            source = m.get('utm_source', '').strip()
            if not source:
                continue
            medium = m.get('utm_medium', '')
            campaign = m.get('utm_campaign', '')
            key = (source, medium, campaign)
            if key not in buckets:
                buckets[key] = {'started': 0, 'completed': 0}
            buckets[key]['started'] += 1
            if row['session_id'] in completed_sids:
                buckets[key]['completed'] += 1

        return sorted(
            [
                {
                    'utm_source': src,
                    'utm_medium': med,
                    'utm_campaign': camp,
                    'started': data['started'],
                    'completed': data['completed'],
                    'rate': round(data['completed'] / data['started'] * 100) if data['started'] else 0,
                }
                for (src, med, camp), data in buckets.items()
            ],
            key=lambda x: -x['started'],
        )
