"""Cursor pagination for list endpoints.

A cursor is signed and bound to the list it came from (`list_key`, e.g.
`responses:<survey uuid>`): one from another list, another survey, or a
tampered one is `400 bad_cursor`. Pages run by primary key, newest first, so
inserts never shift a page. `limit` defaults to 50 and is clamped to 1..200 --
a too-large limit is not an error.
"""
from django.core import signing

from ..errors import BAD_CURSOR, ApiError

DEFAULT_LIMIT = 50
MAX_LIMIT = 200
SALT = 'api.v1.cursor'


def clamp(limit):
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, limit))


def _after(cursor, list_key):
    if not cursor:
        return None
    try:
        data = signing.loads(cursor, salt=SALT)
    except signing.BadSignature:
        raise ApiError(400, BAD_CURSOR, 'This cursor is not valid.')
    if not isinstance(data, dict) or data.get('l') != list_key or not isinstance(data.get('k'), int):
        raise ApiError(400, BAD_CURSOR, 'This cursor belongs to another list.')
    return data['k']


def page(queryset, list_key, cursor=None, limit=DEFAULT_LIMIT):
    """(items, next_cursor) of `queryset`, newest first by primary key."""
    limit = clamp(limit)
    after = _after(cursor, list_key)
    qs = queryset.order_by('-pk')
    if after is not None:
        qs = qs.filter(pk__lt=after)
    items = list(qs[:limit + 1])
    more = len(items) > limit
    items = items[:limit]
    next_cursor = signing.dumps({'l': list_key, 'k': items[-1].pk}, salt=SALT) if more else None
    return items, next_cursor
