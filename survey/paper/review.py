"""The sheet's extraction in the entry form's own dialect (design D6).

`sheet_prefill(sheet, questions)` returns what `views._build_section_context`
puts into `initial` for questions that have no Answer row yet — the same shapes
the Answer-based prefill uses (choice → `str(code)`, multichoice/ranking → list
of str, number → the value, text → text, write-in → `other_option.field_name`),
so `SurveySectionAnswerForm` sees nothing new — plus which fields deserve a
second look and which the model saw blank.
"""
from survey import other_option
from survey.paper.extract import is_doubtful


def sheet_prefill(sheet, questions):
    """(initial, doubtful_codes, blank_codes) for the given section questions."""
    extraction = sheet.extraction or {}
    initial, doubtful, blank = {}, [], []
    for q in questions:
        field = extraction.get(q.code)
        if field is None:
            continue
        value = field.get('value')
        if is_doubtful(field):
            doubtful.append(q.code)
        if value in (None, '', []):
            blank.append(q.code)
            continue
        if q.input_type in ('choice', 'thumbs', 'rating', 'range'):
            initial[q.code] = str(value)
        elif q.input_type in ('multichoice', 'ranking'):
            initial[q.code] = [str(v) for v in (value if isinstance(value, list) else [value])]
        elif q.input_type == 'number':
            try:
                number = float(value)
                initial[q.code] = int(number) if number == int(number) else number
            except (TypeError, ValueError):
                continue
        else:
            initial[q.code] = str(value)
        other_field = other_option.field_name(q.code)
        other = extraction.get(other_field)
        if other and other.get('value'):
            initial[other_field] = str(other['value'])
            if is_doubtful(other):
                doubtful.append(q.code)
    return initial, list(dict.fromkeys(doubtful)), blank


def page_for_section(sheet, section):
    """The sheet's page that shows the section's questions, else its heading,
    else its first page. Questions before the heading: a heading that fit at
    the foot of one page has its questions on the next, and the questions are
    what the operator compares."""
    pages = list(sheet.pages.filter(image__gt='').order_by('page_number', 'seq'))
    if not pages:
        return None, pages
    form = sheet.printed_form
    layout = (form.layout or {}) if form is not None else {}
    keys = [f'question:{q.code}' for q in section.questions()] + [f'section:{section.code}']
    for key in keys:
        for page in pages:
            items = (layout.get(str(page.page_number)) or {}).get('items') or []
            if key in items:
                return page, pages
    return pages[0], pages


def changed_fields(sheet, session):
    """(fields_total, fields_doubtful, fields_changed): the prefill against what
    the operator stored — the quality signal of the reader."""
    from survey.models import Answer
    extraction = sheet.extraction or {}
    codes = [c for c in extraction if not other_option.is_other_field(c)]
    total = len(codes)
    doubtful = sum(1 for c in codes if is_doubtful(extraction[c]))
    stored = {}
    for answer in Answer.objects.filter(survey_session=session, parent_answer_id__isnull=True).select_related('question'):
        q = answer.question
        if q.input_type in ('choice', 'thumbs', 'rating', 'range'):
            if answer.selected_choices:
                stored[q.code] = str(answer.selected_choices[0])
            elif answer.numeric is not None:
                stored[q.code] = str(int(answer.numeric)) if answer.numeric == int(answer.numeric) else str(answer.numeric)
        elif q.input_type in ('multichoice', 'ranking'):
            stored[q.code] = [str(c) for c in (answer.selected_choices or [])]
        elif q.input_type == 'number':
            if answer.numeric is not None:
                stored[q.code] = str(int(answer.numeric)) if answer.numeric == int(answer.numeric) else str(answer.numeric)
        elif answer.text is not None:
            stored[q.code] = answer.text.strip()
    changed = 0
    for code in codes:
        value = extraction[code].get('value')
        if isinstance(value, list):
            value = [str(v) for v in value]
        elif value is not None:
            value = str(value)
        if stored.get(code) != value:
            changed += 1
    return total, doubtful, changed
