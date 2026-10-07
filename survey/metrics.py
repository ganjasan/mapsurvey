"""Time series for the staff funnel dashboard (change funnel-history-metrics).

ONE registry, `SERIES`, of two kinds:

- ``event`` series are computed live from timestamps on existing rows, bucketed
  by ISO week, and are therefore retro-active to the first signup;
- ``state`` series describe the present (active creators, publish rate, …) and
  cannot be recomputed for a past day because the rows behind them keep only
  their latest moment. Their *current* value is computed live; their *history*
  is the `MetricSnapshot` rows that `manage.py snapshot_metrics` writes once a
  day.

The dashboard (`funnel.dashboard_context`), the snapshot command and the tests
iterate the same tuple, so a series added here is snapshotted, charted and
tested without a second list. State values come from the very computations the
dashboard already shows for those numbers (`CreatorFunnelService`), never from
a parallel definition. Design: openspec/changes/funnel-history-metrics/design.md.
"""

from collections import namedtuple
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Min
from django.db.models.functions import TruncWeek
from django.utils import timezone

from .models import MetricSnapshot, SurveyHeader, SurveySession

User = get_user_model()

EVENT = "event"
STATE = "state"

Series = namedtuple("Series", "key label kind unit note")

SERIES = (
    # The creator funnel, five series side by side.
    Series("regs", "Registrations", EVENT, "count", ""),
    Series("activations", "Activations", EVENT, "count",
           "by signup week — activation has no timestamp of its own"),
    Series("surveys_created", "Surveys created", EVENT, "count", ""),
    Series("surveys_published", "Surveys published", EVENT, "count", ""),  # note is dynamic
    Series("first_responses", "First responses", EVENT, "count",
           "surveys whose first external response arrived that week"),
    # Usage.
    Series("responses", "Responses", EVENT, "count", "non-deleted sessions"),
    Series("live_surveys", "Live surveys", EVENT, "count", "surveys with ≥1 response in the week"),
    # State — snapshotted daily.
    Series("activated_30d", "Activated creators · 30d", STATE, "count", "North Star"),
    Series("active_30d", "Active creators · 30d", STATE, "count", ""),
    Series("returned_pct", "Returned", STATE, "pct", "creator action after signup"),
    Series("publish_rate", "Publish rate", STATE, "pct", "of users with responses"),
    Series("collecting_unpublished", "Collecting unpublished", STATE, "count",
           "worklist size: drafts with responses"),
)

BY_KEY = {s.key: s for s in SERIES}
EVENT_SERIES = tuple(s for s in SERIES if s.kind == EVENT)
STATE_SERIES = tuple(s for s in SERIES if s.kind == STATE)

# Delta of a state series is against the snapshot this many days earlier.
STATE_DELTA_DAYS = 7


def week_start(d):
    """Monday of the ISO week containing `d` (a date or datetime)."""
    if hasattr(d, "date"):
        d = d.date()
    return d - timedelta(days=d.weekday())


# -- event series ----------------------------------------------------------------

def _real_users():
    return User.objects.filter(is_staff=False, is_superuser=False)


def _weekly_counts(qs, field, distinct=None):
    """{monday: count} over `qs` bucketed by `date_trunc('week', field)`."""
    rows = (qs.annotate(week=TruncWeek(field)).values("week")
            .annotate(n=Count(distinct, distinct=True) if distinct else Count("id"))
            .order_by())
    return {week_start(r["week"]): r["n"] for r in rows if r["week"] is not None}


def _event_counts(key):
    """{monday: count} for one event series, over all time."""
    if key == "regs":
        return _weekly_counts(_real_users(), "date_joined")
    if key == "activations":
        return _weekly_counts(_real_users().filter(is_active=True), "date_joined")
    if key == "surveys_created":
        return _weekly_counts(
            SurveyHeader.objects.filter(created_by__isnull=False, is_canonical=True,
                                        created_at__isnull=False),
            "created_at")
    if key == "surveys_published":
        return _weekly_counts(
            SurveyHeader.objects.filter(created_by__isnull=False, is_canonical=True,
                                        published_at__isnull=False),
            "published_at")
    if key == "first_responses":
        firsts = (SurveySession.objects
                  .filter(is_deleted=False, opened_by_kind=SurveySession.OPENED_BY_EXTERNAL,
                          survey__created_by__isnull=False)
                  .values("survey_id").annotate(m=Min("start_datetime")).order_by())
        out = {}
        for r in firsts:
            w = week_start(r["m"])
            out[w] = out.get(w, 0) + 1
        return out
    if key == "responses":
        return _weekly_counts(SurveySession.objects.filter(is_deleted=False), "start_datetime")
    if key == "live_surveys":
        return _weekly_counts(SurveySession.objects.filter(is_deleted=False),
                              "start_datetime", distinct="survey_id")
    raise KeyError(key)


def weekly_series(key, start, end):
    """Zero-filled weekly points for an event series: [{x: 'YYYY-MM-DD', y: n}],
    one per ISO week from the week of `start` to the week of `end` inclusive."""
    counts = _event_counts(key)
    first, last = week_start(start), week_start(end)
    points, w = [], first
    while w <= last:
        points.append({"x": w.isoformat(), "y": counts.get(w, 0)})
        w += timedelta(days=7)
    return points


def earliest_event_week(key):
    """Monday of the first bucket with data, or None (for the 'all' period)."""
    counts = _event_counts(key)
    return min(counts) if counts else None


def published_recorded_since():
    """Date of the earliest recorded publish, or None. Publishes before it exist
    only as the creation proxy and are outside the `surveys_published` series."""
    m = SurveyHeader.objects.filter(published_at__isnull=False).aggregate(m=Min("published_at"))["m"]
    return m.date() if m else None


# -- state series ----------------------------------------------------------------

def current_state(key, service=None, now=None):
    """The live value of a state series, from the dashboard's own computations."""
    from .funnel import CreatorFunnelService
    s = service or CreatorFunnelService()
    if key == "activated_30d":
        return float(s.goal_values(now)["activated_30"])
    if key == "publish_rate":
        return float(s.goal_values(now)["pub_rate"])
    if key == "active_30d":
        return float(s.active_user_metrics(now)["active_30"]["count"])
    if key == "returned_pct":
        return float(s.active_user_metrics(now)["returned"]["pct"])
    if key == "collecting_unpublished":
        return float(len(s.collecting_unpublished(limit=None)))
    raise KeyError(key)


def snapshot_series(key, start, end):
    """[(date, value)] of a state series within [start, end], oldest first."""
    return list(MetricSnapshot.objects.filter(key=key, date__gte=start, date__lte=end)
                .order_by("date").values_list("date", "value"))


def history_since(key):
    """Date of the earliest snapshot for `key`, or None."""
    return MetricSnapshot.objects.filter(key=key).aggregate(m=Min("date"))["m"]


def write_snapshots(day=None, service=None):
    """Write today's (or `day`'s) row for every state series; rerun overwrites.
    Returns {key: value}."""
    from .funnel import CreatorFunnelService
    day = day or timezone.localdate()
    s = service or CreatorFunnelService()
    written = {}
    for series in STATE_SERIES:
        value = current_state(series.key, service=s)
        MetricSnapshot.objects.update_or_create(date=day, key=series.key,
                                                defaults={"value": value})
        written[series.key] = value
    return written


# -- tiles -----------------------------------------------------------------------

def _fmt(value, unit):
    if value is None:
        return "—"
    v = int(round(value))
    return f"{v}%" if unit == "pct" else str(v)


def _fmt_delta(delta, unit):
    if delta is None:
        return None
    v = int(round(delta))
    sign = "+" if v > 0 else ("−" if v < 0 else "±")
    body = f"{abs(v)}%" if unit == "pct" else str(abs(v))
    return f"{sign}{body}" if v else "±0"


def _tile(spec, **kw):
    tile = {"key": spec.key, "label": spec.label, "kind": spec.kind,
            "unit": spec.unit, "note": spec.note,
            "current": None, "current_display": "—",
            "delta": None, "delta_display": None, "tone": "",
            "series": [], "partial_last": False, "history_since": None,
            "has_chart": False}
    tile.update(kw)
    tile["current_display"] = _fmt(tile["current"], spec.unit)
    tile["delta_display"] = _fmt_delta(tile["delta"], spec.unit)
    d = tile["delta"]
    # Up is good for everything in the core; the worklist size carries no tone.
    if d is not None and spec.key != "collecting_unpublished":
        tile["tone"] = "up" if d > 0 else ("down" if d < 0 else "flat")
    tile["has_chart"] = len(tile["series"]) >= 2
    return tile


def tiles(weeks=None, now=None, service=None):
    """One tile dict per registry series for the dashboard. `weeks` trims the
    period (None = all). Event tiles: zero-filled weekly buckets up to and
    including the running week, which is drawn but not compared (a Tuesday is
    not a week). State tiles: daily snapshots over the same span; with fewer
    than two they show the live value and say when history starts."""
    from .funnel import CreatorFunnelService
    now = now or timezone.now()
    today = timezone.localdate(now)
    this_week = week_start(today)
    svc = service or CreatorFunnelService()
    out = []

    pub_since = published_recorded_since()
    for s in EVENT_SERIES:
        if weeks:
            start = this_week - timedelta(days=7 * weeks)
        else:
            start = earliest_event_week(s.key) or this_week
        points = weekly_series(s.key, start, today)
        # points[-1] is the running week; the last complete one is current.
        current = points[-2]["y"] if len(points) >= 2 else 0
        previous = points[-3]["y"] if len(points) >= 3 else None
        note = s.note
        if s.key == "surveys_published":
            note = (f"recorded publishes since {pub_since.isoformat()}; earlier ones exist only as the creation proxy"
                    if pub_since else "no recorded publish yet — history starts with the first one")
        out.append(_tile(s, note=note, current=float(current),
                         delta=(current - previous) if previous is not None else None,
                         series=points, partial_last=True))

    for s in STATE_SERIES:
        since = history_since(s.key)
        start = (today - timedelta(days=7 * weeks)) if weeks else (since or today)
        snaps = snapshot_series(s.key, start, today)
        if len(snaps) >= 2:
            latest_day, latest = snaps[-1]
            by_day = dict(snaps)
            earlier = by_day.get(latest_day - timedelta(days=STATE_DELTA_DAYS))
            out.append(_tile(s, current=latest,
                             delta=(latest - earlier) if earlier is not None else None,
                             series=[{"x": d.isoformat(), "y": v} for d, v in snaps],
                             partial_last=False, history_since=since.isoformat()))
        elif snaps:
            out.append(_tile(s, current=snaps[-1][1], history_since=since.isoformat()))
        else:
            out.append(_tile(s, current=current_state(s.key, service=svc, now=now),
                             history_since=today.isoformat()))
    return out
