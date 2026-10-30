"""Pages → sheets (spec paper-photo-entry, design D4).

By upload order and page number: page 1 starts a sheet, 2…M continue the batch's
last sheet when they continue it (same printed form, last page + 1). Placement
walks the batch's unplaced pages in `seq` order and stops at the first one still
queued, so a small photo recognised before the big PDF ahead of it waits its
turn. A page the operator moved is `pinned` and never regrouped.
"""
from django.db import transaction


def place_pages(batch):
    """Place every unplaced, recognised page of the batch in `seq` order.

    Returns the sheets touched. Runs under a lock on the batch row: two workers
    finishing pages at once must not both start sheet 4.
    """
    from survey.models import PaperBatch, PaperPage, PaperSheet

    touched = {}
    with transaction.atomic():
        locked = PaperBatch.objects.select_for_update().get(pk=batch.pk)
        pending = list(PaperPage.objects.filter(batch=locked, sheet__isnull=True, pinned=False)
                       .order_by('seq'))
        last = PaperSheet.objects.filter(batch=locked).order_by('-seq').first()
        for page in pending:
            if page.status == 'queued':
                break   # its turn has not come; later pages wait behind it
            if not page.has_code:
                continue   # unrecognised: stays in its own group of the list
            if page.page_number != 1 and last is not None and _continues(last, page):
                page.sheet = last
            else:
                last = PaperSheet.objects.create(
                    batch=locked, seq=locked.next_sheet_seq, printed_form=page.printed_form)
                locked.next_sheet_seq += 1
                page.sheet = last
            page.save(update_fields=['sheet'])
            touched[last.pk] = last
        locked.save(update_fields=['next_sheet_seq'])
    for sheet in touched.values():
        refresh_sheet(sheet)
    return list(touched.values())


def _continues(sheet, page):
    if sheet.printed_form_id != page.printed_form_id or sheet.status not in ('recognising', 'review', 'incomplete'):
        return False
    last_number = sheet.pages.order_by('-page_number').values_list('page_number', flat=True).first()
    return last_number is not None and page.page_number == last_number + 1


def missing_pages(sheet):
    """Page numbers of the form the sheet does not hold (empty when complete)."""
    numbers = sorted(n for n in sheet.pages.values_list('page_number', flat=True) if n)
    total = max([sheet.printed_form.pages if sheet.printed_form_id else 0] +
                [t for t in sheet.pages.values_list('pages_total', flat=True) if t])
    if not total:
        return []
    return [n for n in range(1, total + 1) if n not in numbers]


def duplicate_pages(sheet):
    numbers = [n for n in sheet.pages.values_list('page_number', flat=True) if n]
    return sorted({n for n in numbers if numbers.count(n) > 1})


def refresh_sheet(sheet):
    """Recompute status and the merged extraction from the sheet's pages."""
    from survey.paper.extract import merge_pages
    if sheet.status in ('entered', 'skipped'):
        return sheet
    pages = list(sheet.pages.order_by('page_number', 'seq'))
    if not pages:
        sheet.delete()
        return None
    if sheet.printed_form_id is None:
        sheet.printed_form = next((p.printed_form for p in pages if p.printed_form_id), None)
    if any(p.status == 'queued' for p in pages):
        sheet.status = 'recognising'
    elif missing_pages(sheet) or duplicate_pages(sheet):
        sheet.status = 'incomplete'
    else:
        sheet.status = 'review'
    sheet.extraction, sheet.doubtful_count = merge_pages(pages)
    sheet.save(update_fields=['status', 'extraction', 'doubtful_count', 'printed_form'])
    return sheet


def move_page(page, sheet):
    """Put `page` on `sheet` (None = a new sheet) by the operator's hand; both
    sheets touched are re-evaluated and the page stays where it was put."""
    from survey.models import PaperBatch, PaperSheet
    old = page.sheet
    with transaction.atomic():
        locked = PaperBatch.objects.select_for_update().get(pk=page.batch_id)
        if sheet is None:
            sheet = PaperSheet.objects.create(batch=locked, seq=locked.next_sheet_seq,
                                              printed_form=page.printed_form)
            locked.next_sheet_seq += 1
            locked.save(update_fields=['next_sheet_seq'])
        page.sheet = sheet
        page.pinned = True
        page.save(update_fields=['sheet', 'pinned'])
    if old is not None and old.pk != sheet.pk:
        refresh_sheet(old)
    return refresh_sheet(sheet)


def remove_page(page):
    """Delete the page (image and row); its sheet is re-evaluated, an emptied one goes."""
    sheet = page.sheet
    page.discard_image()
    page.delete()
    if sheet is not None:
        refresh_sheet(sheet)


def next_reviewable(batch, after=None):
    """The next sheet to review in the batch, after `after` (a sheet) when given."""
    from survey.models import PaperSheet
    qs = PaperSheet.objects.filter(batch=batch, status__in=PaperSheet.REVIEWABLE_STATUSES).order_by('seq')
    if after is not None:
        qs = qs.filter(seq__gt=after.seq)
    return qs.first()
