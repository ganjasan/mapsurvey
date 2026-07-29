"""Import the hand-written outreach dossiers into CreatorProfile / CreatorNote.

Dry run by default; `--apply` writes. Never modifies the source tree. Safe to
re-run: notes are skipped by `source_path`, and profile columns are only
overwritten by non-empty incoming values, so hand corrections survive
(creator-dossiers change, D4).
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from survey.dossiers import (
    date_from_filename, iter_dossiers, normalised_names, parse_emails,
    parse_profile_fields,
)
from survey.models import CreatorNote, CreatorProfile

User = get_user_model()


class Command(BaseCommand):
    help = 'Import docs/marketing/user-outreach/ dossiers into creator profiles and notes.'

    def add_arguments(self, parser):
        parser.add_argument('root', help='Directory holding <username>/profile.md subdirectories.')
        parser.add_argument(
            '--apply', action='store_true',
            help='Write the records (without this the command only reports).',
        )

    def handle(self, *args, **options):
        root = options['root']
        apply_changes = options['apply']

        if not os.path.isdir(root):
            self.stderr.write(self.style.ERROR(f'No such directory: {root}'))
            return

        by_username = {}
        by_email = {}
        for user in User.objects.all():
            by_username[user.username.lower()] = user
            if user.email:
                by_email.setdefault(user.email.lower(), user)
        existing_sources = set(
            CreatorNote.objects.exclude(source_path='')
            .values_list('source_path', flat=True)
        )

        matched = unmatched = notes_created = profiles_touched = 0
        unmatched_names = []
        today = timezone.now().date()

        for dirname, profile_path, correspondence in iter_dossiers(root):
            body = self._read(profile_path) if profile_path and os.path.exists(profile_path) else ''
            user = self._match_user(dirname, body, by_username, by_email)
            if user is None:
                unmatched += 1
                unmatched_names.append(dirname)
                continue
            matched += 1

            new_notes = []

            if body:
                fields = parse_profile_fields(body)
                if fields:
                    profiles_touched += 1
                    if apply_changes:
                        self._update_profile(user, fields)
                rel = os.path.relpath(profile_path)
                if rel not in existing_sources and body.strip():
                    new_notes.append(CreatorNote(
                        user=user, kind='research', body=body, source_path=rel,
                        happened_on=self._file_date(profile_path, today),
                    ))

            for path in correspondence:
                rel = os.path.relpath(path)
                if rel in existing_sources:
                    continue
                body = self._read(path)
                if not body.strip():
                    continue
                new_notes.append(CreatorNote(
                    user=user, kind='email', body=body, source_path=rel,
                    happened_on=date_from_filename(path) or self._file_date(path, today),
                ))

            if new_notes:
                notes_created += len(new_notes)
                self.stdout.write(f'  {user.username}: +{len(new_notes)} note(s)')
                if apply_changes:
                    CreatorNote.objects.bulk_create(new_notes)
                    existing_sources.update(n.source_path for n in new_notes)

        self.stdout.write('')
        self.stdout.write(f'Dossiers matched to a user: {matched}')
        self.stdout.write(f'Unmatched directories:      {unmatched}')
        self.stdout.write(f'Profiles with fields:       {profiles_touched}')
        self.stdout.write(f'Notes to create:            {notes_created}')
        if unmatched_names:
            self.stdout.write('')
            self.stdout.write('Unmatched (no user with this username):')
            for name in unmatched_names:
                self.stdout.write(f'  {name}')

        if apply_changes:
            self.stdout.write(self.style.SUCCESS('\nApplied. Source files untouched.'))
        else:
            self.stdout.write(self.style.WARNING('\nDry run -- nothing written. Re-run with --apply.'))

    @staticmethod
    def _match_user(dirname, body, by_username, by_email):
        """Directory name first, then the email in the dossier header.

        Directory names drift from account names (`j_okafor` vs
        `j.okafor.2@example.edu`), so the header email is the reliable key. Group
        dossiers (`ftspk_class`, `_batch-…`) describe no single account and are
        left unmatched on purpose.
        """
        for name in normalised_names(dirname):
            if name in by_username:
                return by_username[name]
        for address in parse_emails(body):
            if address in by_email:
                return by_email[address]
            if address in by_username:  # several accounts use the email as username
                return by_username[address]
        return None

    def _update_profile(self, user, fields):
        """Write only non-empty incoming values, so hand corrections are not blanked."""
        profile, _ = CreatorProfile.objects.get_or_create(user=user)
        changed = []
        for field, value in fields.items():
            if value and not getattr(profile, field):
                setattr(profile, field, value)
                changed.append(field)
        if changed:
            profile.save(update_fields=changed + ['updated_at'])

    @staticmethod
    def _read(path):
        with open(path, encoding='utf-8', errors='replace') as handle:
            return handle.read()

    @staticmethod
    def _file_date(path, fallback):
        from datetime import date
        try:
            return date.fromtimestamp(os.path.getmtime(path))
        except OSError:
            return fallback
