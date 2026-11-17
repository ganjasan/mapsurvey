"""Background work of the Reports module (change reports-pdf, #707).

A report's PDF is rendered here, on the worker, never in a web request: a map block costs an HTTP
call to the static-map service and the layout holds every picture in memory (the 2026-09 memory
and blocked-thread incidents are why). The web side creates a `ReportPdf` row and polls it.
"""
import logging

from celery import shared_task
from django.core.files.base import ContentFile
from django.utils import timezone

log = logging.getLogger('reports.pdf')


@shared_task(bind=True)
def render_report_pdf(self, pdf_id, base_url=''):
    """Render the PDF of one `ReportPdf` row. Runs once per row: a redelivered message finds the
    row past `queued` and returns."""
    from reports.models import ReportPdf
    from reports.pdf import build_pdf
    claimed = ReportPdf.objects.filter(pk=pdf_id, status='queued').update(status='running')
    if not claimed:
        return
    job = ReportPdf.objects.select_related('report__survey', 'report__organization').get(pk=pdf_id)
    try:
        if job.kind == 'zip':
            data = build_zip(job.report)
            job.file.save(f'{job.report.slug}.zip', ContentFile(data), save=False)
        else:
            data = build_pdf(job.report, base_url=base_url)
            job.file.save(f'{job.report.slug}.pdf', ContentFile(data), save=False)
        job.status, job.size, job.error = 'done', len(data), ''
    except Exception as exc:  # noqa: BLE001 — the row carries the failure to the page
        log.exception('report pdf %s failed', pdf_id)
        job.status, job.error = 'failed', str(exc)[:500]
    job.finished_at = timezone.now()
    job.save()


def build_zip(report, lang='en'):
    """Every data block of the report as `<nn>-<title>.png` and `.csv` in one ZIP (change
    reports-embed): the pictures for slides, the numbers behind them — both from the page's
    payload, so masked as the page is."""
    import io
    import zipfile
    from reports.pictures import block_png
    from reports.render import render_data
    from reports.tables import block_csv, file_stem
    survey = report.survey if report.survey_id else None
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for index, payload in enumerate(render_data(report, lang=lang)['blocks'], start=1):
            stem = file_stem(payload, index)
            table = block_csv(payload)
            if table is not None:
                archive.writestr(stem + '.csv', table[1])
            picture = block_png(payload, survey)
            if picture is not None:
                archive.writestr(stem + '.png', picture)
    return buffer.getvalue()
