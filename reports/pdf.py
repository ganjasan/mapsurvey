"""A report as an A4 PDF (change reports-pdf, #707).

`build_pdf(report, base_url)` lays out the SAME payload the page renders (`render_data`: the live
aggregates, or the frozen snapshot), so a number in the PDF is the number on the page — nothing is
counted here. reportlab draws it, as for the printed survey form: no headless browser on the
server. A map is the Mapbox static image of its extent (`survey.print.static_map`) with the cells
or marks painted over it by Pillow; without a token or on a Mapbox error the cells are drawn on a
plain ground. Every block is kept together on a page, so a chart never splits from its title.

Rendering is slow (one HTTP call per map) and memory-hungry, so it never runs in a web request:
`reports.tasks.render_report_pdf` calls this on the worker and stores the file.
"""
import html as html_lib
import io
import logging
from html.parser import HTMLParser
from xml.sax.saxutils import escape

from django.utils import timezone
from django.utils.translation import gettext as _
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Flowable, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from survey.print import FONT_BOLD, FONT_REGULAR, register_fonts

log = logging.getLogger('reports.pdf')

MARGIN = 18 * mm
# The frame pads its content by 6 pt on each side; tables and drawings are sized to what is left
# so their left edge is the paragraphs'.
WIDTH = A4[0] - 2 * MARGIN - 12
ACCENT = colors.HexColor('#4f46e5')
MUTED = colors.HexColor('#5f6368')
GROUND = colors.HexColor('#f5f6f8')
MAP_W, MAP_H = 900, 520


def _styles():
    base = ParagraphStyle('base', fontName=FONT_REGULAR, fontSize=10.5, leading=15)
    return {
        'base': base,
        'eyebrow': ParagraphStyle('eyebrow', parent=base, fontSize=8, leading=11, textColor=MUTED),
        'title': ParagraphStyle('title', parent=base, fontName=FONT_BOLD, fontSize=22, leading=26, spaceAfter=3 * mm),
        'lead': ParagraphStyle('lead', parent=base, fontSize=12, leading=17, textColor=colors.HexColor('#374151')),
        # keepWithNext: a section's heading never ends a page.
        'heading': ParagraphStyle('heading', parent=base, fontName=FONT_BOLD, fontSize=15, leading=19,
                                  spaceBefore=5 * mm, spaceAfter=3 * mm, keepWithNext=1),
        'block': ParagraphStyle('block', parent=base, fontName=FONT_BOLD, fontSize=11, leading=14, spaceAfter=1.5 * mm),
        'note': ParagraphStyle('note', parent=base, fontSize=8.5, leading=11.5, textColor=MUTED),
        'cell': ParagraphStyle('cell', parent=base, fontSize=9, leading=11.5),
        'cellbold': ParagraphStyle('cellbold', parent=base, fontName=FONT_BOLD, fontSize=9, leading=11.5),
        'big': ParagraphStyle('big', parent=base, fontName=FONT_BOLD, fontSize=16, leading=19),
        'quote': ParagraphStyle('quote', parent=base, fontSize=10.5, leading=15, leftIndent=4 * mm,
                                textColor=colors.HexColor('#1f2937')),
        'list': ParagraphStyle('list', parent=base, leftIndent=6 * mm, bulletIndent=1 * mm, spaceAfter=1 * mm),
    }


def _p(text, style):
    return Paragraph(escape(str(text or '')), style)


class _RichText(HTMLParser):
    """Sanitised creator HTML → paragraphs reportlab can draw: bold, italics, links, lists."""

    INLINE = {'strong': 'b', 'b': 'b', 'em': 'i', 'i': 'i', 'u': 'u'}

    def __init__(self, styles):
        super().__init__(convert_charrefs=True)
        self.styles, self.out, self.buf = styles, [], []
        self.lists, self.counters = [], []

    def _flush(self, bullet=None):
        text = ''.join(self.buf).strip()
        self.buf = []
        if not text:
            return
        if bullet is not None:
            self.out.append(Paragraph(text, self.styles['list'], bulletText=bullet))
        else:
            self.out.append(Paragraph(text, self.styles['base']))
            self.out.append(Spacer(1, 1.5 * mm))

    def handle_starttag(self, tag, attrs):
        if tag in self.INLINE:
            self.buf.append('<%s>' % self.INLINE[tag])
        elif tag == 'a':
            href = dict(attrs).get('href') or ''
            self.buf.append('<a href="%s" color="#4f46e5">' % escape(href, {'"': '&quot;'}))
        elif tag == 'br':
            self.buf.append('<br/>')
        elif tag in ('p', 'li'):
            self._flush()
        elif tag in ('ol', 'ul'):
            self._flush()
            self.lists.append(tag)
            self.counters.append(0)

    def handle_endtag(self, tag):
        if tag in self.INLINE:
            self.buf.append('</%s>' % self.INLINE[tag])
        elif tag == 'a':
            self.buf.append('</a>')
        elif tag == 'p':
            self._flush()
        elif tag == 'li':
            if self.lists and self.lists[-1] == 'ol':
                self.counters[-1] += 1
                self._flush('%d.' % self.counters[-1])
            else:
                self._flush('•')
        elif tag in ('ol', 'ul') and self.lists:
            self._flush()
            self.lists.pop()
            self.counters.pop()
            self.out.append(Spacer(1, 1.5 * mm))

    def handle_data(self, data):
        self.buf.append(escape(data))

    def result(self):
        self._flush()
        return self.out


class _Bars(Flowable):
    """Horizontal bars: label, bar, value — the page's bar chart, drawn."""

    ROW = 6.2 * mm

    def __init__(self, rows, width):
        super().__init__()
        self.rows, self.width = rows, width      # rows: [(label, value | None, display)]
        self.height = self.ROW * len(rows)

    def draw(self):
        c = self.canv
        label_w, value_w = self.width * 0.36, 16 * mm
        bar_w = self.width - label_w - value_w - 4 * mm
        peak = max((value or 0 for _l, value, _d in self.rows), default=0) or 1
        y = self.height - self.ROW
        for label, value, display in self.rows:
            c.setFont(FONT_REGULAR, 9)
            c.setFillColor(colors.HexColor('#1a1d21'))
            text = str(label)
            while c.stringWidth(text, FONT_REGULAR, 9) > label_w - 2 * mm and len(text) > 4:
                text = text[:-2]
            c.drawString(0, y + 1.8 * mm, text if text == str(label) else text + '…')
            c.setFillColor(GROUND)
            c.rect(label_w, y + 1 * mm, bar_w, 3.6 * mm, stroke=0, fill=1)
            if value:
                c.setFillColor(ACCENT)
                c.rect(label_w, y + 1 * mm, bar_w * value / peak, 3.6 * mm, stroke=0, fill=1)
            c.setFillColor(MUTED)
            c.drawRightString(self.width, y + 1.8 * mm, str(display))
            y -= self.ROW


class _Series(Flowable):
    """Opened (light) and answered (dark) per period: the strip of bars under the engagement
    numbers."""

    def __init__(self, points, width, height=22 * mm):
        super().__init__()
        self.points, self.width, self.height = points, width, height

    def draw(self):
        c = self.canv
        peak = max((p['opened']['value'] or 0 for p in self.points), default=0) or 1
        step = self.width / max(1, len(self.points))
        for i, point in enumerate(self.points):
            x = i * step
            for key, color in (('opened', colors.HexColor('#dfe3fb')), ('answered', ACCENT)):
                value = point[key]['value'] or 0
                c.setFillColor(color)
                c.rect(x, 0, max(0.6, step - 1), (self.height - 1) * value / peak, stroke=0, fill=1)


def _table(rows, widths, header=True, bold_last_col=False):
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0, hAlign='LEFT')
    style = [('LINEBELOW', (0, 0), (-1, -1), 0.4, colors.HexColor('#e5e7eb')),
             ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 3),
             ('BOTTOMPADDING', (0, 0), (-1, -1), 3), ('LEFTPADDING', (0, 0), (0, -1), 0)]
    table.setStyle(TableStyle(style))
    return table


def _numbers(items, styles, width):
    """Key numbers: up to four cells in a row."""
    out = []
    for start in range(0, len(items), 4):
        chunk = items[start:start + 4]
        cells = [[_p(i.get('value') if 'value' in i else i.get('display'), styles['big']),
                  _p(i.get('label'), styles['note'])] for i in chunk]
        table = Table([cells], colWidths=[width / len(chunk)] * len(chunk), hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), GROUND), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                   ('LEFTPADDING', (0, 0), (-1, -1), 8), ('TOPPADDING', (0, 0), (-1, -1), 7),
                                   ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
                                   ('LINEAFTER', (0, 0), (-2, -1), 3, colors.white)]))
        out += [table, Spacer(1, 1.5 * mm)]
    return out


# ── maps ──────────────────────────────────────────────────────────────────────

def _extent(features):
    xs, ys = [], []

    def walk(coords):
        if coords and isinstance(coords[0], (int, float)):
            xs.append(coords[0])
            ys.append(coords[1])
        else:
            for part in coords or []:
                walk(part)

    for feature in features:
        walk((feature.get('geometry') or {}).get('coordinates'))
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def map_image(payload, survey=None):
    """A Pillow image of a map block: the basemap of the block's extent with its cells (opacity
    by respondents) or its marks painted over it. None when the block has nothing to draw."""
    from PIL import Image as PilImage
    from PIL import ImageDraw
    from survey.print import static_map
    marks = payload.get('data_type') == 'marks'
    features = ((payload.get('marks') if marks else payload.get('cells')) or {}).get('features') or []
    box = _extent(features)
    if box is None:
        return None
    zoom = min(static_map._zoom_for_bounds(box, MAP_W, MAP_H), 17)
    spec = static_map.FrameSpec(lat=(box[1] + box[3]) / 2, lng=(box[0] + box[2]) / 2, zoom=zoom,
                                basemap=payload.get('basemap') or 'streets', width=MAP_W, height=MAP_H)
    try:
        spec.static_style = static_map.basemap_style(spec.basemap, survey)
        base = static_map.fetch_basemap(spec)
    except Exception:  # noqa: BLE001 — a basemap is decoration; the cells are the content
        log.warning('report pdf: basemap unavailable', exc_info=True)
        base = None
    scale = static_map.SCALE
    size = (MAP_W * scale, MAP_H * scale)
    image = base.resize(size) if base is not None else PilImage.new('RGB', size, '#eef0f3')
    overlay = PilImage.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cx, cy = static_map.project(spec.lng, spec.lat, zoom)

    def px(lng, lat):
        x, y = static_map.project(lng, lat, zoom)
        return ((x - cx + MAP_W / 2) * scale, (y - cy + MAP_H / 2) * scale)

    rgb = static_map._hex(payload.get('color') or '#4f46e5')[:3]
    peak = payload.get('max') or 1
    for feature in features:
        geometry = feature.get('geometry') or {}
        kind, coords = geometry.get('type'), geometry.get('coordinates')
        if kind == 'Polygon' and not marks:
            share = ((feature.get('properties') or {}).get('respondents') or 0) / peak
            draw.polygon([px(x, y) for x, y in coords[0]], fill=rgb + (int(255 * (0.18 + 0.6 * share)),))
        elif kind == 'Point':
            x, y = px(*coords[:2])
            draw.ellipse([x - 7, y - 7, x + 7, y + 7], fill=rgb + (200,), outline=(255, 255, 255, 255), width=2)
        elif kind == 'MultiPoint':
            for point in coords:
                x, y = px(*point[:2])
                draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=rgb + (110,))
        elif kind == 'LineString':
            draw.line([px(x, y) for x, y in coords], fill=rgb + (170,), width=5)
        elif kind == 'Polygon':
            draw.polygon([px(x, y) for x, y in coords[0]], fill=rgb + (40,), outline=rgb + (190,))
    image = PilImage.alpha_composite(image.convert('RGBA'), overlay).convert('RGB')
    return image


def _picture(image, width, max_height=95 * mm):
    w, h = image.size
    height = width * h / w
    if height > max_height:
        width, height = width * max_height / height, max_height
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG', quality=86)
    buffer.seek(0)
    return Image(buffer, width=width, height=height)


# ── blocks ────────────────────────────────────────────────────────────────────

def _block(payload, block, styles, width, survey):
    """The flowables of one payload."""
    kind = payload.get('block_type')
    out = []
    title = payload.get('title')
    if kind == 'heading':
        return [_p(title, styles['heading'])]
    if title:
        out.append(_p(title, styles['block']))
    if kind == 'text':
        parser = _RichText(styles)
        parser.feed(payload.get('html') or '<p>%s</p>' % html_lib.escape(payload.get('body') or ''))
        out += parser.result()
    elif kind == 'image':
        if block is not None and block.image:
            from PIL import Image as PilImage
            try:
                with block.image.open('rb') as handle:
                    out.append(_picture(PilImage.open(io.BytesIO(handle.read())).convert('RGB'), width))
            except Exception:  # noqa: BLE001 — a missing file is a missing picture, not a failed PDF
                log.warning('report pdf: picture of block %s unreadable', block.pk)
        if payload.get('caption'):
            out.append(_p(payload['caption'], styles['note']))
    elif kind == 'numbers':
        out += _numbers(payload.get('items') or [], styles, width)
        if payload.get('note'):
            out.append(_p(payload['note'], styles['note']))
    elif kind == 'quotes':
        for item in payload.get('items') or []:
            out.append(_p('“%s”' % item.get('text', ''), styles['quote']))
            if item.get('source'):
                out.append(Paragraph(escape(item['source']), ParagraphStyle('src', parent=styles['note'], leftIndent=4 * mm)))
            out.append(Spacer(1, 2 * mm))
    elif kind == 'chart' and payload.get('data_type') == 'choices':
        out.append(_Bars([(i['label'], i.get('value'), i['display']) for i in payload.get('items') or []], width))
    elif kind == 'chart' and payload.get('data_type') == 'number' and payload.get('count'):
        out += _numbers([{'value': payload['count'], 'label': _('answers')}, {'value': payload['avg'], 'label': _('average')},
                         {'value': payload['median'], 'label': _('median')},
                         {'value': '%s – %s' % (payload['min_val'], payload['max_val']), 'label': _('range')}],
                        styles, width)
        out.append(_Bars(list(zip(payload.get('hist_labels') or [], payload.get('hist_counts') or [],
                                  payload.get('hist_counts') or [])), width))
    elif kind == 'engagement':
        data = payload.get('data') or {}
        labels = {'opened': _('opened the survey'), 'answered': _('answered'), 'finished': _('finished')}
        out += _numbers([{'value': s['display'], 'label': labels.get(s['key'], s['key'])} for s in data.get('steps') or []],
                        styles, width)
        if len(data.get('series') or []) > 1:
            period = {'day': _('per day'), 'week': _('per week'), 'month': _('per month')}.get(data.get('period'), '')
            out.append(Spacer(1, 2 * mm))
            out.append(_Series(data['series'], width))
            out.append(_p('%s – %s · %s: %s' % (data.get('first'), data.get('last'), period,
                                                 _('opened, and answered (dark)')), styles['note']))
    elif kind == 'crosstab':
        data = payload.get('data') or {}
        columns = (data.get('columns') or {}).get('items') or []
        first = width * 0.32
        rest = (width - first) / (len(columns) + 1)
        rows = [[_p((data.get('rows') or {}).get('name'), styles['cellbold'])]
                + [_p(c['label'], styles['cellbold']) for c in columns] + [_p(_('Total'), styles['cellbold'])]]
        for line in payload.get('table') or []:
            rows.append([_p(line['item']['label'], styles['cell'])]
                        + [_p(c['display'], styles['cell']) for c in line['cells']]
                        + [_p(line['item']['total']['display'], styles['cellbold'])])
        rows.append([_p(_('Total'), styles['cellbold'])] + [_p(c['total']['display'], styles['cellbold']) for c in columns]
                    + [_p((data.get('respondents') or {}).get('display'), styles['cellbold'])])
        out.append(_table(rows, [first] + [rest] * (len(columns) + 1)))
        out.append(_p(_('People who answered both questions. Groups too small to show read “<%(k)s”.')
                      % {'k': payload.get('k')}, styles['note']))
    elif kind == 'map':
        image = map_image(payload, survey)
        if image is not None:
            out.append(_picture(image, width))
        marks = payload.get('data_type') == 'marks'
        line = (_('%(n)s marks from %(p)s respondents') % {'n': payload.get('count'), 'p': payload.get('respondents_total')}
                if marks else _('%(p)s respondents; darker squares were marked by more people')
                % {'p': payload.get('respondents_total')})
        out.append(_p(' · '.join(x for x in (payload.get('description'), line, payload.get('note'),
                                             '© Mapbox © OpenStreetMap' if image is not None else '') if x),
                      styles['note']))
    elif kind == 'budget' and payload.get('budget'):
        out.append(_Bars([(r['name'], None if r['masked'] else r['percent'],
                           '<%s' % payload.get('k') if r['masked'] else '%s%%' % r['percent'])
                          for r in payload['budget']['rows']], width))
    elif kind == 'objects':
        rows = [[_p(_('Object'), styles['cellbold']), _p(_('Answers'), styles['cellbold'])]]
        rows += [[_p(r['title'] or r['key'], styles['cell']), _p(r['answers']['display'], styles['cell'])]
                 for r in (payload.get('rows') or [])[:60]]
        out.append(_table(rows, [width * 0.75, width * 0.25]))
    return out


def build_pdf(report, base_url='', lang='en'):
    """The report's PDF as bytes: the page's own payload on A4, the address and page numbers in
    the footer."""
    from reports.render import build_context
    register_fonts()
    styles = _styles()
    context = build_context(report, lang=lang)
    blocks = {b.pk: b for b in report.blocks.all()}
    survey = report.survey if report.survey_id else None
    address = '%s/r/%s/' % (base_url.rstrip('/'), report.slug) if base_url else '/r/%s/' % report.slug
    stamp = (_('Data as of %(date)s') % {'date': context['frozen_at'].strftime('%d %b %Y')}
             if context.get('frozen') and context.get('frozen_at')
             else _('Printed %(date)s') % {'date': timezone.localtime().strftime('%d %b %Y')})

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(FONT_REGULAR, 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, 10 * mm, address)
        canvas.drawRightString(A4[0] - MARGIN, 10 * mm, '%s · %s' % (stamp, _('page %(n)s') % {'n': doc.page}))
        canvas.restoreState()

    story = []
    if context.get('intro_eyebrow'):
        story.append(_p(context['intro_eyebrow'].upper(), styles['eyebrow']))
    story.append(_p(context['intro_title'], styles['title']))
    if context.get('intro_body'):
        story.append(_p(context['intro_body'], styles['lead']))
    story.append(Spacer(1, 5 * mm))
    pending = []        # a heading waits for the block after it: the two share a page
    for row in context['rows']:
        if len(row) == 2:
            gap = 6 * mm
            half = (WIDTH - gap) / 2
            cells = [_block(payload, blocks.get(payload.get('id')), styles, half, survey) for payload in row]
            table = Table([cells], colWidths=[half + gap / 2, half + gap / 2], hAlign='LEFT')
            table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (0, -1), 0),
                                       ('RIGHTPADDING', (-1, 0), (-1, -1), 0), ('TOPPADDING', (0, 0), (-1, -1), 0)]))
            story += [KeepTogether(pending + [table]), Spacer(1, 5 * mm)]
            pending = []
            continue
        flowables = _block(row[0], blocks.get(row[0].get('id')), styles, WIDTH, survey)
        if row[0].get('block_type') == 'heading':
            pending += flowables
        elif flowables:
            story += [KeepTogether(pending + flowables), Spacer(1, 4 * mm)]
            pending = []
    story += pending
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=16 * mm,
                            bottomMargin=18 * mm, title=context['intro_title'], author='Mapsurvey')
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
