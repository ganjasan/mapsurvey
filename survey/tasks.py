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
    for page_id in upload.pages.values_list('pk', flat=True):
        recognise_paper_page.delay(page_id)


# Transient provider errors (overload, connection loss, malformed output) are
# worth two more tries with a pause; a 4xx verdict is not.
PAPER_PAGE_RETRIES = 2
PAPER_PAGE_RETRY_DELAY = 20


@shared_task(bind=True, max_retries=PAPER_PAGE_RETRIES, default_retry_delay=PAPER_PAGE_RETRY_DELAY)
def recognise_paper_page(self, page_id, force=False):
    """Read the page's form code, place it on a sheet, extract its answers.

    `force` re-runs a `failed` page (the list's Retry). Costs are accounted the
    moment each call ends: an `AIGenerationEvent` row and its `$ai_generation`
    (survey/paper/accounting.py)."""
    from django.utils import timezone
    from .ai import client
    from .ai.client import NotConfigured, ProviderError
    from .models import PaperPage
    from .paper import accounting, codes, extract, sheets

    try:
        page = PaperPage.objects.select_related('batch', 'batch__survey', 'printed_form').get(pk=page_id)
    except PaperPage.DoesNotExist:
        logger.warning('paper page %s: row gone before the worker got to it', page_id)
        return
    if page.status != 'queued' and not (force and page.status == 'failed'):
        return
    if not page.image:
        _page_outcome(page, 'failed', error='The page image is gone.')
        return
    batch = page.batch

    try:
        provider = client.get_provider()
    except NotConfigured as exc:
        _page_outcome(page, 'failed', error='Reading is not configured on this server.')
        logger.warning('paper page %s: %s', page_id, exc)
        return

    # 1. The form code: QR locally, footer text by the model as a fallback.
    if not page.has_code:
        with page.image.open('rb') as fh:
            jpeg = fh.read()
        parsed = codes.decode_qr(jpeg)
        source = 'qr'
        if parsed is None:
            event = accounting.start(page, 'paper_code')
            try:
                parsed, usage = codes.read_code_with_model(provider, jpeg)
            except ProviderError as exc:
                accounting.finish(event, page, 'provider_error', usage=getattr(exc, 'usage', None), error=str(exc))
                del jpeg
                if exc.transient and self.request.retries < PAPER_PAGE_RETRIES:
                    raise self.retry(exc=exc)
                _page_outcome(page, 'failed', error='The page could not be read. Try again.')
                return
            accounting.finish(event, page, 'success', usage=usage)
            source = 'text'
        del jpeg
        if parsed is None or not _assign_code(page, parsed, source):
            _page_outcome(page, 'unrecognised', code_source='')
            sheets.place_pages(batch)
            return

    # 2. The answers.
    event = accounting.start(page, 'paper_page')
    try:
        extraction, usage, _items = extract.extract_page(page, provider)
    except ProviderError as exc:
        accounting.finish(event, page, 'provider_error', usage=getattr(exc, 'usage', None), error=str(exc))
        if exc.transient and self.request.retries < PAPER_PAGE_RETRIES:
            raise self.retry(exc=exc)
        _page_outcome(page, 'failed', error='The page could not be read. Try again.')
        sheets.place_pages(batch)
        return
    except Exception:
        accounting.finish(event, page, 'error', error='unexpected')
        _page_outcome(page, 'failed', error='The page could not be read. The error has been reported.')
        sheets.place_pages(batch)
        raise
    accounting.finish(event, page, 'success', usage=usage)
    page.extraction = extraction
    page.status = 'recognised'
    page.error = ''
    page.recognised_at = timezone.now()
    page.save(update_fields=['extraction', 'status', 'error', 'recognised_at'])
    sheets.place_pages(batch)
    if page.sheet_id:
        sheets.refresh_sheet(page.sheet)
    accounting.page_event(page, 'recognised')
    batch.touch()


def _assign_code(page, parsed, source):
    """Record the parsed (form_id, page, pages) on the page when the form is this
    batch's survey's; False otherwise (someone else's form)."""
    from .models import PrintedForm
    form_id, number, pages_total = parsed
    form = PrintedForm.objects.filter(pk=form_id, survey=page.batch.survey_id).first()
    if form is None or number < 1:
        return False
    page.printed_form = form
    page.page_number = number
    page.pages_total = pages_total or form.pages or None
    page.code_source = source
    page.save(update_fields=['printed_form', 'page_number', 'pages_total', 'code_source'])
    return True


def _page_outcome(page, status, error='', code_source=None):
    from django.utils import timezone
    from .paper import accounting
    page.status = status
    page.error = error
    if code_source is not None:
        page.code_source = code_source
    page.recognised_at = timezone.now()
    page.save(update_fields=['status', 'error', 'code_source', 'recognised_at'])
    accounting.page_event(page, status)


@shared_task(bind=True)
def delete_sheet_images(self, sheet_id):
    """A sheet is entered or skipped: its page images go, the rows stay."""
    from .models import PaperSheet
    try:
        sheet = PaperSheet.objects.get(pk=sheet_id)
    except PaperSheet.DoesNotExist:
        return
    for page in sheet.pages.all():
        page.discard_image()
        page.save(update_fields=['image'])
