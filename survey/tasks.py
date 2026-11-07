"""Celery tasks of the survey app that are not AI generation (see survey/ai/tasks.py).

One task per recipient: a bad address retries on its own and never holds the
other participants' mail hostage. `fail_silently=False` on purpose — a
transport failure must raise so Celery retries it and, past the last retry,
the `task_failure` receiver in mapsurvey/celery.py reports it. Silent loss of
a comment notification is the failure this feature exists to prevent.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_thread_notification(self, thread_id, comment_id, actor_id, recipient_id):
    from django.contrib.auth import get_user_model
    from .comments import display_name, resolve_anchor, thread_path
    from .mail import absolute_url, send_templated_mail
    from .models import Comment, CommentThread

    User = get_user_model()
    try:
        thread = CommentThread.objects.select_related('survey').get(pk=thread_id)
        comment = Comment.objects.select_related('author').prefetch_related('attachments').get(pk=comment_id)
        recipient = User.objects.get(pk=recipient_id)
    except (CommentThread.DoesNotExist, Comment.DoesNotExist, User.DoesNotExist):
        logger.warning('thread notification %s/%s/%s: row gone before send', thread_id, comment_id, recipient_id)
        return
    if not recipient.email or comment.deleted_at is not None:
        return

    actor = comment.author
    anchor = resolve_anchor(thread)
    mentioned = comment.mentions.filter(pk=recipient.pk).exists()
    kind_label = {'survey': 'the survey', 'question': 'the question', 'section': 'the section',
                  'session': 'a response', 'block': 'the results block'}[anchor.kind]
    verb = 'mentioned you on' if mentioned else 'commented on'
    context = {
        'actor_name': display_name(actor),
        'verb': verb,
        'kind_label': kind_label,
        'anchor_label': anchor.label,
        'survey_name': thread.survey.name,
        'body': comment.body,
        'attachments': [a.original_name for a in comment.attachments.all()],
        'thread_url': absolute_url(thread_path(thread, anchor)),
        'mentioned': mentioned,
    }
    subject = f'{context["actor_name"]} {verb} “{anchor.label}” · {thread.survey.name}'
    try:
        send_templated_mail('comments/notify', recipient.email, subject, context, fail_silently=False)
    except Exception as exc:  # noqa: BLE001 — retry, then let task_failure report it
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_event_confirmation(self, registration_id):
    """Mail a landing-event registrant their confirmation with the .ics (change landing-events).
    `landing_events.queue_confirmation` sends inline when the broker is down."""
    from .landing_events import send_confirmation
    try:
        send_confirmation(registration_id)
    except Exception as exc:  # noqa: BLE001 — SMTP hiccup: retry, then let Celery report
        raise self.retry(exc=exc)


@shared_task(bind=True)
def purge_event_registrations(self):
    """Daily: delete landing-event registrations 30 days after their event (change landing-events)."""
    from .landing_events import purge
    deleted = purge()
    if deleted:
        logger.info('purged %s event registrations', deleted)
    return deleted


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_abuse_review_notice(self, review_id):
    """Mail the owner about a held or reported survey (change phishing-content-review).
    Same retry/report shape as the comment notification; the inline fallback
    in `content_screening.notify_owner` covers a broker that is down."""
    from .content_screening import send_notice
    from .models import ContentReview

    review = ContentReview.objects.select_related('survey', 'survey__created_by').filter(pk=review_id).first()
    if review is None:
        logger.warning('review notice %s: row gone before send', review_id)
        return
    try:
        send_notice(review, fail_silently=False)
    except Exception as exc:  # noqa: BLE001 — retry, then let task_failure report it
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notify_demo_request(self, request_id, stage):
    """Mail CONTACT_EMAIL about one "Request a demo" step (change request-demo-form).
    Same retry/report shape as the other notices; `demo_request.notify` sends
    inline when the broker is down."""
    from .demo_request import send_notification
    from .models import DemoRequest

    row = DemoRequest.objects.filter(pk=request_id).first()
    if row is None:
        logger.warning('demo request %s: row gone before send', request_id)
        return
    try:
        send_notification(row, stage, fail_silently=False)
    except Exception as exc:  # noqa: BLE001 — retry, then let task_failure report it
        raise self.retry(exc=exc)


@shared_task(bind=True)
def run_survey_import(self, job_id):
    """Import the archive of a SurveyImportJob (change layer-memory-diet).

    Runs once per job: a redelivered message finds the row past `queued` and
    leaves it alone, so an archive is never imported twice. A validation error
    is the creator's to read on the dashboard card; anything else is marked
    failed for them and re-raised so the task_failure receiver reports it."""
    import io
    from django.utils import timezone
    from .models import SurveyImportJob, SurveyCollaborator
    from .serialization import import_survey_from_zip, ImportError as SerializationImportError

    try:
        job = SurveyImportJob.objects.select_related('organization', 'user').get(pk=job_id)
    except SurveyImportJob.DoesNotExist:
        logger.warning('survey import %s: row gone before the worker got to it', job_id)
        return
    if job.status != 'queued':
        return
    job.status = 'running'
    job.started_at = timezone.now()
    job.save(update_fields=['status', 'started_at'])
    try:
        with job.file.open('rb') as fh:
            archive = io.BytesIO(fh.read())   # zipfile seeks; not every storage backend does
        survey, warnings = import_survey_from_zip(archive, organization=job.organization, created_by=job.user)
        if survey is not None:
            SurveyCollaborator.objects.get_or_create(user=job.user, survey=survey, defaults={'role': 'owner'})
        job.survey = survey
        job.warnings = [str(w) for w in warnings]
        job.status = 'done'
    except SerializationImportError as exc:
        job.status = 'failed'
        job.error = str(exc)
    except Exception:
        job.status = 'failed'
        job.error = 'The import failed unexpectedly. The error has been reported.'
        job.finished_at = timezone.now()
        job.discard_file()
        job.save()
        raise
    job.finished_at = timezone.now()
    job.discard_file()
    job.save()


@shared_task(bind=True)
def apply_survey_schedule(self):
    """Close published surveys whose closing time has passed (change survey-schedule).

    Celery beat (embedded in the worker) runs this every five minutes; the management
    command of the same name runs the same function by hand. Idempotent: a survey is
    picked only while `published`, locked with `skip_locked`, and closed through the
    lifecycle service, so an overlapping run or a redelivery finds nothing to do.
    """
    from .schedule import close_due
    return close_due()


# --- Paper forms from photos (change paper-photo-entry, #495) ---------------------
#
# Three tasks, every one idempotent on its row's status so a redelivered message
# does nothing twice. Decoding and the model call live here and nowhere else.

@shared_task(bind=True)
def ingest_paper_upload(self, upload_id):
    """Split one upload into pages (survey/paper/ingest.py) and queue each page."""
    from .models import PaperUpload
    from .paper.ingest import ingest_upload

    try:
        upload = PaperUpload.objects.select_related('batch').get(pk=upload_id)
    except PaperUpload.DoesNotExist:
        logger.warning('paper upload %s: row gone before the worker got to it', upload_id)
        return
    if upload.status != 'queued':
        return
    ingest_upload(upload)
    # Place every page NOW (its code was read at ingest), so the operator sees
    # the photos land in their slots while uploads are still coming in; the
    # model reads them afterwards, once the uploads have settled (owner,
    # 2026-11-01: slots stood "not photographed" behind the reads of earlier pages).
    from .models import PaperPage
    for page in PaperPage.objects.filter(upload=upload, status='queued', sheet__isnull=True).select_related(
            'batch', 'batch__survey', 'printed_form', 'upload', 'upload__sheet'):
        place_new_page(page)
    schedule_reading(upload.batch_id)


# Reading waits this long after the last upload arrived or was split: a stack
# dropped on the page arrives one file at a time.
READ_SETTLE_SECONDS = 4


def schedule_reading(batch_id):
    """Arm the inbox's reader once; it re-arms itself while uploads keep coming."""
    from django.core.cache import cache
    if cache.add(f'paper-read-scheduled:{batch_id}', 1, timeout=600):
        read_pending_pages.apply_async((batch_id,), countdown=READ_SETTLE_SECONDS)


@shared_task(bind=True)
def read_pending_pages(self, batch_id):
    """Queue the model reads of an inbox's placed pages — after the uploads
    settled, in response and page order, so the reads never stand between an
    upload and its slot."""
    from datetime import timedelta
    from django.core.cache import cache
    from django.utils import timezone
    from .models import PaperPage, PaperUpload
    recent = timezone.now() - timedelta(seconds=READ_SETTLE_SECONDS)
    if PaperUpload.objects.filter(batch_id=batch_id, status='queued').exists() or \
            PaperUpload.objects.filter(batch_id=batch_id, created_at__gte=recent).exists():
        read_pending_pages.apply_async((batch_id,), countdown=READ_SETTLE_SECONDS)
        return
    cache.delete(f'paper-read-scheduled:{batch_id}')
    pages = PaperPage.objects.filter(batch_id=batch_id, status='queued', sheet__isnull=False) \
        .order_by('sheet__seq', 'page_number', 'seq').values_list('pk', flat=True)
    for page_id in pages:
        recognise_paper_page.delay(page_id)


def place_new_page(page):
    """Where a freshly ingested page goes (design D4), from its code: on its
    response, or set aside with the reason. Returns the response or None.
    No model is involved; a code the ingest missed is tried once more on the
    stored JPEG, and a page dropped into a response for a known page number
    takes that number."""
    from .paper import accounting, codes, sheets
    jpeg = None
    if not page.has_code:
        with page.image.open('rb') as fh:
            jpeg = fh.read()
        code = codes.decode_jpeg(jpeg)
        if code is not None:
            _apply_code(page, code, 'qr')
    if not page.has_code and page.upload.sheet_id and not page.upload.expected_page \
            and codes.shows_first_page_link(jpeg, page.batch.survey.uuid):
        # Dropped into a response, form code out of frame, but the page-1
        # "answer online" QR is in it: page 1 of that response's form.
        form_id = page.upload.sheet.printed_form_id or _only_form_of(page.batch)
        if form_id is not None:
            page.printed_form_id = form_id
            page.page_number = 1
            page.copy = page.upload.sheet.copy
            page.code_source = 'qr'
            page.save(update_fields=['printed_form', 'page_number', 'copy', 'code_source'])
    if not page.has_code and page.upload.sheet_id and page.upload.expected_page:
        sheet = page.upload.sheet
        page.printed_form_id = sheet.printed_form_id or page.printed_form_id
        page.page_number = page.upload.expected_page
        page.copy = sheet.copy
        page.code_source = 'manual'
        page.save(update_fields=['printed_form', 'page_number', 'copy', 'code_source'])
    if not page.has_code:
        _page_outcome(page, 'unrecognised', error='No code could be read on this page.')
        return None
    sheet = sheets.place_page(page)
    if sheet is None:
        accounting.page_event(page, 'unrecognised')
        return None
    sheets.refresh_sheet(sheet)
    return sheet


# Transient provider errors (overload, connection loss, malformed output) are
# worth two more tries with a pause; a 4xx verdict is not.
PAPER_PAGE_RETRIES = 2
PAPER_PAGE_RETRY_DELAY = 20


@shared_task(bind=True, max_retries=PAPER_PAGE_RETRIES, default_retry_delay=PAPER_PAGE_RETRY_DELAY)
def recognise_paper_page(self, page_id, force=False):
    """Place the page on its response by its code, then read its answers.

    The code comes from the page's QR, read locally at ingest (and once more here
    on the stored image); a page dropped into a response for a known page number
    takes that number when its QR will not read. No model ever reads a code. The
    one model call reads the answers, and is costed the moment it ends: an
    `AIGenerationEvent` row and its `$ai_generation` (survey/paper/accounting.py).
    `force` re-runs a `failed` page (the list's Retry)."""
    from django.utils import timezone
    from .ai import client
    from .ai.client import NotConfigured, ProviderError
    from .models import PaperPage
    from .paper import accounting, codes, extract, sheets

    try:
        page = PaperPage.objects.select_related('batch', 'batch__survey', 'printed_form', 'upload',
                                                'upload__sheet', 'sheet').get(pk=page_id)
    except PaperPage.DoesNotExist:
        logger.warning('paper page %s: row gone before the worker got to it', page_id)
        return
    if page.status != 'queued' and not (force and page.status == 'failed'):
        return
    if not page.image:
        _page_outcome(page, 'failed', error='The page image is gone.')
        return

    # 1. Where it goes — normally settled at ingest (place_new_page); here for a
    # page re-queued by Retry or Attach.
    if page.sheet_id is None:
        if place_new_page(page) is None:
            return
        page.refresh_from_db()
    sheet = page.sheet
    sheets.refresh_sheet(sheet)

    # 2. The answers.
    try:
        provider = client.get_provider()
    except NotConfigured as exc:
        _page_outcome(page, 'failed', error='Reading is not configured on this server.')
        sheets.refresh_sheet(sheet)
        logger.warning('paper page %s: %s', page_id, exc)
        return
    from .ai.quota import QuotaExceeded, check_quota
    try:
        check_quota(page.batch.organization, 'paper_page')
    except QuotaExceeded:
        _page_outcome(page, 'failed', error='This workspace has used its page allowance.')
        sheets.refresh_sheet(sheet)
        return
    event = accounting.start(page, 'paper_page')
    try:
        extraction, usage, _items = extract.extract_page(page, provider)
    except ProviderError as exc:
        accounting.finish(event, page, 'provider_error', usage=getattr(exc, 'usage', None), error=str(exc))
        if exc.transient and self.request.retries < PAPER_PAGE_RETRIES:
            raise self.retry(exc=exc)
        _page_outcome(page, 'failed', error='The page could not be read. Try again.')
        sheets.refresh_sheet(sheet)
        return
    except Exception:
        accounting.finish(event, page, 'error', error='unexpected')
        _page_outcome(page, 'failed', error='The page could not be read. The error has been reported.')
        sheets.refresh_sheet(sheet)
        raise
    accounting.finish(event, page, 'success', usage=usage)
    page.refresh_from_db(fields=['status'])
    if page.status == 'replaced':
        return   # a newer photo of the same page arrived while this one was being read
    page.extraction = extraction
    page.status = 'recognised'
    page.recognised_at = timezone.now()
    page.save(update_fields=['extraction', 'status', 'recognised_at'])
    # A re-shot page: the answers the operator saved from the FIRST reading
    # without touching them give way to this reading (survey/paper/review.py).
    replaced = sheet.pages.filter(page_number=page.page_number, status='replaced').exclude(pk=page.pk) \
        .order_by('-id').first()
    if replaced is not None and replaced.extraction:
        from .paper.review import supersede_machine_answers
        supersede_machine_answers(sheet, replaced.extraction, extraction)
    sheets.refresh_sheet(sheet)
    accounting.page_event(page, 'recognised')
    page.batch.touch()


def _only_form_of(batch):
    """The survey's printed form when there is exactly one, else None (no guessing)."""
    from .models import PrintedForm
    ids = list(PrintedForm.objects.filter(survey_id=batch.survey_id).values_list('pk', flat=True)[:2])
    return ids[0] if len(ids) == 1 else None


def _apply_code(page, code, source):
    from .paper.ingest import _form_of_survey
    page.printed_form_id = _form_of_survey(page.batch, code.form_id)
    page.copy = code.copy
    page.page_number = code.page
    page.pages_total = code.pages
    page.code_source = source
    page.save(update_fields=['printed_form', 'copy', 'page_number', 'pages_total', 'code_source'])


def _page_outcome(page, status, error=''):
    from django.utils import timezone
    from .paper import accounting
    page.status = status
    page.error = error
    page.recognised_at = timezone.now()
    page.save(update_fields=['status', 'error', 'recognised_at'])
    accounting.page_event(page, status)


@shared_task(bind=True)
def delete_sheet_images(self, sheet_id):
    """A response is stored: its page images go, the rows stay."""
    from .models import PaperSheet
    try:
        sheet = PaperSheet.objects.get(pk=sheet_id)
    except PaperSheet.DoesNotExist:
        return
    for page in sheet.pages.all():
        page.discard_image()
        page.save(update_fields=['image'])
