"""Paper responses — the operator's pages (change paper-photo-entry, #495).

One page per survey, *Paper responses* (`/responses/paper/`): the printed forms
and how many of their copies are back, **New response** (an empty response the
operator photographs one form into) and **Upload a stack** (any number of files;
responses form themselves from the copy numbers), the responses in progress, the
stored ones, and the photos set aside. A response has its own card (its page
slots, a drop zone, Check) and is checked page by page of the printed form.

Everything is under `entry_gate` (editor role on the survey, Pro feature
`operator_entry` on its organisation, per request). Nothing here decodes an image
or parses a PDF: the upload view hands the file to storage and enqueues the
worker; the image view streams what the worker stored.
"""
from django.conf import settings
from django.db import transaction
from django.db.models import Max, Sum
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import product_events as pe
from .models import (
    Answer, PaperBatch, PaperPage, PaperSheet, PaperUpload, PrintedForm, PrintRun, SurveySection, SurveySession,
)
from .operator_entry_views import entry_gate
from .paper import sheets as sheets_mod
from .tasks import ingest_paper_upload, recognise_paper_page
from .versioning import canonical_of


def _inbox(request):
    return sheets_mod.inbox_for(request.survey, user=request.user)


def _sheet(request, sheet_id):
    sheet = PaperSheet.objects.select_related('printed_form', 'batch').filter(
        pk=sheet_id, batch__survey=canonical_of(request.survey)).first()
    if sheet is None:
        raise Http404
    return sheet


def _page(request, page_id):
    page = PaperPage.objects.select_related('sheet', 'batch').filter(
        pk=page_id, batch__survey=canonical_of(request.survey)).first()
    if page is None:
        raise Http404
    return page


def _home_url(survey):
    return reverse('paper_home', args=[survey.uuid])


def _response_url(survey, sheet):
    return reverse('paper_response', args=[survey.uuid, sheet.pk])


def _page_url(survey, sheet, n):
    return reverse('paper_response_page', args=[survey.uuid, sheet.pk, n])


def _hx_or_redirect(request, url):
    if request.headers.get('HX-Request') == 'true':
        response = HttpResponse()
        response['HX-Redirect'] = url
        return response
    return redirect(url)


# ── Paper responses (the survey's page) ────────────────────────────────────

@entry_gate
def paper_home(request, survey_uuid):
    survey = request.survey
    ctx = _home_context(survey, _inbox(request))
    ctx.update({
        'upload_url': reverse('paper_upload', args=[survey.uuid]),
        'list_url': reverse('paper_home_list', args=[survey.uuid]),
        'max_bytes': settings.PAPER_UPLOAD_MAX_BYTES,
    })
    return render(request, 'editor/paper/home.html', ctx)


@entry_gate
def paper_home_list(request, survey_uuid):
    """The list alone — what the page swaps in while anything is being read."""
    return render(request, 'editor/paper/_home_list.html', _home_context(request.survey, _inbox(request)))


@entry_gate
@require_POST
def paper_new(request, survey_uuid):
    """New response: an empty one the operator photographs one form into."""
    survey = request.survey
    batch = _inbox(request)
    with transaction.atomic():
        sheet = sheets_mod.new_sheet(batch, user=request.user)
    pe.emit(pe.PAPER_RESPONSE_CREATED, request.user.pk, {'survey_id': survey.pk, 'surface': 'new_response'})
    return redirect(_response_url(survey, sheet))


@entry_gate
def paper_check_next(request, survey_uuid):
    survey = request.survey
    sheet = sheets_mod.next_reviewable(_inbox(request))
    if sheet is None:
        return redirect(_home_url(survey))
    return redirect(_response_url(survey, sheet))


@entry_gate
@require_POST
def paper_upload(request, survey_uuid):
    """One file per request: into storage, a row, a task. Never read here.

    `sheet` drops it into that response (its card, its review); `page_number`
    says which page it is when its code cannot be read."""
    batch = _inbox(request)
    fh = request.FILES.get('file')
    if fh is None:
        return JsonResponse({'error': _('No file.')}, status=400)
    if fh.size > settings.PAPER_UPLOAD_MAX_BYTES:
        return JsonResponse({'error': _('This file is larger than %(mb)s MB.') % {
            'mb': settings.PAPER_UPLOAD_MAX_BYTES // (1024 * 1024)}}, status=413)
    if batch.pages.exclude(image='').count() >= settings.PAPER_BATCH_MAX_PAGES:
        return JsonResponse({'error': _('Too many photos are waiting. Check or delete some responses first.')}, status=409)
    sheet, expected = None, None
    if request.POST.get('sheet'):
        sheet = PaperSheet.objects.filter(pk=request.POST.get('sheet'), batch=batch).first()
        if sheet is None or not sheet.is_open:
            return JsonResponse({'error': _('This response is not open.')}, status=409)
        try:
            expected = int(request.POST.get('page_number') or 0) or None
        except ValueError:
            expected = None
    with transaction.atomic():
        locked = PaperBatch.objects.select_for_update().get(pk=batch.pk)
        seq = locked.next_upload_seq
        locked.next_upload_seq = seq + 1
        locked.last_activity_at = timezone.now()
        locked.save(update_fields=['next_upload_seq', 'last_activity_at'])
        row = PaperUpload(batch=locked, seq=seq, original_name=(fh.name or '')[:255], size=fh.size,
                          sheet=sheet, expected_page=expected)
        row.file.save(fh.name or 'upload', fh, save=False)
        row.save()
    if sheet is not None:
        sheet.touch()
    transaction.on_commit(lambda: ingest_paper_upload.delay(row.pk))
    return JsonResponse({'id': row.pk, 'seq': seq})


# ── One response ───────────────────────────────────────────────────────────

@entry_gate
def paper_response(request, survey_uuid, sheet_id):
    survey = request.survey
    sheet = _sheet(request, sheet_id)
    ctx = _response_context(survey, sheet)
    ctx.update({
        'upload_url': reverse('paper_upload', args=[survey.uuid]),
        'slots_url': reverse('paper_response_slots', args=[survey.uuid, sheet.pk]),
        'max_bytes': settings.PAPER_UPLOAD_MAX_BYTES,
    })
    return render(request, 'editor/paper/response.html', ctx)


@entry_gate
def paper_response_slots(request, survey_uuid, sheet_id):
    return render(request, 'editor/paper/_response_slots.html',
                  _response_context(request.survey, _sheet(request, sheet_id)))


def _session_for_sheet(request, sheet):
    """The response's session, created from the printed form on first check: its
    version header, its language, source paper, the operator, the link."""
    from .views import session_kind_for
    session = SurveySession.objects.filter(paper_sheet=sheet, is_deleted=False).first()
    if session is None:
        from .paper.extract import version_header
        header = version_header(sheet.printed_form)
        session = SurveySession.objects.create(
            survey=header,
            language=sheet.printed_form.language or None,
            source=SurveySession.SOURCE_PAPER,
            entered_by=request.user,
            opened_by_kind=session_kind_for(request, header),
            paper_sheet=sheet,
        )
    return session


def _has_item_map(form):
    return any('items' in rec for rec in (form.layout or {}).values())


@entry_gate
@require_POST
def paper_response_check(request, survey_uuid, sheet_id):
    """Open the check: page by page of the printed form (at `page` when a page
    thumbnail was clicked); the section flow for a form printed before the item
    map existed."""
    from .operator_entry_views import first_section_url
    survey = request.survey
    sheet = _sheet(request, sheet_id)
    if sheet.status == 'entered' or sheet.printed_form_id is None:
        return redirect(_response_url(survey, sheet))
    session = _session_for_sheet(request, sheet)
    sheet.touch()
    if _has_item_map(sheet.printed_form):
        try:
            number = int(request.POST.get('page') or 1)
        except ValueError:
            number = 1
        if not 1 <= number <= (sheet.printed_form.pages or 1):
            number = 1
        return redirect(_page_url(survey, sheet, number))
    return redirect(first_section_url(survey, session, unanswered_first=True))


@entry_gate
@require_POST
def paper_response_delete(request, survey_uuid, sheet_id):
    """Delete an open response whole — pages, photos, its unfinished session —
    so its copy number is free to be uploaded again. A stored one stays."""
    survey = request.survey
    sheet = _sheet(request, sheet_id)
    sheets_mod.delete_sheet(sheet)
    return _hx_or_redirect(request, _home_url(survey))


def _page_plan(sheet, number):
    """[(section, [codes]), ...] of the questions printed on page `number`, in
    the order the page draws them, resolved on the form's version header."""
    from .paper.extract import version_header
    from .models import Question
    from .question_types import GEO_TYPES
    form = sheet.printed_form
    header = version_header(form)
    layout = form.layout or {}
    items = (layout.get(str(number)) or {}).get('items') or []
    codes = [k.split(':', 1)[1] for k in items if k.startswith('question:')]
    section_keys = [k.split(':', 1)[1] for k in items if k.startswith('section:')]
    by_code = {q.code: q for q in Question.objects.filter(
        survey_section__survey_header=header, code__in=codes, parent_question_id__isnull=True,
    ).select_related('survey_section')}
    # Map questions are answered on the page that carries their section's map
    # frame — the marks are drawn there (item 4) — and on that page ONLY: a
    # question whose heading spilled onto the next page must not be saved from
    # there too, or an empty POST of that page would wipe the placed marks.
    frame_pages = {rec['map'].get('section_code'): int(n) for n, rec in layout.items()
                   if isinstance(rec, dict) and rec.get('map') and rec['map'].get('section_code')}
    codes = [c for c in codes if not (c in by_code and by_code[c].input_type in GEO_TYPES
                                      and frame_pages.get(by_code[c].survey_section.code, number) != number)]
    frame_rec = (layout.get(str(number)) or {}).get('map')
    if frame_rec and frame_rec.get('section_code'):
        for q in Question.objects.filter(
                survey_section__survey_header=header, survey_section__code=frame_rec['section_code'],
                input_type__in=GEO_TYPES, parent_question_id__isnull=True,
        ).select_related('survey_section').order_by('survey_section_id', 'order_number'):
            if q.code not in codes:
                by_code[q.code] = q
                codes.append(q.code)
    plan, seen = [], {}
    for code in codes:
        q = by_code.get(code)
        if q is None:
            continue
        if q.survey_section_id not in seen:
            seen[q.survey_section_id] = (q.survey_section, [])
            plan.append(seen[q.survey_section_id])
        seen[q.survey_section_id][1].append(code)
    # The paper's order, not the shell's: a section is placed where its heading
    # (or its first question) is drawn on the page; the frame section whose
    # heading sat at the foot of the previous page starts this page.
    def paper_order(entry):
        section, section_codes = entry
        positions = [i for i, k in enumerate(items)
                     if k == f'section:{section.code}' or k in {f'question:{c}' for c in section_codes}]
        return min(positions) if positions else -1
    plan.sort(key=paper_order)
    if not plan:
        # A page with no question (a map frame alone, a heading at the foot of a
        # page): show the section the page names, else the form's first section.
        section = SurveySection.objects.filter(survey_header=header, code__in=section_keys).first() \
            or SurveySection.objects.filter(survey_header=header, is_head=True).first()
        if section is not None:
            plan.append((section, []))
    return header, plan


def _paper_map_context(sheet, session, map_rec, geo_questions, language, doubtful):
    """What js/paper_marks.js draws on the map page: the printed frame's bounds
    and, per map question, its letter, the printed rows and columns, and the
    features — the stored rows when the operator saved this page before, else
    what was read off the photo, with where each mark is on the photo."""
    from .paper.extract import describe_question
    from .print.pdf import _marks_count
    from .print.structure import mark_letters
    from .views import geo_answer_features
    extraction = sheet.extraction or {}
    questions = []
    for q, letter in zip(geo_questions, mark_letters(geo_questions)):
        field = extraction.get(q.code) or {}
        read = field.get('value') if isinstance(field.get('value'), list) else []
        stored = geo_answer_features(q, Answer.objects.filter(
            survey_session=session, question=q, parent_answer_id__isnull=True).order_by('id'))
        features = stored or read or []
        boxes = (field.get('feature_boxes') or []) if not stored else []
        # Rows of this table read on a later page (Stack #263): their answers go to the
        # read mark of the same label; a label with no mark is a row the operator places.
        unplaced = []
        if not stored:
            labels = field.get('feature_labels') or []
            extra = list(field.get('rows_extra') or []) + (list(field.get('rows') or []) if field.get('rows_only') else [])
            for row in extra:
                label = str(row.get('label') or '').strip().upper()
                props = dict(row.get('properties') or {})
                props.pop('question_id', None)
                i = labels.index(label) if label in labels else -1
                if 0 <= i < len(features):
                    target = features[i].setdefault('properties', {})
                    for k, v in props.items():
                        target.setdefault(k, v)
                else:
                    unplaced.append({'label': label, 'properties': props})
        subs = []
        for s in q.subQuestions():
            item = describe_question(s, language)
            if item.get('options'):
                item['hint'] = ' · '.join(o['label'] for o in item['options'][:6])
            subs.append(item)
        hi = (q.validation_settings or {}).get('max_features')
        questions.append({
            'code': q.code, 'letter': letter, 'type': q.input_type,
            'name': q.get_translated_name(language) or q.code,
            'color': q.color if q.color and q.color != '#000000' else '#2563eb',
            'rows': _marks_count(q), 'max': hi if isinstance(hi, int) and hi > 0 else None,
            'doubtful': q.code in doubtful, 'subs': subs,
            'features': features, 'boxes': boxes, 'labels': field.get('feature_labels') or [],
            'unplaced': unplaced,
        })
    return {'bbox': map_rec['bbox'], 'zoom': map_rec.get('zoom'), 'questions': questions}


def _steps(survey, sheet, pages_total):
    """The page stepper of the check: one state per printed page."""
    from .paper.extract import is_doubtful
    by_number = {}
    for p in sheets_mod.active_pages(sheet).exclude(image=''):
        by_number.setdefault(p.page_number, p)
    steps = []
    for n in range(1, pages_total + 1):
        p = by_number.get(n)
        if p is None:
            state = 'miss'
        elif p.status == 'queued':
            state = 'busy'
        elif p.status == 'failed':
            state = 'failed'
        elif any(is_doubtful(f) for f in (p.extraction or {}).values()):
            state = 'warn'
        else:
            state = 'ok'
        steps.append({'n': n, 'state': state})
    return steps


@entry_gate
def paper_response_page(request, survey_uuid, sheet_id, number):
    """One printed page of a response: the photograph (or "attach it") on one
    side, the questions printed on that page on the other. POST saves exactly
    those questions (a section spanning two pages keeps the other page's answers)
    and moves on — Next, Back, a stepper page (`goto`), or Saved after the last."""
    from django.utils import translation
    from .operator_entry_views import _saved_url, _vmap
    from .paper.review import pane_pages_json, sheet_prefill
    from .question_types import GEO_TYPES, SURFACE_OPERATOR
    from .views import _add_shell_context, _build_section_context, save_section_answers
    survey = request.survey
    sheet = _sheet(request, sheet_id)
    form = sheet.printed_form
    if form is None or sheet.status == 'entered':
        return redirect(_response_url(survey, sheet))
    pages_total = form.pages or 1
    if number < 1 or number > pages_total:
        raise Http404
    session = _session_for_sheet(request, sheet)
    if session.language:
        translation.activate(session.language)
    header, plan = _page_plan(sheet, number)

    if request.method == 'POST':
        for section, codes in plan:
            if codes:
                save_section_answers(request.POST, session, header, section,
                                     surface=SURFACE_OPERATOR, only_questions=set(codes))
        sheet.touch()
        try:
            goto = int(request.POST.get('goto') or 0)
        except ValueError:
            goto = 0
        back = request.POST.get('nav_direction') == 'back'
        if 1 <= goto <= pages_total:
            url = _page_url(survey, sheet, goto)
        elif back:
            url = _page_url(survey, sheet, max(1, number - 1))
        elif number < pages_total:
            url = _page_url(survey, sheet, number + 1)
        else:
            url = _saved_url(survey, session)
        return _hx_or_redirect(request, url)

    vmap = _vmap(session)
    visible_ids = {s.id for s in vmap.visible_sections}
    plan = [(s, codes) for s, codes in plan if s.id in visible_ids] or plan[:1]
    all_codes = [c for _s, codes in plan for c in codes]
    questions = [q for s, _codes in plan for q in s.questions() if q.code in all_codes]
    prefill, doubtful, blank = sheet_prefill(sheet, questions)
    # The shell (map, geo widgets) belongs to the section with geo questions on
    # this page, else the first; the other sections' fields ride in the same form.
    shell_index = next((i for i, (s, codes) in enumerate(plan)
                        if any(q.code in codes and q.input_type in GEO_TYPES for q in s.questions())), 0)
    shell_section, shell_codes = plan[shell_index]
    # A page with the printed map frame (item 4): the right side is the frame as
    # a live map plus the marks table, half and half with the photo — not the
    # respondent panel with its draw buttons. The geo questions leave the forms;
    # `_paper_map_context` carries them and the hidden inputs post their features.
    geo_codes = {q.code for q in questions if q.input_type in GEO_TYPES}
    map_rec = ((form.layout or {}).get(str(number)) or {}).get('map')
    map_mode = bool(map_rec and geo_codes)
    shell_filter = set(shell_codes) - geo_codes if map_mode else set(shell_codes)
    ctx = _build_section_context(request, survey, header, shell_section, session.language,
                                 number, pages_total, vmap=vmap, session_id=session.pk, entry=True,
                                 prefill=prefill or None, questions_filter=shell_filter)
    if map_mode:
        geo_questions = [q for q in questions if q.input_type in GEO_TYPES]
        ctx['paper_map'] = _paper_map_context(sheet, session, map_rec, geo_questions, session.language, doubtful)
        ctx['existing_geo_answers'] = {}   # the base map stays hidden; the page's own map shows them
        ctx['paper_map_mode'] = True
    # The blocks of the page in the paper's order; the marks block (map + table)
    # sits where the frame section starts, as the printed frame does.
    blocks = []
    for i, (section, codes) in enumerate(plan):
        if i == shell_index:
            form_ = ctx['form']
        else:
            sub = _build_section_context(request, survey, header, section, session.language,
                                         number, pages_total, vmap=vmap, session_id=session.pk, entry=True,
                                         prefill=prefill or None, questions_filter=set(codes))
            form_ = sub['form']
        blocks.append({'section': section, 'form': form_, 'title': section.get_translated_title(session.language),
                       'marks': map_mode and i == shell_index})
    page = sheets_mod.active_pages(sheet).filter(page_number=number).exclude(image='').order_by('-seq').first()
    ctx.update({
        'form_post_url': _page_url(survey, sheet, number),
        'entry_session': session,
        'entry_cancel_url': _response_url(survey, sheet),
        'is_last_section': number == pages_total,
        'paper_page_mode': True,
        'paper_number': number,
        'paper_pages_total': pages_total,
        'paper_steps': _steps(survey, sheet, pages_total),
        'paper_blocks': blocks,
        'paper_sheet': sheet,
        'paper_page': page,
        'paper_pages_json': pane_pages_json(survey, [page] if page else []),
        'paper_missing': page is None,
        'paper_attach_url': reverse('paper_upload', args=[survey.uuid]),
        'paper_page_status_url': reverse('paper_response_page_status', args=[survey.uuid, sheet.pk, number]),
        'paper_doubtful': doubtful,
        'paper_blank': blank,
        'paper_review': True,
        'paper_no_questions': not all_codes,
    })
    _add_shell_context(ctx, header, shell_section)
    return render(request, 'editor/operator_entry/section.html', ctx)


@entry_gate
def paper_response_page_status(request, survey_uuid, sheet_id, number):
    """Polled while a missing page is being attached: missing | queued | recognised | failed | set_aside."""
    sheet = _sheet(request, sheet_id)
    page = sheets_mod.active_pages(sheet).filter(page_number=number).order_by('-seq').first()
    if page is not None:
        return JsonResponse({'state': 'recognised' if page.status == 'recognised' else page.status,
                             'error': page.error})
    attached = PaperPage.objects.filter(upload__sheet=sheet, upload__expected_page=number).order_by('-seq').first()
    if attached is not None and attached.sheet_id != sheet.pk and attached.status != 'queued':
        return JsonResponse({'state': 'set_aside', 'error': attached.error})
    pending = sheet.uploads.filter(expected_page=number, status='queued').exists() or \
        PaperPage.objects.filter(upload__sheet=sheet, upload__expected_page=number, status='queued').exists()
    failed = sheet.uploads.filter(expected_page=number, status='failed').order_by('-seq').first()
    if failed is not None and not pending:
        return JsonResponse({'state': 'failed', 'error': failed.error})
    return JsonResponse({'state': 'queued' if pending else 'missing'})


# ── Pages ──────────────────────────────────────────────────────────────────

@entry_gate
def paper_page_image(request, survey_uuid, page_id):
    page = _page(request, page_id)
    if not page.image:
        raise Http404
    storage = page.image.storage
    if hasattr(storage, 'bucket_name'):
        return redirect(page.image.url)
    response = FileResponse(page.image.open('rb'), content_type='image/jpeg')
    response['Cache-Control'] = 'private, max-age=3600'
    return response


def _back(request, survey, page, sheet=None):
    target = request.POST.get('next') or ''
    if target.startswith('/editor/'):
        return _hx_or_redirect(request, target)
    if sheet is not None:
        return _hx_or_redirect(request, _response_url(survey, sheet))
    return _hx_or_redirect(request, _home_url(survey))


@entry_gate
@require_POST
def paper_page_remove(request, survey_uuid, page_id):
    page = _page(request, page_id)
    sheet = page.sheet
    sheets_mod.remove_page(page)
    return _back(request, request.survey, page, sheet)


@entry_gate
@require_POST
def paper_page_dismiss(request, survey_uuid, page_id):
    """The × on a notice of a response page. A replaced or set-aside photo is not
    on any response's pages, so dismissing its notice deletes it; a photo that went
    to its own copy stays there and only its note is cleared."""
    page = _page(request, page_id)
    if page.sheet_id is None or page.status == 'replaced':
        sheet = page.sheet
        sheets_mod.remove_page(page)
        return _back(request, request.survey, page, sheet)
    page.error = ''
    page.save(update_fields=['error'])
    return _back(request, request.survey, page, page.sheet)


@entry_gate
@require_POST
def paper_response_dismiss_notes(request, survey_uuid, sheet_id):
    """"Dismiss all" on a response's notes block: every replaced photo of the
    response and every set-aside photo dropped into it go (image and row); a
    photo that went to its own copy stays there with its note cleared."""
    survey = request.survey
    sheet = _sheet(request, sheet_id)
    for page in list(sheet.pages.filter(status='replaced')):
        sheets_mod.remove_page(page)
    for page in list(PaperPage.objects.filter(upload__sheet=sheet).exclude(sheet=sheet).exclude(status='queued')):
        if page.sheet_id is None:
            sheets_mod.remove_page(page)
        else:
            page.error = ''
            page.save(update_fields=['error'])
    return _hx_or_redirect(request, _response_url(survey, sheet))


@entry_gate
@require_POST
def paper_page_restore(request, survey_uuid, page_id):
    page = _page(request, page_id)
    sheets_mod.restore_page(page)
    return _back(request, request.survey, page, page.sheet)


@entry_gate
@require_POST
def paper_page_assign(request, survey_uuid, page_id):
    """The operator says which response and page a set-aside photo is."""
    survey = request.survey
    page = _page(request, page_id)
    sheet = PaperSheet.objects.filter(pk=request.POST.get('sheet') or 0, batch=page.batch).first()
    try:
        number = int(request.POST.get('page_number') or 0)
    except ValueError:
        number = 0
    total = sheets_mod.pages_expected(sheet) if sheet else 0
    if sheet is None or not sheet.is_open or number < 1 or (total and number > total):
        return HttpResponse(_('Pick a response and a page number.'), status=400)
    sheets_mod.assign_page(page, sheet, number)
    transaction.on_commit(lambda: recognise_paper_page.delay(page.pk))
    return _back(request, survey, page)


@entry_gate
@require_POST
def paper_page_retry(request, survey_uuid, page_id):
    page = _page(request, page_id)
    if page.status == 'failed':
        page.status = 'queued'
        page.error = ''
        page.save(update_fields=['status', 'error'])
        transaction.on_commit(lambda: recognise_paper_page.delay(page.pk))
    return _back(request, request.survey, page, page.sheet)


# ── Context builders ───────────────────────────────────────────────────────

def _forms_summary(canonical):
    """The printed forms this survey's photos come from: copies printed, back."""
    runs = PrintRun.objects.filter(survey=canonical).select_related('form')
    by_form = {}
    for run in runs:
        entry = by_form.setdefault(run.form_id, {'form': run.form, 'printed': 0, 'runs': []})
        entry['printed'] += run.count
        entry['runs'].append(run)
    for entry in by_form.values():
        ranges = [(r.first_copy, r.last_copy) for r in entry['runs']]
        q = PaperSheet.objects.filter(batch__survey=canonical, copy__isnull=False)
        back = 0
        for lo, hi in ranges:
            back += q.filter(copy__gte=lo, copy__lte=hi).count()
        entry['back'] = back
    forms = sorted(by_form.values(), key=lambda e: -e['form'].pk)
    if not forms:
        latest = PrintedForm.objects.filter(survey=canonical).order_by('-created_at').first()
        if latest is not None:
            forms = [{'form': latest, 'printed': 0, 'back': 0, 'runs': []}]
    return forms


def _slots(sheet, survey):
    """[{n, page, state}] for every page the response's form has, plus any page
    beyond it (a page number the form does not know is still shown)."""
    from .paper.extract import is_doubtful
    total = sheets_mod.pages_expected(sheet)
    pages = list(sheets_mod.active_pages(sheet).order_by('page_number', '-seq'))
    by_number = {}
    for p in pages:
        by_number.setdefault(p.page_number, p)
    numbers = list(range(1, total + 1)) + sorted(n for n in by_number if n and n > total)
    slots = []
    for n in numbers:
        p = by_number.get(n)
        if p is None:
            state = 'miss'
        elif p.status == 'queued':
            state = 'busy'
        elif p.status == 'failed':
            state = 'failed'
        elif any(is_doubtful(f) for f in (p.extraction or {}).values()):
            state = 'warn'
        else:
            state = 'ok'
        slots.append({'n': n, 'page': p, 'state': state,
                      'image_url': reverse('paper_page_image', args=[survey.uuid, p.pk]) if p and p.image else ''})
    return slots


def _card(sheet, survey):
    sheet.slots = _slots(sheet, survey)
    sheet.missing = [s['n'] for s in sheet.slots if s['state'] == 'miss']
    sheet.busy = sum(1 for s in sheet.slots if s['state'] == 'busy')
    sheet.has_pages = any(s['page'] for s in sheet.slots)
    return sheet


def _home_context(survey, batch):
    canonical = canonical_of(survey)
    open_sheets = [_card(s, survey) for s in PaperSheet.objects.filter(
        batch=batch, status__in=PaperSheet.OPEN_STATUSES).select_related('printed_form').order_by('seq')]
    stored = list(PaperSheet.objects.filter(batch=batch, status='entered').select_related('session')
                  .order_by('-entered_at')[:20])
    stored_count = PaperSheet.objects.filter(batch=batch, status='entered').count()
    loose = list(batch.pages.filter(sheet__isnull=True).exclude(status='queued').exclude(image='')
                 .select_related('upload').order_by('-seq'))
    uploads = list(batch.uploads.exclude(status='split').order_by('seq'))
    loose_queued = batch.pages.filter(sheet__isnull=True, status='queued').count()
    in_flight = bool(loose_queued or any(u.status == 'queued' for u in uploads)
                     or any(s.status == 'recognising' for s in open_sheets))
    # The one response missing exactly one page is the likely home of a lone set-aside photo.
    gaps = [(s, s.missing) for s in open_sheets if s.missing]
    suggestion = gaps[0] if len(gaps) == 1 and len(gaps[0][1]) == 1 else None
    forms = _forms_summary(canonical)
    return {
        'survey': survey,
        'batch': batch,
        'forms': forms,
        'forms_total': {'count': len(forms), 'printed': sum(f['printed'] for f in forms), 'back': sum(f['back'] for f in forms)},
        'numbered': PrintRun.objects.filter(survey=canonical).exists(),
        'open_sheets': open_sheets,
        'to_check': sum(1 for s in open_sheets if s.is_reviewable and s.has_pages),
        'stored': stored,
        'stored_count': stored_count,
        'loose_pages': loose,
        'uploads': uploads,
        'loose_queued': loose_queued,
        'in_flight': in_flight,
        'suggestion': suggestion,
        'next_sheet': sheets_mod.next_reviewable(batch),
        'list_url': reverse('paper_home_list', args=[survey.uuid]),
    }


def _response_context(survey, sheet):
    _card(sheet, survey)
    moved = list(PaperPage.objects.filter(upload__sheet=sheet).exclude(sheet=sheet).exclude(status='queued').exclude(error='')
                 .select_related('sheet').order_by('-seq'))
    replaced = list(sheet.pages.filter(status='replaced').exclude(image='').order_by('page_number', '-seq'))
    queued_uploads = sheet.uploads.filter(status='queued').count() + \
        PaperPage.objects.filter(upload__sheet=sheet, sheet__isnull=True, status='queued').count()
    session = SurveySession.objects.filter(paper_sheet=sheet).first()
    return {
        'survey': survey,
        'sheet': sheet,
        'moved': moved,
        'replaced': replaced,
        'notes_count': len(moved) + len(replaced),
        'in_flight': bool(sheet.busy or queued_uploads),
        'stored_session': session if sheet.status == 'entered' else None,
        'slots_url': reverse('paper_response_slots', args=[survey.uuid, sheet.pk]),
        'home_url': _home_url(survey),
    }
