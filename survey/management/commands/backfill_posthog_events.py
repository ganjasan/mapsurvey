"""Replay the creator funnel's history into PostHog from timestamps we already store.

PostHog's first event is from 2026-08-15; the platform's first signup is from
2026-02-18. Without this, every funnel in PostHog starts empty and cannot answer
the question that motivated the move -- whether AI onboarding changed activation
needs a *before* as much as an after.

Run order that keeps you out of trouble:

    manage.py backfill_posthog_events --dry-run     # counts, sends nothing
    manage.py backfill_posthog_events               # sends, idempotent
    manage.py check_posthog_funnel_parity           # the actual acceptance test

Safe to re-run: every event carries a deterministic uuid5 derived from
(event, source row), so PostHog deduplicates instead of doubling the funnel.
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import Min

from survey import product_events as pe
from survey.funnel import PUBLISHED_STATUSES
from survey.models import AIGenerationEvent, Question, SurveyHeader, SurveySession
# Re-exported: the id scheme and the migration client are shared with
# `backfill_ai_events`, and both are imported from here by name in tests.
from survey.posthog_backfill import NAMESPACE, event_uuid, send_events  # noqa: F401


class Command(BaseCommand):
    help = 'Backfill historical creator-funnel events into PostHog.'

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
        for name in pe.CREATOR_FUNNEL_EVENTS:
            self.stdout.write(f'{name:34} {counts.get(name, 0):>6}')
        self.stdout.write(f'{"TOTAL":34} {len(events):>6}')

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('dry run — nothing sent'))
            return
        if not events:
            self.stdout.write('nothing to send')
            return

        self._send(events)

    # -- collection -----------------------------------------------------------

    def _collect(self, since):
        """Build the full event list from current database state.

        Mirrors CreatorFunnelService's filters exactly -- real users only,
        non-deleted sessions, PUBLISHED_STATUSES imported from funnel.py rather
        than restated. A copy of that tuple here would drift, and the first
        symptom would be a reconciliation mismatch nobody can explain.
        """
        users = dict(
            User.objects
            .filter(is_staff=False, is_superuser=False)
            .values_list('id', 'date_joined')
        )
        active_ids = set(
            User.objects
            .filter(is_staff=False, is_superuser=False, is_active=True)
            .values_list('id', flat=True)
        )

        out = []

        for uid, joined in users.items():
            out.append(self._event(pe.CREATOR_REGISTERED, joined, uid, uid))
            if uid in active_ids:
                # No activation timestamp is stored; date_joined is the only
                # anchor we have, so this shares the registration moment.
                out.append(self._event(
                    pe.CREATOR_ACTIVATED, joined, uid, uid,
                    source=pe.SOURCE_BACKFILL_PROXY,
                ))

        surveys = (
            SurveyHeader.objects
            .filter(created_by_id__in=users)
            .values('id', 'created_by_id', 'created_at', 'status')
        )
        first_question = {
            r['survey_section__survey_header_id']: r['m']
            for r in (Question.objects
                      .filter(survey_section__survey_header__created_by_id__in=users)
                      .values('survey_section__survey_header_id')
                      .annotate(m=Min('created_at' if _question_has_created_at() else 'id')))
        } if _question_has_created_at() else {}
        first_response = {
            r['survey_id']: r['m']
            for r in (SurveySession.objects
                      .filter(is_deleted=False, survey__created_by_id__in=users)
                      .values('survey_id')
                      .annotate(m=Min('start_datetime')))
        }
        surveys_with_question = set(
            Question.objects
            .filter(survey_section__survey_header__created_by_id__in=users)
            .values_list('survey_section__survey_header_id', flat=True)
        )

        # Surveys the AI generator produced. Without this the re-runnable part of
        # this command becomes a data corruption: `_event` labels everything
        # `manual`, and since `backfill_ai_events` derives the same uuid5 for the
        # same survey, whichever command ran first would win the dedup and pin
        # the wrong creation_method. Both sides must agree instead.
        ai_survey_ids = set(
            AIGenerationEvent.objects
            .filter(created_survey_id__isnull=False)
            .values_list('created_survey_id', flat=True)
        )

        for s in surveys:
            sid, uid, created_at = s['id'], s['created_by_id'], s['created_at']
            props = {
                'survey_id': str(sid),
                'creation_method': (
                    pe.CREATION_AI if sid in ai_survey_ids else pe.CREATION_MANUAL
                ),
            }
            out.append(self._event(pe.SURVEY_CREATED, created_at, uid, sid, **props))

            if sid in surveys_with_question:
                # Question rows carry no creation timestamp of their own, so the
                # survey's does duty. Approximate, and labelled as such.
                out.append(self._event(
                    pe.SURVEY_QUESTION_ADDED, first_question.get(sid) or created_at,
                    uid, sid, source=pe.SOURCE_BACKFILL_PROXY, **props,
                ))

            if s['status'] in PUBLISHED_STATUSES:
                # The known-weak one: no publish-transition timestamp exists
                # before this change, so survey creation stands in -- the same
                # proxy funnel.py._published_first_created already uses.
                out.append(self._event(
                    pe.SURVEY_PUBLISHED, created_at, uid, sid,
                    source=pe.SOURCE_BACKFILL_PROXY, **props,
                ))

            if sid in first_response:
                out.append(self._event(
                    pe.SURVEY_FIRST_RESPONSE, first_response[sid], uid, sid, **props,
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
            # `creation_method` is passed in per survey rather than defaulted
            # here: it belongs to survey-scoped events only, and defaulting it
            # to `manual` put the property on registration and activation too,
            # where it means nothing -- and silently mislabelled AI surveys once
            # the generator existed.
            'properties': {'timestamp_source': source, **props},
        }

    # -- sending --------------------------------------------------------------

    def _send(self, events):
        """Send through the shared historical-migration client.

        Person properties are deliberately not written here -- they go through
        `sync_posthog_person_properties`, present-dated. See survey/posthog_backfill.py
        for why that separation exists.
        """
        send_events(self, events)
        self.stdout.write('now run: manage.py check_posthog_funnel_parity')


def _question_has_created_at():
    """Question has no created_at in the current schema; kept explicit.

    If one is added later this starts using it automatically and the
    SURVEY_QUESTION_ADDED timestamps stop being a proxy.
    """
    return any(f.name == 'created_at' for f in Question._meta.get_fields())
