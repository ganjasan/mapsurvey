"""Tests for the `creator-dossiers` capability (openspec/specs/creator-dossiers/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
import csv
import os
import tempfile
from io import StringIO
from django.core.management import call_command
from django.db.utils import IntegrityError
import datetime
import shutil
from survey.dossiers import date_from_filename, parse_profile_fields
from survey.models import CreatorNote, CreatorProfile


class CreatorProfileModelTest(TestCase):
    """One profile per user, and consumers survive its absence."""

    def setUp(self):
        User.objects.all().delete()
        self.user = User.objects.create_user(username="dossier", password="x")

    def test_profile_is_unique_per_user(self):
        """
        GIVEN a user who already has a profile
        WHEN a second profile is created for them
        THEN the write fails.
        """
        CreatorProfile.objects.create(user=self.user, organization="A")

        with self.assertRaises(IntegrityError):
            CreatorProfile.objects.create(user=self.user, organization="B")

    def test_export_tolerates_missing_profile(self):
        """
        GIVEN a user with no profile
        WHEN the export runs
        THEN it succeeds and the user's row has empty profile columns.
        """
        out = tempfile.mkdtemp()

        call_command("export_creators", "--out", out, stdout=StringIO())

        with open(os.path.join(out, "profiles.csv"), encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        row = next(r for r in rows if r["username"] == "dossier")
        self.assertEqual(row["organization"], "")


class CreatorNoteModelTest(TestCase):
    """The timeline is dated, ordered and tied to the user's lifetime."""

    def setUp(self):
        User.objects.all().delete()
        self.user = User.objects.create_user(username="noted", password="x")
        self.author = User.objects.create_user(username="author", password="x")

    def test_notes_are_ordered_newest_first(self):
        """
        GIVEN notes from March and July
        WHEN the user's notes are listed
        THEN the July note comes first.
        """
        CreatorNote.objects.create(user=self.user, happened_on=datetime.date(2026, 3, 1), body="old")
        CreatorNote.objects.create(user=self.user, happened_on=datetime.date(2026, 7, 1), body="new")

        self.assertEqual(
            [n.body for n in self.user.creator_notes.all()], ["new", "old"],
        )

    def test_deleting_user_removes_dossier(self):
        """
        GIVEN a user with a profile and a note
        WHEN the user is deleted
        THEN both records go with them.
        """
        CreatorProfile.objects.create(user=self.user)
        CreatorNote.objects.create(user=self.user, happened_on=datetime.date(2026, 7, 1), body="x")

        self.user.delete()

        self.assertEqual(CreatorProfile.objects.count(), 0)
        self.assertEqual(CreatorNote.objects.count(), 0)

    def test_note_survives_author_deletion(self):
        """
        GIVEN a note written by a staff member
        WHEN that staff account is deleted
        THEN the note remains, with no author.
        """
        note = CreatorNote.objects.create(
            user=self.user, author=self.author,
            happened_on=datetime.date(2026, 7, 1), body="x",
        )

        self.author.delete()
        note.refresh_from_db()

        self.assertIsNone(note.author)


class DossierParsingTest(TestCase):
    """Header extraction is deliberately conservative."""

    def test_labelled_fields_are_extracted(self):
        """
        GIVEN a dossier header in the observed markdown variants
        WHEN it is parsed
        THEN the labelled values land in the matching fields.
        """
        text = (
            "# testuser\n\n"
            "- **Organization**: [[Northern University]] (NU), Estonia\n"
            "- **Role**: Undergraduate student\n"
            "- **Location**: Tartu, Estonia\n"
        )

        fields = parse_profile_fields(text)

        self.assertEqual(fields["organization"], "Northern University (NU), Estonia")
        self.assertEqual(fields["role"], "Undergraduate student")
        self.assertEqual(fields["country"], "Tartu, Estonia")

    def test_bold_markers_are_stripped_mid_value(self):
        """
        GIVEN a value wrapping only part of itself in bold
        WHEN it is parsed
        THEN no markdown markers remain.
        """
        text = "- **Organization:** **MAPS Studio** (domain mapsstudio.pl)\n"

        self.assertEqual(
            parse_profile_fields(text)["organization"],
            "MAPS Studio (domain mapsstudio.pl)",
        )

    def test_unknown_values_are_not_stored(self):
        """
        GIVEN a header that records ignorance rather than a fact
        WHEN it is parsed
        THEN the field is left empty.
        """
        text = "- **Organization**: Unknown — likely a university course instructor\n"

        self.assertNotIn("organization", parse_profile_fields(text))

    def test_linkedin_url_found_anywhere_in_body(self):
        """
        GIVEN a LinkedIn URL in prose rather than a header
        WHEN the dossier is parsed
        THEN the URL is captured.
        """
        text = "# x\n\nSome prose citing https://de.linkedin.com/in/jane-example here.\n"

        self.assertEqual(
            parse_profile_fields(text)["linkedin_url"],
            "https://de.linkedin.com/in/jane-example",
        )

    def test_tier_is_not_a_recognised_field(self):
        """
        GIVEN a dossier carrying a Tier header
        WHEN it is parsed
        THEN no field captures it.
        """
        fields = parse_profile_fields("- **Tier**: 1A — Active user\n")

        self.assertEqual(fields, {})

    def test_date_from_correspondence_filename(self):
        """
        GIVEN correspondence filenames with and without a date prefix
        WHEN the date is read
        THEN the prefixed one parses and the other returns None.
        """
        self.assertEqual(
            date_from_filename("2026-04-28_initial-outreach.md"),
            datetime.date(2026, 4, 28),
        )
        self.assertIsNone(date_from_filename("notes.md"))


class ImportDossiersCommandTest(TestCase):
    """Import is a dry run by default, idempotent, and never touches the source."""

    def setUp(self):
        User.objects.all().delete()
        self.user = User.objects.create_user(username="testuser", password="x")
        self.root = tempfile.mkdtemp()
        self.dossier = os.path.join(self.root, "testuser")
        os.makedirs(os.path.join(self.dossier, "correspondence"))
        self.profile_path = os.path.join(self.dossier, "profile.md")
        with open(self.profile_path, "w", encoding="utf-8") as handle:
            handle.write(
                "# testuser\n\n- **Organization**: Northern University\n"
                "- **Role**: Student\n- **Tier**: 1A\n\nLong prose about the person.\n"
            )
        self.letter_path = os.path.join(
            self.dossier, "correspondence", "2026-04-28_initial-outreach.md",
        )
        with open(self.letter_path, "w", encoding="utf-8") as handle:
            handle.write("# Initial outreach\n\nSENT 2026-04-28\n\nHi there.\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_dry_run_writes_nothing(self):
        """
        GIVEN a dossier tree
        WHEN the importer runs without --apply
        THEN no profile or note is created.
        """
        call_command("import_dossiers", self.root, stdout=StringIO())

        self.assertEqual(CreatorProfile.objects.count(), 0)
        self.assertEqual(CreatorNote.objects.count(), 0)

    def test_apply_creates_profile_and_notes(self):
        """
        GIVEN a dossier with a profile body and one letter
        WHEN the importer is applied
        THEN the header fields land on the profile, the body becomes a research
        note and the letter becomes a dated email note.
        """
        call_command("import_dossiers", self.root, "--apply", stdout=StringIO())

        profile = CreatorProfile.objects.get(user=self.user)
        self.assertEqual(profile.organization, "Northern University")
        research = CreatorNote.objects.get(user=self.user, kind="research")
        self.assertIn("Long prose about the person", research.body)
        email = CreatorNote.objects.get(user=self.user, kind="email")
        self.assertEqual(email.happened_on, datetime.date(2026, 4, 28))
        self.assertIn("SENT 2026-04-28", email.body)

    def test_tier_is_not_imported(self):
        """
        GIVEN a dossier carrying a Tier header
        WHEN it is imported
        THEN no profile field holds the tier.
        """
        call_command("import_dossiers", self.root, "--apply", stdout=StringIO())

        profile = CreatorProfile.objects.get(user=self.user)
        for field in ("organization", "role", "country", "how_found_us"):
            self.assertNotIn("1A", getattr(profile, field))

    def test_source_files_are_untouched(self):
        """
        GIVEN a dossier tree
        WHEN the importer is applied
        THEN the source files are byte-identical afterwards.
        """
        before = open(self.profile_path, encoding="utf-8").read()

        call_command("import_dossiers", self.root, "--apply", stdout=StringIO())

        self.assertEqual(open(self.profile_path, encoding="utf-8").read(), before)

    def test_reimport_does_not_duplicate_notes(self):
        """
        GIVEN an import that has already been applied
        WHEN it is applied again over the same tree
        THEN the note count is unchanged.
        """
        call_command("import_dossiers", self.root, "--apply", stdout=StringIO())
        first = CreatorNote.objects.count()

        call_command("import_dossiers", self.root, "--apply", stdout=StringIO())

        self.assertEqual(CreatorNote.objects.count(), first)

    def test_reimport_does_not_blank_corrected_fields(self):
        """
        GIVEN a hand-corrected organisation
        WHEN the import is applied again
        THEN the correction is retained.
        """
        call_command("import_dossiers", self.root, "--apply", stdout=StringIO())
        profile = CreatorProfile.objects.get(user=self.user)
        profile.organization = "Northern University, School of Governance"
        profile.save(update_fields=["organization"])

        call_command("import_dossiers", self.root, "--apply", stdout=StringIO())

        profile.refresh_from_db()
        self.assertEqual(profile.organization, "Northern University, School of Governance")

    def test_unmatched_directory_is_reported_not_imported(self):
        """
        GIVEN a dossier directory matching no user
        WHEN the importer is applied
        THEN nothing is created for it and its name is reported.
        """
        ghost = os.path.join(self.root, "ghost-user")
        os.makedirs(ghost)
        with open(os.path.join(ghost, "profile.md"), "w", encoding="utf-8") as handle:
            handle.write("# ghost\n\nSomeone who never registered.\n")
        out = StringIO()

        call_command("import_dossiers", self.root, "--apply", stdout=out)

        self.assertIn("ghost-user", out.getvalue())
        self.assertFalse(CreatorNote.objects.filter(body__contains="never registered").exists())


class ExportCreatorsCommandTest(TestCase):
    """The CRM exit path, which doubles as the subject access answer."""

    def setUp(self):
        User.objects.all().delete()
        self.user = User.objects.create_user(
            username="exported", email="e@example.com", password="x",
        )
        self.other = User.objects.create_user(username="other", password="x")
        CreatorProfile.objects.create(user=self.user, organization="Example Consulting")
        CreatorNote.objects.create(
            user=self.user, happened_on=datetime.date(2026, 7, 1),
            body='Comma, "quoted" words,\nand a second line.',
        )
        CreatorNote.objects.create(
            user=self.other, happened_on=datetime.date(2026, 7, 2), body="other person",
        )
        self.out = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.out, ignore_errors=True)

    def _read(self, name):
        with open(os.path.join(self.out, name), encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def test_export_writes_both_files(self):
        """
        GIVEN profiles and notes
        WHEN the export runs
        THEN both CSV files exist with their rows.
        """
        call_command("export_creators", "--out", self.out, stdout=StringIO())

        self.assertEqual(len(self._read("profiles.csv")), 2)
        self.assertEqual(len(self._read("notes.csv")), 2)

    def test_single_user_export_excludes_everyone_else(self):
        """
        GIVEN two users with notes
        WHEN the export is restricted to one username
        THEN only that user's rows are written.
        """
        call_command("export_creators", "--out", self.out,
                     "--username", "exported", stdout=StringIO())

        self.assertEqual([r["username"] for r in self._read("profiles.csv")], ["exported"])
        self.assertEqual([r["username"] for r in self._read("notes.csv")], ["exported"])

    def test_note_body_survives_the_round_trip(self):
        """
        GIVEN a note body with commas, quotes and newlines
        WHEN it is exported and parsed back
        THEN the body is unchanged.
        """
        call_command("export_creators", "--out", self.out,
                     "--username", "exported", stdout=StringIO())

        self.assertEqual(
            self._read("notes.csv")[0]["body"],
            'Comma, "quoted" words,\nand a second line.',
        )


class CreatorDossierAdminTest(TestCase):
    """Dossiers are staff-only and visible on the user page."""

    def setUp(self):
        User.objects.all().delete()
        self.staff = User.objects.create_user(
            username="dossier-staff", password="x", is_staff=True, is_superuser=True,
        )
        self.subject = User.objects.create_user(username="subject", password="x")
        CreatorProfile.objects.create(user=self.subject, organization="Example Partners")
        CreatorNote.objects.create(
            user=self.subject, happened_on=datetime.date(2026, 7, 1),
            body="Spoke about the riverside plan.",
        )

    def test_staff_sees_profile_and_notes_on_user_page(self):
        """
        GIVEN a user with a dossier
        WHEN a staff member opens them in the admin
        THEN the organisation and the note body are shown.
        """
        self.client.force_login(self.staff)

        response = self.client.get(f"/admin/auth/user/{self.subject.id}/change/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Example Partners")
        self.assertContains(response, "riverside plan")

    def test_non_staff_is_denied(self):
        """
        GIVEN a user who is not staff
        WHEN they request the notes admin
        THEN they are not served the page.
        """
        self.client.force_login(self.subject)

        response = self.client.get("/admin/survey/creatornote/")

        self.assertNotEqual(response.status_code, 200)


class DossierUserMatchingTest(TestCase):
    """Directory names drift from account names; the header email is the fallback."""

    def setUp(self):
        User.objects.all().delete()
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _dossier(self, dirname, body):
        path = os.path.join(self.root, dirname)
        os.makedirs(path)
        with open(os.path.join(path, "profile.md"), "w", encoding="utf-8") as handle:
            handle.write(body)

    def test_punctuation_variant_of_username_matches(self):
        """
        GIVEN a user named sample.w266 and a directory named sample_w266
        WHEN the import is applied
        THEN the dossier attaches to that user.
        """
        user = User.objects.create_user(username="sample.w266", password="x")
        self._dossier("sample_w266", "# sample\n\nSome prose.\n")

        call_command("import_dossiers", self.root, "--apply", stdout=StringIO())

        self.assertTrue(CreatorNote.objects.filter(user=user).exists())

    def test_header_email_matches_when_name_does_not(self):
        """
        GIVEN a user whose username is an email and a differently named directory
        carrying that email in its header
        WHEN the import is applied
        THEN the dossier attaches to that user.
        """
        user = User.objects.create_user(
            username="mbrito7@example.com", email="mbrito7@example.com", password="x",
        )
        self._dossier("mbrito7", "# mbrito7\n\n- **Email**: mbrito7@example.com\n\nProse.\n")

        call_command("import_dossiers", self.root, "--apply", stdout=StringIO())

        self.assertTrue(CreatorNote.objects.filter(user=user).exists())

    def test_group_dossier_without_any_known_member_is_unmatched(self):
        """
        GIVEN a group dossier naming only unregistered addresses
        WHEN the import is applied
        THEN nothing is created and the directory is reported.
        """
        self._dossier("ftspk_class", "# class\n\n- **Email**: nobody@example.org\n")
        out = StringIO()

        call_command("import_dossiers", self.root, "--apply", stdout=out)

        self.assertIn("ftspk_class", out.getvalue())
        self.assertEqual(CreatorNote.objects.count(), 0)
