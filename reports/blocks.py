"""Blocks written from plain values (change reports-usage-api, #710).

The REST API and the MCP server add and change a report's blocks with dicts, not editor forms.
This is their way into `reports.services` — the same writes the editor makes, so the sanitiser,
the item caps, the Data module's refusals and the version bump are the editor's. `describe` is
what both surfaces return for a block: the report file's own entry plus the block's id.

A spec: {"type": heading | text | numbers | quotes | chart | map | objects | budget | crosstab |
engagement, "title", "width": full | half, "hidden", and what the type holds — "text" (heading),
"html" (text), "items" + "note" (numbers, quotes), "question" (a question code) + "viz" (chart),
"question" + "show_marks" + "description" (map), "rows" + "columns" (crosstab), "question" +
"other" (compare: the same question code in another survey's uuid), and optionally
"survey" (a survey uuid of the workspace; default: the report's home survey)}. Pictures are
uploaded in the editor; an image block cannot be made from a spec.
"""
from django.utils.translation import gettext as _

from reports import services
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
    elif kind == 'map':
        if 'show_marks' in spec:
            kwargs['show_marks'] = bool(spec.get('show_marks'))
        if 'description' in spec:
            kwargs['content'] = spec.get('description') or ''
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
