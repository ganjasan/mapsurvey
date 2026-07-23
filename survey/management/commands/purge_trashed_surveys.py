"""Permanently purge surveys whose trash retention window has expired.

Intended to run daily (Render Cron Job). Uses the same purge routine as the
manual Delete-forever action and writes a survey_auto_purge audit record per
survey with no actor. See openspec/changes/survey-deletion-safety/design.md (D6).
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from survey.models import AuditLog, SurveyHeader
from survey.trash import purge_survey


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
        cutoff = timezone.now() - timedelta(days=options['days'])
        expired = SurveyHeader.objects.filter(deleted_at__lt=cutoff)

        if not expired.exists():
            self.stdout.write("Nothing to purge")
            return

        for survey in expired:
            if options['dry_run']:
                self.stdout.write(f"Would purge '{survey.name}' ({survey.uuid}), trashed {survey.deleted_at:%Y-%m-%d}")
                continue

            AuditLog.objects.create(
                actor=None,
                action='survey_auto_purge',
                survey_uuid=survey.uuid,
                survey_name=survey.name,
                metadata={'trashed_at': survey.deleted_at.isoformat(), 'retention_days': options['days']},
            )
            purge_survey(survey)
            self.stdout.write(f"Purged '{survey.name}' ({survey.uuid})")
