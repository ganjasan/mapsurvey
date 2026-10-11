"""Report-stage outreach signals (openspec: report-stage-outreach-signals).

The best-converting outreach is a note to a creator whose survey has stopped
collecting and who is turning the answers into a report. This module spots that
moment from facts the database already holds and tells the owner. The rules, in
the order they matter:

* ONE sub-signal table. `SUBSIGNALS` is the place a new sign of "they are
  building the report" becomes a rule: a name, a weight and a window. A new
  sub-signal is a row here plus one fact in `collect_facts()`, never a new code
  path. `exported` carries the largest weight because a creator who downloads
  the data is about to build the report -- but it is one weight among others,
  not a verdict: a single export on an otherwise quiet survey does not fire.
* The scorer is pure. `collect_facts()` reads the survey's whole history once;
  `score(facts, as_of)` has no database or network access and evaluates every
  window as it stood on `as_of`. That is what makes the dry run retrospective
  and the historical run cheap (one collection per survey, many dates in memory).
* A survey fires once. `OutreachSignal.survey` is a OneToOne; later runs merge
  new sub-signals into the existing record and never create a second one or
  send a second digest line.
* Detection fails open per survey: a failure while scoring one survey is logged
  and the run goes on. It writes nothing a creator or respondent can see.
* Nothing here stores respondent data: ids, counts and dates only.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone as dt_timezone

from django.conf import settings
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

logger = logging.getLogger(__name__)

# --- sub-signal table --------------------------------------------------------
# name: (weight, window in days or None for "as of now"). Threshold 7
# (settings.REPORT_STAGE_THRESHOLD): `exported` (4) fires with `plateau` (3),
# `closed` (4) or `revisited` (3), or with `institutional` + `geo_rich` (2 + 2);
# alone it does not. Calibrate against the surveys the owner already reached
# out to (design D9) before touching a weight.
SUBSIGNALS = {
    'exported':      (4, 14),   # the heaviest: the report is being built now
    'closed':        (4, 14),
    'plateau':       (3, None),
    'revisited':     (3, 14),
    'geo_rich':      (2, None),
    'institutional': (2, None),
    'pro_interest':  (1, None),
}
# Profile sub-signals describe who the creator is; they never fire on their own.
BEHAVIOURAL = ('exported', 'closed', 'plateau', 'revisited')

MIN_RESPONSES = 30          # settings.REPORT_STAGE_MIN_RESPONSES
THRESHOLD = 7               # settings.REPORT_STAGE_THRESHOLD
PLATEAU_FRACTION = 0.2      # last 7 days below this share of the best 7-day window
PLATEAU_MIN_DAYS = 14       # ...after at least this many days of collection
GEO_RICH_FEATURES = 50
INSTITUTIONAL_SEGMENTS = ('municipality', 'consultancy', 'ngo', 'university')
HISTORICAL_STEP_DAYS = 7
NOTE_SOURCE_PREFIX = 'signal:report-stage:'
ELIGIBLE_STATUSES = ('published', 'closed')
HISTORICAL_STATUSES = ('published', 'closed', 'archived')


def min_responses() -> int:
    return int(getattr(settings, 'REPORT_STAGE_MIN_RESPONSES', MIN_RESPONSES))


def threshold() -> int:
    return int(getattr(settings, 'REPORT_STAGE_THRESHOLD', THRESHOLD))


# --- facts -------------------------------------------------------------------

@dataclass
class SurveyFacts:
    """Everything `score()` needs, for the survey's whole history.

    Daily series rather than totals so one collection serves every `as_of`.
    `closed_days` are the dates of every transition to `closed` (audit log);
    `closed_source` says whether a closed survey without a transition row was
    dated from `updated_at` instead (surveys closed before the audit log).
    """
    survey_id: int = 0
    daily_counts: dict = field(default_factory=dict)   # date -> external, clean, non-empty sessions
    geo_daily: dict = field(default_factory=dict)      # date -> placed geo features
    closed_days: list = field(default_factory=list)
    closed_source: str = ''                            # 'audit' | 'updated_at' | ''
    export_days: list = field(default_factory=list)
    view_days: list = field(default_factory=list)
    segment: str = ''
    institutional_domain: bool = False
    pro_interest: bool = False

    @property
    def first_session_on(self):
        return min(self.daily_counts) if self.daily_counts else None


@dataclass
class ScoreResult:
    fires: bool
    score: int
    signals: dict          # name -> the value that triggered it (for the digest)
    responses: int = 0


def _in_window(day: date, as_of: date, window_days) -> bool:
    if window_days is None:
        return day <= as_of
    return as_of - timedelta(days=window_days) < day <= as_of


def _best_week(daily_counts: dict, first: date, as_of: date) -> int:
    """Largest 7-day window of responses between `first` and `as_of`.

    Over the daily series, not calendar weeks, so a launch on a Thursday is not
    split in two. Linear in the number of days.
    """
    if first is None or first > as_of:
        return 0
    n_days = (as_of - first).days + 1
    series = [daily_counts.get(first + timedelta(days=i), 0) for i in range(n_days)]
    best = window = sum(series[:7])
    for i in range(7, n_days):
        window += series[i] - series[i - 7]
        best = max(best, window)
    return best


def score(facts: SurveyFacts, as_of: date) -> ScoreResult:
    """Deterministic score + the sub-signals that produced it, as of `as_of`. No I/O."""
    responses = sum(n for d, n in facts.daily_counts.items() if d <= as_of)
    if responses < min_responses():
        return ScoreResult(False, 0, {}, responses)

    signals = {}

    export_days = sorted(d for d in facts.export_days if _in_window(d, as_of, SUBSIGNALS['exported'][1]))
    if export_days:
        signals['exported'] = export_days[-1].isoformat()

    closed = sorted(d for d in facts.closed_days if _in_window(d, as_of, SUBSIGNALS['closed'][1]))
    if closed:
        signals['closed'] = closed[-1].isoformat()

    first = facts.first_session_on
    if first is not None and (as_of - first).days >= PLATEAU_MIN_DAYS:
        last7 = sum(n for d, n in facts.daily_counts.items() if _in_window(d, as_of, 7))
        best = _best_week(facts.daily_counts, first, as_of)
        if best > 0 and last7 < PLATEAU_FRACTION * best:
            signals['plateau'] = f'{last7} in the last 7 days vs {best} in the best week'

    view_days = {d for d in facts.view_days if _in_window(d, as_of, SUBSIGNALS['revisited'][1])}
    if len(view_days) >= 2:
        signals['revisited'] = f'{len(view_days)} days'

    geo = sum(n for d, n in facts.geo_daily.items() if d <= as_of)
    if geo >= GEO_RICH_FEATURES:
        signals['geo_rich'] = geo

    if facts.segment in INSTITUTIONAL_SEGMENTS:
        signals['institutional'] = facts.segment
    elif facts.institutional_domain:
        signals['institutional'] = 'domain'

    if facts.pro_interest:
        signals['pro_interest'] = True

    total = sum(SUBSIGNALS[name][0] for name in signals)
    fires = total >= threshold() and any(name in signals for name in BEHAVIOURAL)
    return ScoreResult(fires, total, signals, responses)


# --- collection --------------------------------------------------------------

def _end_of_day(day: date) -> datetime:
    return datetime.combine(day, time.max, tzinfo=dt_timezone.utc)


def collect_facts(survey) -> SurveyFacts:
    """Read the survey's whole history once (canonical + every version).

    The session gate is the Responses page's: external openers, not deleted,
    validation status clean, at least one top-level answer.
    """
    from .analytics import nonempty_sessions
    from .funnel import FREEMAIL_DOMAINS, _domain
    from .models import Answer, AuditLog, CreatorSurveyActivity, ProInterest, SurveySession, UserCohort
    from .public_results import EXCLUDED_VALIDATION_STATUSES
    from .question_types import GEO_TYPES
    from .versioning import canonical_of, family_ids

    canonical = canonical_of(survey)
    facts = SurveyFacts(survey_id=canonical.id)
    ids = family_ids(canonical)

    sessions = nonempty_sessions(
        SurveySession.objects
        .filter(survey_id__in=ids, is_deleted=False,
                opened_by_kind=SurveySession.OPENED_BY_EXTERNAL)
        .exclude(validation_status__in=EXCLUDED_VALIDATION_STATUSES)
    )
    for row in (sessions.annotate(d=TruncDate('start_datetime'))
                .values('d').annotate(n=Count('id', distinct=True))):
        if row['d'] is not None:
            facts.daily_counts[row['d']] = row['n']

    geo_rows = (
        Answer.objects
        .filter(survey_session__in=sessions, question__input_type__in=GEO_TYPES)
        .filter(Q(point__isnull=False) | Q(line__isnull=False)
                | Q(polygon__isnull=False) | Q(multipoint__isnull=False))
        .annotate(d=TruncDate('survey_session__start_datetime'))
        .values('d').annotate(n=Count('id'))
    )
    for row in geo_rows:
        if row['d'] is not None:
            facts.geo_daily[row['d']] = row['n']

    closes = list(
        AuditLog.objects
        .filter(action='status_transition', survey_uuid=canonical.uuid,
                metadata__new_status='closed')
        .order_by('created_at').values_list('created_at', flat=True)
    )
    if closes:
        facts.closed_days = [c.date() for c in closes]
        facts.closed_source = 'audit'
    elif canonical.status in ('closed', 'archived') and canonical.updated_at:
        facts.closed_days = [canonical.updated_at.date()]
        facts.closed_source = 'updated_at'

    for kind, day in (CreatorSurveyActivity.objects
                      .filter(survey=canonical).values_list('kind', 'day')):
        (facts.export_days if kind == 'data_exported' else facts.view_days).append(day)

    owner = canonical.created_by
    if owner is not None:
        facts.segment = (UserCohort.objects
                         .filter(user=owner, dimension__slug='segment')
                         .values_list('cohort__slug', flat=True).first()) or ''
        domain = _domain(owner.email)
        facts.institutional_domain = bool(domain) and domain not in FREEMAIL_DOMAINS
        pro_q = Q(user=owner)
        if owner.email:
            pro_q |= Q(email__iexact=owner.email)
        facts.pro_interest = ProInterest.objects.filter(pro_q).exists()
    return facts


def eligible_surveys(historical: bool = False):
    """Canonical, live (or closed; plus archived for history), not trashed,
    owned by a real non-staff account, not the demo survey. Already-worked
    creators are never excluded: a known client's new survey is a new signal."""
    from .demo import demo_survey_id
    from .models import SurveyHeader

    qs = (SurveyHeader.objects
          .filter(status__in=HISTORICAL_STATUSES if historical else ELIGIBLE_STATUSES,
                  canonical_survey__isnull=True, published_version__isnull=True,
                  deleted_at__isnull=True, created_by__isnull=False,
                  created_by__is_staff=False, created_by__is_superuser=False)
          .select_related('created_by')
          .order_by('id'))
    demo_id = demo_survey_id()
    if demo_id:
        qs = qs.exclude(id=demo_id)
    return qs


# --- the run -----------------------------------------------------------------

@dataclass
class Firing:
    survey: object
    owner: object
    result: ScoreResult
    fired_on: date
    signal: object = None          # the OutreachSignal row (None on a dry run)

    @property
    def worked_since(self):
        profile = getattr(self.owner, 'creator_profile', None)
        if profile is not None and profile.outreach_done:
            return profile.outreach_done_at
        return None

    @property
    def outreach_outcome(self):
        profile = getattr(self.owner, 'creator_profile', None)
        return profile.outreach_outcome if profile is not None else ''


@dataclass
class RunReport:
    as_of: date
    dry_run: bool = False
    fired: list = field(default_factory=list)       # Firing
    enriched: int = 0
    scored: int = 0
    errors: int = 0
    mail_sent: bool = False
    mail_error: str = ''


def _merge_signals(signal, result: ScoreResult):
    """Add sub-signals a later run found; never drop one, never touch status."""
    merged = dict(signal.signals or {})
    new_keys = [k for k in result.signals if k not in merged]
    if not new_keys:
        return False
    for k in new_keys:
        merged[k] = result.signals[k]
    signal.signals = merged
    signal.score = max(signal.score, result.score)
    signal.responses = max(signal.responses, result.responses)
    signal.save(update_fields=['signals', 'score', 'responses', 'updated_at'])
    return True


def _note_body(survey, result: ScoreResult, fired_on: date, signal=None, historical=False):
    from django.urls import reverse

    from .mail import absolute_url

    lines = [
        f'Report-stage signal{" (historical)" if historical else ""} on **{survey.name}** '
        f'as of {fired_on.isoformat()}: {result.responses} responses, score {result.score}.',
        '',
    ]
    for name, value in sorted(result.signals.items()):
        lines.append(f'- {name}: {value}')
    if signal is not None and signal.pk:
        lines += ['', absolute_url(reverse('admin:survey_outreachsignal_change', args=[signal.pk]))]
    return '\n'.join(lines)


def _write_firing(survey, owner, result: ScoreResult, fired_on: date, historical: bool):
    """Create the record, the dossier note and the event. Returns the signal."""
    from . import product_events as pe
    from .models import CreatorNote, OutreachSignal

    signal = OutreachSignal.objects.create(
        survey=survey, user=owner, score=result.score, responses=result.responses,
        signals=result.signals,
        fired_at=datetime.combine(fired_on, time(12, 0), tzinfo=dt_timezone.utc)
        if historical else timezone.now(),
        historical=historical,
    )
    source = f'{NOTE_SOURCE_PREFIX}{survey.uuid}'
    if not CreatorNote.objects.filter(user=owner, source_path=source).exists():
        CreatorNote.objects.create(
            user=owner, author=None, kind='signal', happened_on=fired_on,
            source_path=source,
            body=_note_body(survey, result, fired_on, signal, historical),
        )
    pe.emit(pe.OUTREACH_SIGNAL_FIRED, owner.pk, {
        'survey_id': str(survey.id), 'score': result.score,
        'signals': sorted(result.signals), 'historical': historical,
    })
    return signal


def run(as_of: date | None = None, dry_run: bool = False) -> RunReport:
    """The daily pass: score every eligible survey as of `as_of` (today), record
    the firings, enrich the records that already exist, send one digest."""
    from .models import OutreachSignal

    as_of = as_of or timezone.localdate()
    report = RunReport(as_of=as_of, dry_run=dry_run)
    existing = {s.survey_id: s for s in OutreachSignal.objects.all()}

    for survey in eligible_surveys():
        try:
            facts = collect_facts(survey)
            result = score(facts, as_of)
            report.scored += 1
            if not result.fires:
                continue
            signal = existing.get(survey.id)
            if signal is not None:
                if not dry_run and _merge_signals(signal, result):
                    report.enriched += 1
                continue
            owner = survey.created_by
            firing = Firing(survey=survey, owner=owner, result=result, fired_on=as_of)
            if not dry_run:
                firing.signal = _write_firing(survey, owner, result, as_of, historical=False)
            report.fired.append(firing)
        except Exception:  # noqa: BLE001 — one survey must not stop the run
            report.errors += 1
            logger.exception('report-stage scoring failed for survey %s', getattr(survey, 'id', '?'))

    if report.fired and not dry_run:
        try:
            send_digest(report)
            report.mail_sent = True
        except Exception as exc:  # noqa: BLE001 — the records exist; the mail is the last step
            report.mail_error = str(exc) or exc.__class__.__name__
            logger.exception('report-stage digest could not be sent')
    return report


def run_historical(dry_run: bool = False, today: date | None = None) -> RunReport:
    """Walk every eligible survey's own timeline and record the signal dated
    the first day it would have fired. No digest: the caller prints the table."""
    from .models import OutreachSignal

    today = today or timezone.localdate()
    report = RunReport(as_of=today, dry_run=dry_run)
    existing = set(OutreachSignal.objects.values_list('survey_id', flat=True))

    for survey in eligible_surveys(historical=True):
        if survey.id in existing:
            continue
        try:
            facts = collect_facts(survey)
            report.scored += 1
            fired_on = first_firing_day(facts, today)
            if fired_on is None:
                continue
            result = score(facts, fired_on)
            owner = survey.created_by
            firing = Firing(survey=survey, owner=owner, result=result, fired_on=fired_on)
            if not dry_run:
                firing.signal = _write_firing(survey, owner, result, fired_on, historical=True)
            report.fired.append(firing)
        except Exception:  # noqa: BLE001
            report.errors += 1
            logger.exception('historical report-stage scoring failed for survey %s', getattr(survey, 'id', '?'))
    return report


def first_firing_day(facts: SurveyFacts, today: date) -> date | None:
    """The first day `score()` fires: weekly steps from the first response,
    then day by day inside the first firing week. Pure."""
    first = facts.first_session_on
    if first is None:
        return None
    day = first
    previous = None
    while day <= today:
        if score(facts, day).fires:
            start = (previous + timedelta(days=1)) if previous is not None else first
            probe = start
            while probe < day:
                if score(facts, probe).fires:
                    return probe
                probe += timedelta(days=1)
            return day
        previous = day
        day += timedelta(days=HISTORICAL_STEP_DAYS)
    if previous is not None and previous < today and score(facts, today).fires:
        probe = previous + timedelta(days=1)
        while probe <= today:
            if score(facts, probe).fires:
                return probe
            probe += timedelta(days=1)
    return None


# --- the worked flag ---------------------------------------------------------

def prefill_worked(dry_run: bool = False):
    """Mark every creator with an `email` note on their timeline as worked, by
    the earliest such note's date. Never clears, never moves a date later."""
    from django.db.models import Min

    from .models import CreatorNote, CreatorProfile

    rows = (CreatorNote.objects.filter(kind='email')
            .values('user_id').annotate(first=Min('happened_on')))
    marked = []
    for row in rows:
        profile = CreatorProfile.objects.filter(user_id=row['user_id']).first()
        if profile is not None and profile.outreach_done and profile.outreach_done_at \
                and profile.outreach_done_at <= row['first']:
            continue
        marked.append((row['user_id'], row['first']))
        if not dry_run:
            from django.contrib.auth import get_user_model
            user = get_user_model().objects.get(pk=row['user_id'])
            CreatorProfile.mark_worked(user, on=row['first'])
    return marked


# --- the digest --------------------------------------------------------------

def digest_context(report: RunReport) -> dict:
    from django.urls import reverse

    from .mail import absolute_url

    def row(firing: Firing):
        owner = firing.owner
        profile = getattr(owner, 'creator_profile', None)
        return {
            'survey_name': firing.survey.name,
            'survey_uuid': str(firing.survey.uuid),
            'username': owner.username,
            'organization': profile.organization if profile is not None else '',
            'segment': firing.result.signals.get('institutional', '')
            if firing.result.signals.get('institutional') not in (None, 'domain') else '',
            'responses': firing.result.responses,
            'score': firing.result.score,
            'signals': [(k, v) for k, v in sorted(firing.result.signals.items())],
            'worked_since': firing.worked_since,
            'outreach_outcome': firing.outreach_outcome,
            'signal_url': absolute_url(reverse('admin:survey_outreachsignal_change', args=[firing.signal.pk]))
            if firing.signal is not None else '',
            'dossier_url': absolute_url(reverse('admin:auth_user_change', args=[owner.pk])),
            'responses_url': absolute_url(reverse('editor_survey_analytics', args=[firing.survey.uuid])),
        }

    new = [row(f) for f in report.fired if f.worked_since is None]
    known = [row(f) for f in report.fired if f.worked_since is not None]
    return {'as_of': report.as_of, 'new': new, 'known': known, 'total': len(report.fired)}


def digest_subject(report: RunReport) -> str:
    n = len(report.fired)
    return f'[Mapsurvey] Report stage: {n} survey{"s" if n != 1 else ""} ({report.as_of.isoformat()})'


def send_digest(report: RunReport, fail_silently: bool = False):
    from .mail import send_templated_mail

    to = getattr(settings, 'OUTREACH_SIGNAL_EMAIL', '') or settings.CONTACT_EMAIL
    return send_templated_mail(
        'outreach/report_stage_digest', to, digest_subject(report),
        digest_context(report), fail_silently=fail_silently,
    )
