"""Write today's row of every *state* series of the staff funnel dashboard.

Active creators, returned share, publish rate and the like describe the present
and cannot be recomputed for a past day, so their history is whatever this
command recorded (`MetricSnapshot`, one row per day and key). The Render cron
`mapsurvey-metrics-snapshot` runs it nightly; it is idempotent per day, so a
double-fired cron or a manual rerun after a fix overwrites rather than
duplicates.

Usage:
  python manage.py snapshot_metrics                     # today's rows
  python manage.py snapshot_metrics --date 2026-10-01   # rows dated so, from the CURRENT state

`--date` is for tests and for labelling a repaired missed night as an
approximation — it never pretends to backfill. An exception propagates so a
failed night is a failed cron run in the Render dashboard, not a silently
missing point. Series live in survey/metrics.py.
"""

from datetime import date

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Snapshot the funnel dashboard state series for today (or --date).'

    def add_arguments(self, parser):
        parser.add_argument('--date', help='YYYY-MM-DD to write the rows under instead of today.')

    def handle(self, *args, **options):
        from survey.metrics import write_snapshots

        day = None
        if options['date']:
            try:
                day = date.fromisoformat(options['date'])
            except ValueError as e:
                raise CommandError(f'--date must be YYYY-MM-DD: {e}')

        written = write_snapshots(day)
        shown = ', '.join(f'{k}={v:g}' for k, v in written.items())
        self.stdout.write(f'snapshot_metrics: {len(written)} series for {day or "today"}: {shown}')
