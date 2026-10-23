"""Everything a v1 route can raise, turned into the one envelope.

`{"error": <code>, "detail": <text>, ...}` with optional `fields`; codes are
the stable strings of `api.errors`. Service refusals (`survey.services.errors`)
map here, once, so no route answers them differently. An unexpected exception
is a `500 server_error` with no trace and no model name, and still reaches
PostHog -- without the bearer, which `_posthog_scrub_tags` keeps off every
`/api/` capture.
"""
import logging

from django.conf import settings
from django.http import Http404
from ninja import Schema
from ninja.errors import AuthenticationError, HttpError
from ninja.errors import ValidationError as NinjaValidationError

from survey.services import errors as svc

from .. import errors as codes
from ..decorators import _capture
from ..errors import ApiError, invalid_token, not_found

logger = logging.getLogger(__name__)


class ErrorOut(Schema):
    error: str
    detail: str


def resource_metadata_url():
    return settings.OAUTH_ISSUER.rstrip('/') + '/.well-known/oauth-protected-resource/api/'


def _draft_uuid(draft):
    return str(draft.uuid) if draft is not None else None


def from_service_error(err):
    """The API's answer to a `survey.services` refusal."""
    if isinstance(err, svc.ValidationFailed):
        return ApiError(422, codes.VALIDATION, err.message or 'Invalid input.', fields=err.fields)
    if isinstance(err, svc.StructureLocked):
        return ApiError(409, codes.DRAFT_REQUIRED,
                        'This changes the structure of a live survey. Start unpublished changes '
                        '(POST /surveys/{uuid}/draft) and make the edit there.',
                        draft=_draft_uuid(err.draft), reasons=err.reasons)
    if isinstance(err, svc.ContentLocked):
        return ApiError(409, codes.DRAFT_REQUIRED, err.message, draft=_draft_uuid(err.draft), reasons=[])
    if isinstance(err, svc.AnswersAtRisk):
        return ApiError(409, codes.ANSWERS_AT_RISK,
                        f'This deletes {err.count} answers; repeat with acknowledge_answer_loss=true.',
                        count=err.count)
    if isinstance(err, svc.DeleteBlocked):
        return ApiError(409, codes.DELETE_BLOCKED, err.message)
    if isinstance(err, svc.TranslationGaps):
        return ApiError(409, codes.TRANSLATION_GAPS,
                        'Some languages are missing translations; repeat with '
                        'acknowledge_translation_gaps=true to publish anyway.', gaps=err.gaps)
    if isinstance(err, svc.IncompatibleDraft):
        return ApiError(409, codes.INCOMPATIBLE_DRAFT,
                        'The unpublished changes conflict with collected answers; repeat with force=true '
                        'to publish anyway.', issues=err.issues)
    if isinstance(err, svc.TransitionRefused):
        return ApiError(409, codes.TRANSITION_REFUSED, err.message)
    return ApiError(409, codes.CONFLICT, err.message or 'Conflict.')


def _field_name(loc):
    """A pydantic error location as the field a client sent: drop `body`,
    the payload parameter's name and list indices' parents stay."""
    parts = [str(p) for p in loc if p not in ('body', 'query', 'path', 'form', 'file')]
    if len(parts) > 1 and parts[0] in ('payload', 'params', 'data'):
        parts = parts[1:]
    return '.'.join(parts) or '__all__'


def from_validation_error(exc):
    fields = {}
    for e in exc.errors:
        name = _field_name(e.get('loc', ()))
        msg = 'Unknown field.' if e.get('type') == 'extra_forbidden' else e.get('msg', 'Invalid value.')
        fields.setdefault(name, []).append(msg)
    unknown = sorted(n for n, msgs in fields.items() if 'Unknown field.' in msgs)
    detail = 'Unknown field(s): ' + ', '.join(unknown) if unknown else 'Invalid input.'
    return ApiError(422, codes.VALIDATION, detail, fields=fields)


def register(api):
    @api.exception_handler(ApiError)
    def _api_error(request, exc):
        if exc.code == codes.INVALID_TOKEN:
            exc.headers['WWW-Authenticate'] = invalid_token(resource_metadata_url()).headers['WWW-Authenticate']
        return exc.as_response()

    @api.exception_handler(svc.ServiceError)
    def _service_error(request, exc):
        return from_service_error(exc).as_response()

    @api.exception_handler(NinjaValidationError)
    def _validation(request, exc):
        return from_validation_error(exc).as_response()

    @api.exception_handler(AuthenticationError)
    def _auth(request, exc):
        return _api_error(request, invalid_token())

    @api.exception_handler(Http404)
    def _404(request, exc):
        return not_found().as_response()

    @api.exception_handler(HttpError)
    def _http_error(request, exc):
        status = exc.status_code
        code = codes.NOT_FOUND if status == 404 else (codes.VALIDATION if status in (400, 422) else codes.CONFLICT)
        return ApiError(status, code, str(exc) or 'Error.').as_response()

    @api.exception_handler(Exception)
    def _unexpected(request, exc):
        logger.exception('api v1: unhandled error on %s', request.path)
        _capture(exc, request)
        return ApiError(500, codes.SERVER_ERROR, 'Something went wrong on our side.').as_response()
