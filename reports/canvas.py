"""The report builder's canvas (change reports-canvas-editor, #731).

The builder draws the report itself, so it needs every block — also the ones readers do not see —
with what it shows, what its outline row reads and, when readers do not see it, why. One record
per block, built from the same `ReportService` payloads the page is made of; nothing is cached
here, so an edit shows at once. What the author WRITES (headings, text, key numbers, quotes,
captions) is handed over as stored: a live-number token stays a token while it is being edited.
"""
import json

from django.utils.html import strip_tags
from django.utils.text import Truncator
from django.utils.translation import gettext as _

from reports.models import STORY_BLOCK_TYPES

ICONS = {
    'heading': 'fas fa-heading', 'text': 'fas fa-align-left', 'image': 'far fa-image',
    'numbers': 'fas fa-hashtag', 'quotes': 'fas fa-quote-right', 'chart': 'fas fa-chart-bar',
    'map': 'fas fa-map-marked-alt', 'objects': 'fas fa-list-ul', 'budget': 'fas fa-coins',
    'crosstab': 'fas fa-table', 'engagement': 'fas fa-users', 'compare': 'fas fa-columns',
}
# Blocks drawn in the browser by js/public_results_render.js from their payload.
SCRIPTED = ('chart', 'map', 'objects')
_JSON_ESCAPES = {ord('<'): '\\u003C', ord('>'): '\\u003E', ord('&'): '\\u0026'}


def _en(value):
    if isinstance(value, dict):
        return value.get('en') or ''
    return value or ''


def _label(block):
    """What the outline calls the block: its own title, its question, its first words; '' when it
    has none of them (the row then reads the type's name, once)."""
    title = _en(block.custom_title)
    if title:
        return title
    if block.question_code and block.question is not None:
        return block.question.name or block.question.code
    content = _en(block.content)
    if content and block.block_type in ('heading', 'text', 'image'):
        return Truncator(' '.join(strip_tags(content).split())).chars(42)
    return ''


def _written(block, fill):
    """The payload of a block the author writes, as stored (nothing dropped). A key number or a
    note that is a live-number token also carries what it reads now (`shown`): the canvas shows
    that, and the token itself once the author clicks into it."""
    from reports.story import clean_html
    config = block.config or {}
    payload = {'id': block.id, 'block_type': block.block_type, 'width': block.width or 'full',
               'title': _en(block.custom_title)}
    if block.block_type == 'heading':
        payload['title'] = _en(block.content)
        payload['filled'] = bool(payload['title'].strip())
    elif block.block_type == 'text':
        payload['html'] = clean_html(_en(block.content))
        payload['filled'] = bool(strip_tags(payload['html']).strip())
    elif block.block_type == 'image':
        payload['image_url'] = block.image.url if block.image else ''
        payload['caption'] = _en(block.content)
        payload['filled'] = bool(block.image)
    else:
        payload['items'] = [dict(item) for item in config.get('items') or []]
        payload['note'] = _en(block.content)
        if block.block_type == 'numbers':
            for item in payload['items']:
                item['shown'] = fill(item.get('value', ''))
            payload['note_shown'] = fill(payload['note'])
        payload['filled'] = bool(payload['items'])
    return payload


def _note(block, payload):
    """Why readers do not see the block, or ''."""
    if block.is_hidden:
        return _('Hidden: readers do not see this block.')
    if block.block_type in STORY_BLOCK_TYPES:
        if payload['filled']:
            return ''
        return {
            'heading': _('Type the heading here. An empty heading is left out of the report.'),
            'text': _('Write here. An empty text block is left out of the report.'),
            'image': _('Left out of the report until it has a picture.'),
            'numbers': _('Left out of the report until it has a number.'),
            'quotes': _('Left out of the report until it has a quote.'),
        }[block.block_type]
    if payload is not None:
        return ''
    if block.block_type in ('chart', 'map', 'objects', 'budget', 'compare') and block.question is None:
        return _('The question this block showed is no longer in the survey, so readers do not see it.')
    return _('Nothing to show yet, so readers do not see this block.')


def item_for(service, block):
    """The canvas record of one block. `block.question` must be attached."""
    if block.block_type in STORY_BLOCK_TYPES:
        payload = _written(block, service.tokens.fill_plain)
        default_title = ''
    else:
        payload = service._build_block(block)
        # Without a title of its own the block reads its question's name (or what the renderer
        # derives); the canvas shows that as the placeholder of the title.
        default_title = (payload or {}).get('title') or (block.question.name if block.question is not None else '')
        if payload is not None:
            payload = dict(payload, title=_en(block.custom_title))
            if block.block_type == 'map':
                payload['description'] = ''    # written on the canvas, under the map
    note = _note(block, payload)
    label = _label(block)
    return {
        'payload': payload,
        'payload_json': (json.dumps(dict(payload, title=''), ensure_ascii=False, default=str).translate(_JSON_ESCAPES)
                         if payload is not None and block.block_type in SCRIPTED else ''),
        'default_title': default_title,
        'label': label,
        'type_name': block.get_block_type_display(),
        'icon': ICONS.get(block.block_type, 'fas fa-square'),
        'note': note,
        'shown': not note,
        'k': service.k,
    }


def blocks_of(report):
    from reports.sources import attach_questions
    return attach_questions(report.blocks.select_related('dataset__survey', 'view__dataset__survey'))


def items(report, blocks, lang='en'):
    """{block id: record} for every block of the report, and the service that made them."""
    from reports.render import ReportService
    service = ReportService(report, lang=lang)
    return {block.pk: item_for(service, block) for block in blocks}, service


def pair_ids(blocks, records):
    """Ids of the blocks that share a row with a neighbour: two consecutive half-width blocks
    readers see, by the rule of `reports.render.story_rows`."""
    paired, open_half = set(), None
    for block in blocks:
        if not records[block.pk]['shown']:
            continue
        if block.width == 'half':
            if open_half is not None:
                paired.update((open_half, block.pk))
                open_half = None
            else:
                open_half = block.pk
        else:
            open_half = None
    return paired
