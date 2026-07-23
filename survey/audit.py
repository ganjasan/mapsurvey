"""Append-only audit trail for destructive/lifecycle editor operations.

Mirrors the survey.events.emit_event contract: writing an audit record must
never break the operation it observes, so audit() swallows all exceptions.
See openspec/changes/survey-deletion-safety/design.md (D5).
"""
import logging

from .abuse import client_ip

logger = logging.getLogger(__name__)


def audit(request, action, survey=None, **metadata):
    """Write an AuditLog row. Silently swallows all exceptions.

    Args:
        request: the current HttpRequest (actor + client IP are read from it)
        action: string matching AuditLog.ACTION_CHOICES keys
        survey: optional SurveyHeader whose uuid/name identify the target
        **metadata: extra context stored in the metadata JSONField
    """
    from .models import AuditLog  # local import avoids circular at module load

    try:
        actor = request.user if request.user.is_authenticated else None
        AuditLog.objects.create(
            actor=actor,
            action=action,
            survey_uuid=survey.uuid if survey else None,
            survey_name=survey.name if survey else '',
            ip=client_ip(request) or None,
            metadata=metadata,
        )
    except Exception:
        logger.exception("audit: failed to record %s", action)
