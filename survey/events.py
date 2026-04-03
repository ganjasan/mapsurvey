"""
Lightweight event emission for survey respondent tracking.

Call emit_event() from views after the triggering action succeeds.
All failures are swallowed — never let tracking break the survey UX.
"""
import logging
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_REFERRER_BUCKETS = {
    'google': ['google.com', 'google.co'],
    'bing': ['bing.com'],
    'social': [
        'facebook.com', 'fb.com', 'twitter.com', 'x.com', 't.co',
        'instagram.com', 'linkedin.com', 'youtube.com',
        't.me', 'telegram.org', 'vk.com', 'ok.ru',
        'reddit.com', 'tiktok.com', 'whatsapp.com',
    ],
    'email': ['mail.google.com', 'mail.yahoo.com', 'outlook.live.com'],
}


def _classify_referrer(raw_referrer):
    """
    Extract hostname and classify into a bucket.
    Returns (host, bucket) where bucket is one of:
    'direct', 'google', 'bing', 'social', 'email', 'other'.
    """
    if not raw_referrer:
        return '', 'direct'

    try:
        host = urlparse(raw_referrer).hostname or ''
        host = host.lower()
        if host.startswith('www.'):
            host = host[4:]
    except Exception:
        return '', 'direct'

    if not host:
        return '', 'direct'

    for bucket, patterns in _REFERRER_BUCKETS.items():
        if any(host == p or host.endswith('.' + p) for p in patterns):
            return host, bucket

    return host, 'other'


def _parse_user_agent(ua):
    """
    Parse user agent string into device_type, os, browser.
    Returns dict with keys: device_type, os, browser.
    """
    if not ua:
        return {'device_type': 'unknown', 'os': 'unknown', 'browser': 'unknown'}

    # Device type (order: tablet before mobile — iPad UA contains "Mobile")
    if re.search(r'iPad|Android(?!.*Mobile)|Tablet', ua, re.I):
        device_type = 'tablet'
    elif re.search(r'Mobi|Android.*Mobile|iPhone|iPod|Windows Phone', ua, re.I):
        device_type = 'mobile'
    elif re.search(r'bot|crawl|spider|slurp|wget|curl', ua, re.I):
        device_type = 'bot'
    else:
        device_type = 'desktop'

    # OS (order: iOS before macOS — iPhone/iPad UA contains "Mac OS X")
    if re.search(r'iPhone|iPad|iPod', ua):
        os_name = 'iOS'
    elif re.search(r'Android', ua):
        os_name = 'Android'
    elif re.search(r'Windows', ua):
        os_name = 'Windows'
    elif re.search(r'Mac OS X|Macintosh', ua):
        os_name = 'macOS'
    elif re.search(r'CrOS', ua):
        os_name = 'ChromeOS'
    elif re.search(r'Linux', ua):
        os_name = 'Linux'
    else:
        os_name = 'other'

    # Browser (order matters — check specific before generic)
    if re.search(r'Edg/', ua):
        browser = 'Edge'
    elif re.search(r'OPR/|Opera', ua):
        browser = 'Opera'
    elif re.search(r'YaBrowser', ua):
        browser = 'Yandex'
    elif re.search(r'SamsungBrowser', ua):
        browser = 'Samsung'
    elif re.search(r'Firefox/', ua):
        browser = 'Firefox'
    elif re.search(r'CriOS|Chrome/', ua) and not re.search(r'Chromium', ua):
        browser = 'Chrome'
    elif re.search(r'Safari/', ua) and not re.search(r'Chrome|Chromium', ua):
        browser = 'Safari'
    else:
        browser = 'other'

    return {'device_type': device_type, 'os': os_name, 'browser': browser}


_UTM_KEYS = ('utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content')


def store_utm_in_session(request):
    """Persist UTM params from request.GET into session for later capture."""
    params = {}
    for key in _UTM_KEYS:
        val = request.GET.get(key, '').strip()[:200]
        if val:
            params[key] = val
    if params:
        request.session['utm_params'] = params


def _consume_utm_from_session(request):
    """Return stored UTM params from session and clear them."""
    return request.session.pop('utm_params', {})


def build_session_start_metadata(request):
    """
    Extract user agent, referrer, device info, and UTM params for session_start event.
    """
    raw_referrer = request.META.get('HTTP_REFERER', '')
    host, bucket = _classify_referrer(raw_referrer)
    raw_ua = request.META.get('HTTP_USER_AGENT', '')
    device_info = _parse_user_agent(raw_ua)
    utm = _consume_utm_from_session(request)
    return {
        'user_agent': raw_ua[:512],
        'referrer_raw': raw_referrer[:512],
        'referrer_host': host,
        'referrer_type': bucket,
        **device_info,
        **utm,
    }


def emit_event(session, event_type, metadata=None):
    """
    Write a SurveyEvent row. Silently swallows all exceptions.

    Args:
        session: SurveySession instance (must be saved, i.e. has a PK)
        event_type: string matching EVENT_TYPE_CHOICES keys
        metadata: optional dict stored in the event's metadata JSONField
    """
    from .models import SurveyEvent  # local import avoids circular at module load

    if session is None or not session.pk:
        return

    try:
        SurveyEvent.objects.create(
            session=session,
            event_type=event_type,
            metadata=metadata or {},
        )
    except Exception:
        logger.exception(
            'Failed to emit event %s for session %s',
            event_type, getattr(session, 'pk', '?'),
        )
