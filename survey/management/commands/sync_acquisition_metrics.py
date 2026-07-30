"""Pull acquisition metrics from Google Search Console and Plausible into the local store.

Run daily by a Render cron job (design D5). Safe to re-run at any time: rows are keyed
by (source, date, segment) and overwritten, so a provider's retroactive revisions land
and a day lost to a transient failure self-heals on the next run.

Usage:
  python manage.py sync_acquisition_metrics                  # last 7 days, both sources
  python manage.py sync_acquisition_metrics --days 400       # backfill as far as the API allows
  python manage.py sync_acquisition_metrics --source gsc     # one source only

Exit status is non-zero only when every requested source failed, so a broken cron run
is visible while a not-configured source is not treated as breakage.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from survey.acquisition import NotConfigured, ProviderError, fetch_gsc, fetch_plausible
from survey.models import AcquisitionDaily, AcquisitionSyncState

FETCHERS = {
    'gsc': fetch_gsc,
    'plausible': fetch_plausible,
}

DEFAULT_DAYS = 7


class Command(BaseCommand):
    help = 'Sync Google Search Console and Plausible metrics into AcquisitionDaily.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=DEFAULT_DAYS,
            help=f'How many trailing days to fetch (default {DEFAULT_DAYS}).',
        )
        parser.add_argument(
            '--source', choices=sorted(FETCHERS), default=None,
            help='Restrict the sync to one source (default: all).',
        )

    def handle(self, *args, **options):
        days = max(1, options['days'])
        sources = [options['source']] if options['source'] else sorted(FETCHERS)

        outcomes = {}
        for source in sources:
            outcomes[source] = self._sync_one(source, days)

        for source, outcome in outcomes.items():
            self._report(source, outcome)

        # Only a genuine failure of everything requested is a failed run. A source that
        # was never configured is a reported state, not breakage (design D6).
        if outcomes and all(o['status'] == 'failed' for o in outcomes.values()):
            self.stderr.write(self.style.ERROR('every requested source failed'))
            raise SystemExit(1)

    def _sync_one(self, source, days):
        """Fetch and store one source. Never raises; returns an outcome dict."""
        state, _ = AcquisitionSyncState.objects.get_or_create(source=source)
        state.last_attempt_at = timezone.now()

        try:
            rows = FETCHERS[source](days)
        except NotConfigured as exc:
            # Leave any previously stored rows alone -- absence of a credential says
            # nothing about the data we already have.
            state.is_configured = False
            state.last_error = str(exc)
            state.save(update_fields=('is_configured', 'last_attempt_at', 'last_error'))
            return {'status': 'not_configured', 'reason': str(exc), 'written': 0}
        except ProviderError as exc:
            state.is_configured = True
            state.last_error = str(exc)
            state.save(update_fields=('is_configured', 'last_attempt_at', 'last_error'))
            return {'status': 'failed', 'reason': str(exc), 'written': 0}

        written = self._store(rows)
        state.is_configured = True
        state.last_error = ''
        state.last_success_at = timezone.now()
        state.save(update_fields=(
            'is_configured', 'last_attempt_at', 'last_success_at', 'last_error',
        ))
        return {'status': 'ok', 'reason': '', 'written': written,
                'days': len({r['date'] for r in rows})}

    @staticmethod
    @transaction.atomic
    def _store(rows):
        """Upsert rows on (source, date, segment). Returns the number written."""
        for row in rows:
            key = {
                'source': row['source'],
                'date': row['date'],
                'segment': row.get('segment', ''),
            }
            values = {k: v for k, v in row.items() if k not in key}
            AcquisitionDaily.objects.update_or_create(**key, defaults=values)
        return len(rows)

    def _report(self, source, outcome):
        status = outcome['status']
        if status == 'ok':
            self.stdout.write(self.style.SUCCESS(
                f"{source}: {outcome['written']} rows across {outcome.get('days', 0)} days"
            ))
        elif status == 'not_configured':
            self.stdout.write(f"{source}: not configured — {outcome['reason']}")
        else:
            self.stderr.write(self.style.ERROR(f"{source}: failed — {outcome['reason']}"))
