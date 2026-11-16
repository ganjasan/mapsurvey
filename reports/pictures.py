"""A block as a PNG with its title (change reports-embed, #708).

For slides and documents: the chart or map of one block, drawn by Pillow from the block's payload
— the same masked numbers the page shows. A map is `reports.pdf.map_image` (static basemap plus
cells or marks); a chart is bars; a cross-tab is its table. No headless browser.
"""
import io

from PIL import Image, ImageDraw

WIDTH = 1200
PAD = 48
INK, MUTED, ACCENT, GROUND = '#1a1d21', '#5f6368', '#4f46e5', '#eef0f3'
PICTURE_BLOCK_TYPES = ('chart', 'map', 'crosstab', 'engagement', 'budget')


def _fonts():
    from survey.print.static_map import _font
    return {'title': _font(34), 'text': _font(24), 'small': _font(19)}


def _fit(draw, text, font, width):
    text = str(text)
    if draw.textlength(text, font=font) <= width:
        return text
    while len(text) > 3 and draw.textlength(text + '…', font=font) > width:
        text = text[:-1]
    return text + '…'


def _bars(rows):
    """[(label, value | None, display)] as horizontal bars."""
    fonts = _fonts()
    row_h = 52
    image = Image.new('RGB', (WIDTH, max(1, len(rows)) * row_h), 'white')
    draw = ImageDraw.Draw(image)
    label_w, value_w = 380, 110
    bar_w = WIDTH - 2 * PAD - label_w - value_w
    peak = max((value or 0 for _l, value, _d in rows), default=0) or 1
    for i, (label, value, display) in enumerate(rows):
        y = i * row_h
        draw.text((PAD, y + 10), _fit(draw, label, fonts['text'], label_w - 16), font=fonts['text'], fill=INK)
        x0 = PAD + label_w
        draw.rectangle([x0, y + 12, x0 + bar_w, y + 40], fill=GROUND)
        if value:
            draw.rectangle([x0, y + 12, x0 + bar_w * value / peak, y + 40], fill=ACCENT)
        text = str(display)
        draw.text((WIDTH - PAD - draw.textlength(text, font=fonts['text']), y + 10), text, font=fonts['text'], fill=MUTED)
    return image


def _table(rows):
    fonts = _fonts()
    row_h = 46
    columns = max(len(r) for r in rows)
    first_w = 340
    col_w = (WIDTH - 2 * PAD - first_w) / max(1, columns - 1)
    image = Image.new('RGB', (WIDTH, len(rows) * row_h + 4), 'white')
    draw = ImageDraw.Draw(image)
    for r, row in enumerate(rows):
        y = r * row_h
        for c, value in enumerate(row):
            x = PAD if c == 0 else PAD + first_w + (c - 1) * col_w
            width = first_w - 12 if c == 0 else col_w - 12
            draw.text((x, y + 10), _fit(draw, value, fonts['small'], width), font=fonts['small'],
                      fill=INK if r and c else MUTED if not r else INK)
        draw.line([PAD, y + row_h, WIDTH - PAD, y + row_h], fill='#e5e7eb', width=1)
    return image


def _body(payload, survey):
    from reports.tables import rows_of
    kind = payload.get('block_type')
    if kind == 'map':
        from reports.pdf import map_image
        image = map_image(payload, survey)
        if image is None:
            return None
        ratio = (WIDTH - 2 * PAD) / image.size[0]
        inner = image.resize((WIDTH - 2 * PAD, int(image.size[1] * ratio)))
        canvas = Image.new('RGB', (WIDTH, inner.size[1]), 'white')
        canvas.paste(inner, (PAD, 0))
        return canvas
    if kind == 'chart' and payload.get('data_type') == 'choices':
        return _bars([(i['label'], i.get('value'), i['display']) for i in payload.get('items') or []])
    if kind == 'chart' and payload.get('data_type') == 'number':
        return _bars(list(zip(payload.get('hist_labels') or [], payload.get('hist_counts') or [],
                              payload.get('hist_counts') or [])))
    if kind == 'engagement':
        steps = (payload.get('data') or {}).get('steps') or []
        return _bars([(s['key'], s.get('value'), s['display']) for s in steps])
    if kind == 'budget' and payload.get('budget'):
        return _bars([(r['name'], None if r['masked'] else r['percent'],
                       '<%s' % payload.get('k') if r['masked'] else '%s%%' % r['percent'])
                      for r in payload['budget']['rows']])
    if kind == 'crosstab':
        rows = rows_of(payload)
        return _table(rows) if rows else None
    return None


def caption_of(payload):
    kind = payload.get('block_type')
    if kind == 'map' and payload.get('data_type') == 'marks':
        return '%s marks · %s respondents · © Mapbox © OpenStreetMap' % (payload.get('count'), payload.get('respondents_total'))
    if kind == 'map':
        return ' · '.join(x for x in (payload.get('description'),
                                      '%s respondents; darker squares were marked by more people'
                                      % payload.get('respondents_total'), '© Mapbox © OpenStreetMap') if x)
    if kind == 'chart' and payload.get('data_type') == 'choices':
        return '%s answers' % payload.get('total_answers', '')
    if kind == 'crosstab':
        return 'People who answered both questions. Groups too small to show read “<%s”.' % payload.get('k')
    return ''


def block_png(payload, survey=None):
    """PNG bytes of a block — title, picture, caption — or None for a block with nothing to draw."""
    body = _body(payload, survey)
    if body is None:
        return None
    fonts = _fonts()
    probe = ImageDraw.Draw(body)
    title = _fit(probe, payload.get('title') or '', fonts['title'], WIDTH - 2 * PAD)
    caption = _fit(probe, caption_of(payload), fonts['small'], WIDTH - 2 * PAD)
    top = PAD + (58 if title else 0)
    bottom = (44 if caption else 0) + PAD
    image = Image.new('RGB', (WIDTH, top + body.size[1] + bottom), 'white')
    image.paste(body, (0, top))
    draw = ImageDraw.Draw(image)
    if title:
        draw.text((PAD, PAD - 8), title, font=fonts['title'], fill=INK)
    if caption:
        draw.text((PAD, top + body.size[1] + 12), caption, font=fonts['small'], fill=MUTED)
    buffer = io.BytesIO()
    image.save(buffer, format='PNG', optimize=True)
    return buffer.getvalue()
