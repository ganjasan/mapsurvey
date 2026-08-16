"""Replay the AI drafting sub-funnel into PostHog from `AIGenerationEvent` rows.

The generator shipped before its instrumentation, so the drafts generated in
between exist only in our own table. Same reasoning as the creator-funnel
backfill: a funnel step that is empty before today cannot answer whether AI
onboarding changed anything, which is the only reason to measure it.

    manage.py backfill_ai_events --dry-run     # counts, sends nothing
    manage.py backfill_ai_events               # sends, idempotent

Every timestamp here is one the row already stores. Nothing is proxied:
a row with no `redirected_at` produces no `ai_draft_opened`, rather than one
with a substituted time -- an invented "the creator waited" is worse than a
missing one, because the gap between finishing and opening is exactly the
abandonment measure this exists to produce.
"""

from django.core.management.base import BaseCommand

from survey import product_events as pe
from survey.models import AIGenerationEvent
from survey.posthog_backfill import event_uuid, send_events

# Only rows whose generation actually started. `pending` is not a terminal
# state: it is either in flight right now or a worker died, and neither should
# be replayed as a finished draft.
TERMINAL_OUTCOMES = ('success', 'invalid_draft', 'provider_error', 'error', 'not_configured')


class Command(BaseCommand):
    help = 'Backfill historical AI drafting events into PostHog.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print counts per event type and send nothing.',
        )
        parser.add_argument(
            '--since', default=None, metavar='YYYY-MM-DD',
            help='Only events at or after this date. Omit for all history.',
        )
        parser.add_argument(
            '--limit', type=int, default=None,
            help='Stop after this many events (smoke-testing the pipeline).',
        )

    def handle(self, *args, **options):
        events = sorted(self._collect(options['since']), key=lambda e: e['timestamp'])
        if options['limit']:
            events = events[:options['limit']]

        counts = {}
        for e in events:
            counts[e['event']] = counts.get(e['event'], 0) + 1
        for name in (*pe.AI_DRAFT_EVENTS, pe.SURVEY_CREATED):
            self.stdout.write(f'{name:34} {counts.get(name, 0):>6}')
        self.stdout.write(f'{"TOTAL":34} {len(events):>6}')

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('dry run — nothing sent'))
            return
        if not events:
            self.stdout.write('nothing to send')
            return

        send_events(self, events)

    # -- collection -----------------------------------------------------------

    def _collect(self, since):
        rows = (
            AIGenerationEvent.objects
            .filter(user__isnull=False)
            .values(
                'id', 'user_id', 'created_survey_id', 'outcome', 'created_at',
                'redirected_at', 'languages', 'brief', 'provider', 'model',
                'latency_ms', 'input_tokens', 'output_tokens',
            )
        )

        out = []
        for r in rows:
            uid, rid = r['user_id'], r['id']
            # The request happened whatever came after it, including a row still
            # pending: a brief was submitted and that is the funnel step.
            out.append(self._event(
                pe.AI_DRAFT_REQUESTED, r['created_at'], uid, rid,
                language_count=len(r['languages'] or []),
                has_use_case=bool((r['brief'] or {}).get('use_case')),
            ))

            if r['outcome'] not in TERMINAL_OUTCOMES:
                continue

            # No terminal timestamp is stored -- `created_at` is the only anchor
            # the row has. Labelled as a proxy so a latency insight can drop it;
            # `latency_ms` below carries the real duration where the provider
            # reported one.
            finished = {'outcome': r['outcome']}
            for field in ('provider', 'model', 'latency_ms', 'input_tokens', 'output_tokens'):
                if r[field] not in (None, ''):
                    finished[field] = r[field]
            out.append(self._event(
                pe.AI_DRAFT_FINISHED, r['created_at'], uid, rid,
                source=pe.SOURCE_BACKFILL_PROXY, **finished,
            ))

            if r['outcome'] == 'success' and r['created_survey_id']:
                out.append(self._event(
                    pe.SURVEY_CREATED, r['created_at'], uid, r['created_survey_id'],
                    source=pe.SOURCE_BACKFILL_PROXY,
                    survey_id=str(r['created_survey_id']),
                    creation_method=pe.CREATION_AI,
                ))

            if r['redirected_at']:
                out.append(self._event(
                    pe.AI_DRAFT_OPENED, r['redirected_at'], uid, rid,
                    survey_id=str(r['created_survey_id']),
                ))

        if since:
            out = [e for e in out if e['timestamp'].date().isoformat() >= since]
        return out

    @staticmethod
    def _event(name, timestamp, user_id, *key_parts, source=pe.SOURCE_BACKFILL, **props):
        return {
            'event': name,
            'distinct_id': str(user_id),
            'timestamp': timestamp,
            'uuid': event_uuid(name, *key_parts),
            'properties': {'timestamp_source': source, **props},
        }
