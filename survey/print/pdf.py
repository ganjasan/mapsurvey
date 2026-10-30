"""The paper form of a survey as a PDF (spec printable-form; design D1, D2, D5–D7).

`build_form(survey, language, paper, user=…, base_url=…)` walks the survey the
way the respondent page does — sections in chain order, `group_runs`, the
`respondent` surface of the visibility engine — and renders one flowable per
item through `QUESTION_SHAPES`. A map section prints its frame
(`static_map.render_frame`) with a letter legend and the sub-question tables.
Every page gets four alignment marks, the form code (text + QR) and
"page N of M" from `_NumberedCanvas`, which knows the page count at save time.

The identity of the print is a `PrintedForm` row (D6): created before the
document is laid out (the footer needs its code), updated with the page count
and the map-frame layout after. The fixed strings go through gettext under
`translation.override(language)`, so they come from the respondent catalogs.
"""
import hashlib
import html
import io
import json
import re
import string
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

from django.conf import settings
from django.utils import translation
from django.utils.html import strip_tags
from django.utils.translation import gettext as _
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, KeepTogether, PageBreak, PageTemplate, Paragraph, Spacer, Table,
    TableStyle,
)

from survey.layers import layer_lite
from survey.models import PrintedForm, TrackedLink
from survey.print import FONT_BOLD, FONT_REGULAR, register_fonts
from survey.print import form_code, static_map
from survey.print.structure import plan_items
from survey.question_types import GEO_TYPES, THUMBS_CHOICES
from survey.versioning import canonical_of
from survey.visibility import describe_rule

PAPERS = {PrintedForm.PAPER_A4: A4, PrintedForm.PAPER_LETTER: letter}
MARGIN = 15 * mm
MARK_SIZE = 6 * mm
MARK_INSET = 8 * mm
FOOTER_H = 14 * mm
QR_MM = 16
BOX = '☐'
SYMBOLS = {'point': '●', 'line': '━', 'polygon': '▭', 'spraycan': '░'}
DEFAULT_MARKS = 3
MAX_OBJECT_ROWS = 60
WATERMARK_STATUSES = ('draft', 'testing')


# ── styles ─────────────────────────────────────────────────────────────────

def _styles():
    base = ParagraphStyle('base', fontName=FONT_REGULAR, fontSize=10, leading=13, alignment=TA_LEFT)
    return {
        'base': base,
        'title': ParagraphStyle('title', parent=base, fontName=FONT_BOLD, fontSize=16, leading=20, spaceAfter=2 * mm),
        'section': ParagraphStyle('section', parent=base, fontName=FONT_BOLD, fontSize=13, leading=16,
                                  spaceBefore=4 * mm, spaceAfter=1.5 * mm),
        'group': ParagraphStyle('group', parent=base, fontName=FONT_BOLD, fontSize=11, leading=14, spaceBefore=3 * mm),
        'question': ParagraphStyle('question', parent=base, fontName=FONT_BOLD, fontSize=10.5, leading=13.5,
                                   spaceBefore=3 * mm),
        'help': ParagraphStyle('help', parent=base, fontSize=8.5, leading=11, textColor=colors.HexColor('#444444')),
        'note': ParagraphStyle('note', parent=base, fontSize=8.5, leading=11, textColor=colors.HexColor('#7a4b00')),
        'option': ParagraphStyle('option', parent=base, fontSize=10, leading=14),
        'small': ParagraphStyle('small', parent=base, fontSize=7.5, leading=9.5, textColor=colors.HexColor('#555555')),
        'cell': ParagraphStyle('cell', parent=base, fontSize=8.5, leading=10.5),
        'cellhead': ParagraphStyle('cellhead', parent=base, fontName=FONT_BOLD, fontSize=8.5, leading=10.5),
    }


def plain(text):
    """Creator rich text → one plain line (tags stripped, entities decoded, spaces collapsed)."""
    if not text:
        return ''
    text = html.unescape(strip_tags(str(text).replace('</p>', ' ').replace('<br>', ' ').replace('<br/>', ' ')))
    return re.sub(r'\s+', ' ', text).strip()


def para(text, style):
    return Paragraph(escape(text or ''), style)


# ── flowables ──────────────────────────────────────────────────────────────

class RuledLines(Flowable):
    """`count` horizontal lines to write on, 7 mm apart."""

    def __init__(self, count=1, width=0, gap=7 * mm):
        super().__init__()
        self.count, self._w, self.gap = max(1, count), width, gap

    def wrap(self, availWidth, availHeight):
        self._w = self._w or availWidth
        return self._w, self.count * self.gap + 1 * mm

    def draw(self):
        c = self.canv
        c.setStrokeColor(colors.HexColor('#777777'))
        c.setLineWidth(0.5)
        for i in range(self.count):
            y = (self.count - i - 1) * self.gap + 1 * mm
            c.line(0, y, self._w, y)


class Boxes(Flowable):
    """A row of `count` empty boxes (digits, a date), `size` mm each."""

    def __init__(self, count, size=7, labels=None):
        super().__init__()
        self.count, self.size, self.labels = count, size * mm, labels or []

    def wrap(self, availWidth, availHeight):
        self._w = self.count * self.size + 2 * mm
        return self._w, self.size + (3.5 * mm if self.labels else 1 * mm)

    def draw(self):
        c = self.canv
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.6)
        bottom = 3 * mm if self.labels else 0.5 * mm
        for i in range(self.count):
            c.rect(i * self.size, bottom, self.size, self.size)
            if i < len(self.labels) and self.labels[i]:
                c.setFont(FONT_REGULAR, 6.5)
                c.drawCentredString(i * self.size + self.size / 2, 0.5 * mm, self.labels[i])


class MapFrame(Flowable):
    """The section map image; on draw it reports its page and rectangle (mm from
    the top-left corner of the page) into `records`, keyed by page number."""

    def __init__(self, frame, width, records, page_height):
        super().__init__()
        self.frame = frame
        self._w = width
        img = frame.image
        self._h = width * img.height / img.width
        self.records = records
        self.page_height = page_height

    def wrap(self, availWidth, availHeight):
        return self._w, self._h

    def draw(self):
        c = self.canv
        c.drawImage(ImageReader(self.frame.image), 0, 0, width=self._w, height=self._h)
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.8)
        c.rect(0, 0, self._w, self._h)
        x, y = c.absolutePosition(0, 0)
        spec = self.frame.spec
        # setdefault: the page's entry may already hold `items` (ItemMarker).
        self.records.setdefault(str(c.getPageNumber()), {})['map'] = {
            'x_mm': round(x / mm, 2),
            'y_mm': round((self.page_height - y - self._h) / mm, 2),
            'w_mm': round(self._w / mm, 2),
            'h_mm': round(self._h / mm, 2),
            'bbox': spec.bounds,
            'zoom': spec.zoom,
            'basemap': spec.basemap if self.frame.basemap_ok else None,
            'section_code': spec.section_code,
        }


class ItemMarker(Flowable):
    """Zero-height flowable that records, at draw time, which page an item
    starts on: `records[page]["items"]` gets `section:<code>`, `group:<code>` or
    `question:<code>` in drawing order (change paper-photo-entry, #495). It
    travels inside the item's KeepTogether so it can never land on the page
    before the heading it marks. Draw time, not layout time, because platypus
    may wrap a flowable on one page and move it to the next."""

    def __init__(self, key, records):
        super().__init__()
        self.key = key
        self.records = records

    def wrap(self, availWidth, availHeight):
        return 0, 0

    def draw(self):
        items = self.records.setdefault(str(self.canv.getPageNumber()), {}).setdefault('items', [])
        if self.key not in items:
            items.append(self.key)


# ── page decoration ────────────────────────────────────────────────────────

@dataclass
class PageChrome:
    form_id: int
    title: str
    page_size: tuple
    watermark: str = ''
    online_qr: 'Image.Image | None' = None   # noqa: F821 — Pillow image for page 1
    online_label: str = ''
    office_label: str = ''
    page_label: str = 'Page %(n)s of %(total)s'


class _NumberedCanvas(rl_canvas.Canvas):
    """Draws the page chrome once the page count is known (the "of M" and the QR
    payload both need it). Standard reportlab recipe: states are collected in
    showPage() and replayed in save()."""
    chrome: PageChrome = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_states = []

    def showPage(self):
        self._saved_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_states)
        for state in self._saved_states:
            self.__dict__.update(state)
            self._decorate(self._pageNumber, total)
            super().showPage()
        super().save()

    def _decorate(self, page, total):
        chrome = self.chrome
        w, h = chrome.page_size
        self.saveState()
        # Alignment marks (D7): four filled squares, 8 mm from the corners.
        self.setFillColor(colors.black)
        for x in (MARK_INSET, w - MARK_INSET - MARK_SIZE):
            for y in (MARK_INSET, h - MARK_INSET - MARK_SIZE):
                self.rect(x, y, MARK_SIZE, MARK_SIZE, stroke=0, fill=1)
        # Header: the survey title, small.
        self.setFont(FONT_REGULAR, 7.5)
        self.setFillColor(colors.HexColor('#555555'))
        self.drawString(MARGIN + 4 * mm, h - MARGIN + 3 * mm, chrome.title[:90])
        # Footer: form code text left, page count centre, QR right.
        code_text = form_code.page_text(chrome.form_id, page)
        self.setFont(FONT_BOLD, 9)
        self.setFillColor(colors.black)
        self.drawString(MARGIN + 4 * mm, MARK_INSET + 1 * mm, code_text)
        self.setFont(FONT_REGULAR, 8)
        self.drawCentredString(w / 2, MARK_INSET + 1 * mm, chrome.page_label % {'n': page, 'total': total})
        qr = form_code.qr_image(form_code.qr_payload(chrome.form_id, page, total), px=256)
        size = QR_MM * mm
        self.drawImage(ImageReader(qr), w - MARGIN - size - 4 * mm, MARK_INSET - 1 * mm, width=size, height=size)
        if chrome.watermark:
            self.saveState()
            self.setFont(FONT_BOLD, 54)
            self.setFillColor(colors.Color(0.5, 0.5, 0.5, alpha=0.18))
            self.translate(w / 2, h / 2)
            self.rotate(35)
            self.drawCentredString(0, 0, chrome.watermark)
            self.restoreState()
        self.restoreState()


# ── question shapes ────────────────────────────────────────────────────────

@dataclass
class Ctx:
    lang: str
    styles: dict
    width: float
    letters: dict = field(default_factory=dict)   # question id -> letter (geo questions of the section)


def _question_header(q, ctx, prefix=''):
    name = plain(q.get_translated_name(ctx.lang)) or q.code
    star = ' <font color="#c00000">*</font>' if q.required and q.input_type != 'layer_objects' else ''
    out = [Paragraph(f'{escape(prefix)}{escape(name)}{star}', ctx.styles['question'])]
    sub = plain(q.get_translated_subtext(ctx.lang))
    if sub and q.input_type != 'html':
        out.append(para(sub, ctx.styles['help']))
    return out


def _options(q, ctx, hint):
    out = [para(hint, ctx.styles['help'])] if hint else []
    other = q.other_choice_code()
    for choice in q.choices or []:
        code = choice.get('code')
        label = plain(q.get_choice_name(code, ctx.lang))
        if other is not None and code == other:
            out.append(Paragraph(f'{BOX} {escape(label)}: ' + '_' * 34, ctx.styles['option']))
        else:
            out.append(Paragraph(f'{BOX} {escape(label)}', ctx.styles['option']))
    return out


def shape_text(q, ctx):
    return [RuledLines(4)]


def shape_text_line(q, ctx):
    return [RuledLines(1)]


def shape_number(q, ctx):
    return [Spacer(1, 1 * mm), Boxes(8)]


def shape_choice(q, ctx):
    return _options(q, ctx, _('Choose one'))


def shape_multichoice(q, ctx):
    return _options(q, ctx, _('Choose all that apply'))


def shape_range(q, ctx):
    codes = [c.get('code') for c in (q.choices or []) if isinstance(c.get('code'), int)]
    if not codes:
        return [RuledLines(1)]
    lo, hi = min(codes), max(codes)
    values = list(range(lo, hi + 1))
    if len(values) > 12:
        return [Paragraph(f'{lo} … {hi}: ' + '_' * 12, ctx.styles['option'])]
    return [Spacer(1, 1 * mm), Boxes(len(values), size=8, labels=[str(v) for v in values])]


def shape_rating(q, ctx):
    stars = len(q.choices or []) or 5
    return [Spacer(1, 1 * mm), Boxes(stars, size=8, labels=[str(i) for i in range(1, stars + 1)])]


def shape_thumbs(q, ctx):
    up, down = THUMBS_CHOICES[0]['code'], THUMBS_CHOICES[1]['code']
    return [Paragraph(f'{BOX} ▲ {escape(plain(q.get_choice_name(up, ctx.lang)))}'
                      f'&nbsp;&nbsp;&nbsp;&nbsp;{BOX} ▼ {escape(plain(q.get_choice_name(down, ctx.lang)))}',
                      ctx.styles['option'])]


def shape_datetime(q, ctx):
    return [para(_('Date/Time'), ctx.styles['help']), Spacer(1, 0.5 * mm),
            Paragraph('__ __ / __ __ / __ __ __ __ &nbsp;&nbsp; __ __ : __ __', ctx.styles['option'])]


def shape_ranking(q, ctx):
    out = [para(_('Write 1 for your first choice, 2 for your second, and so on.'), ctx.styles['help'])]
    for choice in q.choices or []:
        out.append(Paragraph(f'___ &nbsp; {escape(plain(q.get_choice_name(choice.get("code"), ctx.lang)))}',
                             ctx.styles['option']))
    return out


def shape_html(q, ctx):
    return [para(plain(q.get_translated_subtext(ctx.lang)), ctx.styles['base'])]


def shape_image(q, ctx):
    try:
        from reportlab.platypus import Image as RLImage
        from PIL import Image as PILImage
        with q.image.open('rb') as fh:
            img = PILImage.open(fh)
            img.load()
        ratio = img.height / img.width
        width = min(ctx.width, 120 * mm)
        img = img.convert('RGB')
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=80)
        buf.seek(0)
        return [RLImage(buf, width=width, height=width * ratio)]
    except Exception:  # noqa: BLE001 — a missing picture must not cost the form
        return []


def shape_file(q, ctx):
    return [para(_('Online only'), ctx.styles['note'])]


def _how_to_mark(q, letter):
    """The one-sentence instruction for a geo question, with its symbol in front."""
    how = {
        'point': _('Draw a dot and write the letter %(letter)s next to it'),
        'line': _('Draw the line and write the letter %(letter)s at its start'),
        'polygon': _('Outline the area and write the letter %(letter)s inside it'),
        'spraycan': _('Shade the area and write the letter %(letter)s next to it'),
    }.get(q.input_type, _('Draw a dot and write the letter %(letter)s next to it')) % {'letter': letter}
    return f'{SYMBOLS.get(q.input_type, "●")}  {how}'


def shape_geo(q, ctx):
    letter = ctx.letters.get(q.id, '?')
    return [para(_('Mark on the map') + f' ({letter}). ' + _how_to_mark(q, letter), ctx.styles['note'])]


def shape_layer_objects(q, ctx):
    return []   # the objects table prints with the map block


def shape_unknown(q, ctx):
    return [RuledLines(4)]


QUESTION_SHAPES = {
    'text': shape_text, 'text_line': shape_text_line, 'number': shape_number,
    'choice': shape_choice, 'multichoice': shape_multichoice, 'range': shape_range,
    'rating': shape_rating, 'thumbs': shape_thumbs, 'datetime': shape_datetime,
    'ranking': shape_ranking, 'html': shape_html, 'image': shape_image,
    'photo': shape_file, 'audio': shape_file, 'document': shape_file,
    'point': shape_geo, 'line': shape_geo, 'polygon': shape_geo, 'spraycan': shape_geo,
    'layer_objects': shape_layer_objects,
}


def _rule_note(kind, host, survey, ctx):
    info = describe_rule(kind, host, survey)
    if not info or info['broken'] or not info['label']:
        return []
    condition = info['label'][3:] if info['label'].startswith('if ') else info['label']
    return [para(_('Answer only if %(condition)s') % {'condition': condition}, ctx.styles['note'])]


def question_block(q, ctx, survey, records=None):
    parts = [ItemMarker(f'question:{q.code}', records)] if records is not None else []
    parts += _question_header(q, ctx) if q.input_type not in ('html',) else []
    parts += _rule_note('question', q, survey, ctx)
    parts += QUESTION_SHAPES.get(q.input_type, shape_unknown)(q, ctx)
    return KeepTogether(parts) if parts else Spacer(1, 0)


# ── the map block ──────────────────────────────────────────────────────────

def _allowed(q):
    vs = q.validation_settings or {}
    lo, hi = vs.get('min_features'), vs.get('max_features')
    if q.input_type == 'spraycan':
        return ''
    if isinstance(hi, int) and hi > 0:
        return _('up to %(n)s') % {'n': hi}
    if isinstance(lo, int) and lo > 0:
        return _('at least %(n)s') % {'n': lo}
    return ''


def _marks_count(q):
    hi = (q.validation_settings or {}).get('max_features')
    return hi if isinstance(hi, int) and 0 < hi <= 10 else DEFAULT_MARKS


def _sub_table(q, ctx, rows, first_header):
    subs = [s for s in q.subQuestions()]
    if not subs:
        return []
    head = [para(first_header, ctx.styles['cellhead'])]
    for s in subs:
        text = plain(s.get_translated_name(ctx.lang)) or s.code
        if s.input_type in ('choice', 'multichoice', 'thumbs', 'rating'):
            opts = ' '.join(f'{BOX}{plain(s.get_choice_name(c.get("code"), ctx.lang))}' for c in (s.choices or [])[:6])
            text = f'{text}<br/><font size="7">{escape(opts)}</font>'
            head.append(Paragraph(f'<b>{escape(plain(s.get_translated_name(ctx.lang)) or s.code)}</b><br/>'
                                  f'<font size="7">{escape(opts)}</font>', ctx.styles['cell']))
        else:
            head.append(para(text, ctx.styles['cellhead']))
    data = [head] + [[para(label, ctx.styles['cell'])] + [''] * len(subs) for label in rows]
    first_w = 28 * mm
    col_w = [first_w] + [(ctx.width - first_w) / len(subs)] * len(subs)
    table = Table(data, colWidths=col_w, rowHeights=[None] + [9 * mm] * len(rows), repeatRows=1)
    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#777777')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eeeeee')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, -1), FONT_REGULAR),
    ]))
    return [Spacer(1, 1.5 * mm), table]


def map_block(section, survey, geo_questions, object_questions, ctx, records, page_height):
    """Frame + attribution + legend + per-question tables for one section."""
    out = []
    if section.layout == 'map':
        # Creator-facing (a gap the creator sees on page 1), not translated on purpose.
        frame = static_map.render_frame(section, survey, 'Map unavailable — attach a printed map here')
        out.append(MapFrame(frame, ctx.width, records, page_height))
        line = static_map.ATTRIBUTION if frame.basemap_ok else ''
        if frame.truncated_layers:
            line += ('  ' if line else '') + ', '.join(frame.truncated_layers) + ': ' + _('and %(n)s more') % {'n': '…'}
        if line:
            out.append(para(line, ctx.styles['small']))
    # The legend reads as sentences, one per map question: the letter, the question,
    # and what to draw with the symbol in front. No colour swatch: it means nothing
    # to a respondent and nothing at all on a photocopy.
    legend = []
    for q in geo_questions:
        letter = ctx.letters[q.id]
        allowed = _allowed(q)
        name = plain(q.get_translated_name(ctx.lang)) or q.code
        detail = escape(_how_to_mark(q, letter)) + (f' ({escape(allowed)})' if allowed else '')
        legend.append([Paragraph(f'<b>{letter}</b>', ctx.styles['option']),
                       Paragraph(f'<b>{escape(name)}</b><br/><font size="9" color="#333333">{detail}</font>',
                                 ctx.styles['option'])])
    if legend:
        table = Table(legend, colWidths=[9 * mm, ctx.width - 9 * mm])
        table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                   ('BOTTOMPADDING', (0, 0), (-1, -1), 3), ('TOPPADDING', (0, 0), (-1, -1), 1)]))
        out += [Spacer(1, 2 * mm), para(_('Mark on the map'), ctx.styles['group']), table]
    for q in geo_questions:
        n = _marks_count(q)
        letter = ctx.letters[q.id]
        out += _sub_table(q, ctx, [f'{letter}{i}' for i in range(1, n + 1)], _('Mark'))
    for q in object_questions:
        layer = layer_lite(q)
        if layer is None:
            continue
        objects = list(layer.items.filter(status='visible').order_by('position', 'id')[:MAX_OBJECT_ROWS + 1])
        cut = len(objects) > MAX_OBJECT_ROWS
        objects = objects[:MAX_OBJECT_ROWS]
        out += _question_header(q, ctx)
        rows = [plain(o.title) or o.key for o in objects]
        if q.subQuestions().exists():
            out += _sub_table(q, ctx, rows, _('Object'))
        else:
            out += [para(', '.join(rows), ctx.styles['cell'])]
        if cut:
            out.append(para(_('and %(n)s more') % {'n': layer.items.filter(status='visible').count() - MAX_OBJECT_ROWS},
                            ctx.styles['small']))
    return out


# ── the build ──────────────────────────────────────────────────────────────

@dataclass
class BuildResult:
    pdf: bytes
    form: PrintedForm
    pages: int
    map_pages: int


def _structure(survey, language, paper):
    """(sections → printable runs, hash). The walk is `structure.plan_items`, shared
    with the photo reader (change paper-photo-entry), so the hash, the PDF and what
    a page is read against agree."""
    plan, digest = plan_items(survey, language), []
    for section, runs in plan:
        for group, members in runs:
            digest.append({
                'g': group.code if group else None,
                'gt': plain(group.get_translated_title(language)) if group else None,
                'q': [{'c': q.code, 't': q.input_type, 'n': plain(q.get_translated_name(language)),
                       's': plain(q.get_translated_subtext(language)), 'r': q.required,
                       'o': [[c.get('code'), plain(q.get_choice_name(c.get('code'), language))] for c in (q.choices or [])],
                       'v': q.validation_settings or {},
                       'sub': [[s.code, s.input_type, plain(s.get_translated_name(language))] for s in q.subQuestions()]}
                      for q in members],
            })
        digest.append({'sec': section.code, 'title': plain(section.get_translated_title(language)),
                       'sub': plain(section.get_translated_subheading(language)), 'layout': section.layout,
                       'rule': section.visibility_rule})
    payload = json.dumps({'lang': language, 'paper': paper, 'items': digest}, sort_keys=True, ensure_ascii=False)
    return plan, hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _tracked_link(canonical):
    link = TrackedLink.objects.filter(survey=canonical, utm_source='paper', utm_medium='print_form').first()
    if link is None:
        link = TrackedLink.objects.create(survey=canonical, utm_source='paper', utm_medium='print_form')
    return link


def build_form(survey, language, paper, *, user=None, base_url=''):
    """Render the paper form; returns BuildResult(pdf bytes, PrintedForm, pages, map pages)."""
    if paper not in PAPERS:
        raise ValueError(f'unknown paper {paper!r}')
    register_fonts()
    canonical = canonical_of(survey)
    with translation.override(language):
        plan, digest = _structure(survey, language, paper)
        link = _tracked_link(canonical)
        form, _created = PrintedForm.objects.get_or_create(
            survey=canonical, version_number=survey.version_number, language=language, paper=paper,
            structure_hash=digest, defaults={'created_by': user, 'tracked_link': link})
        page_size = PAPERS[paper]
        page_w, page_h = page_size
        styles = _styles()
        width = page_w - 2 * MARGIN
        records = {}
        story = []

        # Page 1 head: title, the online QR, the office-use box.
        online_url = link.build_url(base_url or getattr(settings, 'SITE_URL', ''))
        qr = form_code.qr_image(online_url, px=256)
        from reportlab.platypus import Image as RLImage
        buf = io.BytesIO()
        qr.save(buf, format='PNG')
        buf.seek(0)
        head_left = [para(survey.name, styles['title']),
                     para(_('Prefer to answer online? Scan this code.'), styles['small']),
                     Spacer(1, 2 * mm),
                     para(_('* required'), styles['small'])]
        # The office-use box is for the creator's team (the entry form's language), not the respondent.
        office = Table([[para('Office use', styles['cellhead'])],
                        [para('Sheet no. ________', styles['cell'])]],
                       colWidths=[38 * mm])
        office.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#777777')),
                                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eeeeee'))]))
        head = Table([[head_left, RLImage(buf, width=22 * mm, height=22 * mm), office]],
                     colWidths=[width - 66 * mm, 26 * mm, 40 * mm])
        head.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (0, 0), 0)]))
        story += [head, Spacer(1, 3 * mm)]

        map_pages = 0
        for section, runs in plan:
            ctx = Ctx(lang=language, styles=styles, width=width)
            all_q = [q for _g, members in runs for q in members]
            geo_q = [q for q in all_q if q.input_type in GEO_TYPES]
            obj_q = [q for q in all_q if q.input_type == 'layer_objects']
            for i, q in enumerate(geo_q):
                ctx.letters[q.id] = string.ascii_uppercase[i % 26] * (1 + i // 26)
            story.append(KeepTogether([
                ItemMarker(f'section:{section.code}', records),
                para(plain(section.get_translated_title(language)) or section.name, styles['section'])]))
            sub = plain(section.get_translated_subheading(language))
            if sub:
                story.append(para(sub, styles['help']))
            story += _rule_note('section', section, survey, ctx)
            if geo_q or obj_q:
                block = map_block(section, survey, geo_q, obj_q, ctx, records, page_h)
                if block and section.layout == 'map':
                    map_pages += 1
                story += block
            for group, members in runs:
                if group is not None:
                    story.append(KeepTogether([
                        ItemMarker(f'group:{group.code}', records),
                        para(plain(group.get_translated_title(language)) or 'Group', styles['group'])]))
                    desc = plain(group.get_translated_description(language))
                    if desc:
                        story.append(para(desc, styles['help']))
                    story += _rule_note('group', group, survey, ctx)
                for q in members:
                    story.append(question_block(q, ctx, survey, records))
            story.append(Spacer(1, 2 * mm))

        chrome = PageChrome(
            form_id=form.pk, title=survey.name, page_size=page_size,
            watermark='DRAFT — not for distribution' if survey.status in WATERMARK_STATUSES else '',
            page_label=_('Page %(n)s of %(total)s'))
        out = io.BytesIO()
        doc = BaseDocTemplate(out, pagesize=page_size, leftMargin=MARGIN, rightMargin=MARGIN,
                              topMargin=MARGIN + 2 * mm, bottomMargin=MARGIN + FOOTER_H,
                              title=f'{survey.name} — form {form.code}', author='Mapsurvey')
        frame = Frame(MARGIN, MARGIN + FOOTER_H, width, page_h - 2 * MARGIN - FOOTER_H - 2 * mm, id='body',
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        doc.addPageTemplates([PageTemplate(id='form', frames=[frame])])

        canvas_cls = type('_Canvas', (_NumberedCanvas,), {'chrome': chrome})
        doc.build(story, canvasmaker=canvas_cls)
        pdf = out.getvalue()
        pages = doc.page
        PrintedForm.objects.filter(pk=form.pk).update(pages=pages, layout=records)
        form.pages, form.layout = pages, records
    return BuildResult(pdf=pdf, form=form, pages=pages,
                       map_pages=sum(1 for rec in records.values() if 'map' in rec))
