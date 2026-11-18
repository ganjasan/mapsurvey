"""What the author writes into a story (change reports-story, #704).

A linear story is headings, text, pictures, key numbers and quotes between the blocks that show
data. Nothing here is computed: numbers and quotes are typed (or pasted) by the author — the owner
allowed typed numbers on 2026-11-16, because a report made by hand has to stay editable. Every
value passes through here on its way in, from the editor and from an imported report file alike.
"""
from reports.models import MAX_ITEMS, WIDTH_CHOICES

WIDTHS = tuple(w for w, _label in WIDTH_CHOICES)
MAX_VALUE = 40
MAX_LABEL = 120
MAX_QUOTE = 1000
MAX_SOURCE = 160


QUOTE_STYLES = ('list', 'pull', 'cards')
XTAB_VIEWS = ('bars', 'stacked', 'ranking', 'table')
XTAB_VALUES = ('percent', 'count')


def clean_ref(raw):
    """Where a picked quote came from: {survey: <uuid>, question: <code>}, or None. Accepts the
    dict or the editor's row attribute `<uuid>:<code>`."""
    import uuid as uuid_module
    if isinstance(raw, str):
        survey, _sep, question = raw.partition(':')
        raw = {'survey': survey, 'question': question}
    if not isinstance(raw, dict):
        return None
    try:
        survey = str(uuid_module.UUID(str(raw.get('survey') or '')))
    except ValueError:
        return None
    question = str(raw.get('question') or '').strip()[:100]
    return {'survey': survey, 'question': question} if question else None


def _text(value, limit):
    return ' '.join(str(value or '').split())[:limit]


def clean_html(raw):
    """Rich text of a Text block as stored: sanitised by the creator allow-list; text typed
    before the blocks were rich (no markup) is escaped, never read as markup."""
    from survey.html_sanitize import coerce_creator_html
    return coerce_creator_html(raw or '')


def clean_config(block_type, raw):
    """The `config` a block of this type may hold; anything else is dropped."""
    raw = raw if isinstance(raw, dict) else {}
    items = raw.get('items') if isinstance(raw.get('items'), list) else []
    if block_type == 'numbers':
        out = []
        for item in items[:MAX_ITEMS]:
            if not isinstance(item, dict):
                continue
            value, label = _text(item.get('value'), MAX_VALUE), _text(item.get('label'), MAX_LABEL)
            if value or label:
                out.append({'value': value, 'label': label})
        return {'items': out}
    if block_type == 'quotes':
        out = []
        for item in items[:MAX_ITEMS]:
            if not isinstance(item, dict):
                continue
            text = str(item.get('text') or '').strip()[:MAX_QUOTE]
            if not text:
                continue
            quote = {'text': text, 'source': _text(item.get('source'), MAX_SOURCE)}
            ref = clean_ref(item.get('ref'))
            if ref:
                # Picked from the answers (change report-quotes-from-answers, #749): where it came
                # from, and whether the author has cut it since (`quotes.mark_origins` decides).
                quote['ref'] = ref
                if item.get('shortened'):
                    quote['shortened'] = True
            out.append(quote)
        config = {'items': out}
        if raw.get('style') in QUOTE_STYLES and raw.get('style') != 'list':
            config['style'] = raw['style']
        return config
    if block_type == 'map':
        # Individual marks instead of the grid: the survey owner's choice (owner, 2026-11-16).
        return {'marks': True} if raw.get('marks') else {}
    if block_type == 'crosstab':
        # How the cross-tab is drawn (change crosstab-settings-in-block, #751). No `view`: a block
        # made before the settings, drawn as the table it always was.
        out = {}
        if raw.get('view') in XTAB_VIEWS:
            out['view'] = raw['view']
            out['values'] = raw.get('values') if raw.get('values') in XTAB_VALUES else 'percent'
            if raw.get('sort'):
                out['sort'] = True
        return out
    return {}


def items_from_lines(block_type, text):
    """The editor's textarea as items: one per line, the two parts split by " | ".

    Key numbers: ``447 | residents answered``. Quotes: ``The bridge… | Pin: needs attention``
    (the source is optional)."""
    items = []
    for line in str(text or '').splitlines():
        line = line.strip()
        if not line:
            continue
        left, _sep, right = line.partition(' | ')
        if block_type == 'numbers':
            items.append({'value': left, 'label': right})
        else:
            items.append({'text': left, 'source': right})
    return clean_config(block_type, {'items': items})


def lines_from_items(block_type, config):
    """The inverse of `items_from_lines`, for the editor's textarea."""
    first, second = ('value', 'label') if block_type == 'numbers' else ('text', 'source')
    lines = []
    for item in (config or {}).get('items') or []:
        a, b = str(item.get(first) or ''), str(item.get(second) or '')
        lines.append(f'{a} | {b}' if b else a)
    return '\n'.join(lines)


def clean_width(value):
    return value if value in WIDTHS else 'full'
