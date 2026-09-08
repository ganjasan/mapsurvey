"""
Lightweight event emission for survey respondent tracking.

Call emit_event() from views after the triggering action succeeds.
All failures are swallowed — never let tracking break the survey UX.
"""
import logging
import re
import time
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Order matters: the first bucket whose pattern matches wins, and several hosts
# would match more than one. `mail.google.com` is email, not google;
# `gemini.google.com` is an AI assistant, not search; `mail.yahoo.com` is email,
# not search_other. So the specific buckets sit above the broad ones.
_REFERRER_BUCKETS = {
    'email': ['mail.google.com', 'mail.yahoo.com', 'outlook.live.com'],
    'ai': [
        'chatgpt.com', 'chat.openai.com', 'perplexity.ai', 'gemini.google.com',
        'claude.ai', 'copilot.microsoft.com', 'you.com', 'phind.com',
    ],
    'search_other': [
        'duckduckgo.com', 'search.brave.com', 'yahoo.com', 'ecosia.org',
        'startpage.com', 'yandex.ru', 'yandex.com',
    ],
    'google': ['google.com', 'google.co'],
    'bing': ['bing.com'],
    'social': [
        'facebook.com', 'fb.com', 'twitter.com', 'x.com', 't.co',
        'instagram.com', 'linkedin.com', 'youtube.com',
        't.me', 'telegram.org', 'vk.com', 'ok.ru',
        'reddit.com', 'tiktok.com', 'whatsapp.com',
    ],
}

# ChatGPT appends `utm_source=chatgpt.com` to outbound links and often sends no
# referrer at all; the other assistants are inconsistent. A UTM naming any of
# these promotes an otherwise direct/other visit to the `ai` bucket.
_AI_UTM_TOKENS = ('chatgpt', 'openai', 'perplexity', 'gemini', 'claude', 'copilot')


def is_own_host(host, request=None, own_host=None):
    """True when `host` is this site (or a subdomain of it).

    An internal hop -- landing -> /register/ -- must never be recorded as the
    acquisition source; that mistake spoiled 36 of the first 114 attribution rows.
    """
    if not host:
        return False
    if own_host is None:
        own_host = request.get_host() if request is not None else ''
    hosts = [own_host] if isinstance(own_host, str) else list(own_host or [])
    host = host.lower()
    for our in hosts:
        our = (our or '').split(':')[0].lower().lstrip('.')
        if our and (host == our or host.endswith('.' + our)):
            return True
    return False


def classify_source(raw_referrer, utm_source='', request=None, own_host=None):
    """(host, bucket) for a first touch, combining referrer and UTM.

    The referrer decides first. The site's own host counts as no referrer. When
    that leaves `direct` or `other`, an AI-assistant `utm_source` decides instead.
    """
    host, bucket = _classify_referrer(raw_referrer)
    if is_own_host(host, request=request, own_host=own_host):
        host, bucket = '', 'direct'
    utm = (utm_source or '').lower()
    if bucket in ('direct', 'other') and utm and any(t in utm for t in _AI_UTM_TOKENS):
        bucket = 'ai'
    return host, bucket


def _classify_referrer(raw_referrer):
    """
    Extract hostname and classify into a bucket.
    Returns (host, bucket) where bucket is one of:
    'direct', 'email', 'ai', 'search_other', 'google', 'bing', 'social', 'other'.
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


FIRST_TOUCH_COOKIE = 'ms_ft'
FIRST_TOUCH_MAX_AGE = 90 * 24 * 3600
_FIRST_TOUCH_SALT = 'survey.first_touch'


def build_first_touch(request):
    """The first-touch record for this request, or None when nothing is known.

    Keys are one letter because the value rides in a cookie on every marketing
    request: r = raw referrer (truncated), h = referrer host, b = bucket,
    s/m/c = utm source/medium/campaign, p = landing path, t = unix time.
    Holds no identifier of any kind.
    """
    raw = request.META.get('HTTP_REFERER', '')[:200]
    utm = {k: request.GET.get(k, '').strip()[:100] for k in ('utm_source', 'utm_medium', 'utm_campaign')}
    host, bucket = classify_source(raw, utm['utm_source'], request=request)
    if not host:
        raw = ''
    return {
        'r': raw, 'h': host, 'b': bucket,
        's': utm['utm_source'], 'm': utm['utm_medium'], 'c': utm['utm_campaign'],
        'p': request.path[:200], 't': int(time.time()),
    }


def read_first_touch(request):
    """Decode the first-touch cookie, or None when absent or tampered with."""
    from django.core import signing

    raw = request.COOKIES.get(FIRST_TOUCH_COOKIE)
    if not raw:
        return None
    try:
        data = signing.loads(raw, salt=_FIRST_TOUCH_SALT, max_age=FIRST_TOUCH_MAX_AGE)
    except (signing.BadSignature, signing.SignatureExpired):
        return None
    return data if isinstance(data, dict) else None


def encode_first_touch(data):
    from django.core import signing

    return signing.dumps(data, salt=_FIRST_TOUCH_SALT, compress=True)


def capture_signup_source(request):
    """Legacy session-based first-touch capture (landing / register GET).

    Kept as the fallback for visitors whose first touch predates the cookie
    (`FirstTouchMiddleware`), which is now the primary store. Session-only and
    fail-open -- never breaks page rendering. Stores UTM params and the first
    *external* referrer seen, so an internal hop (landing -> /register/) does not
    overwrite the real source.
    """
    try:
        store_utm_in_session(request)
        raw = request.META.get('HTTP_REFERER', '')
        if raw and 'signup_referrer' not in request.session:
            host, bucket = _classify_referrer(raw)
            if host and not is_own_host(host, request=request):
                request.session['signup_referrer'] = {
                    'raw': raw[:512], 'host': host, 'bucket': bucket,
                }
    except Exception:
        logger.debug("capture_signup_source failed", exc_info=True)


def first_touch_for_signup(request):
    """Resolve the first touch at registration: cookie, then legacy session, then direct.

    Never falls back to the current request's referrer -- at registration that is
    the site itself.
    """
    ft = read_first_touch(request)
    if ft:
        return {
            'raw_referrer': ft.get('r') or '',
            'host': ft.get('h') or '',
            'bucket': ft.get('b') or 'direct',
            'utm_source': ft.get('s') or '',
            'utm_medium': ft.get('m') or '',
            'utm_campaign': ft.get('c') or '',
            'landing_path': ft.get('p') or '',
        }
    src = request.session.get('signup_referrer') or {}
    utm = _consume_utm_from_session(request)
    raw = src.get('raw') or ''
    host, bucket = classify_source(raw, utm.get('utm_source', ''), request=request)
    return {
        'raw_referrer': raw if host else '',
        'host': host,
        'bucket': bucket,
        'utm_source': utm.get('utm_source', ''),
        'utm_medium': utm.get('utm_medium', ''),
        'utm_campaign': utm.get('utm_campaign', ''),
        'landing_path': '',
    }


def persist_signup_attribution(user, request):
    """Create the SignupAttribution row for a newly registered creator.

    Fail-open: any error is swallowed so registration always completes (mirrors
    emit_event). Reads the first-touch cookie, then the legacy session values.
    """
    try:
        from .models import SignupAttribution
        if SignupAttribution.objects.filter(user=user).exists():
            return None
        ft = first_touch_for_signup(request)
        row = SignupAttribution.objects.create(
            user=user,
            raw_referrer=ft['raw_referrer'][:512],
            source_bucket=ft['bucket'] or 'direct',
            utm_source=ft['utm_source'][:100],
            utm_medium=ft['utm_medium'][:100],
            utm_campaign=ft['utm_campaign'][:100],
            landing_path=ft['landing_path'][:200],
        )
        request.session.pop('signup_referrer', None)
        return row
    except Exception:
        logger.exception("persist_signup_attribution failed for user %s", getattr(user, 'id', '?'))
        return None


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
