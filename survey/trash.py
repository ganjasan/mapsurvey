"""Trash lifecycle for surveys: soft-delete, restore, permanent purge.

Trash sets SurveyHeader.deleted_at (design D1); the survey disappears from
the dashboard and public URLs but keeps all data. Purge reproduces the old
hard-delete cascade plus media cleanup and also covers satellites the old
code missed (live draft copies). See
openspec/changes/survey-deletion-safety/design.md (D3, D7).
"""
from datetime import timedelta

from django.utils import timezone

from .models import SurveyHeader, SurveySession, Question


def trash_survey(survey):
    """Move a survey to trash (soft-delete)."""
    survey.deleted_at = timezone.now()
    survey.save(update_fields=['deleted_at'])


def restore_survey(survey):
    """Restore a trashed survey to its exact pre-trash state."""
    survey.deleted_at = None
    survey.save(update_fields=['deleted_at'])


def purge_survey(survey):
    """Permanently delete a survey, its versions/drafts, sessions and media.

    Media files are removed through the Django storage API only (works for
    both local disk and S3). Sessions are deleted explicitly because
    SurveySession.survey uses PROTECT.
    """
    headers = [survey]
    headers += list(SurveyHeader.objects.filter(canonical_survey=survey, is_canonical=False))
    headers += list(SurveyHeader.objects.filter(published_version=survey))

    # Media cleanup before the DB cascade removes the file references
    for header in headers:
        if header.cover_image:
            header.cover_image.delete(save=False)
    questions = Question.objects.filter(survey_section__survey_header__in=headers).exclude(image='')
    for question in questions:
        if question.image:
            question.image.delete(save=False)

    # Sessions first (PROTECT FK prevents cascade deletion), then headers.
    # The canonical goes last so version/draft self-FKs never dangle mid-loop.
    for header in headers:
        SurveySession.objects.filter(survey=header).delete()
    for header in reversed(headers):
        header.delete()


def purge_expired_surveys(days=None, dry_run=False, log=lambda msg: None):
    """Purge all surveys whose trash retention window has expired.

    Shared core behind the purge_trashed_surveys management command and the
    /internal/purge-trash/ endpoint. Writes a survey_auto_purge audit row
    per survey (no actor). Returns the number of surveys purged (or that
    would be purged, when dry_run).
    """
    from .models import AuditLog

    if days is None:
        days = SurveyHeader.TRASH_RETENTION_DAYS
    cutoff = timezone.now() - timedelta(days=days)
    expired = list(SurveyHeader.objects.filter(deleted_at__lt=cutoff))

    for survey in expired:
        if dry_run:
            log(f"Would purge '{survey.name}' ({survey.uuid}), trashed {survey.deleted_at:%Y-%m-%d}")
            continue
        AuditLog.objects.create(
            actor=None,
            action='survey_auto_purge',
            survey_uuid=survey.uuid,
            survey_name=survey.name,
            metadata={'trashed_at': survey.deleted_at.isoformat(), 'retention_days': days},
        )
        purge_survey(survey)
        log(f"Purged '{survey.name}' ({survey.uuid})")

    return len(expired)
