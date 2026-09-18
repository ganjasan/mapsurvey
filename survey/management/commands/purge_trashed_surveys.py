"""Permanently purge surveys whose trash retention window has expired.

Thin wrapper around survey.trash.purge_expired_surveys — the same core
drives the /internal/purge-trash/ endpoint used by the curl-based Render
cron. See openspec/changes/survey-deletion-safety/design.md (D6).
"""
from django.core.management.base import BaseCommand, CommandError

from survey.models import SurveyHeader
from survey.trash import purge_expired_surveys


class Command(BaseCommand):
    help = "Permanently delete surveys trashed longer than the retention window"

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=SurveyHeader.TRASH_RETENTION_DAYS,
            help='Retention window in days (default: %(default)s)',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='List surveys that would be purged without deleting anything',
        )

    def handle(self, *args, **options):
        run = purge_expired_surveys(
            days=options['days'], dry_run=options['dry_run'], log=self.stdout.write,
        )
        if run.purged == 0 and run.failed == 0:
            self.stdout.write("Nothing to purge")
        if run.failed:
            # Non-zero exit so a scheduler notices; the per-survey reason is in
            # the log above and in the exception the logger recorded.
            raise CommandError(f"{run.failed} survey(s) could not be purged")
