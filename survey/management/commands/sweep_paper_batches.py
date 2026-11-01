"""Delete the paper responses nobody has touched for a month.

Page images live while a response is open for checking and go when it is
stored (change paper-photo-entry, #495). A response someone started and walked
away from would keep its photographs forever; this deletes every open response
whose `last_activity_at` is older than PAPER_BATCH_TTL_DAYS — pages, images,
its unfinished session (to the trash), the row — and deletes the images of
set-aside photos (on no response) older than that and any original still
waiting to be split. Stored responses are never touched.

Usage:
  python manage.py sweep_paper_batches            # dry run: report only
  python manage.py sweep_paper_batches --delete   # actually delete
"""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Delete open paper responses untouched for PAPER_BATCH_TTL_DAYS, with their photos.'

    def add_arguments(self, parser):
        parser.add_argument('--delete', action='store_true',
                            help='Actually delete. Default is a dry run.')
        parser.add_argument('--days', type=int, default=settings.PAPER_BATCH_TTL_DAYS,
                            help='Inactivity window in days (default: %(default)s)')

    def handle(self, *args, **options):
        from survey.models import PaperPage, PaperSheet, PaperUpload
        from survey.paper.sheets import delete_sheet

        cutoff = timezone.now() - timedelta(days=options['days'])
        stale = list(PaperSheet.objects.filter(status__in=PaperSheet.OPEN_STATUSES, last_activity_at__lt=cutoff)
                     .select_related('batch__survey'))
        loose = list(PaperPage.objects.filter(sheet__isnull=True, created_at__lt=cutoff).exclude(image=''))
        originals = list(PaperUpload.objects.filter(created_at__lt=cutoff).exclude(file=''))
        if not (stale or loose or originals):
            self.stdout.write('Nothing past the inactivity window.')
            return
        for sheet in stale:
            images = sheet.pages.exclude(image='').count()
            self.stdout.write(f'response {sheet.pk} ({sheet.batch.survey.name}): last activity '
                              f'{sheet.last_activity_at:%Y-%m-%d}, {images} page image(s)')
        self.stdout.write(f'{len(loose)} set-aside photo(s), {len(originals)} original(s) past the window')
        if not options['delete']:
            self.stdout.write(f'{len(stale)} response(s) would be deleted. Re-run with --delete.')
            return
        for sheet in stale:
            delete_sheet(sheet)
        for page in loose:
            page.discard_image()
            page.save(update_fields=['image'])
        for upload in originals:
            upload.discard_file()
            upload.save(update_fields=['file'])
        self.stdout.write(f'Deleted {len(stale)} response(s).')
