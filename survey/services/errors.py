"""Refusals a service raises. Each surface maps them to its own response:
the editor to the status and body it always returned, the API to its
envelope (`api/v1/errors.py`). Nothing here knows about HTTP."""


class ServiceError(Exception):
    code = 'service_error'

    def __init__(self, message='', **extra):
        super().__init__(message or self.code)
        self.message = message
        self.extra = extra


class ValidationFailed(ServiceError):
    """Input refused before anything was written. `fields` maps a field name
    (or `__all__`) to a list of messages; `form` is the bound form when one
    did the validating, so the editor can re-render it."""
    code = 'validation'

    def __init__(self, fields, form=None, message=''):
        super().__init__(message or 'Invalid input.')
        self.fields = {k: [str(m) for m in v] for k, v in dict(fields).items()}
        self.form = form

    @classmethod
    def single(cls, field, message):
        return cls({field: [message]}, message=message)


class ContentLocked(ServiceError):
    """Nothing may be edited on this survey now: it is live and has
    unpublished changes (publishing them would overwrite the edit), or live
    editing is switched off. `draft` is the unpublished-changes survey, if any."""
    code = 'content_locked'

    def __init__(self, message, draft=None):
        super().__init__(message)
        self.draft = draft


class StructureLocked(ServiceError):
    """A structural change on a live survey: it belongs on the unpublished
    changes. `reasons` are the `versioning.structural_*` strings (empty for a
    plain structural operation such as add or delete)."""
    code = 'structure_locked'

    def __init__(self, message, reasons=(), draft=None):
        super().__init__(message)
        self.reasons = list(reasons)
        self.draft = draft


class AnswersAtRisk(ServiceError):
    code = 'answers_at_risk'

    def __init__(self, count, explain_versioning=False):
        super().__init__(f'{count} answers would be deleted.')
        self.count = count
        self.explain_versioning = explain_versioning


class DeleteBlocked(ServiceError):
    """The delete would orphan something that refers to the object; `body`
    is what the editor has always answered with (a JSON-able dict)."""
    code = 'delete_blocked'

    def __init__(self, message, body=None):
        super().__init__(message)
        self.body = body or {}


class TransitionRefused(ServiceError):
    code = 'transition_refused'


class EmailUnconfirmed(ServiceError):
    """The acting account has not confirmed its email address, and nothing goes
    live from an unconfirmed address: publishing waits for it (change
    login-grace-period, #487)."""
    code = 'email_unconfirmed'

    def __init__(self, message='Confirm your email address to publish.'):
        super().__init__(message)


class TranslationGaps(ServiceError):
    code = 'translation_gaps'

    def __init__(self, gaps):
        super().__init__('Some languages are missing translations.')
        self.gaps = gaps


class IncompatibleDraft(ServiceError):
    code = 'incompatible_draft'

    def __init__(self, issues):
        super().__init__('The unpublished changes are incompatible with collected answers.')
        self.issues = issues


class Conflict(ServiceError):
    code = 'conflict'


class LimitReached(ServiceError):
    """A size or count cap the operation would exceed (a survey copy holding
    too many attachment bytes)."""
    code = 'limit_reached'
