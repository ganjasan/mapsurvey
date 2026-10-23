"""Redirect URI rules -- the ONE place that decides (change oauth-server, D3).

RFC 9700 §4.1.1: exact string matching, `https` only. RFC 8252 §7.3: a native
app listening on the loopback interface cannot know its port in advance, so
`http://127.0.0.1:<port>/…` is accepted with ANY port -- that is how Claude
Code gets its callback. The toolkit checks schemes inside `Application.clean()`
against a flat list and matches exactly, with no loopback notion, and the
model cannot be swapped once its tables exist; so the scheme list includes
`http` and this module is what keeps that honest. It runs:

- at DCR registration and RFC 7592 update (`api.oauth.dcr.normalise_metadata`)
- on a fetched CIMD document (`api.oauth.cimd.MetadataFetcher`)
- on every `Application` save (`pre_save` in `api.apps`, the admin/shell backstop)
- at authorize and token time (`validator.validate_redirect_uri`)

`localhost` is on the list although RFC 8252 prefers the literal addresses:
Claude Code registers `http://localhost:<port>/callback`.
"""
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError

LOOPBACK_HOSTS = frozenset({'127.0.0.1', '::1', 'localhost'})


def _split(uri):
    try:
        return urlsplit(uri)
    except ValueError:
        return None


def is_loopback(uri):
    """`http://127.0.0.1…`, `http://[::1]…` or `http://localhost…` -- any port,
    no userinfo, no fragment."""
    p = _split(uri)
    return bool(
        p is not None and p.scheme == 'http' and p.hostname in LOOPBACK_HOSTS
        and not p.username and not p.password and not p.fragment
    )


def problem(uri):
    """Why `uri` may not be registered, or None when it may."""
    p = _split(uri)
    if p is None or not p.scheme or not p.hostname:
        return 'not an absolute URI'
    if p.fragment:
        return 'a redirect URI must not carry a fragment'
    if p.username or p.password:
        return 'a redirect URI must not carry userinfo'
    if '*' in uri:
        return 'wildcards are not accepted'
    if p.scheme == 'https':
        return None
    if p.scheme == 'http':
        return None if p.hostname in LOOPBACK_HOSTS else 'http is accepted for loopback hosts only'
    return f'scheme {p.scheme!r} is not accepted'


def check_registrable(uris):
    """Raise ValidationError naming the first URI that may not be registered."""
    for uri in uris:
        why = problem(uri)
        if why:
            raise ValidationError(f'redirect URI {uri!r}: {why}', code='invalid_redirect_uri')


def matches(requested, registered):
    """Exact match, except a loopback URI matches a registered loopback URI with
    the same scheme, host, path and query and any port."""
    if requested in registered:
        return problem(requested) is None
    if not is_loopback(requested):
        return False
    r = urlsplit(requested)
    for candidate in registered:
        if not is_loopback(candidate):
            continue
        c = urlsplit(candidate)
        if (c.hostname, c.path, c.query) == (r.hostname, r.path, r.query):
            return True
    return False
