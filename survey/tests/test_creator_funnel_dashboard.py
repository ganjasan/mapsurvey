"""Tests for the `creator-funnel-dashboard` capability (openspec/specs/creator-funnel-dashboard/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from survey.models import SurveyHeader, SurveySection, Question, SurveySession
from survey.funnel import CreatorFunnelService
from datetime import timedelta as _timedelta
from survey.funnel import bar_chart_geometry
from survey.funnel import dashboard_context as _dashboard_context
from survey.models import SignupAttribution
from survey.tests.helpers import _make_org, _u, _user_at


class CreatorFunnelServiceTest(TestCase):
    """Tests for the platform creator acquisition->activation funnel service."""

    def setUp(self):
        self.org = _make_org("FunnelOrg")
        now = timezone.now()
        self.march = now.replace(year=2026, month=3, day=10, hour=12, minute=0, second=0, microsecond=0)
        self.april = now.replace(year=2026, month=4, day=15, hour=12, minute=0, second=0, microsecond=0)

        # Excluded populations.
        _user_at("staff_user", self.march, is_staff=True)
        _user_at("super_user", self.march, is_superuser=True)

        # March cohort.
        self.a = _user_at("creator_a", self.march)   # created + question + published + 5 resp
        self.b = _user_at("creator_b", self.march)   # created draft, no question, 0 resp

        # April cohort.
        self.c = _user_at("creator_c", self.april)   # created + question + testing + 1 resp (+1 deleted)
        _user_at("creator_d", self.april)            # registered, never created

        # Survey A: published, has a question, 5 non-deleted sessions.
        sa = SurveyHeader.objects.create(name="a_survey", organization=self.org,
                                         created_by=self.a, status="published")
        sec_a = SurveySection.objects.create(name="a_sec", survey_header=sa, is_head=True)
        Question.objects.create(name="a_q", survey_section=sec_a, input_type="text", order_number=1)
        for _ in range(5):
            SurveySession.objects.create(survey=sa)

        # Survey B: draft, no question, no sessions.
        SurveyHeader.objects.create(name="b_survey", organization=self.org,
                                    created_by=self.b, status="draft")

        # Survey C: testing (NOT published), has a question, 1 live + 1 deleted session.
        sc = SurveyHeader.objects.create(name="c_survey", organization=self.org,
                                         created_by=self.c, status="testing")
        sec_c = SurveySection.objects.create(name="c_sec", survey_header=sc, is_head=True)
        Question.objects.create(name="c_q", survey_section=sec_c, input_type="text", order_number=1)
        SurveySession.objects.create(survey=sc)
        SurveySession.objects.create(survey=sc, is_deleted=True)

    def _cohort(self, rows, key):
        return next(r for r in rows if r["cohort"] == key)

    def test_cohort_counts_and_stage_membership(self):
        """
        GIVEN two cohorts of real creators at different activation stages
        WHEN cohort_funnel() aggregates them
        THEN each cohort reports correct registration and per-stage counts
        """
        rows = CreatorFunnelService().cohort_funnel()
        mar = self._cohort(rows, "2026-03")
        apr = self._cohort(rows, "2026-04")

        self.assertEqual(mar["regs"], 2)
        self.assertEqual(mar["created"], 2)
        self.assertEqual(mar["added_question"], 1)   # only A has a question
        self.assertEqual(mar["published"], 1)        # only A is published
        self.assertEqual(mar["got_1"], 1)
        self.assertEqual(mar["got_5"], 1)
        self.assertEqual(mar["got_10"], 0)

        self.assertEqual(apr["regs"], 2)
        self.assertEqual(apr["created"], 1)          # only C created
        self.assertEqual(apr["added_question"], 1)
        self.assertEqual(apr["published"], 0)        # C is 'testing', not published

    def test_staff_and_superusers_excluded(self):
        """
        GIVEN staff and superuser accounts exist
        WHEN the funnel aggregates registrations
        THEN neither appears in any cohort count
        """
        rows = CreatorFunnelService().cohort_funnel()
        total_regs = sum(r["regs"] for r in rows)
        self.assertEqual(total_regs, 4)  # a, b, c, d only

    def test_deleted_sessions_not_counted(self):
        """
        GIVEN survey C has one live and one deleted session
        WHEN response thresholds are computed
        THEN only the live session counts (got_1 == 1, got_5 == 0)
        """
        apr = self._cohort(CreatorFunnelService().cohort_funnel(), "2026-04")
        self.assertEqual(apr["got_1"], 1)
        self.assertEqual(apr["got_5"], 0)

    def test_alltime_totals_match_cohort_sums(self):
        """
        GIVEN the per-cohort funnel
        WHEN alltime_totals() sums the stages
        THEN totals equal the sum across cohorts
        """
        svc = CreatorFunnelService()
        totals = svc.alltime_totals()
        self.assertEqual(totals["regs"], 4)
        self.assertEqual(totals["created"], 3)
        self.assertEqual(totals["added_question"], 2)
        self.assertEqual(totals["published"], 1)
        self.assertEqual(totals["got_1"], 2)
        self.assertEqual(totals["got_5"], 1)
        self.assertEqual(totals["got_10"], 0)

    def test_weekly_signups_sum(self):
        """
        GIVEN four real registrations
        WHEN weekly_signups() groups by week
        THEN the weekly counts sum to four and rows carry ISO week + count
        """
        weekly = CreatorFunnelService().weekly_signups()
        self.assertEqual(sum(w["signups"] for w in weekly), 4)
        self.assertTrue(all("week" in w and "signups" in w for w in weekly))


class FunnelDashboardAdminAccessTest(TestCase):
    """Access control for the staff-only funnel dashboard admin page."""

    def setUp(self):
        self.url = reverse("admin:survey_funnelreport_changelist")

    def test_staff_sees_dashboard(self):
        """
        GIVEN a staff user
        WHEN they open the funnel dashboard admin page
        THEN it renders with the funnel content
        """
        User.objects.create_superuser("boss", "boss@example.com", "x")
        c = Client()
        c.login(username="boss", password="x")
        resp = c.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Monthly cohort funnel")
        self.assertContains(resp, "Living users")

    def test_non_staff_denied(self):
        """
        GIVEN an authenticated non-staff user
        WHEN they request the funnel dashboard admin page
        THEN they are redirected to the admin login (no funnel data)
        """
        User.objects.create_user("plain", password="x")
        c = Client()
        c.login(username="plain", password="x")
        resp = c.get(self.url)
        self.assertEqual(resp.status_code, 302)

    def test_anonymous_denied(self):
        """
        GIVEN an unauthenticated request
        WHEN it hits the funnel dashboard admin page
        THEN it is redirected to the admin login
        """
        resp = Client().get(self.url)
        self.assertEqual(resp.status_code, 302)


class ActiveUserMetricsTest(TestCase):
    """Tests for the "living users" (active/returned/dormant) metrics."""

    def setUp(self):
        self.org = _make_org("ActiveOrg")
        self.now = timezone.now()

        def user(name, days_ago_joined):
            u = User.objects.create_user(username=name, password="x")
            u.date_joined = self.now - _timedelta(days=days_ago_joined)
            u.save(update_fields=["date_joined"])
            return u

        # A: session 3 days ago -> active in all windows, returned
        self.a = user("act_a", 100)
        sa = SurveyHeader.objects.create(name="a_s", organization=self.org, created_by=self.a)
        SurveySession.objects.create(survey=sa, start_datetime=self.now - _timedelta(days=3))

        # B: last_login 20 days ago -> active 30/90, returned
        self.b = user("act_b", 100)
        self.b.last_login = self.now - _timedelta(days=20)
        self.b.save(update_fields=["last_login"])

        # C: survey edited 60 days ago -> active 90 only, returned
        self.c = user("act_c", 200)
        sc = SurveyHeader.objects.create(name="c_s", organization=self.org, created_by=self.c)
        SurveyHeader.objects.filter(pk=sc.pk).update(updated_at=self.now - _timedelta(days=60))

        # D: no activity at all -> dormant
        user("act_d", 200)

    def test_active_windows_returned_and_dormant(self):
        """
        GIVEN creators with activity at 3 / 20 / 60 days ago and one with none
        WHEN active_user_metrics() classifies them
        THEN window counts, returned, and dormant match the constructed scenario
        """
        m = CreatorFunnelService().active_user_metrics(now=self.now)
        self.assertEqual(m["total"], 4)
        self.assertEqual(m["active_7"]["count"], 1)    # A
        self.assertEqual(m["active_30"]["count"], 2)   # A, B
        self.assertEqual(m["active_90"]["count"], 3)   # A, B, C
        self.assertEqual(m["returned"]["count"], 3)    # A, B, C came back
        self.assertEqual(m["dormant"]["count"], 1)     # D
        self.assertEqual(m["active_30"]["pct"], 50)    # 2 of 4

    def test_last_activity_counts_as_returned(self):
        """
        GIVEN a creator whose last_login is unchanged since registration and who
              never saved a parent survey, but who made an authenticated request
              yesterday (recorded in UserActivity)
        WHEN active_user_metrics() classifies them
        THEN they are counted as returned and active via last_activity, while a
             user with no UserActivity row keeps its prior classification
        """
        from survey.models import UserActivity
        e = User.objects.create_user(username="act_e", password="x")
        e.date_joined = self.now - _timedelta(days=100)
        e.save(update_fields=["date_joined"])
        UserActivity.objects.create(user=e, last_activity=self.now - _timedelta(days=1))

        m = CreatorFunnelService().active_user_metrics(now=self.now)
        self.assertEqual(m["total"], 5)
        self.assertEqual(m["active_7"]["count"], 2)    # A (edit) + E (last_activity)
        self.assertEqual(m["returned"]["count"], 4)    # A, B, C, E
        self.assertEqual(m["dormant"]["count"], 1)     # D unchanged (no row)

    def test_weekly_activity_sums_sessions(self):
        """
        GIVEN two non-deleted sessions exist
        WHEN weekly_activity() groups by week
        THEN the response counts sum to the number of live sessions
        """
        rows = CreatorFunnelService().weekly_activity()
        self.assertEqual(sum(r["responses"] for r in rows), 1 + 0)  # only A's live session


class BarChartGeometryTest(TestCase):
    """Tests for the inline-SVG bar geometry helper."""

    def test_geometry_shape_and_scaling(self):
        """
        GIVEN a weekly series with a known maximum
        WHEN bar_chart_geometry builds SVG geometry
        THEN it yields one bar per point, the tallest bar reaches the plot height,
             and bars sit within the drawing area
        """
        series = [{"week": "2026-01-05", "signups": 2},
                  {"week": "2026-01-12", "signups": 4},
                  {"week": "2026-01-19", "signups": 0}]
        g = bar_chart_geometry(series, "signups", width=200, height=100, pad=10)
        self.assertEqual(g["count"], 3)
        self.assertEqual(len(g["bars"]), 3)
        self.assertEqual(g["max"], 4)
        self.assertEqual(g["bars"][2]["h"], 0.0)             # zero value -> zero height
        self.assertAlmostEqual(g["bars"][1]["h"], 80.0, 1)   # max value -> full plot height
        self.assertTrue(all(b["y"] >= g["max_y"] for b in g["bars"]))

    def test_empty_series_does_not_crash(self):
        """
        GIVEN an empty series
        WHEN bar_chart_geometry runs
        THEN it returns zero bars and a zero max without dividing by zero
        """
        g = bar_chart_geometry([], "signups")
        self.assertEqual(g["count"], 0)
        self.assertEqual(g["bars"], [])
        self.assertEqual(g["max"], 0)


class CohortWindowMetricsTest(TestCase):
    """Time-boxed cohort columns: pub_14d and got5_30d."""

    def setUp(self):
        self.org = _make_org("WinOrg")
        self.now = timezone.now()
        self.d = self.now.replace(year=2026, month=3, day=5, hour=9, minute=0, second=0, microsecond=0)

    def _survey(self, user, created_offset_days, status="published"):
        s = SurveyHeader.objects.create(name=f"{user.username}_s", organization=self.org,
                                        created_by=user, status=status)
        SurveyHeader.objects.filter(pk=s.pk).update(created_at=self.d + _timedelta(days=created_offset_days))
        return s

    def test_windowed_columns_respect_time_boxes(self):
        """
        GIVEN one creator who publishes within 14d and collects 5 responses within 30d,
              and another who does both but too late
        WHEN cohort_funnel computes the windowed columns
        THEN only the in-window creator is counted in pub_14d and got5_30d
        """
        x = _u("win_x", self.d)
        sx = self._survey(x, created_offset_days=5)                 # published within 14d
        for k in range(6):
            SurveySession.objects.create(survey=sx, start_datetime=self.d + _timedelta(days=2 + k))  # 5th <= 30d

        y = _u("win_y", self.d)
        sy = self._survey(y, created_offset_days=20)                # published after 14d
        for k in range(6):
            SurveySession.objects.create(survey=sy, start_datetime=self.d + _timedelta(days=40 + k))  # 5th > 30d

        row = next(r for r in CreatorFunnelService().cohort_funnel() if r["cohort"] == "2026-03")
        self.assertEqual(row["regs"], 2)
        self.assertEqual(row["published"], 2)     # both published (all-time)
        self.assertEqual(row["got_5"], 2)         # both collected 5 (all-time)
        self.assertEqual(row["pub_14d"], 1)       # only X published in-window
        self.assertEqual(row["got5_30d"], 1)      # only X hit 5 responses in-window


class ClusterRadarTest(TestCase):
    """Cluster radar: temporal burst + same-domain grouping."""

    def test_burst_and_domain_cluster_detected(self):
        """
        GIVEN 5 institutional-domain signups within a 24h window a few days ago
        WHEN cluster_radar runs
        THEN it reports a signup burst (>=5 in 48h) and a domain cluster for that domain
        """
        base = timezone.now() - _timedelta(days=4)
        for i in range(5):
            _u(f"cl_{i}", base + _timedelta(hours=i * 5), email=f"cl_{i}@tudelft.nl")
        # noise: two freemail users, not clustered
        _u("noise_a", base, email="a@gmail.com")
        _u("noise_b", base, email="b@gmail.com")

        alerts = CreatorFunnelService().cluster_radar()
        kinds = {a["kind"] for a in alerts}
        self.assertIn("burst", kinds)
        self.assertIn("domain", kinds)
        domain_alert = next(a for a in alerts if a["kind"] == "domain")
        self.assertEqual(domain_alert["domain"], "tudelft.nl")
        self.assertGreaterEqual(domain_alert["count"], 5)


class ActionListsTest(TestCase):
    """Dormant-valuable and collecting-but-unpublished action lists."""

    def setUp(self):
        self.org = _make_org("ActOrg")
        self.now = timezone.now()

    def test_dormant_valuable_is_institutional_no_survey(self):
        """
        GIVEN an institutional user with no survey, an institutional user WITH a survey,
              and a freemail user with no survey
        WHEN dormant_valuable runs
        THEN only the institutional-no-survey user is listed
        """
        inst = _u("inst_none", self.now - _timedelta(days=30), email="p@cnr.it")
        inst2 = _u("inst_has", self.now - _timedelta(days=30), email="q@columbia.edu")
        SurveyHeader.objects.create(name="s", organization=self.org, created_by=inst2, status="draft")
        _u("free_none", self.now - _timedelta(days=30), email="r@gmail.com")

        names = {r["username"] for r in CreatorFunnelService().dormant_valuable()}
        self.assertIn("inst_none", names)
        self.assertNotIn("inst_has", names)
        self.assertNotIn("free_none", names)

    def test_collecting_unpublished_lists_draft_with_responses(self):
        """
        GIVEN a draft survey with responses and a published survey with responses
        WHEN collecting_unpublished runs
        THEN only the draft survey appears
        """
        d = _u("draft_u", self.now - _timedelta(days=10))
        sd = SurveyHeader.objects.create(name="draft_s", organization=self.org, created_by=d, status="draft")
        for _ in range(3):
            SurveySession.objects.create(survey=sd, start_datetime=self.now - _timedelta(days=1))
        p = _u("pub_u", self.now - _timedelta(days=10))
        sp = SurveyHeader.objects.create(name="pub_s", organization=self.org, created_by=p, status="published")
        SurveySession.objects.create(survey=sp, start_datetime=self.now - _timedelta(days=1))

        surveys = {r["survey"] for r in CreatorFunnelService().collecting_unpublished()}
        self.assertIn("draft_s", surveys)
        self.assertNotIn("pub_s", surveys)


class DashboardContextSmokeTest(TestCase):
    """dashboard_context assembles all sections without error."""

    def test_context_has_all_sections(self):
        """
        GIVEN an empty database
        WHEN dashboard_context is built
        THEN it returns every section key and does not raise
        """
        ctx = _dashboard_context()
        for key in ("goals", "sources", "clusters", "abuse", "cohorts", "totals",
                    "active", "top_surveys", "ttv", "dormant_valuable", "collecting_unpublished",
                    "signups_chart", "activity_chart"):
            self.assertIn(key, ctx)
        self.assertEqual(len(ctx["goals"]), 4)
        self.assertFalse(ctx["sources"]["available"])   # Phase 1 not shipped


class TopActiveSurveysTest(TestCase):
    """Top active surveys ranked by recent response volume."""

    def setUp(self):
        self.org = _make_org("TopOrg")
        self.now = timezone.now()
        self.owner = _u("top_owner", self.now)

    def _survey_with_sessions(self, name, recent, old=0):
        s = SurveyHeader.objects.create(name=name, organization=self.org,
                                        created_by=self.owner, status="published")
        for _ in range(recent):
            SurveySession.objects.create(survey=s, start_datetime=self.now - _timedelta(days=2))
        for _ in range(old):
            SurveySession.objects.create(survey=s, start_datetime=self.now - _timedelta(days=60))
        return s

    def test_ranked_by_recent_responses_and_excludes_old(self):
        """
        GIVEN surveys with different recent response counts (and one with only old ones)
        WHEN top_active_surveys runs
        THEN it ranks by last-30d responses, descending, excluding out-of-window sessions
        """
        self._survey_with_sessions("busy", recent=8)
        self._survey_with_sessions("medium", recent=3)
        self._survey_with_sessions("stale", recent=0, old=20)   # only old -> not active

        rows = CreatorFunnelService().top_active_surveys()
        names = [r["name"] for r in rows]
        self.assertEqual(names[:2], ["busy", "medium"])
        self.assertNotIn("stale", names)
        self.assertEqual(rows[0]["responses"], 8)

    def test_limit_respected(self):
        """
        GIVEN more surveys than the limit
        WHEN top_active_surveys runs with limit=2
        THEN at most 2 rows are returned
        """
        for i in range(4):
            self._survey_with_sessions(f"s{i}", recent=i + 1)
        self.assertEqual(len(CreatorFunnelService().top_active_surveys(limit=2)), 2)


class AttributionCoverageGoalTest(TestCase):
    """The attribution-coverage goal card computes real coverage (not hardcoded)."""

    def test_coverage_reflects_attributed_recent_signups(self):
        """
        GIVEN four recent signups, two of which have a SignupAttribution row
        WHEN goals() computes the attribution-coverage card
        THEN it reports 50% (not a hardcoded 0%)
        """
        for i in range(2):
            u = User.objects.create_user(f"att_{i}", password="x")
            SignupAttribution.objects.create(user=u, utm_source="edu")
        for i in range(2):
            User.objects.create_user(f"noatt_{i}", password="x")

        cards = {c["label"]: c for c in CreatorFunnelService().goals()}
        cov = cards["Attribution coverage"]
        self.assertEqual(cov["value"], "50%")


class FunnelActivationStagesTest(TestCase):
    """Activated / logged-in stages on the creator funnel."""

    def setUp(self):
        User.objects.all().delete()
        now = timezone.now()
        self.month = now.replace(year=2026, month=3, day=10, hour=12,
                                 minute=0, second=0, microsecond=0)
        self.key = self.month.strftime("%Y-%m")

        # Never confirmed the address (change login-grace-period: accounts are
        # active from registration; "activated" = a confirmed address).
        from survey.models import EmailVerification
        u = _user_at("never_activated", self.month)
        EmailVerification.objects.create(user=u, verified_at=None)
        self.unconfirmed = u

        # Activated but never logged in — the leak this change targets.
        _user_at("activated_only", self.month)

        # Activated and logged in.
        signed_in = _user_at("signed_in", self.month)
        signed_in.last_login = self.month
        signed_in.save(update_fields=["last_login"])

    def _row(self):
        from survey.funnel import CreatorFunnelService
        rows = CreatorFunnelService().cohort_funnel()
        return next(r for r in rows if r["cohort"] == self.key)

    def test_activated_counts_only_confirmed_addresses(self):
        """
        GIVEN one unconfirmed and two confirmed registrations in a cohort
        WHEN the cohort funnel is computed
        THEN the activated stage counts the two confirmed accounts
        """
        row = self._row()
        self.assertEqual(row["regs"], 3)
        self.assertEqual(row["activated"], 2)

    def test_grace_sign_in_counts_as_logged_in_not_activated(self):
        """
        GIVEN the unconfirmed account signed in during its grace period
        WHEN the cohort funnel is computed
        THEN it counts in the logged-in stage and still not in activated
        """
        self.unconfirmed.last_login = self.month
        self.unconfirmed.save(update_fields=["last_login"])

        row = self._row()
        self.assertEqual(row["logged_in"], 2)
        self.assertEqual(row["activated"], 2)

    def test_logged_in_counts_only_users_who_signed_in(self):
        """
        GIVEN an active account that never logged in and one that did
        WHEN the cohort funnel is computed
        THEN only the latter counts in the logged-in stage
        """
        self.assertEqual(self._row()["logged_in"], 1)

    def test_alltime_totals_include_the_new_stages(self):
        """
        GIVEN cohorts carrying activated and logged-in counts
        WHEN all-time totals are computed
        THEN the totals row sums both new stages
        """
        from survey.funnel import CreatorFunnelService
        totals = CreatorFunnelService().alltime_totals()
        self.assertEqual(totals["activated"], 2)
        self.assertEqual(totals["logged_in"], 1)

    def test_dashboard_renders_the_new_columns(self):
        """
        GIVEN a staff user
        WHEN they open the funnel dashboard
        THEN the cohort table shows Activated and Logged in columns
        """
        User.objects.create_superuser("boss2", "boss2@example.com", "x")
        c = Client()
        c.login(username="boss2", password="x")
        resp = c.get(reverse("admin:survey_funnelreport_changelist"))
        self.assertContains(resp, "Activated")
        self.assertContains(resp, "Logged")


class FunnelDashboardAcquisitionLinkTest(TestCase):
    """The Django funnel dashboard hands the top of the funnel to PostHog."""

    def test_context_carries_link_and_no_provider_stages(self):
        """
        GIVEN the dashboard context
        WHEN it is built
        THEN the acquisition block has the PostHog URL, registrations and demo opens,
             and no impressions, channels or freshness figures
        """
        ctx = _dashboard_context()
        acq = ctx['acq']
        self.assertTrue(acq['posthog_url'].startswith('https://'))
        self.assertIn('registrations_in_window', acq)
        self.assertIn('demo', acq)
        for gone in ('stages', 'channels', 'freshness', 'clicks', 'conversions'):
            self.assertNotIn(gone, acq)
