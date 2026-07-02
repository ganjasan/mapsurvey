"""Read-only rendering service for the public survey results page.

Builds ordered, privacy-guarded per-block payloads for a PublicResultsPage:
- aggregates over CLEAN sessions only (not deleted, not not_approved/on_hold)
- spans the canonical survey and all its version copies
- masks small buckets via k-anonymity
- strips record-level identifiers from geo features and exposes only the
  popup label fields the creator explicitly selected

The same payload shape is produced for live rendering and for freezing into a
snapshot, so one template renders both modes.
"""

import json
import statistics

from django.core.cache import cache
from django.utils import timezone

from .models import (
    SurveyHeader, SurveySession, Answer,
    PUBLIC_RESULTS_SNAPSHOT_VERSION,
)
from .analytics import _compute_histogram

# Live aggregates are cached briefly so viral traffic does not hammer the DB.
LIVE_CACHE_TTL = 60

# Validation statuses that must never reach the public page.
EXCLUDED_VALIDATION_STATUSES = ('not_approved', 'on_hold')

# Question types whose individual answers are never published.
TEXT_INPUT_TYPES = ('text', 'text_line')

GEO_INPUT_TYPES = ('point', 'line', 'polygon')


def canonical_survey(survey):
    """Return the canonical survey for any version (or the survey itself)."""
    return survey.canonical_survey or survey


def _localize(value, lang):
    """Resolve a multilingual JSON value (or plain string) for a language."""
    if isinstance(value, dict):
        if not value:
            return ''
        return value.get(lang) or value.get('en') or next(iter(value.values()))
    return value or ''


class PublicResultsService:
    """Produce per-block payloads for a published public results page."""

    def __init__(self, page, lang='en'):
        self.page = page
        self.lang = lang
        self.canonical = canonical_survey(page.survey)
        self.k = max(1, page.k_anonymity_threshold or 1)
        self._survey_ids = self._collect_survey_ids()
        self._clean_ids = self._collect_clean_session_ids()

    # ---- clean session resolution -------------------------------------

    def _collect_survey_ids(self):
        ids = {self.canonical.id}
        ids.update(
            SurveyHeader.objects
            .filter(canonical_survey=self.canonical)
            .values_list('id', flat=True)
        )
        return ids

    def _collect_clean_session_ids(self):
        return set(
            SurveySession.objects
            .filter(survey_id__in=self._survey_ids, is_deleted=False)
            .exclude(validation_status__in=EXCLUDED_VALIDATION_STATUSES)
            .values_list('id', flat=True)
        )

    def response_count(self):
        return len(self._clean_ids)

    # ---- k-anonymity ---------------------------------------------------

    def _mask(self, count):
        """Return a display dict for a count, masking small non-zero buckets.

        Masked buckets expose no exact value — only the "<K" label and a
        sentinel value of None — so the raw number cannot be recovered from
        the served payload.
        """
        if 0 < count < self.k:
            return {'value': None, 'display': '<{}'.format(self.k), 'masked': True}
        return {'value': count, 'display': str(count), 'masked': False}

    # ---- block payloads -----------------------------------------------

    def build_blocks(self):
        """Return ordered, rendered payloads for all visible blocks."""
        payloads = []
        for block in self.page.blocks.filter(is_hidden=False):
            payload = self._build_block(block)
            if payload is not None:
                payloads.append(payload)
        return payloads

    def _build_block(self, block):
        if block.block_type == 'text':
            return self._text_payload(block)
        if block.block_type == 'image':
            return self._image_payload(block)
        if block.block_type in ('chart', 'map'):
            # A chart/map block must reference an existing question. A deleted
            # question (SET_NULL) silently drops the block.
            if block.question_id is None or block.question is None:
                return None
            if block.block_type == 'map':
                return self._map_payload(block)
            return self._chart_payload(block)
        return None

    def _base(self, block, extra_title=None):
        title = _localize(block.custom_title, self.lang)
        if not title and block.question is not None:
            title = block.question.name
        return {
            'id': block.id,
            'block_type': block.block_type,
            'viz': block.viz,
            'title': title,
        }

    def _text_payload(self, block):
        payload = self._base(block)
        payload['body'] = _localize(block.content, self.lang)
        return payload

    def _image_payload(self, block):
        if not block.image:
            return None
        payload = self._base(block)
        payload['image_url'] = block.image.url
        payload['caption'] = _localize(block.content, self.lang)
        return payload

    def _chart_payload(self, block):
        question = block.question
        itype = question.input_type
        payload = self._base(block)
        if itype in TEXT_INPUT_TYPES:
            # Defensive: text questions must never be published as blocks.
            return None
        if itype in ('choice', 'multichoice', 'rating'):
            payload.update(self._choice_data(question))
        elif itype in ('number', 'range'):
            payload.update(self._number_data(question))
        else:
            payload['data_type'] = 'unsupported'
        return payload

    def _answers(self, question):
        return Answer.objects.filter(
            question=question,
            survey_session_id__in=self._clean_ids,
        )

    def _choice_data(self, question):
        counts = {c['code']: 0 for c in (question.choices or [])}
        for selected in self._answers(question).values_list('selected_choices', flat=True):
            for code in (selected or []):
                counts[code] = counts.get(code, 0) + 1

        items = []
        total = 0
        for c in (question.choices or []):
            raw = counts.get(c['code'], 0)
            total += raw
            masked = self._mask(raw)
            items.append({
                'code': c['code'],
                'label': question.get_choice_name(c['code'], self.lang),
                'display': masked['display'],
                'value': masked['value'],
                'masked': masked['masked'],
            })
        return {'data_type': 'choices', 'items': items, 'total_answers': total}

    def _number_data(self, question):
        values = list(
            self._answers(question)
            .filter(numeric__isnull=False)
            .values_list('numeric', flat=True)
        )
        if not values:
            return {'data_type': 'number', 'count': 0}
        lo, hi = min(values), max(values)
        hist = _compute_histogram(values, lo, hi)
        return {
            'data_type': 'number',
            'count': len(values),
            'avg': round(sum(values) / len(values), 1),
            'min_val': lo,
            'max_val': hi,
            'median': round(statistics.median(values), 1),
            'hist_labels': hist['labels'],
            'hist_counts': hist['counts'],
        }

    def _map_payload(self, block):
        question = block.question
        payload = self._base(block)
        payload['basemap'] = block.basemap or 'streets'
        label_codes = set(block.geo_label_fields or [])

        features = []
        geo_field = question.input_type if question.input_type in GEO_INPUT_TYPES else None
        if geo_field is None:
            payload['data_type'] = 'geo'
            payload['feature_collection'] = {'type': 'FeatureCollection', 'features': []}
            return payload

        geo_answers = list(
            self._answers(question)
            .exclude(**{'{}__isnull'.format(geo_field): True})
            .select_related('question')
        )

        # Popup attributes are the point's OWN sub-answers (parent_answer),
        # so different points from the same respondent show their own values.
        labels_by_point = {}
        if label_codes:
            labels_by_point = self._collect_point_labels(geo_answers, label_codes)

        for a in geo_answers:
            geom = a.point or a.line or a.polygon
            if geom is None:
                continue
            features.append({
                'type': 'Feature',
                'geometry': json.loads(geom.geojson),
                'properties': labels_by_point.get(a.id, {}),
            })

        payload['data_type'] = 'geo'
        payload['feature_collection'] = {'type': 'FeatureCollection', 'features': features}
        payload['count'] = len(features)
        return payload

    def _collect_point_labels(self, geo_answers, label_codes):
        """Map geo_answer_id -> {label: value} from each point's own sub-answers.

        Only sub-answers of the given geo answers (via parent_answer), for the
        creator-selected sub-question codes, within clean sessions. Free text
        self-excludes (see _answer_display_value). No identifiers are emitted.
        """
        parent_ids = [a.id for a in geo_answers]
        if not parent_ids:
            return {}
        sub_answers = (
            Answer.objects
            .filter(
                parent_answer_id__in=parent_ids,
                question__code__in=label_codes,
                survey_session_id__in=self._clean_ids,
            )
            .select_related('question')
        )
        result = {}
        for a in sub_answers:
            value = self._answer_display_value(a)
            if value in (None, ''):
                continue
            # The FK field is literally named `parent_answer_id`, so the raw id
            # is `parent_answer_id_id` (accessing `.parent_answer_id` returns the
            # related Answer object, not its pk).
            result.setdefault(a.parent_answer_id_id, {})[a.question.name] = value
        return result

    def _answer_display_value(self, answer):
        q = answer.question
        if q.input_type in ('choice', 'multichoice', 'rating'):
            names = [q.get_choice_name(code, self.lang) for code in (answer.selected_choices or [])]
            return ', '.join(n for n in names if n)
        if q.input_type in ('number', 'range'):
            return answer.numeric
        # Free text is never exposed in popups.
        if q.input_type in TEXT_INPUT_TYPES:
            return None
        return None

    # ---- snapshot ------------------------------------------------------

    def build_snapshot(self):
        """Serialize the full current render into a frozen snapshot payload."""
        return {
            'snapshot_version': PUBLIC_RESULTS_SNAPSHOT_VERSION,
            'lang': self.lang,
            'response_count': self.response_count(),
            'blocks': self.build_blocks(),
        }


def build_page_context(page, lang='en'):
    """Build the template context for rendering a public results page.

    Shared by the public view (/r/<slug>/) and the editor preview endpoint
    so both render identically.
    """
    from django.urls import reverse

    data = render_page_data(page, lang=lang)
    survey = page.survey
    canonical = survey.canonical_survey or survey
    intro = page.intro or {}
    intro_title = _localize(intro.get('title'), lang) or survey.name
    intro_body = _localize(intro.get('body'), lang)

    return {
        'page': page,
        'survey': survey,
        'lang': lang,
        'intro_title': intro_title,
        'intro_body': intro_body,
        'response_count': data['response_count'],
        'blocks': data['blocks'],
        'blocks_json': json.dumps(data['blocks'], ensure_ascii=False),
        'frozen': data.get('frozen', False),
        'frozen_at': data.get('frozen_at'),
        'stale': data.get('stale', False),
        'show_response_count': page.show_response_count,
        'show_cta': page.show_participate_cta and canonical.can_accept_responses(),
        'survey_url': reverse('survey', kwargs={'survey_slug': str(survey.uuid)}),
        'noindex': page.visibility == 'unlisted',
    }


def _live_cache_key(page, lang):
    # `updated_at` acts as a version stamp. Any change to the page or its blocks
    # bumps it (see bump_page_version), which changes the key so the editor
    # preview and the public page reflect edits on the next render. New
    # *responses* do NOT touch updated_at, so live aggregates still honour the
    # TTL window and don't hammer the DB under viral traffic.
    version = page.updated_at.timestamp() if page.updated_at else 0
    return 'pubresults:{}:{}:{}:{}'.format(page.slug, lang, page.mode, version)


def bump_page_version(page):
    """Bump the page's version stamp so live caches are bypassed on next read.

    Call after any change to a page's block configuration (add/edit/delete/
    reorder). Touching `updated_at` changes the live cache key, so the editor
    preview and the public page reflect the change immediately instead of
    after the live-cache TTL elapses.
    """
    page.save(update_fields=['updated_at'])


def freeze_page(page, lang='en'):
    """Capture the current render into the page snapshot and switch to frozen."""
    service = PublicResultsService(page, lang=lang)
    page.snapshot = service.build_snapshot()
    page.snapshot_version = PUBLIC_RESULTS_SNAPSHOT_VERSION
    page.frozen_at = timezone.now()
    page.mode = 'frozen'
    page.save(update_fields=[
        'snapshot', 'snapshot_version', 'frozen_at', 'mode', 'updated_at',
    ])
    return page


def unfreeze_page(page):
    """Return a frozen page to live mode (snapshot is retained but unused)."""
    page.mode = 'live'
    page.save(update_fields=['mode', 'updated_at'])
    cache.delete(_live_cache_key(page, page.snapshot.get('lang', 'en') if page.snapshot else 'en'))
    return page


def render_page_data(page, lang='en'):
    """Return the render payload for a page: {response_count, blocks, ...}.

    Frozen pages read the stored snapshot (no DB/cache access). A snapshot
    written by an incompatible format version yields a `stale` flag so the
    template can ask the creator to re-freeze instead of showing wrong data.
    Live pages compute aggregates, cached for LIVE_CACHE_TTL seconds.
    """
    if page.mode == 'frozen':
        snap = page.snapshot or {}
        if snap.get('snapshot_version') != PUBLIC_RESULTS_SNAPSHOT_VERSION:
            return {
                'frozen': True, 'stale': True,
                'response_count': 0, 'blocks': [], 'frozen_at': page.frozen_at,
            }
        return {
            'frozen': True, 'stale': False,
            'response_count': snap.get('response_count', 0),
            'blocks': snap.get('blocks', []),
            'frozen_at': page.frozen_at,
            'lang': snap.get('lang'),
        }

    key = _live_cache_key(page, lang)
    cached = cache.get(key)
    if cached is not None:
        return cached

    service = PublicResultsService(page, lang=lang)
    data = {
        'frozen': False, 'stale': False,
        'response_count': service.response_count(),
        'blocks': service.build_blocks(),
    }
    cache.set(key, data, LIVE_CACHE_TTL)
    return data
