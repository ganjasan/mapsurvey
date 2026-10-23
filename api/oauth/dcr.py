"""Dynamic client registration: the limiter and the metadata normalisation
that DCR and CIMD share (change oauth-server, D8).

Registration is open -- neither ChatGPT nor claude.ai can authenticate to
register -- so two things stand between the endpoint and a flood: a per-IP
budget (10 an hour, 50 a day; fail-open like every limiter here, because a
cache outage must not take connectors down with it) and a 30-day purge of
registrations nobody authorised (`purge_oauth_clients`).

Normalisation is what the consent page relies on: the name is attacker-
chosen ("Mapsurvey Official"), so it is bounded and shown AFTER the redirect
host; `logo_uri` and friends are dropped unread -- a logo is a tracking pixel
at best and an SSRF at worst; redirect URIs go through the one rule.
"""
import json
import re
import unicodedata

from django.core.exceptions import ValidationError
from django_ratelimit.core import get_usage

from survey.abuse import ratelimit_key

from ..errors import ApiError
from . import redirects

NAME_MAX = 80
# Metadata members we never store or render. `logo_uri` is the one that matters.
DROPPED_MEMBERS = ('logo_uri', 'client_uri', 'policy_uri', 'tos_uri', 'jwks_uri', 'jwks')

LIMITS = (('oauth.dcr.hour', '10/h'), ('oauth.dcr.day', '50/d'))

_WS = re.compile(r'\s+')


def clean_name(value):
    if not isinstance(value, str):
        return ''
    value = ''.join(ch for ch in value if unicodedata.category(ch)[0] != 'C')
    return _WS.sub(' ', value).strip()[:NAME_MAX]


def normalise_metadata(data):
    """Bound the name, drop what we never render, run the redirect rule.
    Returns a new dict; raises ValidationError (code invalid_redirect_uri)."""
    out = {k: v for k, v in data.items() if k not in DROPPED_MEMBERS}
    if 'client_name' in out:
        out['client_name'] = clean_name(out['client_name'])
    uris = out.get('redirect_uris')
    if isinstance(uris, list) and all(isinstance(u, str) for u in uris):
        redirects.check_registrable(uris)
    return out


def limited(request):
    """(True, retry_after_seconds) when this IP has used its budget; counts the attempt."""
    for group, rate in LIMITS:
        usage = get_usage(request, group=group, key=ratelimit_key, rate=rate, increment=True)
        if usage and usage.get('should_limit'):
            return True, int(usage.get('time_left') or 60)
    return False, 0


def rate_limited_response(retry_after):
    err = ApiError(429, 'rate_limited', 'Too many client registrations from this address.',
                   limit='oauth.dcr', retry_after=retry_after)
    err.headers['Retry-After'] = str(retry_after)
    return err.as_response()


def error_response(code, description, status=400):
    """RFC 7591 §3.2.2 error shape (the toolkit's own)."""
    from django.http import JsonResponse
    return JsonResponse({'error': code, 'error_description': description}, status=status)


def rewrite_body(request):
    """Normalise the JSON body in place. Returns an error response, or None.
    A body that is not a JSON object is left for the toolkit to refuse."""
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        data = normalise_metadata(data)
    except ValidationError as exc:
        return error_response('invalid_redirect_uri', '; '.join(exc.messages))
    request._body = json.dumps(data).encode('utf-8')
    return None
