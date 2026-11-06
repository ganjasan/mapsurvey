"""Pages → responses (spec paper-photo-entry, design D4). Deterministic: the code
decides, never the order the files arrived in.

* A page of a NUMBERED copy goes to that copy's response, made on first sight —
  whichever file, card or order it came in. Dropped into another response's card,
  it still goes to its own copy (the card says where it went).
* A page of a form printed WITHOUT numbers can only be told apart by where the
  operator put it: into a response ("New response" + photos), or as one PDF of a
  stack upload (one PDF = one response). A loose photo of such a form is set
  aside — there is nothing to tell whose it is.
* The same page of the same response twice: the later photo wins, the earlier is
  `replaced` and can be restored.
"""
from django.db import transaction
from django.utils.translation import gettext as _


def inbox_for(survey, user=None):
    """The survey's paper inbox (one open `PaperBatch` per canonical survey)."""
    from survey.models import PaperBatch
    from survey.versioning import canonical_of
    canonical = canonical_of(survey)
    batch = PaperBatch.objects.filter(survey=canonical, status=PaperBatch.STATUS_OPEN).first()
    if batch is None:
        batch = PaperBatch.objects.create(survey=canonical, organization=canonical.organization, created_by=user)
    return batch


def new_sheet(batch, *, user=None, copy=None, printed_form=None, source_upload=None):
    """A response numbered from the inbox counter. Caller holds the batch lock."""
    from survey.models import PaperBatch, PaperSheet
    locked = PaperBatch.objects.select_for_update().get(pk=batch.pk)
    sheet = PaperSheet.objects.create(batch=locked, seq=locked.next_sheet_seq, copy=copy,
                                      printed_form=printed_form, source_upload=source_upload, created_by=user)
    locked.next_sheet_seq += 1
    locked.save(update_fields=['next_sheet_seq'])
    return sheet


def place_page(page):
    """Put a page with a code on its response; returns the response or None.

    None = set aside (`unrecognised` with the reason in `error`)."""
    from survey.models import PaperBatch, PaperSheet
    upload = page.upload
    dropped_into = upload.sheet
    with transaction.atomic():
        PaperBatch.objects.select_for_update().filter(pk=page.batch_id).first()
        target = None
        if page.copy:
            target = PaperSheet.objects.filter(batch_id=page.batch_id, copy=page.copy).first()
            if target is None and dropped_into is not None and dropped_into.copy is None \
                    and dropped_into.is_open and not _holds_other_pages(dropped_into, page):
                # An empty "New response" takes the copy of its first page.
                dropped_into.copy = page.copy
                dropped_into.save(update_fields=['copy'])
                target = dropped_into
            if target is None:
                target = new_sheet(page.batch, user=page.batch.created_by, copy=page.copy,
                                   printed_form=page.printed_form)
            if dropped_into is not None and target.pk != dropped_into.pk:
                page.error = _('This photo is %(copy)s, page %(page)s — it went there.') % {
                    'copy': target.label, 'page': page.page_number}
        elif dropped_into is not None:
            target = dropped_into
        elif upload.is_pdf:
            target = PaperSheet.objects.filter(batch_id=page.batch_id, source_upload=upload).first() or \
                new_sheet(page.batch, user=page.batch.created_by, printed_form=page.printed_form, source_upload=upload)
        else:
            return _set_aside(page, _('This form has no copy numbers: add this photo to a response, '
                                      'or upload one PDF per filled form.'))

        if target.status == 'entered':
            return _set_aside(page, _('%(copy)s is already stored — this photo was not used.') % {'copy': target.label})
        if target.printed_form_id is None:
            target.printed_form_id = page.printed_form_id
            target.save(update_fields=['printed_form'])
        elif target.printed_form_id != page.printed_form_id:
            return _set_aside(page, _('This page is from another printed form than %(copy)s.') % {'copy': target.label})

        for old in target.pages.filter(page_number=page.page_number).exclude(pk=page.pk).exclude(status='replaced'):
            old.status = 'replaced'
            old.save(update_fields=['status'])
        page.sheet = target
        page.save(update_fields=['sheet', 'error'])
    target.touch()
    return target


def _holds_other_pages(sheet, page):
    return sheet.pages.exclude(pk=page.pk).exclude(status='replaced').exists()


def _set_aside(page, reason):
    page.sheet = None
    page.status = 'unrecognised'
    page.error = reason[:200]
    page.save(update_fields=['sheet', 'status', 'error'])
    return None


def active_pages(sheet):
    return sheet.pages.exclude(status='replaced')


def pages_expected(sheet):
    """How many pages the response's form has, else the survey's newest form's."""
    from survey.models import PrintedForm
    if sheet.printed_form_id and sheet.printed_form.pages:
        return sheet.printed_form.pages
    latest = PrintedForm.objects.filter(survey_id=sheet.batch.survey_id).order_by('-created_at').first()
    return latest.pages if latest and latest.pages else 0


def missing_pages(sheet):
    numbers = {n for n in active_pages(sheet).values_list('page_number', flat=True) if n}
    total = pages_expected(sheet)
    return [n for n in range(1, total + 1) if n not in numbers]


def refresh_sheet(sheet):
    """Recompute status and the merged extraction from the response's pages."""
    from survey.paper.extract import merge_pages
    if sheet.status == 'entered':
        return sheet
    pages = list(active_pages(sheet).order_by('page_number', 'seq'))
    if any(p.status == 'queued' for p in pages):
        sheet.status = 'recognising'
    elif pages and not missing_pages(sheet):
        sheet.status = 'review'
    else:
        sheet.status = 'incomplete'
    sheet.extraction, sheet.doubtful_count = merge_pages([p for p in pages if p.status == 'recognised'])
    sheet.save(update_fields=['status', 'extraction', 'doubtful_count'])
    return sheet


def restore_page(page):
    """Bring a replaced photo back; the one that replaced it becomes `replaced`."""
    sheet = page.sheet
    if sheet is None or page.status != 'replaced':
        return
    for other in sheet.pages.filter(page_number=page.page_number).exclude(pk=page.pk).exclude(status='replaced'):
        other.status = 'replaced'
        other.save(update_fields=['status'])
    page.status = 'recognised' if page.extraction or page.recognised_at else 'queued'
    page.save(update_fields=['status'])
    refresh_sheet(sheet)


def assign_page(page, sheet, number):
    """The operator says which response and page a set-aside photo is."""
    page.sheet = sheet
    page.page_number = number
    page.pages_total = pages_expected(sheet) or None
    if sheet.printed_form_id:
        page.printed_form_id = sheet.printed_form_id
    page.code_source = 'manual'
    page.status = 'queued'
    page.error = ''
    page.extraction = {}
    page.save()
    for old in sheet.pages.filter(page_number=number).exclude(pk=page.pk).exclude(status='replaced'):
        old.status = 'replaced'
        old.save(update_fields=['status'])
    refresh_sheet(sheet)


def delete_sheet(sheet):
    """Delete an open response whole (owner, 2026-11-01: "skipped" kept a row that
    held the copy number, so the copy could never be uploaded again): its pages
    with their images, its unfinished session to the trash, the row. The copy
    number is free again. A stored response is not deleted here — it is a
    response on Responses now and is deleted there."""
    from survey.models import SurveySession
    if sheet.status == 'entered':
        return False
    for page in list(sheet.pages.all()):
        page.discard_image()
        page.delete()
    for session in SurveySession.objects.filter(paper_sheet=sheet, is_deleted=False):
        session.is_deleted = True
        session.save(update_fields=['is_deleted'])
    sheet.delete()
    return True


def remove_page(page):
    """Delete the page (image and row); its response is re-evaluated."""
    sheet = page.sheet
    page.discard_image()
    page.delete()
    if sheet is not None:
        refresh_sheet(sheet)


def next_reviewable(batch, after=None):
    """The next response to check: complete ones first, then incomplete ones that
    hold at least one read page; `after` skips the one just stored."""
    from survey.models import PaperSheet
    qs = PaperSheet.objects.filter(batch=batch)
    if after is not None:
        qs = qs.exclude(pk=after.pk)
    complete = qs.filter(status='review').order_by('seq').first()
    if complete is not None:
        return complete
    return qs.filter(status='incomplete', pages__status='recognised').order_by('seq').first()
