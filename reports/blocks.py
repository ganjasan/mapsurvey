"""Blocks written from plain values (change reports-usage-api, #710).

The REST API and the MCP server add and change a report's blocks with dicts, not editor forms.
This is their way into `reports.services` — the same writes the editor makes, so the sanitiser,
the item caps, the Data module's refusals and the version bump are the editor's. `describe` is
what both surfaces return for a block: the report file's own entry plus the block's id.

A spec: {"type": heading | text | numbers | quotes | chart | map | objects | budget | crosstab |
engagement, "title", "width": full | half, "hidden", and what the type holds — "text" (heading),
"html" (text), "items" + "note" (numbers, quotes), "question" (a question code) + "viz" (chart),
"question" + "show_marks" + "description" (map) and how it is drawn — "view", "opts", "color",
"name", "frame" (None clears it), "legend", "scale", "toggle", "basemap", "popup_fields" and
"layers" ([{"id"?, "survey"?, "question", "view", "show_marks", "color", "name", "opts",
"popup_fields"}], the names `describe` returns — "code", "marks", "fields" — accepted too; change
report-api-map-layers) —, "rows" + "columns" + "display" ({view, values, sort}) (crosstab), "question" +
"other" (compare: the same question code in another survey's uuid), and optionally
"survey" (a survey uuid of the workspace; default: the report's home survey)}. Pictures are
uploaded in the editor; an image block cannot be made from a spec.
"""
import re

from django.utils.translation import gettext as _

from reports import services, story
from reports.models import QUESTION_BLOCK_TYPES, VIEW_BLOCK_TYPES

STORY_TYPES = ('heading', 'text', 'numbers', 'quotes')
TYPES = STORY_TYPES + QUESTION_BLOCK_TYPES + VIEW_BLOCK_TYPES + ('compare',)
CHART_VIZ = ('auto', 'bar', 'pie', 'donut', 'table')


class BlockRefused(Exception):
    def __init__(self, message, field='type'):
        super().__init__(message)
        self.message, self.field = message, field


def _survey(report, spec):
    from survey.models import SurveyHeader
    from survey.versioning import canonical_of
    uuid = spec.get('survey')
    if uuid:
        survey = SurveyHeader.objects.filter(uuid=uuid, organization_id=report.organization_id,
                                             deleted_at__isnull=True).first()
        if survey is None:
            raise BlockRefused(_('No survey of this workspace has that id.'), 'survey')
        return canonical_of(survey)
    if not report.survey_id:
        raise BlockRefused(_('This report has no home survey: name the survey the block shows.'), 'survey')
    return canonical_of(report.survey)


MAP_KEYS = ('view', 'opts', 'color', 'name', 'frame', 'legend', 'scale', 'toggle', 'layers')
LAYER_IDS = ('a', 'b', 'c', 'd', 'e', 'f', 'g', 'h')


def _refuse_view(view, question, field):
    if view is not None and view not in story.MAP_VIEWS:
        raise BlockRefused(_('A map is drawn as: %(choices)s.') % {'choices': ', '.join(story.MAP_VIEWS)}, field)
    if view == 'hotspots' and question is not None and question.input_type != 'point':
        raise BlockRefused(_('Hot spots are drawn for a question of points only.'), field)


def _checked_opts(raw, field):
    """A view's settings as sent, every value one the view has — else refused (the editor's
    cleaner would drop it)."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise BlockRefused(_('The settings of a view are an object.'), field)
    for key, value in raw.items():
        if value is None:
            continue
        if key in ('list', 'shade', 'solid'):
            if not isinstance(value, bool):
                raise BlockRefused(_('%(key)s is true or false.') % {'key': key}, '%s.%s' % (field, key))
        elif key not in story.MAP_OPTS:
            raise BlockRefused(_('A view has no setting %(key)s.') % {'key': key}, '%s.%s' % (field, key))
        elif value not in story.MAP_OPTS[key] or isinstance(value, bool):
            raise BlockRefused(_('%(key)s is one of: %(choices)s.')
                               % {'key': key, 'choices': ', '.join(str(c) for c in story.MAP_OPTS[key])},
                               '%s.%s' % (field, key))
    return {k: v for k, v in raw.items() if v is not None}


def _checked_fields(question, codes, field):
    """Popup fields: codes of the question's sub-questions a popup may show (never free text)."""
    from reports.sources import popup_subquestions
    codes = [str(c) for c in (codes or [])]
    allowed = {sub.code for sub in popup_subquestions([question.id]).get(question.id, ())} if question else set()
    for code in codes:
        if code not in allowed:
            raise BlockRefused(_('A popup shows the answers of a sub-question of the map question, never free '
                                 'text; %(code)s is not one.') % {'code': code}, field)
    return codes


def _marks_clash(look, field):
    if look.get('view') == 'marks' and look.get('show_marks') is False:
        raise BlockRefused(_('The Marks view shows every mark: it needs show_marks.'), field)


def _map_settings(block, spec):
    """The `update_block` arguments a map spec names (change report-api-map-layers): `map_display`
    in the dialect of `story.clean_config('map')`, popup fields and the basemap. Everything is
    checked first, so a refusal writes nothing; what the editor would quietly drop is refused."""
    question = block.question
    out, display = {}, {}
    if 'view' in spec:
        _refuse_view(spec['view'], question, 'view')
        _marks_clash(spec, 'view')
        if spec['view'] is not None:
            display['view'] = spec['view']
    if 'opts' in spec:
        display['opts'] = _checked_opts(spec['opts'], 'opts')
    if 'color' in spec:
        color = spec['color'] or ''
        if color and not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise BlockRefused(_('A colour is written as #rrggbb.'), 'color')
        display['color'] = color
    if 'name' in spec:
        display['name'] = spec['name'] or ''
    if 'frame' in spec:
        frame = spec['frame']
        if frame is not None and story.clean_frame(frame) is None:
            raise BlockRefused(_('A frame is [west, south, east, north] in degrees, west of east and south of '
                                 'north.'), 'frame')
        display['frame'] = frame or ''
    for key in ('legend', 'scale', 'toggle'):
        if key in spec and spec[key] is not None:
            display[key] = bool(spec[key])
    if 'layers' in spec:
        display['layers'] = _checked_layers(block, spec['layers'] or [])
    if 'popup_fields' in spec:
        out['geo_label_fields'] = _checked_fields(question, spec['popup_fields'], 'popup_fields')
    if spec.get('basemap'):
        from survey import basemaps
        choices = {key for key, _label in basemaps.choices_for(block.report.organization)}
        if spec['basemap'] not in choices:
            raise BlockRefused(_('This workspace has no basemap %(key)s.') % {'key': spec['basemap']}, 'basemap')
        out.update(basemap=spec['basemap'], valid_basemaps=choices)
    if display:
        out['map_display'] = display
    return out


def _checked_layers(block, layers):
    """The other layers of a map, each checked by the rule the editor drops them by
    (`services.layer_refusal`) and refused instead; ids kept for the layers that have one."""
    if len(layers) > story.MAX_MAP_LAYERS:
        raise BlockRefused(_('A map takes at most %(n)s layers beside its own question.')
                           % {'n': story.MAX_MAP_LAYERS}, 'layers')
    current = {layer.get('id') for layer in (block.config or {}).get('layers') or []}
    own_survey = services.own_layer_key(block)[0]
    seen, out, kept = {services.own_layer_key(block)}, [], set()
    for index, raw in enumerate(layers):
        field = 'layers.%d' % index
        if not isinstance(raw, dict):
            raise BlockRefused(_('A layer is an object.'), field)
        code = str(raw.get('question') or raw.get('code') or '')
        marks = raw.get('show_marks', raw.get('marks'))
        look = {'view': raw.get('view') or 'heat', 'show_marks': marks}
        refusal, key, question = services.layer_refusal(
            block, {'survey': str(raw.get('survey') or own_survey), 'code': code}, seen)
        if refusal:
            raise BlockRefused(refusal, field + '.question')
        seen.add(key)
        _refuse_view(look['view'], question, field + '.view')
        _marks_clash(look, field + '.view')
        color = raw.get('color') or ''
        if color and not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise BlockRefused(_('A colour is written as #rrggbb.'), field + '.color')
        layer_id = raw.get('id') if raw.get('id') in current - kept else None
        if layer_id:
            kept.add(layer_id)
        entry = {'id': layer_id, 'survey': key[0], 'code': code,
                 'view': look['view'], 'marks': bool(marks), 'color': color, 'name': raw.get('name') or '',
                 'opts': _checked_opts(raw.get('opts'), field + '.opts'),
                 'fields': _checked_fields(question, raw.get('popup_fields', raw.get('fields')), field + '.popup_fields')}
        out.append(entry)
    taken = {entry['id'] for entry in out if entry['id']}
    for entry in out:
        if not entry['id']:
            entry['id'] = next(i for i in LAYER_IDS if i not in taken)
            taken.add(entry['id'])
    return out


def _common(actor, block, spec):
    """Apply the values every block type shares, and the type's own text values."""
    kwargs = {}
    if 'title' in spec:
        kwargs['custom_title'] = str(spec.get('title') or '')[:300]
    if 'width' in spec:
        kwargs['width'] = spec.get('width')
    if 'hidden' in spec:
        kwargs['is_hidden'] = bool(spec.get('hidden'))
    kind = block.block_type
    if kind == 'heading' and 'text' in spec:
        kwargs['content'] = spec.get('text') or ''
    elif kind == 'text' and 'html' in spec:
        kwargs['content'] = spec.get('html') or ''
    elif kind in ('numbers', 'quotes'):
        if 'items' in spec:
            kwargs['items'] = spec.get('items') or []
        if 'note' in spec:
            kwargs['content'] = spec.get('note') or ''
        if kind == 'quotes' and 'style' in spec:
            if spec.get('style') not in story.QUOTE_STYLES:
                raise BlockRefused(_('Quotes are laid out as: %(choices)s.')
                                   % {'choices': ', '.join(story.QUOTE_STYLES)}, 'style')
            kwargs['quote_style'] = spec['style']
    elif kind == 'map':
        if 'show_marks' in spec:
            kwargs['show_marks'] = bool(spec.get('show_marks'))
        if 'description' in spec:
            kwargs['content'] = spec.get('description') or ''
        kwargs.update(_map_settings(block, spec))
    elif kind == 'crosstab' and spec.get('display') is not None:
        display = spec['display']
        if not isinstance(display, dict) or display.get('view') not in story.XTAB_VIEWS:
            raise BlockRefused(_('A cross-tab is drawn as: %(choices)s.') % {'choices': ', '.join(story.XTAB_VIEWS)},
                               'display.view')
        if display.get('values') not in (None,) + story.XTAB_VALUES:
            raise BlockRefused(_('A cross-tab shows: %(choices)s.') % {'choices': ', '.join(story.XTAB_VALUES)},
                               'display.values')
        kwargs['crosstab_display'] = {'view': display.get('view'), 'values': display.get('values') or 'percent',
                                      'sort': bool(display.get('sort'))}
    elif kind == 'chart' and 'viz' in spec:
        if spec.get('viz') not in CHART_VIZ:
            raise BlockRefused(_('A chart is drawn as: %(choices)s.') % {'choices': ', '.join(CHART_VIZ)}, 'viz')
        kwargs['viz'] = spec['viz']
    if kwargs:
        services.update_block(actor, block, **kwargs)
    return block


def add(actor, report, spec):
    """A new block at the end of the report from a spec. Raises BlockRefused."""
    from data.questions import question_of
    from reports.render import block_type_for_question
    kind = spec.get('type')
    if kind not in TYPES:
        raise BlockRefused(_('A block is one of: %(types)s.') % {'types': ', '.join(TYPES)})
    try:
        if kind in STORY_TYPES:
            block = services.add_story_block(actor, report, kind)
        elif kind == 'compare':
            from survey.models import SurveyHeader
            survey = _survey(report, spec)
            question = question_of(survey, str(spec.get('question') or ''))
            if question is None:
                raise BlockRefused(_('The survey has no question with that code.'), 'question')
            other = SurveyHeader.objects.filter(uuid=spec.get('other') or None, organization_id=report.organization_id,
                                                deleted_at__isnull=True).first() if spec.get('other') else None
            try:
                block = services.add_compare_block(actor, report, question, other)
            except services.ReportRefused as refusal:
                raise BlockRefused(refusal.message, 'other')
        elif kind in VIEW_BLOCK_TYPES:
            block = services.add_view_block(actor, report, kind, _survey(report, spec),
                                            rows=str(spec.get('rows') or ''), columns=str(spec.get('columns') or ''))
        else:
            survey = _survey(report, spec)
            question = question_of(survey, str(spec.get('question') or ''))
            if question is None:
                raise BlockRefused(_('The survey has no question with that code.'), 'question')
            if block_type_for_question(question) != kind:
                raise BlockRefused(_('That question is shown as a %(kind)s block.')
                                   % {'kind': block_type_for_question(question) or _('text answer, which is never published')},
                                   'type')
            block = services.add_question_block(actor, report, question)
    except services.ReportRefused as refusal:
        raise BlockRefused(refusal.message, 'rows' if kind == 'crosstab' else 'type')
    try:
        return _common(actor, block, spec)
    except BlockRefused:
        services.delete_block(actor, block)
        raise


def change(actor, block, spec):
    """Change what a spec names on an existing block; its type and its question stay."""
    return _common(actor, block, spec)


def describe(block):
    """What the API returns for a block: the report file's entry of it, with its id."""
    from reports.files import entry_of
    return {'id': block.pk, **entry_of(block)}
