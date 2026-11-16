"""List — and freeze — the published live reports of workspaces without the Reports feature
(change reports-pro, #709).

Reports is a Pro module; a published report of a workspace without it is served as a frozen
snapshot. `reports.gate.freeze_if_lapsed` does that the first time such a report is opened; this
command does it for all of them at once, so that on ship day every snapshot carries the ship day's
date, and `--dry-run` gives the count for the letter to their owners.

    python manage.py freeze_reports_without_pro --dry-run
    python manage.py freeze_reports_without_pro
"""
from django.core.management.base import BaseCommand

from reports import gate


class Command(BaseCommand):
    help = 'Freeze published live reports of workspaces without the Reports feature.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='List the reports, change nothing.')

    def handle(self, *args, **options):
        reports = gate.lapsed_reports()
        for report in reports:
            self.stdout.write('%s\t/r/%s/\tworkspace %s (%s)\t%s blocks' % (
                'would freeze' if options['dry_run'] else 'frozen', report.slug,
                report.organization.slug, report.organization_id, report.blocks.count()))
            if not options['dry_run']:
                gate.freeze_if_lapsed(report)
        workspaces = len({r.organization_id for r in reports})
        self.stdout.write(self.style.SUCCESS('%d report(s) in %d workspace(s)%s' % (
            len(reports), workspaces, ' — dry run, nothing changed' if options['dry_run'] else '')))
