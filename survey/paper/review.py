"""The sheet's extraction in the entry form's own dialect (design D6).

`sheet_prefill(sheet, questions)` returns what `views._build_section_context`
puts into `initial` for questions that have no Answer row yet — the same shapes
the Answer-based prefill uses (choice → `str(code)`, multichoice/ranking → list
of str, number → the value, text → text, write-in → `other_option.field_name`),
so `SurveySectionAnswerForm` sees nothing new — plus which fields deserve a
second look and which the model saw blank.
"""
import json

from django.urls import reverse

from survey import other_option
from survey.paper.extract import is_doubtful, page_boxes
from survey.question_types import GEO_TYPES


def pane_pages_json(survey, pages):
    """The photo pane's page list: id, page number, image URL and the question
    boxes the model reported on that photo (the form leads, the photo follows)."""
    return json.dumps([{
        'id': p.pk, 'number': p.page_number,
        'url': reverse('paper_page_image', args=[survey.uuid, p.pk]),
        'boxes': page_boxes(p),
    } for p in pages])


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
        elif q.input_type in GEO_TYPES:
            # Marks placed from the photo (item 4): GeoJSON features, restored
            # onto the map by `_build_section_context` like stored answers.
            if isinstance(value, list) and all(isinstance(f, dict) for f in value):
                initial[q.code] = value
        else:
            initial[q.code] = str(value)
        other_field = other_option.field_name(q.code)
        other = extraction.get(other_field)
        if other and other.get('value'):
            initial[other_field] = str(other['value'])
            if is_doubtful(other):
                doubtful.append(q.code)
    return initial, list(dict.fromkeys(doubtful)), blank


def supersede_machine_answers(sheet, old_extraction, new_extraction):
    """A page was photographed again and read again (owner, 2026-11-01: the
    re-shot page showed the old positions). Stored answers that still equal
    what the FIRST reading put in — the operator pressed Next without touching
    them — are deleted, so the new reading prefills; anything the operator
    changed stays. Returns the codes superseded."""
    from survey.models import Answer, Question, SurveySession
    session = SurveySession.objects.filter(paper_sheet=sheet, is_deleted=False).first()
    if session is None:
        return []
    superseded = []
    for code, new_field in (new_extraction or {}).items():
        if other_option.is_other_field(code):
            continue
        old_field = (old_extraction or {}).get(code)
        if not isinstance(old_field, dict):
            continue
        question = Question.objects.filter(survey_section__survey_header=session.survey, code=code,
                                           parent_question_id__isnull=True).first()
        if question is None:
            continue
        rows = list(Answer.objects.filter(survey_session=session, question=question, parent_answer_id__isnull=True))
        if not rows:
            continue
        if _stored_equals(question, rows, old_field.get('value'), old_extraction):
            Answer.objects.filter(parent_answer_id__in=[r.pk for r in rows]).delete()
            Answer.objects.filter(pk__in=[r.pk for r in rows]).delete()
            superseded.append(code)
    return superseded


def _stored_equals(question, rows, old_value, old_extraction):
    """Do the stored rows say exactly what the earlier reading said?"""
    if question.input_type in GEO_TYPES:
        if not isinstance(old_value, list):
            return False
        stored = sorted(tuple(round(c, 5) for c in _first_coords(a.geometry)) for a in rows if a.geometry is not None)
        read = sorted(tuple(round(c, 5) for c in _first_coords_geojson(f.get('geometry'))) for f in old_value if isinstance(f, dict))
        return stored == read and len(stored) > 0
    answer = rows[0]
    if question.input_type in ('choice', 'thumbs', 'rating', 'range'):
        stored = str(answer.selected_choices[0]) if answer.selected_choices else (
            str(int(answer.numeric)) if answer.numeric is not None and answer.numeric == int(answer.numeric) else None)
        return old_value is not None and stored == str(old_value)
    if question.input_type in ('multichoice', 'ranking'):
        return isinstance(old_value, list) and [str(c) for c in (answer.selected_choices or [])] == [str(v) for v in old_value]
    if question.input_type == 'number':
        if answer.numeric is None or old_value is None:
            return False
        try:
            return abs(float(answer.numeric) - float(old_value)) < 1e-9
        except (TypeError, ValueError):
            return False
    if answer.text is not None and old_value is not None:
        return answer.text.strip() == str(old_value).strip()
    return False


def _first_coords(geometry):
    coords = geometry.coords
    while isinstance(coords, (tuple, list)) and coords and isinstance(coords[0], (tuple, list)):
        coords = coords[0]
    return coords


def _first_coords_geojson(geometry):
    coords = (geometry or {}).get('coordinates') or []
    while isinstance(coords, list) and coords and isinstance(coords[0], list):
        coords = coords[0]
    return coords


def page_for_section(sheet, section):
    """The sheet's page that shows the section's questions, else its heading,
    else its first page. Questions before the heading: a heading that fit at
    the foot of one page has its questions on the next, and the questions are
    what the operator compares."""
    pages = list(sheet.pages.filter(image__gt='').exclude(status='replaced').order_by('page_number', 'seq'))
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
        elif q.input_type in GEO_TYPES:
            # A placed mark the operator kept, moved or deleted: counted by number of features.
            stored[q.code] = stored.get(q.code, 0) + 1
        elif answer.text is not None:
            stored[q.code] = answer.text.strip()
    changed = 0
    for code in codes:
        value = extraction[code].get('value')
        if isinstance(value, list) and value and isinstance(value[0], dict):
            value = len(value)
        elif isinstance(value, list):
            value = [str(v) for v in value]
        elif value is not None:
            value = str(value)
        if stored.get(code) != value:
            changed += 1
    return total, doubtful, changed
