"""Push creator segmentation into PostHog as person properties.

Deliberately a *separate* pass from `backfill_posthog_events`, and not an
optional nicety: during a historical migration PostHog applies `$set` regardless
of the event's timestamp (PostHog/posthog#37000), so a person property attached
to a March event would overwrite today's value. The backfill therefore sends no
`$set` at all, and current state is written here, once, with today's timestamp.

What this buys: today `cohort_breakdown` renders on one admin page. As person
properties the same segmentation filters every insight, every session recording
and every future experiment -- a university-vs-consultancy split of the
activation funnel becomes a dropdown instead of a code change.

What it must not leak: `DomainSegmentRule` maps named customer domains to
segments and is loaded from a gitignored file precisely because this repository
is public. Only the *verdict* (`segment: university`) travels; the rules stay
in our database.
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from survey.cohorts import user_cohort_map
from survey.funnel import FREEMAIL_DOMAINS, _domain


class Command(BaseCommand):
    help = 'Set PostHog person properties (segment, plan, domain) for creators.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--limit', type=int, default=None)

    def handle(self, *args, **options):
        from django.conf import settings

        if not options['dry_run'] and not settings.POSTHOG_PROJECT_KEY:
            raise CommandError('POSTHOG_PROJECT_KEY is not set.')

        assignments = user_cohort_map()
        rows = []
        for uid, email, joined in (
            User.objects
            .filter(is_staff=False, is_superuser=False)
            .values_list('id', 'email', 'date_joined')
        ):
            domain = _domain(email) or ''
            cohorts = assignments.get(uid, {})
            rows.append((uid, {
                'email_domain': domain,
                'is_freemail': bool(domain) and domain in FREEMAIL_DOMAINS,
                'segment': cohorts.get('segment', ''),
                'plan': cohorts.get('plan', ''),
                'date_joined': joined.isoformat(),
            }))

        if options['limit']:
            rows = rows[:options['limit']]

        classified = sum(1 for _, p in rows if p['segment'])
        self.stdout.write(f'creators:   {len(rows)}')
        self.stdout.write(f'with segment: {classified}')
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('dry run — nothing sent'))
            return

        import posthog

        for uid, props in rows:
            # posthog.set(), not a $set rider on a captured event: this is current
            # state carrying today's timestamp, which is the whole point of
            # keeping it out of the historical backfill.
            posthog.set(distinct_id=str(uid), properties=props)
        posthog.flush()
        self.stdout.write(self.style.SUCCESS(f'updated {len(rows)} people'))
