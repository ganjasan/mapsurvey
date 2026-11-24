"""Read-only rendering of a report (change reports-object, #703; before that the public results page).

Builds ordered, privacy-guarded per-block payloads for a Report:
- aggregates over CLEAN, NON-EMPTY sessions only (`data.scope.SessionScope.public`)
- each block reads the survey its dataset names, across that survey's version copies — so one
  report may show several surveys
- masks small buckets via k-anonymity
- strips record-level identifiers from geo features and exposes only the
  popup label fields the creator explicitly selected

The same payload shape is produced for live rendering and for freezing into a
snapshot, so one template renders both modes.
"""

import json
import statistics
import uuid as uuid_module

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.text import slugify

from reports.models import DEFAULT_K, Report, ReportBlock, SNAPSHOT_VERSION
from survey.analytics import _compute_histogram
from survey.models import Answer, Question
from survey.question_types import GEO_TYPES, geo_column
from survey.versioning import canonical_of, family_ids

# Live aggregates are cached briefly so viral traffic does not hammer the DB.
LIVE_CACHE_TTL = 60

# Question types whose individual answers are never published.
TEXT_INPUT_TYPES = ('text', 'text_line')

GEO_INPUT_TYPES = GEO_TYPES

# Question types that aggregate into a chart block on the public page.
CHART_INPUT_TYPES = ('choice', 'multichoice', 'rating', 'thumbs', 'number', 'range')


def block_type_for_question(question):
    """Map a question's input type to its public-page block type (or None)."""
    # Budget questions publish their aggregate, the placed-items one too:
    # what was funded is the result (change budget-question).
    if question.input_type == 'budget':
        return 'budget'
    if question.input_type in GEO_INPUT_TYPES:
        return 'map'
    if question.input_type in CHART_INPUT_TYPES:
        return 'chart'
    if question.input_type == 'layer_objects':
        return 'objects'
    return None  # text/datetime/html/... — not publishable


def canonical_survey(survey):
    """Return the canonical survey for any version (or the survey itself)."""
    return canonical_of(survey)


def study_area_outline(question):
    """The study area of `question`'s survey as GeoJSON (≤2,000 vertices, the study area service's
    limit), or None. Reports computes nothing here: the outline is the survey's own polygon."""
    import json as _json
    from survey.services.study_area import get as study_area_of
    if question is None:
        return None
    area = study_area_of(question.survey_section.survey_header)
    return _json.loads(area.geometry.geojson) if area is not None else None


def _localize(value, lang):
    """Resolve a multilingual JSON value (or plain string) for a language."""
    if isinstance(value, dict):
        if not value:
            return ''
        return value.get(lang) or value.get('en') or next(iter(value.values()))
    return value or ''


class ReportService:
    """Produce per-block payloads for a report."""

    def __init__(self, report, lang='en'):
        self.report = report
        self.lang = lang
        self.k = max(1, report.k_anonymity_threshold or 1)
        self.home = canonical_of(report.survey) if getattr(report, 'survey', None) is not None else None
        self._scopes = {}      # canonical survey id -> (family header ids, clean session ids)
        from reports.tokens import Tokens
        self.tokens = Tokens(self.home, self.k)    # live numbers in text (reports.tokens)

    @classmethod
    def for_survey(cls, survey, k, lang='en'):
        """The same service without a report (change landing-results): a site's results block
        aggregates one question of a linked survey with the same clean-session rule and masking.
        `k` is the K of the survey's report, or the model default."""
        from types import SimpleNamespace
        return cls(SimpleNamespace(survey=survey, k_anonymity_threshold=k), lang=lang)

    # ---- clean session resolution -------------------------------------

    def _scope(self, survey):
        """(family header ids, clean non-empty session ids) of a canonical survey, computed once
        per render (ADR-001 §6.2: the same answered responses Responses shows)."""
        hit = self._scopes.get(survey.id)
        if hit is None:
            from data.scope import SessionScope
            ids = family_ids(survey)
            hit = self._scopes[survey.id] = (ids, SessionScope(ids, nonempty=True).ids())
        return hit

    def _scope_of(self, question):
        return self._scope(canonical_of(question.survey_section.survey_header))

    def response_count(self):
        """Answered responses behind the report: its home survey's, or — for a report without
        one — those of every survey its blocks read."""
        if self.home is not None:
            return len(self._scope(self.home)[1])
        from reports.sources import source_surveys
        return sum(len(self._scope(s)[1]) for s in source_surveys(self.report))

    # ---- k-anonymity ---------------------------------------------------

    def _mask(self, count):
        """Return a display dict for a count, masking small non-zero buckets.

        Masked buckets expose no exact value — only the "<K" label and a
        sentinel value of None — so the raw number cannot be recovered from
        the served payload.
        """
        from data.aggregate import mask
        return mask(count, self.k)

    # ---- block payloads -----------------------------------------------

    def build_blocks(self):
        """Return ordered, rendered payloads for all visible blocks."""
        payloads = []
        from reports.sources import attach_questions
        blocks = attach_questions(
            self.report.blocks.filter(is_hidden=False)
            .select_related('dataset__survey', 'view__dataset__survey'))
        for block in blocks:
            payload = self._build_block(block)
            if payload is not None:
                payloads.append(payload)
        return payloads

    def _build_block(self, block):
        if block.block_type == 'text':
            return self._text_payload(block)
        if block.block_type == 'heading':
            payload = self._base(block)
            payload['title'] = payload['title'] or _localize(block.content, self.lang)
            return payload if payload['title'] else None
        if block.block_type in ('numbers', 'quotes'):
            payload = self._base(block)
            payload['items'] = [dict(item) for item in (block.config or {}).get('items') or []]
            if block.block_type == 'quotes':
                # Readers get the words and the source; where a quote was picked is the editor's.
                payload['items'] = [{'text': item.get('text', ''), 'source': item.get('source', '')}
                                    for item in payload['items']]
                payload['style'] = (block.config or {}).get('style') or 'list'
            if block.block_type == 'numbers':
                for item in payload['items']:      # a key number may be a live token
                    item['value'] = self.tokens.fill_plain(item.get('value', ''))
            payload['note'] = self.tokens.fill_plain(_localize(block.content, self.lang))
            return payload if payload['items'] else None
        if block.block_type in ('crosstab', 'engagement'):
            return self._view_payload(block)
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
        if block.block_type == 'compare':
            return self._compare_payload(block)
        if block.block_type == 'objects':
            if block.question_id is None or block.question is None:
                return None
            return self._objects_payload(block)
        if block.block_type == 'budget':
            if block.question_id is None or block.question is None:
                return None
            return self._budget_payload(block)
        return None

    def _budget_payload(self, block):
        """A budget question's aggregate over clean sessions, every item behind
        fewer than k respondents masked (spec public-results-page "Budget
        block"). Individual allocations never leave survey/budget_stats.py."""
        from survey.budget_stats import aggregate, masked
        payload = self._base(block)
        payload['data_type'] = 'budget'
        agg = masked(aggregate(block.question, session_ids=self._scope_of(block.question)[1], language=self.lang), self.k)
        if agg is None:
            payload['budget'] = None
            return payload
        rows = []
        for e in agg['items']:
            if agg['mode'] == 'split':
                share = e.get('mean_share')
                detail = e.get('mean_amount_label') or ''
            elif agg['mode'] == 'projects':
                share = e.get('pick_share')
                detail = e.get('cost_label') or ''
            else:
                share = e.get('budget_share')
                detail = '' if e.get('masked') else '×%s' % e.get('total_count', 0)
            rows.append({
                'name': e['name'],
                'color': e.get('color') or '',
                'masked': bool(e.get('masked')),
                'percent': None if share is None else round(share * 100),
                'detail': detail,
                'fit': e['code'] in (agg.get('fits') or []),
            })
        payload['budget'] = {
            'mode': agg['mode'],
            'total_label': agg['total_label'],
            'respondents': self._mask(agg['respondents']),
            'rows': rows,
        }
        payload['k'] = self.k
        return payload

    def _objects_payload(self, block):
        """Per-object aggregates of an Objects-on-the-map question, masked by k
        (spec object-answers): objects with fewer than k answers show as masked;
        free-text values are never included."""
        from survey.object_stats import object_aggregates
        question = block.question
        payload = self._base(block)
        payload['data_type'] = 'objects'
        aggregates = object_aggregates(question, session_ids=self._scope_of(question)[1])
        rows = []
        subs_meta = []
        for entry in aggregates.values():
            answers = self._mask(entry['answers'])
            row = {'key': entry['key'], 'title': entry['title'], 'category': entry['category'],
                   'answers': answers, 'subs': []}
            for sub in entry['subs'].values():
                if sub['type'] in ('text', 'text_line'):
                    continue
                cell = {'code': sub['code'], 'type': sub['type']}
                if answers['masked'] or not entry['answers']:
                    cell['display'] = answers['display'] if entry['answers'] else '—'
                elif sub['type'] in ('rating', 'range', 'number'):
                    cell['display'] = '' if sub.get('mean') is None else str(sub['mean'])
                    cell['value'] = sub.get('mean')
                elif sub['type'] == 'thumbs':
                    cell['display'] = '👍 %s / 👎 %s' % (sub['up'], sub['down'])
                    cell['up'], cell['down'] = sub['up'], sub['down']
                elif sub['type'] in ('choice', 'multichoice'):
                    cell['display'] = ', '.join('%s×%s' % (n, sub['labels'].get(code, code))
                                                for code, n in sub['counts'].items() if n) or '—'
                else:
                    cell['display'] = str(sub['count'])
                row['subs'].append(cell)
            rows.append(row)
            if not subs_meta:
                subs_meta = [{'code': s['code'], 'name': s['name'], 'type': s['type']}
                             for s in entry['subs'].values() if s['type'] not in ('text', 'text_line')]
        rows.sort(key=lambda r: (-(r['answers']['value'] or 0), r['title']))
        payload['rows'] = rows
        payload['sub_questions'] = subs_meta
        payload['k'] = self.k
        return payload

    def _base(self, block, extra_title=None):
        title = _localize(block.custom_title, self.lang)
        if not title and block.question is not None:
            title = block.question.name
        return {
            'id': block.id,
            'block_type': block.block_type,
            'viz': block.viz,
            'title': title,
            'width': getattr(block, 'width', 'full') or 'full',
        }

    def _text_payload(self, block):
        from reports.story import clean_html
        payload = self._base(block)
        payload['body'] = _localize(block.content, self.lang)
        # Rich text since change reports-story. A snapshot frozen before it has `body` only, and
        # the page escapes that one.
        payload['html'] = self.tokens.fill(clean_html(payload['body']))
        return payload

    def _view_payload(self, block):
        """A cross-tab or an engagement block: the result of its analysis view, computed by
        `data.dataviews.result` with this report's K. Nothing is aggregated here."""
        from data.dataviews import result
        view = block.view if block.view_id else None
        if view is None or view.kind != block.block_type:
            return None
        payload = self._base(block)
        data = result(view, lang=self.lang, k=self.k)
        if not data or data.get('missing'):
            return None
        payload['data'] = data
        payload['k'] = self.k
        if block.block_type == 'crosstab':
            payload['title'] = payload['title'] or '%s × %s' % (data['rows']['name'], data['columns']['name'])
            display = block.config or {}
            payload['display'] = {'view': display.get('view') or 'table',
                                  'values': display.get('values') or 'percent', 'sort': bool(display.get('sort'))}
            order = xtab_order(data, payload['display']['sort'])
            payload['table'] = [{'item': data['rows']['items'][i], 'cells': data['cells'][i]} for i in order]
            payload['xtab'] = xtab_view(data, payload['display'], order)
        else:
            peak = max((p['opened']['value'] or 0 for p in data['series']), default=0)
            for point in data['series']:
                for key in ('opened', 'answered'):
                    value = point[key]['value'] or 0
                    point[key + '_percent'] = round(100 * value / peak) if peak else 0
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
        if itype in ('choice', 'multichoice', 'rating', 'thumbs'):
            payload.update(self._choice_data(question))
        elif itype in ('number', 'range'):
            payload.update(self._number_data(question))
        else:
            payload['data_type'] = 'unsupported'
        return payload

    # ---- one question in two rounds (change reports-reuse, #711) -------

    def _round(self, question, survey):
        """One round of a comparison: who answered, and each option's count and share. A masked
        option carries no share; a round with fewer than K respondents carries none at all."""
        answers = self._answers(question)
        if question.input_type in ('number', 'range'):
            data = self._number_data(question)
            people = self._mask(data.get('count', 0))
            shown = not people['masked'] and data.get('count')
            return {'name': survey.name, 'n': people, 'cells': {
                'average': {'display': data['avg'] if shown else '—', 'share': None, 'masked': False},
                'median': {'display': data['median'] if shown else '—', 'share': None, 'masked': False}}}
        n = answers.exclude(selected_choices=[]).exclude(selected_choices__isnull=True) \
            .values('survey_session_id').distinct().count()
        people = self._mask(n)
        cells = {}
        for item in self._choice_data(question)['items']:
            share = None
            if not item['masked'] and not people['masked'] and n:
                share = round(100 * (item['value'] or 0) / n)
            cells[item['code']] = {'display': item['display'], 'share': share, 'masked': item['masked'],
                                   'label': item['label']}
        return {'name': survey.name, 'n': people, 'cells': cells}

    def _compare_payload(self, block):
        from django.utils.translation import gettext as _
        from reports.services import comparable
        from survey.models import SurveyHeader
        question = block.question if block.question_code else None
        other = SurveyHeader.objects.filter(
            uuid=(block.config or {}).get('other') or None, organization_id=self.report.organization_id,
            deleted_at__isnull=True).first() if (block.config or {}).get('other') else None
        twin = comparable(question, other)
        if twin is None or not block.dataset_id or not block.dataset.survey_id:
            return None
        rounds = [self._round(question, block.dataset.survey), self._round(twin, other)]
        payload = self._base(block)
        numeric = question.input_type in ('number', 'range')
        if numeric:
            keys = [('average', _('Average')), ('median', _('Median'))]
        else:
            keys, seen = [], set()
            for source in (question, twin):
                for choice in (source.choices or []):
                    if choice['code'] not in seen:
                        seen.add(choice['code'])
                        keys.append((choice['code'], source.get_choice_name(choice['code'], self.lang)))
        empty = {'display': '—', 'share': None, 'masked': False}
        payload.update(
            data_type='number' if numeric else 'choices', k=self.k,
            rounds=[{'name': r['name'], 'n': r['n']['display']} for r in rounds],
            rows=[{'label': label, 'cells': [dict(r['cells'].get(key, empty)) for r in rounds]} for key, label in keys],
            masked=any(c.get('masked') for r in rounds for c in r['cells'].values()) or any(r['n']['masked'] for r in rounds))
        return payload

    def _answers(self, question):
        """Answers for the question's whole lineage across the version family.

        The block's question FK may point at a current OR an archived question
        object (publish_draft moves old questions to the archived header and
        clones new ones), so a single-object filter silently loses one side.
        Lineage = same code + input_type within the family.
        """
        survey_ids, clean_ids = self._scope_of(question)
        return Answer.objects.filter(
            question__code=question.code,
            question__input_type=question.input_type,
            question__survey_section__survey_header_id__in=survey_ids,
            survey_session_id__in=clean_ids,
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
        """A map block: its own question and the other layers its author put on the same map
        (change report-map-views). Each layer is `_map_layer`; the block's own sits at the top
        level of the payload, the others under `layers`, drawn beneath it in that order."""
        from reports import story
        question = block.question
        config = getattr(block, 'config', None) or {}
        payload = self._base(block)
        payload['basemap'] = block.basemap or 'streets'
        payload['description'] = _localize(getattr(block, 'content', None) or {}, self.lang)
        color = config.get('color') or (
            question.color if (question.color or '').lower() not in ('', '#000000')
            else ('#d6336c' if question.input_type == 'spraycan' else '#4f46e5'))
        view = getattr(block, 'view', None)
        if view is not None and view.color and not config.get('color'):
            color = view.color
        payload.update(self._map_layer(question, config, color, block.geo_label_fields))
        payload['name'] = config.get('name') or question.name
        if config.get('frame'):
            payload['frame'] = config['frame']
        payload['legend'] = config.get('legend') is not False
        payload['scale'] = config.get('scale') is not False
        payload['toggle'] = bool(config.get('toggle'))
        # The outline of the study area of the block's own question's survey (change
        # map-layers-study-area): drawn under every layer, never part of the frame, counts or checks.
        if config.get('study_area') is not False:
            area = study_area_outline(question)
            if area is not None:
                payload['study_area'] = area
        layers = []
        for index, layer in enumerate(config.get('layers') or []):
            other = self._layer_question(block, layer)
            if other is None:
                continue            # its survey or question is gone: the layer is left out
            data = self._map_layer(other, layer,
                                   layer.get('color') or story.MAP_LAYER_COLORS[index % len(story.MAP_LAYER_COLORS)],
                                   layer.get('fields'))
            data.update(id=layer['id'], name=layer.get('name') or other.name)
            layers.append(data)
        payload['map_id'] = 'map-%s' % block.id
        if layers:
            payload['layers'] = layers
            # What the page writes under a map of several layers: the legend (also where readers
            # switch layers when the author lets them) and a list of places per layer that has one.
            drawn = [dict(payload, id='main')] + layers
            if payload['legend'] or payload['toggle']:
                payload['legend_rows'] = [{'id': layer['id'], 'name': layer['name'], 'color': layer['color'],
                                           'display': layer['display']} for layer in drawn]
            else:
                payload['legend_rows'] = []
            payload['spot_lists'] = [
                {'name': layer['name'], 'color': layer['color'], 'spots': layer['hotspots'],
                 'map_id': payload['map_id']}
                for layer in drawn if layer.get('hotspots') and layer['opts']['list']]
            payload['any_grid'] = any(layer['data_type'] == 'grid' for layer in drawn)
        return payload

    def _layer_question(self, block, layer):
        """The map question a layer names (survey uuid + code), of the report's workspace."""
        from data.questions import question_of
        from survey.models import SurveyHeader
        try:
            survey = SurveyHeader.objects.filter(uuid=layer.get('survey'),
                                                 organization_id=self.report.organization_id).first()
        except (ValueError, ValidationError):
            survey = None
        if survey is None:
            return None
        question = question_of(canonical_of(survey), layer.get('code'))
        return question if question is not None and question.input_type in GEO_INPUT_TYPES else None

    # Squares finer or coarser than the automatic choice (data.aggregate.GRID_STEPS).
    MAP_CELL_STEPS = {'finer': (80, 40, 20, 10), 'coarser': (20, 10, 5, 3)}

    def _map_layer(self, question, look, color, label_fields):
        """One layer of a map. By default cells that count DISTINCT respondents, cells under K left
        out (change data-aggregate, ADR-001 §6.3) — never an answer's own geometry; with `marks`
        the geometry of every mark and nothing else. `display` is the look (story.map_view),
        `data_type` what the layer carries; `opts` what the page needs of the view's settings."""
        from reports import story
        look = look or {}
        opts = story.map_opts(look)
        layer = {'data_type': 'grid', 'color': color, 'k': self.k,
                 'display': story.map_view(look, question.input_type),
                 'opts': {key: opts[key] for key in ('spread', 'strength', 'list', 'shade', 'size', 'solid')}}
        empty = {'type': 'FeatureCollection', 'features': []}
        if question.input_type not in GEO_INPUT_TYPES:
            layer.update(cells=empty, max=0, respondents_total=0, respondents_hidden=0, cell_m=0, count=0,
                         note='')
            return layer
        geo_field = geo_column(question.input_type)
        rows = list(
            self._answers(question)
            .exclude(**{'{}__isnull'.format(geo_field): True})
            .only('id', 'survey_session_id', geo_field)
        )
        members = [(a.survey_session_id, a.id, getattr(a, geo_field)) for a in rows]
        label_codes = set(label_fields or []) if question.input_type != 'spraycan' else set()
        clean_ids = self._scope_of(question)[1]
        if layer['display'] == 'hotspots':
            layer['hotspots'] = self._hotspots(question, members, bool(look.get('marks')), opts, label_codes)
        if look.get('marks'):
            # The author chose to show the marks themselves (owner decision 2026-11-16: the survey
            # owner answers for that). Geometry only — no answer id, no session, no sub-answers.
            layer['data_type'] = 'marks'
            layer['marks'] = {'type': 'FeatureCollection', 'features': [
                {'type': 'Feature', 'properties': {}, 'geometry': json.loads(geom.geojson)}
                for _session, _answer, geom in members]}
            layer['count'] = len(members)
            layer['respondents_total'] = len({session for session, _a, _g in members})
            layer['spray'] = question.input_type == 'spraycan'
            return layer
        from data.aggregate import GRID_STEPS, grid
        # The finest grid that shows most respondents (change data-grid-adaptive), cells under K
        # omitted whatever the size.
        cells = grid(members, k=self.k, min_cell_m=self.MAP_GRID_MIN_M,
                     steps=self.MAP_CELL_STEPS.get(opts['cell'], GRID_STEPS))
        fields_by_cell = self._cell_fields(cells['cells'], label_codes, clean_ids) if label_codes else {}
        from django.contrib.gis.geos import Polygon as GeosPolygon
        features = []
        for i, cell in enumerate(cells['cells']):
            props = {'respondents': cell['respondents']}
            if fields_by_cell.get(i):
                props['fields'] = fields_by_cell[i]
            features.append({
                'type': 'Feature',
                'geometry': json.loads(GeosPolygon.from_bbox(cell['bbox']).geojson),
                'properties': props,
            })
        layer['cells'] = {'type': 'FeatureCollection', 'features': features}
        layer['max'] = cells['max']
        layer['respondents_total'] = cells['respondents_total']
        layer['respondents_hidden'] = cells['respondents_hidden']
        layer['cell_m'] = cells['cell_m']
        layer['count'] = len(features)
        layer['note'] = self._grid_note(cells)
        return layer

    def _hotspots(self, question, members, every_mark, opts, label_codes):
        """The places the marks gather, ranked (data.aggregate.hotspots): at least K respondents
        each unless the author shows the marks themselves. Each carries the masked summary of the
        sub-questions the author picked, as a square does."""
        from data.aggregate import hotspots
        spots = hotspots(members, k=self.k, every_mark=every_mark, cell_m=float(opts['place']),
                         merge_m=opts['place'] * 1.25, limit=opts['top'] or 50)
        fields = (self._cell_fields(spots, label_codes, self._scope_of(question)[1])
                  if label_codes and spots else {})
        out = []
        for i, spot in enumerate(spots):
            item = {key: spot[key] for key in ('rank', 'lng', 'lat', 'respondents', 'marks')}
            if fields.get(i):
                item['fields'] = fields[i]
            out.append(item)
        return out

    def _grid_note(self, cells):
        """What a visitor reads under (or instead of) the map: why nothing or not everyone shows."""
        from django.utils import translation
        from django.utils.translation import gettext, ngettext
        total, hidden = cells['respondents_total'], cells['respondents_hidden']
        if not total or not hidden:
            return ''
        with translation.override(self.lang):
            if not cells['cells']:
                return gettext('Not enough answers yet to show this map without revealing anyone: '
                               'areas with fewer than %(k)s people stay hidden.') % {'k': self.k}
            return ngettext('%(n)s respondent is in an area with fewer than %(k)s people and is not shown.',
                            '%(n)s respondents are in areas with fewer than %(k)s people and are not shown.',
                            hidden) % {'n': hidden, 'k': self.k}

    # Cell size: the finest of data.aggregate.GRID_STEPS cells across the answers' bbox that shows
    # most respondents, never finer than MAP_GRID_MIN_M (change data-grid-adaptive).
    MAP_GRID_MIN_M = 20.0

    def _cell_fields(self, cells, label_codes, clean_ids):
        """{cell index: [{'name', 'values': [{'label', 'display'}]} | {'name', 'mean'}]} —
        the selected sub-questions answered by the cell's geo answers, masked: a choice under K
        shows "<K", a number's mean only when at least K values exist. Free text never."""
        member_cell = {}
        for i, cell in enumerate(cells):
            for member in cell['members']:
                member_cell.setdefault(member, []).append(i)
        if not member_cell:
            return {}
        subs = (Answer.objects
                .filter(parent_answer_id__in=list(member_cell), question__code__in=label_codes,
                        survey_session_id__in=clean_ids)
                .exclude(question__input_type__in=TEXT_INPUT_TYPES)
                .select_related('question'))
        acc = {}     # (cell, code) -> {'q': question, 'choices': {code: n}, 'numbers': []}
        for a in subs:
            for i in member_cell.get(a.parent_answer_id_id, ()):
                entry = acc.setdefault((i, a.question.code),
                                       {'q': a.question, 'choices': {}, 'numbers': []})
                if a.question.input_type in ('number', 'range'):
                    if a.numeric is not None:
                        entry['numbers'].append(a.numeric)
                else:
                    for code in (a.selected_choices or []):
                        entry['choices'][code] = entry['choices'].get(code, 0) + 1
        out = {}
        for (i, _code), entry in sorted(acc.items(), key=lambda kv: (kv[0][0], kv[1]['q'].order_number)):
            q = entry['q']
            if q.input_type in ('number', 'range'):
                if len(entry['numbers']) >= self.k:
                    out.setdefault(i, []).append(
                        {'name': q.name, 'mean': round(sum(entry['numbers']) / len(entry['numbers']), 1)})
                continue
            values = []
            for code, n in sorted(entry['choices'].items(), key=lambda kv: -kv[1]):
                masked = self._mask(n)
                values.append({'label': q.get_choice_name(code, self.lang), 'display': masked['display']})
            if values:
                out.setdefault(i, []).append({'name': q.name, 'values': values})
        return out

    # ---- snapshot ------------------------------------------------------

    def build_snapshot(self):
        """Serialize the full current render into a frozen snapshot payload."""
        return {
            'snapshot_version': SNAPSHOT_VERSION,
            'lang': self.lang,
            'response_count': self.response_count(),
            'blocks': self.build_blocks(),
            # The opening paragraph with its live numbers as they stood at the freeze.
            'intro_body': self.tokens.fill_plain(_localize((self.report.intro or {}).get('body'), self.lang)),
        }


# ── how a cross-tab is drawn (change crosstab-settings-in-block, #751) ─────────────────────────
# Presentation only: every number below is a count or a total the Data module published (masked
# and withheld as it decided); a share is one of them divided by another, never a recount.

XTAB_COLORS = ('#4f46e5', '#d97706', '#0f766e', '#db2777', '#0284c7', '#65a30d', '#7c3aed', '#ea580c')


def _visible_sum(cells):
    return sum(c['value'] or 0 for c in cells if not c['masked'])


def xtab_order(data, sort):
    """The rows (options of the Question) in survey order, or by how many chose them."""
    order = list(range(len(data['rows']['items'])))
    if sort:
        def size(i):
            total = data['rows']['items'][i]['total']['value']
            return -(total if total is not None else _visible_sum(data['cells'][i]))
        order.sort(key=size)
    return order


def _pct(part, whole):
    return round(100 * part / whole) if whole else 0


def xtab_view(data, display, order):
    """What the chosen view draws: `bars`, `stacked` or `ranking` (the table reads `table`)."""
    view, percent = display['view'], display['values'] == 'percent'
    rows, columns, cells = data['rows']['items'], data['columns']['items'], data['cells']
    series = [{'index': c, 'label': item['label'], 'color': XTAB_COLORS[c % len(XTAB_COLORS)],
               'total': item['total']} for c, item in enumerate(columns)]
    out = {'view': view, 'percent': percent, 'series': series, 'left_out': [], 'categories': []}
    if view == 'bars':
        # A share needs its group's total; a group whose total is withheld shows no bars.
        # A group nobody is in has nothing to draw and is no secret: it is just not drawn.
        shown = [s for s in series if not percent or (s['total']['value'] or 0) > 0]
        out['left_out'] = [s['label'] for s in series if s not in shown and s['total']['value'] is None]
        out['series'] = shown
        peak = max([c['value'] or 0 for line in cells for c in line if not c['masked']] or [0])
        for r in order:
            bars = []
            for s in shown:
                cell = cells[r][s['index']]
                if cell['masked']:
                    bars.append({'color': s['color'], 'width': 0, 'display': cell['display'], 'masked': True})
                    continue
                value = cell['value'] or 0
                share = _pct(value, s['total']['value']) if percent else None
                bars.append({'color': s['color'], 'masked': False,
                             'width': share if percent else _pct(value, peak),
                             'display': '%s%%' % share if percent else str(value)})
            out['categories'].append({'label': rows[r]['label'], 'bars': bars})
    elif view == 'stacked':
        # Each option's people split by group, as a share of the option's answers; an option with
        # a masked pair is left out — its other pairs would give the hidden one away.
        for r in order:
            line = cells[r]
            if any(c['masked'] for c in line):
                out['left_out'].append(rows[r]['label'])
                continue
            whole = _visible_sum(line)
            if not whole:
                continue
            segments = [{'color': s['color'], 'label': s['label'], 'width': _pct(line[s['index']]['value'] or 0, whole),
                         'display': ('%s%%' % _pct(line[s['index']]['value'] or 0, whole)) if percent
                         else str(line[s['index']]['value'] or 0)}
                        for s in series if line[s['index']]['value']]
            out['categories'].append({'label': rows[r]['label'], 'segments': segments})
    elif view == 'ranking':
        everyone = data['respondents']['value']
        totals = [(r, rows[r]['total']) for r in range(len(rows))]
        totals.sort(key=lambda pair: -(pair[1]['value'] if pair[1]['value'] is not None else -1))
        peak = max([t['value'] or 0 for _r, t in totals] or [0])
        out['percent'] = percent and bool(everyone)
        out['counts_instead'] = percent and everyone is None
        for rank, (r, total) in enumerate(totals, start=1):
            value = total['value']
            if value is None:
                display, width = total['display'], 0
            elif out['percent']:
                display, width = '%s%%' % _pct(value, everyone), _pct(value, everyone)
            else:
                display, width = str(value), _pct(value, peak)
            out['categories'].append({'rank': rank, 'label': rows[r]['label'], 'width': width, 'display': display,
                                      'masked': value is None})
    # Too few answers to draw anything as chosen: the table says what can be said.
    drawn = (out['series'] if view == 'bars' else out['categories']) if view != 'table' else True
    if not drawn:
        out.update(view='table', fallback=True)
    return out


def k_for_survey(survey):
    """The K a surface outside a report uses for a survey's aggregates (a Site results block, a
    grid view): the K of the survey's report, or the default."""
    report = report_of(survey)
    return max(1, (report.k_anonymity_threshold if report is not None else DEFAULT_K) or 1)


def report_of(survey):
    """The survey's report — the oldest one whose home it is — or None. Read-only."""
    return Report.objects.filter(survey=survey).order_by('id').first()


def build_context(report, lang='en'):
    """Template context of a report's page. Shared by /r/<slug>/ and the editor preview so both
    render identically."""
    from django.urls import reverse

    data = render_data(report, lang=lang)
    survey = report.survey if report.survey_id else None
    canonical = canonical_of(survey) if survey is not None else None
    intro = report.intro or {}
    intro_title = _localize(intro.get('title'), lang) or (survey.name if survey is not None else report.slug)
    intro_body = _localize(intro.get('body'), lang)
    if data.get('frozen'):
        intro_body = data.get('intro_body') or intro_body
    elif canonical is not None and '{' in (intro_body or ''):
        from reports.tokens import Tokens
        intro_body = Tokens(canonical, report.k_anonymity_threshold).fill_plain(intro_body)

    return {
        'page': report,
        'report': report,
        'survey': survey,
        'lang': lang,
        'intro_title': intro_title,
        'intro_body': intro_body,
        'intro_eyebrow': _localize(intro.get('eyebrow'), lang),
        'rows': story_rows(data['blocks']),
        'response_count': data['response_count'],
        'blocks': data['blocks'],
        'blocks_json': json.dumps(data['blocks'], ensure_ascii=False),
        'frozen': data.get('frozen', False),
        'frozen_at': data.get('frozen_at'),
        'stale': data.get('stale', False),
        'show_response_count': report.show_response_count,
        'show_cta': bool(canonical is not None and report.show_participate_cta
                         and canonical.can_accept_responses()),
        'survey_url': reverse('survey', kwargs={'survey_slug': str(survey.uuid)}) if survey is not None else '',
        'noindex': report.visibility != 'public',
        'pdf_url': _page_pdf_url(report),
    }


def story_rows(blocks):
    """The blocks as the rows of a story: two consecutive half-width blocks share a row, any other
    block has its own. [[payload], [payload, payload], …]"""
    rows = []
    for block in blocks:
        half = block.get('width') == 'half'
        if half and rows and len(rows[-1]) == 1 and rows[-1][0].get('width') == 'half':
            rows[-1].append(block)
        else:
            rows.append([block])
    return rows


def _page_pdf_url(report):
    """Where the stored PDF of a published, frozen report is served, or '' when there is none."""
    if not report.is_published or report.mode != 'frozen' or not report.pk:
        return ''
    from django.urls import reverse
    from reports.services import ready_pdf
    return reverse('report_page_pdf', args=[report.slug]) if ready_pdf(report) is not None else ''


def _live_cache_key(report, lang):
    # `updated_at` acts as a version stamp. Any change to the report or its blocks
    # bumps it (see bump_version), which changes the key so the editor
    # preview and the public page reflect edits on the next render. New
    # *responses* do NOT touch updated_at, so live aggregates still honour the
    # TTL window and don't hammer the DB under viral traffic.
    version = report.updated_at.timestamp() if report.updated_at else 0
    return 'pubresults:{}:{}:{}:{}'.format(report.slug, lang, report.mode, version)


def unique_slug(name):
    base = slugify(name or '')[:48] or 'results'
    candidate = base
    if Report.objects.filter(slug=candidate).exists():
        candidate = '{}-{}'.format(base, uuid_module.uuid4().hex[:6])
    return candidate


def report_for_survey(survey, **defaults):
    """Return the survey's report, creating an empty one if missing."""
    report = report_of(survey)
    if report is None:
        report = Report.objects.create(
            survey=survey, organization_id=survey.organization_id,
            slug=unique_slug(survey.name), **defaults)
    return report


def scaffold_report(survey):
    """Ensure a draft report exists for the survey and populate default blocks, once.

    One block per publishable top-level question in survey order (map for geo
    questions, chart for choice/rating/number/range). Runs only while
    `scaffolded_at` is unset AND the report has no blocks — so a report the
    creator already built by hand is left untouched, and blocks the creator
    deletes are never re-created on a later publish. Reports created here start
    unlisted; `is_published` stays False either way, so nothing becomes
    publicly reachable.
    """
    from reports.sources import dataset_for
    canonical = canonical_of(survey)
    report = report_for_survey(canonical, visibility='unlisted')
    if report.scaffolded_at is not None or report.created_by_id is not None:
        # A report somebody started (and gave this survey as its home) is theirs to fill.
        return report
    update_fields = ['scaffolded_at', 'updated_at']
    if not report.blocks.exists():
        # A report lazily created by the config tab predates the scaffold and
        # carries the model's `public` default; a scaffolded draft must stay
        # unlisted until the creator reviews it. Hand-built reports (non-empty)
        # never reach this branch, so their visibility is never overridden.
        if report.visibility != 'unlisted':
            report.visibility = 'unlisted'
            update_fields.append('visibility')
        questions = (
            Question.objects
            .filter(survey_section__survey_header=canonical,
                    parent_question_id__isnull=True)
            .select_related('survey_section__survey_header')
            .order_by('survey_section__id', 'order_number')
        )
        blocks = []
        for question in questions:
            block_type = block_type_for_question(question)
            if block_type is None:
                continue
            blocks.append(ReportBlock(
                report=report, dataset=dataset_for(question), question_code=question.code,
                block_type=block_type, order=len(blocks),
                config={'view': 'heat'} if block_type == 'map' else {},   # services.new_map_config
            ))
        ReportBlock.objects.bulk_create(blocks)
    # Stamped even when blocks already existed (hand-built report): it is
    # "resolved" either way and must never be re-checked or re-populated.
    # updated_at doubles as the live-cache version stamp (see bump_version).
    report.scaffolded_at = timezone.now()
    report.save(update_fields=update_fields)
    return report


def bump_version(report):
    """Bump the report's version stamp so live caches are bypassed on next read.

    Call after any change to a report's block configuration (add/edit/delete/
    reorder). Touching `updated_at` changes the live cache key, so the editor
    preview and the public page reflect the change immediately instead of
    after the live-cache TTL elapses.
    """
    report.save(update_fields=['updated_at'])


def freeze_report(report, lang='en'):
    """Capture the current render into the report's snapshot and switch to frozen."""
    service = ReportService(report, lang=lang)
    report.snapshot = service.build_snapshot()
    report.snapshot_version = SNAPSHOT_VERSION
    report.frozen_at = timezone.now()
    report.mode = 'frozen'
    report.save(update_fields=[
        'snapshot', 'snapshot_version', 'frozen_at', 'mode', 'updated_at',
    ])
    return report


def unfreeze_report(report):
    """Return a frozen report to live mode (snapshot is retained but unused)."""
    report.mode = 'live'
    report.save(update_fields=['mode', 'updated_at'])
    cache.delete(_live_cache_key(report, report.snapshot.get('lang', 'en') if report.snapshot else 'en'))
    return report


def render_data(report, lang='en'):
    """Return the render payload of a report: {response_count, blocks, ...}.

    Frozen reports read the stored snapshot (no DB/cache access). A snapshot
    written by an incompatible format version yields a `stale` flag so the
    template can ask the creator to re-freeze instead of showing wrong data.
    Live reports compute aggregates, cached for LIVE_CACHE_TTL seconds.
    """
    if report.mode == 'frozen':
        snap = report.snapshot or {}
        if snap.get('snapshot_version') != SNAPSHOT_VERSION:
            return {
                'frozen': True, 'stale': True,
                'response_count': 0, 'blocks': [], 'frozen_at': report.frozen_at,
            }
        return {
            'frozen': True, 'stale': False,
            'response_count': snap.get('response_count', 0),
            'blocks': snap.get('blocks', []),
            'intro_body': snap.get('intro_body'),
            'frozen_at': report.frozen_at,
            'lang': snap.get('lang'),
        }

    key = _live_cache_key(report, lang)
    cached = cache.get(key)
    if cached is not None:
        return cached

    service = ReportService(report, lang=lang)
    data = {
        'frozen': False, 'stale': False,
        'response_count': service.response_count(),
        'blocks': service.build_blocks(),
    }
    cache.set(key, data, LIVE_CACHE_TTL)
    return data
