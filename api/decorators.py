"""`@api_endpoint(audience, scopes=())`: the one wrapper every token-authenticated
view goes through.

What it guarantees, in order: no CSRF check (there is no cookie credential to
protect), a principal from the bearer header or a 401, the declared scopes, the
per-token rate windows, then the view. Whatever comes back or is raised is
turned into the envelope with `Cache-Control: no-store`. An unexpected
exception becomes `500 server_error` -- no trace, no model name -- and is
still handed to PostHog, because catching it here is what keeps Django's HTML
500 page off the API; the middleware never sees it.
"""
import logging
from functools import wraps

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from . import limits, rights
from .auth import authenticate
from .errors import SERVER_ERROR, ApiError, finalize, invalid_token

logger = logging.getLogger(__name__)


def _capture(exc, request):
    try:
        import posthog
        if getattr(posthog, 'disabled', True):
            return
        principal = getattr(request, 'principal', None)
        distinct_id = str(principal.user.pk) if principal is not None else None
        posthog.capture_exception(exc, distinct_id=distinct_id, properties={'$request_path': request.path})
    except Exception:  # noqa: BLE001 -- analytics never breaks a response
        logger.debug('posthog: capture_exception failed', exc_info=True)


def api_endpoint(audience, scopes=()):
    def deco(view):
        @csrf_exempt
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            request.principal = None
            try:
                principal = authenticate(request, audience)
                if principal is None:
                    raise invalid_token()
                request.principal = principal
                for scope in scopes:
                    rights.require_scope(principal, scope)
                limits.check_request(principal, request.method)
                response = view(request, *args, **kwargs)
                if not isinstance(response, HttpResponse):
                    response = JsonResponse(response, safe=False)
                return finalize(response)
            except ApiError as err:
                return err.as_response()
            except Exception as exc:  # noqa: BLE001 -- the envelope, then PostHog
                logger.exception('api: unhandled error in %s', getattr(view, '__name__', view))
                _capture(exc, request)
                return ApiError(500, SERVER_ERROR, 'Something went wrong on our side.').as_response()
        return wrapper
    return deco
