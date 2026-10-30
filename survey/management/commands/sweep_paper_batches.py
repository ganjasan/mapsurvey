"""Close paper-photo batches nobody has touched for a month and drop their images.

Page images live while a sheet is open for review and go when it is entered
or skipped (change paper-photo-entry, #495). A batch someone started and
walked away from would keep its photographs forever; this closes every open
batch whose `last_activity_at` is older than PAPER_BATCH_TTL_DAYS and deletes
the page images and any originals still waiting to be split. Rows stay —
which sheet of which batch a session came from is still answerable.

Usage:
  python manage.py sweep_paper_batches            # dry run: report only
  python manage.py sweep_paper_batches --delete   # actually close and delete
"""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Close paper-photo batches untouched for PAPER_BATCH_TTL_DAYS and delete their images.'

    def add_arguments(self, parser):
        parser.add_argument('--delete', action='store_true',
                            help='Actually close and delete. Default is a dry run.')
        parser.add_argument('--days', type=int, default=settings.PAPER_BATCH_TTL_DAYS,
                            help='Inactivity window in days (default: %(default)s)')

    def handle(self, *args, **options):
        from survey.models import PaperBatch

        cutoff = timezone.now() - timedelta(days=options['days'])
        stale = PaperBatch.objects.filter(status=PaperBatch.STATUS_OPEN, last_activity_at__lt=cutoff)
        batches = list(stale.select_related('survey'))
        if not batches:
            self.stdout.write('No open batches past the inactivity window.')
            return
        for batch in batches:
            images = batch.pages.exclude(image='').count()
            originals = batch.uploads.exclude(file='').count()
            self.stdout.write(f'batch {batch.pk} ({batch.survey.name}): last activity {batch.last_activity_at:%Y-%m-%d}, '
                              f'{images} page image(s), {originals} original(s)')
            if not options['delete']:
                continue
            for page in batch.pages.exclude(image=''):
                page.discard_image()
                page.save(update_fields=['image'])
            for upload in batch.uploads.exclude(file=''):
                upload.discard_file()
                upload.save(update_fields=['file'])
            batch.status = PaperBatch.STATUS_CLOSED
            batch.save(update_fields=['status'])
        if options['delete']:
            self.stdout.write(f'Closed {len(batches)} batch(es).')
        else:
            self.stdout.write(f'{len(batches)} batch(es) would be closed. Re-run with --delete.')
