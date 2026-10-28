"""Tests for the `user-cohorts` capability (openspec/specs/user-cohorts/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from survey.models import Organization, SurveyHeader, SurveySession
from survey.funnel import CreatorFunnelService
from django.conf import settings
import csv
import os
import tempfile
from io import StringIO
from django.core.management import call_command
from django.db.utils import IntegrityError
from survey.cohorts import assign_cohort, classify_segment, get_cohort
from survey.models import Cohort, CohortDimension, DomainSegmentRule, UserCohort


class CohortVocabularyTest(TestCase):
    """Dimensions and cohorts as staff-editable data."""

    def test_seed_migration_created_both_dimensions(self):
        """
        GIVEN a migrated database
        WHEN the seeded cohort vocabulary is queried
        THEN the plan and segment dimensions exist with their cohorts.
        """
        self.assertTrue(CohortDimension.objects.filter(slug="plan").exists())
        self.assertTrue(CohortDimension.objects.filter(slug="segment").exists())
        self.assertIsNotNone(get_cohort("plan", "pro"))
        self.assertIsNotNone(get_cohort("segment", "municipality"))

    def test_same_slug_allowed_in_two_dimensions(self):
        """
        GIVEN a cohort slug already used in the plan dimension
        WHEN the same slug is created in the segment dimension
        THEN both cohorts exist.
        """
        plan = CohortDimension.objects.get(slug="plan")
        segment = CohortDimension.objects.get(slug="segment")
        Cohort.objects.create(dimension=plan, slug="other", name="Other")
        Cohort.objects.create(dimension=segment, slug="other", name="Other")

        self.assertEqual(Cohort.objects.filter(slug="other").count(), 2)

    def test_duplicate_slug_within_dimension_rejected(self):
        """
        GIVEN the free cohort in the plan dimension
        WHEN a second cohort with the same slug is created there
        THEN the write fails.
        """
        plan = CohortDimension.objects.get(slug="plan")
        with self.assertRaises(IntegrityError):
            Cohort.objects.create(dimension=plan, slug="free", name="Free again")


class CohortAssignmentTest(TestCase):
    """One cohort per dimension, and manual assignments win."""

    def setUp(self):
        self.user = User.objects.create_user(username="coh", password="x")
        self.university = get_cohort("segment", "university")
        self.consultancy = get_cohort("segment", "consultancy")
        self.pro = get_cohort("plan", "pro")

    def test_user_holds_cohorts_in_two_dimensions(self):
        """
        GIVEN a user
        WHEN they are assigned a plan cohort and a segment cohort
        THEN both assignments coexist.
        """
        assign_cohort(self.user, self.pro)
        assign_cohort(self.user, self.university)

        slugs = set(UserCohort.objects.filter(user=self.user)
                    .values_list("cohort__slug", flat=True))
        self.assertEqual(slugs, {"pro", "university"})

    def test_reassignment_within_dimension_replaces(self):
        """
        GIVEN a user assigned the university segment
        WHEN they are assigned the consultancy segment
        THEN exactly one segment assignment remains, pointing at consultancy.
        """
        assign_cohort(self.user, self.university)
        assign_cohort(self.user, self.consultancy)

        rows = UserCohort.objects.filter(user=self.user, dimension__slug="segment")
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().cohort.slug, "consultancy")

    def test_dimension_derived_from_cohort(self):
        """
        GIVEN an assignment saved with a mismatched dimension
        WHEN it is saved
        THEN the dimension is corrected to the cohort's own dimension.
        """
        row = UserCohort(
            user=self.user,
            dimension=CohortDimension.objects.get(slug="plan"),
            cohort=self.university,
        )
        row.save()

        self.assertEqual(row.dimension.slug, "segment")

    def test_auto_does_not_overwrite_manual(self):
        """
        GIVEN a manually assigned segment
        WHEN an automatic rule proposes a different cohort
        THEN the manual assignment is untouched.
        """
        assign_cohort(self.user, self.consultancy, source="manual")
        result = assign_cohort(self.user, self.university, source="auto")

        self.assertIsNone(result)
        row = UserCohort.objects.get(user=self.user, dimension__slug="segment")
        self.assertEqual(row.cohort.slug, "consultancy")
        self.assertEqual(row.source, "manual")

    def test_auto_updates_its_own_earlier_guess(self):
        """
        GIVEN an automatic segment assignment
        WHEN classification proposes a different cohort
        THEN the assignment is updated and stays automatic.
        """
        assign_cohort(self.user, self.university, source="auto")
        assign_cohort(self.user, self.consultancy, source="auto")

        row = UserCohort.objects.get(user=self.user, dimension__slug="segment")
        self.assertEqual(row.cohort.slug, "consultancy")
        self.assertEqual(row.source, "auto")

    def test_manual_overrides_auto(self):
        """
        GIVEN an automatic segment assignment
        WHEN a staff member assigns a different cohort
        THEN the assignment becomes manual.
        """
        assign_cohort(self.user, self.university, source="auto")
        assign_cohort(self.user, self.consultancy, source="manual")

        row = UserCohort.objects.get(user=self.user, dimension__slug="segment")
        self.assertEqual(row.cohort.slug, "consultancy")
        self.assertEqual(row.source, "manual")


class SegmentClassificationTest(TestCase):
    """Email-domain rules propose a segment, or decline to."""

    def test_academic_domains_map_to_university(self):
        """
        GIVEN institutional academic addresses
        WHEN they are classified
        THEN the university segment is proposed.
        """
        for email in ("a@example.edu", "b@example.ac.uk", "c@uni-example.de"):
            with self.subTest(email=email):
                self.assertEqual(classify_segment(email), "university")

    def test_government_domains_map_to_municipality(self):
        """
        GIVEN public-sector addresses
        WHEN they are classified
        THEN the municipality segment is proposed.
        """
        for email in ("a@example.gov.uk", "b@example.gov", "c@example.gov.au"):
            with self.subTest(email=email):
                self.assertEqual(classify_segment(email), "municipality")

    def test_student_domain_beats_academic_rule(self):
        """
        GIVEN a student sub-domain of a university
        WHEN it is classified
        THEN the student-cohort segment is proposed, not university.
        """
        self.assertEqual(classify_segment("a@student.example.edu"), "student-cohort")

    def test_database_rule_overrides_suffix_rule(self):
        """
        GIVEN a database rule mapping an .org domain to municipality
        WHEN an address at that domain is classified
        THEN the rule wins over the .org suffix rule.
        """
        DomainSegmentRule.objects.create(
            domain="county.example.org", cohort=get_cohort("segment", "municipality"),
        )

        self.assertEqual(classify_segment("x@county.example.org"), "municipality")

    def test_suffix_rules_apply_without_any_database_rule(self):
        """
        GIVEN no domain rules at all
        WHEN an .ac.uk address is classified
        THEN the university cohort is proposed.
        """
        self.assertEqual(DomainSegmentRule.objects.count(), 0)

        self.assertEqual(classify_segment("x@example.ac.uk"), "university")

    def test_preloaded_map_is_used_instead_of_querying(self):
        """
        GIVEN a preloaded domain map naming a domain with no database rule
        WHEN an address at that domain is classified with that map
        THEN the mapped cohort is proposed.
        """
        result = classify_segment(
            "x@firm.example.net", domain_map={"firm.example.net": "consultancy"},
        )

        self.assertEqual(result, "consultancy")

    def test_freemail_yields_no_proposal(self):
        """
        GIVEN a freemail address
        WHEN it is classified
        THEN nothing is proposed.
        """
        self.assertIsNone(classify_segment("someone@gmail.com"))

    def test_malformed_email_yields_no_proposal(self):
        """
        GIVEN an empty or malformed address
        WHEN it is classified
        THEN nothing is proposed and no error is raised.
        """
        self.assertIsNone(classify_segment(""))
        self.assertIsNone(classify_segment(None))
        self.assertIsNone(classify_segment("no-at-sign"))


class AssignCohortsCommandTest(TestCase):
    """The bulk classification command is a dry run by default and idempotent."""

    def setUp(self):
        User.objects.all().delete()
        User.objects.create_user(username="prof", email="p@example.edu", password="x")
        User.objects.create_user(username="civic", email="c@example.gov.uk", password="x")
        User.objects.create_user(username="anon", email="a@gmail.com", password="x")

    def test_dry_run_writes_nothing(self):
        """
        GIVEN classifiable users
        WHEN the command runs without --apply
        THEN no assignment is created.
        """
        call_command("assign_cohorts", stdout=StringIO())

        self.assertEqual(UserCohort.objects.count(), 0)

    def test_apply_creates_assignments(self):
        """
        GIVEN classifiable users
        WHEN the command runs with --apply
        THEN each classifiable user gets an automatic assignment.
        """
        call_command("assign_cohorts", "--apply", stdout=StringIO())

        slugs = dict(UserCohort.objects.values_list("user__username", "cohort__slug"))
        self.assertEqual(slugs, {"prof": "university", "civic": "municipality"})
        self.assertTrue(all(r.source == "auto" for r in UserCohort.objects.all()))

    def test_second_apply_is_a_noop(self):
        """
        GIVEN the command has already been applied
        WHEN it is applied again unchanged
        THEN the assignments and their timestamps are unchanged.
        """
        call_command("assign_cohorts", "--apply", stdout=StringIO())
        before = list(UserCohort.objects.order_by("id")
                      .values_list("id", "cohort_id", "assigned_at"))

        call_command("assign_cohorts", "--apply", stdout=StringIO())
        after = list(UserCohort.objects.order_by("id")
                     .values_list("id", "cohort_id", "assigned_at"))

        self.assertEqual(before, after)

    def test_apply_skips_manual_assignments(self):
        """
        GIVEN a user labelled by hand
        WHEN the command is applied
        THEN their manual label survives.
        """
        prof = User.objects.get(username="prof")
        assign_cohort(prof, get_cohort("segment", "consultancy"), source="manual")

        call_command("assign_cohorts", "--apply", stdout=StringIO())

        row = UserCohort.objects.get(user=prof, dimension__slug="segment")
        self.assertEqual(row.cohort.slug, "consultancy")
        self.assertEqual(row.source, "manual")


class CohortBreakdownTest(TestCase):
    """The dashboard slices the funnel by cohort."""

    def setUp(self):
        User.objects.all().delete()
        self.org = Organization.objects.create(name="Cohort Org")

    def _creator(self, username, cohort_slug=None, published=False, responses=0):
        user = User.objects.create_user(username=username, password="x")
        if cohort_slug:
            assign_cohort(user, get_cohort("segment", cohort_slug))
        if published or responses:
            survey = SurveyHeader.objects.create(
                organization=self.org, name=f"s-{username}", created_by=user,
                status="published" if published else "draft",
            )
            for _ in range(responses):
                SurveySession.objects.create(survey=survey)
        return user

    def _segment_rows(self):
        blocks = {b["slug"]: b for b in CreatorFunnelService().cohort_breakdown()}
        return {r["label"]: r for r in blocks["segment"]["rows"]}

    def test_rows_partition_all_registrations(self):
        """
        GIVEN labelled and unlabelled creators
        WHEN the breakdown is computed
        THEN the cohort rows plus unclassified sum to the registration total.
        """
        self._creator("labelled", "university")
        self._creator("unlabelled")

        block = {b["slug"]: b for b in CreatorFunnelService().cohort_breakdown()}["segment"]
        self.assertEqual(sum(r["users"] for r in block["rows"]), block["total"])
        self.assertEqual(block["total"], 2)

    def test_activation_counted_per_cohort(self):
        """
        GIVEN a cohort of two creators, one of whom published and collected
        WHEN the breakdown is computed
        THEN that cohort reports one published and one collecting creator.
        """
        self._creator("active", "consultancy", published=True, responses=3)
        self._creator("idle", "consultancy")

        row = self._segment_rows()["Consultancies"]
        self.assertEqual(row["users"], 2)
        self.assertEqual(row["published"], 1)
        self.assertEqual(row["collecting"], 1)
        self.assertEqual(row["responses"], 3)

    def test_unclassified_row_present_when_no_assignments(self):
        """
        GIVEN creators with no cohort at all
        WHEN the breakdown is computed
        THEN every user lands in the unclassified row and nothing errors.
        """
        self._creator("nobody")

        rows = self._segment_rows()
        self.assertEqual(rows["Unclassified"]["users"], 1)

    def test_staff_are_excluded(self):
        """
        GIVEN a staff account
        WHEN the breakdown is computed
        THEN it is not counted as a registration.
        """
        User.objects.create_user(username="staffy", password="x", is_staff=True)
        self._creator("real")

        block = {b["slug"]: b for b in CreatorFunnelService().cohort_breakdown()}["segment"]
        self.assertEqual(block["total"], 1)


class CohortDashboardViewTest(TestCase):
    """The funnel dashboard renders the audience block."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username="dash-staff", password="x", is_staff=True, is_superuser=True,
        )
        self.client.force_login(self.staff)

    def test_dashboard_shows_cohort_dimensions(self):
        """
        GIVEN a staff user
        WHEN they open the funnel dashboard
        THEN the audience block lists every cohort dimension.
        """
        response = self.client.get("/admin/survey/funnelreport/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Audience mix")
        self.assertContains(response, "Universities")
        self.assertContains(response, "Unclassified")


class AssignCohortsFromCsvTest(TestCase):
    """Curated lists label the users no rule can reach."""

    def setUp(self):
        User.objects.all().delete()
        self.user = User.objects.create_user(
            username="curated", email="c@gmail.com", password="x",
        )
        self.path = os.path.join(tempfile.mkdtemp(), "labels.csv")

    def _write(self, body):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(body)

    def test_csv_assigns_manual_labels(self):
        """
        GIVEN a curated list naming a freemail user
        WHEN the command is applied with --from-csv
        THEN the user gets that cohort as a manual assignment.
        """
        self._write("# comment\ncurated,ngo,Community group\n")

        call_command("assign_cohorts", "--from-csv", self.path, "--apply",
                     stdout=StringIO())

        row = UserCohort.objects.get(user=self.user, dimension__slug="segment")
        self.assertEqual(row.cohort.slug, "ngo")
        self.assertEqual(row.source, "manual")
        self.assertEqual(row.note, "Community group")

    def test_csv_dry_run_writes_nothing(self):
        """
        GIVEN a curated list
        WHEN the command runs without --apply
        THEN no assignment is created.
        """
        self._write("curated,ngo\n")

        call_command("assign_cohorts", "--from-csv", self.path, stdout=StringIO())

        self.assertEqual(UserCohort.objects.count(), 0)

    def test_csv_labels_survive_a_later_rule_run(self):
        """
        GIVEN a curated label on a user
        WHEN the domain rules are applied afterwards
        THEN the curated label is untouched.
        """
        self.user.email = "c@example.edu"
        self.user.save(update_fields=["email"])
        self._write("curated,ngo\n")
        call_command("assign_cohorts", "--from-csv", self.path, "--apply",
                     stdout=StringIO())

        call_command("assign_cohorts", "--apply", stdout=StringIO())

        row = UserCohort.objects.get(user=self.user, dimension__slug="segment")
        self.assertEqual(row.cohort.slug, "ngo")

    def test_unknown_rows_are_skipped_not_fatal(self):
        """
        GIVEN a list naming an unknown user and an unknown cohort
        WHEN the command is applied
        THEN those rows are skipped and the valid row still lands.
        """
        self._write("ghost,ngo\ncurated,not-a-cohort\ncurated,ngo\n")

        call_command("assign_cohorts", "--from-csv", self.path, "--apply",
                     stdout=StringIO(), stderr=StringIO())

        self.assertEqual(UserCohort.objects.count(), 1)
        self.assertEqual(
            UserCohort.objects.get().cohort.slug, "ngo",
        )

    def test_shipped_curated_file_is_well_formed(self):
        """
        GIVEN the curated file in the private ops repo (settings.OPS_DIR)
        WHEN its rows are read
        THEN every row names a cohort that exists in the segment dimension.

        The ops repo holds lead dossiers with personal data and is never part of
        this checkout, so the file is absent in CI -- skip rather than fail there.
        """
        path = os.path.join(
            settings.OPS_DIR, "docs", "marketing", "cohorts",
            "segment-manual-2026-07-29.csv",
        )
        if not os.path.exists(path):
            self.skipTest("curated cohort file not present (ops repo not checked out)")
        slugs = set(Cohort.objects.filter(dimension__slug="segment")
                    .values_list("slug", flat=True))

        with open(path, newline="", encoding="utf-8") as handle:
            rows = [
                [c.strip() for c in row if c.strip()]
                for row in csv.reader(handle)
            ]
        rows = [r for r in rows if r and not r[0].startswith("#")]

        self.assertTrue(rows)
        for row in rows:
            with self.subTest(row=row[0]):
                self.assertGreaterEqual(len(row), 2)
                self.assertIn(row[1], slugs)


class DomainRuleLoadingTest(TestCase):
    """Domain rules come from a local file, never from source or a migration."""

    def setUp(self):
        DomainSegmentRule.objects.all().delete()
        self.path = os.path.join(tempfile.mkdtemp(), "rules.csv")

    def _write(self, body):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(body)

    def test_dry_run_writes_no_rules(self):
        """
        GIVEN a rules file
        WHEN it is loaded without --apply
        THEN no rule is created.
        """
        self._write("firm.example.net,consultancy,A firm\n")

        call_command("assign_cohorts", "--rules-csv", self.path, stdout=StringIO())

        self.assertEqual(DomainSegmentRule.objects.count(), 0)

    def test_rules_are_created_then_updated(self):
        """
        GIVEN a rules file applied once
        WHEN it is applied again with a different cohort for the same domain
        THEN one rule remains, pointing at the newer cohort.
        """
        self._write("firm.example.net,consultancy\n")
        call_command("assign_cohorts", "--rules-csv", self.path, "--apply", stdout=StringIO())

        self._write("firm.example.net,business\n")
        call_command("assign_cohorts", "--rules-csv", self.path, "--apply", stdout=StringIO())

        rules = DomainSegmentRule.objects.all()
        self.assertEqual(rules.count(), 1)
        self.assertEqual(rules.first().cohort.slug, "business")

    def test_unknown_cohort_row_is_skipped(self):
        """
        GIVEN a rules file naming a cohort that does not exist
        WHEN it is applied
        THEN no rule is created for that row.
        """
        self._write("firm.example.net,not-a-cohort\n")

        call_command("assign_cohorts", "--rules-csv", self.path, "--apply",
                     stdout=StringIO(), stderr=StringIO())

        self.assertEqual(DomainSegmentRule.objects.count(), 0)

    def test_domain_is_stored_lowercased(self):
        """
        GIVEN a rule saved with a mixed-case domain
        WHEN it is read back
        THEN the domain is lowercase.
        """
        rule = DomainSegmentRule.objects.create(
            domain="  Firm.Example.NET ", cohort=get_cohort("segment", "consultancy"),
        )

        rule.refresh_from_db()
        self.assertEqual(rule.domain, "firm.example.net")

    def test_one_rule_per_domain(self):
        """
        GIVEN a rule for a domain
        WHEN a second rule is created for the same domain
        THEN the write fails.
        """
        DomainSegmentRule.objects.create(
            domain="firm.example.net", cohort=get_cohort("segment", "consultancy"),
        )

        with self.assertRaises(IntegrityError):
            DomainSegmentRule.objects.create(
                domain="firm.example.net", cohort=get_cohort("segment", "business"),
            )

    def test_classification_uses_loaded_rules(self):
        """
        GIVEN rules loaded from a file
        WHEN users at those domains are classified
        THEN they receive the cohorts the rules name.
        """
        User.objects.all().delete()
        User.objects.create_user(username="a", email="x@firm.example.net", password="x")
        self._write("firm.example.net,consultancy\n")
        call_command("assign_cohorts", "--rules-csv", self.path, "--apply", stdout=StringIO())

        call_command("assign_cohorts", "--apply", stdout=StringIO())

        self.assertEqual(
            UserCohort.objects.get(user__username="a").cohort.slug, "consultancy",
        )
