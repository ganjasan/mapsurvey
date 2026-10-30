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


def build_user_message(items, whole_form):
    lines = [prompts.USER_HEAD_WHOLE_FORM if whole_form else prompts.USER_HEAD]
    for item in items:
        line = f"- {item['code']} ({item['type']}): {item['name']}"
        if item.get('options'):
            opts = '; '.join(f"{o['code']} = {o['label']}" + (' [write-in]' if o.get('write_in') else '')
                             for o in item['options'])
            line += f'\n  options: {opts}'
        lines.append(line)
    return '\n'.join(lines)


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
        out[code] = {'value': value, 'confidence': confidence, 'unreadable': unreadable or not ok}
    return out


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
    return raw.strip() or None, True


def is_doubtful(field, threshold=None):
    threshold = doubtful_threshold() if threshold is None else threshold
    return bool(field.get('unreadable')) or float(field.get('confidence', 0)) < threshold


def merge_pages(pages):
    """(extraction, doubtful_count) over a sheet's pages, an earlier page winning."""
    merged = {}
    for page in sorted(pages, key=lambda p: (p.page_number or 0, p.seq)):
        for code, field in (page.extraction or {}).items():
            merged.setdefault(code, field)
    doubtful = sum(1 for f in merged.values() if is_doubtful(f))
    return merged, doubtful


def extract_page(page, provider):
    """Ask the provider about `page`; returns (extraction dict, usage, items)."""
    items, whole = items_for_page(page)
    with page.image.open('rb') as fh:
        jpeg = fh.read()
    blob, usage = provider.complete_structured(
        system=prompts.SYSTEM, user=build_user_message(items, whole), schema=prompts.RESPONSE_SCHEMA,
        max_tokens=8000, images=[('image/jpeg', jpeg)])
    del jpeg
    fields = (blob or {}).get('fields') if isinstance(blob, dict) else None
    extraction = coerce_fields(fields, items)
    logger.info('paper page %s: %d items asked, %d fields read', page.pk, len(items), len(extraction))
    return extraction, usage, items


def json_items(items):
    return json.dumps(items, ensure_ascii=False)
