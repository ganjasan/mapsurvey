"""Classify users into segment cohorts from their email domain.

Dry run by default -- pass --apply to write. Safe to re-run: automatic
classification never touches an assignment a human made (survey/cohorts.py).
"""

import csv
from collections import Counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from survey.cohorts import (
    DIM_SEGMENT, assign_cohort, classify_segment, get_cohort,
)
from survey.models import UserCohort

User = get_user_model()


class Command(BaseCommand):
    help = 'Assign segment cohorts to users based on their email domain.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Write the assignments (without this the command only reports).',
        )
        parser.add_argument(
            '--include-staff', action='store_true',
            help='Also classify staff and superuser accounts (skipped by default).',
        )
        parser.add_argument(
            '--from-csv', dest='from_csv', metavar='PATH',
            help='Apply a curated list instead of the domain rules. CSV columns: '
                 'username, cohort slug, [note]. Rows are written as manual '
                 'assignments, so later rule runs will not overwrite them.',
        )

    def handle(self, *args, **options):
        apply_changes = options['apply']
        if options['from_csv']:
            return self._handle_csv(options['from_csv'], apply_changes)
        users = User.objects.all().order_by('id')
        if not options['include_staff']:
            users = users.filter(is_staff=False, is_superuser=False)

        manual_uids = set(
            UserCohort.objects
            .filter(dimension__slug=DIM_SEGMENT, source='manual')
            .values_list('user_id', flat=True)
        )
        current = dict(
            UserCohort.objects
            .filter(dimension__slug=DIM_SEGMENT)
            .values_list('user_id', 'cohort__slug')
        )

        cohort_cache = {}
        proposed = Counter()
        changes = []
        skipped_manual = 0
        unclassified = 0

        for user in users:
            slug = classify_segment(user.email)
            if slug is None:
                unclassified += 1
                continue
            if user.id in manual_uids:
                skipped_manual += 1
                continue

            proposed[slug] += 1
            if current.get(user.id) == slug:
                continue

            if slug not in cohort_cache:
                cohort_cache[slug] = get_cohort(DIM_SEGMENT, slug)
            cohort = cohort_cache[slug]
            if cohort is None:
                self.stderr.write(self.style.ERROR(
                    f'Cohort "{DIM_SEGMENT}/{slug}" does not exist -- run migrations first.'
                ))
                return

            changes.append((user, cohort, current.get(user.id)))

        for user, cohort, was in changes:
            arrow = f'{was} -> {cohort.slug}' if was else cohort.slug
            self.stdout.write(f'  {user.username} <{user.email}>: {arrow}')
            if apply_changes:
                assign_cohort(user, cohort, source='auto')

        total = users.count()
        self.stdout.write('')
        self.stdout.write(f'Users considered:        {total}')
        self.stdout.write(f'Classified by rule:      {sum(proposed.values())}')
        self.stdout.write(f'No domain signal:        {unclassified}')
        self.stdout.write(f'Skipped (manual label):  {skipped_manual}')
        self.stdout.write(f'Assignments to write:    {len(changes)}')
        for slug, count in proposed.most_common():
            self.stdout.write(f'    {slug:18} {count}')

        self._finish(apply_changes)

    def _handle_csv(self, path, apply_changes):
        """Apply a curated username -> cohort list as manual assignments.

        The dimension is taken from the cohort itself, so the file only names the
        cohort. Unknown usernames and cohorts are reported and skipped rather than
        aborting the run -- a curated list is edited by hand and will have typos.
        """
        cohort_cache = {}
        applied = missing_users = missing_cohorts = 0

        with open(path, newline='', encoding='utf-8') as handle:
            for lineno, row in enumerate(csv.reader(handle), start=1):
                row = [c.strip() for c in row if c.strip() != '']
                if not row or row[0].startswith('#'):
                    continue
                if len(row) < 2:
                    self.stderr.write(self.style.WARNING(
                        f'line {lineno}: expected "username,cohort[,note]" -- skipped'
                    ))
                    continue
                username, cohort_slug = row[0], row[1]
                note = row[2] if len(row) > 2 else ''

                user = User.objects.filter(username=username).first()
                if user is None:
                    missing_users += 1
                    self.stderr.write(self.style.WARNING(
                        f'line {lineno}: no user "{username}" -- skipped'
                    ))
                    continue

                if cohort_slug not in cohort_cache:
                    cohort_cache[cohort_slug] = get_cohort(DIM_SEGMENT, cohort_slug)
                cohort = cohort_cache[cohort_slug]
                if cohort is None:
                    missing_cohorts += 1
                    self.stderr.write(self.style.WARNING(
                        f'line {lineno}: no cohort "{DIM_SEGMENT}/{cohort_slug}" -- skipped'
                    ))
                    continue

                applied += 1
                self.stdout.write(f'  {username}: {cohort_slug}')
                if apply_changes:
                    assign_cohort(user, cohort, source='manual', note=note)

        self.stdout.write('')
        self.stdout.write(f'Rows to assign:          {applied}')
        self.stdout.write(f'Unknown usernames:       {missing_users}')
        self.stdout.write(f'Unknown cohorts:         {missing_cohorts}')
        self._finish(apply_changes)

    def _finish(self, apply_changes):
        if apply_changes:
            self.stdout.write(self.style.SUCCESS('\nApplied.'))
        else:
            self.stdout.write(self.style.WARNING('\nDry run -- nothing written. Re-run with --apply.'))
