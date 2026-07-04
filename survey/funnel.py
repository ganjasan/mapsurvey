"""Platform creator acquisition -> activation funnel.

This is the *creator-lifecycle* funnel (register -> create survey -> add question ->
publish -> collect responses), aggregated across the whole platform for a staff-only
admin dashboard. It is distinct from `survey.analytics` / `SurveyEvent`, which track
*respondent* behaviour inside a single published survey.

All stages are derived live from existing tables (no event log, no backfill) -- see
openspec/changes/funnel-monitoring/design.md (D2). Every method returns plain
dicts/lists so no ORM objects leak into templates.
"""

import statistics
from collections import Counter, deque
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Min
from django.db.models.functions import TruncMonth, TruncWeek
from django.utils import timezone

from .models import SurveyHeader, Question, SurveySession

User = get_user_model()

# Statuses that count as "the creator published a survey".
PUBLISHED_STATUSES = ("published", "closed", "archived")

# Statuses where a survey can still collect responses via test links but is not
# formally published -- the "collecting but unpublished" leak (H5).
UNPUBLISHED_STATUSES = ("draft", "testing")

# Response thresholds surfaced as activation stages.
RESPONSE_THRESHOLDS = (1, 5, 10)

# Rolling windows (days) for the "active creators" metrics.
ACTIVE_WINDOWS = (7, 30, 90)

# Time-boxed activation windows (days) for fair cohort-over-cohort comparison.
PUBLISH_WINDOW_DAYS = 14
RESPONSE_WINDOW_DAYS = 30

# GTM plan targets (docs/gtm/gtm-plan-2026-h2.md). Used by the goals block.
GOAL_TARGETS = {
    "activated_30d": 25,   # activated creators / month, Oct target
    "regs_30d": 100,       # registrations / month, Oct target
    "publish_rate": 80,    # % of users-with-responses who published (H5)
    "attribution": 90,     # % of signups with a known source (needs Phase 1)
}

# Free-mail providers -- an institutional (non-freemail) domain is a soft signal
# of a higher-value / potential-cluster account (used by cluster radar + dormant list).
FREEMAIL_DOMAINS = frozenset({
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "ymail.com",
    "outlook.com", "hotmail.com", "hotmail.co.uk", "live.com", "msn.com",
    "icloud.com", "me.com", "aol.com", "gmx.com", "gmx.de", "web.de",
    "proton.me", "protonmail.com", "pm.me", "yandex.ru", "mail.ru",
    "qq.com", "163.com", "126.com", "foxmail.com", "naver.com", "example.com",
})


def _tone(pct):
    """Colour semantics for the goals block: green >=80, amber >=30, else red."""
    return "act" if pct >= 80 else ("warn" if pct >= 30 else "bad")


def _domain(email):
    return email.split("@")[-1].lower() if email and "@" in email else ""


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

    def _published_first_created(self):
        """uid -> earliest created_at among the creator's published surveys.

        Proxy for "when did they publish" -- we lack a publish-transition
        timestamp, so the publish-window metric uses survey creation of a
        now-published survey. Documented as approximate in design.md.
        """
        return {
            r["created_by_id"]: r["m"]
            for r in (SurveyHeader.objects
                      .filter(created_by__isnull=False, status__in=PUBLISHED_STATUSES)
                      .values("created_by_id")
                      .annotate(m=Min("created_at")))
        }

    def _session_times(self):
        """uid -> sorted list of non-deleted session start times (their surveys)."""
        times = {}
        for uid, st in (SurveySession.objects
                        .filter(is_deleted=False, survey__created_by__isnull=False)
                        .values_list("survey__created_by_id", "start_datetime")):
            times.setdefault(uid, []).append(st)
        for v in times.values():
            v.sort()
        return times

    def cohort_funnel(self):
        """Per registration-month cohort: registrations and per-stage counts.

        Each row also carries time-boxed columns (`pub_14d`, `got5_30d`) so young
        and old cohorts are comparable, and a `spark` (inline-SVG geometry of weekly
        signups within the cohort month).
        """
        created = self._created_uids()
        with_q = self._question_uids()
        published = self._published_uids()
        resp = self._response_counts()
        pub_created = self._published_first_created()
        session_times = self._session_times()
        pub_window = timedelta(days=PUBLISH_WINDOW_DAYS)
        resp_window = timedelta(days=RESPONSE_WINDOW_DAYS)

        cohorts = {}
        dates = {}
        for uid, joined in self._real_users().values_list("id", "date_joined"):
            key = joined.strftime("%Y-%m")
            row = cohorts.setdefault(key, self._blank_row(key))
            dates.setdefault(key, []).append(joined)
            row["regs"] += 1
            if uid in created:
                row["created"] += 1
            if uid in with_q:
                row["added_question"] += 1
            if uid in published:
                row["published"] += 1
            pj = pub_created.get(uid)
            if pj and pj <= joined + pub_window:
                row["pub_14d"] += 1
            n = resp.get(uid, 0)
            for t in RESPONSE_THRESHOLDS:
                if n >= t:
                    row[f"got_{t}"] += 1
            times = session_times.get(uid)
            if times and len(times) >= 5 and times[4] <= joined + resp_window:
                row["got5_30d"] += 1

        ordered = [cohorts[k] for k in sorted(cohorts)]
        for row in ordered:                       # attach per-cohort sparkline
            wc = Counter(d.isocalendar()[1] for d in dates[row["cohort"]])
            series = [{"week": str(w), "v": wc[w]} for w in sorted(wc)]
            row["spark"] = bar_chart_geometry(series, "v", width=110, height=22, pad=2)
        return ordered

    def alltime_totals(self):
        """Single funnel row across all real registrations (for header cards)."""
        total = self._blank_row("all-time")
        keys = ("regs", "created", "added_question", "published", "pub_14d",
                "got_1", "got_5", "got_10", "got5_30d")
        for r in self.cohort_funnel():
            for k in keys:
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

    def top_active_surveys(self, limit=10, days=30, now=None):
        """The surveys collecting the most responses recently (the live ones).

        Ranked by non-deleted sessions in the last `days`. Returns survey name,
        owner, status, and the recent response count -- with an admin deep link
        built in the template.
        """
        now = now or timezone.now()
        rows = (SurveySession.objects
                .filter(is_deleted=False, start_datetime__gte=now - timedelta(days=days))
                .values("survey_id", "survey__name", "survey__status",
                        "survey__created_by__username")
                .annotate(n=Count("id"))
                .order_by("-n")[:limit])
        return [{"survey_id": r["survey_id"],
                 "name": r["survey__name"] or "—",
                 "status": r["survey__status"],
                 "owner": r["survey__created_by__username"] or "—",
                 "responses": r["n"]} for r in rows]

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

    # -- section blocks for the dashboard --------------------------------------

    def goals(self, now=None):
        """North-Star goal cards: current vs GTM target, with tone + bar %."""
        now = now or timezone.now()
        users = self._real_users()
        cut30 = now - timedelta(days=30)
        resp = self._response_counts()
        published = self._published_uids()

        recent_ids = set(users.filter(date_joined__gte=cut30).values_list("id", flat=True))
        regs_30 = len(recent_ids)
        activated_30 = sum(1 for uid in recent_ids if resp.get(uid, 0) >= 5)
        has_resp = {uid for uid, n in resp.items() if n >= 1}
        pub_rate = round(100 * len(has_resp & published) / len(has_resp)) if has_resp else 0

        # Real attribution coverage: share of recent signups with a known source.
        # Rises from deploy onward (no backfill), so pre-deploy signups don't count.
        from .models import SignupAttribution
        attributed_30 = (SignupAttribution.objects.filter(user_id__in=recent_ids)
                         .values("user_id").distinct().count())
        coverage = round(100 * attributed_30 / regs_30) if regs_30 else 0

        def card(label, value_display, pct_to_target, target_display, note):
            pct = min(100, max(0, pct_to_target))
            return {"label": label, "value": value_display, "target": target_display,
                    "pct": pct, "tone": _tone(pct_to_target), "note": note}

        t = GOAL_TARGETS
        return [
            card("Activated creators · 30d", str(activated_30),
                 round(100 * activated_30 / t["activated_30d"]), str(t["activated_30d"]),
                 "published + ≥5 responses"),
            card("Registrations · 30d", str(regs_30),
                 round(100 * regs_30 / t["regs_30d"]), str(t["regs_30d"]),
                 "real signups"),
            card("Publish rate", f"{pub_rate}%",
                 round(100 * pub_rate / t["publish_rate"]), f"{t['publish_rate']}%",
                 "of users with responses (H5)"),
            card("Attribution coverage", f"{coverage}%",
                 round(100 * coverage / t["attribution"]), f"{t['attribution']}%",
                 "new signups with a known source"),
        ]

    def cluster_radar(self, now=None):
        """Detect likely classroom/team clusters early: temporal bursts and
        same-domain groups. Returns a list of alert dicts (empty = all quiet)."""
        now = now or timezone.now()
        alerts = []

        # Temporal burst: the largest group of >=5 signups within any 48h window
        # over the last 21 days.
        recent = list(self._real_users()
                      .filter(date_joined__gte=now - timedelta(days=21))
                      .order_by("date_joined")
                      .values_list("id", "date_joined", "email"))
        window, best = deque(), None
        for item in recent:
            window.append(item)
            while window and (item[1] - window[0][1]) > timedelta(hours=48):
                window.popleft()
            if len(window) >= 5 and (best is None or len(window) > len(best)):
                best = list(window)
        if best:
            doms = Counter(_domain(e) for _, _, e in best if _domain(e))
            alerts.append({
                "kind": "burst", "count": len(best),
                "detail": f"{len(best)} signups in 48h",
                "domain": doms.most_common(1)[0][0] if doms else "",
                "since": best[0][1].date().isoformat(),
                "user_ids": [u for u, _, _ in best][:12],
            })

        # Domain cluster: >=3 real signups on the same non-freemail domain in 30d.
        dom, dom_users = Counter(), {}
        for uid, _, email in (self._real_users()
                              .filter(date_joined__gte=now - timedelta(days=30))
                              .values_list("id", "date_joined", "email")):
            d = _domain(email)
            if d and d not in FREEMAIL_DOMAINS:
                dom[d] += 1
                dom_users.setdefault(d, []).append(uid)
        for d, c in dom.most_common():
            if c >= 3:
                alerts.append({"kind": "domain", "count": c, "domain": d,
                               "detail": f"{c} signups · {d}", "since": "30d",
                               "user_ids": dom_users[d][:12]})
        return alerts

    def abuse_summary(self, now=None):
        """Bots blocked in the last 7 days + top offending IPs (from AbuseEvent)."""
        from .models import AbuseEvent
        now = now or timezone.now()
        qs = AbuseEvent.objects.filter(created_at__gte=now - timedelta(days=7))
        top = (qs.exclude(ip__isnull=True)
               .values("ip").annotate(n=Count("id")).order_by("-n")[:5])
        return {"blocked_7d": qs.count(),
                "top_ips": [{"ip": r["ip"], "n": r["n"]} for r in top]}

    def time_to_value(self):
        """Median days from registration to first survey / publish / first response."""
        users = dict(self._real_users().values_list("id", "date_joined"))
        first_survey = self._min_map(SurveyHeader.objects.filter(created_by__isnull=False),
                                     "created_by_id", "created_at")
        first_pub = self._min_map(
            SurveyHeader.objects.filter(created_by__isnull=False, status__in=PUBLISHED_STATUSES),
            "created_by_id", "created_at")
        first_resp = self._min_map(
            SurveySession.objects.filter(is_deleted=False, survey__created_by__isnull=False),
            "survey__created_by_id", "start_datetime")

        def median_days(m):
            vals = [max(0.0, (dt - users[uid]).total_seconds() / 86400)
                    for uid, dt in m.items() if uid in users and dt]
            return round(statistics.median(vals), 1) if vals else None

        return {"to_survey": median_days(first_survey),
                "to_publish": median_days(first_pub),
                "to_response": median_days(first_resp)}

    def dormant_valuable(self, limit=15):
        """Institutional-domain registrants who never created a survey -> outreach."""
        created = self._created_uids()
        rows = []
        for uid, dj, email, uname in (self._real_users().exclude(id__in=created)
                                      .values_list("id", "date_joined", "email", "username")):
            d = _domain(email)
            if d and d not in FREEMAIL_DOMAINS:
                rows.append({"uid": uid, "username": uname, "domain": d,
                             "joined": dj.date().isoformat()})
        rows.sort(key=lambda r: r["joined"], reverse=True)
        return rows[:limit]

    def collecting_unpublished(self, limit=15):
        """Surveys collecting responses while still draft/testing -> nudge to publish (H5)."""
        rows = (SurveySession.objects
                .filter(is_deleted=False, survey__status__in=UNPUBLISHED_STATUSES,
                        survey__created_by__isnull=False)
                .values("survey_id", "survey__name",
                        "survey__created_by_id", "survey__created_by__username")
                .annotate(n=Count("id")).order_by("-n")[:limit])
        return [{"survey_id": r["survey_id"], "survey": r["survey__name"],
                 "uid": r["survey__created_by_id"],
                 "username": r["survey__created_by__username"],
                 "responses": r["n"]} for r in rows]

    def signups_by_source(self, now=None, days=7):
        """Recent registrations grouped by acquisition source (Phase 1).

        Source = utm_source when present, else the classified referrer bucket,
        else 'unknown' for users with no attribution row (e.g. pre-Phase-1
        signups). `available` is False until any attribution has been captured,
        so the panel can show a placeholder note before the feature is live.
        """
        from .models import SignupAttribution
        now = now or timezone.now()
        available = SignupAttribution.objects.exists()

        recent = self._real_users().filter(date_joined__gte=now - timedelta(days=days))
        attr = {
            a["user_id"]: (a["utm_source"] or a["source_bucket"] or "direct")
            for a in SignupAttribution.objects.filter(user__in=recent)
            .values("user_id", "utm_source", "source_bucket")
        }
        counts = Counter(attr.get(uid, "unknown")
                         for uid in recent.values_list("id", flat=True))
        rows = [{"source": s, "regs": c} for s, c in counts.most_common()]
        return {"available": available, "rows": rows}

    @staticmethod
    def _min_map(qs, key_field, value_field):
        return {r[key_field]: r["m"]
                for r in qs.values(key_field).annotate(m=Min(value_field))}

    @staticmethod
    def _blank_row(label):
        return {
            "cohort": label, "regs": 0, "created": 0, "added_question": 0,
            "published": 0, "pub_14d": 0,
            "got_1": 0, "got_5": 0, "got_10": 0, "got5_30d": 0,
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


def dashboard_context(weeks=None):
    """Full template context for the funnel dashboard. Recomputed per request --
    cheap at current scale; cache here first if it ever slows.

    `weeks` (int) trims the two weekly charts to the most recent N weeks; None = all.
    """
    s = CreatorFunnelService()
    weekly = s.weekly_signups()
    activity = s.weekly_activity()
    if weeks:
        weekly = weekly[-weeks:]
        activity = activity[-weeks:]
    return {
        "weeks": weeks,
        "goals": s.goals(),
        "sources": s.signups_by_source(),
        "clusters": s.cluster_radar(),
        "abuse": s.abuse_summary(),
        "cohorts": s.cohort_funnel(),
        "totals": s.alltime_totals(),
        "active": s.active_user_metrics(),
        "top_surveys": s.top_active_surveys(),
        "ttv": s.time_to_value(),
        "dormant_valuable": s.dormant_valuable(),
        "collecting_unpublished": s.collecting_unpublished(),
        "signups_chart": bar_chart_geometry(weekly, "signups"),
        "activity_chart": bar_chart_geometry(activity, "responses"),
    }
