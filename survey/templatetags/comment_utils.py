from django import template

register = template.Library()


@register.filter
def thread_count(counts, key):
    """`{{ thread_counts|thread_count:"question:Q_1" }}` → open threads on that row.

    `counts` is `comments.open_counts()`; a missing dict (a render site that
    forgot to pass it) yields 0 rather than an error, and the drawer's refresh
    event corrects the badge on the next action.
    """
    if not counts or not key or ':' not in key:
        return 0
    kind, k = key.split(':', 1)
    bucket = counts.get(kind) if isinstance(counts, dict) else None
    if not bucket:
        return 0
    return bucket.get(k, 0)


@register.simple_tag
def badge_key(kind, key):
    return f'{kind}:{key}'


@register.filter
def thread_new(counts, key):
    """True when the anchor has activity the current member has not seen yet."""
    if not counts or not key:
        return False
    return key in (counts.get('new_keys') or ())
