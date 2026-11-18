"""What the author writes into a story (change reports-story, #704).

A linear story is headings, text, pictures, key numbers and quotes between the blocks that show
data. Nothing here is computed: numbers and quotes are typed (or pasted) by the author — the owner
allowed typed numbers on 2026-11-16, because a report made by hand has to stay editable. Every
value passes through here on its way in, from the editor and from an imported report file alike.
"""
import re

from reports.models import MAX_ITEMS, WIDTH_CHOICES

WIDTHS = tuple(w for w, _label in WIDTH_CHOICES)
MAX_VALUE = 40
MAX_LABEL = 120
MAX_QUOTE = 1000
MAX_SOURCE = 160


QUOTE_STYLES = ('list', 'pull', 'cards')
XTAB_VIEWS = ('bars', 'stacked', 'ranking', 'table')
XTAB_VALUES = ('percent', 'count')
# How a map block is drawn (change report-map-views): soft shading, numbered hot spots (point
# questions), the squares that count respondents, or the marks themselves.
MAP_VIEWS = ('heat', 'hotspots', 'squares', 'marks')
# A view's own settings and what each may be; the first of MAP_OPT_DEFAULTS is what a layer has
# until its author says otherwise. `top` 0 = every hot spot; `place` is metres.
MAP_OPTS = {'spread': ('tight', 'medium', 'wide'), 'strength': (1, 2, 3, 4, 5), 'top': (5, 10, 0),
            'place': (60, 120, 300), 'cell': ('auto', 'finer', 'coarser'), 'size': ('s', 'm', 'l')}
MAP_OPT_DEFAULTS = {'spread': 'medium', 'strength': 3, 'top': 5, 'place': 120, 'cell': 'auto', 'size': 'm'}
# Layers a map takes beside its own question.
MAX_MAP_LAYERS = 3
# The colour of a layer whose author picked none, by its place in the list.
MAP_LAYER_COLORS = ('#2563eb', '#0f766e', '#7c3aed')


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
        # How the map is drawn (change report-map-views). No `view`: a block made before, squares
        # or — with `marks` — the marks. `marks` is the survey owner's choice (owner, 2026-11-16):
        # the marks themselves leave the workspace, as marks or as the heat and hot spots made of
        # every one of them; the view `marks` cannot be had without it.
        # The block's own question is its first layer; `layers` are the others drawn on the same
        # map (change report-map-views): another map question, by survey and code.
        out = clean_map_look(raw)
        frame = clean_frame(raw.get('frame'))
        if frame:
            out['frame'] = frame
        for key in ('legend', 'scale'):        # on unless switched off
            if raw.get(key) is False:
                out[key] = False
        if raw.get('toggle'):                   # readers may switch layers on and off
            out['toggle'] = True
        layers, seen = [], set()
        for layer in raw.get('layers') or []:
            if not isinstance(layer, dict) or len(layers) >= MAX_MAP_LAYERS:
                continue
            layer_id, code = str(layer.get('id') or ''), str(layer.get('code') or '')[:50]
            if not re.fullmatch(r'[a-z0-9]{1,8}', layer_id) or layer_id in seen or not code:
                continue
            seen.add(layer_id)
            entry = {'id': layer_id, 'survey': str(layer.get('survey') or '')[:40], 'code': code}
            entry.update(clean_map_look(layer))
            fields = [str(c)[:50] for c in (layer.get('fields') or []) if c][:20]
            if fields:
                entry['fields'] = fields
            layers.append(entry)
        if layers:
            out['layers'] = layers
        return out
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


def clean_map_opts(raw):
    """A view's own settings, defaults left out: heat `spread` and `strength`; hot spots `top`
    (how many are numbered), `place` (metres that count as one place), `list` and `shade`;
    squares `cell`; marks `size` and `solid`."""
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    for key, allowed in MAP_OPTS.items():
        value = raw.get(key)
        if isinstance(allowed[0], int) and not isinstance(value, bool):
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
        if value in allowed and value != MAP_OPT_DEFAULTS[key]:
            out[key] = value
    for key in ('list', 'shade'):               # on unless switched off
        if raw.get(key) is False:
            out[key] = False
    if raw.get('solid'):                        # marks drawn opaque
        out['solid'] = True
    return out


def clean_map_look(raw):
    """How one layer of a map is drawn: `view`, `marks` (every mark leaves the workspace — the
    Marks view cannot be had without it), `color`, `name` (in the legend) and the view's `opts`."""
    out = {}
    if raw.get('view') in MAP_VIEWS:
        out['view'] = raw['view']
    if raw.get('marks') or out.get('view') == 'marks':
        out['marks'] = True
    color = str(raw.get('color') or '')
    if re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        out['color'] = color.lower()
    name = _text(raw.get('name'), 80)
    if name:
        out['name'] = name
    opts = clean_map_opts(raw.get('opts'))
    if opts:
        out['opts'] = opts
    return out


def map_opts(look):
    """A layer's view settings with the defaults filled in."""
    opts = dict(MAP_OPT_DEFAULTS, list=True, shade=True, solid=False)
    opts.update((look or {}).get('opts') or {})
    return opts


def clean_frame(value):
    """[west, south, east, north] in degrees — the part of the map the author framed — or None.
    Takes the list or the "w,s,e,n" text the editor posts."""
    if isinstance(value, str):
        value = [part for part in value.split(',') if part.strip()]
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        west, south, east, north = (round(float(v), 6) for v in value)
    except (TypeError, ValueError):
        return None
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        return None
    return [west, south, east, north]


def map_view(config, input_type):
    """The view a map block is drawn in: the author's, when the question's type has it; a block
    made before the views keeps what it showed — the marks or the squares."""
    config = config or {}
    view = config.get('view')
    if view == 'hotspots' and input_type != 'point':
        view = 'heat'
    if view in MAP_VIEWS:
        return view
    return 'marks' if config.get('marks') else 'squares'


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
