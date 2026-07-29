"""Export creator profiles and notes as CSV.

Two uses, same command: handing the outreach record to a CRM, and answering a
GDPR subject access request for one person (`--username`). Building this now is
what keeps the storage decision reversible (creator-dossiers change, D5).
"""

import csv
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from survey.models import CreatorNote, CreatorProfile, SurveySession

User = get_user_model()

PUBLISHED_STATUSES = ('published', 'closed', 'archived')

PROFILE_COLUMNS = (
    'username', 'email', 'date_joined', 'organization', 'role', 'country',
    'linkedin_url', 'website', 'how_found_us', 'segment', 'plan',
    'surveys', 'published_surveys', 'responses', 'summary',
)

NOTE_COLUMNS = ('username', 'happened_on', 'kind', 'author', 'source_path', 'body')


class Command(BaseCommand):
    help = 'Export creator profiles and notes to CSV for CRM migration or a subject access request.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--out', default='.', help='Directory to write profiles.csv and notes.csv into.',
        )
        parser.add_argument(
            '--username', help='Restrict the export to a single user (subject access request).',
        )

    def handle(self, *args, **options):
        out_dir = options['out']
        username = options['username']
        os.makedirs(out_dir, exist_ok=True)

        users = User.objects.all().order_by('username')
        if username:
            users = users.filter(username=username)
            if not users.exists():
                self.stderr.write(self.style.ERROR(f'No user named "{username}".'))
                return

        users = users.annotate(
            n_surveys=Count('created_surveys', distinct=True),
            n_published=Count('created_surveys', distinct=True,
                              filter=Q(created_surveys__status__in=PUBLISHED_STATUSES)),
        )

        profiles = {p.user_id: p for p in CreatorProfile.objects.all()}
        cohorts = self._cohort_map()
        responses = self._response_counts()

        profiles_path = os.path.join(out_dir, 'profiles.csv')
        with open(profiles_path, 'w', newline='', encoding='utf-8') as handle:
            writer = csv.writer(handle)
            writer.writerow(PROFILE_COLUMNS)
            for user in users:
                p = profiles.get(user.id)
                assigned = cohorts.get(user.id, {})
                writer.writerow([
                    user.username, user.email,
                    user.date_joined.date().isoformat() if user.date_joined else '',
                    getattr(p, 'organization', ''), getattr(p, 'role', ''),
                    getattr(p, 'country', ''), getattr(p, 'linkedin_url', ''),
                    getattr(p, 'website', ''), getattr(p, 'how_found_us', ''),
                    assigned.get('segment', ''), assigned.get('plan', ''),
                    user.n_surveys, user.n_published, responses.get(user.id, 0),
                    getattr(p, 'summary', ''),
                ])

        notes_qs = (CreatorNote.objects
                    .filter(user__in=users)
                    .select_related('user', 'author')
                    .order_by('user__username', 'happened_on'))
        notes_path = os.path.join(out_dir, 'notes.csv')
        with open(notes_path, 'w', newline='', encoding='utf-8') as handle:
            writer = csv.writer(handle)
            writer.writerow(NOTE_COLUMNS)
            count = 0
            for note in notes_qs.iterator():
                writer.writerow([
                    note.user.username, note.happened_on.isoformat(), note.kind,
                    note.author.username if note.author else '',
                    note.source_path, note.body,
                ])
                count += 1

        self.stdout.write(f'Profiles: {users.count()} -> {profiles_path}')
        self.stdout.write(f'Notes:    {count} -> {notes_path}')
        if username:
            self.stdout.write(self.style.WARNING(
                '\nSubject access export: this is everything we hold about this person '
                'in these tables. Review before sending.'
            ))

    @staticmethod
    def _cohort_map():
        from survey.models import UserCohort
        out = {}
        for uid, dim, coh in (UserCohort.objects
                              .values_list('user_id', 'dimension__slug', 'cohort__slug')):
            out.setdefault(uid, {})[dim] = coh
        return out

    @staticmethod
    def _response_counts():
        rows = (SurveySession.objects
                .filter(is_deleted=False, survey__created_by__isnull=False)
                .values('survey__created_by_id')
                .annotate(n=Count('id')))
        return {r['survey__created_by_id']: r['n'] for r in rows}
