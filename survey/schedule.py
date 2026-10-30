"""The survey period: "accepts answers from … to …" (change survey-schedule, #497).

Two optional instants on the CANONICAL survey, `opens_at` and `closes_at` (UTC), plus the
IANA zone the creator typed them in (`schedule_timezone`, display only). Everything that asks
"is this survey open right now?" comes here -- the respondent gate, the periodic task, the
publishing widget and the API output -- so there is one definition of the period:

- before `opens_at` the survey is published but respondents see the "opens on" page;
- at or after `closes_at` respondents see the closed page at once, and `close_due()` (Celery
  beat, every five minutes) performs the real `transition(..., 'closed')` so the status, the
  audit row and every creator surface are what a manual Close produces;
- reopening by hand clears a `closes_at` that has passed (`clear_past`), so the task never
  closes a reopened survey again.

Opening never changes status: publishing stays the creator's click (content screening, the
translation-gap acknowledgement and the `survey_published` event are human moments).
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo, available_timezones

from django.db import transaction
from django.utils import timezone
from django.utils.formats import date_format

logger = logging.getLogger(__name__)

PERIOD_FIELDS = ('opens_at', 'closes_at', 'schedule_timezone')
#: Beat interval in seconds; `CELERY_BEAT_SCHEDULE` reads it, the docs quote it.
CLOSE_INTERVAL_SECONDS = 300
INPUT_FORMAT = '%Y-%m-%dT%H:%M'   # what <input type="datetime-local"> posts and renders


def _canonical(survey):
    from .versioning import canonical_of
    return canonical_of(survey)


def is_valid_zone(name):
    return not name or name in available_timezones()


def zone_name(survey):
    return _canonical(survey).schedule_timezone or 'UTC'


def zone(survey):
    try:
        return ZoneInfo(zone_name(survey))
    except Exception:          # a zone the tz database no longer knows
        return ZoneInfo('UTC')


def phase(survey, now=None):
    """`'before'` | `'open'` | `'after'` for the canonical survey's period, or `None` when
    the survey is not `published` (the period means nothing for drafts, testing, closed)."""
    canonical = _canonical(survey)
    if canonical.status != 'published':
        return None
    now = now or timezone.now()
    if canonical.opens_at and now < canonical.opens_at:
        return 'before'
    if canonical.closes_at and now >= canonical.closes_at:
        return 'after'
    return 'open'


def format_in_zone(instant, survey):
    """`instant` as the creator would read it: in the survey's zone, in the active
    language's medium date-time format."""
    local = instant.astimezone(zone(survey))
    return date_format(local, 'DATETIME_FORMAT')


def input_value(instant, survey):
    """`instant` as the value of a `datetime-local` input, in the survey's zone."""
    if instant is None:
        return ''
    return instant.astimezone(zone(survey)).strftime(INPUT_FORMAT)


def next_event(survey, now=None):
    """What the publishing widget shows under the status chip: `{'kind': 'opens'|'closes',
    'at': <instant>, 'text': <formatted in zone>}`, or `None` when nothing is ahead."""
    current = phase(survey, now)
    canonical = _canonical(survey)
    now = now or timezone.now()
    if current == 'before':
        return {'kind': 'opens', 'at': canonical.opens_at, 'text': format_in_zone(canonical.opens_at, survey)}
    if current == 'open' and canonical.closes_at and canonical.closes_at > now:
        return {'kind': 'closes', 'at': canonical.closes_at, 'text': format_in_zone(canonical.closes_at, survey)}
    return None


def move_to_canonical(survey):
    """The Settings form is bound to whatever row the editor shows -- the draft copy while
    unpublished changes exist -- but the period belongs to the live survey: respondents and
    the task read it there, and `publish_draft()` does not copy it. Called by
    `services.surveys.update_settings` after `form.save()`."""
    canonical = _canonical(survey)
    if canonical.pk == survey.pk:
        return
    for name in PERIOD_FIELDS:
        setattr(canonical, name, getattr(survey, name))
        setattr(survey, name, '' if name == 'schedule_timezone' else None)
    canonical.save(update_fields=PERIOD_FIELDS)
    survey.save(update_fields=PERIOD_FIELDS)


def clear_past(survey, now=None):
    """On a manual reopen: drop the instants that have already passed, so the period reads
    clean and the task cannot close the survey again. A `closes_at` still ahead is kept --
    the creator closed early by hand and the plan stands. Returns what was cleared (for the
    audit row); saves the canonical row when anything changed."""
    canonical = _canonical(survey)
    now = now or timezone.now()
    cleared = {}
    if canonical.closes_at and canonical.closes_at <= now:
        cleared['closes_at'] = canonical.closes_at.isoformat()
        canonical.closes_at = None
        if canonical.opens_at and canonical.opens_at <= now:
            cleared['opens_at'] = canonical.opens_at.isoformat()
            canonical.opens_at = None
    if cleared:
        canonical.save(update_fields=[k for k in cleared])
        if canonical.pk != survey.pk:
            for k in cleared:
                setattr(survey, k, None)
    return cleared


def due_for_close(now=None):
    """Canonical, live, not trashed, past their closing time."""
    from .models import SurveyHeader
    now = now or timezone.now()
    return SurveyHeader.objects.filter(
        status='published', closes_at__lte=now, deleted_at__isnull=True,
        canonical_survey__isnull=True, published_version__isnull=True,
    ).order_by('closes_at')


def close_due(now=None):
    """Close every due survey through the lifecycle service; one transaction per survey,
    `skip_locked` so an overlapping run never processes the same row twice; a failure is
    logged and the pass continues. Returns how many were closed."""
    from .models import SurveyHeader
    from .services.context import Actor, SURFACE_SCHEDULE
    from .services.publishing import transition

    closed = 0
    for pk in list(due_for_close(now).values_list('pk', flat=True)):
        try:
            with transaction.atomic():
                survey = (SurveyHeader.objects.select_for_update(skip_locked=True)
                          .filter(pk=pk, status='published').first())
                if survey is None:
                    continue
                transition(Actor(user=None, surface=SURFACE_SCHEDULE), survey, 'closed',
                           audit_metadata={'scheduled': True})
                closed += 1
                logger.info('survey schedule: closed %s at its closing time', survey.uuid)
        except Exception:
            logger.exception('survey schedule: could not close survey %s', pk)
    return closed


def parse_posted(raw):
    """A posted period value: aware (ISO 8601 with an offset -- the API) or naive (the
    `datetime-local` input, read in the survey's zone by the form). None when unparseable."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).strip().replace('Z', '+00:00'))
    except ValueError:
        return None
