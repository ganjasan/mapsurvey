"""Report-stage outreach signals: the daily pass, the historical analysis and
the worked-flag pre-fill (change report-stage-outreach-signals).

    manage.py detect_report_stage                      # daily: score, record, digest
    manage.py detect_report_stage --dry-run --as-of 2026-08-01
    manage.py detect_report_stage --historical [--dry-run]
    manage.py detect_report_stage --prefill-worked [--dry-run]

Run on production by the `mapsurvey-report-stage` Render cron (report_stage.sh);
the other two modes by hand, once, in the order design.md's migration plan gives.
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from survey import report_stage


class Command(BaseCommand):
    help = 'Detect surveys entering the reporting stage and tell the owner.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Print what would fire; write nothing, send nothing.')
        parser.add_argument('--as-of', default=None,
                            help='Evaluate every window as of this date (YYYY-MM-DD).')
        parser.add_argument('--historical', action='store_true',
                            help='Walk each survey\'s past and record the signals that would have fired.')
        parser.add_argument('--prefill-worked', action='store_true',
                            help='Mark creators with a sent email on their timeline as worked.')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        as_of = None
        if options['as_of']:
            try:
                as_of = date.fromisoformat(options['as_of'])
            except ValueError:
                raise CommandError('--as-of must be YYYY-MM-DD')

        if options['prefill_worked']:
            marked = report_stage.prefill_worked(dry_run=dry_run)
            verb = 'would mark' if dry_run else 'marked'
            self.stdout.write(f'{verb} {len(marked)} creator(s) as worked from email notes')
            return

        if options['historical']:
            report = report_stage.run_historical(dry_run=dry_run)
            self._table(report, historical=True)
            return

        report = report_stage.run(as_of=as_of, dry_run=dry_run)
        self._table(report, historical=False)
        if report.mail_error:
            raise CommandError(f'digest not sent: {report.mail_error}')

    def _table(self, report, historical):
        prefix = '[dry run] ' if report.dry_run else ''
        self.stdout.write(
            f'{prefix}{"historical" if historical else "as of " + report.as_of.isoformat()}: '
            f'{report.scored} scored, {len(report.fired)} fired, {report.enriched} enriched, '
            f'{report.errors} error(s)'
        )
        if not report.fired:
            return
        header = f'{"survey":40} {"owner":20} {"worked":12} {"fired":10} {"resp":>5}  sub-signals'
        self.stdout.write(header)
        self.stdout.write('-' * len(header))
        for f in sorted(report.fired, key=lambda x: x.fired_on):
            worked = f.worked_since.isoformat() if f.worked_since else '-'
            signals = ', '.join(f'{k}={v}' for k, v in sorted(f.result.signals.items()))
            self.stdout.write(
                f'{(f.survey.name or "")[:40]:40} {f.owner.username[:20]:20} {worked:12} '
                f'{f.fired_on.isoformat():10} {f.result.responses:>5}  {signals}'
            )
        if not historical and not report.dry_run:
            self.stdout.write('digest sent' if report.mail_sent else 'digest NOT sent')
