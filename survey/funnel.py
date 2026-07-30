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

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Min, Sum
from django.db.models.functions import TruncMonth, TruncWeek
from django.utils import timezone

from .models import (
    AcquisitionDaily, AcquisitionSyncState, DemoOpen, SurveyHeader, Question,
    SurveySession, UserActivity,
    SYNC_FAILING, SYNC_NEVER_RUN, SYNC_NOT_CONFIGURED, SYNC_OK,
)

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
        for uid, joined, is_active, last_login in self._real_users().values_list(
            "id", "date_joined", "is_active", "last_login"
        ):
            key = joined.strftime("%Y-%m")
            row = cohorts.setdefault(key, self._blank_row(key))
            dates.setdefault(key, []).append(joined)
            row["regs"] += 1
            # Two pre-product stages straight off auth_user. Both are
            # point-in-time (an account activated today counts in its signup
            # cohort immediately), like every other stage in this table.
            if is_active:
                row["activated"] += 1
            if last_login is not None:
                row["logged_in"] += 1
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
        keys = ("regs", "activated", "logged_in", "created", "added_question",
                "published", "pub_14d",
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
        edit to any survey they own, their last authenticated request
        (`UserActivity.last_activity`), and the latest non-deleted response on any
        of their surveys. From that we derive:
          - active_7 / active_30 / active_90: any activity within the rolling window
          - returned: a *creator action* (login, survey edit, or an authenticated
            request -- NOT a respondent's answer) on a day after they registered;
            i.e. they genuinely came back
          - dormant: registered but never came back (the complement of returned)

        `last_activity` is forward-only (populated from deploy, no backfill); users
        without a row fall back to `last_login` + `updated_at` and are never
        reclassified downward.
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
        last_activity = dict(
            UserActivity.objects.values_list("user_id", "last_activity")
        )
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
            # Creator's own actions (drives "returned"): login, survey edits, and
            # any authenticated request (last_activity) -- NOT respondent answers.
            creator_acts = [t for t in (last_login, survey_edit.get(uid), last_activity.get(uid)) if t is not None]
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

    def cohort_breakdown(self):
        """The funnel sliced by every cohort dimension.

        Returns one block per dimension, each holding one row per cohort plus an
        explicit "unclassified" row, so the rows always partition the real
        registrations. Costs one extra query (the assignment map) on top of the
        stage-membership sets the funnel already computes -- see the user-cohorts
        change (D5).
        """
        from .cohorts import dimensions_with_cohorts, user_cohort_map

        uids = set(self._real_users().values_list("id", flat=True))
        created = self._created_uids() & uids
        published = self._published_uids() & uids
        responses = {u: n for u, n in self._response_counts().items() if u in uids}
        assignments = user_cohort_map()

        def row(label, slug, color, members):
            n = len(members)
            got = [u for u in members if responses.get(u)]
            return {
                "label": label, "slug": slug, "color": color,
                "users": n,
                "users_pct": round(100 * n / len(uids)) if uids else 0,
                "created": len(members & created),
                "published": len(members & published),
                "collecting": len(got),
                "responses": sum(responses.get(u, 0) for u in got),
                "publish_pct": round(100 * len(members & published) / n) if n else 0,
                "collect_pct": round(100 * len(got) / n) if n else 0,
            }

        blocks = []
        for dimension in dimensions_with_cohorts():
            assigned = set()
            rows = []
            for cohort in dimension.cohorts.all():
                members = {
                    uid for uid in uids
                    if assignments.get(uid, {}).get(dimension.slug) == cohort.slug
                }
                assigned |= members
                rows.append(row(cohort.name, cohort.slug, cohort.color, members))
            rows.append(row("Unclassified", "", "", uids - assigned))
            blocks.append({
                "slug": dimension.slug,
                "name": dimension.name,
                "description": dimension.description,
                "total": len(uids),
                "classified": len(assigned),
                "classified_pct": round(100 * len(assigned) / len(uids)) if uids else 0,
                "rows": rows,
            })
        return blocks

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
            "cohort": label, "regs": 0,
            "activated": 0, "logged_in": 0,
            "created": 0, "added_question": 0,
            "published": 0, "pub_14d": 0,
            "got_1": 0, "got_5": 0, "got_10": 0, "got5_30d": 0,
        }


# -- top of the funnel: acquisition ------------------------------------------

# GSC revises recent days, so the window ends before them (mirrors acquisition.GSC_LAG_DAYS).
ACQUISITION_LAG_DAYS = 2

# Default window for the acquisition block, in days.
ACQUISITION_WINDOW_DAYS = 30


def _stage(label, value, source, note='', unavailable=''):
    """One acquisition stage.

    `value is None` together with a filled `unavailable` is the "we do not know" state.
    It must never be rendered as 0: a broken sync and a genuinely quiet week look
    identical as a zero, and the two lead to opposite decisions (design D6).
    """
    return {
        'label': label,
        'value': value,
        'source': source,
        'note': note,
        'unavailable': unavailable,
        'known': value is not None,
    }


def _conversion(label, upper, lower):
    """Rate between two stages, unknown when either side is unknown.

    A rate against a missing numerator or denominator is not a smaller number, it is
    no number at all -- so unavailability propagates instead of collapsing to 0%.
    """
    if not upper['known'] or not lower['known'] or not upper['value']:
        return {'label': label, 'pct': None, 'known': False}
    return {'label': label, 'pct': round(100 * lower['value'] / upper['value'], 1),
            'known': True}


class AcquisitionService:
    """The pre-registration funnel, read entirely from locally stored metrics.

    Impressions and landing visits come from `AcquisitionDaily` (synced out of band),
    registrations and demo opens from our own tables. Nothing here calls an external
    API -- see design D1.
    """

    def __init__(self, days=ACQUISITION_WINDOW_DAYS, today=None):
        self.days = max(1, days)
        today = today or timezone.localdate()
        self.end = today - timedelta(days=ACQUISITION_LAG_DAYS)
        self.start = self.end - timedelta(days=self.days - 1)
        self._states = None

    # -- source state ---------------------------------------------------------

    def states(self):
        """source -> AcquisitionSyncState, with a placeholder for sources never run."""
        if self._states is None:
            found = {s.source: s for s in AcquisitionSyncState.objects.all()}
            for source in ('gsc', 'plausible'):
                found.setdefault(source, AcquisitionSyncState(source=source))
            self._states = found
        return self._states

    def _unavailable_reason(self, source, has_rows):
        """Why a source's numbers cannot be shown, or '' when they can."""
        state = self.states()[source]
        if state.state == SYNC_NOT_CONFIGURED:
            return state.last_error or 'not configured'
        if state.state == SYNC_NEVER_RUN and not has_rows:
            return 'configured but never synced'
        if not has_rows and not state.last_success_at:
            return 'no data synced yet'
        return ''

    def freshness(self):
        """Per-source sync state for display: age of the last success and staleness."""
        now = timezone.now()
        stale_after = timedelta(hours=getattr(settings, 'ACQUISITION_STALE_HOURS', 48))
        out = []
        for source in ('gsc', 'plausible'):
            state = self.states()[source]
            age = (now - state.last_success_at) if state.last_success_at else None
            out.append({
                'source': source,
                'state': state.state,
                'configured': state.is_configured,
                'last_success': state.last_success_at,
                'age_hours': round(age.total_seconds() / 3600, 1) if age else None,
                'stale': bool(state.is_configured and (age is None or age > stale_after)),
                'error': state.last_error,
            })
        return out

    # -- stages ---------------------------------------------------------------

    def _sum(self, source, segment, field):
        """Summed metric over the window, plus whether any row existed at all."""
        qs = AcquisitionDaily.objects.filter(
            source=source, segment=segment, date__gte=self.start, date__lte=self.end,
        )
        total = qs.aggregate(n=Sum(field))['n']
        # "Any row for this source" (not just this window) separates a never-synced
        # source from one that synced fine over a period with nothing to report.
        any_row = AcquisitionDaily.objects.filter(source=source).exists()
        return total, any_row

    def impressions(self):
        total, any_row = self._sum('gsc', AcquisitionDaily.SEGMENT_MARKETING, 'impressions')
        reason = self._unavailable_reason('gsc', any_row)
        if reason:
            return _stage('Google impressions', None, 'Search Console', unavailable=reason)
        return _stage('Google impressions', total or 0, 'Search Console',
                      note='marketing pages, survey pages excluded')

    def google_clicks(self):
        total, any_row = self._sum('gsc', AcquisitionDaily.SEGMENT_MARKETING, 'clicks')
        reason = self._unavailable_reason('gsc', any_row)
        if reason:
            return _stage('Google clicks', None, 'Search Console', unavailable=reason)
        return _stage('Google clicks', total or 0, 'Search Console',
                      note='organic clicks from search')

    def landing_visits(self):
        total, any_row = self._sum('plausible', AcquisitionDaily.SEGMENT_LANDING, 'visitors')
        reason = self._unavailable_reason('plausible', any_row)
        if reason:
            return _stage('Landing visits', None, 'Plausible', unavailable=reason)
        return _stage('Landing visits', total or 0, 'Plausible',
                      note='unique visitors on the landing page, all channels')

    def registrations(self):
        """Real signups in the window -- same population the cohort funnel counts."""
        n = (get_user_model().objects
             .filter(is_staff=False, is_superuser=False,
                     date_joined__date__gte=self.start, date_joined__date__lte=self.end)
             .count())
        return _stage('Registrations', n, 'our database',
                      note='staff and superusers excluded')

    # -- demo -----------------------------------------------------------------

    def demo(self):
        """Demo opens: window total from sessions, plus the anonymous/signed-in split.

        The total is retroactive across all history because it derives from sessions.
        The split derives from `DemoOpen`, which only exists from deploy onward, so it
        carries the date recording began rather than pretending earlier sessions were
        anonymous (design D4).
        """
        from .acquisition import demo_survey

        survey = demo_survey()
        if survey is None:
            return {
                'stage': _stage('Demo opens', None, 'our database',
                                unavailable='DEMO_SURVEY_URL unset or the survey no longer exists'),
                'survey_name': '', 'split_known': False,
            }

        total = (SurveySession.objects
                 .filter(survey=survey, is_deleted=False,
                         start_datetime__date__gte=self.start,
                         start_datetime__date__lte=self.end)
                 .count())

        opens = DemoOpen.objects.filter(
            created_at__date__gte=self.start, created_at__date__lte=self.end,
        )
        anonymous = opens.filter(user__isnull=True).count()
        signed_in = opens.filter(user__isnull=False).count()
        since = DemoOpen.objects.aggregate(m=Min('created_at'))['m']

        return {
            'stage': _stage('Demo opens', total, 'our database',
                            note='sessions started on the demo survey'),
            'survey_name': survey.name or str(survey.uuid),
            'split_known': since is not None,
            'anonymous': anonymous,
            'signed_in': signed_in,
            'split_since': since.date() if since else None,
        }

    # -- channels -------------------------------------------------------------

    def channels(self, limit=8):
        """Landing traffic by referrer channel over the window, largest first."""
        rows = (AcquisitionDaily.objects
                .filter(source='plausible',
                        segment__startswith=AcquisitionDaily.CHANNEL_PREFIX,
                        date__gte=self.start, date__lte=self.end)
                .values('segment')
                .annotate(visitors=Sum('visitors'))
                .order_by('-visitors')[:limit])
        prefix = len(AcquisitionDaily.CHANNEL_PREFIX)
        out = [{'channel': r['segment'][prefix:] or 'Direct / None',
                'visitors': r['visitors'] or 0} for r in rows]
        if out:
            return {'available': True, 'rows': out, 'unavailable': ''}
        reason = self._unavailable_reason(
            'plausible', AcquisitionDaily.objects.filter(source='plausible').exists()
        )
        return {'available': False, 'rows': [],
                'unavailable': reason or 'no channel data in this window'}

    # -- assembled block ------------------------------------------------------

    def block(self):
        impressions = self.impressions()
        visits = self.landing_visits()
        regs = self.registrations()
        demo = self.demo()

        return {
            'start': self.start,
            'end': self.end,
            'days': self.days,
            'lag_days': ACQUISITION_LAG_DAYS,
            'stages': [impressions, visits, regs, demo['stage']],
            'clicks': self.google_clicks(),
            'conversions': [
                _conversion('impressions → visits', impressions, visits),
                _conversion('visits → registrations', visits, regs),
                _conversion('registrations → demo', regs, demo['stage']),
            ],
            'demo': demo,
            'channels': self.channels(),
            'freshness': self.freshness(),
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
    # The acquisition window follows the period selector so the top of the funnel and
    # the charts below describe the same stretch of time. "All" has no useful meaning
    # for it (GSC history only starts at property verification), so it falls back to
    # the default window.
    acq_days = weeks * 7 if weeks else ACQUISITION_WINDOW_DAYS
    return {
        "weeks": weeks,
        "acq": AcquisitionService(days=acq_days).block(),
        "goals": s.goals(),
        "sources": s.signups_by_source(),
        "cohort_blocks": s.cohort_breakdown(),
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
