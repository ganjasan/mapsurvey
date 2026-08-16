"""Shared machinery for replaying historical events into PostHog.

Extracted from `backfill_posthog_events` when a second backfill (AI drafting)
needed the same three guarantees, and a copy of them would have been a copy of
the two rules that are easy to get wrong:

- **Deterministic ids.** Every event carries a `uuid5` derived from (event name,
  source row), so PostHog deduplicates a re-run instead of doubling the funnel.
- **A dedicated client.** `historical_migration` is a client-level setting in
  this SDK, so a backfill builds its own client and can never reconfigure the
  live one out from under a running process.
- **No person properties.** During a historical migration PostHog applies `$set`
  regardless of the event's timestamp (PostHog/posthog#37000), so a February
  event would clobber today's values. The guard raises rather than trusting
  anyone to remember.
"""

import uuid

from django.core.management.base import CommandError

# Stable namespace for deterministic event ids. Changing it re-imports everything
# as new events -- which is why it is a constant here and not a setting.
NAMESPACE = uuid.UUID('6f9a1a7e-0d3c-4c1f-9a2e-5f1b2c3d4e5f')


def event_uuid(event, *parts):
    """Deterministic id for one (event, source row) pair.

    Idempotency is the difference between a migration we can re-run and a
    one-shot we are afraid to touch.
    """
    return str(uuid.uuid5(NAMESPACE, ':'.join([event, *(str(p) for p in parts)])))


def send_events(command, events):
    """Send prepared events through a historical-migration client."""
    from django.conf import settings

    from posthog import Client

    if not settings.POSTHOG_PROJECT_KEY:
        raise CommandError(
            'POSTHOG_PROJECT_KEY is not set — refusing to run a backfill against nothing.'
        )

    client = Client(
        settings.POSTHOG_PROJECT_KEY,
        host=settings.POSTHOG_API_HOST,
        historical_migration=True,
    )
    try:
        for i, e in enumerate(events, 1):
            if '$set' in e['properties'] or '$set_once' in e['properties']:
                raise CommandError(
                    'refusing to send $set during a historical migration '
                    '(PostHog/posthog#37000 overwrites regardless of timestamp)'
                )
            client.capture(
                e['event'],
                distinct_id=e['distinct_id'],
                properties=e['properties'],
                timestamp=e['timestamp'],
                uuid=e['uuid'],
            )
            if i % 250 == 0:
                command.stdout.write(f'  sent {i}/{len(events)}')
        client.flush()
    finally:
        client.shutdown()

    command.stdout.write(command.style.SUCCESS(f'sent {len(events)} events'))
