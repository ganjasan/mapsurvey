"""Trash lifecycle for surveys: soft-delete, restore, permanent purge.

Trash sets SurveyHeader.deleted_at (design D1); the survey disappears from
the dashboard and public URLs but keeps all data. Purge reproduces the old
hard-delete cascade plus media cleanup and also covers satellites the old
code missed (live draft copies). See
openspec/changes/survey-deletion-safety/design.md (D3, D7).
"""
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
