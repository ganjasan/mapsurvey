"""Platform creator acquisition -> activation funnel.

This is the *creator-lifecycle* funnel (register -> create survey -> add question ->
publish -> collect responses), aggregated across the whole platform for a staff-only
admin dashboard. It is distinct from `survey.analytics` / `SurveyEvent`, which track
*respondent* behaviour inside a single published survey.

All stages are derived live from existing tables (no event log, no backfill) -- see
openspec/changes/funnel-monitoring/design.md (D2). Every method returns plain
dicts/lists so no ORM objects leak into templates.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Max
from django.db.models.functions import TruncMonth, TruncWeek
from django.utils import timezone

from .models import SurveyHeader, Question, SurveySession

User = get_user_model()

# Statuses that count as "the creator published a survey".
PUBLISHED_STATUSES = ("published", "closed", "archived")

# Response thresholds surfaced as activation stages.
RESPONSE_THRESHOLDS = (1, 5, 10)

# Rolling windows (days) for the "active creators" metrics.
ACTIVE_WINDOWS = (7, 30, 90)


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

    def weekly_activity(self):
        """Ongoing usage over time: non-deleted respondent sessions per ISO week.

        A liveliness signal complementing weekly_signups -- it shows whether
        surveys keep collecting responses week over week: [{week, responses}].
        """
        rows = (
            SurveySession.objects
            .filter(is_deleted=False)
            .annotate(week=TruncWeek("start_datetime"))
            .values("week")
            .annotate(responses=Count("id"))
            .order_by("week")
        )
        return [
            {"week": r["week"].date().isoformat() if r["week"] else None,
             "responses": r["responses"]}
            for r in rows
        ]

    def active_user_metrics(self, now=None):
        """"Living" creators: registered users who keep using the platform.

        A user's `activity_at` is the most recent of: their last login, the last
        edit to any survey they own, and the latest non-deleted response on any of
        their surveys. From that we derive:
          - active_7 / active_30 / active_90: any activity within the rolling window
          - returned: a *creator action* (login or survey edit -- NOT a respondent's
            answer) on a day after they registered; i.e. they genuinely came back
          - dormant: registered but never came back (the complement of returned)
        Returns a dict of {count, pct} blocks plus `total`.
        """
        now = now or timezone.now()

        survey_edit = {
            r["created_by_id"]: r["m"]
            for r in (SurveyHeader.objects
                      .filter(created_by__isnull=False)
                      .values("created_by_id")
                      .annotate(m=Max("updated_at")))
        }
        last_response = {
            r["survey__created_by_id"]: r["m"]
            for r in (SurveySession.objects
                      .filter(is_deleted=False, survey__created_by__isnull=False)
                      .values("survey__created_by_id")
                      .annotate(m=Max("start_datetime")))
        }

        windows = {w: 0 for w in ACTIVE_WINDOWS}
        returned = dormant = total = 0
        cutoffs = {w: now - timedelta(days=w) for w in ACTIVE_WINDOWS}

        for uid, joined, last_login in self._real_users().values_list(
                "id", "date_joined", "last_login"):
            total += 1
            # Creator's own actions (drives "returned"): login + survey edits only.
            creator_acts = [t for t in (last_login, survey_edit.get(uid)) if t is not None]
            creator_action = max(creator_acts) if creator_acts else None
            # Any liveliness (drives active windows): also counts collected responses.
            live = creator_acts + ([last_response[uid]] if uid in last_response else [])
            activity_at = max(live) if live else None

            if creator_action and creator_action.date() > joined.date():
                returned += 1
            else:
                dormant += 1

            if activity_at:
                for w in ACTIVE_WINDOWS:
                    if activity_at >= cutoffs[w]:
                        windows[w] += 1

        def block(count):
            return {"count": count, "pct": round(100 * count / total) if total else 0}

        result = {"total": total,
                  "returned": block(returned),
                  "dormant": block(dormant)}
        for w in ACTIVE_WINDOWS:
            result[f"active_{w}"] = block(windows[w])
        return result

    @staticmethod
    def _blank_row(label):
        return {
            "cohort": label, "regs": 0, "created": 0, "added_question": 0,
            "published": 0, "got_1": 0, "got_5": 0, "got_10": 0,
        }


def bar_chart_geometry(series, value_key, width=760, height=170, pad=26):
    """Turn a weekly series into inline-SVG bar geometry (no chart library).

    `series` is a list of dicts each with a "week" label and a numeric `value_key`.
    Returns a dict the template can render directly with <rect>/<text>, including
    sparse x-axis labels so the axis stays readable for long series.
    """
    n = len(series)
    vmax = max((row[value_key] for row in series), default=0)
    baseline = height - pad
    plot_w = width - 2 * pad
    plot_h = height - 2 * pad
    step = plot_w / n if n else plot_w
    bar_w = max(1.0, step * 0.68)
    label_every = max(1, (n + 7) // 8)  # ~8 labels max

    bars = []
    for i, row in enumerate(series):
        v = row[value_key]
        h = (v / vmax * plot_h) if vmax else 0
        x = pad + i * step + (step - bar_w) / 2
        bars.append({
            "x": round(x, 1),
            "y": round(baseline - h, 1),
            "w": round(bar_w, 1),
            "h": round(h, 1),
            "cx": round(x + bar_w / 2, 1),
            "value": v,
            "label": row.get("week"),
            "show_label": (i % label_every == 0) or (i == n - 1),
        })
    return {
        "width": width, "height": height, "pad": pad,
        "baseline": baseline, "max": vmax, "count": n, "bars": bars,
        "x0": pad, "x1": width - pad, "label_y": height - 8, "max_y": pad - 8,
    }
