"""One vision call per page, bounded by the items printed on it (design D5).

`items_for_page` says what the model is asked about: the keys recorded in
`PrintedForm.layout[page]["items"]` resolved against the form's version, in the
form's language, through the same walk the PDF was printed from
(`print.structure.plan_items`). Forms printed before the item map existed get
the whole structure and the instruction to report only what the page shows.

Values come back typed per question and are checked against the items — an
option code the question does not have is dropped and the field marked
doubtful, never stored as if the model had read it.
"""
import json
import logging

from django.conf import settings

from survey import other_option
from survey.paper import prompts
from survey.print.structure import plan_items
from survey.question_types import GEO_TYPES
from survey.versioning import family_headers

logger = logging.getLogger('survey.paper')

# Types the paper form has a box for and the model can read. Geo (item 4),
# Objects-on-the-map, files, and the display blocks are never asked.
READABLE_TYPES = ('text', 'text_line', 'number', 'choice', 'multichoice', 'range', 'rating', 'thumbs',
                  'datetime', 'ranking')
CODE_TYPES = ('choice', 'multichoice', 'ranking', 'thumbs')
NUMBER_TYPES = ('number', 'range', 'rating')
TEXT_TYPES = ('text', 'text_line', 'datetime')


def _plain(text):
    from django.utils.html import strip_tags
    import html
    return html.unescape(strip_tags(text or '')).strip()


def version_header(printed_form):
    """The SurveyHeader row of the version the form was printed from."""
    for header in family_headers(printed_form.survey):
        if header.version_number == printed_form.version_number:
            return header
    return printed_form.survey


def describe_question(q, language):
    """The item dict the prompt is built from and the values are checked against."""
    item = {'code': q.code, 'type': q.input_type, 'name': _plain(q.get_translated_name(language)) or q.code}
    if q.input_type in ('choice', 'multichoice', 'ranking', 'range', 'rating'):
        other = q.other_choice_code()
        options = []
        for choice in q.choices or []:
            code = choice.get('code')
            entry = {'code': str(code), 'label': _plain(q.get_choice_name(code, language))}
            if other is not None and code == other:
                entry['write_in'] = True
            options.append(entry)
        if q.input_type == 'rating' and not options:
            options = [{'code': str(i), 'label': str(i)} for i in range(1, 6)]
        item['options'] = options
    if q.input_type == 'thumbs':
        item['options'] = [{'code': '1', 'label': 'up'}, {'code': '0', 'label': 'down'}]
    return item


def items_for_page(page):
    """(items, whole_form) — the readable question items the page is asked about."""
    form = page.printed_form
    header = version_header(form)
    language = form.language
    plan = plan_items(header, language)
    questions = [q for _section, runs in plan for _group, members in runs for q in members]
    keys = ((form.layout or {}).get(str(page.page_number)) or {}).get('items')
    if keys is None:
        wanted = None
        whole = True
    else:
        wanted = {k.split(':', 1)[1] for k in keys if k.startswith('question:')}
        whole = False
    items = [describe_question(q, language) for q in questions
             if q.input_type in READABLE_TYPES and (wanted is None or q.code in wanted)]
    return items, whole


def _item_line(item, indent=''):
    line = f"{indent}- {item['code']} ({item['type']}): {item['name']}"
    if item.get('options'):
        opts = '; '.join(f"{o['code']} = {o['label']}" + (' [write-in]' if o.get('write_in') else '')
                         for o in item['options'])
        line += f'\n{indent}  options: {opts}'
    return line


def build_user_message(items, whole_form, geo_items=None, table_items=None):
    lines = [prompts.USER_HEAD_WHOLE_FORM if whole_form else prompts.USER_HEAD]
    lines += [_item_line(item) for item in items]
    if geo_items:
        lines.append(prompts.USER_MAP_HEAD)
        for item in geo_items:
            shape = {'point': 'a dot', 'line': 'a line', 'polygon': 'an outlined area',
                     'spraycan': 'a shaded area'}.get(item['type'], 'a dot')
            lines.append(f"- {item['letter']} = {item['code']} ({item['type']}, {shape}): {item['name']}")
            if item.get('subs'):
                lines.append(f"  columns of the {item['letter']} table (one row per mark, {item['letter']}1, {item['letter']}2 …):")
                lines += [_item_line(sub, '  ') for sub in item['subs']]
    if table_items:
        lines.append(prompts.USER_TABLE_HEAD)
        for item in table_items:
            lines.append(f"- rows {item['letter']}1, {item['letter']}2 … of the table of {item['code']} ({item['name']}): "
                         f"report each as a mark with question \"{item['code']}\" and no points")
            if item.get('subs'):
                lines.append('  columns of that table:')
                lines += [_item_line(sub, '  ') for sub in item['subs']]
    return '\n'.join(lines)


def map_record(page):
    """`PrintedForm.layout[page]["map"]` when this page carries a map frame."""
    form = page.printed_form
    if form is None or not page.page_number:
        return None
    return ((form.layout or {}).get(str(page.page_number)) or {}).get('map')


def geo_items_for_page(page):
    """(map record, [geo item]) — the map questions whose marks are on this
    page's frame (the section the frame belongs to), each with its legend letter
    and the readable sub-questions of its table; (None, []) without a frame."""
    from survey.print.structure import mark_letters
    rec = map_record(page)
    if not rec:
        return None, []
    form = page.printed_form
    header = version_header(form)
    language = form.language
    for section, runs in plan_items(header, language):
        if section.code != rec.get('section_code'):
            continue
        geo_q = [q for _g, members in runs for q in members if q.input_type in GEO_TYPES]
        return rec, [_geo_item(q, letter, language) for q, letter in zip(geo_q, mark_letters(geo_q))]
    return rec, []


def _geo_item(q, letter, language):
    item = describe_question(q, language)
    item['letter'] = letter
    item['subs'] = [describe_question(s, language) for s in q.subQuestions() if s.input_type in READABLE_TYPES]
    return item


def table_items_for_page(page):
    """[geo item] whose marks TABLE runs onto this page from the page that
    carries its map frame (Stack #263: copy 165's A2–A3 rows on page 3 under the
    ROUTE map). On paper a geo question's own block follows its table, so its
    `question:<code>` marker names the page the table ends on; every page after
    the frame's up to and including that one carries rows of it."""
    from survey.print.structure import mark_letters
    form = page.printed_form
    n = page.page_number
    if form is None or not n:
        return []
    layout = form.layout or {}
    frame_pages = {rec['map'].get('section_code'): int(k) for k, rec in layout.items()
                   if isinstance(rec, dict) and rec.get('map') and rec['map'].get('section_code')}
    marker_pages = {key.split(':', 1)[1]: int(k) for k, rec in layout.items() if isinstance(rec, dict)
                    for key in (rec.get('items') or []) if key.startswith('question:')}
    header = version_header(form)
    language = form.language
    out = []
    for section, runs in plan_items(header, language):
        frame = frame_pages.get(section.code)
        if frame is None or frame == n:
            continue
        geo_q = [q for _g, members in runs for q in members if q.input_type in GEO_TYPES]
        for q, letter in zip(geo_q, mark_letters(geo_q)):
            end = marker_pages.get(q.code)
            if end is not None and frame < n <= end:
                out.append(_geo_item(q, letter, language))
    return out


def doubtful_threshold():
    return float(getattr(settings, 'PAPER_DOUBTFUL_CONFIDENCE', 0.75))


def coerce_fields(fields, items):
    """{code: {value, confidence, unreadable}} from the model's list, typed and checked.

    Unknown codes are dropped. A value the question cannot hold (an option code
    not in its list, a non-number for a number) becomes null + doubtful."""
    by_code = {item['code']: item for item in items}
    out = {}
    for field in fields or []:
        code = str(field.get('code') or '')
        value = field.get('value')
        try:
            confidence = float(field.get('confidence', 0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = min(1.0, max(0.0, confidence))
        unreadable = bool(field.get('unreadable'))
        if code.endswith('__other'):
            base = code[:-len('__other')]
            if base in by_code and any(o.get('write_in') for o in by_code[base].get('options', [])):
                out[other_option.field_name(base)] = {
                    'value': (str(value).strip() if value not in (None, '', []) else None),
                    'confidence': confidence, 'unreadable': unreadable}
            continue
        item = by_code.get(code)
        if item is None:
            continue
        value, ok = _coerce_value(item, value)
        if not ok:
            confidence = 0.0
        elif item['type'] == 'datetime' and value and value.endswith(NO_TIME):
            # No time on the paper: the field needs one, so 00:00 stands in and
            # the operator is asked to look (below the doubtful threshold).
            confidence = min(confidence, 0.5)
        out[code] = {'value': value, 'confidence': confidence, 'unreadable': unreadable or not ok}
        box = _box(field.get('box'))
        if box:
            out[code]['box'] = box
    return out


def _box(raw):
    """[ymin, xmin, ymax, xmax] in 0..1000 (Gemini's box convention), or None.

    Where the question sits on THIS photo — the review scrolls the photo to it
    and outlines it while the operator is on that question. A box that is not
    four numbers in range with a positive area is dropped, not repaired."""
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    try:
        y0, x0, y1, x1 = (int(round(float(v))) for v in raw)
    except (TypeError, ValueError):
        return None
    if not all(0 <= v <= 1000 for v in (y0, x0, y1, x1)) or y1 <= y0 or x1 <= x0:
        return None
    return [y0, x0, y1, x1]


def page_boxes(page):
    """{question code: box} of one page — what the photo pane outlines."""
    return {code: f['box'] for code, f in (page.extraction or {}).items()
            if isinstance(f, dict) and f.get('box') and not code.endswith('-other')}


def _coerce_value(item, value):
    """(typed value | None, ok). `ok` False = the model's value does not fit the question."""
    if value in (None, '', []):
        return None, True
    kind = item['type']
    if kind in CODE_TYPES:
        codes = {o['code'] for o in item.get('options', [])}
        values = value if isinstance(value, list) else [value]
        values = [str(v).strip() for v in values]
        if not all(v in codes for v in values):
            return None, False
        if kind == 'choice' or kind == 'thumbs':
            return values[0], True
        if kind == 'ranking':
            return values, len(set(values)) == len(codes) and set(values) == codes
        return list(dict.fromkeys(values)), True
    if kind in NUMBER_TYPES:
        raw = value[0] if isinstance(value, list) else value
        text = str(raw).strip().replace(',', '.')
        try:
            number = float(text)
        except ValueError:
            return None, False
        if kind in ('range', 'rating'):
            codes = {o['code'] for o in item.get('options', [])}
            as_int = str(int(number)) if number == int(number) else text
            if codes and as_int not in codes:
                return None, False
            return as_int, True
        return (str(int(number)) if number == int(number) else text), True
    raw = ' '.join(str(v) for v in value) if isinstance(value, list) else str(value)
    if kind == 'datetime':
        normal = normalise_datetime(raw)
        return (normal, True) if normal else (None, False)
    return raw.strip() or None, True


# What a date without a written time becomes (the datetime-local input needs a time).
NO_TIME = 'T00:00'
_DATE_FORMATS = ('%Y-%m-%d', '%d/%m/%Y', '%d.%m.%Y', '%d-%m-%Y', '%d/%m/%y', '%d.%m.%y', '%d-%m-%y')
_TIME_FORMATS = ('%H:%M', '%H.%M', '%H:%M:%S')


def normalise_datetime(text):
    """'YYYY-MM-DDTHH:MM' — what the respondent page's datetime-local input holds —
    from the model's answer (asked for ISO; day-first forms tolerated), or None.

    A value the input cannot hold is dropped by the browser without a word, so a
    date in any other shape never reaches the operator; it is checked here."""
    from datetime import datetime
    text = (text or '').strip().replace('T', ' ')
    if not text:
        return None
    date_part, _, time_part = text.partition(' ')
    time_part = time_part.strip()
    for fmt in _DATE_FORMATS:
        try:
            day = datetime.strptime(date_part, fmt)
            break
        except ValueError:
            continue
    else:
        return None
    if not time_part:
        return day.strftime('%Y-%m-%d') + NO_TIME
    for fmt in _TIME_FORMATS:
        try:
            clock = datetime.strptime(time_part, fmt)
            return day.strftime('%Y-%m-%d') + clock.strftime('T%H:%M')
        except ValueError:
            continue
    return None


def is_doubtful(field, threshold=None):
    threshold = doubtful_threshold() if threshold is None else threshold
    return bool(field.get('unreadable')) or float(field.get('confidence', 0)) < threshold


def merge_pages(pages):
    """(extraction, doubtful_count) over a sheet's pages, an earlier page winning."""
    merged = {}
    for page in sorted(pages, key=lambda p: (p.page_number or 0, p.seq)):
        for code, field in (page.extraction or {}).items():
            if code in merged:
                if isinstance(field, dict) and field.get('rows_only') and isinstance(merged[code], dict):
                    # The table's rows read on a later page join the map's field by label.
                    merged[code] = dict(merged[code])
                    merged[code]['rows_extra'] = list(merged[code].get('rows_extra') or []) + list(field.get('rows') or [])
                continue
            merged[code] = field
    doubtful = sum(1 for f in merged.values() if is_doubtful(f))
    return merged, doubtful


def extract_page(page, provider):
    """Ask the provider about `page`; returns (extraction dict, usage, items)."""
    items, whole = items_for_page(page)
    map_rec, geo_items = geo_items_for_page(page)
    table_items = table_items_for_page(page)
    with page.image.open('rb') as fh:
        jpeg = fh.read()
    # Thinking tokens count against max_tokens on Gemini (a 200-token cap once came back
    # empty, all of it spent thinking); a page of
    # fields is a few hundred tokens of answer, the rest is headroom for reasoning.
    blob, usage = provider.complete_structured(
        system=prompts.SYSTEM, user=build_user_message(items, whole, geo_items, table_items), schema=prompts.RESPONSE_SCHEMA,
        max_tokens=16000, images=[('image/jpeg', jpeg)])
    blob = blob if isinstance(blob, dict) else {}
    extraction = coerce_fields(blob.get('fields'), items)
    raw_marks = [m for m in (blob.get('marks') or []) if isinstance(m, dict)]
    if table_items:
        # Rows of a table whose map is on another page: answers by label, no geometry.
        from survey.paper import marks
        table_codes = {item['code'] for item in table_items}
        table_marks = [m for m in raw_marks if str(m.get('question') or '') in table_codes]
        raw_marks = [m for m in raw_marks if str(m.get('question') or '') not in table_codes]
        extraction.update(marks.table_rows(table_marks, table_items))
    if geo_items and raw_marks:
        # Marks on the printed map → coordinates (item 4): registered on the
        # photo itself, so the image is still needed here.
        import io
        from PIL import Image
        from survey.paper import marks, texture
        with Image.open(io.BytesIO(jpeg)) as img:
            img.load()
            extraction.update(marks.place_marks(raw_marks, blob.get('map_frame'), geo_items,
                                                map_rec, img, page.printed_form.paper,
                                                frame_corners=blob.get('map_frame_corners'),
                                                reference=texture.reference_image(page)))
    del jpeg
    logger.info('paper page %s: %d items asked, %d fields read', page.pk, len(items), len(extraction))
    return extraction, usage, items


def json_items(items):
    return json.dumps(items, ensure_ascii=False)
