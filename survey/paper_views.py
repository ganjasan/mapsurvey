"""Paper forms from photos — the batch pages (change paper-photo-entry, #495).

The batch list, the per-file upload endpoint, the polled status, the page and
sheet actions, and the gated page image. Everything is under `entry_gate`
(editor role on the survey, Pro feature `operator_entry` on its organisation,
per request — the same gate as the entry header). Nothing here decodes an
image or parses a PDF: the upload view hands the file to storage and enqueues
the worker; the image view streams what the worker stored.
"""
import json

from django.conf import settings
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import product_events as pe
from .models import Answer, PaperBatch, PaperPage, PaperSheet, PaperUpload, PrintedForm, SurveySession
from .operator_entry_views import entry_gate
from .paper import sheets as sheets_mod
from .tasks import delete_sheet_images, ingest_paper_upload, recognise_paper_page
from .versioning import canonical_of


def _batch(request, batch_id):
    """The batch, or 404 — it must belong to this survey's canonical row."""
    batch = PaperBatch.objects.filter(pk=batch_id, survey=canonical_of(request.survey)).first()
    if batch is None:
        raise Http404
    return batch


def _page(request, batch, page_id):
    return get_object_or_404(PaperPage, pk=page_id, batch=batch)


def _sheet(request, batch, sheet_id):
    return get_object_or_404(PaperSheet, pk=sheet_id, batch=batch)


def _batch_url(survey, batch):
    return reverse('paper_batch', args=[survey.uuid, batch.pk])


# ── the pages ──────────────────────────────────────────────────────────────

@entry_gate
def batches(request, survey_uuid):
    survey = request.survey
    canonical = canonical_of(survey)
    rows = list(PaperBatch.objects.filter(survey=canonical).select_related('created_by'))
    counts = _batch_counts(rows)
    return render(request, 'editor/paper/batches.html', {
        'survey': survey,
        'batches': [(b, counts.get(b.pk, {})) for b in rows],
    })


@entry_gate
@require_POST
def batch_new(request, survey_uuid):
    survey = request.survey
    batch = PaperBatch.objects.create(
        survey=canonical_of(survey), organization=survey.organization, created_by=request.user)
    pe.emit(pe.PAPER_BATCH_CREATED, request.user.pk, {'survey_id': survey.pk})
    return redirect(_batch_url(survey, batch))


@entry_gate
def batch(request, survey_uuid, batch_id):
    survey = request.survey
    batch = _batch(request, batch_id)
    ctx = _batch_context(survey, batch)
    ctx.update({
        'upload_url': reverse('paper_upload', args=[survey.uuid, batch.pk]),
        'status_url': reverse('paper_batch_status', args=[survey.uuid, batch.pk]),
        'max_bytes': settings.PAPER_UPLOAD_MAX_BYTES,
        'max_pages': settings.PAPER_BATCH_MAX_PAGES,
    })
    return render(request, 'editor/paper/batch.html', ctx)


@entry_gate
def batch_list_partial(request, survey_uuid, batch_id):
    """The sheet list alone — what the page swaps in while polling."""
    survey = request.survey
    batch = _batch(request, batch_id)
    return render(request, 'editor/paper/_sheet_list.html', _batch_context(survey, batch))


@entry_gate
def batch_status(request, survey_uuid, batch_id):
    batch = _batch(request, batch_id)
    uploads_open = batch.uploads.filter(status='queued').count()
    pages_open = batch.pages.filter(status='queued').count()
    sheet_counts = {}
    for row in batch.sheets.values('status'):
        sheet_counts[row['status']] = sheet_counts.get(row['status'], 0) + 1
    return JsonResponse({
        'in_flight': bool(uploads_open or pages_open),
        'uploads_open': uploads_open,
        'pages_open': pages_open,
        'pages': batch.pages.count(),
        'unrecognised': batch.pages.filter(status='unrecognised').count(),
        'failed': batch.pages.filter(status='failed').count() + batch.uploads.filter(status='failed').count(),
        'sheets': sheet_counts,
        'status': batch.status,
    })


@entry_gate
@require_POST
def batch_close(request, survey_uuid, batch_id):
    survey = request.survey
    batch = _batch(request, batch_id)
    batch.status = PaperBatch.STATUS_CLOSED
    batch.save(update_fields=['status'])
    for sheet in batch.sheets.filter(status__in=PaperSheet.OPEN_STATUSES):
        delete_sheet_images.delay(sheet.pk)
    for page in batch.pages.filter(sheet__isnull=True):
        page.discard_image()
        page.save(update_fields=['image'])
    return redirect(reverse('paper_batches', args=[survey.uuid]))


# ── uploads ────────────────────────────────────────────────────────────────

@entry_gate
@require_POST
def upload(request, survey_uuid, batch_id):
    """One file per request: into storage, a row, a task. Never read here."""
    batch = _batch(request, batch_id)
    if not batch.is_open:
        return JsonResponse({'error': _('This batch is closed.')}, status=409)
    if batch.pages.count() >= settings.PAPER_BATCH_MAX_PAGES:
        return JsonResponse({'error': _('This batch is full. Start a new one.')}, status=409)
    fh = request.FILES.get('file')
    if fh is None:
        return JsonResponse({'error': _('No file.')}, status=400)
    if fh.size > settings.PAPER_UPLOAD_MAX_BYTES:
        return JsonResponse({'error': _('This file is larger than %(mb)s MB.') % {
            'mb': settings.PAPER_UPLOAD_MAX_BYTES // (1024 * 1024)}}, status=413)
    with transaction.atomic():
        locked = PaperBatch.objects.select_for_update().get(pk=batch.pk)
        seq = locked.next_upload_seq
        locked.next_upload_seq = seq + 1
        locked.last_activity_at = timezone.now()
        locked.save(update_fields=['next_upload_seq', 'last_activity_at'])
        row = PaperUpload(batch=locked, seq=seq, original_name=(fh.name or '')[:255], size=fh.size)
        row.file.save(fh.name or 'upload', fh, save=False)
        row.save()
    transaction.on_commit(lambda: ingest_paper_upload.delay(row.pk))
    return JsonResponse({'id': row.pk, 'seq': seq})


# ── pages ──────────────────────────────────────────────────────────────────

@entry_gate
def page_image(request, survey_uuid, batch_id, page_id):
    batch = _batch(request, batch_id)
    page = _page(request, batch, page_id)
    if not page.image:
        raise Http404
    storage = page.image.storage
    if hasattr(storage, 'bucket_name'):
        return redirect(page.image.url)
    response = FileResponse(page.image.open('rb'), content_type='image/jpeg')
    response['Cache-Control'] = 'private, max-age=3600'
    return response


@entry_gate
@require_POST
def page_move(request, survey_uuid, batch_id, page_id):
    survey = request.survey
    batch = _batch(request, batch_id)
    page = _page(request, batch, page_id)
    target = request.POST.get('sheet') or ''
    sheet = None if target in ('', 'new') else _sheet(request, batch, int(target))
    sheets_mod.move_page(page, sheet)
    batch.touch()
    return _list_or_redirect(request, survey, batch)


@entry_gate
@require_POST
def page_remove(request, survey_uuid, batch_id, page_id):
    survey = request.survey
    batch = _batch(request, batch_id)
    page = _page(request, batch, page_id)
    sheets_mod.remove_page(page)
    batch.touch()
    return _list_or_redirect(request, survey, batch)


@entry_gate
@require_POST
def page_assign(request, survey_uuid, batch_id, page_id):
    """The operator names the printed form and page number of an unrecognised page."""
    survey = request.survey
    batch = _batch(request, batch_id)
    page = _page(request, batch, page_id)
    form = PrintedForm.objects.filter(pk=request.POST.get('form') or 0, survey=batch.survey).first()
    try:
        number = int(request.POST.get('page_number') or 0)
    except ValueError:
        number = 0
    if form is None or number < 1 or (form.pages and number > form.pages):
        return HttpResponse(_('Pick a printed form and a page number.'), status=400)
    page.printed_form = form
    page.page_number = number
    page.pages_total = form.pages or None
    page.code_source = 'manual'
    page.status = 'queued'
    page.error = ''
    page.extraction = {}
    page.save()
    transaction.on_commit(lambda: recognise_paper_page.delay(page.pk))
    return _list_or_redirect(request, survey, batch)


@entry_gate
@require_POST
def page_retry(request, survey_uuid, batch_id, page_id):
    survey = request.survey
    batch = _batch(request, batch_id)
    page = _page(request, batch, page_id)
    if page.status == 'failed':
        page.status = 'queued'
        page.error = ''
        page.save(update_fields=['status', 'error'])
        transaction.on_commit(lambda: recognise_paper_page.delay(page.pk))
    return _list_or_redirect(request, survey, batch)


# ── sheets ─────────────────────────────────────────────────────────────────

@entry_gate
@require_POST
def sheet_enter(request, survey_uuid, batch_id, sheet_id):
    """Open the sheet's review: its session from the printed form, then the entry flow."""
    from .operator_entry_views import first_section_url
    from .views import session_kind_for
    survey = request.survey
    batch = _batch(request, batch_id)
    sheet = _sheet(request, batch, sheet_id)
    if sheet.status in ('entered', 'skipped') or sheet.printed_form_id is None:
        return redirect(_batch_url(survey, batch))
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
    batch.touch()
    return redirect(first_section_url(survey, session, unanswered_first=True))


@entry_gate
@require_POST
def sheet_skip(request, survey_uuid, batch_id, sheet_id):
    survey = request.survey
    batch = _batch(request, batch_id)
    sheet = _sheet(request, batch, sheet_id)
    if sheet.status not in ('entered', 'skipped'):
        sheet.status = 'skipped'
        sheet.save(update_fields=['status'])
        session = SurveySession.objects.filter(paper_sheet=sheet).first()
        if session is not None and not Answer.objects.filter(
                survey_session=session, parent_answer_id__isnull=True).exists():
            session.is_deleted = True
            session.save(update_fields=['is_deleted'])
        delete_sheet_images.delay(sheet.pk)
    batch.touch()
    return _list_or_redirect(request, survey, batch)


# ── helpers ────────────────────────────────────────────────────────────────

def _list_or_redirect(request, survey, batch):
    if request.headers.get('HX-Request') == 'true':
        return render(request, 'editor/paper/_sheet_list.html', _batch_context(survey, batch))
    return redirect(_batch_url(survey, batch))


def _batch_counts(rows):
    counts = {}
    for row in PaperSheet.objects.filter(batch__in=rows).values('batch_id', 'status'):
        counts.setdefault(row['batch_id'], {}).setdefault(row['status'], 0)
        counts[row['batch_id']][row['status']] += 1
    for row in PaperPage.objects.filter(batch__in=rows, status='unrecognised').values('batch_id'):
        counts.setdefault(row['batch_id'], {}).setdefault('unrecognised', 0)
        counts[row['batch_id']]['unrecognised'] += 1
    return counts


def _batch_context(survey, batch):
    sheets = list(batch.sheets.select_related('printed_form').prefetch_related('pages').order_by('seq'))
    for sheet in sheets:
        sheet.page_rows = sorted(sheet.pages.all(), key=lambda p: (p.page_number or 0, p.seq))
        sheet.missing = sheets_mod.missing_pages(sheet) if sheet.status == 'incomplete' else []
        sheet.duplicates = sheets_mod.duplicate_pages(sheet) if sheet.status == 'incomplete' else []
        sheet.has_session = SurveySession.objects.filter(paper_sheet=sheet, is_deleted=False).exists()
    uploads = list(batch.uploads.exclude(status='split').order_by('seq'))
    loose = list(batch.pages.filter(sheet__isnull=True).exclude(status='queued').order_by('seq'))
    queued_loose = batch.pages.filter(sheet__isnull=True, status='queued').count()
    status = {
        'review': sum(1 for s in sheets if s.status in PaperSheet.REVIEWABLE_STATUSES),
        'entered': sum(1 for s in sheets if s.status == 'entered'),
        'skipped': sum(1 for s in sheets if s.status == 'skipped'),
        'unrecognised': sum(1 for p in loose if p.status == 'unrecognised'),
        'failed': sum(1 for p in loose if p.status == 'failed') + sum(1 for u in uploads if u.status == 'failed'),
    }
    in_flight = bool(queued_loose or any(u.status == 'queued' for u in uploads)
                     or any(s.status == 'recognising' for s in sheets))
    forms = list(PrintedForm.objects.filter(survey=batch.survey).order_by('-created_at'))
    return {
        'survey': survey,
        'batch': batch,
        'sheets': sheets,
        'uploads': uploads,
        'loose_pages': loose,
        'queued_loose': queued_loose,
        'counts': status,
        'in_flight': in_flight,
        'printed_forms': forms,
        'list_url': reverse('paper_batch_list', args=[survey.uuid, batch.pk]),
        'batch_url': _batch_url(survey, batch),
        'next_sheet': sheets_mod.next_reviewable(batch),
    }
