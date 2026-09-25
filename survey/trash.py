"""Trash lifecycle for surveys: soft-delete, restore, permanent purge.

Trash sets SurveyHeader.deleted_at (design D1); the survey disappears from
the dashboard and public URLs but keeps all data. Purge reproduces the old
hard-delete cascade plus media cleanup and also covers satellites the old
code missed (live draft copies). See
openspec/changes/survey-deletion-safety/design.md (D3, D7).
"""
import logging
from collections import namedtuple
from datetime import timedelta

from django.utils import timezone

from .models import (
    SurveyHeader, SurveySession, Question, SurveyMapLayer, LayerObjectAsset,
)

logger = logging.getLogger(__name__)

#: Result of one auto-purge run. `purged` counts surveys deleted (or, under
#: dry_run, those that would be); `failed` counts the ones that raised and
#: were skipped so the rest of the run could proceed.
PurgeRun = namedtuple('PurgeRun', ['purged', 'failed'])


def trash_survey(survey):
    """Move a survey to trash (soft-delete)."""
    survey.deleted_at = timezone.now()
    survey.save(update_fields=['deleted_at'])


def restore_survey(survey):
    """Restore a trashed survey to its exact pre-trash state."""
    survey.deleted_at = None
    survey.save(update_fields=['deleted_at'])


def purge_survey(survey):
    """Permanently delete a survey, its versions/drafts, sessions, layers and media.

    Media files are removed through the Django storage API only (works for
    both local disk and S3). Sessions and reference layers are handled
    explicitly because each sits behind a PROTECT FK.
    """
    headers = [survey]
    headers += list(SurveyHeader.objects.filter(canonical_survey=survey, is_canonical=False))
    headers += list(SurveyHeader.objects.filter(published_version=survey))

    # Media cleanup before the DB cascade removes the file references
    for header in headers:
        if header.cover_image:
            header.cover_image.delete(save=False)
    # Versions and drafts share one image-basemap file name; delete each once,
    # after checking nothing outside this family still names it.
    image_names = {h.image_basemap.name for h in headers if h.image_basemap}
    header_ids = [h.pk for h in headers]
    for name in image_names:
        if not SurveyHeader.objects.filter(image_basemap=name).exclude(pk__in=header_ids).exists():
            SurveyHeader._meta.get_field('image_basemap').storage.delete(name)
    questions = Question.objects.filter(survey_section__survey_header__in=headers).exclude(image='')
    for question in questions:
        if question.image:
            question.image.delete(save=False)
    assets = LayerObjectAsset.objects.filter(
        object__layer__survey__in=headers,
    ).exclude(file='')
    for asset in assets:
        if asset.file:
            asset.file.delete(save=False)

    # Sessions first (PROTECT FK prevents cascade deletion), then the layers,
    # then the headers. The canonical goes last so version/draft self-FKs never
    # dangle mid-loop.
    for header in headers:
        SurveySession.objects.filter(survey=header).delete()

    # Question.layer is PROTECT so that deleting a layer on its own refuses and
    # names the bound question. Django evaluates PROTECT while collecting rows,
    # without exempting a question that is itself being collected, so the
    # binding has to go before the layers do. Scope it through the headers, not
    # through the layers: a question in a survey that is not being purged must
    # keep its binding. Nulling rather than deleting leaves the question to the
    # header cascade, which already orders answers and sub-questions correctly.
    Question.objects.filter(
        survey_section__survey_header__in=headers, layer__isnull=False,
    ).update(layer=None)
    SurveyMapLayer.objects.filter(survey__in=headers).delete()

    for header in reversed(headers):
        header.delete()


def purge_expired_surveys(days=None, dry_run=False, log=lambda msg: None):
    """Purge all surveys whose trash retention window has expired.

    Shared core behind the purge_trashed_surveys management command and the
    /internal/purge-trash/ endpoint. Writes a survey_auto_purge audit row
    per survey (no actor). Returns a PurgeRun of how many surveys were purged
    (or would be, when dry_run) and how many failed.

    One survey that cannot be purged does not end the run: the next one is
    still owed its retention. The failure is logged and counted rather than
    swallowed — a purge that silently stops is how a survey stayed undeleted
    for two days without anyone knowing.
    """
    from .models import AuditLog

    if days is None:
        days = SurveyHeader.TRASH_RETENTION_DAYS
    cutoff = timezone.now() - timedelta(days=days)
    expired = list(SurveyHeader.objects.filter(deleted_at__lt=cutoff))

    purged = 0
    failed = 0
    for survey in expired:
        if dry_run:
            log(f"Would purge '{survey.name}' ({survey.uuid}), trashed {survey.deleted_at:%Y-%m-%d}")
            purged += 1
            continue
        AuditLog.objects.create(
            actor=None,
            action='survey_auto_purge',
            survey_uuid=survey.uuid,
            survey_name=survey.name,
            metadata={'trashed_at': survey.deleted_at.isoformat(), 'retention_days': days},
        )
        try:
            purge_survey(survey)
        except Exception:
            failed += 1
            logger.exception("Purge failed for survey %s (%s)", survey.uuid, survey.name)
            log(f"FAILED to purge '{survey.name}' ({survey.uuid})")
            continue
        purged += 1
        log(f"Purged '{survey.name}' ({survey.uuid})")

    return PurgeRun(purged=purged, failed=failed)
