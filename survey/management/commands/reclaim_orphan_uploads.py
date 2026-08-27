"""Delete respondent uploads that never became answers.

Files upload the moment a respondent picks them; a popup closed without Apply,
an abandoned section, a replaced file — all leave an Upload with
attached=False. After a grace period long enough to span an interrupted
session, those rows and their stored objects go.

Usage:
  python manage.py reclaim_orphan_uploads            # dry run: report only
  python manage.py reclaim_orphan_uploads --delete   # actually delete

The post_delete signal on Upload removes the stored object with the row, so a
queryset delete here cannot leak files. Attached uploads are never touched —
they belong to submitted answers.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

GRACE_HOURS = 48


class Command(BaseCommand):
    help = 'Delete uploads never attached to a submitted answer (48h grace).'

    def add_arguments(self, parser):
        parser.add_argument('--delete', action='store_true',
                            help='Actually delete. Default is a dry run.')

    def handle(self, *args, **options):
        from survey.models import Upload

        cutoff = timezone.now() - timedelta(hours=GRACE_HOURS)
        orphans = Upload.objects.filter(attached=False, created_at__lt=cutoff)

        count = orphans.count()
        if not count:
            self.stdout.write('No orphaned uploads past the grace period.')
            return

        if not options['delete']:
            total = sum(orphans.values_list('size', flat=True))
            self.stdout.write(f'would delete {count} uploads ({total} bytes) — pass --delete')
            return

        # .delete() row by row through the queryset fires the post_delete
        # signal per instance, which is what removes each stored object.
        deleted = 0
        for orphan in orphans.iterator():
            orphan.delete()
            deleted += 1
        self.stdout.write(self.style.SUCCESS(f'Reclaimed {deleted} orphaned uploads.'))
