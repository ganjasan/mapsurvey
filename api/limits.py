"""Rate limits for token-authenticated traffic.

Three kinds, all fixed windows on the Django cache (Redis in production):

- per-token request windows -- reads, writes and a daily cap -- keyed by the
  token id. Not by IP (Cloudflare and offices share addresses) and not by user
  (one creator's runaway agent must not take their other integration down);
- named daily caps for the expensive actions a resource server calls out by
  name (`hit(principal, "survey_create")`), so an agent in a loop stops at 50
  surveys rather than 5 000 calls;
- a per-IP cap on FAILED bearer attempts, consulted before the token lookup,
  so guessing tokens costs the guesser and not the database.

Fail-open: when the cache is unreachable the request goes through, logged once
per process. `RATELIMIT_FAIL_OPEN` is the project's rule for registration too;
the Pro gate and the role checks still hold without a counter.
"""
import logging
import time

from django.conf import settings
from django.core.cache import cache

from .errors import RATE_LIMITED, ApiError

logger = logging.getLogger(__name__)

MINUTE = 60
DAY = 24 * 3600

# group -> (limit, window seconds). settings.API_RATE_LIMITS overrides by group.
DEFAULT_LIMITS = {
    'api.read': (600, MINUTE),
    'api.write': (60, MINUTE),
    'api.day': (5000, DAY),
    'api.auth_fail': (30, MINUTE),
    # One MCP session's tool calls (change mcp-server): an agent in a loop is
    # the realistic failure, and it burns one session, not the token's day.
    'mcp.session': (300, 10 * MINUTE),
}

# action -> per-token daily cap. A new expensive action is a row here; `hit()`
# with an unregistered name is a programming error, not a free pass.
DAILY_CAPS = {
    'survey_create': 50,
    'survey_delete': 20,
    'survey_import': 20,
    'export': 100,
}

READ_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS'})

_warned = False


def limit_for(group):
    overrides = getattr(settings, 'API_RATE_LIMITS', None) or {}
    if group in overrides:
        return tuple(overrides[group])
    if group in DEFAULT_LIMITS:
        return DEFAULT_LIMITS[group]
    if group.startswith('cap.'):
        action = group[len('cap.'):]
        return DAILY_CAPS[action], DAY
    raise KeyError(group)


def _window(window_seconds, now=None):
    now = now if now is not None else time.time()
    start = int(now // window_seconds) * window_seconds
    return start, int(start + window_seconds - now) or 1


def _count(key, window_seconds, increment, now=None):
    """Current count in the window for `key`, after incrementing when asked.
    Raises whatever the cache raises; callers decide fail-open."""
    start, time_left = _window(window_seconds, now)
    cache_key = f'api-limit:{key}:{start}'
    if increment:
        added = cache.add(cache_key, 1, timeout=window_seconds + 1)
        if added:
            return 1, time_left
        try:
            return cache.incr(cache_key), time_left
        except ValueError:
            # Expired between add and incr; start a fresh window.
            cache.set(cache_key, 1, timeout=window_seconds + 1)
            return 1, time_left
    value = cache.get(cache_key)
    return (value or 0), time_left


def _fail_open(exc):
    global _warned
    if not _warned:
        logger.warning('api limits: cache unavailable, failing open (%s)', exc)
        _warned = True


def _exceeded(key, group, increment=True):
    """(exceeded, time_left) for one group. Fail-open on cache trouble."""
    limit, window = limit_for(group)
    try:
        # The group is part of the key: reads, writes and the day share a token
        # but not a counter (the first run of test_reads_do_not_consume_writes).
        count, time_left = _count(f'{group}:{key}', window, increment)
    except Exception as exc:  # noqa: BLE001 -- any backend error is an outage to us
        _fail_open(exc)
        return False, 0
    return count > limit, time_left


def _limited(group, time_left):
    err = ApiError(429, RATE_LIMITED, 'Rate limit exceeded; try again later.', limit=group, retry_after=time_left)
    err.headers['Retry-After'] = str(time_left)
    return err


def check_request(principal, method):
    """Per-token windows for one request: the read or write minute window and the
    daily cap. Raises ApiError(429) with Retry-After when any is exceeded."""
    key = f'tok:{principal.token_id}'
    groups = ('api.read' if method.upper() in READ_METHODS else 'api.write', 'api.day')
    for group in groups:
        exceeded, time_left = _exceeded(key, group)
        if exceeded:
            raise _limited(group, time_left)


def hit(principal, action):
    """Count one use of a named expensive action against the token's daily cap.
    KeyError for an action that is not in DAILY_CAPS."""
    if action not in DAILY_CAPS and f'cap.{action}' not in (getattr(settings, 'API_RATE_LIMITS', None) or {}):
        raise KeyError(action)
    exceeded, time_left = _exceeded(f'tok:{principal.token_id}', f'cap.{action}')
    if exceeded:
        raise _limited(action, time_left)


def check_group(group, key):
    """Count one hit of `key` against a named group (`DEFAULT_LIMITS` or an
    override) and raise ApiError(429) with Retry-After when it is exceeded.
    The MCP server's per-session cap; REST uses the per-token windows above."""
    exceeded, time_left = _exceeded(key, group)
    if exceeded:
        raise _limited(group, time_left)


def auth_failures_exceeded(ip):
    """Read-only: has this IP already spent its failed-attempt budget?"""
    limit, window = limit_for('api.auth_fail')
    try:
        count, time_left = _count(f'api.auth_fail:ip:{ip}', window, increment=False)
    except Exception as exc:  # noqa: BLE001
        _fail_open(exc)
        return False, 0
    return count >= limit, time_left


def auth_failure(ip):
    """Count one failed bearer attempt from `ip`."""
    _exceeded(f'ip:{ip}', 'api.auth_fail', increment=True)


def reset_warning_for_tests():
    global _warned
    _warned = False
