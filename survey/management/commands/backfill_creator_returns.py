"""Restore `CreatorSurveyActivity` rows for the period before the table
existed, from the `responses_viewed` / `data_exported` events PostHog has held
since the distribution-events change (spec creator-return-activity).

    POSTHOG_PERSONAL_API_KEY=... manage.py backfill_creator_returns [--until YYYY-MM-DD] [--dry-run]

Writes only days before `--until` (default: the first day the application
recorded a row itself), never touches an existing row, marks what it writes
`restored=True`. Re-runnable. A `data_exported` without a `format` is the
survey.json backup and is skipped, as the forward helper skips it.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Min

from survey.models import CreatorSurveyActivity, SurveyHeader
from survey.posthog_query import PostHogQueryError, credentials, hogql
from survey.versioning import canonical_of

SQL = """
    SELECT distinct_id,
           properties.survey_id AS survey_id,
           event,
           toDate(timestamp) AS day,
           count() AS n,
           max(timestamp) AS last_at
    FROM events
    WHERE event IN ('responses_viewed', 'data_exported')
      AND properties.timestamp_source = 'live'
      AND (event = 'responses_viewed' OR properties.format != '')
      AND toDate(timestamp) < toDate('{until}')
      AND timestamp >= now() - INTERVAL 3 YEAR
    GROUP BY distinct_id, survey_id, event, day
"""


class Command(BaseCommand):
    help = 'Restore creator return-activity rows from PostHog for the period before recording began.'

    def add_arguments(self, parser):
        parser.add_argument('--until', default=None,
                            help='Restore days strictly before this date (default: first recorded day).')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--personal-api-key', default=None)

    def handle(self, *args, **options):
        until = None
        if options['until']:
            try:
                until = date.fromisoformat(options['until'])
            except ValueError:
                raise CommandError('--until must be YYYY-MM-DD')
        if until is None:
            until = (CreatorSurveyActivity.objects.filter(restored=False)
                     .aggregate(first=Min('day'))['first'])
        if until is None:
            raise CommandError('Nothing recorded yet: pass --until explicitly.')

        try:
            host, project_id, key = credentials(options['personal_api_key'])
            rows = hogql(SQL.format(until=until.isoformat()), host, project_id, key)
        except PostHogQueryError as exc:
            raise CommandError(str(exc))

        User = get_user_model()
        users = {str(u.pk): u for u in User.objects.all()}
        surveys = {str(s.pk): s for s in SurveyHeader.objects.all()}
        to_create, skipped = [], 0
        for distinct_id, survey_id, event, day, n, last_at in rows:
            user = users.get(str(distinct_id))
            survey = surveys.get(str(survey_id))
            if user is None or survey is None:
                skipped += 1
                continue
            to_create.append(CreatorSurveyActivity(
                user=user, survey=canonical_of(survey), kind=event,
                day=date.fromisoformat(str(day)[:10]), count=int(n),
                last_at=last_at, restored=True,
            ))

        verb = 'would restore' if options['dry_run'] else 'restored'
        if not options['dry_run']:
            created = CreatorSurveyActivity.objects.bulk_create(to_create, ignore_conflicts=True)
            n_created = len(created)
        else:
            n_created = len(to_create)
        self.stdout.write(f'{verb} {n_created} row(s) before {until.isoformat()}; '
                          f'{skipped} event(s) skipped (unknown user or survey)')
