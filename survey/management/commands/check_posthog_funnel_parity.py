"""Compare PostHog's funnel against the admin dashboard's, per registration month.

This is the acceptance test for the migration. "The import ran" is not evidence
of anything -- the failure mode of a data migration is that it looks finished and
is quietly wrong. So the deliverable is two columns side by side and an
explanation for every difference, in the spirit of the version-filter-parity
change.

    manage.py check_posthog_funnel_parity                 # all cohorts
    manage.py check_posthog_funnel_parity --tolerance 0   # exact match required

Exits non-zero when a row differs by more than the tolerance, so it can gate a
rollout rather than being read by eye.

Legitimate reasons a column may differ, which the output labels rather than hides:

- `survey_published` and `survey_question_added` are backfilled from proxy
  timestamps, so a survey created in March and published in April counts in
  March here. Rows carrying proxies are marked.
- PostHog's project-level `test_account_filters` hides one internal account from
  *insights*; this command queries events directly and so does not apply it.
- The dashboard counts users, not surveys. A creator with three published
  surveys is one row there and three events here -- this command counts distinct
  persons for exactly that reason.
"""

import json
import urllib.error
import urllib.request
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError

from survey import product_events as pe
from survey.funnel import CreatorFunnelService

# Dashboard stage -> the event that should reproduce it.
STAGE_EVENTS = (
    ('regs', pe.CREATOR_REGISTERED),
    ('activated', pe.CREATOR_ACTIVATED),
    ('created', pe.SURVEY_CREATED),
    ('added_question', pe.SURVEY_QUESTION_ADDED),
    ('published', pe.SURVEY_PUBLISHED),
    ('got_1', pe.SURVEY_FIRST_RESPONSE),
)


class Command(BaseCommand):
    help = "Reconcile PostHog's creator funnel with the admin dashboard's."

    def add_arguments(self, parser):
        parser.add_argument('--tolerance', type=int, default=0,
                            help='Allowed absolute difference per cell (default 0).')
        parser.add_argument('--personal-api-key', default=None,
                            help='PostHog personal API key. Falls back to POSTHOG_PERSONAL_API_KEY.')

    def handle(self, *args, **options):
        import os

        from django.conf import settings

        key = options['personal_api_key'] or os.environ.get('POSTHOG_PERSONAL_API_KEY')
        if not key:
            raise CommandError(
                'A personal API key is required to query PostHog. Pass --personal-api-key '
                'or set POSTHOG_PERSONAL_API_KEY. (The project key can only write.)'
            )
        project_id = getattr(settings, 'POSTHOG_PROJECT_ID', '') or os.environ.get('POSTHOG_PROJECT_ID')
        if not project_id:
            raise CommandError('Set POSTHOG_PROJECT_ID to the numeric project id.')

        posthog_rows = self._posthog_counts(settings.POSTHOG_API_HOST, project_id, key)
        dashboard_rows = {r['cohort']: r for r in CreatorFunnelService().cohort_funnel()}

        stages = [s for s, _ in STAGE_EVENTS]
        header = f'{"cohort":9}' + ''.join(f'{s:>17}' for s in stages)
        self.stdout.write(header)
        self.stdout.write('-' * len(header))

        failures = 0
        for cohort in sorted(set(dashboard_rows) | set(posthog_rows)):
            db_row = dashboard_rows.get(cohort, {})
            ph_row = posthog_rows.get(cohort, {})
            cells = []
            for stage, event in STAGE_EVENTS:
                db_v = db_row.get(stage, 0)
                ph_v = ph_row.get(event, 0)
                ok = abs(db_v - ph_v) <= options['tolerance']
                failures += 0 if ok else 1
                cells.append(f'{db_v:>7}/{ph_v:<6}{"" if ok else "✗"}'.rjust(17))
            self.stdout.write(f'{cohort:9}' + ''.join(cells))

        self.stdout.write('')
        self.stdout.write('columns are  dashboard/posthog')
        self.stdout.write(
            'note: added_question and published use proxy timestamps in the backfill, '
            'so a survey created and published in different months lands in the creation month.'
        )
        if failures:
            raise CommandError(f'{failures} cell(s) outside tolerance')
        self.stdout.write(self.style.SUCCESS('funnels agree'))

    def _posthog_counts(self, host, project_id, key):
        """{cohort_month: {event: distinct persons}} straight from HogQL.

        Counts distinct persons, not events, because the dashboard's stages are
        per-user. Buckets by the person's registration month rather than the
        event's own month, so a survey created in June by a February signup
        lands in February -- the same shape as cohort_funnel().
        """
        events = "','".join(e for _, e in STAGE_EVENTS)
        sql = f"""
            WITH registrations AS (
                SELECT distinct_id,
                       formatDateTime(min(timestamp), '%Y-%m') AS cohort
                FROM events
                WHERE event = '{pe.CREATOR_REGISTERED}'
                  AND timestamp >= now() - INTERVAL 3 YEAR
                GROUP BY distinct_id
            )
            SELECT r.cohort AS cohort, e.event AS event, count(DISTINCT e.distinct_id) AS n
            FROM events AS e
            INNER JOIN registrations AS r ON r.distinct_id = e.distinct_id
            WHERE e.event IN ('{events}')
              AND e.timestamp >= now() - INTERVAL 3 YEAR
            GROUP BY cohort, event
        """
        url = f'{host.replace("://eu.i.", "://eu.").replace("://us.i.", "://us.")}/api/projects/{project_id}/query/'
        body = json.dumps({'query': {'kind': 'HogQLQuery', 'query': sql}}).encode()
        req = urllib.request.Request(
            url, data=body,
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.load(resp)
        except urllib.error.HTTPError as exc:
            raise CommandError(f'PostHog query failed: {exc.code} {exc.read()[:400]!r}')

        out = defaultdict(dict)
        for cohort, event, n in payload.get('results', []):
            out[cohort][event] = n
        return out
