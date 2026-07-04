"""Platform creator acquisition -> activation funnel.

This is the *creator-lifecycle* funnel (register -> create survey -> add question ->
publish -> collect responses), aggregated across the whole platform for a staff-only
admin dashboard. It is distinct from `survey.analytics` / `SurveyEvent`, which track
*respondent* behaviour inside a single published survey.

All stages are derived live from existing tables (no event log, no backfill) -- see
openspec/changes/funnel-monitoring/design.md (D2). Every method returns plain
dicts/lists so no ORM objects leak into templates.
"""

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.db.models.functions import TruncMonth, TruncWeek

from .models import SurveyHeader, Question, SurveySession

User = get_user_model()

# Statuses that count as "the creator published a survey".
PUBLISHED_STATUSES = ("published", "closed", "archived")

# Response thresholds surfaced as activation stages.
RESPONSE_THRESHOLDS = (1, 5, 10)


class CreatorFunnelService:
    """Aggregates the creator funnel over existing tables.

    Cheap at current scale (hundreds of users, thousands of sessions): a handful of
    indexed aggregate queries combined in Python. If it ever slows, cache the result
    for a few minutes -- the page is staff-only and mild staleness is acceptable.
    """

    def _real_users(self):
        """Registrations that count: real people, not staff/superusers or bots.

        Bot signups are already purged operationally (see abuse-prevention epic).
        Hook left here to also exclude AbuseEvent-flagged users if that linkage is
        added later.
        """
        return User.objects.filter(is_staff=False, is_superuser=False)

    # -- stage membership sets (uid -> reached stage) ------------------------------

    def _created_uids(self):
        return set(
            SurveyHeader.objects
            .filter(created_by__isnull=False)
            .values_list("created_by_id", flat=True)
        )

    def _question_uids(self):
        return set(
            Question.objects
            .filter(survey_section__survey_header__created_by__isnull=False)
            .values_list("survey_section__survey_header__created_by_id", flat=True)
        )

    def _published_uids(self):
        return set(
            SurveyHeader.objects
            .filter(created_by__isnull=False, status__in=PUBLISHED_STATUSES)
            .values_list("created_by_id", flat=True)
        )

    def _response_counts(self):
        """uid -> number of non-deleted respondent sessions across their surveys."""
        rows = (
            SurveySession.objects
            .filter(is_deleted=False, survey__created_by__isnull=False)
            .values("survey__created_by_id")
            .annotate(n=Count("id"))
        )
        return {r["survey__created_by_id"]: r["n"] for r in rows}

    # -- public API ---------------------------------------------------------------

    def cohort_funnel(self):
        """Per registration-month cohort: registrations and per-stage counts.

        Returns a list of dicts ordered by cohort, oldest first:
            {cohort, regs, created, added_question, published, got_1, got_5, got_10}
        """
        created = self._created_uids()
        with_q = self._question_uids()
        published = self._published_uids()
        resp = self._response_counts()

        cohorts = {}
        for uid, joined in self._real_users().values_list("id", "date_joined"):
            key = joined.strftime("%Y-%m")
            row = cohorts.setdefault(key, self._blank_row(key))
            row["regs"] += 1
            if uid in created:
                row["created"] += 1
            if uid in with_q:
                row["added_question"] += 1
            if uid in published:
                row["published"] += 1
            n = resp.get(uid, 0)
            for t in RESPONSE_THRESHOLDS:
                if n >= t:
                    row[f"got_{t}"] += 1
        return [cohorts[k] for k in sorted(cohorts)]

    def alltime_totals(self):
        """Single funnel row across all real registrations (for header cards)."""
        total = self._blank_row("all-time")
        rows = self.cohort_funnel()
        for r in rows:
            for k in ("regs", "created", "added_question", "published",
                      "got_1", "got_5", "got_10"):
                total[k] += r[k]
        return total

    def weekly_signups(self):
        """Real registrations grouped by ISO week, oldest first: [{week, signups}]."""
        rows = (
            self._real_users()
            .annotate(week=TruncWeek("date_joined"))
            .values("week")
            .annotate(signups=Count("id"))
            .order_by("week")
        )
        return [
            {"week": r["week"].date().isoformat() if r["week"] else None,
             "signups": r["signups"]}
            for r in rows
        ]

    @staticmethod
    def _blank_row(label):
        return {
            "cohort": label, "regs": 0, "created": 0, "added_question": 0,
            "published": 0, "got_1": 0, "got_5": 0, "got_10": 0,
        }
