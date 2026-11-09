"""Events on sites (change landing-events, #579; epic #348).

An event is a `SiteBlock` of kind `event`; residents register with a name and an email
(`EventRegistration`). This is the one place Mapsurvey stores a resident's name and email, so
the rules are narrow: for the organising workspace only, for this event only, deleted 30 days
after it (`purge`) or with the block. Registering locks the block row so the seat limit holds
under concurrent posts; the same email holds at most one active registration per event.
"""
import csv
import io
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)

RETENTION_DAYS = 30
REGISTER_LIMIT = '5/h'

REGISTERED, ALREADY, FULL, CLOSED = 'registered', 'already', 'full', 'closed'


def _zone(data):
    try:
        return ZoneInfo(data.get('tz') or 'UTC')
    except Exception:  # noqa: BLE001 — a zone the tz database no longer knows
        return ZoneInfo('UTC')


def starts_at(data):
    """The event's start as an aware datetime, or None for broken data."""
    try:
        naive = datetime.strptime(f"{data.get('date')} {data.get('start') or '00:00'}", '%Y-%m-%d %H:%M')
    except (TypeError, ValueError):
        return None
    return naive.replace(tzinfo=_zone(data))


def ends_at(data):
    """End = date + end time when given (and after the start), else start + 2 hours."""
    start = starts_at(data)
    if start is None:
        return None
    if data.get('end'):
        try:
            end = datetime.strptime(f"{data['date']} {data['end']}", '%Y-%m-%d %H:%M').replace(tzinfo=_zone(data))
            if end > start:
                return end
        except ValueError:
            pass
    return start + timedelta(hours=2)


def active(block):
    return block.registrations.filter(cancelled_at__isnull=True)


def seats_left(block):
    capacity = block.data.get('capacity')
    if not capacity:
        return None
    return max(0, capacity - active(block).count())


def accepting(block, now=None):
    """Registration is open: switched on and the event has not ended."""
    end = ends_at(block.data)
    return bool(block.data.get('open')) and end is not None and (now or timezone.now()) < end


def register(block, name, email):
    """(status, registration) — REGISTERED (new row), ALREADY (same email active: no new row,
    the caller sends the confirmation again), FULL, CLOSED. The block row is locked so two
    visitors cannot take the last seat."""
    from .models import EventRegistration, SiteBlock
    email = email.strip().lower()
    with transaction.atomic():
        locked = SiteBlock.objects.select_for_update().get(pk=block.pk)
        if not accepting(locked):
            return CLOSED, None
        existing = active(locked).filter(email=email).first()
        if existing is not None:
            return ALREADY, existing
        capacity = locked.data.get('capacity')
        if capacity and active(locked).count() >= capacity:
            return FULL, None
        reg = EventRegistration.objects.create(block=locked, name=name.strip()[:120], email=email)
    return REGISTERED, reg


def cancel(registration):
    if registration.cancelled_at is None:
        registration.cancelled_at = timezone.now()
        registration.save(update_fields=['cancelled_at'])


def purge(now=None):
    """Delete the registrations of events that ended more than RETENTION_DAYS ago. Returns the count."""
    from .models import EventRegistration, SiteBlock
    limit = (now or timezone.now()) - timedelta(days=RETENTION_DAYS)
    expired = []
    for block in SiteBlock.objects.filter(kind='event', registrations__isnull=False).distinct().only('id', 'data'):
        end = ends_at(block.data)
        if end is not None and end < limit:
            expired.append(block.pk)
    if not expired:
        return 0
    deleted, _ = EventRegistration.objects.filter(block_id__in=expired).delete()
    return deleted


# ─── mail ─────────────────────────────────────────────────────────────────────

def _ics_text(value):
    return (value or '').replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\n', '\\n')


def _fold(line):
    """RFC 5545 line folding at 75 octets."""
    raw = line.encode('utf-8')
    if len(raw) <= 75:
        return line
    out, chunk = [], b''
    for ch in line:
        b = ch.encode('utf-8')
        if len(chunk) + len(b) > (75 if not out else 74):
            out.append(chunk.decode('utf-8'))
            chunk = b''
        chunk += b
    out.append(chunk.decode('utf-8'))
    return '\r\n '.join(out)


def ics(block, registration, site_url):
    """A one-event VCALENDAR in UTC."""
    from urllib.parse import urlparse
    data = block.data
    fmt = '%Y%m%dT%H%M%SZ'
    utc = ZoneInfo('UTC')
    host = urlparse(settings.SITE_URL).hostname or 'mapsurvey.org'
    title = block.title or block.site.title
    desc = '\n\n'.join(x for x in (data.get('description') or '', site_url) if x)
    lines = [
        'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Mapsurvey//Site events//EN', 'METHOD:PUBLISH',
        'BEGIN:VEVENT', f'UID:{registration.token}@{host}',
        f'DTSTAMP:{timezone.now().astimezone(utc).strftime(fmt)}',
        f'DTSTART:{starts_at(data).astimezone(utc).strftime(fmt)}',
        f'DTEND:{ends_at(data).astimezone(utc).strftime(fmt)}',
        f'SUMMARY:{_ics_text(title)}',
        f'LOCATION:{_ics_text(data.get("place"))}',
        f'DESCRIPTION:{_ics_text(desc)}',
        f'URL:{site_url}',
        'END:VEVENT', 'END:VCALENDAR',
    ]
    return '\r\n'.join(_fold(line) for line in lines) + '\r\n'


def mail_context(registration):
    from .mail import absolute_url
    block = registration.block
    site = block.site
    start = starts_at(block.data)
    return {
        'registration': registration, 'block': block, 'site': site, 'event': block.data,
        'title': block.title or site.title, 'starts_at': start, 'ends_at': ends_at(block.data),
        'tz': block.data.get('tz') or 'UTC',
        'site_url': absolute_url(reverse('site_public', args=[site.slug])),
        'cancel_url': absolute_url(reverse('site_event_cancel', args=[registration.token])),
        'retention_days': RETENTION_DAYS,
    }


def send_confirmation(registration_id):
    """Render and send the confirmation with the .ics attached. Raises on SMTP failure
    (the Celery task retries); returns False when the row is gone or cancelled."""
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.utils import translation

    from .models import EventRegistration
    reg = EventRegistration.objects.select_related('block__site').filter(pk=registration_id).first()
    if reg is None or reg.cancelled_at is not None:
        return False
    ctx = mail_context(reg)
    with translation.override(reg.block.site.language):
        from django.utils.translation import gettext as _
        subject = _("You're registered: %(title)s") % {'title': ctx['title']}
        text = render_to_string('sites/mail/event_confirmation.txt', ctx)
        html = render_to_string('sites/mail/event_confirmation.html', ctx)
    msg = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [reg.email])
    msg.attach_alternative(html, 'text/html')
    msg.attach('event.ics', ics(reg.block, reg, ctx['site_url']), 'text/calendar; charset=utf-8; method=PUBLISH')
    msg.send()
    return True


def queue_confirmation(registration):
    """Enqueue the mail; send it here when the broker refuses (a registration with no mail
    is the state to avoid)."""
    from .tasks import send_event_confirmation
    try:
        send_event_confirmation.delay(registration.pk)
    except Exception:  # noqa: BLE001
        logger.exception('could not enqueue event confirmation %s; sending inline', registration.pk)
        try:
            send_confirmation(registration.pk)
        except Exception:  # noqa: BLE001
            logger.exception('inline event confirmation %s failed', registration.pk)


# ─── attendee export ──────────────────────────────────────────────────────────

def _guard(value):
    value = str(value or '')
    return "'" + value if value[:1] in ('=', '+', '-', '@', '\t', '\r') else value


def csv_bytes(block):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['name', 'email', 'registered_at', 'status'])
    for reg in block.registrations.order_by('created_at', 'id'):
        writer.writerow([_guard(reg.name), _guard(reg.email), reg.created_at.isoformat(timespec='seconds'),
                         'active' if reg.is_active else 'cancelled'])
    return ('\ufeff' + buf.getvalue()).encode('utf-8')
